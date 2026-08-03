# Autodesk MCP + RAG

Research repo for an Autodesk-oriented cloud AI service:

- **Inventor MCP:** [bimwright/ipt-mcp](https://github.com/bimwright/ipt-mcp) (Apache-2.0)
- **AutoCAD MCP:** [U-C4N/Autocad-MCP](https://github.com/U-C4N/Autocad-MCP) (MIT)
- **Cloneable private/public AI (RAG):** [AnythingLLM](https://github.com/Mintplex-Labs/anything-llm) (MIT)

MCP servers drive Inventor/AutoCAD. AnythingLLM is the subscriber-facing AI (docs + chat; private or public workspaces). LLMs are pluggable (OpenAI / open local models).

**Plan:** [PLAN.md](./PLAN.md) — Docker + Kubernetes + Terraform/OpenTofu, scope, flows, build order.

Status: planning. Implementation not started.
