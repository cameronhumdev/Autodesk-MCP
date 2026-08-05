# Remaining work — honest status

Local full app path (LLM + RAG + real MCP) is in progress. Docker/cloud deferred.

**Hard rule:** Inventor and AutoCAD are **separate tracks** under `cad/inventor/` and `cad/autocad/`.

---

## Working now (local, no Docker)

| Item | Reality |
|------|---------|
| AutoCAD MCP (U-C4N) | **Live** — `AUTOCAD_BACKEND=mcp` (ezdxf verified; COM when AutoCAD running) |
| AutoCAD → RAG export | **Live** — `autocad_export_to_rag` |
| Inventor MCP server (ipt-mcp) | **Live** — 45 tools via `Bimwright.Ipt.Server.exe` |
| Inventor add-in bundle | **Deployed** — `%APPDATA%\Autodesk\ApplicationPlugins\Bimwright.Ipt.bundle` (2027) |
| Inventor → live session | Needs Inventor 2027 running with add-in loaded (descriptor under `%LOCALAPPDATA%\Bimwright\ipt-mcp\`) |
| Local RAG | **Live** — `rag/local` |
| LLM | Ollama / OpenAI-compatible via test-ui |
| Mock CAD backends | Escape hatch only (`*_BACKEND=mock`) — **not** the product default |

---

## Still open

| # | Item | Notes |
|---|------|--------|
| 1 | Inventor live create/set/export with app open | Start Inventor; confirm descriptor; run sample 4 |
| 2 | AutoCAD COM (not just ezdxf) | Start AutoCAD; `AUTOCAD_MCP_BACKEND=com` |
| 3 | Richer CAD→RAG (PDF/STEP/DXF files) | Text summaries work; file artifacts next |
| 4 | AnythingLLM product RAG | Deferred with Docker |
| 5 | Client agent gateway relay (real cloud, not stub) | Stub + download agent in `client/` — replace stub later |
| 6 | K8s / Terraform / billing / ChatGPT gateway | Explicitly later |

---

## Run

```bat
pwsh scripts\setup-cad-mcp.ps1
REM Start Inventor 2027 + (optional) AutoCAD 2027
test-ui\start.bat
```
