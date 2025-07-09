#!/bin/bash
# GitHub Achievement Hunter Setup Script
# This script sets up the development environment for the GitHub Achievement Hunter

set -e  # Exit on error

echo "==================================="
echo "GitHub Achievement Hunter Setup"
echo "==================================="
echo ""

# Check Python version
echo "Checking Python version..."
python_version=$(python3 --version 2>&1 | awk '{print $2}')
required_version="3.8"

if [ "$(printf '%s\n' "$required_version" "$python_version" | sort -V | head -n1)" != "$required_version" ]; then 
    echo "Error: Python $required_version or higher is required. Found: $python_version"
    exit 1
fi
echo "✓ Python $python_version found"
echo ""

# Create virtual environment
echo "Creating virtual environment..."
if [ -d "venv" ]; then
    echo "Virtual environment already exists. Skipping creation."
else
    python3 -m venv venv
    echo "✓ Virtual environment created"
fi
echo ""

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate
echo "✓ Virtual environment activated"
echo ""

# Upgrade pip
echo "Upgrading pip..."
pip install --upgrade pip
echo "✓ pip upgraded"
echo ""

# Install dependencies
echo "Installing dependencies..."
pip install -r requirements.txt
echo "✓ Dependencies installed"
echo ""

# Create necessary directories
echo "Creating necessary directories..."
mkdir -p config logs
echo "✓ Directories created"
echo ""

# Copy example files
echo "Setting up configuration files..."
if [ ! -f ".env" ]; then
    if [ -f ".env.example" ]; then
        cp .env.example .env
        echo "✓ Created .env file from template"
    else
        echo "⚠ Warning: .env.example not found. Creating empty .env file."
        touch .env
    fi
else
    echo "✓ .env file already exists"
fi

if [ ! -f "config/config.yaml" ]; then
    if [ -f "config/config.yaml.example" ]; then
        cp config/config.yaml.example config/config.yaml
        echo "✓ Created config.yaml from template"
    else
        echo "⚠ Warning: config.yaml.example not found"
    fi
else
    echo "✓ config.yaml already exists"
fi
echo ""

# Make main.py executable
if [ -f "main.py" ]; then
    chmod +x main.py
    echo "✓ Made main.py executable"
fi
echo ""

echo "==================================="
echo "Setup Complete!"
echo "==================================="
echo ""
echo "Next steps:"
echo "1. Edit .env file with your GitHub tokens:"
echo "   - GITHUB_PRIMARY_TOKEN=your_primary_token"
echo "   - GITHUB_SECONDARY_TOKEN=your_secondary_token"
echo ""
echo "2. Edit config/config.yaml with your GitHub usernames and preferences"
echo ""
echo "3. Activate the virtual environment:"
echo "   source venv/bin/activate"
echo ""
echo "4. Run the achievement hunter:"
echo "   python main.py --help"
echo ""
echo "For more information, see README.md"