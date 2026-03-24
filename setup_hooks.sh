#!/bin/bash

echo "Setting up git hooks..."

mkdir -p .git/hooks

if [ -f "hooks/pre-commit" ]; then
    cp hooks/pre-commit .git/hooks/pre-commit
    chmod +x .git/hooks/pre-commit
    echo "Pre-commit hook installed"
else
    echo "hooks/pre-commit not found"
    exit 1
fi

echo "Git hooks setup complete!"
