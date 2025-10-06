#!/bin/bash

# Azure Functions Local Setup Script
# This script helps you set up and test your Azure Function locally

set -e

echo "🚀 Setting up Azure Functions development environment..."

# Check if Azure Functions Core Tools is installed
if ! command -v func &> /dev/null
then
    echo "❌ Azure Functions Core Tools not found!"
    echo "📦 Installing Azure Functions Core Tools..."
    
    if [[ "$OSTYPE" == "darwin"* ]]; then
        # macOS
        brew tap azure/functions
        brew install azure-functions-core-tools@4
    else
        echo "Please install Azure Functions Core Tools manually:"
        echo "https://learn.microsoft.com/azure/azure-functions/functions-run-local"
        exit 1
    fi
fi

echo "✅ Azure Functions Core Tools found: $(func --version)"

# Check if Python is available
if ! command -v python3 &> /dev/null
then
    echo "❌ Python 3 not found! Please install Python 3.9 or higher."
    exit 1
fi

echo "✅ Python found: $(python3 --version)"

# Create virtual environment if it doesn't exist
if [ ! -d ".venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv .venv
fi

# Activate virtual environment
echo "🔧 Activating virtual environment..."
source .venv/bin/activate

# Install dependencies
echo "📦 Installing Python dependencies..."
pip install -r requirements.txt

# Check if local.settings.json exists
if [ ! -f "local.settings.json" ]; then
    echo "❌ local.settings.json not found!"
    echo "Please configure your local.settings.json with Azure credentials."
    exit 1
fi

echo "✅ local.settings.json found"

# Check if Azurite is installed (optional)
if ! command -v azurite &> /dev/null
then
    echo "⚠️  Azurite not found (optional for local blob storage testing)"
    echo "Install with: npm install -g azurite"
else
    echo "✅ Azurite found"
fi

echo ""
echo "✨ Setup complete! You can now:"
echo ""
echo "  1. Start the function locally:"
echo "     func start"
echo ""
echo "  2. Test the health endpoint:"
echo "     curl http://localhost:7071/api/health"
echo ""
echo "  3. Deploy to Azure:"
echo "     func azure functionapp publish <function-app-name>"
echo ""
echo "📖 For more details, see AZURE_FUNCTIONS_README.md"
