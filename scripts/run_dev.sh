#!/bin/bash
# Development server startup script

echo "Starting Filmlist Development Server"
echo "===================================="

# Check if virtual environment is activated
if [[ "$VIRTUAL_ENV" == "" ]]; then
    echo "Virtual environment not activated. Activating venv311..."
    source venv311/bin/activate
fi

# Check if .env exists
if [ ! -f .env ]; then
    echo "Warning: .env file not found. Please copy .env.template to .env and configure it."
    exit 1
fi

# Start the development server
echo "Starting FastAPI development server..."
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000