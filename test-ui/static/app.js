const logScrollEl = document.getElementById("log");
const logEl = document.getElementById("logMessages");
const chatsEl = document.getElementById("chats");
const modeBadge = document.getElementById("modeBadge");
const trackBadge = document.getElementById("trackBadge");
const kitBadge = document.getElementById("kitBadge");
const baseModellingKitEl = document.getElementById("baseModellingKit");
const modelFooter = document.getElementById("modelFooter");
const modelFooterName = document.getElementById("modelFooterName");
const llmSettingsBtn = document.getElementById("llmSettingsBtn");
const chatTitleEl = document.getElementById("chatTitle");
const form = document.getElementById("form");
const input = document.getElementById("input");
const sendBtn = document.getElementById("send");
const newChatBtn = document.getElementById("newChat");

const TRACK_KEY = "autodesk-mcp-track";
const CHAT_FILTER_KEY = "autodesk-mcp-chat-filter";
const BASE_MODELLING_KIT_KEY = "autodesk-mcp-base-modelling-kit";
const LEGACY_CABINET_KIT_KEY = "autodesk-mcp-cabinet-kit";
const NEAR_BOTTOM_PX = 96;

let track = localStorage.getItem(TRACK_KEY) || "inventor";
let chatFilter = localStorage.getItem(CHAT_FILTER_KEY) || "all";
if (!["all", "inventor", "autocad"].includes(chatFilter)) chatFilter = "all";
let baseModellingKit = (() => {
  const v = localStorage.getItem(BASE_MODELLING_KIT_KEY);
  if (v === "1" || v === "0") return v === "1";
  // Migrate prior toggle name if present
  if (localStorage.getItem(LEGACY_CABINET_KIT_KEY) === "1") return true;
  return false;
})();
let chatId = null;
let messages = [];

/** chatId -> true while a request is in flight (multiple chats can run at once) */
const pendingChats = new Set();
/** Sidebar/meta for in-flight chats (kept even after you switch away) */
const pendingMeta = new Map();
/** Local transcripts so switching away mid-reply doesn't lose the turn */
const chatCache = new Map();
/** Deduplicate concurrent draft→create so two sends can't fight over chatId */
let ensureChatPromise = null;
/** chatId -> AbortController for in-flight /api/chat requests */
const abortControllers = new Map();

const BASE_TITLE = "Autodesk-MCP";
let titleFlashTimer = null;
let notifyPermissionAsked = false;

/** Follow the latest message unless the user scrolls up to read history */
let stickToBottom = true;
let scrollRaf = 0;

function isNearBottom() {
  if (!logScrollEl) return true;
  const gap =
    logScrollEl.scrollHeight - logScrollEl.scrollTop - logScrollEl.clientHeight;
  return gap <= NEAR_BOTTOM_PX;
}

/** Scroll chat to latest content (ChatGPT-style stick-to-bottom). */
function scrollLogToBottom(force = false) {
  if (!logScrollEl) return;
  if (!force && !stickToBottom) return;
  stickToBottom = true;
  if (scrollRaf) cancelAnimationFrame(scrollRaf);
  scrollRaf = requestAnimationFrame(() => {
    scrollRaf = 0;
    logScrollEl.scrollTop = logScrollEl.scrollHeight;
  });
}

if (logScrollEl) {
  logScrollEl.addEventListener(
    "scroll",
    () => {
      stickToBottom = isNearBottom();
    },
    { passive: true }
  );
}

if (logEl && typeof ResizeObserver !== "undefined") {
  const logResizeObserver = new ResizeObserver(() => {
    if (stickToBottom) scrollLogToBottom(true);
  });
  logResizeObserver.observe(logEl);
}

/** Short two-tone ding when a reply finishes. */
function playDoneDing() {
  try {
    const Ctx = window.AudioContext || window.webkitAudioContext;
    if (!Ctx) return;
    const ctx = new Ctx();
    const now = ctx.currentTime;
    const master = ctx.createGain();
    master.gain.value = 0.18;
    master.connect(ctx.destination);

    const tone = (freq, start, dur) => {
      const o = ctx.createOscillator();
      const g = ctx.createGain();
      o.type = "sine";
      o.frequency.value = freq;
      g.gain.setValueAtTime(0.0001, now + start);
      g.gain.exponentialRampToValueAtTime(1, now + start + 0.02);
      g.gain.exponentialRampToValueAtTime(0.0001, now + start + dur);
      o.connect(g);
      g.connect(master);
      o.start(now + start);
      o.stop(now + start + dur + 0.02);
    };
    tone(880, 0, 0.14);
    tone(1175, 0.12, 0.22);
    setTimeout(() => {
      try {
        ctx.close();
      } catch (_err) {
        /* ignore */
      }
    }, 500);
  } catch (_err) {
    /* audio blocked / unavailable */
  }
}

function flashTabTitle(prefix) {
  if (titleFlashTimer) {
    clearInterval(titleFlashTimer);
    titleFlashTimer = null;
  }
  if (!document.hidden) {
    document.title = BASE_TITLE;
    return;
  }
  let on = true;
  document.title = `${prefix} · ${BASE_TITLE}`;
  titleFlashTimer = setInterval(() => {
    if (!document.hidden) {
      clearInterval(titleFlashTimer);
      titleFlashTimer = null;
      document.title = BASE_TITLE;
      return;
    }
    document.title = on ? `${prefix} · ${BASE_TITLE}` : BASE_TITLE;
    on = !on;
  }, 1000);
}

async function ensureNotifyPermission() {
  if (!("Notification" in window)) return false;
  if (Notification.permission === "granted") return true;
  if (Notification.permission === "denied") return false;
  if (notifyPermissionAsked) return false;
  notifyPermissionAsked = true;
  try {
    const perm = await Notification.requestPermission();
    return perm === "granted";
  } catch (_err) {
    return false;
  }
}

/**
 * Ding + OS notification (other tabs/apps) + tab-title flash when unfocused.
 * Not window.alert — uses the browser Notification API.
 */
function notifyReplyReady({ title, body, fromBackground }) {
  playDoneDing();
  const snippet = (body || "Reply ready").replace(/\s+/g, " ").trim().slice(0, 140);
  const heading = title || "Reply ready";

  if (document.hidden || fromBackground) {
    flashTabTitle("● Done");
  }

  if (
    ("Notification" in window) &&
    Notification.permission === "granted" &&
    (document.hidden || fromBackground)
  ) {
    try {
      const n = new Notification(`Autodesk-MCP — ${heading}`, {
        body: snippet,
        icon: "/static/favicon.png",
        badge: "/static/favicon.png",
        tag: "autodesk-mcp-reply",
        renotify: true,
      });
      n.onclick = () => {
        try {
          window.focus();
        } catch (_err) {
          /* ignore */
        }
        n.close();
      };
    } catch (_err) {
      /* Notification construct failed */
    }
  }
}

document.addEventListener("visibilitychange", () => {
  if (!document.hidden) {
    if (titleFlashTimer) {
      clearInterval(titleFlashTimer);
      titleFlashTimer = null;
    }
    document.title = BASE_TITLE;
  }
});

function updateComposerPlaceholder() {
  if (baseModellingKit) {
    input.placeholder =
      track === "inventor"
        ? "Base modelling kit — new part / sketch / extrude…"
        : "Base modelling kit — drawing / solid_box / boolean…";
    return;
  }
  input.placeholder =
    track === "inventor"
      ? "Inventor mode — part / parameters / export…"
      : "AutoCAD mode — drawing / layers / export…";
}

function setBaseModellingKit(on) {
  baseModellingKit = Boolean(on);
  localStorage.setItem(BASE_MODELLING_KIT_KEY, baseModellingKit ? "1" : "0");
  localStorage.removeItem(LEGACY_CABINET_KIT_KEY);
  if (baseModellingKitEl) baseModellingKitEl.checked = baseModellingKit;
  if (kitBadge) {
    kitBadge.hidden = !baseModellingKit;
    kitBadge.textContent = "Base modelling kit";
    kitBadge.className = "badge kit-on";
  }
  updateComposerPlaceholder();
}

function setTrack(next) {
  track = next === "autocad" ? "autocad" : "inventor";
  localStorage.setItem(TRACK_KEY, track);
  document.querySelectorAll(".track-btn").forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.track === track);
  });
  trackBadge.textContent = track === "inventor" ? "Inventor" : "AutoCAD";
  trackBadge.className = `badge track-${track}`;
  updateComposerPlaceholder();
}

function setChatFilter(next) {
  chatFilter =
    next === "inventor" || next === "autocad" || next === "all" ? next : "all";
  localStorage.setItem(CHAT_FILTER_KEY, chatFilter);
  document.querySelectorAll(".filter-btn").forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.filter === chatFilter);
  });
}

function trackLabel(t) {
  if (!t) return "Any";
  return t === "autocad" ? "AutoCAD" : "Inventor";
}

function isDraft() {
  return !chatId;
}

function isCurrentPending() {
  return Boolean(chatId && pendingChats.has(chatId));
}

function updateSendEnabled() {
  sendBtn.disabled = isCurrentPending();
}

function stopCurrentChat() {
  if (!chatId) return;
  const ac = abortControllers.get(chatId);
  if (ac) ac.abort();
}

function clearLog() {
  if (logEl) logEl.innerHTML = "";
  stickToBottom = true;
}

function renderMessages() {
  clearLog();
  for (const m of messages) {
    if (m.role === "user" || m.role === "assistant") {
      addMessage(
        m.role,
        m.content || "",
        m.actions,
        m.pending_switch,
        m.elapsed_ms,
        m.pending_launch
      );
    }
  }
  if (isCurrentPending()) showThinking();
  scrollLogToBottom(true);
}

function escapeHtml(s) {
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

/** Lightweight markdown fallback: **bold**, line breaks. Escapes HTML first. */
function formatMessageHtml(text) {
  return escapeHtml(text || "")
    .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
    .replace(/\n/g, "<br>");
}

let markdownReady = false;

function ensureMarkdownConfigured() {
  if (markdownReady || typeof marked === "undefined") return;
  try {
    if (typeof marked.use === "function") {
      marked.use({ gfm: true, breaks: true });
    } else if (typeof marked.setOptions === "function") {
      marked.setOptions({ gfm: true, breaks: true });
    }
  } catch (_err) {
    /* keep defaults */
  }
  markdownReady = true;
}

/** Full GFM markdown for assistant replies (marked + DOMPurify when available). */
function renderAssistantMarkdown(text) {
  const raw = text || "";
  if (typeof marked === "undefined" || typeof DOMPurify === "undefined") {
    return formatMessageHtml(raw);
  }
  try {
    ensureMarkdownConfigured();
    const html =
      typeof marked.parse === "function" ? marked.parse(raw) : marked(raw);
    return DOMPurify.sanitize(String(html), {
      USE_PROFILES: { html: true },
      ADD_ATTR: ["target", "rel"],
    });
  } catch (_err) {
    return formatMessageHtml(raw);
  }
}

function formatDuration(ms) {
  const sec = Math.max(0, (Number(ms) || 0) / 1000);
  if (sec < 10) return `${sec.toFixed(1)}s`;
  return `${Math.round(sec)}s`;
}

function pendingFromActions(actions, activeTrack) {
  const list = actions || [];
  const mode = activeTrack || track;
  for (let i = list.length - 1; i >= 0; i -= 1) {
    const a = list[i];
    const result = a && a.result;
    if (
      a &&
      a.tool === "request_track_switch" &&
      result &&
      result.needs_confirmation &&
      result.to_track
    ) {
      return {
        from_track: mode,
        to_track: result.to_track,
        reason: result.reason || "",
        prompt: result.prompt || `Switch to ${result.to_track}?`,
      };
    }
  }
  return null;
}

function pendingLaunchFromActions(actions) {
  const list = actions || [];
  for (let i = list.length - 1; i >= 0; i -= 1) {
    const a = list[i];
    const result = a && a.result;
    if (!(result && result.needs_confirmation && result.app)) continue;
    if (result.action === "force_restart") {
      return {
        app: result.app,
        action: "force_restart",
        reason: result.reason || "",
        prompt: result.prompt || `Quit and restart ${result.app}?`,
        drawing_path: result.drawing_path || null,
        status: result.status || {},
      };
    }
    if (
      a.tool === "request_launch_cad" ||
      a.tool === "recover_autocad" ||
      a.tool === "recover_inventor" ||
      result.ui === "confirm_cancel"
    ) {
      return {
        app: result.app,
        reason: result.reason || "",
        prompt: result.prompt || `Launch ${result.app}?`,
        status: result.status || {},
        drawing_path: result.drawing_path || null,
      };
    }
  }
  return null;
}

function resolvePendingLaunch(messageOrPending, actions) {
  if (messageOrPending && messageOrPending.app) return messageOrPending;
  return pendingLaunchFromActions(actions);
}

/** Recover Confirm/Cancel for older chats that only saved reply text. */
function pendingFromContent(content, activeTrack) {
  const text = content || "";
  const mode = activeTrack || track;
  if (!/confirm or cancel/i.test(text) && !/switch to \*\*/i.test(text)) {
    return null;
  }
  const lower = text.toLowerCase();
  let toTrack = null;
  if (/switch to \*\*autocad\*\*|switch to autocad/i.test(text)) {
    toTrack = "autocad";
  } else if (/switch to \*\*inventor\*\*|switch to inventor/i.test(text)) {
    toTrack = "inventor";
  } else if (lower.includes("autocad") && mode === "inventor") {
    toTrack = "autocad";
  } else if (lower.includes("inventor") && mode === "autocad") {
    toTrack = "inventor";
  }
  if (!toTrack || toTrack === mode) return null;
  return {
    from_track: mode,
    to_track: toTrack,
    reason: "Recovered switch request",
    prompt: `Switch to ${toTrack === "autocad" ? "AutoCAD" : "Inventor"} mode?`,
  };
}

function resolvePending(messageOrPending, actions, content, activeTrack) {
  if (messageOrPending && messageOrPending.to_track) return messageOrPending;
  return (
    pendingFromActions(actions, activeTrack) ||
    pendingFromContent(content, activeTrack)
  );
}

function buildWorkedDetails(actions, elapsedMs) {
  const details = document.createElement("details");
  details.className = "worked";
  const summary = document.createElement("summary");
  const n = (actions || []).length;
  const label =
    n === 0
      ? `Worked for ${formatDuration(elapsedMs)}`
      : n === 1
        ? `Worked for ${formatDuration(elapsedMs)} · 1 tool`
        : `Worked for ${formatDuration(elapsedMs)} · ${n} tools`;
  const labelEl = document.createElement("span");
  labelEl.className = "worked-label";
  labelEl.textContent = label;
  const chevron = document.createElement("span");
  chevron.className = "worked-chevron";
  chevron.setAttribute("aria-hidden", "true");
  chevron.textContent = "▾";
  summary.appendChild(labelEl);
  summary.appendChild(chevron);
  details.appendChild(summary);

  const body = document.createElement("div");
  body.className = "worked-body";
  if (!n) {
    const empty = document.createElement("div");
    empty.className = "worked-empty";
    empty.textContent = "No tools were called for this reply.";
    body.appendChild(empty);
  }
  for (const action of actions || []) {
    const row = document.createElement("div");
    row.className = "worked-step";
    const name = document.createElement("div");
    name.className = "worked-tool";
    name.textContent = action.tool || "tool";
    row.appendChild(name);
    if (action.arguments) {
      const args = document.createElement("pre");
      args.className = "worked-args";
      let raw = action.arguments;
      try {
        raw =
          typeof raw === "string"
            ? JSON.stringify(JSON.parse(raw), null, 2)
            : JSON.stringify(raw, null, 2);
      } catch (_err) {
        /* keep raw */
      }
      args.textContent = raw;
      row.appendChild(args);
    }
    if (action.result !== undefined) {
      const res = document.createElement("pre");
      res.className = "worked-result";
      res.textContent = JSON.stringify(action.result, null, 2);
      row.appendChild(res);
    }
    body.appendChild(row);
  }
  details.appendChild(body);
  return details;
}

function addMessage(role, content, actions, pendingSwitch, elapsedMs, pendingLaunch) {
  const div = document.createElement("div");
  div.className = `msg ${role}`;
  const roleEl = document.createElement("div");
  roleEl.className = "role";
  roleEl.textContent = role;
  div.appendChild(roleEl);

  const actionList = actions || [];
  if (role === "assistant" && (actionList.length || elapsedMs > 0)) {
    div.appendChild(buildWorkedDetails(actionList, elapsedMs || 0));
  }

  const body = document.createElement("div");
  if (role === "assistant") {
    body.className = "msg-body md";
    body.innerHTML = renderAssistantMarkdown(content);
    body.querySelectorAll("a[href]").forEach((a) => {
      a.target = "_blank";
      a.rel = "noopener noreferrer";
    });
  } else {
    body.className = "msg-body";
    body.textContent = content || "";
  }
  div.appendChild(body);

  const pending = resolvePending(pendingSwitch, actionList, content, track);
  if (pending && pending.to_track) {
    div.appendChild(buildSwitchCard(pending));
  }

  const launch = resolvePendingLaunch(pendingLaunch, actionList);
  if (launch && launch.app) {
    div.appendChild(buildLaunchCard(launch));
  }

  logEl.appendChild(div);
  scrollLogToBottom(true);
  return div;
}

function setCardResolved(card, actionsEl, statusText) {
  card.classList.add("resolved");
  actionsEl.innerHTML = "";
  const status = document.createElement("span");
  status.className = "switch-status";
  status.textContent = statusText;
  actionsEl.appendChild(status);
}

function markMessageResolution(kind, resolution, statusText) {
  // Keep the confirm line in the transcript; just stamp Confirmed/Cancelled.
  for (let i = messages.length - 1; i >= 0; i -= 1) {
    const m = messages[i];
    if (m.role !== "assistant") continue;
    if (kind === "switch" && m.pending_switch && !m.pending_switch.resolution) {
      m.pending_switch = {
        ...m.pending_switch,
        resolution,
        resolution_text: statusText,
      };
      return m;
    }
    if (kind === "launch" && m.pending_launch && !m.pending_launch.resolution) {
      m.pending_launch = {
        ...m.pending_launch,
        resolution,
        resolution_text: statusText,
      };
      return m;
    }
  }
  return null;
}

function buildSwitchCard(pending) {
  const card = document.createElement("div");
  card.className = "switch-card";
  const toLabel = pending.to_track === "autocad" ? "AutoCAD" : "Inventor";
  const fromLabel = pending.from_track === "autocad" ? "AutoCAD" : "Inventor";
  const text = document.createElement("p");
  text.className = "switch-prompt";
  text.innerHTML = formatMessageHtml(`Switch to **${toLabel}** mode?`);
  const actions = document.createElement("div");
  actions.className = "switch-actions";
  card.appendChild(text);
  card.appendChild(actions);

  if (pending.resolution === "confirmed" || pending.resolution === "cancelled") {
    setCardResolved(
      card,
      actions,
      pending.resolution_text ||
        (pending.resolution === "confirmed" ? "Confirmed…" : "Cancelled…")
    );
    return card;
  }

  const confirmBtn = document.createElement("button");
  confirmBtn.type = "button";
  confirmBtn.className = "switch-confirm";
  confirmBtn.textContent = "Confirm";
  const cancelBtn = document.createElement("button");
  cancelBtn.type = "button";
  cancelBtn.className = "switch-cancel";
  cancelBtn.textContent = "Cancel";

  confirmBtn.addEventListener("click", async () => {
    confirmBtn.disabled = true;
    cancelBtn.disabled = true;
    const statusText = "Confirmed…";
    setCardResolved(card, actions, statusText);
    markMessageResolution("switch", "confirmed", statusText);
    const next = pending.to_track === "autocad" ? "autocad" : "inventor";
    setTrack(next);
    const id = chatId;
    const title = chatTitleEl.textContent;
    const snapshot = messages.map((m) => ({ ...m }));
    if (id) {
      await saveChatMessages(id, snapshot, next, title);
    }
    await loadStatus();
    await loadChatList();
    // Re-run the user request in the new track; keep the confirm line on screen.
    await continueChat({
      chatId: id,
      track: next,
      messages: snapshot,
      title,
    });
  });

  cancelBtn.addEventListener("click", async () => {
    const statusText = "Cancelled…";
    setCardResolved(card, actions, statusText);
    markMessageResolution("switch", "cancelled", statusText);
    if (chatId) {
      await saveChatMessages(chatId, messages, track, chatTitleEl.textContent);
    }
  });

  actions.appendChild(confirmBtn);
  actions.appendChild(cancelBtn);
  return card;
}

function buildLaunchCard(pending) {
  const card = document.createElement("div");
  card.className = "switch-card launch-card";
  const label = pending.app === "autocad" ? "AutoCAD" : "Inventor";
  const isKill = pending.action === "force_restart";
  const already = pending.status && pending.status.running;
  const reason = (pending.reason || "").trim();
  const text = document.createElement("p");
  text.className = "switch-prompt";
  if (isKill) {
    text.innerHTML = formatMessageHtml(
      `Quit and restart **${label}**?\n\n` +
        (reason ? `**Reason:** ${reason}\n\n` : "") +
        `This closes the ${label} process — unsaved work may be lost.`
    );
  } else {
    text.innerHTML = formatMessageHtml(
      already
        ? `**${label}** looks already running. Continue?`
        : `Launch **${label}**?`
    );
  }
  const actions = document.createElement("div");
  actions.className = "switch-actions";
  card.appendChild(text);
  card.appendChild(actions);

  if (pending.resolution === "confirmed" || pending.resolution === "cancelled") {
    setCardResolved(
      card,
      actions,
      pending.resolution_text ||
        (pending.resolution === "confirmed" ? "Confirmed…" : "Cancelled…")
    );
    return card;
  }

  const confirmBtn = document.createElement("button");
  confirmBtn.type = "button";
  confirmBtn.className = "switch-confirm";
  confirmBtn.textContent = isKill
    ? "Quit & restart"
    : already
      ? "Continue"
      : "Confirm";
  const cancelBtn = document.createElement("button");
  cancelBtn.type = "button";
  cancelBtn.className = "switch-cancel";
  cancelBtn.textContent = "Cancel";

  confirmBtn.addEventListener("click", async () => {
    confirmBtn.disabled = true;
    cancelBtn.disabled = true;
    if (isKill && !reason) {
      const errText = `A reason is required before quitting ${label}.`;
      setCardResolved(card, actions, errText);
      markMessageResolution("launch", "cancelled", errText);
      return;
    }
    text.textContent = isKill
      ? `Quitting and restarting ${label}…`
      : already
        ? `Checking ${label}…`
        : `Starting ${label}…`;
    try {
      const res = await fetch(
        isKill ? "/api/cad/force-restart" : "/api/cad/launch",
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(
            isKill
              ? {
                  app: pending.app,
                  wait_s: 90,
                  drawing_path: pending.drawing_path || null,
                  reason,
                }
              : {
                  app: pending.app,
                  wait_s: 90,
                  drawing_path: pending.drawing_path || null,
                }
          ),
        }
      );
      const data = await res.json();
      if (!data.ok) {
        const errText =
          data.error ||
          data.detail ||
          (isKill
            ? `Could not restart ${label}.`
            : `Could not launch ${label}.`);
        setCardResolved(card, actions, errText);
        markMessageResolution("launch", "cancelled", errText);
        if (chatId) {
          await saveChatMessages(
            chatId,
            messages,
            track,
            chatTitleEl.textContent
          );
        }
        return;
      }
      const statusText = "Confirmed…";
      // Restore the prompt line; status sits where the buttons were.
      if (isKill) {
        text.innerHTML = formatMessageHtml(
          `Quit and restart **${label}**?\n\n` +
            (reason ? `**Reason:** ${reason}\n\n` : "") +
            "This closes the AutoCAD process — unsaved work may be lost."
        );
      } else {
        text.innerHTML = formatMessageHtml(
          already
            ? `**${label}** looks already running. Continue?`
            : `Launch **${label}**?`
        );
      }
      setCardResolved(card, actions, statusText);
      markMessageResolution("launch", "confirmed", statusText);
      const id = chatId;
      const title = chatTitleEl.textContent;
      const snapshot = messages.map((m) => ({ ...m }));
      if (id) {
        await saveChatMessages(id, snapshot, track, title);
      }
      await loadStatus();
      // Brief settle so COM can come up after the process appears
      await new Promise((r) => setTimeout(r, isKill ? 6000 : 4000));
      // Keep the confirm line; continue with the same transcript (resolved).
      await continueChat({
        chatId: id,
        track,
        messages: snapshot,
        title,
      });
    } catch (err) {
      const errText = isKill
        ? `Restart failed: ${err}`
        : `Launch failed: ${err}`;
      setCardResolved(card, actions, errText);
      markMessageResolution("launch", "cancelled", errText);
    }
  });

  cancelBtn.addEventListener("click", async () => {
    const statusText = "Cancelled…";
    setCardResolved(card, actions, statusText);
    markMessageResolution("launch", "cancelled", statusText);
    if (chatId) {
      await saveChatMessages(chatId, messages, track, chatTitleEl.textContent);
    }
  });

  actions.appendChild(confirmBtn);
  actions.appendChild(cancelBtn);
  return card;
}

function showThinking() {
  hideThinking();
  const div = document.createElement("div");
  div.className = "msg assistant thinking";
  div.id = "thinkingBubble";

  const roleEl = document.createElement("div");
  roleEl.className = "role";
  roleEl.textContent = "assistant";
  div.appendChild(roleEl);

  const row = document.createElement("div");
  row.className = "thinking-row";

  const status = document.createElement("div");
  status.className = "thinking-status";
  status.id = "thinkingStatus";

  const dots = document.createElement("div");
  dots.className = "thinking-dots";
  dots.setAttribute("aria-hidden", "true");
  dots.innerHTML = "<span></span><span></span><span></span>";
  status.appendChild(dots);

  const statusLabel = document.createElement("span");
  statusLabel.className = "thinking-status-label";
  statusLabel.id = "thinkingStatusLabel";
  statusLabel.textContent = "Working…";
  status.appendChild(statusLabel);
  row.appendChild(status);

  const stop = document.createElement("button");
  stop.type = "button";
  stop.className = "thinking-stop";
  stop.id = "thinkingStop";
  stop.title = "Stop";
  stop.setAttribute("aria-label", "Stop generating");
  stop.innerHTML = '<span class="thinking-stop-icon" aria-hidden="true"></span>';
  stop.addEventListener("click", () => stopCurrentChat());
  row.appendChild(stop);

  div.appendChild(row);

  // Tools panel is created only once tools are actually used (see updateThinkingTools).
  logEl.appendChild(div);
  scrollLogToBottom(true);
}

function hideThinking() {
  const el = document.getElementById("thinkingBubble");
  if (el) el.remove();
}

function ensureThinkingToolsPanel() {
  const bubble = document.getElementById("thinkingBubble");
  if (!bubble) return null;
  let details = document.getElementById("thinkingTools");
  if (details) return details;

  details = document.createElement("details");
  details.className = "worked thinking-tools";
  details.open = false;
  details.id = "thinkingTools";
  const summary = document.createElement("summary");
  const labelEl = document.createElement("span");
  labelEl.className = "worked-label";
  labelEl.id = "thinkingToolsLabel";
  labelEl.textContent = "Tools";
  const chevron = document.createElement("span");
  chevron.className = "worked-chevron";
  chevron.setAttribute("aria-hidden", "true");
  chevron.textContent = "▾";
  summary.appendChild(labelEl);
  summary.appendChild(chevron);
  details.appendChild(summary);
  const body = document.createElement("div");
  body.className = "worked-body";
  body.id = "thinkingToolsBody";
  details.appendChild(body);
  bubble.appendChild(details);
  return details;
}

function updateThinkingTools(actions) {
  const list = actions || [];
  const n = list.length;
  const statusLabel = document.getElementById("thinkingStatusLabel");
  if (statusLabel) statusLabel.textContent = "Working…";
  if (!n) {
    const details = document.getElementById("thinkingTools");
    if (details) details.remove();
    if (statusLabel) statusLabel.hidden = false;
    return;
  }

  ensureThinkingToolsPanel();
  // Keep "Working…" next to Stop; tools panel shows the tool count.
  if (statusLabel) statusLabel.hidden = false;
  const body = document.getElementById("thinkingToolsBody");
  const label = document.getElementById("thinkingToolsLabel");
  if (!body || !label) return;
  label.textContent = n === 1 ? "1 tool" : `${n} tools`;
  body.innerHTML = "";
  for (const action of list) {
    const row = document.createElement("div");
    row.className = "worked-step";
    if (action.pending) row.classList.add("worked-pending");
    const name = document.createElement("div");
    name.className = "worked-tool";
    name.textContent = action.tool || "tool";
    if (action.pending) name.textContent += " …";
    row.appendChild(name);
    if (action.arguments && Object.keys(action.arguments).length) {
      const args = document.createElement("pre");
      args.className = "worked-args";
      try {
        args.textContent = JSON.stringify(action.arguments, null, 2);
      } catch (_err) {
        args.textContent = String(action.arguments);
      }
      row.appendChild(args);
    }
    if (!action.pending && action.result !== undefined) {
      const res = document.createElement("pre");
      res.className = "worked-result";
      const ok =
        action.result &&
        typeof action.result === "object" &&
        action.result.ok !== false &&
        !action.result.error;
      res.classList.add(ok ? "worked-ok" : "worked-fail");
      try {
        res.textContent = JSON.stringify(action.result, null, 2);
      } catch (_err) {
        res.textContent = String(action.result);
      }
      row.appendChild(res);
    }
    body.appendChild(row);
  }
  scrollLogToBottom();
}

async function readChatSse(res, onEvent) {
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buf = "";
  let finalEvent = null;
  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buf += decoder.decode(value, { stream: true });
    const parts = buf.split("\n\n");
    buf = parts.pop() || "";
    for (const part of parts) {
      const lines = part.split("\n");
      let data = "";
      for (const line of lines) {
        if (line.startsWith("data: ")) data += line.slice(6);
        else if (line.startsWith("data:")) data += line.slice(5);
      }
      if (!data.trim()) continue;
      let event;
      try {
        event = JSON.parse(data);
      } catch (_err) {
        continue;
      }
      if (typeof onEvent === "function") onEvent(event);
      if (event.type === "final") finalEvent = event;
    }
  }
  return finalEvent;
}

async function saveChatMessages(id, msgs, chatTrack, title) {
  const res = await fetch(`/api/chats/${id}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      messages: msgs.map((m) => ({
        role: m.role,
        content: m.content || "",
        actions: m.actions,
        pending_switch: m.pending_switch,
        pending_launch: m.pending_launch,
        elapsed_ms: m.elapsed_ms,
      })),
      track: chatTrack,
      title: title || undefined,
    }),
  });
  return res.ok;
}

function hostHint(baseUrl) {
  try {
    const u = new URL(baseUrl || "", window.location.origin);
    if (u.hostname === "127.0.0.1" || u.hostname === "localhost") return "local";
    return u.hostname;
  } catch (_err) {
    return "";
  }
}

async function loadStatus() {
  const res = await fetch("/api/status");
  const data = await res.json();
  modeBadge.textContent = data.llm_mode;
  modeBadge.className = `badge ${data.llm_mode === "live" ? "live" : "demo"}`;
  const model = (data.llm_model || "").trim() || "unknown";
  const provider = (data.llm_provider || "").trim();
  const host = hostHint(data.llm_base_url);
  if (modelFooterName) {
    modelFooterName.textContent = provider ? `${provider} · ${model}` : model;
  }
  const fullN =
    track === "inventor"
      ? data.tools_inventor_count
      : data.tools_autocad_count;
  const kitN =
    track === "inventor"
      ? data.tools_inventor_base_modelling_kit_count
      : data.tools_autocad_base_modelling_kit_count;
  const toolHint =
    typeof fullN === "number" && typeof kitN === "number"
      ? baseModellingKit
        ? ` · base modelling kit ${kitN}/${fullN} tools`
        : ` · ${fullN} tools (kit ${kitN})`
      : "";
  const keyHint = data.llm_api_key_set
    ? ` · key ${data.llm_api_key_hint || "set"}`
    : " · no API key";
  const tip = host
    ? `${model} · ${host} · ${data.llm_base_url || ""}${keyHint}${toolHint}`
    : `${model} · ${data.llm_base_url || ""}${keyHint}${toolHint}`;
  if (modelFooter) modelFooter.title = tip;
  if (llmSettingsBtn) {
    llmSettingsBtn.title = `LLM settings — ${tip}`;
  }
}

const llmSettingsModal = document.getElementById("llmSettingsModal");
const llmSettingsForm = document.getElementById("llmSettingsForm");
const llmProviderEl = document.getElementById("llmProvider");
const llmModelSelectEl = document.getElementById("llmModelSelect");
const llmModelCustomEl = document.getElementById("llmModelCustom");
const llmModelCustomWrap = document.getElementById("llmModelCustomWrap");
const llmBaseUrlEl = document.getElementById("llmBaseUrl");
const llmApiKeyEl = document.getElementById("llmApiKey");
const llmClearKeyEl = document.getElementById("llmClearKey");
const llmHelpEl = document.getElementById("llmHelp");
const llmKeyHintEl = document.getElementById("llmKeyHint");
const llmSaveStatusEl = document.getElementById("llmSaveStatus");

const LLM_OTHER = "__other__";
let llmPresets = null;

function selectedModelValue() {
  if (!llmModelSelectEl) return "";
  if (llmModelSelectEl.value === LLM_OTHER) {
    return (llmModelCustomEl && llmModelCustomEl.value.trim()) || "";
  }
  return (llmModelSelectEl.value || "").trim();
}

function syncCustomModelVisibility() {
  const other = llmModelSelectEl && llmModelSelectEl.value === LLM_OTHER;
  if (llmModelCustomWrap) llmModelCustomWrap.hidden = !other;
}

function fillModelSelect(provider, currentModel) {
  if (!llmModelSelectEl) return;
  const p = (llmPresets && llmPresets[provider]) || {};
  const models = Array.isArray(p.models) ? [...p.models] : [];
  const preferred = currentModel || p.model || "";
  llmModelSelectEl.innerHTML = "";
  for (const id of models) {
    const opt = document.createElement("option");
    opt.value = id;
    opt.textContent = id;
    llmModelSelectEl.appendChild(opt);
  }
  const other = document.createElement("option");
  other.value = LLM_OTHER;
  other.textContent = "Other…";
  llmModelSelectEl.appendChild(other);

  if (preferred && models.includes(preferred)) {
    llmModelSelectEl.value = preferred;
    if (llmModelCustomEl) llmModelCustomEl.value = "";
  } else if (preferred) {
    llmModelSelectEl.value = LLM_OTHER;
    if (llmModelCustomEl) llmModelCustomEl.value = preferred;
  } else if (models.length) {
    llmModelSelectEl.value = models[0];
    if (llmModelCustomEl) llmModelCustomEl.value = "";
  } else {
    llmModelSelectEl.value = LLM_OTHER;
  }
  syncCustomModelVisibility();
}

function applyPresetToForm(name) {
  if (!llmPresets || !llmPresets[name]) return;
  const p = llmPresets[name];
  fillModelSelect(name, p.model || "");
  if (llmBaseUrlEl && !llmBaseUrlEl.dataset.dirty) {
    llmBaseUrlEl.value = p.base_url || "";
  }
  updateLlmHelp(name);
}

function updateLlmHelp(provider) {
  if (!llmHelpEl) return;
  const p = (llmPresets && llmPresets[provider]) || {};
  if (provider === "claude") {
    const keys = p.keys_url || "https://platform.claude.com/settings/keys";
    const help = p.help_url || "https://platform.claude.com/docs/en/get-api-key";
    llmHelpEl.innerHTML =
      `Get a key from <a href="${keys}" target="_blank" rel="noopener">Claude Console</a> ` +
      `(<a href="${help}" target="_blank" rel="noopener">how-to</a>). ` +
      `Claude.ai chat alone is not enough — billing/credits usually required.`;
  } else if (provider === "openai") {
    llmHelpEl.innerHTML =
      `Get a key from <a href="https://platform.openai.com/api-keys" target="_blank" rel="noopener">OpenAI API keys</a>.`;
  } else if (provider === "ollama") {
    llmHelpEl.textContent =
      "Local Ollama — no API key needed. Base URL is usually http://127.0.0.1:11434/v1.";
  } else {
    llmHelpEl.textContent =
      "Any OpenAI-compatible /v1 endpoint (LiteLLM, OpenRouter, etc.).";
  }
}

function closeLlmSettings() {
  if (llmSettingsModal) llmSettingsModal.hidden = true;
}

async function openLlmSettings() {
  if (!llmSettingsModal) return;
  llmSaveStatusEl.textContent = "";
  if (llmApiKeyEl) llmApiKeyEl.value = "";
  if (llmClearKeyEl) llmClearKeyEl.checked = false;
  if (llmBaseUrlEl) delete llmBaseUrlEl.dataset.dirty;
  try {
    const res = await fetch("/api/settings/llm");
    const data = await res.json();
    llmPresets = data.presets || {};
    const provider = data.provider || "ollama";
    if (llmProviderEl) llmProviderEl.value = provider;
    if (llmBaseUrlEl) llmBaseUrlEl.value = data.base_url || "";
    fillModelSelect(provider, data.model || "");
    if (llmKeyHintEl) {
      llmKeyHintEl.textContent = data.api_key_set
        ? `Saved key: ${data.api_key_hint || "set"} (leave blank to keep it)`
        : "No API key saved yet.";
    }
    updateLlmHelp(provider);
  } catch (err) {
    if (llmSaveStatusEl) llmSaveStatusEl.textContent = `Could not load: ${err}`;
  }
  llmSettingsModal.hidden = false;
  if (llmApiKeyEl) llmApiKeyEl.focus();
}

if (llmSettingsBtn) {
  llmSettingsBtn.addEventListener("click", () => {
    openLlmSettings();
  });
}

if (llmSettingsModal) {
  llmSettingsModal.querySelectorAll("[data-close-llm-settings]").forEach((el) => {
    el.addEventListener("click", closeLlmSettings);
  });
}

if (llmProviderEl) {
  llmProviderEl.addEventListener("change", () => {
    if (llmBaseUrlEl) delete llmBaseUrlEl.dataset.dirty;
    applyPresetToForm(llmProviderEl.value);
  });
}
if (llmModelSelectEl) {
  llmModelSelectEl.addEventListener("change", () => {
    syncCustomModelVisibility();
    if (llmModelSelectEl.value === LLM_OTHER && llmModelCustomEl) {
      llmModelCustomEl.focus();
    }
  });
}
if (llmBaseUrlEl) {
  llmBaseUrlEl.addEventListener("input", () => {
    llmBaseUrlEl.dataset.dirty = "1";
  });
}

if (llmSettingsForm) {
  llmSettingsForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    if (llmSaveStatusEl) llmSaveStatusEl.textContent = "Saving…";
    const model = selectedModelValue();
    if (!model) {
      if (llmSaveStatusEl) {
        llmSaveStatusEl.textContent = "Pick a model (or enter a custom id).";
      }
      return;
    }
    const body = {
      provider: llmProviderEl ? llmProviderEl.value : "custom",
      model,
      base_url: llmBaseUrlEl ? llmBaseUrlEl.value.trim() : "",
      mode: "live",
    };
    if (llmClearKeyEl && llmClearKeyEl.checked) {
      body.clear_api_key = true;
      body.api_key = "";
    } else if (llmApiKeyEl && llmApiKeyEl.value.trim()) {
      body.api_key = llmApiKeyEl.value.trim();
    }
    try {
      const res = await fetch("/api/settings/llm", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(data.detail || data.error || `HTTP ${res.status}`);
      }
      if (llmSaveStatusEl) llmSaveStatusEl.textContent = "Saved — ready to chat.";
      if (llmApiKeyEl) llmApiKeyEl.value = "";
      if (llmClearKeyEl) llmClearKeyEl.checked = false;
      if (llmKeyHintEl) {
        llmKeyHintEl.textContent = data.api_key_set
          ? `Saved key: ${data.api_key_hint || "set"}`
          : "No API key saved.";
      }
      await loadStatus();
      setTimeout(closeLlmSettings, 600);
    } catch (err) {
      if (llmSaveStatusEl) llmSaveStatusEl.textContent = String(err.message || err);
    }
  });
}

document.addEventListener("keydown", (e) => {
  if (e.key === "Escape" && llmSettingsModal && !llmSettingsModal.hidden) {
    closeLlmSettings();
  }
});

async function deleteChat(deletedId) {
  if (pendingChats.has(deletedId)) {
    alert("This chat is still waiting for a reply — switch back to it or wait.");
    return;
  }
  if (!confirm("Delete this chat?")) return;
  const wasCurrent = chatId === deletedId;
  const delRes = await fetch(`/api/chats/${deletedId}`, { method: "DELETE" });
  if (!delRes.ok) {
    alert("Could not delete that chat.");
    return;
  }
  pendingChats.delete(deletedId);
  pendingMeta.delete(deletedId);
  chatCache.delete(deletedId);
  if (wasCurrent) {
    chatId = null;
    messages = [];
    clearLog();
    chatTitleEl.textContent = "New chat";
    await startNewChat(false);
  }
  await loadChatList();
  updateSendEnabled();
}

function renderChatCard(c, { draft = false } = {}) {
  const modeless = draft || c.modeless || !c.track;
  const cTrack = modeless
    ? null
    : c.track === "autocad"
      ? "autocad"
      : "inventor";
  const waiting = !draft && c.id && pendingChats.has(c.id);
  const active = draft ? isDraft() : c.id === chatId;

  const row = document.createElement("div");
  row.className =
    "chat-item" + (active ? " active" : "") + (waiting ? " pending" : "");

  const btn = document.createElement("button");
  btn.type = "button";
  btn.className = "chat-btn";

  const top = document.createElement("div");
  top.className = "chat-btn-top";
  const title = document.createElement("strong");
  title.textContent = c.title || "New chat";
  top.appendChild(title);

  const meta = document.createElement("span");
  meta.className = "chat-meta";
  const tagClass = modeless ? "track-any" : `track-${cTrack}`;
  const tagText = modeless ? "Any" : trackLabel(cTrack);
  meta.innerHTML =
    `<span class="badge ${tagClass}">${tagText}</span>` +
    `<span class="chat-count">${draft ? "draft" : `${c.message_count} msgs`}</span>`;

  btn.appendChild(top);
  btn.appendChild(meta);

  if (!draft) {
    const del = document.createElement("span");
    del.className = "chat-del";
    del.title = "Delete chat";
    del.setAttribute("role", "button");
    del.tabIndex = 0;
    del.setAttribute("aria-label", "Delete chat");
    del.textContent = "×";
    del.addEventListener("click", (e) => {
      e.stopPropagation();
      e.preventDefault();
      deleteChat(c.id);
    });
    del.addEventListener("keydown", (e) => {
      if (e.key === "Enter" || e.key === " ") {
        e.stopPropagation();
        e.preventDefault();
        deleteChat(c.id);
      }
    });
    btn.appendChild(del);
    btn.addEventListener("click", (e) => {
      if (e.target.closest(".chat-del")) return;
      openChat(c.id);
    });
  } else {
    btn.addEventListener("click", () => startNewChat());
  }

  if (waiting) {
    const loading = document.createElement("div");
    loading.className = "chat-loading";
    loading.innerHTML =
      '<span class="chat-loading-dots" aria-hidden="true"><span></span><span></span><span></span></span>' +
      "<span>Waiting for reply…</span>";
    btn.appendChild(loading);
  }

  row.appendChild(btn);
  chatsEl.appendChild(row);
}

async function loadChatList() {
  const res = await fetch("/api/chats");
  const data = await res.json();
  chatsEl.innerHTML = "";
  let chats = data.chats || [];
  if (chatFilter === "inventor" || chatFilter === "autocad") {
    chats = chats.filter((c) => c.track === chatFilter);
  }

  // Draft New chat only while you're on it (first load / after pressing New)
  if (isDraft()) {
    renderChatCard(
      { id: null, title: "New chat", track: null, message_count: 0 },
      { draft: true }
    );
  }

  // Always keep in-flight chats visible, even after switching away
  const listedIds = new Set(chats.map((c) => c.id));
  for (const id of pendingChats) {
    if (listedIds.has(id)) continue;
    const meta = pendingMeta.get(id) || {
      title: "Chat",
      track,
      message_count: 1,
    };
    chats = [
      {
        id,
        title: meta.title || "Chat",
        track: meta.track || track,
        message_count: meta.message_count || 1,
      },
      ...chats,
    ];
    listedIds.add(id);
  }

  if (!chats.length && !isDraft()) {
    const empty = document.createElement("p");
    empty.className = "meta";
    empty.textContent =
      chatFilter === "all"
        ? "No chats yet. Press New to start."
        : `No ${trackLabel(chatFilter)} chats yet.`;
    chatsEl.appendChild(empty);
    return;
  }

  for (const c of chats) {
    renderChatCard(c);
  }
}

/** Enter client-only draft New chat (not persisted until first send). */
async function startNewChat(refreshList = true) {
  if (isDraft() && messages.length === 0) {
    chatTitleEl.textContent = "New chat";
    clearLog();
    hideThinking();
    if (refreshList) await loadChatList();
    updateSendEnabled();
    return;
  }
  chatId = null;
  messages = [];
  chatTitleEl.textContent = "New chat";
  clearLog();
  hideThinking();
  if (refreshList) await loadChatList();
  updateSendEnabled();
}

function mapStoredMessages(list) {
  return (list || [])
    .filter((m) => m.role === "user" || m.role === "assistant")
    .map((m) => ({
      role: m.role,
      content: m.content || "",
      actions: m.actions || undefined,
      pending_switch: resolvePending(
        m.pending_switch,
        m.actions,
        m.content || "",
        track
      ),
      pending_launch: resolvePendingLaunch(m.pending_launch, m.actions),
      elapsed_ms: m.elapsed_ms || 0,
    }));
}

async function openChat(id) {
  if (id === chatId) return;

  // Prefer local cache for in-flight chats (server may not have the assistant yet)
  if (pendingChats.has(id) && chatCache.has(id)) {
    const cached = chatCache.get(id);
    chatId = id;
    messages = cached.messages.map((m) => ({ ...m }));
    if (cached.track) setTrack(cached.track);
    chatTitleEl.textContent = cached.title || "Chat";
    renderMessages();
    await loadStatus();
    await loadChatList();
    updateSendEnabled();
    input.focus();
    return;
  }

  const res = await fetch(`/api/chats/${id}`);
  if (!res.ok) return;
  const data = await res.json();
  chatId = data.id;
  messages = mapStoredMessages(data.messages);
  if (chatCache.has(id)) {
    // Merge any newer local user turn if server is briefly behind
    const cached = chatCache.get(id);
    if ((cached.messages || []).length > messages.length) {
      messages = cached.messages.map((m) => ({ ...m }));
    }
  }
  const modeless = data.modeless || !data.track || messages.length === 0;
  if (!modeless && data.track) {
    setTrack(data.track === "autocad" ? "autocad" : "inventor");
  }
  chatTitleEl.textContent = data.title || "Chat";
  chatCache.set(id, {
    messages: messages.map((m) => ({ ...m })),
    title: chatTitleEl.textContent,
    track,
  });
  renderMessages();
  await loadStatus();
  await loadChatList();
  updateSendEnabled();
  input.focus();
}

async function ensureChat() {
  if (chatId) return chatId;
  if (ensureChatPromise) {
    await ensureChatPromise;
    return chatId;
  }
  ensureChatPromise = (async () => {
    // Persist draft as a real chat only when the first message is sent.
    // Storage key is the unique id returned here — title is display-only.
    const res = await fetch("/api/chats", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ track, title: "New chat" }),
    });
    if (!res.ok) {
      throw new Error(`Could not create chat (${res.status})`);
    }
    const data = await res.json();
    if (!data.id) {
      throw new Error("Create chat returned no id");
    }
    chatId = data.id;
  })();
  try {
    await ensureChatPromise;
  } finally {
    ensureChatPromise = null;
  }
  return chatId;
}

/**
 * Run a reply for a specific chat. Multiple chats can be in flight at once.
 * Switching away is safe — the response applies to the request's chat only.
 */
/** Content sent to the LLM for resolved Confirm/Cancel lines (keeps UI card separately). */
function apiContentForMessage(m) {
  if (m.pending_launch && m.pending_launch.resolution === "confirmed") {
    const app = m.pending_launch.app === "autocad" ? "AutoCAD" : "Inventor";
    if (m.pending_launch.action === "force_restart") {
      const why = (m.pending_launch.reason || "").trim() || "COM/RPC recovery";
      return (
        `User confirmed quitting and restarting ${app} (reason: ${why}). ` +
        `Session was reset — recreate geometry from scratch, then continue.`
      );
    }
    return `User confirmed launching ${app}. Continue the previous request with live CAD tools.`;
  }
  if (m.pending_launch && m.pending_launch.resolution === "cancelled") {
    const app = m.pending_launch.app === "autocad" ? "AutoCAD" : "Inventor";
    if (m.pending_launch.action === "force_restart") {
      return (
        `User cancelled quitting ${app}. Do not kill or restart ${app}. ` +
        `Try soft recover only, or explain the blocker briefly.`
      );
    }
    return `User cancelled launching ${app}. Do not retry launch unless asked.`;
  }
  if (m.pending_switch && m.pending_switch.resolution === "confirmed") {
    const label =
      m.pending_switch.to_track === "autocad" ? "AutoCAD" : "Inventor";
    return `User confirmed switching to ${label} mode. Continue the previous request.`;
  }
  if (m.pending_switch && m.pending_switch.resolution === "cancelled") {
    return "User cancelled the mode switch. Stay in the current mode.";
  }
  return m.content || "";
}

async function continueChat(opts = null) {
  const requestChatId = (opts && opts.chatId) || chatId;
  const requestTrack = (opts && opts.track) || track;
  const requestMessages = (opts && opts.messages)
    ? opts.messages.map((m) => ({ ...m }))
    : messages.map((m) => ({ ...m }));
  const requestTitle =
    (opts && opts.title) || chatTitleEl.textContent || "Chat";

  if (!requestChatId || !requestMessages.length) return;
  if (pendingChats.has(requestChatId)) return;

  // Cache + persist BEFORE any further UI work so switching away can't drop it
  chatCache.set(requestChatId, {
    messages: requestMessages.map((m) => ({ ...m })),
    title: requestTitle,
    track: requestTrack,
  });
  pendingMeta.set(requestChatId, {
    title: requestTitle,
    track: requestTrack,
    message_count: requestMessages.length,
  });
  pendingChats.add(requestChatId);
  updateSendEnabled();

  const saved = await saveChatMessages(
    requestChatId,
    requestMessages,
    requestTrack,
    requestTitle
  );
  if (!saved) {
    pendingChats.delete(requestChatId);
    pendingMeta.delete(requestChatId);
    if (chatId === requestChatId) {
      addMessage("assistant", "Could not save this chat — try sending again.");
    }
    await loadChatList();
    updateSendEnabled();
    return;
  }

  if (chatId === requestChatId) showThinking();
  await loadChatList();

  const started = performance.now();
  const ac = new AbortController();
  abortControllers.set(requestChatId, ac);
  let wasAborted = false;
  const liveActions = [];
  try {
    const res = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      signal: ac.signal,
      body: JSON.stringify({
        messages: requestMessages.map((m) => ({
          role: m.role,
          content: apiContentForMessage(m),
        })),
        track: requestTrack,
        chat_id: requestChatId,
        stream: true,
        base_modelling_kit: baseModellingKit,
      }),
    });
    if (!res.ok) {
      const errText = await res.text();
      throw new Error(errText.slice(0, 300) || `HTTP ${res.status}`);
    }

    const data =
      (await readChatSse(res, (event) => {
        if (chatId !== requestChatId) return;
        if (event.type === "tool_start") {
          liveActions.push({
            tool: event.tool,
            arguments: event.arguments || {},
            pending: true,
          });
          updateThinkingTools(liveActions);
        } else if (event.type === "tool_end") {
          const idx = liveActions.findIndex(
            (a) => a.tool === event.tool && a.pending
          );
          const step = {
            tool: event.tool,
            arguments: event.arguments || {},
            result: event.result,
            pending: false,
          };
          if (idx >= 0) liveActions[idx] = step;
          else liveActions.push(step);
          updateThinkingTools(liveActions);
        }
      })) || {};

    const elapsedMs = performance.now() - started;
    const actions = data.actions || liveActions.filter((a) => !a.pending);

    let assistantMsg;
    if (data.error) {
      assistantMsg = {
        role: "assistant",
        content: data.error,
        actions,
        elapsed_ms: elapsedMs,
      };
    } else {
      const reply = data.reply || "(empty reply)";
      const pending =
        data.pending_switch || pendingFromActions(actions, requestTrack);
      const pendingLaunch =
        data.pending_launch || pendingLaunchFromActions(actions);
      assistantMsg = {
        role: "assistant",
        content: reply,
        actions,
        pending_switch: pending || undefined,
        pending_launch: pendingLaunch || undefined,
        elapsed_ms: elapsedMs,
      };
    }

    const nextMessages = [...requestMessages, assistantMsg];
    chatCache.set(requestChatId, {
      messages: nextMessages.map((m) => ({ ...m })),
      title: requestTitle,
      track: requestTrack,
    });
    pendingMeta.set(requestChatId, {
      title: requestTitle,
      track: requestTrack,
      message_count: nextMessages.length,
    });

    // Persist full UI meta (resolved Confirm lines) — server chat persist
    // only sees role/content from the API body and would drop resolution.
    await saveChatMessages(
      requestChatId,
      nextMessages,
      requestTrack,
      requestTitle
    );

    // Only touch the open transcript if we're still on this chat
    if (chatId === requestChatId) {
      hideThinking();
      messages = nextMessages.map((m) => ({ ...m }));
      addMessage(
        "assistant",
        assistantMsg.content,
        assistantMsg.actions,
        assistantMsg.pending_switch,
        elapsedMs,
        assistantMsg.pending_launch
      );
      modeBadge.textContent = data.mode || modeBadge.textContent;
      modeBadge.className = `badge ${data.mode === "live" ? "live" : "demo"}`;
    }
  } catch (err) {
    wasAborted = err && err.name === "AbortError";
    const stoppedActions = liveActions.map((a) =>
      a.pending
        ? {
            tool: a.tool,
            arguments: a.arguments || {},
            result: { ok: false, error: "Stopped" },
          }
        : {
            tool: a.tool,
            arguments: a.arguments || {},
            result: a.result,
          }
    );
    const errMsg = {
      role: "assistant",
      content: wasAborted ? "Stopped." : String(err),
      actions: stoppedActions.length ? stoppedActions : undefined,
      elapsed_ms: performance.now() - started,
    };
    const nextMessages = [...requestMessages, errMsg];
    chatCache.set(requestChatId, {
      messages: nextMessages.map((m) => ({ ...m })),
      title: requestTitle,
      track: requestTrack,
    });
    await saveChatMessages(
      requestChatId,
      nextMessages,
      requestTrack,
      requestTitle
    );
    if (chatId === requestChatId) {
      hideThinking();
      messages = nextMessages.map((m) => ({ ...m }));
      addMessage(
        "assistant",
        errMsg.content,
        errMsg.actions,
        null,
        errMsg.elapsed_ms
      );
    }
  } finally {
    abortControllers.delete(requestChatId);
    pendingChats.delete(requestChatId);
    pendingMeta.delete(requestChatId);
    await loadChatList();
    updateSendEnabled();
    if (chatId === requestChatId) input.focus();

    // Ding / notify when finished — skip noisy ding on user Stop
    if (!wasAborted) {
      const cached = chatCache.get(requestChatId);
      const last = (cached && cached.messages) || [];
      const lastAssistant = [...last]
        .reverse()
        .find((m) => m.role === "assistant");
      notifyReplyReady({
        title: requestTitle || "Chat",
        body: (lastAssistant && lastAssistant.content) || "Reply ready",
        fromBackground: chatId !== requestChatId,
      });
    }
  }
}

async function sendPrompt() {
  const text = input.value.trim();
  if (!text || isCurrentPending()) return;
  // Block double-send on draft before chatId exists
  if (!chatId && ensureChatPromise) return;
  // User gesture — ask once for OS notifications (other tabs / apps)
  ensureNotifyPermission();
  try {
    await ensureChat();
  } catch (err) {
    addMessage("assistant", String(err));
    return;
  }
  if (!chatId || pendingChats.has(chatId)) return;

  input.value = "";
  messages.push({ role: "user", content: text });
  addMessage("user", text);
  // Display title only — chats are stored/loaded by unique id, never by name
  if (chatTitleEl.textContent === "New chat") {
    chatTitleEl.textContent =
      text.slice(0, 56) + (text.length > 56 ? "…" : "");
  }

  // Persist immediately so switching away cannot orphan an empty chat
  const id = chatId;
  const title = chatTitleEl.textContent;
  chatCache.set(id, {
    messages: messages.map((m) => ({ ...m })),
    title,
    track,
  });
  pendingMeta.set(id, {
    title,
    track,
    message_count: messages.length,
  });
  const snapshot = messages.map((m) => ({ ...m }));
  await saveChatMessages(id, snapshot, track, title);
  await loadChatList();
  // Pass snapshot so a mid-save chat switch can't hijack this request
  continueChat({
    chatId: id,
    track,
    messages: snapshot,
    title,
  });
}

document.querySelectorAll(".track-btn").forEach((btn) => {
  btn.addEventListener("click", async () => {
    if (btn.dataset.track === track) return;
    setTrack(btn.dataset.track);
    if (messages.length > 0) {
      await startNewChat();
    } else if (!chatId) {
      await startNewChat();
    }
    await loadStatus();
    await loadChatList();
  });
});

if (baseModellingKitEl) {
  baseModellingKitEl.addEventListener("change", async () => {
    setBaseModellingKit(baseModellingKitEl.checked);
    await loadStatus();
  });
}

document.querySelectorAll(".filter-btn").forEach((btn) => {
  btn.addEventListener("click", async () => {
    if (btn.dataset.filter === chatFilter) return;
    setChatFilter(btn.dataset.filter);
    await loadChatList();
  });
});

newChatBtn.addEventListener("click", async () => {
  await startNewChat();
  input.focus();
});

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  await sendPrompt();
});

input.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    sendPrompt();
  }
});

(async function init() {
  setTrack(track);
  setChatFilter(chatFilter);
  setBaseModellingKit(baseModellingKit);
  // Resume the most recent chat; only draft New when none exist (or user clicks New).
  let opened = false;
  try {
    const res = await fetch("/api/chats");
    const data = await res.json();
    const chats = data.chats || [];
    if (chats.length && chats[0].id) {
      await openChat(chats[0].id);
      opened = true;
    }
  } catch (_err) {
    /* fall through to New chat */
  }
  if (!opened) {
    await startNewChat();
    await loadStatus();
    await loadChatList();
  }
  updateSendEnabled();
  input.focus();
})();
