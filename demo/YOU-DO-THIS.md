# Finish install (your clicks — once)

Code and scripts are ready. Windows is waiting on you for:

## 1. Docker UAC

If a **User Account Control** prompt is open for Docker Desktop — click **Yes**.

Installer has been waiting on admin approval.

## 2. Ubuntu (WSL) first login

An **Ubuntu** window may be open asking for a new UNIX username + password.  
Create them (password won’t show while typing). That finishes WSL so Docker can run.

## 3. Start the demo

Double-click:

```text
demo\start-demo.bat
```

If Kubernetes isn’t enabled yet, the script falls back to Compose on **http://127.0.0.1:3188**.

For K8s UI: enable in Docker Desktop → Settings → Kubernetes → Apply & Restart, then re-run the script → **http://localhost:30080**.

## 4. In AnythingLLM (only LLM step)

- Provider: **Ollama**
- URL: `http://host.docker.internal:11434` (Compose) or same if pre-set in K8s
- Model: `qwen2.5:7b` (script pulls it if Ollama is installed)

Create a workspace → upload a PDF → chat.
