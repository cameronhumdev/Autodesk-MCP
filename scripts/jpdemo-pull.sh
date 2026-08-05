#!/usr/bin/env bash
# Pull Autodesk-MCP onto jp-demo and sync the Snap-Docker build mirror.
# Run on jp-demo:  bash /opt/adsk-mcp-cloud/scripts/jpdemo-pull.sh
set -euo pipefail

REPO_URL="${REPO_URL:-https://github.com/cameronhumdev/Autodesk-MCP.git}"
OPT_ROOT="${OPT_ROOT:-/opt/adsk-mcp-cloud}"
HOME_MIRROR="${HOME_MIRROR:-$HOME/adsk-mcp-cloud}"
BRANCH="${BRANCH:-main}"

echo "==> ensure $OPT_ROOT"
if [ ! -d "$OPT_ROOT/.git" ]; then
  if [ -w "$(dirname "$OPT_ROOT")" ] || sudo -n true 2>/dev/null; then
    sudo mkdir -p "$OPT_ROOT"
    sudo chown "$(id -u):$(id -g)" "$OPT_ROOT"
  else
    echo "Need write access to $OPT_ROOT (or passwordless sudo)." >&2
    exit 1
  fi
  git clone --branch "$BRANCH" "$REPO_URL" "$OPT_ROOT"
else
  cd "$OPT_ROOT"
  git remote set-url origin "$REPO_URL"
  git fetch origin
  git checkout "$BRANCH"
  # Deploy tree: match GitHub exactly (drop scp leftovers / local edits)
  git reset --hard "origin/$BRANCH"
  git clean -fd
fi

cd "$OPT_ROOT"
echo "==> $(git log -1 --oneline)"

echo "==> sync mirror $HOME_MIRROR (Snap Docker cannot build from /opt)"
mkdir -p "$HOME_MIRROR"
rsync -a --delete \
  --exclude '.git' \
  --exclude 'client/.bundles' \
  --exclude '.venv' \
  --exclude 'vendor' \
  --exclude '__pycache__' \
  "$OPT_ROOT/" "$HOME_MIRROR/"

ln -sfn "$OPT_ROOT" "$HOME/adsk-mcp-cloud-git"
echo "==> pull done"
echo "    git:    $OPT_ROOT"
echo "    mirror: $HOME_MIRROR"
echo "    next:   bash $OPT_ROOT/scripts/jpdemo-tmux.sh"
