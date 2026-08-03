# Test both UIs

| UI | What it is | URL | Start |
|----|------------|-----|--------|
| **Custom test UI** | Our thin playground (mock CAD + local RAG) | http://127.0.0.1:8080 | `test-ui\start.bat` |
| **AnythingLLM** | Real product UI (docs, workspaces, MCP-ready) | http://localhost:3080 | `test-ui\start-anythingllm.bat` |

### Real LLM (not demo mode)

| Path | Steps |
|------|--------|
| **OpenAI API** (not ChatGPT Plus) | Needs a separate API key + credit — Plus subscription alone does not work |
| **Ollama + Qwen** (recommended open) | 1) Install https://ollama.com  2) `test-ui\setup-ollama.bat` (pulls `qwen2.5:7b`)  3) `start.bat` |

Open picks for tools/CAD agents: **Qwen2.5/Qwen3** (best balance) · Llama 3.1 8B · smaller: `qwen2.5:3b` if RAM is tight.

Demo mode = keyword mock only. Badge should say **live** or **auto**, not **demo**.

Run them at the same time — different ports.

---

## A. Custom test UI

1. Double-click `test-ui\start.bat`
2. Open http://127.0.0.1:8080
3. Use sidebar samples (RAG + mock Inventor/AutoCAD tools)
4. Close the console window to stop

No Docker required. Demo mode works without Ollama.

---

## B. AnythingLLM

**Needs:** Docker Desktop running.

1. Double-click `test-ui\start-anythingllm.bat`
2. Open http://localhost:3080
3. Finish onboarding → pick an LLM (OpenAI key **or** Ollama at `http://host.docker.internal:11434`)
4. Create a workspace → upload a PDF → chat
5. Stop: `test-ui\stop-anythingllm.bat`

**Desktop alternative (no Docker):** install [AnythingLLM Desktop](https://anythingllm.com/download) and test the same UI locally.

---

## What to compare

| Check | Custom test UI | AnythingLLM |
|-------|----------------|-------------|
| Chat | Yes | Yes |
| Upload real PDFs | Minimal / seed docs | Yes |
| Multi-user / workspaces | No | Yes |
| MCP → Inventor/AutoCAD | Mock only | Real MCP (when Windows MCP servers run) |
| Look / branding | Ours (tiny) | Theirs (or embed / custom UI later) |

---

## Later: plugin inside Inventor / AutoCAD

Same backends; different shell:

```text
Inventor/AutoCAD add-in (WebView or panel)
        → AnythingLLM (embed or API)     preferred product path
   or   → your custom UI → AnythingLLM API
        → MCP tools still talk to the live app on Windows
```

| Approach | Notes |
|----------|--------|
| **Embed AnythingLLM** in a WebView panel | Fastest in-app chat |
| **Custom panel UI** → AnythingLLM API | Cleaner brand; more work |
| **MCP from AnythingLLM agents** | CAD actions while chat runs in-app or browser |

v1: test browser UIs. v2: wrap the winner in an Autodesk add-in WebView.
