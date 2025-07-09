#!/usr/bin/env python3
"""Setup script for GitHub Achievement Hunter."""

from setuptools import setup, find_packages
import os

# Read the README file
with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

# Read requirements
with open("requirements.txt", "r", encoding="utf-8") as fh:
    requirements = [line.strip() for line in fh if line.strip() and not line.startswith("#")]

setup(
    name="github-achievement-hunter",
    version="1.0.0",
    author="GitHub Achievement Hunter Contributors",
    description="Automated tool for earning GitHub achievements",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/github-achievement-hunter",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Version Control :: Git",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.8",
    install_requires=requirements,
    entry_points={
        "console_scripts": [
            "github-achievement-hunter=main:main",
        ],
    },
    include_package_data=True,
    package_data={
        "github_achievement_hunter": ["../config/*.example"],
    },
)