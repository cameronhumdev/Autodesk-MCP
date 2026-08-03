# Autodesk MCP + RAG — comparison research

Ordered shortlists for **Inventor MCPs**, **AutoCAD MCPs**, and **cloneable RAG / private AI** platforms suitable for a commercial cloud service.

Status: **research only**.  
Licenses below are the **open-source project licenses** (not Autodesk product licensing).

**Repo:** https://github.com/cameronhumdev/Autodesk-MCP

---

## Do these work with any LLM?

**Yes at the protocol level.** MCP servers do not bind to one model. Any **MCP client** can call their tools; the client chooses the LLM.

| What | LLM-specific? | Detail |
|------|---------------|--------|
| Inventor / AutoCAD MCP servers | No | Speak MCP. Work with ChatGPT, Claude, Cursor, AnythingLLM, custom agents, etc. |
| RAG platforms | No | You plug in OpenAI, Anthropic, Azure, Ollama, vLLM, OpenRouter, … |
| ChatGPT as the UI | OpenAI models only (inside ChatGPT) | Needs **remote HTTPS** MCP, not local stdio |
| Tool quality | Model-dependent | Weak / non-tool-trained models may skip or misuse tools |

---

# 1. Inventor MCPs (ordered)

## Ranked comparison

| Rank | Project | License | Commercial OK? | Benefits | Disadvantages |
|------|---------|---------|----------------|----------|---------------|
| **1** | [bimwright/ipt-mcp](https://github.com/bimwright/ipt-mcp) | Apache-2.0 | Yes | In-process add-in (STA-safe); Inventor **2022–2027**; ~**46 tools**; read-only mode; authenticated local pipe; server builds without Inventor; export STEP/STL/DXF; ToolBaker | Heavier .NET setup; Windows-only; smaller community than AutoCAD peers |
| **2** | [NeonGlay/inventor-mcp](https://github.com/NeonGlay/inventor-mcp) | MIT | Yes | **34 tools**; fast Python install; high-level mm parametric tools; sheet metal + tapped holes; Inventor 2026 API notes; `execute_python` escape hatch | Out-of-process COM (less robust than add-in); mainly part/sheet-metal focused |
| **3** | [Cadtastic-Solutions/Autodesk-Inventor-MCP](https://github.com/cadtastic-solutions/autodesk-inventor-mcp) | Apache-2.0 | Yes | Solid .NET 8 session infrastructure; Inventor 2025+; Claude plugin packaging | Tool surface today is **session lifecycle**, not full modeling suite |
| **—** | [hsavas/inventor-mcp](https://github.com/hsavas/inventor-mcp) | Custom | **No** without permission | Broad domains: sketch, feature, assembly, drawing, export, view | **Non-commercial unless author grants written permission** |

---

## Actual tools — Rank 1: ipt-mcp (~46)

| Toolset | Tools |
|---------|-------|
| **meta** | `inventor_list_available_targets`, `inventor_get_current_target`, `inventor_switch_target` |
| **query** | `inventor_health`, `inventor_list_open_documents`, `inventor_get_document_info` |
| **document** | `inventor_new_part`, `inventor_new_assembly`, `inventor_open_document`, `inventor_save_document`, `inventor_close_document`, `inventor_set_units`, `inventor_set_material` |
| **parameters** | `inventor_list_parameters`, `inventor_get_parameter`, `inventor_set_parameter`, `inventor_create_parameter` |
| **properties** | `inventor_get_iproperty`, `inventor_set_iproperty`, `inventor_get_mass_properties` |
| **sketch** | `inventor_create_sketch`, `inventor_project_geometry`, `inventor_draw_line`, `inventor_draw_circle`, `inventor_draw_rectangle`, `inventor_draw_arc`, `inventor_add_sketch_dimension`, `inventor_add_sketch_constraint`, `inventor_close_sketch` |
| **feature** | `inventor_extrude`, `inventor_revolve`, `inventor_fillet`, `inventor_chamfer`, `inventor_create_work_plane`, `inventor_create_work_axis` |
| **export** | `inventor_capture_view`, `inventor_export_step`, `inventor_export_stl`, `inventor_export_dxf` |
| **code** (opt-in, off by default) | `inventor_send_code` |
| **toolbaker** | `inventor_list_baked_tools`, `inventor_list_bake_suggestions`, `inventor_create_bake_issue_draft`, `inventor_run_baked_tool`, `inventor_accept_bake_suggestion`, `inventor_dismiss_bake_suggestion` |

---

## Actual tools — Rank 2: NeonGlay inventor-mcp (34)

| Area | Tools |
|------|-------|
| Session / meta | `connect`, `status`, `inspect`, `reload_api`, `transaction`, `execute_python` |
| Document | `create_part`, `save_document`, `export_document` |
| Query geometry | `list_edges`, `list_faces`, `find_edge`, `find_face`, `list_features` |
| Sketch | `create_sketch`, `draw_rectangle`, `draw_circle`, `draw_line`, `draw_polygon`, `draw_closed_profile` |
| Solid features | `extrude`, `revolve`, `fillet`, `chamfer`, `hole`, `hole_linear`, `circular_pattern` |
| Feature edit | `delete_feature`, `suppress_feature` |
| Parameters | `get_parameters`, `set_parameter`, `add_parameter` |
| Sheet metal | `set_sheet_metal_thickness`, `sheet_metal_face`, `flange`, `sheet_metal_cut` |

---

## Actual tools — Rank 3: Cadtastic Autodesk-Inventor-MCP

| Area | Tools (current skeleton) |
|------|--------------------------|
| Session | `inventor_versions_list`, `inventor_session_start`, `inventor_session_adopt`, `inventor_session_list`, `inventor_session_terminate` |

Modeling tools are roadmap / branch features — not a full part-modeling MCP yet.

---

## Actual tools — Excluded: hsavas (license block)

Organized modules (not for commercial use without permission): `sketch_tools`, `feature_tools`, `assembly_tools`, `drawing_tools`, `geometry_tools`, `parameter_tools`, `property_tools`, `appearance_tools`, `export_tools`, `view_tools`, `app_tools`.

---

# 2. AutoCAD MCPs (ordered)

## Ranked comparison

| Rank | Project | License | Commercial OK? | Benefits | Disadvantages |
|------|---------|---------|----------------|----------|---------------|
| **1** | [puran-water/autocad-mcp](https://github.com/puran-water/autocad-mcp) | MIT | Yes | Most mature (~400+★); **8 consolidated tools** + many ops; File IPC (LT 2024+) **or** headless ezdxf; focus-free automation; `execute_lisp` escape hatch; companion drafting skill | File IPC aimed at LT; P&ID needs CTO library; not the richest ISO/GD&T set |
| **2** | [U-C4N/Autocad-MCP](https://github.com/U-C4N/Autocad-MCP) (`autocad-mcp-pro`) | MIT | Yes | **~131 tools**; COM + ezdxf; ISO 129/286/1101 GD&T; quality loop + delivery manifests; lean/core/full profiles; optional 3D solids; HTTP option | Newer project; denser tool surface can overwhelm weak models (use `TOOL_PROFILE=lean`) |
| **3** | [varavista/autocad-mcp](https://github.com/varavista/autocad-mcp) | Apache-2.0 | Yes | **22 tools / 130+ ops**; File IPC + COM + ezdxf; multi-CAD (ZWCAD, BricsCAD, GstarCAD); xref, electrical, Excel, NLP | Low adoption; more to validate in production |
| **4** | [thepiruthvirajan/autocad-mcp-server](https://github.com/thepiruthvirajan/autocad-mcp-server) | Apache-2.0 | Yes | Simple COM; building-structure helpers (`create_structure` wall/door/window/room); clear API docs | Narrower general CAD surface; AEC-oriented |
| **5** | [beiming183-cloud/AutoCAD-MCP](https://github.com/beiming183-cloud/AutoCAD-MCP) | MIT | Yes | Based on puran-water line; stronger validation / evidence focus | Smaller community; fork lineage |
| **—** | [xstaar/autocad-mcp](https://github.com/xstaar/autocad-mcp) | Proprietary | **No** | 684 YQArch arch commands / 55 tools | Activation system; not open for commercial reuse |

---

## Actual tools — Rank 1: puran-water/autocad-mcp

8 MCP tools; each takes an `operation` (+ data). Ops:

| MCP tool | Operations |
|----------|------------|
| **`drawing`** | `create`, `open`, `info`, `save`, `save_as_dxf`, `plot_pdf`, `purge`, `get_variables`, `undo`, `redo` |
| **`entity`** | Create: `create_line`, `create_circle`, `create_polyline`, `create_rectangle`, `create_arc`, `create_ellipse`, `create_mtext`, `create_hatch` · Read: `list`, `count`, `get` · Modify: `copy`, `move`, `rotate`, `scale`, `mirror`, `offset`*, `array`, `fillet`*, `chamfer`*, `erase` |
| **`layer`** | `list`, `create`, `set_current`, `set_properties`, `freeze`, `thaw`, `lock`, `unlock` |
| **`block`** | `list`, `insert`, `insert_with_attributes`, `get_attributes`, `update_attribute`, `define` (ezdxf) |
| **`annotation`** | `create_text`, `create_dimension_linear`, `create_dimension_aligned`, `create_dimension_angular`, `create_dimension_radius`, `create_leader` |
| **`pid`** | `setup_layers`, `insert_symbol`, `list_symbols`, `draw_process_line`, `connect_equipment`, `add_flow_arrow`, `add_equipment_tag`, `add_line_number`, `insert_valve`, `insert_instrument`, `insert_pump`, `insert_tank` |
| **`view`** | `zoom_extents`, `zoom_window`, `get_screenshot` |
| **`system`** | `status`, `health`, `get_backend`, `runtime`, `init`, `execute_lisp` |

\* `offset` / `fillet` / `chamfer` = File IPC only (not ezdxf).

---

## Actual tools — Rank 2: U-C4N Autocad-MCP (~131; profiles lean/core/full)

| Area | Representative tools / capabilities |
|------|-------------------------------------|
| Drawing lifecycle | create, open, save, export DXF/PDF, audit, purge, undo/redo |
| Geometry | lines, arcs, polylines, splines, hatches, trim/extend/fillet/chamfer, handle-preserving edits |
| Annotation | ISO 129 dimensions, ISO 286 fits (`fit="H7"`), TABLE, MLEADER, GD&T frames + datums (ISO 1101) |
| Engineering generators | involute gears, DIN 6885 keyed bores, ISO A3 titleblock |
| Paper space | `layout_list`, `layout_create`, `layout_set_current`, `viewport_create`, `drawing_export_pdf` |
| 3D solids (opt-in `ENABLE_3D`) | `solid_box`, `solid_cylinder`, `solid_extrude`, `solid_revolve`, `solid_boolean` |
| Quality loop | `drawing_preflight` → `drawing_plan` → `drawing_critique` → `drawing_refine` → `drawing_finalize` |
| Delivery | `drawing_deliver` (DXF/PDF/PNG + SHA-256 manifest) |
| Discovery | `system_about`, `system_capabilities`, `system_status` |

Runtime inventory via `system_about` is authoritative.

---

## Actual tools — Rank 3: varavista/autocad-mcp (22 tools)

| # | Tool | Operations (summary) |
|---|------|----------------------|
| 1 | `drawing` | create, open, save, info, purge, plot_pdf, undo, redo, audit, units, limits, wblock |
| 2 | `entity` | create_line/circle/polyline/rectangle/arc/ellipse/mtext/hatch; list/count/get; copy/move/rotate/scale/mirror/offset/array/fillet/chamfer/erase/explode/join/extend/trim/break_at |
| 3 | `layer` | list, create, set_current, set_properties, freeze, thaw, lock, unlock |
| 4 | `block` | list, insert, insert_with_attributes, get/update attributes, define |
| 5 | `annotation` | create_text, linear/aligned/angular/radius dims, create_leader |
| 6 | `pid` | setup_layers, insert_symbol, list_symbols, process lines, valves/instruments/pumps/tanks |
| 7 | `view` | zoom_extents/window/center, pan, zoom_scale, screenshot, layer_visibility |
| 8 | `system` | status, health, runtime, init, execute_lisp |
| 9 | `query` | entity_properties/geometry, drawing/layer summary, styles, block_tree, metadata |
| 10 | `search` | text, by_attribute/window/proximity/type/layer/block/handle, equipment find/inspect |
| 11 | `geometry` | distance, length, area, bounding_box, polyline_info |
| 12 | `select` | filter, bulk_move/copy/erase/set_property, find_replace, layer_rename/merge |
| 13 | `modify` | set_property, set_text |
| 14 | `validate` | layer/text standards, orphaned, attributes, connectivity, duplicates, QC report |
| 15 | `export` | entity_data, bom, data_extract, layer_report, block_count, drawing_statistics |
| 16 | `xref` | list, attach, detach, reload, bind, path_update, query_entities |
| 17 | `layout` | list/create/switch/delete, viewport_*, page_setup, titleblock_fill, batch_plot |
| 18 | `electrical` | nec_lookup, voltage_drop, conduit_fill, load_calc, symbol_insert, circuit_trace, panel_schedule_gen, wire_number_assign |
| 19 | `connection` | connect, disconnect, status, list_supported, switch_backend |
| 20 | `batch` | draw_lines/circles/rectangles/polylines/texts |
| 21 | `nlp` | parse + execute natural-language CAD commands |
| 22 | `excel_export` | full_export, selected_export |

---

## Actual tools — Rank 4: thepiruthvirajan/autocad-mcp-server

| Tool | Purpose |
|------|---------|
| `get_drawing_info` | Drawing path, layers, entity counts |
| `get_entities` | List entities (optional max), grouped by layer |
| `create_structure` | Intelligent AEC: `wall`, `door`, `window`, `room`, `furniture`, `outlet`, `switch`, `light`, … |
| `create_line` | Line |
| `create_circle` | Circle |
| `create_rectangle` | Rectangle |
| `create_text` | Text label |
| `create_arc` | Arc |
| `create_or_get_layer` | Layer create/get |
| `set_current_layer` | Set active layer |
| `delete_entity_by_handle` | Delete by handle |
| `delete_entities_by_layer` | Delete layer contents |
| `delete_entities_by_type` | Delete by entity type |
| `delete_entities_by_color` | Delete by color |
| `delete_last_entities` | Delete last N |
| `undo_last_operation` | Undo |
| `change_entity_color` | Recolor entity |
| `zoom_extents` | Zoom extents |

---

## Actual tools — Rank 5: beiming183-cloud/AutoCAD-MCP

Same consolidated pattern as puran-water lineage:

`drawing`, `entity`, `solid`, `product`, `layer`, `block`, `annotation`, `pid`, `transaction`, `view`, `system` — with extra geometry audit / product-contract emphasis.

---

# 3. RAG / private AI platforms (ordered)

## Ranked comparison

| Rank | Project | License | Commercial SaaS OK? | Benefits | Disadvantages |
|------|---------|---------|---------------------|----------|---------------|
| **1** | [Mintplex-Labs/anything-llm](https://github.com/Mintplex-Labs/anything-llm) | MIT | Yes | Closest to “cloneable private ChatGPT”; multi-user Docker; workspaces; agents; **MCP client**; embed widget; many LLM + vector DB backends | You still build billing/tenancy/governance for a cloud product |
| **2** | [langflow-ai/openrag](https://github.com/langflow-ai/openrag) | Apache-2.0 | Yes | Packaged RAG (Langflow + Docling + OpenSearch); built-in **HTTP `/mcp`** for ChatGPT/Cursor; agentic RAG | Heavier stack; younger than AnythingLLM |
| **3** | [infiniflow/ragflow](https://github.com/infiniflow/ragflow) | Apache-2.0 | Yes | Best-in-class deep doc parsing; grounded citations; multi-tenant KBs; agents + MCP | Heavier ops; less “simple ChatGPT clone” UX |

### Avoid / constrain for multi-tenant resale

| Project | Why |
|---------|-----|
| [Dify](https://github.com/langgenius/dify) | Modified Apache — multi-tenant SaaS restricted without their commercial license |
| [Open WebUI](https://github.com/open-webui/open-webui) | Branding clause; white-label needs enterprise license |
| [n8n](https://github.com/n8n-io/n8n) | Fair-code SaaS restrictions |

---

## Actual capabilities / tools — Rank 1: AnythingLLM

| Capability | What it exposes |
|------------|-----------------|
| Workspaces | Isolated doc + chat contexts (private/public-style separation) |
| Document RAG | Upload/ingest PDFs, office docs, etc.; chat with citations |
| Agents / Agent Flows | Web browse, scrape, SQL, custom skills; no-code flows |
| **MCP** | Connect external MCP servers (e.g. Inventor/AutoCAD) as agent tools |
| Multi-user | Users + permissions (Docker) |
| Embed | Website chat widget |
| API | Developer API for custom clients |
| Memories | Automatic / user-managed memory |
| LLM providers | OpenAI, Anthropic, Gemini, Azure, Bedrock, Groq, OpenRouter, Mistral, DeepSeek, **Ollama**, LM Studio, LocalAI, llama.cpp, LiteLLM, … |
| Vector DBs | LanceDB (default), PGVector, Chroma, Pinecone, Qdrant, Weaviate, Milvus, … |

---

## Actual capabilities / tools — Rank 2: OpenRAG

| Capability | What it exposes |
|------------|-----------------|
| Ingest | Upload + Docling parsing via Langflow workflows |
| Search / chat | Semantic search + LLM answers over OpenSearch |
| Agentic RAG | Re-ranking / multi-agent style orchestration |
| Visual builder | Langflow drag-and-drop pipelines |
| **MCP (`/mcp`)** | Streamable HTTP MCP: RAG chat, semantic search, document ingestion, knowledge filters, settings |
| SDKs | Python + TypeScript |
| Auth | API key (`X-API-Key`) on REST and MCP |

---

## Actual capabilities / tools — Rank 3: RAGFlow

| Capability | What it exposes |
|------------|-----------------|
| DeepDoc parsing | Layout-aware PDF/DOCX/XLSX/PPT/images/tables |
| Chunk templates | Configurable chunking strategies |
| Grounded answers | Paragraph-level citations |
| Knowledge bases | Multi-tenant datasets |
| Agents | Visual agentic workflows + code executor; MCP support |
| Recall | Hybrid / multiple recall strategies |
| LLM / embed | Configurable providers (cloud + local) |
| Deploy | Docker self-host |

---

## LLM runners to pair with RAG (any of these)

| Runner | License | Role |
|--------|---------|------|
| OpenAI / Azure / Anthropic / Gemini / OpenRouter | Proprietary API | Cloud models via AnythingLLM / OpenRAG / RAGFlow |
| [Ollama](https://github.com/ollama/ollama) | MIT | Local / private open models |
| vLLM | Apache-2.0 | Self-hosted high-throughput serving |
| llama.cpp | MIT | Local inference |

---

# 4. Client wiring

| Client | Transport | LLM | Can use Inventor/AutoCAD MCP? | Can use RAG? |
|--------|-----------|-----|-------------------------------|--------------|
| ChatGPT Developer Mode | Remote **HTTPS** MCP | OpenAI | Yes (bridge Windows CAD MCP → HTTPS) | OpenRAG `/mcp` or custom knowledge MCP |
| Cursor | stdio or HTTP | Any Cursor model | Yes (stdio on CAD Windows box) | Via MCP or separate UI |
| Claude Desktop / Code | stdio | Anthropic | Yes | Via MCP |
| AnythingLLM | MCP + built-in RAG | Any configured provider | Yes | Built-in |

---

# 5. Suggested product shortlist

| Layer | Pick | License |
|-------|------|---------|
| Inventor | **ipt-mcp** | Apache-2.0 |
| AutoCAD | **puran-water/autocad-mcp** (add **U-C4N** if you need full AutoCAD COM + ISO/GD&T) | MIT |
| Subscriber private/public AI | **AnythingLLM** | MIT |
| ChatGPT knowledge connector | **OpenRAG** `/mcp` | Apache-2.0 |

---

# 6. Next (not done)

- [ ] Vendor shortlisted repos (submodules or forks) with LICENSE notices
- [ ] HTTPS MCP bridge: ChatGPT ↔ Windows Inventor/AutoCAD agents
- [ ] Tenant model on AnythingLLM (private vs public workspaces)
- [ ] Smoke-test against local Inventor + AutoCAD installs

---

*Re-check each upstream `LICENSE` before shipping; terms can change.*
