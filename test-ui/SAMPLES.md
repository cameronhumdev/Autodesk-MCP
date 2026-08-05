# Sample prompts

Click a sample in the UI or paste these into chat.

## 1. Health check

```
Call the health tool and report Inventor and AutoCAD track status (live MCP modes).
```

## 2. Company standard (RAG)

```
What is our minimum flange thickness for DN50? Search the knowledge base first.
```

## 3. Layer standard (RAG)

```
Which AutoCAD layer should dimensions go on? Use knowledge search.
```

## 4. Inventor track (live ipt-mcp)

```
Using Inventor tools only: create part DemoFlange, set parameter Thickness to 8 mm, then inventor_export_to_rag. Do not call AutoCAD tools.
```

## 5. AutoCAD track (live U-C4N)

```
Using AutoCAD tools only: create a rectangle 100 by 50 on layer WALLS, list layers, then autocad_export_to_rag. Do not call Inventor tools.
```

## 6. Multi-step Inventor + RAG

```
1) Search knowledge for flange thickness.
2) Inventor only: create part DemoFlange and set Thickness to that standard.
3) Export the Inventor part to RAG.
Summarize each tool. Do not use AutoCAD.
```

## 7. Echo / sandbox

```
Use the echo tool with message "hello from Autodesk-MCP".
```
