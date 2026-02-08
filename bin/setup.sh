#!/bin/bash
set -e

echo "🚀 Setting up AI News Platform..."

# Find best Python version (prefer 3.12, then 3.11, then default python3)
PYTHON_CMD=""
if command -v python3.12 &> /dev/null; then
    PYTHON_CMD="python3.12"
    echo "✓ Found Python 3.12"
elif command -v python3.11 &> /dev/null; then
    PYTHON_CMD="python3.11"
    echo "✓ Found Python 3.11"
elif command -v python3 &> /dev/null; then
    # Check if default python3 is 3.11+
    PYTHON_VERSION=$($python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
    PYTHON_MAJOR=$(echo $PYTHON_VERSION | cut -d. -f1)
    PYTHON_MINOR=$(echo $PYTHON_VERSION | cut -d. -f2)

    if [ "$PYTHON_MAJOR" -ge 3 ] && [ "$PYTHON_MINOR" -ge 11 ]; then
        PYTHON_CMD="python3"
        echo "✓ Found Python $PYTHON_VERSION"
    else
        echo "❌ Python 3.11+ required, found $PYTHON_VERSION"
        echo "Please install Python 3.11+:"
        echo "  brew install python@3.11"
        exit 1
    fi
else
    echo "❌ Python 3.11+ required but not found"
    echo "Please install Python 3.11+:"
    echo "  brew install python@3.11"
    exit 1
fi

# Check Node.js version
if ! command -v node &> /dev/null; then
    echo "❌ Node.js 18+ required but not found"
    echo "Please install Node.js 18+:"
    echo "  brew install node@18"
    exit 1
fi

# Remove old venv if it exists
if [ -d "venv" ]; then
    echo "🗑️  Removing old virtual environment..."
    rm -rf venv
fi

# Create virtual environment
echo "📦 Creating Python virtual environment with $PYTHON_CMD..."
$PYTHON_CMD -m venv venv
source venv/bin/activate

# Install Python dependencies
echo "📦 Installing Python dependencies..."
pip install --upgrade pip
pip install -e ".[dev]"

# Install Node.js dependencies
echo "📦 Installing Node.js dependencies..."
npm install

# Create .env if not exists
if [ ! -f .env ]; then
    echo "📝 Creating .env from template..."
    cp .env.example .env
    echo "⚠️  Please edit .env with your API keys"
fi

# Create data directory
mkdir -p data/snapshots

# Initialize database
echo "🗄️  Initializing database..."
python -m backend.storage.migrations upgrade

# Setup launchd (macOS scheduled tasks)
if [[ "$OSTYPE" == "darwin"* ]] && [[ "$1" == "--with-schedule" || "$1" == "--reload-launchd" ]]; then
    echo "⏰ Setting up launchd scheduled tasks..."

    # Update plist with current directory
    CURRENT_DIR=$(pwd)
    sed "s|{{WORKING_DIRECTORY}}|$CURRENT_DIR|g" launchd/com.ainews.ingest.plist.template > launchd/com.ainews.ingest.plist
    sed "s|{{WORKING_DIRECTORY}}|$CURRENT_DIR|g" launchd/com.ainews.digest.plist.template > launchd/com.ainews.digest.plist

    # Load plist files
    launchctl unload ~/Library/LaunchAgents/com.ainews.ingest.plist 2>/dev/null || true
    launchctl unload ~/Library/LaunchAgents/com.ainews.digest.plist 2>/dev/null || true

    cp launchd/com.ainews.ingest.plist ~/Library/LaunchAgents/
    cp launchd/com.ainews.digest.plist ~/Library/LaunchAgents/

    launchctl load ~/Library/LaunchAgents/com.ainews.ingest.plist
    launchctl load ~/Library/LaunchAgents/com.ainews.digest.plist

    echo "✅ Scheduled tasks loaded"
fi

echo "✅ Setup complete!"
echo ""
echo "Next steps:"
echo "  1. Edit .env with your API keys (optional)"
echo "  2. Run: ./bin/start.sh"
echo "  3. Open: http://localhost:3000"
