# Best picks (no tiers) — open license only

Re-ranked for **what is best to use**, not product packaging.  
Your request was: Inventor + AutoCAD MCP, ChatGPT + open LLM, cloneable private/public AI, cloud service, commercial-friendly OSS.

---

## Inventor MCP — best first

| Rank | Project | License | Why this rank |
|------|---------|---------|---------------|
| **1 — use this** | [bimwright/ipt-mcp](https://github.com/bimwright/ipt-mcp) | Apache-2.0 | Best overall: in-process Inventor add-in, 2022–2027, ~46 real modeling tools, read-only mode, safer for agents/cloud. Core and trustworthy. |
| **2** | [NeonGlay/inventor-mcp](https://github.com/NeonGlay/inventor-mcp) | MIT | Strong runner-up if you want faster Python setup and sheet-metal / tapped-hole shortcuts. Less robust than an in-process add-in. |
| **3** | [Cadtastic Autodesk-Inventor-MCP](https://github.com/cadtastic-solutions/autodesk-inventor-mcp) | Apache-2.0 | Session management only today — not enough to drive real modeling alone. |
| Skip | hsavas/inventor-mcp | Custom | Not free for commercial use. |

**Inventor decision: ipt-mcp.**

---

## AutoCAD MCP — best first

More tools can be better **if** they are high quality and open-licensed. U-C4N’s “Pro” name is **not paid** — it is still **MIT**.

| Rank | Project | License | Why this rank |
|------|---------|---------|---------------|
| **1 — use this** | [U-C4N/Autocad-MCP](https://github.com/U-C4N/Autocad-MCP) (`autocad-mcp-pro` on PyPI) | **MIT (free, commercial OK)** | Best capability set: ~131 tools, live AutoCAD COM **and** headless ezdxf, ISO dimension/fits/GD&T, paper space, quality/check/deliver workflow, optional 3D solids. Best match if you have full AutoCAD and want the strongest open server. |
| **2** | [puran-water/autocad-mcp](https://github.com/puran-water/autocad-mcp) | MIT | Most proven in the community (~400★). Excellent if you need AutoCAD **LT** or a simpler, battle-tested surface. Slightly less “engineering drawing” depth than U-C4N. |
| **3** | [varavista/autocad-mcp](https://github.com/varavista/autocad-mcp) | Apache-2.0 | Very wide tool list (xref, electrical, Excel, multi-CAD). Not ranked #1 because adoption/proof is thin — more tools on paper, less evidence in the wild. |
| **4** | [thepiruthvirajan/autocad-mcp-server](https://github.com/thepiruthvirajan/autocad-mcp-server) | Apache-2.0 | Fine for building/AEC shortcuts; narrower than #1/#2 for general CAD. |
| Skip | xstaar/autocad-mcp | Proprietary | Not open for commercial reuse. |

**AutoCAD decision: U-C4N first** (best open capability for full AutoCAD).  
Keep puran-water in mind only if you hit LT-only environments or need the most community-proven path.

### Why “more tools” didn’t auto-win for varavista

| | U-C4N | varavista | puran-water |
|--|-------|-----------|-------------|
| Tool volume | Very high | Very high | Medium (consolidated) |
| Open license | MIT | Apache-2.0 | MIT |
| Evidence / maturity | Benchmarks, tests, packaging | Low stars / early | Highest community use |
| Full AutoCAD COM | Yes | Yes | File IPC / LT-oriented (+ ezdxf) |
| Engineering standards | Strong (ISO/GD&T) | Some domain extras | Basic drafting + P&ID |

So: **U-C4N = best; varavista = lots of tools but not proven best; puran-water = safest proven alternative.**

---

## RAG — human language (what each provides)

Think of the LLM as a smart person with **no access to your company’s files** unless you give them a library.

**RAG = that library + a librarian.**  
You upload manuals, standards, specs, past project notes. When someone asks a question, the system finds the relevant pages and the AI answers from those — not from guesswork.

### Why RAG exists in *this* project

You asked for a cloud service where subscribers get a **private or public AI**.

| Without RAG | With RAG |
|-------------|----------|
| AI can drive Inventor/AutoCAD (via MCP) but only knows general knowledge | AI can also answer from **that subscriber’s documents** |
| “Draw a flange” works | “What’s *our* flange standard, then model it” works |
| No cloneable “company brain” | Each subscriber (or public site) gets their own knowledge base |

CAD MCP = hands on the Autodesk app.  
RAG = memory of documents.  
LLM = brain that uses both.

---

### Each RAG option in plain English

| Rank | Name | In human language, what you get | Best for your task because… |
|------|------|----------------------------------|-----------------------------|
| **1 — use this** | **AnythingLLM** | An app that feels like **your own ChatGPT**. People log in, upload PDFs/docs, chat with them, and (via MCP) can also trigger Inventor/AutoCAD tools. Supports OpenAI **or** a local/open model (Ollama etc.). Multi-user. You can give each customer a private space, or a shared/public one. | Closest to “cloneable private/public AI” as a product people actually use. |
| **2** | **OpenRAG** | A **document search + Q&A engine** with a ready-made **web plug** so ChatGPT can query that knowledge over the internet (`/mcp`). Less of a full “ChatGPT clone” UI; more of a knowledge backend ChatGPT/Cursor can attach to. | When the main front door is **ChatGPT** and you need their knowledge base reachable remotely. |
| **3** | **RAGFlow** | A **heavy-duty document reader**: especially good at messy PDFs, tables, drawings-as-docs — then answers with clear “this came from page X” style grounding. | When document accuracy (specs, standards packs) matters more than a pretty all-in-one chat app. |

**RAG decision: AnythingLLM** as the subscriber-facing AI product; add OpenRAG if ChatGPT-as-front-door knowledge is required; use RAGFlow ideas/stack if PDF/table quality becomes the bottleneck.

---

## Final stack (best, open license only)

| Role | Pick | License |
|------|------|---------|
| Inventor | **ipt-mcp** | Apache-2.0 |
| AutoCAD | **U-C4N/Autocad-MCP** | MIT |
| Subscriber private/public AI (RAG app) | **AnythingLLM** | MIT |
| Optional ChatGPT knowledge pipe | OpenRAG | Apache-2.0 |

No paid MCP/RAG “pro license” in this shortlist — “Pro” in U-C4N’s name is branding only.
