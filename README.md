# Autodesk MCP + RAG (Cloud Service Research)

Research and shortlist for offering **Inventor / AutoCAD MCP automation** plus a **cloneable private/public RAG AI** as a cloud service.

Status: **research only** — no product implementation yet.  
Open-source licenses below refer to the **MCP/RAG projects**, not Autodesk product licenses.

---

## LLM compatibility (short answer)

**MCP servers are not tied to a specific LLM.** They speak the [Model Context Protocol](https://modelcontextprotocol.io). Any host that is an MCP *client* can call their tools.

| Layer | What chooses the LLM? | Notes |
|-------|----------------------|--------|
| Inventor / AutoCAD MCP servers | Nothing — LLM-agnostic | Expose tools over MCP (stdio or HTTP). Work with Claude, GPT, Gemini, local models, etc. **if** the client supports MCP tool calling. |
| RAG platforms (AnythingLLM, OpenRAG, RAGFlow) | You configure the provider | OpenAI, Anthropic, Azure, Ollama, vLLM, OpenRouter, etc. — model-agnostic by design. |
| ChatGPT as client | OpenAI models only (inside ChatGPT) | Needs **remote HTTPS** MCP (SSE / streamable HTTP), not local stdio. |
| Cursor / Claude Desktop / AnythingLLM agents | Whatever model that client is set to | Local stdio MCP works; quality of tool use still depends on the model. |

**Practical caveat:** Weaker / non-tool-trained models may ignore tools or call them poorly. Protocol support ≠ equal agent quality. Prefer models with solid function/tool calling for CAD automation.

---

## Recommended stack (ordered)

| Rank | Role | Pick | License | Why |
|------|------|------|---------|-----|
| 1 | Inventor MCP | [bimwright/ipt-mcp](https://github.com/bimwright/ipt-mcp) | Apache-2.0 | Production-shaped gateway + add-in, 2022–2027, 46 tools, read-only mode |
| 2 | AutoCAD MCP | [puran-water/autocad-mcp](https://github.com/puran-water/autocad-mcp) | MIT | Most mature community server; File IPC + headless ezdxf |
| 3 | RAG / private AI shell | [Mintplex-Labs/anything-llm](https://github.com/Mintplex-Labs/anything-llm) | MIT | Multi-user, workspaces, agents, native MCP, many LLM backends |
| 4 | Optional knowledge MCP for ChatGPT | [langflow-ai/openrag](https://github.com/langflow-ai/openrag) | Apache-2.0 | Packaged RAG + built-in HTTP `/mcp` endpoint |

Alternate AutoCAD (full COM / richer engineering): [U-C4N/Autocad-MCP](https://github.com/U-C4N/Autocad-MCP) (MIT).  
Alternate Inventor (simpler Python): [NeonGlay/inventor-mcp](https://github.com/NeonGlay/inventor-mcp) (MIT).

---

## Inventor MCP comparison

Ordered for commercial cloud use (license + maturity + tool surface).

| Rank | Repo | License | Commercial OK? | Runtime | Tools / surface | Adv. | Disadv. |
|------|------|---------|----------------|---------|-----------------|------|---------|
| 1 | [bimwright/ipt-mcp](https://github.com/bimwright/ipt-mcp) | Apache-2.0 | Yes | .NET 8 MCP + per-year Inventor add-in | ~46 tools: docs, params, iProperties, sketch, feature, export, target switching, ToolBaker | Version range 2022–2027; STA-safe add-in; read-only mode; authenticated local transport; builds server without Inventor | Heavier setup; Windows + Inventor required to run; newer / smaller community |
| 2 | [NeonGlay/inventor-mcp](https://github.com/NeonGlay/inventor-mcp) | MIT | Yes | Python + pywin32 COM | Parametric parts, sheet metal, holes, fillets, transactions, `execute_python` escape hatch | Fast to try; high-level mm tools; Inventor 2026 API notes; any MCP client | COM out-of-process (less robust than in-process add-in); smaller project |
| 3 | [Cadtastic-Solutions/Autodesk-Inventor-MCP](https://github.com/cadtastic-solutions/autodesk-inventor-mcp) | Apache-2.0 | Yes | .NET 8 | Session tools + developer plugin skeleton | Good for Inventor 2025+ add-in / Claude plugin workflows | More developer-toolkit than end-user modeling suite |
| — | [hsavas/inventor-mcp](https://github.com/hsavas/inventor-mcp) | Custom | **No** (non-commercial without permission) | Python + COM | Sketches, features, assemblies, drawings | Broad COM surface | **Not OK for commercial SaaS without author permission** |

### ipt-mcp tool groups (representative)

| Group | Examples |
|-------|----------|
| Meta / target | `inventor_list_available_targets`, `inventor_switch_target` |
| Query | `inventor_health`, `inventor_get_document_info` |
| Document | `inventor_new_part`, `inventor_open_document`, `inventor_save_document` |
| Parameters | `inventor_list_parameters`, `inventor_set_parameter`, `inventor_create_parameter` |
| Properties | `inventor_get_iproperty`, `inventor_get_mass_properties` |
| Sketch | `inventor_create_sketch`, `inventor_draw_line/circle/rectangle/arc`, constraints |
| Feature | `inventor_extrude`, `inventor_revolve`, `inventor_fillet`, `inventor_chamfer` |
| Export | `inventor_capture_view`, `inventor_export_step/stl/dxf` |
| Opt-in | `inventor_send_code` (disabled by default) |

---

## AutoCAD MCP comparison

| Rank | Repo | License | Commercial OK? | Backends | Tools / surface | Adv. | Disadv. |
|------|------|---------|----------------|----------|-----------------|------|---------|
| 1 | [puran-water/autocad-mcp](https://github.com/puran-water/autocad-mcp) | MIT | Yes | File IPC (LT 2024+), ezdxf headless | 8 consolidated tools: drawing, entity, layer, block, annotation, pid, view, system | Most stars/forks; focus-free IPC; works without full AutoCAD via ezdxf; companion drafting skill | LT-oriented File IPC; not the richest COM feature set |
| 2 | [U-C4N/Autocad-MCP](https://github.com/U-C4N/Autocad-MCP) | MIT | Yes | COM (live AutoCAD) + ezdxf | ~122 tools; ISO GD&T / dimension-tolerance validation | Production-grade dual engine; strong engineering standards | Newer / smaller community than puran-water |
| 3 | [thepiruthvirajan/autocad-mcp-server](https://github.com/thepiruthvirajan/autocad-mcp-server) | Apache-2.0 | Yes | COM | Walls, doors, windows, layers, building structures | Clear AEC-oriented tooling; Apache-2.0 | Narrower general drafting surface |
| 4 | [varavista/autocad-mcp](https://github.com/varavista/autocad-mcp) | Apache-2.0 | Yes | File IPC + COM + ezdxf | ~22 tools / 130+ ops; multi-CAD (ZWCAD, BricsCAD, …) | Unified backends; multi-CAD interesting for cloud | Low adoption / early |
| 5 | [beiming183-cloud/AutoCAD-MCP](https://github.com/beiming183-cloud/AutoCAD-MCP) | MIT | Yes | File IPC + ezdxf (+ validation) | Consolidated tools + geometry audits | Strong validation / evidence focus | Fork lineage; smaller community |
| — | [xstaar/autocad-mcp](https://github.com/xstaar/autocad-mcp) | Proprietary | **No** | File IPC + YQArch | 684 arch commands / 55 tools | Huge command set | Activation/licensing; not open for commercial reuse |

### puran-water tool surface (representative)

| Tool | Role |
|------|------|
| `drawing` | New/open/save drawing lifecycle |
| `entity` | Create/edit geometry entities |
| `layer` | Layer management |
| `block` | Blocks / inserts |
| `annotation` | Text, dimensions, notes |
| `pid` | P&ID-oriented symbols |
| `view` | Views / screenshots |
| `system` | Undo/redo, LISP exec, system ops |

---

## RAG / private AI comparison

Ordered for **cloneable subscriber AI** (private or public) with commercial SaaS in mind.

| Rank | Project | License | Commercial SaaS OK? | What you get | Adv. | Disadv. |
|------|---------|---------|---------------------|--------------|------|---------|
| 1 | [AnythingLLM](https://github.com/Mintplex-Labs/anything-llm) | MIT | Yes | Docs RAG, multi-user Docker, agents, embed widget, **MCP client** | Best “private ChatGPT” clone; any major / local LLM; MCP to CAD servers | Need to add tenancy/billing/governance yourself for a real cloud product |
| 2 | [OpenRAG](https://github.com/langflow-ai/openrag) | Apache-2.0 | Yes | Langflow + Docling + OpenSearch RAG; HTTP **`/mcp`** | ChatGPT-friendly remote MCP for knowledge; packaged stack | Heavier (OpenSearch etc.); younger than AnythingLLM |
| 3 | [RAGFlow](https://github.com/infiniflow/ragflow) | Apache-2.0 | Yes | Deep document parsing, citations, multi-tenant KBs, agents | Excellent PDF/table understanding | Heavier ops; less “one-box ChatGPT clone” UX than AnythingLLM |

### Avoid or constrain for multi-tenant resale

| Project | License issue |
|---------|----------------|
| [Dify](https://github.com/langgenius/dify) | Modified Apache — **multi-tenant SaaS restricted** without their commercial license |
| [Open WebUI](https://github.com/open-webui/open-webui) | Branding / fair-use clause; white-label needs enterprise license (or careful fork strategy) |
| [n8n](https://github.com/n8n-io/n8n) | Fair-code — SaaS restrictions |

### LLM backends (pair with RAG)

| Runner / API | License (typical) | Role |
|--------------|-------------------|------|
| OpenAI / Azure OpenAI | Proprietary API | Cloud GPT models via AnythingLLM / OpenRAG |
| Anthropic / Google / OpenRouter | Proprietary API | Alternate cloud models |
| [Ollama](https://github.com/ollama/ollama) | MIT | Local / private open models |
| vLLM / llama.cpp | Apache-2.0 / MIT | Self-hosted open LLM serving |

---

## Client matrix (how users talk to the tools)

| Client | Transport needed | LLM | Can drive Inventor/AutoCAD MCP? | Can use RAG? |
|--------|------------------|-----|----------------------------------|--------------|
| ChatGPT (Developer Mode / connectors) | Remote **HTTPS** MCP | OpenAI only | Yes, if you bridge Windows CAD MCP to HTTPS | Yes via OpenRAG `/mcp` or your own knowledge MCP |
| Cursor | stdio or SSE/HTTP | Any model Cursor supports | Yes (local stdio on Windows CAD box) | Via RAG MCP or separate workspace |
| Claude Desktop / Claude Code | stdio (local) | Anthropic | Yes | Same |
| AnythingLLM | MCP (stdio/HTTP) + its own RAG | Any configured provider | Yes (agent + MCP) | Built-in |
| Custom agent (OpenAI Responses API, etc.) | HTTP MCP | Whatever you wire | Yes | Yes |

---

## Cloud service shape (research)

```text
Subscriber browser / ChatGPT / Cursor
            │
            ▼
   Cloud: RAG + LLM router (AnythingLLM / OpenRAG)
            │  HTTPS MCP (knowledge + orchestration)
            ▼
   Edge / Windows host with Inventor or AutoCAD
            │  local MCP (stdio → optional HTTPS bridge)
            ▼
   Autodesk application (subscriber PC or your CAD farm)
```

CAD automation must run where Inventor/AutoCAD runs (Windows). RAG + LLM can run in cloud or on-prem per subscriber (private vs public AI).

---

## License summary (OSS projects only)

| Use commercially as SaaS building block? | Projects |
|------------------------------------------|----------|
| **Yes** (permissive) | ipt-mcp, NeonGlay inventor-mcp, Cadtastic Inventor MCP, puran-water autocad-mcp, U-C4N Autocad-MCP, thepiruthvirajan, varavista, beiming183, AnythingLLM, OpenRAG, RAGFlow, Ollama |
| **No / needs permission or paid deal** | hsavas inventor-mcp, xstaar autocad-mcp, Dify (SaaS clause), Open WebUI (branding / enterprise for white-label), n8n (fair-code) |

Always re-check `LICENSE` in each upstream repo before shipping; terms can change.

---

## Sources

- Inventor: [ipt-mcp](https://github.com/bimwright/ipt-mcp), [NeonGlay/inventor-mcp](https://github.com/NeonGlay/inventor-mcp), [Cadtastic Autodesk-Inventor-MCP](https://github.com/cadtastic-solutions/autodesk-inventor-mcp), [hsavas/inventor-mcp](https://github.com/hsavas/inventor-mcp)
- AutoCAD: [puran-water/autocad-mcp](https://github.com/puran-water/autocad-mcp), [U-C4N/Autocad-MCP](https://github.com/U-C4N/Autocad-MCP), [thepiruthvirajan/autocad-mcp-server](https://github.com/thepiruthvirajan/autocad-mcp-server), [varavista/autocad-mcp](https://github.com/varavista/autocad-mcp), [xstaar/autocad-mcp](https://github.com/xstaar/autocad-mcp)
- RAG: [AnythingLLM](https://github.com/Mintplex-Labs/anything-llm), [OpenRAG](https://github.com/langflow-ai/openrag), [RAGFlow](https://github.com/infiniflow/ragflow)
- Roundup: [Snyk — 9 MCP servers for CAD](https://snyk.io/articles/9-mcp-servers-for-computer-aided-drafting-cad-with-ai/)

---

## Next (not done yet)

- [ ] Vendor shortlist into this monorepo (or git submodules) under clear LICENSE notices
- [ ] HTTPS MCP bridge for ChatGPT ↔ Windows CAD agents
- [ ] Tenant model: private vs public workspaces on AnythingLLM / OpenRAG
- [ ] Smoke-test against local Inventor + AutoCAD installs
