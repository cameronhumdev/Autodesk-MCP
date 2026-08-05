# Inventor track (`cad/inventor/`)

| Item | Value |
|------|--------|
| Upstream | https://github.com/bimwright/ipt-mcp |
| License | Apache-2.0 |
| OS | Windows + Inventor (for live MCP) |
| Package import | add `cad/` to `PYTHONPATH`, then `from inventor import get_inventor_backend` |

**Separate from AutoCAD.** Do not share backends or merge tools with `cad/autocad/`.

## Modes

| `INVENTOR_BACKEND` | Behavior |
|--------------------|----------|
| `mock` (default) | In-process stand-in — no Inventor required |
| `mcp` | Stdio client to `Bimwright.Ipt.Server.exe` |

```text
INVENTOR_BACKEND=mcp
INVENTOR_MCP_COMMAND=D:\path\to\Bimwright.Ipt.Server.exe
```

Live mode also needs the ipt-mcp Inventor add-in loaded in a running Inventor session.

## Façade tools (test-ui)

- `inventor_status`
- `inventor_create_part`
- `inventor_set_parameter`
- `inventor_export_to_rag` → RAG doc id `inventor:part:<name>`

## Layout

```text
inventor/
  adapter.py       # Protocol
  mock_backend.py
  mcp_backend.py   # ipt-mcp mapping
  factory.py
  rag_export.py
```
