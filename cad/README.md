# `cad/` — separate Autodesk MCP tracks (real by default)

Inventor and AutoCAD are **not one module**.

| Track | Folder | Upstream | Default |
|-------|--------|----------|---------|
| Inventor | `cad/inventor/` | bimwright/ipt-mcp | `INVENTOR_BACKEND=mcp` |
| AutoCAD | `cad/autocad/` | U-C4N autocad-mcp-pro | `AUTOCAD_BACKEND=mcp` |

```text
cad/
  shared/stdio_client.py   # official MCP Python SDK client
  inventor/
  autocad/
```

Add **`cad/`** to `PYTHONPATH`, then:

```python
from inventor import get_inventor_backend, export_inventor_to_rag
from autocad import get_autocad_backend, export_autocad_to_rag
```

(`cad/` was renamed from `mcp/` so it does not shadow the official `mcp` Python package.)

Mock backends exist only if you set `*_BACKEND=mock` — not used by the product path.
