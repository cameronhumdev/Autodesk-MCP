"""In-memory CAD tool relay: cloud UI → gateway → laptop agent."""

from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any


@dataclass
class _Job:
    id: str
    tool: str
    arguments: dict[str, Any]
    created: float = field(default_factory=time.time)
    done: threading.Event = field(default_factory=threading.Event)
    result: Any = None
    error: str | None = None


class RelayHub:
    """One agent per tenant (dev: single 'dev' tenant)."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._agents: dict[str, dict[str, Any]] = {}
        self._pending: dict[str, list[_Job]] = {}
        self._jobs: dict[str, _Job] = {}
        self._wake: dict[str, threading.Event] = {}

    def agent_online(self, tenant_id: str = "dev") -> bool:
        with self._lock:
            ag = self._agents.get(tenant_id)
            if not ag:
                return False
            return (time.time() - float(ag.get("last_seen") or 0)) < 90

    def agent_hello(self, tenant_id: str, meta: dict[str, Any] | None = None) -> None:
        with self._lock:
            self._agents[tenant_id] = {
                "last_seen": time.time(),
                "meta": meta or {},
            }
            self._pending.setdefault(tenant_id, [])
            self._wake.setdefault(tenant_id, threading.Event())

    def agent_heartbeat(self, tenant_id: str) -> None:
        with self._lock:
            ag = self._agents.get(tenant_id)
            if ag:
                ag["last_seen"] = time.time()

    def poll(
        self, tenant_id: str, wait_s: float = 25.0
    ) -> dict[str, Any] | None:
        deadline = time.time() + max(0.5, wait_s)
        while time.time() < deadline:
            with self._lock:
                self.agent_heartbeat(tenant_id)
                q = self._pending.get(tenant_id) or []
                if q:
                    job = q.pop(0)
                    return {
                        "id": job.id,
                        "tool": job.tool,
                        "arguments": job.arguments,
                    }
                ev = self._wake.setdefault(tenant_id, threading.Event())
                ev.clear()
            remaining = deadline - time.time()
            if remaining <= 0:
                break
            ev.wait(timeout=min(remaining, 2.0))
        return None

    def submit_result(
        self, job_id: str, *, ok: bool, result: Any = None, error: str | None = None
    ) -> bool:
        with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                return False
            job.result = result
            job.error = None if ok else (error or "agent error")
            job.done.set()
            return True

    def call_tool(
        self,
        tool: str,
        arguments: dict[str, Any] | None = None,
        *,
        tenant_id: str = "dev",
        timeout_s: float = 120.0,
    ) -> dict[str, Any]:
        if not self.agent_online(tenant_id):
            return {
                "ok": False,
                "error": (
                    "No laptop CAD agent connected. On your PC run: "
                    "python -m client serve-agent"
                ),
                "agent_online": False,
            }
        job = _Job(
            id=uuid.uuid4().hex,
            tool=tool,
            arguments=arguments or {},
        )
        with self._lock:
            self._jobs[job.id] = job
            self._pending.setdefault(tenant_id, []).append(job)
            self._wake.setdefault(tenant_id, threading.Event()).set()
        finished = job.done.wait(timeout=max(5.0, timeout_s))
        with self._lock:
            self._jobs.pop(job.id, None)
        if not finished:
            return {
                "ok": False,
                "error": f"CAD agent timed out after {timeout_s:.0f}s waiting for {tool}",
                "agent_online": True,
            }
        result = job.result
        if isinstance(result, dict):
            return result
        if job.error:
            return {"ok": False, "error": job.error, "agent_online": True}
        return {"ok": True, "result": result}


HUB = RelayHub()
