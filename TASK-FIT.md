# Multi-MCP, differentiators, and how this fits the cloud task

Maps the shortlist to the goal: **Inventor + AutoCAD MCP**, **ChatGPT + open LLM**, **cloneable private/public subscriber AI**, offered as a **cloud service**.

---

## Using multiple MCPs as one — worth it? Easy?

**Yes — and for your product it’s the right design.** You almost never pick “one mega MCP”; you run **several specialized servers** and let the client (or a gateway) see them together.

| Approach | How it works | Difficulty | When to use |
|----------|--------------|------------|-------------|
| **A. Client multi-attach (recommended start)** | Cursor / Claude Desktop / AnythingLLM / ChatGPT connectors each register N MCP servers (`inventor`, `autocad`, `knowledge`) | **Easy** — config only | Local CAD box + AnythingLLM; ChatGPT with multiple connectors |
| **B. Gateway / aggregator** | One HTTPS MCP endpoint that proxies tools from Inventor + AutoCAD + RAG backends (namespace tools: `inventor_*`, `autocad_*`, `kb_*`) | **Medium** | Cloud SaaS + ChatGPT wanting a single connector URL |
| **C. Merge into one codebase** | Fork and glue servers into one process | **Hard / not worth it** | Avoid — license mix, different runtimes (.NET vs Python), worse upgrades |

### Worth combining?

| Combine | Worth it? | Why |
|---------|-----------|-----|
| Inventor MCP + AutoCAD MCP | **Yes** | Different apps; subscribers use both; no single upstream covers both |
| CAD MCP(s) + RAG MCP | **Yes — core of your offer** | CAD tools = *do*; RAG = *know* (standards, company docs, past drawings Q&A) |
| Two AutoCAD MCPs at once (e.g. puran + U-C4N) | **Usually no** | Overlapping tools confuse the model; pick one primary, optional second profile later |
| Two Inventor MCPs at once | **Usually no** | Same overlap problem; pick ipt-mcp **or** NeonGlay |

**Practical product shape:**

```text
Subscriber UI (ChatGPT connector / AnythingLLM / Cursor)
        │
        ├─ knowledge MCP  ← RAG (private or public workspace)
        ├─ inventor MCP   ← Windows host with Inventor
        └─ autocad MCP    ← Windows host with AutoCAD
```

Easy at the client. For ChatGPT as a polished cloud product, plan **B** (one branded HTTPS gateway) later.

---

## Inventor MCPs — what each has over the others (importance for your task)

| Rank | Project | License | Tools (count / focus) | What it has over the others (decide on this) | Why it matters for *your* cloud task |
|------|---------|---------|------------------------|-----------------------------------------------|--------------------------------------|
| **1** | [ipt-mcp](https://github.com/bimwright/ipt-mcp) | Apache-2.0 | ~46: targets, docs, params, iProperties, sketch, extrude/revolve/fillet/chamfer, work features, export STEP/STL/DXF, ToolBaker, optional `send_code` | **Production reliability**: in-process add-in on Inventor’s STA thread; multi-version **2022–2027**; **read-only mode**; multi-session target switching | Cloud/agent safety + wide customer Inventor versions; safest base for a paid service |
| **2** | [NeonGlay/inventor-mcp](https://github.com/NeonGlay/inventor-mcp) | MIT | 34: connect/status, sketch primitives, extrude/revolve, hole/tapped/C’bore, fillet/chamfer, circular pattern, sheet metal face/flange/cut, params, `execute_python` | **Faster parametric / sheet-metal modeling** and Inventor **2026 quirk knowledge**; Python escape hatch | Best if demo speed and flange/shaft/sheet-metal “talk to model” UX matter more than multi-year enterprise hardening |
| **3** | [Cadtastic Inventor MCP](https://github.com/cadtastic-solutions/autodesk-inventor-mcp) | Apache-2.0 | Session only: versions list, session start/adopt/list/terminate | **Session lifecycle scaffolding** for 2025+ .NET add-in plugins | Useful if you build your *own* tool layer later; not enough alone for “AI designs parts” |
| **—** | hsavas | Custom (non-commercial) | Broad: sketch/feature/assembly/drawing/export/view modules | Broadest domain *coverage* in marketing | **Cannot use for commercial SaaS** without permission — skip |

**Recommendation for task:** Primary **ipt-mcp**. Optionally keep NeonGlay as a “parametric specialist” profile on the same Windows image, but don’t expose both tool sets to one agent at once.

### ipt-mcp tools (quick list)

`inventor_list/switch_target`, health/docs, new part/assembly, open/save/close, units/material, parameters CRUD, iProperties + mass props, sketch create/draw/constrain, extrude/revolve/fillet/chamfer/work plane/axis, capture view, export step/stl/dxf, ToolBaker, opt-in `inventor_send_code`.

### NeonGlay tools (quick list)

`connect`, `status`, `inspect`, `transaction`, `execute_python`, `create_part`, `save/export_document`, sketch draw_*, `extrude`, `revolve`, `fillet`, `chamfer`, `hole`, `hole_linear`, `circular_pattern`, sheet metal thickness/face/flange/cut, params, feature list/delete/suppress, find edge/face.

---

## AutoCAD MCPs — what each has over the others

| Rank | Project | License | Tools | What it has over the others | Why it matters for *your* cloud task |
|------|---------|---------|-------|-----------------------------|--------------------------------------|
| **1** | [puran-water/autocad-mcp](https://github.com/puran-water/autocad-mcp) | MIT | 8 tools × many ops: `drawing`, `entity`, `layer`, `block`, `annotation`, `pid`, `view`, `system` (+ `execute_lisp`) | **Maturity + LT + headless**: most adopted; works on **AutoCAD LT 2024+** via File IPC **or** no AutoCAD via **ezdxf**; focus-free IPC | Lowest friction for many subscribers (LT is common); headless DXF = cloud workers without a GUI seat for some jobs |
| **2** | [U-C4N/Autocad-MCP](https://github.com/U-C4N/Autocad-MCP) | MIT | ~131 tools; lean/core/full profiles; ISO dims/fits/GD&T; quality loop; delivery manifests; optional 3D solids; COM + ezdxf | **Engineering drawing quality**: ISO 129/286/1101, critique/score/finalize, paper space, proof artifacts | Differentiate your cloud offer for mechanical drawing QA — not just “draw a line” |
| **3** | [varavista/autocad-mcp](https://github.com/varavista/autocad-mcp) | Apache-2.0 | 22 tools / 130+ ops including `xref`, `layout`, `electrical`, `validate`, `excel_export`, `nlp`, multi-CAD COM | **Breadth + multi-CAD** (ZWCAD/BricsCAD/GstarCAD) + electrical/NEC helpers | If you later sell beyond Autodesk-only shops |
| **4** | [thepiruthvirajan/…](https://github.com/thepiruthvirajan/autocad-mcp-server) | Apache-2.0 | `create_structure` (wall/door/window/room/…), basic geometry, layers, deletes, zoom | **AEC building primitives** in few calls | Floor-plan / building automation demos; weaker general drafting |
| **5** | [beiming183 …](https://github.com/beiming183-cloud/AutoCAD-MCP) | MIT | puran-like set + `solid`/`product`/`transaction` + audits | **Validation / evidence** emphasis on the puran architecture | Nice hardening ideas; don’t pick over #1/#2 unless you commit to that fork |
| **—** | xstaar | Proprietary | 684 YQArch arch commands | Huge arch command set | Not open for commercial reuse |

**Recommendation for task:** Default **puran-water** (coverage + LT + headless). Offer **U-C4N** as a “Pro drafting / ISO” tier if you want a premium mechanical SKU. Don’t run both full surfaces in one session.

### puran-water ops (by tool)

| Tool | Ops |
|------|-----|
| `drawing` | create, open, info, save, save_as_dxf, plot_pdf, purge, get_variables, undo, redo |
| `entity` | create_line/circle/polyline/rectangle/arc/ellipse/mtext/hatch; list/count/get; copy/move/rotate/scale/mirror/offset*/array/fillet*/chamfer*/erase |
| `layer` | list, create, set_current, set_properties, freeze, thaw, lock, unlock |
| `block` | list, insert, insert_with_attributes, get/update_attribute, define |
| `annotation` | text + linear/aligned/angular/radius dims + leader |
| `pid` | symbols, process lines, valves/instruments/pumps/tanks, tags |
| `view` | zoom_extents/window, get_screenshot |
| `system` | status, health, get_backend, runtime, init, execute_lisp |

### U-C4N differentiator tools (examples)

Quality: `drawing_preflight` → `drawing_plan` → `drawing_critique` → `drawing_refine` → `drawing_finalize` → `drawing_deliver`.  
Standards: ISO fits/GD&T/TABLE/MLEADER.  
Layouts: `layout_*`, `viewport_create`.  
3D (opt-in): `solid_box/cylinder/extrude/revolve/boolean`.

---

## RAG platforms — what each does, why use it, how it applies to your task

Your task needs a **cloneable AI** so subscribers get **private or public** knowledge assistants, plus ChatGPT / open LLM — *alongside* CAD MCPs, not instead of them.

| Rank | Platform | License | What it *does* | Why choose it | How it applies to **your** task |
|------|----------|---------|----------------|---------------|----------------------------------|
| **1** | [AnythingLLM](https://github.com/Mintplex-Labs/anything-llm) | MIT | Full “private ChatGPT” app: upload docs → vector RAG → chat; multi-user workspaces; agents; **MCP client** to call Inventor/AutoCAD tools; embed widget; any LLM (OpenAI, Ollama, …) | Best **product shell** to clone per subscriber (or per tenant workspace): private vs public workspaces, agents that can use CAD MCPs | **Subscriber-facing cloud UI** + tenancy starting point; open LLM path (Ollama/vLLM) and ChatGPT-API path in one product |
| **2** | [OpenRAG](https://github.com/langflow-ai/openrag) | Apache-2.0 | Packaged RAG stack (Langflow + Docling + OpenSearch); chat + search; exposes **HTTP `/mcp`** (search, ingest, RAG chat, filters) | Best **ChatGPT connector** for *knowledge* without reinventing remote MCP | Wire **ChatGPT Developer Mode** to subscriber knowledge bases; complements CAD agents that stay on Windows |
| **3** | [RAGFlow](https://github.com/infiniflow/ragflow) | Apache-2.0 | Deep document understanding (PDFs/tables/layouts), grounded citations, multi-tenant KBs, agent workflows + MCP | Best when **drawing packages / manuals / specs** must be parsed accurately | Backend for “ask our engineering standards PDF” and audit-friendly citations; heavier to operate |

### How RAG + CAD MCP split the job

| User ask | Who answers |
|----------|-------------|
| “What does our company standard say about flange thickness?” | **RAG** (docs in private workspace) |
| “Extrude this sketch 20 mm in Inventor” | **Inventor MCP** |
| “Draw a 100×50 rectangle on layer WALLS” | **AutoCAD MCP** |
| “According to the ISO note in our KB, dimension this hole H7 then draw it” | **RAG then AutoCAD MCP** (multi-MCP agent) |

That’s why multiple MCPs + one RAG platform is the product — not a single repo.

### Suggested wiring for your original brief

| Requirement from you | Piece |
|----------------------|--------|
| Inventor + AutoCAD with Autodesk apps | ipt-mcp + puran-water (Windows agents) |
| Work with ChatGPT | OpenRAG `/mcp` and/or HTTPS gateway exposing CAD tools; ChatGPT connector(s) |
| Open LLM local or cloud | AnythingLLM → Ollama/vLLM **or** cloud OpenAI/Anthropic |
| Cloneable private or public AI | AnythingLLM workspaces (private vs shared/public); optional OpenRAG per tenant |
| Cloud service | Host RAG + LLM router in cloud; keep CAD MCP on Windows (subscriber PC or your CAD farm); optional aggregator later |

**Avoid for SaaS resale without extra licenses:** Dify (SaaS clause), Open WebUI (branding), n8n (fair-code).

---

## Bottom line

1. **Multiple MCPs together: yes, easy at the client; worth it** for Inventor + AutoCAD + knowledge. Don’t merge codebases; don’t attach two overlapping AutoCAD/Inventor servers at once.  
2. **Differentiators that matter:** ipt-mcp = reliability/versions; NeonGlay = sheet-metal/parametric speed; puran-water = LT+headless maturity; U-C4N = ISO/QA pro tier.  
3. **RAG:** AnythingLLM = subscriber product; OpenRAG = ChatGPT knowledge MCP; RAGFlow = hard-document accuracy engine. Together with CAD MCPs they deliver the cloud offer you described.
