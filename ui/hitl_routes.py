"""
API routes for Human-in-the-Loop workflow management.

Allows moderators to:
1. View paused workflows waiting for review
2. Get workflow details with AI analysis
3. Resume workflows with human decisions
"""

from fastapi import APIRouter, HTTPException, Form
from fastapi.responses import RedirectResponse
from typing import Dict, Any, List
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from agents.moderation_agent_hitl import ModerationAgentWithHITL
from data.db import Database
from data.vector_store import VectorStore

router = APIRouter()

# Global instances (initialized in main app)
db = None
vector_store = None
hitl_agent = None


def init_hitl_routes(database: Database, vs: VectorStore):
    """Initialize HITL routes with database and vector store."""
    global db, vector_store, hitl_agent
    db = database
    vector_store = vs
    hitl_agent = ModerationAgentWithHITL(db, vector_store)


@router.get("/api/hitl/paused-workflows")
async def get_paused_workflows() -> Dict[str, Any]:
    """
    Get all workflows paused and waiting for human review.

    Returns:
        List of paused workflows with their state
    """
    # In a real implementation, you'd query the checkpoint store
    # For now, we'll query review queue with pending status

    paused_workflows = await db.get_review_queue(status="pending", limit=50)

    # Enhance with workflow state information
    enhanced = []
    for workflow in paused_workflows:
        enhanced.append({
            "thread_id": workflow.get("case_id"),
            "user_id": workflow.get("user_id"),
            "content": workflow.get("content"),
            "violation_type": workflow.get("violation_type"),
            "confidence": workflow.get("confidence"),
            "created_at": workflow.get("created_at"),
            "priority": workflow.get("priority"),
            "status": "PAUSED_FOR_HUMAN_REVIEW"
        })

    return {
        "count": len(enhanced),
        "workflows": enhanced
    }


@router.get("/api/hitl/workflow/{thread_id}")
async def get_workflow_state(thread_id: str) -> Dict[str, Any]:
    """
    Get detailed state of a paused workflow.

    Args:
        thread_id: Thread ID of the workflow

    Returns:
        Full workflow state including AI analysis
    """
    # Get case from database
    case = await db.get_case(thread_id)

    if not case:
        raise HTTPException(status_code=404, detail="Workflow not found")

    # Get user history
    user_history = await db.get_cases_by_user(case["user_id"])

    # Get similar cases
    similar_cases = vector_store.search_similar_violations(
        content=case["content"],
        n_results=5
    )

    return {
        "thread_id": thread_id,
        "status": "PAUSED_FOR_HUMAN_REVIEW",
        "case": case,
        "user_history": user_history[:10],
        "similar_cases": similar_cases,
        "ai_analysis": {
            "violation_type": case.get("violation_type"),
            "severity": case.get("severity"),
            "confidence": case.get("confidence"),
            "risk_score": case.get("risk_score"),
            "reasoning": case.get("reasoning")
        }
    }


@router.post("/api/hitl/workflow/{thread_id}/resume")
async def resume_workflow(
    thread_id: str,
    moderator_decision: str = Form(...),
    moderator_reasoning: str = Form(...),
    moderator_id: str = Form(default="moderator_001")
) -> Dict[str, Any]:
    """
    Resume a paused workflow with human decision.

    Args:
        thread_id: Thread ID of paused workflow
        moderator_decision: Human decision (approved/rejected/escalated)
        moderator_reasoning: Moderator's reasoning
        moderator_id: ID of the moderator

    Returns:
        Final workflow result
    """
    if not hitl_agent:
        raise HTTPException(status_code=500, detail="HITL agent not initialized")

    # Validate decision
    valid_decisions = ["approved", "rejected", "escalated"]
    if moderator_decision not in valid_decisions:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid decision. Must be one of: {valid_decisions}"
        )

    try:
        # Resume workflow with human input
        result = await hitl_agent.resume_with_human_input(
            thread_id=thread_id,
            moderator_decision=moderator_decision,
            moderator_reasoning=moderator_reasoning,
            moderator_id=moderator_id
        )

        # Update review queue status
        async with db.get_connection() as conn:
            await conn.execute(
                """
                UPDATE review_queue
                SET status = 'completed',
                    completed_at = CURRENT_TIMESTAMP,
                    assigned_to = ?
                WHERE case_id = ?
                """,
                (moderator_id, thread_id)
            )
            await conn.commit()

        return {
            "status": "success",
            "message": "Workflow resumed and completed",
            "result": {
                "decision": result.get("decision"),
                "case_id": result.get("case_id"),
                "notification_sent": result.get("notification_sent"),
                "reviewed_by": result.get("reviewed_by")
            }
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to resume workflow: {str(e)}"
        )


@router.post("/api/hitl/workflow/start")
async def start_hitl_workflow(
    content: str = Form(...),
    content_type: str = Form(...),
    user_id: str = Form(...)
) -> Dict[str, Any]:
    """
    Start a new HITL workflow for content moderation.

    Args:
        content: Content to moderate
        content_type: Type of content (message, bio, profile, etc.)
        user_id: User ID who created the content

    Returns:
        Workflow status (may be paused or completed)
    """
    if not hitl_agent:
        raise HTTPException(status_code=500, detail="HITL agent not initialized")

    thread_id = f"case_{user_id}_{hash(content) % 100000}"

    state = {
        "content_id": f"content_{hash(content) % 100000}",
        "content_type": content_type,
        "content": content,
        "user_id": user_id,
        "metadata": {},
    }

    try:
        result = await hitl_agent.run(state, thread_id=thread_id)

        status = result.get("status", "COMPLETED")

        if status == "PAUSED_FOR_HUMAN_REVIEW":
            # Add to review queue
            async with db.get_connection() as conn:
                import uuid
                queue_id = f"queue_{uuid.uuid4().hex[:12]}"
                await conn.execute(
                    """
                    INSERT INTO review_queue
                    (id, case_id, priority, assigned_to, status, created_at)
                    VALUES (?, ?, ?, NULL, 'pending', CURRENT_TIMESTAMP)
                    """,
                    (queue_id, thread_id, "high")
                )
                await conn.commit()

            return {
                "status": "paused",
                "message": "Workflow paused for human review",
                "thread_id": thread_id,
                "ai_analysis": {
                    "violation_type": result.get("violation_type"),
                    "confidence": result.get("confidence"),
                    "reasoning": result.get("reasoning")
                }
            }
        else:
            return {
                "status": "completed",
                "message": "Workflow completed automatically",
                "result": {
                    "decision": result.get("decision"),
                    "case_id": result.get("case_id"),
                    "confidence": result.get("confidence")
                }
            }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to start workflow: {str(e)}"
        )


@router.get("/api/hitl/stats")
async def get_hitl_stats() -> Dict[str, Any]:
    """
    Get statistics about HITL workflows.

    Returns:
        Stats about paused, completed, and total workflows
    """
    stats = await db.get_statistics()

    # Get paused workflows count
    paused_workflows = await db.get_review_queue(status="pending")

    return {
        "total_cases": stats.get("total_cases", 0),
        "paused_workflows": len(paused_workflows),
        "review_queue_size": stats.get("review_queue_size", 0),
        "decisions": stats.get("decisions", {}),
        "hitl_enabled": True
    }
