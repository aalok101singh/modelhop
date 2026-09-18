"""MCP hook for tool-invocation turns (v1.1 W2)."""

from __future__ import annotations

from typing import Any, Dict, Optional


async def mcp_tool_hook(
    query: str,
    tool_name: str,
    tool_args: Optional[Dict[str, Any]] = None,
    mh=None,
    trust_required: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Route a tool-invocation turn with spend/latency awareness.

    Returns {"response": str, "model": str, "degraded": bool}.
    Indirect prompt injection note: tool output is treated as DATA, never
    spliced into control prompts (analyzer delimiting enforces this).
    """
    if mh is None:
        from modelhop import ModelHop as _MH

        mh = _MH()
    context = {"tool": tool_name, "tool_args_keys": sorted((tool_args or {}).keys())}
    result = await mh.route(query, trust_required=trust_required or {}, context=context)
    return {"response": result.response, "model": result.model, "degraded": result.degraded}
