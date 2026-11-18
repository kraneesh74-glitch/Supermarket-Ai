"""Unified Tool Registry for Supermarket AI Agent (Strictly 4 Tools - 📘 Lesson 2)."""

from typing import Any, Dict, List
import json
from packages.tools.base import SupermarketTool, ToolResult
from packages.tools.inventory_tool import inventory_tool
from packages.tools.store_info_tool import store_info_tool
from packages.tools.order_tool import order_tool
from packages.tools.promo_tool import promo_tool
from apps.agent.cache import cache

# Strictly 4 core supermarket tools (📘 Lesson 2)
CORE_TOOLS: Dict[str, SupermarketTool] = {
    inventory_tool.name: inventory_tool,
    store_info_tool.name: store_info_tool,
    order_tool.name: order_tool,
    promo_tool.name: promo_tool,
}

# Cache tag mapping for multi-tier caching (Task 4.3)
CACHEABLE_TOOLS = {
    "get_store_info": ("store_info", 1800),         # 30 mins
    "get_active_promotions": ("promotions", 900),   # 15 mins
    "check_inventory_and_price": ("inventory", 300),# 5 mins
}


def get_tool_schemas() -> List[Dict[str, Any]]:
    """Return JSON schemas for the 4 core tools formatted for LLM function calling."""
    schemas = []
    for tool in CORE_TOOLS.values():
        schemas.append({
            "name": tool.name,
            "description": tool.description,
            "parameters": tool.parameters,
        })
    return schemas


def execute_tool(tool_name: str, arguments: Dict[str, Any]) -> ToolResult:
    """Execute tool with caching, error interception and self-healing guidance (📘 Lesson 2 & Task 4.3)."""
    if tool_name not in CORE_TOOLS:
        valid_tools = list(CORE_TOOLS.keys())
        return ToolResult(
            success=False,
            error=f"Tool '{tool_name}' does not exist.",
            recovery_suggestion=f"Please choose from one of the 4 supported tools: {valid_tools}",
        )

    # Check cache for cacheable read tools
    cache_key = None
    if tool_name in CACHEABLE_TOOLS:
        sorted_args = json.dumps(arguments, sort_keys=True)
        cache_key = f"{tool_name}:{sorted_args}"
        cached_result = cache.get(cache_key)
        if cached_result is not None:
            return ToolResult(success=True, data=cached_result)

    tool = CORE_TOOLS[tool_name]
    result = tool.run(**arguments)

    # Store successful result in cache
    if result.success and cache_key and tool_name in CACHEABLE_TOOLS:
        tag, ttl = CACHEABLE_TOOLS[tool_name]
        cache.set(cache_key, result.data, ttl=ttl, tag=tag)

    return result

