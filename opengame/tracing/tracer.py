"""Tracer — captures agent trace events during game generation.

Thread-safe, lightweight event collector that flushes to SQLite
at session end. Designed to be used as an async context manager.
"""

from __future__ import annotations

import time
from contextlib import asynccontextmanager
from typing import Any

from opengame.tracing.store import TraceStore


class TraceSession:
    """An active trace session recording one game generation run.

    Collects events in memory and flushes to the TraceStore on close.
    """

    def __init__(self, store: TraceStore) -> None:
        self.store = store
        self.session_id: int | None = None
        self._seq: int = 0
        self._events: list[dict[str, Any]] = []
        self._phase_timers: dict[str, float] = {}

    def start(self, prompt: str, model: str, metadata: dict[str, Any] | None = None) -> None:
        """Begin the trace session."""
        self.session_id = self.store.create_session(prompt, model, metadata)
        self._seq = 0
        self._events = []

    def finish(self, success: bool, error: str | None = None) -> None:
        """Flush any remaining buffered events and close the session."""
        self._flush()
        if self.session_id is not None:
            self.store.finish_session(self.session_id, success, error)

    def _flush(self) -> None:
        """Write buffered events to DB immediately."""
        if self._events:
            self.store.add_event_batch(self._events)
            self._events.clear()

    # --- Phase tracking ---

    def phase_start(self, phase: str, detail: str = "") -> None:
        """Record the start of a pipeline phase."""
        self._seq += 1
        self._phase_timers[phase] = time.monotonic()
        self._emit(phase, "phase_start", {"detail": detail})

    def phase_end(self, phase: str, result: str = "", metrics: dict[str, Any] | None = None) -> None:
        """Record the end of a pipeline phase and flush to DB."""
        self._seq += 1
        elapsed = 0.0
        if phase in self._phase_timers:
            elapsed = time.monotonic() - self._phase_timers.pop(phase)
        data: dict[str, Any] = {"result": result, "elapsed_ms": int(elapsed * 1000)}
        if metrics:
            data.update(metrics)
        self._emit(phase, "phase_end", data)
        self._flush()  # Persist events after each phase

    # --- LLM tracing ---

    def llm_call(
        self, phase: str, model: str, messages_len: int, tools_count: int = 0,
    ) -> int:
        """Record an LLM API call. Returns call_id for matching with llm_response."""
        self._seq += 1
        call_id = self._seq
        self._emit(phase, "llm_call", {
            "call_id": call_id, "model": model,
            "messages_len": messages_len, "tools_count": tools_count,
        })
        return call_id

    def llm_response(
        self, phase: str, call_id: int, finish_reason: str = "stop",
        tokens: int = 0, elapsed_ms: int = 0, has_tool_calls: bool = False,
    ) -> None:
        """Record the LLM response for a previous call."""
        self._seq += 1
        self._emit(phase, "llm_response", {
            "call_id": call_id, "finish_reason": finish_reason,
            "tokens": tokens, "elapsed_ms": elapsed_ms,
            "has_tool_calls": has_tool_calls,
        })

    def record_llm_exchange(
        self,
        phase: str,
        messages: list[dict[str, Any]],
        response_content: str | None,
        model: str = "",
        finish_reason: str = "stop",
        token_usage: dict[str, int] | None = None,
        tool_calls: list[dict[str, Any]] | None = None,
        elapsed_ms: int = 0,
    ) -> None:
        """Record a complete LLM exchange — messages sent + response received.

        Captures the full OpenAI-format conversation for training and debugging.
        Large message contents are truncated to avoid excessive DB bloat.

        Args:
            phase: Pipeline phase (scaffold, gdd, implementation, etc.).
            messages: Full messages array sent to the LLM.
            response_content: The LLM's text response.
            model: Model name used for this call.
            finish_reason: stop, tool_calls, length, etc.
            token_usage: Dict with prompt_tokens, completion_tokens, total_tokens.
            tool_calls: Tool calls returned by the LLM.
            elapsed_ms: Call duration in milliseconds.
        """
        self._seq += 1
        # Truncate message contents to keep DB size reasonable
        truncated_messages = []
        for msg in messages:
            m = {"role": msg.get("role", "unknown")}
            content = msg.get("content", "")
            if isinstance(content, str):
                m["content"] = content[:2000]  # truncate per message
            elif content is None:
                m["content"] = None
            else:
                m["content"] = str(content)[:2000]
            # Preserve tool_calls in assistant messages
            if msg.get("tool_calls"):
                m["tool_calls"] = [
                    {"id": tc.get("id", ""), "function": {
                        "name": tc.get("function", {}).get("name", ""),
                        "arguments": tc.get("function", {}).get("arguments", "")[:500],
                    }}
                    for tc in msg["tool_calls"]
                ]
            if msg.get("tool_call_id"):
                m["tool_call_id"] = msg["tool_call_id"]
            truncated_messages.append(m)

        # Truncate response
        resp = (response_content or "")[:3000]

        self._emit(phase, "llm_exchange", {
            "model": model,
            "messages": truncated_messages,
            "messages_count": len(messages),
            "response": resp,
            "finish_reason": finish_reason,
            "token_usage": token_usage or {},
            "tool_calls": tool_calls or [],
            "elapsed_ms": elapsed_ms,
        })
        self._flush()  # Persist LLM exchanges immediately

    # --- Tool tracing ---

    def tool_call(self, phase: str, tool_name: str, tool_call_id: str) -> None:
        """Record a tool execution start."""
        self._seq += 1
        self._emit(phase, "tool_call", {
            "tool_name": tool_name, "tool_call_id": tool_call_id,
        })

    def tool_result(
        self, phase: str, tool_name: str, tool_call_id: str,
        success: bool, output_len: int, error: str | None = None,
        elapsed_ms: int = 0,
    ) -> None:
        """Record a tool execution result."""
        self._seq += 1
        self._emit(phase, "tool_result", {
            "tool_name": tool_name, "tool_call_id": tool_call_id,
            "success": success, "output_len": output_len,
            "error": error, "elapsed_ms": elapsed_ms,
        })

    # --- Error/exception tracing ---

    def error(self, phase: str, error_message: str, error_type: str = "generic") -> None:
        """Record an error that occurred during a phase."""
        self._seq += 1
        self._emit(phase, "error", {
            "error_type": error_type, "message": error_message[:500],
        })
        self._flush()  # Flush immediately on errors

    # --- Debug iteration ---

    def debug_iteration(
        self, phase: str, iteration: int, stage: str, passed: bool,
        error_code: str = "", repair_action: str = "",
    ) -> None:
        """Record a single debug loop iteration."""
        self._seq += 1
        self._emit(phase, "debug_iteration", {
            "iteration": iteration, "stage": stage, "passed": passed,
            "error_code": error_code, "repair_action": repair_action[:200],
        })

    # --- Internal ---

    def _emit(self, phase: str, event_type: str, data: dict[str, Any]) -> None:
        """Buffer a trace event for batch insert."""
        self._events.append({
            "session_id": self.session_id,
            "seq": self._seq,
            "phase": phase,
            "event_type": event_type,
            "data": data,
        })


class Tracer:
    """Async context manager for trace sessions.

    Usage:
        store = TraceStore()
        store.open()
        async with Tracer(store, prompt, model) as trace:
            trace.phase_start("scaffold")
            ...
            trace.phase_end("scaffold", result="platformer")
        # trace.finish() called automatically on exit
    """

    def __init__(
        self, store: TraceStore, prompt: str, model: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self.store = store
        self.prompt = prompt
        self.model = model
        self.metadata = metadata
        self.session = TraceSession(store)

    async def __aenter__(self) -> TraceSession:
        self.session.start(self.prompt, self.model, self.metadata)
        return self.session

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        if exc_type is not None:
            self.session.finish(
                success=False,
                error=f"{exc_type.__name__}: {exc_val}",
            )
        else:
            self.session.finish(success=True)
