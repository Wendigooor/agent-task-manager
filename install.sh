#!/usr/bin/env bash
set -euo pipefail

# ATM Install — one-liner
# curl -fsSL https://raw.githubusercontent.com/Wendigooor/agent-task-manager/main/install.sh | bash

REPO="git@github.com:Wendigooor/agent-task-manager.git"
TARGET="${ATM_INSTALL_DIR:-$HOME/.atm}"

if [ -d "$TARGET" ]; then
    echo "ATM already installed at $TARGET"
    echo "To update: cd $TARGET && git pull"
    exit 0
fi

echo "Installing ATM to $TARGET..."
git clone --depth 1 "$REPO" "$TARGET"

# Create symlink
mkdir -p "$HOME/.local/bin"
ln -sf "$TARGET/bin/atm" "$HOME/.local/bin/atm"

# Check PATH
if ! echo "$PATH" | tr ':' '\n' | grep -q "$HOME/.local/bin"; then
    echo ""
    echo "Add to your shell profile:"
    echo '  export PATH="$HOME/.local/bin:$PATH"'
fi

echo ""
echo "ATM installed. Run: atm doctor"
