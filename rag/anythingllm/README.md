# AnythingLLM

| Item | Value |
|------|--------|
| Upstream | https://github.com/Mintplex-Labs/anything-llm |
| License | MIT |
| Local UI | http://127.0.0.1:3188 |

## Start / stop (Windows)

```text
test-ui\start-anythingllm.bat
test-ui\stop-anythingllm.bat
```

Needs Docker Desktop. Details: [`docs/TEST-BOTH-UIS.md`](../docs/TEST-BOTH-UIS.md)

## Compose

```bash
cd docker
docker compose -f compose.anythingllm.yml up -d
```
