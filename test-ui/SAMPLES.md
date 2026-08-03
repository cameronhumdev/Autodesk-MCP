# Sample prompts

Click a sample in the UI or paste these into chat.

## 1. Health check

```
Call the health tool and tell me if the test stack is up.
```

## 2. Company standard (RAG)

```
What is our minimum flange thickness for DN50? Search the knowledge base first.
```

## 3. Layer standard (RAG)

```
Which AutoCAD layer should dimensions go on? Use knowledge search.
```

## 4. Mock Inventor action

```
Create a mock Inventor part named DemoFlange, then set parameter Thickness to 8 mm.
```

## 5. Mock AutoCAD action

```
In mock AutoCAD, create a rectangle 100 by 50 on layer WALLS, then list layers.
```

## 6. Multi-step demo

```
1) Search knowledge for flange thickness.
2) Create a mock Inventor part DemoFlange.
3) Set Thickness to that standard value.
Summarize each tool you used.
```

## 7. Echo / sandbox

```
Use the echo tool with message "hello from Autodesk-MCP test UI".
```
