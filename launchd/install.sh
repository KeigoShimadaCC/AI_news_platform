#!/bin/bash
set -e

# Install launchd plists for AI News Platform scheduling
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
PLIST_DIR="$HOME/Library/LaunchAgents"

echo "Installing AI News Platform launchd jobs..."
echo "Project directory: $PROJECT_DIR"

# Create log directory
mkdir -p "$PROJECT_DIR/data/logs"

# Install ingest plist
INGEST_SRC="$SCRIPT_DIR/com.ainews.ingest.plist.template"
INGEST_DST="$PLIST_DIR/com.ainews.ingest.plist"

if [ -f "$INGEST_SRC" ]; then
    sed "s|{{WORKING_DIRECTORY}}|$PROJECT_DIR|g" "$INGEST_SRC" > "$INGEST_DST"
    echo "Installed: $INGEST_DST"
    launchctl load "$INGEST_DST" 2>/dev/null || true
fi

# Install digest plist
DIGEST_SRC="$SCRIPT_DIR/com.ainews.digest.plist.template"
DIGEST_DST="$PLIST_DIR/com.ainews.digest.plist"

if [ -f "$DIGEST_SRC" ]; then
    sed "s|{{WORKING_DIRECTORY}}|$PROJECT_DIR|g" "$DIGEST_SRC" > "$DIGEST_DST"
    echo "Installed: $DIGEST_DST"
    launchctl load "$DIGEST_DST" 2>/dev/null || true
fi

echo ""
echo "Done! Scheduled jobs:"
echo "  - Ingest: every 6 hours"
echo "  - Digest: daily at 8:00 AM"
echo ""
echo "To uninstall:"
echo "  launchctl unload ~/Library/LaunchAgents/com.ainews.ingest.plist"
echo "  launchctl unload ~/Library/LaunchAgents/com.ainews.digest.plist"
echo "  rm ~/Library/LaunchAgents/com.ainews.{ingest,digest}.plist"
