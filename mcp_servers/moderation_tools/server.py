"""
MCP Server for Moderation Tools.
Exposes moderation actions as MCP tools for agents.
"""

import asyncio
import json
from typing import Any
from mcp.server import Server
from mcp.types import Tool, TextContent
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from data.db import Database
from mcp_servers.moderation_tools.tools import ModerationTools

# Initialize server
app = Server("cupidsshield-moderation-tools")

# Global database and tools instance
db = None
moderation_tools = None


@app.list_tools()
async def list_tools() -> list[Tool]:
    """List available moderation tools."""
    return [
        Tool(
            name="flag_content",
            description="Flag content for moderation review and create a case",
            inputSchema={
                "type": "object",
                "properties": {
                    "content_id": {"type": "string", "description": "Unique content identifier"},
                    "content_type": {
                        "type": "string",
                        "enum": ["profile", "message", "photo", "bio"],
                        "description": "Type of content",
                    },
                    "content": {"type": "string", "description": "The content text"},
                    "user_id": {"type": "string", "description": "User who created content"},
                    "violation_type": {
                        "type": "string",
                        "description": "Type of violation (harassment, scam, fake_profile, inappropriate, age_verification)",
                    },
                    "confidence": {
                        "type": "number",
                        "minimum": 0,
                        "maximum": 1,
                        "description": "Confidence score 0-1",
                    },
                    "reasoning": {"type": "string", "description": "Explanation for flagging"},
                    "severity": {
                        "type": "string",
                        "enum": ["low", "medium", "high", "critical"],
                        "description": "Severity level",
                        "default": "medium",
                    },
                    "metadata": {
                        "type": "object",
                        "description": "Additional context",
                    },
                },
                "required": [
                    "content_id",
                    "content_type",
                    "content",
                    "user_id",
                    "violation_type",
                    "confidence",
                    "reasoning",
                ],
            },
        ),
        Tool(
            name="apply_moderation_action",
            description="Apply a moderation action (ban, warn, etc.) to a user",
            inputSchema={
                "type": "object",
                "properties": {
                    "case_id": {"type": "string", "description": "Case ID to apply action to"},
                    "action": {
                        "type": "string",
                        "enum": [
                            "warn",
                            "temp_ban_24h",
                            "temp_ban_7d",
                            "permanent_ban",
                            "permanent_ban_and_report",
                        ],
                        "description": "Action to take",
                    },
                    "reviewed_by": {
                        "type": "string",
                        "description": "Who applied action (agent or moderator_id)",
                        "default": "agent",
                    },
                    "justification": {
                        "type": "string",
                        "description": "Additional justification",
                    },
                },
                "required": ["case_id", "action"],
            },
        ),
        Tool(
            name="get_user_history",
            description="Get moderation history for a user",
            inputSchema={
                "type": "object",
                "properties": {
                    "user_id": {"type": "string", "description": "User ID to look up"},
                    "limit": {
                        "type": "integer",
                        "description": "Maximum cases to return",
                        "default": 10,
                        "minimum": 1,
                        "maximum": 50,
                    },
                },
                "required": ["user_id"],
            },
        ),
        Tool(
            name="create_case",
            description="Create a new moderation case",
            inputSchema={
                "type": "object",
                "properties": {
                    "content_type": {
                        "type": "string",
                        "enum": ["profile", "message", "photo", "bio"],
                    },
                    "content": {"type": "string"},
                    "user_id": {"type": "string"},
                    "violation_type": {"type": "string"},
                    "reasoning": {"type": "string"},
                    "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                    "severity": {
                        "type": "string",
                        "enum": ["low", "medium", "high", "critical"],
                        "default": "medium",
                    },
                    "decision": {"type": "string"},
                    "metadata": {"type": "object"},
                },
                "required": [
                    "content_type",
                    "content",
                    "user_id",
                    "violation_type",
                    "reasoning",
                    "confidence",
                ],
            },
        ),
        Tool(
            name="update_case",
            description="Update an existing case decision",
            inputSchema={
                "type": "object",
                "properties": {
                    "case_id": {"type": "string"},
                    "decision": {"type": "string"},
                    "reasoning": {"type": "string"},
                    "reviewed_by": {"type": "string"},
                    "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                },
                "required": ["case_id", "decision", "reasoning", "reviewed_by"],
            },
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: Any) -> list[TextContent]:
    """Handle tool calls."""
    global moderation_tools

    try:
        # Route to appropriate tool
        if name == "flag_content":
            result = await moderation_tools.flag_content(**arguments)
        elif name == "apply_moderation_action":
            result = await moderation_tools.apply_moderation_action(**arguments)
        elif name == "get_user_history":
            result = await moderation_tools.get_user_history(**arguments)
        elif name == "create_case":
            result = await moderation_tools.create_case(**arguments)
        elif name == "update_case":
            result = await moderation_tools.update_case(**arguments)
        else:
            result = {"success": False, "error": f"Unknown tool: {name}"}

        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    except Exception as e:
        error_result = {"success": False, "error": str(e)}
        return [TextContent(type="text", text=json.dumps(error_result, indent=2))]


async def main():
    """Run the MCP server."""
    global db, moderation_tools

    # Initialize database
    db = Database()
    await db.initialize()

    # Initialize tools
    moderation_tools = ModerationTools(db)

    print("CupidsShield Moderation Tools MCP Server")
    print("=" * 50)
    print("Server ready and listening for tool calls...")
    print()
    print("Available tools:")
    tools = await list_tools()
    for tool in tools:
        print(f"  - {tool.name}: {tool.description}")
    print()

    # Run server
    from mcp.server.stdio import stdio_server

    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
