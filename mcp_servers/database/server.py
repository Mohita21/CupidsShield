"""
MCP Server for Database Queries.
Exposes database and vector search as MCP tools for agents.
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
from data.vector_store import VectorStore
from mcp_servers.database.queries import DatabaseQueries

# Initialize server
app = Server("cupidsshield-database")

# Global instances
db = None
vector_store = None
db_queries = None


@app.list_tools()
async def list_tools() -> list[Tool]:
    """List available database query tools."""
    return [
        Tool(
            name="query_cases",
            description="Query moderation cases with filters",
            inputSchema={
                "type": "object",
                "properties": {
                    "decision": {
                        "type": "string",
                        "enum": ["approved", "rejected", "escalated", "pending"],
                        "description": "Filter by decision",
                    },
                    "violation_type": {
                        "type": "string",
                        "description": "Filter by violation type",
                    },
                    "limit": {
                        "type": "integer",
                        "default": 100,
                        "minimum": 1,
                        "maximum": 500,
                    },
                },
            },
        ),
        Tool(
            name="get_case",
            description="Get a specific moderation case by ID",
            inputSchema={
                "type": "object",
                "properties": {
                    "case_id": {"type": "string", "description": "Case ID to retrieve"},
                },
                "required": ["case_id"],
            },
        ),
        Tool(
            name="get_appeal",
            description="Get an appeal by ID",
            inputSchema={
                "type": "object",
                "properties": {
                    "appeal_id": {"type": "string", "description": "Appeal ID to retrieve"},
                },
                "required": ["appeal_id"],
            },
        ),
        Tool(
            name="create_appeal",
            description="Create a new appeal for a moderation case",
            inputSchema={
                "type": "object",
                "properties": {
                    "case_id": {"type": "string", "description": "Case ID to appeal"},
                    "user_explanation": {
                        "type": "string",
                        "description": "User's explanation for the appeal",
                    },
                    "new_evidence": {
                        "type": "string",
                        "description": "Additional evidence provided",
                    },
                },
                "required": ["case_id", "user_explanation"],
            },
        ),
        Tool(
            name="resolve_appeal",
            description="Resolve an appeal with a decision",
            inputSchema={
                "type": "object",
                "properties": {
                    "appeal_id": {"type": "string"},
                    "decision": {
                        "type": "string",
                        "enum": ["upheld", "overturned", "escalated"],
                    },
                    "reasoning": {"type": "string"},
                    "resolved_by": {"type": "string", "default": "agent"},
                    "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                },
                "required": ["appeal_id", "decision", "reasoning"],
            },
        ),
        Tool(
            name="update_case_status",
            description="Update a case decision/status",
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
        Tool(
            name="search_similar_cases",
            description="Search for similar cases using vector similarity",
            inputSchema={
                "type": "object",
                "properties": {
                    "content": {
                        "type": "string",
                        "description": "Content to find similar cases for",
                    },
                    "violation_type": {
                        "type": "string",
                        "description": "Filter by violation type",
                    },
                    "n_results": {
                        "type": "integer",
                        "default": 5,
                        "minimum": 1,
                        "maximum": 20,
                    },
                },
                "required": ["content"],
            },
        ),
        Tool(
            name="get_review_queue",
            description="Get items from moderator review queue",
            inputSchema={
                "type": "object",
                "properties": {
                    "status": {
                        "type": "string",
                        "enum": ["pending", "in_review", "completed"],
                        "default": "pending",
                    },
                    "limit": {"type": "integer", "default": 50, "minimum": 1, "maximum": 200},
                },
            },
        ),
        Tool(
            name="get_audit_log",
            description="Get audit log entries",
            inputSchema={
                "type": "object",
                "properties": {
                    "case_id": {"type": "string", "description": "Filter by case ID"},
                    "limit": {"type": "integer", "default": 100, "minimum": 1, "maximum": 500},
                },
            },
        ),
        Tool(
            name="get_statistics",
            description="Get database and vector store statistics",
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="search_relevant_policies",
            description="Search for relevant T&S policies for content",
            inputSchema={
                "type": "object",
                "properties": {
                    "content": {"type": "string", "description": "Content to find policies for"},
                    "category": {"type": "string", "description": "Filter by policy category"},
                    "n_results": {"type": "integer", "default": 3, "minimum": 1, "maximum": 10},
                },
                "required": ["content"],
            },
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: Any) -> list[TextContent]:
    """Handle tool calls."""
    global db_queries

    try:
        # Route to appropriate query
        if name == "query_cases":
            result = await db_queries.query_cases(**arguments)
        elif name == "get_case":
            result = await db_queries.get_case(**arguments)
        elif name == "get_appeal":
            result = await db_queries.get_appeal(**arguments)
        elif name == "create_appeal":
            result = await db_queries.create_appeal(**arguments)
        elif name == "resolve_appeal":
            result = await db_queries.resolve_appeal(**arguments)
        elif name == "update_case_status":
            result = await db_queries.update_case_status(**arguments)
        elif name == "search_similar_cases":
            result = await db_queries.search_similar_cases(**arguments)
        elif name == "get_review_queue":
            result = await db_queries.get_review_queue(**arguments)
        elif name == "get_audit_log":
            result = await db_queries.get_audit_log(**arguments)
        elif name == "get_statistics":
            result = await db_queries.get_statistics()
        elif name == "search_relevant_policies":
            result = await db_queries.search_relevant_policies(**arguments)
        else:
            result = {"success": False, "error": f"Unknown tool: {name}"}

        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    except Exception as e:
        error_result = {"success": False, "error": str(e)}
        return [TextContent(type="text", text=json.dumps(error_result, indent=2))]


async def main():
    """Run the MCP server."""
    global db, vector_store, db_queries

    # Initialize database
    db = Database()
    await db.initialize()

    # Initialize vector store
    vector_store = VectorStore()
    # Load sample policies if not already loaded
    if vector_store.get_collection_stats()["policy_count"] == 0:
        vector_store.load_sample_policies()

    # Initialize query tools
    db_queries = DatabaseQueries(db, vector_store)

    print("CupidsShield Database MCP Server")
    print("=" * 50)
    print("Server ready and listening for tool calls...")
    print()
    print("Available tools:")
    tools = await list_tools()
    for tool in tools:
        print(f"  - {tool.name}: {tool.description}")
    print()

    # Print stats
    stats = await db_queries.get_statistics()
    if stats["success"]:
        print(f"Database stats: {stats['statistics']}")
    print()

    # Run server
    from mcp.server.stdio import stdio_server

    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
