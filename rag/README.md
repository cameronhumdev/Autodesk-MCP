# `rag/` — Knowledge / cloneable AI (swappable)

| Item | Value |
|------|--------|
| Default | AnythingLLM (MIT) |
| Role | Private / public subscriber AI over documents |
| Replace by | Drop in another adapter that implements `adapter.py` |

## Layout

```text
rag/
  README.md
  adapter.py          # Interface every RAG backend must satisfy
  local/              # Tiny file RAG for local tests (no AnythingLLM required)
  anythingllm/        # Notes + hook points for AnythingLLM (v1 cloud)
```

## Swap

1. Implement `RagBackend` in a new folder.
2. Set `RAG_BACKEND=local|anythingllm|<your_name>` (see `docker/` / `test-ui/`).
3. Leave other modules unchanged.

## Docs

- Local backend: [`local/README.md`](./local/README.md)
- AnythingLLM: [`anythingllm/README.md`](./anythingllm/README.md)
