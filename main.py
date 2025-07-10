#!/usr/bin/env python3
"""
GitHub Achievement Hunter - Main Entry Point

This is the main CLI interface for the GitHub Achievement Hunter tool.
It orchestrates all achievement hunters and manages the hunting process.
"""

import argparse
import sys
from github_achievement_hunter.utils.config import ConfigLoader
from github_achievement_hunter.utils.auth import GitHubAuthenticator
from github_achievement_hunter.utils.github_client import GitHubClient
from github_achievement_hunter.utils.progress_tracker import ProgressTracker
from github_achievement_hunter.utils.logger import AchievementLogger
from github_achievement_hunter.achievements import (
    QuickdrawHunter, YoloHunter, PullSharkHunter,
    PairExtraordinaireHunter, GalaxyBrainHunter
)


def main():
    """Main entry point for the GitHub Achievement Hunter CLI."""
    parser = argparse.ArgumentParser(
        description='GitHub Achievement Hunter - Automate earning GitHub achievements'
    )
    parser.add_argument(
        '--config', '-c',
        default='config/config.yaml',
        help='Path to configuration file'
    )
    parser.add_argument(
        '--achievements', '-a',
        nargs='+',
        choices=['quickdraw', 'yolo', 'pull_shark', 'pair_extraordinaire', 'galaxy_brain', 'all'],
        default=['all'],
        help='Achievements to hunt'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Run in dry-run mode (no actual API calls)'
    )
    parser.add_argument(
        '--progress-file',
        default='progress.json',
        help='Path to progress tracking file'
    )
    parser.add_argument(
        '--log-level',
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
        default='INFO',
        help='Logging level'
    )
    
    args = parser.parse_args()
    
    # Initialize components
    config = ConfigLoader(args.config)
    logger = AchievementLogger(args.log_level).get_logger()
    progress = ProgressTracker(args.progress_file)
    
    # Set dry-run in config if specified
    if args.dry_run:
        config.config['settings']['dry_run'] = True
    
    # Initialize GitHub clients
    primary_auth = GitHubAuthenticator.from_config(config.config['github']['primary_account'])
    primary_client = GitHubClient(primary_auth, config.config['settings']['rate_limit_buffer'])
    
    # Secondary account is optional - only initialize if configured
    secondary_auth = None
    secondary_client = None
    if config.config['github'].get('secondary_account'):
        try:
            secondary_auth = GitHubAuthenticator.from_config(config.config['github']['secondary_account'])
            secondary_client = GitHubClient(secondary_auth, config.config['settings']['rate_limit_buffer'])
            logger.info("Secondary account authenticated successfully")
        except Exception as e:
            logger.warning(f"Failed to authenticate secondary account: {e}")
            if any(achievement in ['pull_shark', 'pair_extraordinaire', 'galaxy_brain'] for achievement in achievements_to_run):
                logger.error("Secondary account is required for multi-account achievements")
                sys.exit(1)
    
    # Determine which achievements to run
    achievements_to_run = args.achievements
    if 'all' in achievements_to_run:
        achievements_to_run = ['quickdraw', 'yolo', 'pull_shark', 'pair_extraordinaire', 'galaxy_brain']
    
    # Initialize hunters
    hunters = {
        'quickdraw': QuickdrawHunter,
        'yolo': YoloHunter,
        'pull_shark': PullSharkHunter,
        'pair_extraordinaire': PairExtraordinaireHunter,
        'galaxy_brain': GalaxyBrainHunter
    }
    
    # Run selected achievement hunters
    for achievement in achievements_to_run:
        if achievement in hunters and config.config['achievements'][achievement]['enabled']:
            logger.info(f'\nStarting {achievement} achievement hunter...')
            
            # Initialize hunter based on its requirements
            if achievement in ['quickdraw', 'yolo']:
                # These hunters only need primary client
                hunter = hunters[achievement](
                    primary_client, progress, config
                )
            else:
                # These hunters need both clients
                hunter = hunters[achievement](
                    primary_client, secondary_client, progress, config
                )
            
            try:
                hunter.run()
            except Exception as e:
                logger.error(f'Failed to complete {achievement}: {e}')
                if not config.config['settings'].get('continue_on_error', True):
                    sys.exit(1)
    
    logger.info('\nAchievement hunting complete!')
    logger.info('Check your GitHub profile for unlocked achievements.')


if __name__ == '__main__':
    main()