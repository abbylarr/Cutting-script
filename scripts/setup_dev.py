#!/usr/bin/env python3
"""
Development setup script for filmlist project.
"""
import os
import sys
import subprocess
from pathlib import Path

def run_command(cmd, description):
    """Run a shell command and handle errors."""
    print(f"Running: {description}")
    print(f"Command: {cmd}")
    
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    
    if result.returncode != 0:
        print(f"Error: {description} failed")
        print(f"stdout: {result.stdout}")
        print(f"stderr: {result.stderr}")
        return False
    
    print(f"Success: {description} completed")
    if result.stdout:
        print(f"Output: {result.stdout}")
    return True

def check_requirements():
    """Check if required software is installed."""
    requirements = {
        "python3.11": "python3.11 --version",
        "postgresql": "psql --version",
        "redis": "redis-cli --version",
        "ffmpeg": "ffmpeg -version"
    }
    
    missing = []
    for name, cmd in requirements.items():
        if not run_command(cmd, f"Checking {name}"):
            missing.append(name)
    
    if missing:
        print(f"\nMissing requirements: {', '.join(missing)}")
        print("Please install the missing software before continuing.")
        return False
    
    return True

def setup_virtual_environment():
    """Create and activate virtual environment."""
    if not Path("venv311").exists():
        if not run_command("python3.11 -m venv venv311", "Creating virtual environment"):
            return False
    
    # Check if we're in virtual environment
    if sys.prefix == sys.base_prefix:
        print("Please activate the virtual environment:")
        print("source venv311/bin/activate  # On Linux/Mac")
        print("venv311\\Scripts\\activate     # On Windows")
        return False
    
    return True

def install_dependencies():
    """Install Python dependencies."""
    return run_command("pip install -r requirements.txt", "Installing Python dependencies")

def setup_environment():
    """Setup environment variables."""
    if not Path(".env").exists():
        if Path(".env.template").exists():
            run_command("cp .env.template .env", "Creating .env file from template")
            print("\nPlease edit .env file with your configuration:")
            print("- Set OPENAI_API_KEY")
            print("- Configure DATABASE_URL if needed")
            print("- Configure REDIS_URL if needed")
        else:
            print("Warning: .env.template not found")
    else:
        print(".env file already exists")

def main():
    """Main setup function."""
    print("Filmlist Development Setup")
    print("=" * 30)
    
    # Check requirements
    if not check_requirements():
        sys.exit(1)
    
    # Setup virtual environment
    if not setup_virtual_environment():
        sys.exit(1)
    
    # Install dependencies
    if not install_dependencies():
        sys.exit(1)
    
    # Setup environment
    setup_environment()
    
    print("\nSetup completed successfully!")
    print("\nNext steps:")
    print("1. Edit .env file with your configuration")
    print("2. Create PostgreSQL database: createdb filmlist")
    print("3. Run database migrations: alembic upgrade head")
    print("4. Start the development server: uvicorn app.main:app --reload")

if __name__ == "__main__":
    main()