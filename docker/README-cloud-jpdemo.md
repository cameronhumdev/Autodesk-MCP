# jp-demo cloud deploy (`/opt/adsk-mcp-cloud`)

| Item | Value |
|------|--------|
| Host | `jp-demo` / `192.168.1.169` |
| Git | `/opt/adsk-mcp-cloud` → https://github.com/cameronhumdev/Autodesk-MCP.git |
| Docker build mirror | `$HOME/adsk-mcp-cloud` (Snap Docker cannot bind-mount `/opt`) |
| AnythingLLM | http://192.168.1.169:3188 |
| Gateway | http://192.168.1.169:8790 |

## Start / update

```bash
cd /opt/adsk-mcp-cloud && git pull
rsync -a --delete --exclude '.git' --exclude 'client/.bundles' \
  /opt/adsk-mcp-cloud/ "$HOME/adsk-mcp-cloud/"
cd "$HOME/adsk-mcp-cloud/docker"
~/.docker/cli-plugins/docker-compose -f compose.cloud.yml up -d --build
```

## What’s running

| Service | Port | URL (on LAN / via tunnel) |
|---------|------|---------------------------|
| AnythingLLM | 3188 | RAG / chat UI |
| Gateway | 8790 | `/v1/health`, activate, bundle download |

MCP CAD still runs on **Windows** (local package). Cloud = AI + gateway only.

## Test from a PC on the same LAN as jp-demo

Pause Cloudflare WARP if LAN HTTP fails.

```bat
curl http://192.168.1.169:8790/v1/health
start http://192.168.1.169:3188

set DEPLOY_MODE=cloud
set GATEWAY_URL=http://192.168.1.169:8790
set LICENSE_KEY=dev-local
python -m client run
```

## Port-forward (when you’re on another subnet / WARP)

Forwards jp-demo localhost services to your PC:

```powershell
# One-time host key: first connect interactively if needed
plink -ssh cameron@192.168.1.169 -L 18790:127.0.0.1:8790 -L 13188:127.0.0.1:3188 -N
```

Or OpenSSH:

```powershell
ssh -N -L 18790:127.0.0.1:8790 -L 13188:127.0.0.1:3188 jp-demo
```

Then test against the **local** forwards:

```bat
curl http://127.0.0.1:18790/v1/health
start http://127.0.0.1:13188

set DEPLOY_MODE=cloud
set GATEWAY_URL=http://127.0.0.1:18790
set LICENSE_KEY=dev-local
python -m client run
```

Leave the tunnel window open while testing.

## Update + start (on jp-demo only)

SSH to the server, then:

```bash
cd /opt/adsk-mcp-cloud
bash scripts/jpdemo-pull.sh    # git reset to origin + rsync Docker mirror
bash scripts/jpdemo-tmux.sh    # tmux session `adsk-mcp` (compose + logs)
# later:
tmux attach -t adsk-mcp        # detach: Ctrl-b d
```

tmux windows: `stack` · `anythingllm` · `git` · `health`