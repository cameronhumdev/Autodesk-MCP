#!/usr/bin/env bash
# Start / attach jp-demo cloud stack in a tmux session.
# Run on jp-demo:  bash /opt/adsk-mcp-cloud/scripts/jpdemo-tmux.sh
set -euo pipefail

SESSION="${SESSION:-adsk-mcp}"
HOME_MIRROR="${HOME_MIRROR:-$HOME/adsk-mcp-cloud}"
OPT_ROOT="${OPT_ROOT:-/opt/adsk-mcp-cloud}"
COMPOSE_FILE="compose.cloud.yml"
COMPOSE_BIN="${COMPOSE_BIN:-}"

if [ -z "$COMPOSE_BIN" ]; then
  if [ -x "$HOME/.docker/cli-plugins/docker-compose" ]; then
    COMPOSE_BIN="$HOME/.docker/cli-plugins/docker-compose"
  elif command -v docker-compose >/dev/null 2>&1; then
    COMPOSE_BIN="$(command -v docker-compose)"
  else
    echo "docker compose not found. Install plugin or docker-compose." >&2
    exit 1
  fi
fi

if [ ! -f "$HOME_MIRROR/docker/$COMPOSE_FILE" ]; then
  echo "Missing $HOME_MIRROR/docker/$COMPOSE_FILE — run jpdemo-pull.sh first." >&2
  exit 1
fi

start_stack() {
  cd "$HOME_MIRROR/docker"
  echo "==> compose up ($COMPOSE_BIN -f $COMPOSE_FILE)"
  "$COMPOSE_BIN" -f "$COMPOSE_FILE" up -d --build
  sleep 2
  "$COMPOSE_BIN" -f "$COMPOSE_FILE" ps
  echo "==> health"
  curl -fsS http://127.0.0.1:8790/v1/health || true
  echo
  curl -sS -o /dev/null -w "anythingllm_http=%{http_code}\n" http://127.0.0.1:3188/ || true
}

# Already have session → optionally attach
if tmux has-session -t "$SESSION" 2>/dev/null; then
  echo "Session '$SESSION' already exists"
  start_stack
  if [ "${ATTACH:-1}" = "1" ]; then
    echo "Attaching (detach: Ctrl-b d)"
    if [ -n "${TMUX:-}" ]; then
      tmux switch-client -t "$SESSION"
    else
      exec tmux attach -t "$SESSION"
    fi
  fi
  exit 0
fi

echo "==> creating tmux session '$SESSION'"
tmux new-session -d -s "$SESSION" -n stack -c "$HOME_MIRROR/docker"

# window 0: stack — bring containers up, then follow gateway logs
tmux send-keys -t "$SESSION:stack" \
  "export PATH=\"\$HOME/.docker/cli-plugins:\$PATH\"; $(printf '%q' "$COMPOSE_BIN") -f $(printf '%q' "$COMPOSE_FILE") up -d --build; $(printf '%q' "$COMPOSE_BIN") -f $(printf '%q' "$COMPOSE_FILE") ps; echo; curl -fsS http://127.0.0.1:8790/v1/health; echo; $(printf '%q' "$COMPOSE_BIN") -f $(printf '%q' "$COMPOSE_FILE") logs -f --tail=50" C-m

# window 1: anythingllm logs
tmux new-window -t "$SESSION" -n anythingllm -c "$HOME_MIRROR/docker"
tmux send-keys -t "$SESSION:anythingllm" \
  "docker logs -f --tail=50 adsk-mcp-anythingllm" C-m

# window 2: shell in git checkout
tmux new-window -t "$SESSION" -n git -c "$OPT_ROOT"
tmux send-keys -t "$SESSION:git" \
  "git status -sb; git log -1 --oneline; echo; echo 'pull: bash scripts/jpdemo-pull.sh'" C-m

# window 3: health watch
tmux new-window -t "$SESSION" -n health -c "$HOME_MIRROR/docker"
tmux send-keys -t "$SESSION:health" \
  "watch -n 5 'curl -fsS http://127.0.0.1:8790/v1/health; echo; curl -sS -o /dev/null -w anythingllm=%{http_code} http://127.0.0.1:3188/; echo; docker ps --filter name=adsk-mcp --format \"table {{.Names}}\\t{{.Status}}\\t{{.Ports}}\"'" C-m

tmux select-window -t "$SESSION:stack"

echo "URLs (on jp-demo / LAN):"
echo "  Chat UI      http://192.168.1.169:8787"
echo "  AnythingLLM  http://192.168.1.169:3188"
echo "  Gateway      http://192.168.1.169:8790/v1/health"
echo "Laptop agent:  GATEWAY_URL=http://192.168.1.169:8790  python -m client serve-agent"
echo "Attach: tmux attach -t $SESSION   (detach: Ctrl-b d)"

if [ "${ATTACH:-1}" = "1" ] && [ -z "${TMUX:-}" ]; then
  exec tmux attach -t "$SESSION"
fi
