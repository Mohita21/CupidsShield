"""
MCP Server for Notifications.
Exposes notification and alerting tools for agents.
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
from mcp_servers.notifications.notifiers import Notifiers

# Initialize server
app = Server("cupidsshield-notifications")

# Global instances
db = None
notifiers = None


@app.list_tools()
async def list_tools() -> list[Tool]:
    """List available notification tools."""
    return [
        Tool(
            name="send_user_notification",
            description="Send a notification to a user",
            inputSchema={
                "type": "object",
                "properties": {
                    "user_id": {"type": "string", "description": "User ID to notify"},
                    "notification_type": {
                        "type": "string",
                        "description": "Type of notification",
                    },
                    "title": {"type": "string", "description": "Notification title"},
                    "message": {"type": "string", "description": "Notification message"},
                    "case_id": {"type": "string", "description": "Related case ID"},
                    "metadata": {"type": "object", "description": "Additional metadata"},
                },
                "required": ["user_id", "notification_type", "title", "message"],
            },
        ),
        Tool(
            name="send_moderator_alert",
            description="Send an alert to moderators",
            inputSchema={
                "type": "object",
                "properties": {
                    "alert_type": {"type": "string", "description": "Type of alert"},
                    "priority": {
                        "type": "string",
                        "enum": ["low", "medium", "high", "urgent"],
                        "description": "Priority level",
                    },
                    "title": {"type": "string", "description": "Alert title"},
                    "description": {"type": "string", "description": "Alert description"},
                    "case_id": {"type": "string", "description": "Related case ID"},
                    "appeal_id": {"type": "string", "description": "Related appeal ID"},
                    "assigned_to": {
                        "type": "string",
                        "description": "Specific moderator to assign to",
                    },
                    "metadata": {"type": "object", "description": "Additional metadata"},
                },
                "required": ["alert_type", "priority", "title", "description"],
            },
        ),
        Tool(
            name="log_action",
            description="Log an action to the audit trail",
            inputSchema={
                "type": "object",
                "properties": {
                    "action": {"type": "string", "description": "Action performed"},
                    "actor": {"type": "string", "description": "Who performed the action"},
                    "case_id": {"type": "string", "description": "Related case ID"},
                    "appeal_id": {"type": "string", "description": "Related appeal ID"},
                    "details": {"type": "object", "description": "Additional details"},
                },
                "required": ["action", "actor"],
            },
        ),
        Tool(
            name="send_decision_notification",
            description="Send a moderation decision notification to a user",
            inputSchema={
                "type": "object",
                "properties": {
                    "user_id": {"type": "string"},
                    "case_id": {"type": "string"},
                    "decision": {
                        "type": "string",
                        "enum": ["approved", "rejected", "escalated"],
                    },
                    "violation_type": {"type": "string"},
                    "reasoning": {"type": "string"},
                    "action_taken": {"type": "string", "description": "Action taken (optional)"},
                },
                "required": ["user_id", "case_id", "decision", "violation_type", "reasoning"],
            },
        ),
        Tool(
            name="send_appeal_update",
            description="Send an appeal decision update to a user",
            inputSchema={
                "type": "object",
                "properties": {
                    "user_id": {"type": "string"},
                    "appeal_id": {"type": "string"},
                    "case_id": {"type": "string"},
                    "decision": {
                        "type": "string",
                        "enum": ["upheld", "overturned", "escalated"],
                    },
                    "reasoning": {"type": "string"},
                },
                "required": ["user_id", "appeal_id", "case_id", "decision", "reasoning"],
            },
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: Any) -> list[TextContent]:
    """Handle tool calls."""
    global notifiers

    try:
        # Route to appropriate notifier
        if name == "send_user_notification":
            result = await notifiers.send_user_notification(**arguments)
        elif name == "send_moderator_alert":
            result = await notifiers.send_moderator_alert(**arguments)
        elif name == "log_action":
            result = await notifiers.log_action(**arguments)
        elif name == "send_decision_notification":
            result = await notifiers.send_decision_notification(**arguments)
        elif name == "send_appeal_update":
            result = await notifiers.send_appeal_update(**arguments)
        else:
            result = {"success": False, "error": f"Unknown tool: {name}"}

        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    except Exception as e:
        error_result = {"success": False, "error": str(e)}
        return [TextContent(type="text", text=json.dumps(error_result, indent=2))]


async def main():
    """Run the MCP server."""
    global db, notifiers

    # Initialize database
    db = Database()
    await db.initialize()

    # Initialize notifiers
    notifiers = Notifiers(db)

    print("🔔 CupidsShield Notifications MCP Server")
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
