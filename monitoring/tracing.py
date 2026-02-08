"""
LangSmith tracing setup for CupidsShield.
Enables comprehensive monitoring and observability of agent workflows.
"""

import os
from functools import wraps
from typing import Any, Callable
from langsmith import traceable
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


def setup_langsmith():
    """
    Configure LangSmith tracing.

    Reads from environment variables:
    - LANGCHAIN_TRACING_V2: Enable tracing (true/false)
    - LANGCHAIN_API_KEY: LangSmith API key
    - LANGCHAIN_PROJECT: Project name
    """
    tracing_enabled = os.getenv("LANGCHAIN_TRACING_V2", "false").lower() == "true"
    api_key = os.getenv("LANGCHAIN_API_KEY")
    project = os.getenv("LANGCHAIN_PROJECT", "cupidsshield")

    if tracing_enabled and api_key:
        print(f"LangSmith tracing enabled for project: {project}")
        print(f"  View traces at: https://smith.langchain.com/")
        return True
    elif tracing_enabled and not api_key:
        print("LangSmith tracing enabled but no API key found")
        print("  Set LANGCHAIN_API_KEY in .env file")
        return False
    else:
        print("LangSmith tracing disabled")
        return False


def trace_agent_workflow(name: str = None):
    """
    Decorator to trace agent workflow execution.

    Usage:
        @trace_agent_workflow(name="moderation_workflow")
        async def run_moderation(state):
            ...
    """
    def decorator(func: Callable) -> Callable:
        workflow_name = name or func.__name__

        @traceable(
            name=workflow_name,
            run_type="chain",
            tags=["agent_workflow", "cupidsshield"]
        )
        @wraps(func)
        async def wrapper(*args, **kwargs):
            return await func(*args, **kwargs)

        return wrapper
    return decorator


def trace_node(name: str = None, node_type: str = "processing"):
    """
    Decorator to trace individual workflow nodes.

    Args:
        name: Node name (defaults to function name)
        node_type: Type of node (intake, assessment, decision, action, notification)

    Usage:
        @trace_node(name="risk_assessment", node_type="assessment")
        async def _risk_assessment_node(self, state):
            ...
    """
    def decorator(func: Callable) -> Callable:
        node_name = name or func.__name__

        @traceable(
            name=node_name,
            run_type="tool",
            tags=[f"node_{node_type}", "workflow_step"]
        )
        @wraps(func)
        async def wrapper(*args, **kwargs):
            return await func(*args, **kwargs)

        return wrapper
    return decorator


def trace_tool_call(name: str = None):
    """
    Decorator to trace MCP tool calls.

    Usage:
        @trace_tool_call(name="flag_content")
        async def flag_content(content_id, ...):
            ...
    """
    def decorator(func: Callable) -> Callable:
        tool_name = name or func.__name__

        @traceable(
            name=tool_name,
            run_type="tool",
            tags=["mcp_tool", "tool_call"]
        )
        @wraps(func)
        async def wrapper(*args, **kwargs):
            return await func(*args, **kwargs)

        return wrapper
    return decorator


def trace_db_operation(name: str = None):
    """
    Decorator to trace database operations.

    Usage:
        @trace_db_operation(name="create_case")
        async def create_case(self, ...):
            ...
    """
    def decorator(func: Callable) -> Callable:
        op_name = name or func.__name__

        @traceable(
            name=op_name,
            run_type="retriever",
            tags=["database", "data_operation"]
        )
        @wraps(func)
        async def wrapper(*args, **kwargs):
            return await func(*args, **kwargs)

        return wrapper
    return decorator


def trace_vector_search(name: str = None):
    """
    Decorator to trace vector similarity searches.

    Usage:
        @trace_vector_search(name="search_similar_violations")
        def search_similar_violations(self, content, ...):
            ...
    """
    def decorator(func: Callable) -> Callable:
        search_name = name or func.__name__

        @traceable(
            name=search_name,
            run_type="retriever",
            tags=["vector_search", "similarity_search", "chromadb"]
        )
        @wraps(func)
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)

        return wrapper
    return decorator


# Initialize on import
_tracing_enabled = setup_langsmith()


def is_tracing_enabled() -> bool:
    """Check if tracing is currently enabled."""
    return _tracing_enabled
