#!/bin/bash

echo "=== Debug Environment Loading ==="
echo "Before sourcing:"
echo "OPENAI_API_KEY: '$OPENAI_API_KEY'"

echo "Sourcing .env.development..."
source .env.development

echo "After sourcing:"
echo "OPENAI_API_KEY: '$OPENAI_API_KEY'"
echo "Length: ${#OPENAI_API_KEY}"

if [ -z "$OPENAI_API_KEY" ] || [ "$OPENAI_API_KEY" = "your_openai_api_key_here" ]; then
    echo "VALIDATION FAILED"
else
    echo "VALIDATION PASSED"
fi