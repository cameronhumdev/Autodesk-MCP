"""MCP stdio client using the official Python MCP SDK."""

from __future__ import annotations

import asyncio
import json
import os
import threading
from contextlib import AsyncExitStack
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


class McpStdioError(RuntimeError):
    pass


class McpStdioClient:
    """Sync façade over the async MCP stdio client (one server subprocess).

    The asyncio loop lives on a dedicated thread so this is safe to call from
    FastAPI/uvicorn's already-running event loop.
    """

    def __init__(
        self,
        command: list[str],
        env: dict[str, str] | None = None,
        cwd: str | None = None,
        timeout_s: float = 90.0,
    ) -> None:
        if not command:
            raise ValueError("empty MCP command")
        self.command = command[0]
        self.args = command[1:]
        self.env = env
        self.cwd = cwd
        self.timeout_s = timeout_s
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._stack: AsyncExitStack | None = None
        self._session: ClientSession | None = None
        self._started = threading.Event()
        self._start_error: BaseException | None = None
        self._lock = threading.Lock()

    def start(self) -> None:
        with self._lock:
            if self._session is not None:
                return
            if self._thread is not None and self._thread.is_alive():
                self._wait_started()
                return
            self._started.clear()
            self._start_error = None
            self._thread = threading.Thread(
                target=self._thread_main,
                name=f"mcp-stdio-{self.command}",
                daemon=True,
            )
            self._thread.start()
            self._wait_started()

    def _wait_started(self) -> None:
        if not self._started.wait(timeout=self.timeout_s):
            raise McpStdioError("MCP client failed to start (timeout)")
        if self._start_error is not None:
            raise McpStdioError(f"MCP client failed to start: {self._start_error}") from self._start_error
        if self._session is None:
            raise McpStdioError("MCP client failed to start (no session)")

    def _thread_main(self) -> None:
        loop = asyncio.new_event_loop()
        self._loop = loop
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self._async_start())
        except BaseException as exc:  # noqa: BLE001 — surface to waiter
            self._start_error = exc
            self._started.set()
            try:
                loop.close()
            except Exception:
                pass
            self._loop = None
            return

        self._started.set()
        try:
            loop.run_forever()
        finally:
            try:
                if self._stack is not None:
                    loop.run_until_complete(self._stack.aclose())
            except Exception:
                pass
            self._stack = None
            self._session = None
            try:
                loop.close()
            except Exception:
                pass
            self._loop = None

    async def _async_start(self) -> None:
        full_env = os.environ.copy()
        if self.env:
            full_env.update(self.env)
        full_env.setdefault("PYTHONUTF8", "1")
        full_env.setdefault("PYTHONIOENCODING", "utf-8")
        params = StdioServerParameters(
            command=self.command,
            args=self.args,
            env=full_env,
            cwd=self.cwd,
        )
        self._stack = AsyncExitStack()
        read, write = await self._stack.enter_async_context(stdio_client(params))
        session = await self._stack.enter_async_context(ClientSession(read, write))
        await asyncio.wait_for(session.initialize(), timeout=self.timeout_s)
        self._session = session

    def _run(self, coro: Any) -> Any:
        self.start()
        assert self._loop is not None
        fut = asyncio.run_coroutine_threadsafe(coro, self._loop)
        try:
            return fut.result(timeout=self.timeout_s)
        except Exception as exc:
            raise McpStdioError(str(exc)) from exc

    def close(self) -> None:
        loop = self._loop
        stack = self._stack
        if loop is None:
            return
        if stack is not None and loop.is_running():
            try:
                asyncio.run_coroutine_threadsafe(stack.aclose(), loop).result(timeout=5)
            except Exception:
                pass
        if loop.is_running():
            loop.call_soon_threadsafe(loop.stop)
        thread = self._thread
        if thread is not None and thread.is_alive():
            thread.join(timeout=5)
        self._stack = None
        self._session = None
        self._thread = None

    def list_tools(self) -> list[dict[str, Any]]:
        """Return upstream MCP tools including JSON Schema (inputSchema)."""
        self.start()
        assert self._session is not None

        async def _list_all() -> list[Any]:
            assert self._session is not None
            collected: list[Any] = []
            cursor: str | None = None
            while True:
                result = await asyncio.wait_for(
                    self._session.list_tools(cursor=cursor),
                    timeout=self.timeout_s,
                )
                collected.extend(result.tools or [])
                cursor = (
                    getattr(result, "nextCursor", None)
                    or getattr(result, "next_cursor", None)
                    or None
                )
                if not cursor:
                    break
            return collected

        raw_tools = self._run(_list_all())
        tools: list[dict[str, Any]] = []
        for t in raw_tools:
            schema = getattr(t, "inputSchema", None)
            if schema is None:
                schema = {"type": "object", "properties": {}}
            elif hasattr(schema, "model_dump"):
                schema = schema.model_dump(mode="json")
            elif not isinstance(schema, dict):
                try:
                    schema = dict(schema)
                except Exception:
                    schema = {"type": "object", "properties": {}}
            tools.append(
                {
                    "name": t.name,
                    "description": t.description or t.name,
                    "inputSchema": schema,
                }
            )
        return tools

    def call_tool(self, name: str, arguments: dict[str, Any] | None = None) -> Any:
        self.start()
        assert self._session is not None
        try:
            result = self._run(
                asyncio.wait_for(
                    self._session.call_tool(name, arguments or {}),
                    timeout=self.timeout_s,
                )
            )
        except McpStdioError:
            raise
        except Exception as exc:
            raise McpStdioError(f"tool {name} failed: {exc}") from exc

        if getattr(result, "isError", False):
            raise McpStdioError(f"tool {name} error: {result}")

        parts: list[str] = []
        for block in result.content or []:
            text = getattr(block, "text", None)
            if text is not None:
                parts.append(text)
            else:
                parts.append(str(block))
        text = "\n".join(parts).strip()
        if not text:
            return {"ok": True}
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return {"text": text}
