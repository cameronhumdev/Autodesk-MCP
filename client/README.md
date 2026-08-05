# `client/` — download / resolve agent + gateway

One agent, two modes:

| `DEPLOY_MODE` | MCP location | Gateway |
|---------------|--------------|---------|
| `local` | Relative paths under install/repo (`vendor/…`, `.venv/…`) | Skipped |
| `cloud` | Download track zips from `GATEWAY_URL` into `client/.bundles/current/` | Activate + heartbeat |

Same code path after resolve: sets `INVENTOR_MCP_COMMAND` / `AUTOCAD_MCP_COMMAND` (and writes `client/.bundles/runtime/mcp.{json,ps1,bat}`).

## Quick use

```bat
REM Local (default) — point at existing MCP builds
set DEPLOY_MODE=local
python -m client run

REM Cloud path — start stub gateway in another terminal, then download
python -m client gateway
set DEPLOY_MODE=cloud
set GATEWAY_URL=http://127.0.0.1:8790
set LICENSE_KEY=dev-local
python -m client run
```

Then load env into test-ui (PowerShell):

```powershell
. .\client\.bundles\runtime\mcp.ps1
.\test-ui\start.bat
```

## Commands

| Cmd | Does |
|-----|------|
| `python -m client ensure` | Resolve/download MCP only |
| `python -m client connect` | Gateway session only |
| `python -m client run` | ensure + connect + write runtime env |
| `python -m client gateway` | Dev stub on `:8790` |

## Layout

```text
client/
  agent.py          # ensure + connect
  local.py          # relative path resolution
  download.py       # manifest + zip fetch
  gateway.py        # outbound HTTPS client
  gateway_stub.py   # local test server
  config.py
  paths.py
```
