const logEl = document.getElementById("log");
const samplesEl = document.getElementById("samples");
const statusEl = document.getElementById("status");
const modeBadge = document.getElementById("modeBadge");
const form = document.getElementById("form");
const input = document.getElementById("input");
const sendBtn = document.getElementById("send");

const messages = [];

function addMessage(role, content, actions) {
  const div = document.createElement("div");
  div.className = `msg ${role}`;
  const roleEl = document.createElement("div");
  roleEl.className = "role";
  roleEl.textContent = role;
  const body = document.createElement("div");
  body.textContent = content;
  div.appendChild(roleEl);
  div.appendChild(body);
  if (actions && actions.length) {
    const pre = document.createElement("pre");
    pre.textContent = JSON.stringify(actions, null, 2);
    div.appendChild(pre);
  }
  logEl.appendChild(div);
  logEl.scrollTop = logEl.scrollHeight;
}

async function loadStatus() {
  const res = await fetch("/api/status");
  const data = await res.json();
  statusEl.textContent = [
    `llm_mode: ${data.llm_mode}`,
    `model: ${data.llm_model || "(none)"}`,
    `rag: ${data.rag?.backend} (${data.rag?.documents ?? 0} docs)`,
    `tools: ${(data.tools || []).join(", ")}`,
  ].join("\n");
  modeBadge.textContent = data.llm_mode;
  modeBadge.className = `badge ${data.llm_mode === "live" ? "live" : "demo"}`;
}

async function loadSamples() {
  const res = await fetch("/api/samples");
  const data = await res.json();
  samplesEl.innerHTML = "";
  for (const s of data.samples || []) {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "sample";
    btn.innerHTML = `<strong>${s.id}. ${s.title}</strong><span>${s.prompt}</span>`;
    btn.addEventListener("click", () => {
      input.value = s.prompt;
      input.focus();
    });
    samplesEl.appendChild(btn);
  }
}

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  const text = input.value.trim();
  if (!text) return;
  input.value = "";
  messages.push({ role: "user", content: text });
  addMessage("user", text);
  sendBtn.disabled = true;
  try {
    const res = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ messages }),
    });
    const data = await res.json();
    if (data.error) {
      addMessage("assistant", data.error, data.actions);
    } else {
      const reply = data.reply || "(empty reply)";
      messages.push({ role: "assistant", content: reply });
      addMessage("assistant", reply, data.actions);
    }
    modeBadge.textContent = data.mode || modeBadge.textContent;
    modeBadge.className = `badge ${data.mode === "live" ? "live" : "demo"}`;
  } catch (err) {
    addMessage("assistant", String(err));
  } finally {
    sendBtn.disabled = false;
  }
});

loadStatus();
loadSamples();
