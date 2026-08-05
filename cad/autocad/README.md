# AutoCAD track (`cad/autocad/`)

| Item | Value |
|------|--------|
| Upstream | https://github.com/U-C4N/Autocad-MCP (`autocad-mcp-pro`) |
| License | MIT |
| OS | Windows + AutoCAD (COM) **or** headless `ezdxf` |
| Package import | add `cad/` to `PYTHONPATH`, then `from autocad import get_autocad_backend` |

**Separate from Inventor.** Do not share backends or merge tools with `cad/inventor/`.

## Modes

| `AUTOCAD_BACKEND` | Behavior |
|-------------------|----------|
| `mock` (default) | In-process stand-in — no AutoCAD required |
| `mcp` | Stdio client to `autocad-mcp` |

```text
AUTOCAD_BACKEND=mcp
AUTOCAD_MCP_COMMAND=autocad-mcp
AUTOCAD_MCP_BACKEND=ezdxf
```

Headless path (no AutoCAD app):

```bat
pip install autocad-mcp-pro
set AUTOCAD_BACKEND=mcp
set AUTOCAD_MCP_COMMAND=autocad-mcp
set AUTOCAD_MCP_BACKEND=ezdxf
```

Live AutoCAD: `AUTOCAD_MCP_BACKEND=com` (and install COM extras per upstream docs).

## Façade tools (test-ui)

- `autocad_status`
- `autocad_create_rectangle`
- `autocad_list_layers`
- `autocad_export_to_rag` → RAG doc id `autocad:drawing:session`

## Layout

```text
autocad/
  adapter.py
  mock_backend.py
  mcp_backend.py   # U-C4N tool mapping
  factory.py
  rag_export.py
```
