"""
agent.py — ReefScout's agentic core.

This is the piece the whole project hangs on (rubric #6/#7): a manual tool-call loop
where **the model decides** which MCP tools to call, in what order, and when to stop.

Flow per user message:
  1. Connect to the MCP server (stdio JSON-RPC) and list its tools.
  2. Convert MCP tool schemas to the Anthropic `tools` parameter shape.
  3. Call Claude. If `stop_reason == "tool_use"`, dispatch each tool_use block to the
     MCP server, append the tool_result blocks, and loop. Otherwise return the text.
  4. Every dispatch is recorded in a trace that the UI renders ("what the agent did")
     and the eval harness asserts against.

Deliberately a hand-written loop rather than the SDK's automatic tool-runner: the loop
itself is the evidence of agentic behavior, and we want full control over tracing.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from contextlib import AsyncExitStack
from datetime import date
from pathlib import Path
from typing import Any, Optional

from anthropic import AsyncAnthropic
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

DEFAULT_MODEL = "claude-sonnet-4-6"
MAX_LOOP_ITERATIONS = 12   # safety net so a pathological loop can't spend unbounded tokens
MAX_TOKENS = 8000
TOOL_RESULT_CHAR_LIMIT = 30_000  # keep one giant tool result from blowing up the context


def _model() -> str:
    return os.environ.get("REEFSCOUT_MODEL", DEFAULT_MODEL)


class ReefScoutAgent:
    """Owns one MCP server connection and an Anthropic client.

    Created once at app startup (see main.py lifespan) so the MCP subprocess and the
    NOAA station cache persist across requests instead of respawning per chat.
    """

    def __init__(self) -> None:
        self._stack: Optional[AsyncExitStack] = None
        self._mcp: Optional[ClientSession] = None
        self._tools: list[dict] = []
        self._client = AsyncAnthropic()  # key from ANTHROPIC_API_KEY
        self._lock = asyncio.Lock()  # serialize agent runs over the single MCP session

    # -- lifecycle ----------------------------------------------------------------

    async def start(self) -> None:
        self._stack = AsyncExitStack()
        # cwd pinned to the project root so `-m app.mcp_server` resolves regardless of
        # where the parent process was launched from.
        project_root = Path(__file__).resolve().parent.parent
        params = StdioServerParameters(
            command=sys.executable, args=["-m", "app.mcp_server"], cwd=str(project_root)
        )
        read, write = await self._stack.enter_async_context(stdio_client(params))
        self._mcp = await self._stack.enter_async_context(ClientSession(read, write))
        await self._mcp.initialize()

        # MCP tool schema -> Anthropic `tools` parameter shape.
        listed = await self._mcp.list_tools()
        self._tools = [
            {"name": t.name, "description": t.description or "", "input_schema": t.inputSchema}
            for t in listed.tools
        ]

    async def stop(self) -> None:
        if self._stack is not None:
            await self._stack.aclose()
            self._stack = None
            self._mcp = None

    # -- tool dispatch ------------------------------------------------------------

    async def _dispatch(self, name: str, args: dict) -> tuple[str, bool]:
        """Execute one tool call on the MCP server. Returns (result_text, is_error)."""
        assert self._mcp is not None
        try:
            result = await self._mcp.call_tool(name, args)
        except Exception as exc:  # noqa: BLE001 - surface failures to the model, don't crash
            return f"Tool execution failed: {exc}", True

        parts = [c.text for c in result.content if getattr(c, "type", None) == "text"]
        text = "\n".join(parts) if parts else "(empty result)"
        if len(text) > TOOL_RESULT_CHAR_LIMIT:
            text = text[:TOOL_RESULT_CHAR_LIMIT] + "\n...[truncated]"
        return text, bool(result.isError)

    @staticmethod
    def _trace_summary(result_text: str, is_error: bool) -> str:
        """One-line, human-readable digest of a tool result for the UI trace panel."""
        if is_error:
            return f"error: {result_text[:110]}"
        try:
            data = json.loads(result_text)
        except (json.JSONDecodeError, TypeError):
            return result_text[:120]
        if isinstance(data, dict):
            if data.get("found") is False:
                return f"no data: {str(data.get('error'))[:100]}"
            keys = [k for k in data.keys() if k not in ("found", "source")][:5]
            return "→ " + ", ".join(keys) if keys else "→ ok"
        return result_text[:120]

    # -- the agentic loop ---------------------------------------------------------

    async def run(self, message: str, history: list[dict] | None = None) -> dict:
        """Run one user message through the agent. Returns {reply, trace, usage}."""
        if self._mcp is None:
            raise RuntimeError("Agent not started")

        messages: list[dict] = list(history or []) + [{"role": "user", "content": message}]
        trace: list[dict] = []
        usage = {"input_tokens": 0, "output_tokens": 0, "cache_read_input_tokens": 0}

        from app.prompts import SYSTEM_PROMPT  # late import: prompts iterate during dev

        async with self._lock:
            for _ in range(MAX_LOOP_ITERATIONS):
                response = await self._client.messages.create(
                    model=_model(),
                    max_tokens=MAX_TOKENS,
                    # Block 1 (cached): stable prompt — the breakpoint here also caches
                    # the tools prefix, so loop iterations 2..n re-read at ~0.1x cost.
                    # Block 2 (after the breakpoint): today's date. Without it the model
                    # resolves "tomorrow" from its training data — caught in smoke
                    # testing when "tomorrow" came out as a date in the wrong year.
                    system=[
                        {
                            "type": "text",
                            "text": SYSTEM_PROMPT,
                            "cache_control": {"type": "ephemeral"},
                        },
                        {
                            "type": "text",
                            "text": f"Today's date is {date.today().isoformat()} "
                                    f"({date.today().strftime('%A')}).",
                        },
                    ],
                    tools=self._tools,
                    messages=messages,
                )
                usage["input_tokens"] += response.usage.input_tokens
                usage["output_tokens"] += response.usage.output_tokens
                usage["cache_read_input_tokens"] += response.usage.cache_read_input_tokens or 0

                # THE decision point: the model chose to stop, or chose to call tools.
                if response.stop_reason != "tool_use":
                    reply = "".join(b.text for b in response.content if b.type == "text")
                    return {"reply": reply, "trace": trace, "usage": usage}

                # Model chose tools: execute each tool_use block via MCP.
                messages.append({"role": "assistant", "content": response.content})
                tool_results: list[dict] = []
                for block in response.content:
                    if block.type != "tool_use":
                        continue
                    started = time.perf_counter()
                    result_text, is_error = await self._dispatch(block.name, dict(block.input))
                    elapsed_ms = int((time.perf_counter() - started) * 1000)
                    trace.append({
                        "tool": block.name,
                        "args": dict(block.input),
                        "summary": self._trace_summary(result_text, is_error),
                        "ms": elapsed_ms,
                    })
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result_text,
                        "is_error": is_error,
                    })
                messages.append({"role": "user", "content": tool_results})

        # Loop guard tripped — return what we have rather than erroring out.
        return {
            "reply": ("I hit my tool-call limit before finishing. Here's what I gathered "
                      "so far — try narrowing the question."),
            "trace": trace,
            "usage": usage,
        }
