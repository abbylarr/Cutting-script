#!/usr/bin/env python3
"""
Validate that the project structure is correctly set up.
"""
import os
from pathlib import Path

def check_file_exists(filepath, description):
    """Check if a file exists and report the result."""
    if Path(filepath).exists():
        print(f"✓ {description}: {filepath}")
        return True
    else:
        print(f"✗ {description}: {filepath} (MISSING)")
        return False

def check_directory_exists(dirpath, description):
    """Check if a directory exists and report the result."""
    if Path(dirpath).is_dir():
        print(f"✓ {description}: {dirpath}/")
        return True
    else:
        print(f"✗ {description}: {dirpath}/ (MISSING)")
        return False

def main():
    """Main validation function."""
    print("Filmlist Project Structure Validation")
    print("=" * 40)
    
    all_good = True
    
    # Core application files
    files_to_check = [
        ("app/__init__.py", "App module init"),
        ("app/main.py", "FastAPI main application"),
        ("app/core/config.py", "Configuration module"),
        ("app/core/redis.py", "Redis utilities"),
        ("app/db/base.py", "Database base configuration"),
        ("app/api/v1/api.py", "API router"),
        ("requirements.txt", "Python dependencies"),
        (".env.template", "Environment template"),
        ("alembic.ini", "Alembic configuration"),
        ("alembic/env.py", "Alembic environment"),
        ("README.md", "Project documentation"),
        (".gitignore", "Git ignore rules"),
    ]
    
    for filepath, description in files_to_check:
        if not check_file_exists(filepath, description):
            all_good = False
    
    # Directories to check
    directories_to_check = [
        ("app/api/v1/endpoints", "API endpoints directory"),
        ("app/models", "Models directory"),
        ("app/schemas", "Schemas directory"),
        ("app/services", "Services directory"),
        ("alembic/versions", "Alembic versions directory"),
        ("uploads", "Uploads directory"),
        ("output", "Output directory"),
        ("scripts", "Scripts directory"),
    ]
    
    for dirpath, description in directories_to_check:
        if not check_directory_exists(dirpath, description):
            all_good = False
    
    print("\n" + "=" * 40)
    if all_good:
        print("✓ All required files and directories are present!")
        print("\nNext steps:")
        print("1. Install dependencies: pip install -r requirements.txt")
        print("2. Copy .env.template to .env and configure")
        print("3. Setup database and run migrations")
        print("4. Start development server")
    else:
        print("✗ Some files or directories are missing!")
        print("Please check the missing items above.")
    
    return all_good

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)