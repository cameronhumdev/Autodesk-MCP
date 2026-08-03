# Plan — Autodesk MCP + cloneable RAG cloud

## Docker + Compose + Terraform (all three)

Yes — v1 uses **all three**. They stack; they don’t replace each other.

| | **Docker** (Engine) | **Docker Compose** | **Terraform / OpenTofu** |
|--|---------------------|--------------------|---------------------------|
| Job | The **runtime** that runs container images | The **app recipe** for one stack: which containers, how they link | The **cloud recipe** that creates the machine/network/storage and deploys that Compose stack per subscriber |
| Handles | Pull images, create/run containers, cgroups/networking at engine level | `docker-compose.yml`: services, **networks**, **volumes**, **depends_on**, **healthchecks**, restart policies, env files | VMs (or similar), disks/buckets, DNS/TLS, firewalls, “what goes where”, `subscriber_id` clones |
| Health / failure | Engine can restart a container if asked | **Where we define** healthchecks + restart + “wait for DB before AnythingLLM” | Can replace a whole dead VM / re-apply infra; not the day-to-day process supervisor |
| AI brain | Runs the AnythingLLM **image** | Wires AnythingLLM (+ DB/vector/Ollama if local) as one unit | Places that Compose unit on isolated infra + private storage per subscriber |
| Do we need it? | **Yes** — nothing runs without the engine | **Yes** (v1) — simplest way to run/link the AI stack with healthchecks | **Yes** (cloud) — how we clone and isolate subscribers |

**Short version (order they sit in the stack):**
1. **Terraform / OpenTofu** — builds the VM, disk, DNS (clone per subscriber).  
2. **Docker Engine** — installed on that VM; this is Docker — it runs every container.  
3. **Docker Compose** — file on that VM that tells Docker *which* containers, how they link, **healthchecks**, restarts.  

Local laptop: **Docker Engine + Docker Compose** (no Terraform).  
Cloud clone: **Terraform → Docker Engine → Docker Compose → AnythingLLM**.

**License / cost**

| Tool | Free to use? |
|------|----------------|
| **Docker Engine** (Linux server) | Yes (open source). Docker *Desktop* on work PCs has its own company license rules. |
| **Docker Compose** | Yes — free/OSS (Compose V2 plugin with Engine). |
| **Terraform** CLI | Usable free; HashiCorp BSL. Many teams use **OpenTofu** (MPL-2.0 fork, same workflow). |
| **Terraform Cloud** | Optional SaaS; free tier / paid teams — not required. |

Software licenses for this trio can be $0; you still pay cloud compute.

---

## Simple scope (v1)

### In scope
1. **AnythingLLM** — cloneable private / public AI (docs + chat)
2. **OpenTofu/Terraform module** — spin up one isolated subscriber VM + storage + DNS
3. **Docker Engine** on that VM — container runtime (required)
4. **Docker Compose** on that VM — AnythingLLM (+ DB/vector as needed), healthchecks, networks
5. **Doc ingest** — PDFs and text first; CAD exports later
6. **LLM plug** — cloud API and/or Ollama on the same (or sibling) host
7. **Wire docs only** — private workspace vs shared/public workspace

### Later (v2)
7. Windows **CAD workers** with **ipt-mcp** + **U-C4N** Autocad-MCP  
8. Pipeline: `.ipt` / `.dwg` → PDF/DXF/properties → into that subscriber’s RAG  
9. ChatGPT remote MCP connector / HTTPS gateway  
10. Billing / signup automation  

### Out of scope for v1
- Merging Inventor + AutoCAD into one MCP binary  
- Raw binary `.ipt`/`.dwg` as RAG documents without export  
- Multi-region HA / full Kubernetes (unless you already standardize on it)

---

## Operation flow

### A. Provision (clone a subscriber AI)

```mermaid
flowchart TD
  T[1 Terraform / OpenTofu]
  VM[2 VM + disk + HTTPS]
  DE[3 Docker Engine]
  DC[4 Docker Compose]
  ALLM[5 AnythingLLM container]
  LLM[Ollama or API config]
  Vol[Private subscriber volume]

  T --> VM
  VM --> DE
  DE --> DC
  DC -->|healthchecks networks volumes| ALLM
  DC --> LLM
  Vol --> ALLM
  LLM --> ALLM
```

Docker is step **3** — not optional, not the same thing as Compose.

### B. Day-to-day use (private or public AI)

```mermaid
flowchart TD
  User[Subscriber user]
  User -->|HTTPS chat| ALLM[AnythingLLM]
  ALLM -->|retrieve chunks| Docs[Their PDFs / exports on private storage]
  ALLM -->|prompt + context| Brain[LLM: OpenAI API or Ollama]
  Brain --> ALLM
  ALLM --> User

  Admin[Admin]
  Admin -->|upload docs| Docs
  Admin -->|set workspace private or shared| ALLM
```

### C. Later: CAD in the loop (v2)

```mermaid
flowchart TD
  User[User in AnythingLLM or ChatGPT]
  User --> ALLM[AnythingLLM]
  ALLM -->|ask standards / manuals| RAG[Doc RAG]
  ALLM -->|tool call MCP| Bridge[HTTPS or local MCP bridge]
  Bridge --> Inv[ipt-mcp on Windows + Inventor]
  Bridge --> ACad[U-C4N on Windows + AutoCAD]
  Inv --> CADFiles[Models / drawings]
  ACad --> CADFiles
  CADFiles -->|export PDF DXF props| RAG
```

---

## What “separate” means per subscriber

| Layer | Isolation |
|-------|-----------|
| Infra | Own VM **or** own Compose project + volumes (Terraform module input: `subscriber_id`) |
| Data | Own disk/bucket — other tenants cannot read it |
| AI brain | Own AnythingLLM workspace(s); private by default |
| Public AI | Optional second workspace marked shared, or embed widget |
| CAD (v2) | Optional dedicated Windows worker or pooled workers with strict tenant auth |

---

## Build order (start creating)

| Step | Deliverable |
|------|-------------|
| 1 | Install **Docker Engine** + **Docker Compose** locally |
| 2 | Compose file: AnythingLLM up, chat + PDF upload works |
| 3 | OpenTofu/Terraform: one VM, install **Docker Engine**, run Compose, volume + HTTPS |
| 4 | Parameterize: `subscriber_id`, private vs public workspace flags |
| 5 | Document “clone” = `tofu apply -var=subscriber_id=acme` |
| 6 | (v2) Windows CAD worker + MCP + export-to-RAG path |

---

## Stack choices (locked for v1)

| Role | Choice | License |
|------|--------|---------|
| RAG / cloneable AI | AnythingLLM | MIT |
| Container runtime | Docker Engine | OSS |
| App stack / healthchecks | Docker Compose | OSS |
| Infra as code | OpenTofu (Terraform-compatible) | MPL-2.0 |
| Inventor MCP (v2) | ipt-mcp | Apache-2.0 |
| AutoCAD MCP (v2) | U-C4N Autocad-MCP | MIT |
