# GitHub Achievement Hunter

An automated Python tool designed to help users obtain specific GitHub achievements through programmatic interactions with GitHub's API.

## Overview

GitHub Achievement Hunter automates the process of earning 5 specific GitHub achievements by creating repositories, issues, pull requests, and managing collaborative activities between two GitHub accounts.

### Supported Achievements

- **Pull Shark** 🦈 - Merge 2, 16, 128, and 1024 pull requests
- **Quickdraw** ⚡ - Close an issue within 5 minutes of opening
- **Pair Extraordinaire** 👥 - Coauthor 10, 24, and 48 commits
- **Galaxy Brain** 🧠 - Get 8, 16, 32, and 64 answers accepted on discussions
- **YOLO** 🚀 - Merge a pull request without a review

## Requirements

- Python 3.8+
- Two GitHub accounts (primary and secondary)
- GitHub Personal Access Tokens for both accounts

## Installation

### Method 1: Quick Setup (Recommended)

1. Clone the repository:
```bash
git clone https://github.com/yourusername/github-achievement-hunter.git
cd github-achievement-hunter
```

2. Run the setup script:
```bash
chmod +x scripts/setup.sh
./scripts/setup.sh
```

3. Configure your GitHub credentials in `.env`:
```bash
GITHUB_PRIMARY_TOKEN=your_primary_token_here
GITHUB_SECONDARY_TOKEN=your_secondary_token_here
```

### Method 2: Manual Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/github-achievement-hunter.git
cd github-achievement-hunter
```

2. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Copy the environment variables template:
```bash
cp .env.example .env
```

5. Configure your GitHub credentials in `.env`:
```bash
GITHUB_PRIMARY_TOKEN=your_primary_token_here
GITHUB_SECONDARY_TOKEN=your_secondary_token_here
```

### Method 3: Package Installation

```bash
pip install git+https://github.com/yourusername/github-achievement-hunter.git
```

After installation, the `github-achievement-hunter` command will be available globally.

## Configuration

Edit `config/config.yaml` to customize:

- GitHub account details
- Repository name and description
- Which achievements to target
- Batch sizes and rate limits
- Progress tracking settings

### Example Configuration

```yaml
github:
  primary_account:
    username: "your-primary-username"
    token: "${GITHUB_PRIMARY_TOKEN}"
  secondary_account:
    username: "your-secondary-username"
    token: "${GITHUB_SECONDARY_TOKEN}"

achievements:
  pull_shark:
    enabled: true
    target_count: 1024
  quickdraw:
    enabled: true
  # ... more achievements
```

## Usage

Run the achievement hunter:

```bash
python main.py
```

### Command Line Options

```bash
# Show help and all available options
python main.py --help

# Run specific achievements only
python main.py --achievements quickdraw yolo pull_shark

# Run all achievements
python main.py --achievements all

# Dry run mode (no actual API calls)
python main.py --dry-run

# Use custom configuration file
python main.py --config path/to/config.yaml

# Set custom progress file
python main.py --progress-file my-progress.json

# Set logging level
python main.py --log-level DEBUG
```

### Examples

```bash
# Run only Quickdraw and YOLO achievements
python main.py -a quickdraw yolo

# Run with debug logging and dry-run mode
python main.py --log-level DEBUG --dry-run

# Use custom config and run specific achievements
python main.py -c custom-config.yaml -a pair_extraordinaire galaxy_brain
```

## Progress Tracking

The tool automatically saves progress to `progress.json` and can resume from interruptions. Progress includes:

- Completed achievements
- Current counts for each achievement
- Last successful operation timestamps

## Rate Limiting

The tool respects GitHub's API rate limits:
- Implements exponential backoff with automatic retry
- Batches operations where possible
- Tracks remaining API calls and warns when low
- Pauses execution when rate limit is exceeded
- Estimated completion time: ~20-30 hours for all achievements

### API Rate Limits
- **Authenticated requests**: 5,000 per hour
- **GraphQL requests**: 5,000 points per hour
- **Secondary rate limits**: May apply for rapid creation of content

The tool automatically handles rate limiting, but you can monitor API usage in the logs.

## Project Structure

```
github_achievement_hunter/
├── achievements/       # Achievement-specific modules
├── utils/             # Helper utilities
├── config/            # Configuration files
├── logs/              # Application logs
└── main.py           # Entry point
```

## Troubleshooting

### Common Issues

**Authentication Failed**
- Verify your GitHub tokens have the required scopes: `repo`, `workflow`, `write:discussion`
- Check that tokens are correctly set in `.env` file
- Ensure tokens haven't expired

**Rate Limit Exceeded**
- The tool will automatically wait and retry
- Consider running fewer achievements at once
- Use `--log-level DEBUG` to see detailed rate limit information

**Permission Denied**
- Ensure both accounts have appropriate permissions
- For Galaxy Brain, enable GitHub Discussions on the repository
- Check repository settings allow issues and pull requests

**Module Not Found**
- Ensure you're in the project directory
- Activate the virtual environment: `source venv/bin/activate`
- Reinstall dependencies: `pip install -r requirements.txt`

### Debug Mode

Run with debug logging to see detailed information:
```bash
python main.py --log-level DEBUG
```

Check logs in the `logs/` directory for detailed error messages.

## Security

- Never commit tokens or credentials
- Use environment variables for sensitive data
- All credentials are stored securely
- `.gitignore` configured for safety
- Tokens should have minimal required scopes

## Compliance

This tool is designed for personal use and educational purposes. Users are responsible for:
- Following GitHub's Terms of Service
- Using only their own accounts
- Respecting rate limits
- Not using the tool for spam or abuse

## Contributing

Contributions are welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Open a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Disclaimer

This tool automates GitHub activities. Use responsibly and in accordance with GitHub's Terms of Service. The authors are not responsible for any misuse or consequences of using this tool.