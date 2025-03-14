#!/bin/bash

# Fantasy PL MCP Installation Script
echo "Setting up Fantasy PL MCP Server..."

# Check Python version
python_version=$(python3 --version 2>&1 | awk '{print $2}')
required_version="3.8.0"

# Function to compare versions
version_compare() {
    if [[ $1 == $2 ]]; then
        return 0
    fi
    local IFS=.
    local i ver1=($1) ver2=($2)
    for ((i=${#ver1[@]}; i<${#ver2[@]}; i++)); do
        ver1[i]=0
    done
    for ((i=0; i<${#ver1[@]}; i++)); do
        if [[ -z ${ver2[i]} ]]; then
            ver2[i]=0
        fi
        if ((10#${ver1[i]} > 10#${ver2[i]})); then
            return 1
        fi
        if ((10#${ver1[i]} < 10#${ver2[i]})); then
            return 2
        fi
    done
    return 0
}

# Check if Python version is sufficient
version_compare "$python_version" "$required_version"
result=$?
if [[ $result == 2 ]]; then
    echo "Error: Python $required_version or higher is required (found $python_version)"
    exit 1
fi

# Create virtual environment
echo "Creating virtual environment..."
cd server || { echo "Error: server directory not found"; exit 1; }
python3 -m venv venv

# Activate virtual environment
if [[ "$OSTYPE" == "darwin"* || "$OSTYPE" == "linux-gnu"* ]]; then
    echo "Activating virtual environment (Unix/macOS)..."
    source venv/bin/activate
elif [[ "$OSTYPE" == "msys" || "$OSTYPE" == "cygwin" || "$OSTYPE" == "win32" ]]; then
    echo "Activating virtual environment (Windows)..."
    source venv/Scripts/activate
else
    echo "Unknown OS type: $OSTYPE"
    echo "Please activate the virtual environment manually"
    exit 1
fi

# Install dependencies
echo "Installing dependencies..."
pip install -r requirements.txt

# Create cache directory
echo "Setting up cache directory..."
mkdir -p fpl_cache

# Installation complete
echo ""
echo "✅ Fantasy PL MCP Server installation complete!"
echo ""
echo "To run the server:"
echo "  1. Activate the virtual environment:"
echo "     source server/venv/bin/activate  # On Windows: server\\venv\\Scripts\\activate"
echo ""
echo "  2. Run the server:"
echo "     cd server"
echo "     python server.py"
echo ""
echo "  3. For testing with MCP Inspector:"
echo "     npx @modelcontextprotocol/inspector python server.py"
echo ""
echo "  4. For integration with Claude Desktop:"
echo "     mcp install server.py --name \"Fantasy PL\""
echo ""