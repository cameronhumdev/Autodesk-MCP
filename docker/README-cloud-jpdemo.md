# jp-demo cloud deploy (`/opt/adsk-mcp-cloud`)

| Item | Value |
|------|--------|
| Host | `jp-demo` / `192.168.1.169` |
| Git | `/opt/adsk-mcp-cloud` → https://github.com/cameronhumdev/Autodesk-MCP.git |
| Docker build mirror | `$HOME/adsk-mcp-cloud` (Snap Docker cannot bind-mount `/opt`) |
| **Chat UI (product path)** | http://192.168.1.169:8787 |
| AnythingLLM (optional) | http://192.168.1.169:3188 |
| Gateway | http://192.168.1.169:8790 |

## What runs where

```text
Browser → Chat UI on jp-demo (:8787)
            → Anthropic/OpenAI (API key on server)
            → local RAG on server
            → CAD tools → gateway (:8790) → laptop agent → Inventor/AutoCAD MCP
```

## On jp-demo

```bash
cd /opt/adsk-mcp-cloud
./scripts/jpdemo-pull.sh
./scripts/jpdemo-tmux.sh
```

Put LLM secrets in `~/adsk-mcp-cloud/docker/.env` (not committed):

```env
LLM_BASE_URL=https://api.anthropic.com/v1
LLM_MODEL=claude-sonnet-4-6
LLM_API_KEY=sk-ant-...
CAD_SERVICE_KEY=dev-cloud
```

Then rebuild UI: `cd ~/adsk-mcp-cloud/docker && ~/.docker/cli-plugins/docker-compose -f compose.cloud.yml up -d --build`

## On your laptop (CAD agent — required for geometry)

```powershell
# If WARP / wrong subnet — tunnel first:
ssh -N -L 18790:127.0.0.1:8790 -L 18787:127.0.0.1:8787 jp-demo

$env:GATEWAY_URL = "http://127.0.0.1:18790"   # or http://192.168.1.169:8790 on same LAN
$env:LICENSE_KEY = "dev-local"
pwsh scripts\serve-agent.ps1
```

Keep that window open. Chat in the **cloud** UI:

- LAN: http://192.168.1.169:8787  
- Tunnel: http://127.0.0.1:18787  

Token usage (input/output) shows under each assistant reply. Confirm CAD launch cards still appear in the UI; the agent starts Inventor/AutoCAD on the laptop.
