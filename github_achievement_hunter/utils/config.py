import os
import re
import yaml
from typing import Any, Dict, Optional, Union
from pathlib import Path

from .logger import AchievementLogger, log_context, log_errors


class ConfigError(Exception):
    """Raised when there's an error in configuration loading or validation."""
    pass


class ConfigLoader:
    """
    Loads and manages configuration from YAML files with environment variable substitution.
    
    Features:
    - Load configuration from YAML files
    - Environment variable substitution using ${VAR_NAME} syntax
    - Configuration validation
    - Dot notation access for nested values
    - Default values for optional settings
    """
    
    def __init__(self, config_path: str = 'config/config.yaml'):
        """
        Initialize the ConfigLoader.
        
        Args:
            config_path: Path to the configuration file
        """
        self.logger = AchievementLogger().get_logger()
        self.config_path = Path(config_path)
        
        with log_context(f"Loading configuration from {config_path}", self.logger):
            self.config = self._load_config()
            self.config = self._substitute_env_vars(self.config)
            self._apply_defaults()
            self._validate_config()
            
        self.logger.info(f"Configuration loaded successfully from {self.config_path}")
    
    @log_errors(reraise=True)
    def _load_config(self) -> Dict[str, Any]:
        """
        Load configuration from YAML file.
        
        Returns:
            Dictionary containing the configuration
            
        Raises:
            ConfigError: If the file cannot be read or parsed
        """
        if not self.config_path.exists():
            self.logger.error(f"Configuration file not found: {self.config_path}")
            raise ConfigError(f"Configuration file not found: {self.config_path}")
        
        try:
            with open(self.config_path, 'r') as f:
                config = yaml.safe_load(f)
                if config is None:
                    self.logger.debug("Empty configuration file, returning empty dict")
                    return {}
                self.logger.debug(f"Loaded {len(config)} top-level configuration sections")
                return config
        except yaml.YAMLError as e:
            self.logger.error(f"YAML parsing error: {e}")
            raise ConfigError(f"Error parsing YAML file: {e}")
        except Exception as e:
            self.logger.error(f"Failed to read configuration file: {e}")
            raise ConfigError(f"Error reading configuration file: {e}")
    
    def _substitute_env_vars(self, obj: Any) -> Any:
        """
        Recursively substitute environment variables in the configuration.
        
        Replaces ${VAR_NAME} with the value of environment variable VAR_NAME.
        
        Args:
            obj: The object to process
            
        Returns:
            The processed object with environment variables substituted
        """
        
        if isinstance(obj, dict):
            return {k: self._substitute_env_vars(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._substitute_env_vars(item) for item in obj]
        elif isinstance(obj, str):
            # Find all ${VAR_NAME} patterns
            pattern = re.compile(r'\$\{([^}]+)\}')
            
            def replacer(match):
                var_name = match.group(1)
                value = os.getenv(var_name)
                if value is None:
                    # Keep the original placeholder if env var not found
                    self.logger.warning(f"Environment variable {var_name} not found, keeping placeholder")
                    return match.group(0)
                self.logger.debug(f"Substituted environment variable {var_name}")
                return value
            
            return pattern.sub(replacer, obj)
        else:
            return obj
    
    def _apply_defaults(self):
        """Apply default values for optional configuration settings."""
        defaults = {
            'github': {
                'rate_limit': {
                    'requests_per_hour': 4500,
                    'request_delay': 0.8
                }
            },
            'notifications': {
                'enabled': True,
                'methods': {
                    'console': True,
                    'email': False,
                    'webhook': {
                        'enabled': False
                    }
                },
                'triggers': {
                    'achievement_unlock': True,
                    'milestone_progress': True,
                    'daily_summary': False
                }
            },
            'database': {
                'type': 'sqlite',
                'sqlite': {
                    'path': './data/achievements.db'
                }
            },
            'logging': {
                'level': 'INFO',
                'file': {
                    'enabled': True,
                    'path': './logs/achievement_hunter.log',
                    'max_size_mb': 10,
                    'backup_count': 5
                },
                'console': {
                    'enabled': True,
                    'colorized': True
                }
            },
            'monitoring': {
                'dashboard': {
                    'enabled': True,
                    'port': 8080,
                    'host': '0.0.0.0'
                },
                'metrics': {
                    'enabled': True,
                    'interval_seconds': 300
                }
            },
            'cache': {
                'enabled': True,
                'backend': 'memory',
                'ttl': 3600
            },
            'scheduler': {
                'enabled': True,
                'schedule': '0 * * * *',
                'timezone': 'UTC'
            },
            'advanced': {
                'retry': {
                    'enabled': True,
                    'max_attempts': 3,
                    'backoff_factor': 2
                },
                'timeout': 30,
                'user_agent': 'GitHub-Achievement-Hunter/1.0',
                'debug': False
            }
        }
        
        # Deep merge defaults with loaded config
        self.config = self._deep_merge(defaults, self.config)
    
    def _deep_merge(self, default: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
        """
        Deep merge two dictionaries, with override taking precedence.
        
        Args:
            default: The default dictionary
            override: The override dictionary
            
        Returns:
            Merged dictionary
        """
        result = default.copy()
        
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value
        
        return result
    
    @log_errors(reraise=True)
    def _validate_config(self):
        """
        Validate the configuration to ensure all required fields exist and are valid.
        
        Raises:
            ConfigError: If validation fails
        """
        self.logger.debug("Validating configuration")
        
        # Check required fields
        required_fields = [
            'github.token',
            'target.username',
            'achievements'
        ]
        
        for field in required_fields:
            if self.get(field) is None:
                raise ConfigError(f"Required configuration field missing: {field}")
        
        # Validate GitHub token format (should not be a placeholder)
        token = self.get('github.token')
        if token and token.startswith('${') and token.endswith('}'):
            raise ConfigError(f"GitHub token not set. Please set the {token[2:-1]} environment variable.")
        
        # Validate achievement targets are positive integers
        achievements = self.get('achievements', {})
        for key, value in achievements.items():
            if key == 'language_repos':
                if isinstance(value, dict):
                    for lang, count in value.items():
                        if not isinstance(count, int) or count < 0:
                            raise ConfigError(f"Achievement target for {lang} repositories must be a positive integer")
            else:
                if not isinstance(value, int) or value < 0:
                    raise ConfigError(f"Achievement target '{key}' must be a positive integer")
        
        # Validate database configuration
        db_type = self.get('database.type')
        if db_type not in ['sqlite', 'postgresql', 'mysql']:
            raise ConfigError(f"Invalid database type: {db_type}")
        
        # Validate log level
        log_level = self.get('logging.level')
        valid_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
        if log_level not in valid_levels:
            raise ConfigError(f"Invalid log level: {log_level}. Must be one of {valid_levels}")
        
        # Validate port numbers
        dashboard_port = self.get('monitoring.dashboard.port')
        if not isinstance(dashboard_port, int) or dashboard_port < 1 or dashboard_port > 65535:
            raise ConfigError("Dashboard port must be between 1 and 65535")
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        Get a configuration value using dot notation.
        
        Args:
            key: The configuration key (e.g., 'github.token' or 'achievements.stars')
            default: Default value to return if key not found
            
        Returns:
            The configuration value or default if not found
        """
        keys = key.split('.')
        value = self.config
        
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        
        return value
    
    def set(self, key: str, value: Any):
        """
        Set a configuration value using dot notation.
        
        Args:
            key: The configuration key (e.g., 'github.token')
            value: The value to set
        """
        keys = key.split('.')
        config = self.config
        
        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]
        
        config[keys[-1]] = value
    
    def get_all(self) -> Dict[str, Any]:
        """
        Get the entire configuration dictionary.
        
        Returns:
            The complete configuration dictionary
        """
        return self.config.copy()
    
    def reload(self):
        """Reload the configuration from file."""
        self.logger.info("Reloading configuration")
        with log_context("Configuration reload", self.logger):
            self.config = self._load_config()
            self.config = self._substitute_env_vars(self.config)
            self._apply_defaults()
            self._validate_config()
        self.logger.info("Configuration reloaded successfully")