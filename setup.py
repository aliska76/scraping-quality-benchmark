#!/usr/bin/env python3
"""
Project installer for Tavily Scraping Assignment.
Run on Windows, Mac and Linux.
"""

import subprocess
import sys
import platform
import os
from pathlib import Path

def print_step(message):
    """Steps"""
    print("\n" + "=" * 60)
    print(f"[STEP] {message}")
    print("=" * 60)

def run_command(cmd, shell=False):
    """Runs a command and returns the result."""
    try:
        if shell and platform.system() == "Windows":
            result = subprocess.run(cmd, shell=True, check=True, capture_output=True, text=True)
        else:
            result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        return True, result.stdout
    except subprocess.CalledProcessError as e:
        return False, e.stderr

def setup():
    """The main function of the installation"""
    
    print("\n" + "=" * 60)
    print("   Tavily Scraping Assignment - Setup")
    print("=" * 60)
    
    # Determine the OS
    system = platform.system()
    print(f"\n[INFO] Operating System: {system}")
    
    # Step 1: Check Python
    print_step("Step 1: Checking Python...")
    
    python_version = sys.version_info
    if python_version.major < 3 or (python_version.major == 3 and python_version.minor < 8):
        print("[ERROR] Python 3.8 or higher is required!")
        print(f"        Your version: {python_version.major}.{python_version.minor}")
        sys.exit(1)
    
    print(f"[OK] Python {python_version.major}.{python_version.minor}.{python_version.micro}")
    
    # Step 2: Installing Dependencies
    print_step("Step 2: Installing Python packages from requirements.txt...")
    
    if not Path("requirements.txt").exists():
        print("[ERROR] requirements.txt not found!")
        sys.exit(1)
    
    success, output = run_command([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
    
    if not success:
        print("[ERROR] Failed to install packages!")
        print(f"        Error: {output}")
        sys.exit(1)
    
    print("[OK] Packages installed successfully")
    
    # Step 3: Install Playwright Browser
    print_step("Step 3: Installing Playwright Chromium browser...")
    
    print("   [INFO] This may take a few minutes (downloading ~200MB)...")
    
    success, output = run_command([sys.executable, "-m", "playwright", "install", "chromium"])
    
    if not success:
        print("[WARNING] Playwright browser installation failed!")
        print(f"          Error: {output}")
        print("\n   You can try to install manually later:")
        print("   python -m playwright install chromium")
    else:
        print("[OK] Playwright Chromium installed successfully")
    
    # Step 4: Verifying the installation
    print_step("Step 4: Verifying installation...")
    
    # Check httpx
    try:
        import httpx
        print("   [OK] httpx")
    except ImportError:
        print("   [FAIL] httpx")
    
    # Check trafilatura
    try:
        import trafilatura
        print("   [OK] trafilatura")
    except ImportError:
        print("   [FAIL] trafilatura")
    
    # Check readability
    try:
        from readability import Document
        print("   [OK] readability-lxml")
    except ImportError:
        print("   [FAIL] readability-lxml")
    
    # Check pypdf
    try:
        import pypdf
        print("   [OK] pypdf")
    except ImportError:
        print("   [FAIL] pypdf")
    
    # Check playwright
    try:
        import playwright
        print("   [OK] playwright")
    except ImportError:
        print("   [FAIL] playwright")
    
    # Step 5: Create directories
    print_step("Step 5: Creating project directories...")
    
    directories = ["results", "logs", "data"]
    for dir_name in directories:
        Path(dir_name).mkdir(exist_ok=True)
        print(f"   [DIR] {dir_name}/")
    
    # End
    print("\n" + "=" * 60)
    print("   Setup completed successfully!")
    print("=" * 60)
    
    print("\n[NEXT] Next steps:")
    print("   1. Place your train.csv and test.csv in the project folder")
    print("   2. Make sure proxy.json is present")
    print("   3. Run: python main.py --input train.csv --output results/train_results.jsonl")
    print("   4. Evaluate: python score.py --results results/train_results.jsonl --ground-truth train.csv")
    
    print("\n[NEXT] To test Playwright on problem URLs:")
    print("   python test_playwright.py")

if __name__ == "__main__":
    try:
        setup()
    except KeyboardInterrupt:
        print("\n\n[ERROR] Setup cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n[ERROR] Unexpected error: {e}")
        sys.exit(1)