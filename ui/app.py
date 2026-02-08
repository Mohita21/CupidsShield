"""
FastAPI application for Human-in-the-Loop moderation UI.
Provides review queue, case details, and decision submission for human moderators.
"""

import asyncio
from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pathlib import Path
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from data.db import Database
from data.vector_store import VectorStore

# Initialize FastAPI app
app = FastAPI(
    title="Cupid's Shield - Moderator UI",
    description="Human-in-the-Loop interface for Trust & Safety moderation with HITL support",
    version="0.2.0"
)

# Setup templates
templates_dir = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=str(templates_dir))

# Initialize database
db = Database()
vector_store = VectorStore()

# HITL agent (initialized on startup)
hitl_agent = None


@app.on_event("startup")
async def startup_event():
    """Initialize database and HITL agent on startup."""
    global hitl_agent

    await db.initialize()
    print("Database initialized")

    # Load sample policies if vector store is empty
    vs_stats = vector_store.get_collection_stats()
    if vs_stats["policy_count"] == 0:
        print("Loading sample T&S policies...")
        vector_store.load_sample_policies()
        print("Sample policies loaded")
    else:
        print(f"Vector store ready: {vs_stats['policy_count']} policies, {vs_stats['historical_cases_count']} cases")

    # Initialize HITL agent
    from agents.moderation_agent_hitl import ModerationAgentWithHITL
    hitl_agent = ModerationAgentWithHITL(db, vector_store)
    print("HITL agent initialized")

    print("CupidsShield Moderator UI running with HITL support")


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """Home page with overview."""
    stats = await db.get_statistics()
    vs_stats = vector_store.get_collection_stats()

    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "stats": stats,
            "vs_stats": vs_stats,
        }
    )


@app.get("/queue", response_class=HTMLResponse)
async def review_queue(request: Request, status: str = "pending"):
    """Review queue page."""
    queue_items = await db.get_review_queue(status=status, limit=50)

    return templates.TemplateResponse(
        "queue.html",
        {
            "request": request,
            "queue_items": queue_items,
            "status": status,
        }
    )


@app.get("/case/{case_id}", response_class=HTMLResponse)
async def case_detail(request: Request, case_id: str):
    """Case detail page."""
    case = await db.get_case(case_id)

    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    # Get user history
    user_history = await db.get_cases_by_user(case["user_id"])

    # Get similar cases
    similar_cases = vector_store.search_similar_violations(
        content=case["content"],
        violation_type=case.get("violation_type"),
        n_results=3
    )

    # Get audit log for this case
    audit_log = await db.get_audit_log(case_id=case_id, limit=20)

    return templates.TemplateResponse(
        "case_detail.html",
        {
            "request": request,
            "case": case,
            "user_history": user_history[:5],
            "similar_cases": similar_cases,
            "audit_log": audit_log,
        }
    )


@app.post("/case/{case_id}/review")
async def submit_review(
    case_id: str,
    decision: str = Form(...),
    reasoning: str = Form(...),
    moderator_id: str = Form(default="moderator_001")
):
    """Submit moderator review decision and resume HITL workflow if paused."""

    # Get the case to check if it's an escalated HITL case
    case = await db.get_case(case_id)

    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    # If this is an escalated case, try to resume the HITL workflow
    if case["decision"] == "escalated" and hitl_agent is not None:
        try:
            print(f"\n🔄 Attempting to resume HITL workflow for case {case_id}")

            # Resume the paused workflow
            final_result = await hitl_agent.resume_with_human_input(
                thread_id=case_id,
                moderator_decision=decision,
                moderator_reasoning=reasoning,
                moderator_id=moderator_id
            )

            print(f"HITL workflow resumed successfully!")
            print(f"  Final Decision: {final_result.get('decision')}")
            print(f"  Reviewed By: {final_result.get('reviewed_by')}")

        except Exception as e:
            print(f"Could not resume HITL workflow: {e}")
            print(f"   Falling back to regular decision update")

            # Fallback: Just update the case decision
            await db.update_case_decision(
                case_id=case_id,
                decision=decision,
                reasoning=reasoning,
                reviewed_by=moderator_id,
            )
    else:
        # Not an escalated case or HITL not available - just update decision
        await db.update_case_decision(
            case_id=case_id,
            decision=decision,
            reasoning=reasoning,
            reviewed_by=moderator_id,
        )

    # Complete queue item if exists
    async with db.get_connection() as conn:
        await conn.execute(
            """
            UPDATE review_queue
            SET status = 'completed', completed_at = CURRENT_TIMESTAMP,
                assigned_to = ?
            WHERE case_id = ? AND status IN ('pending', 'in_review')
            """,
            (moderator_id, case_id)
        )
        await conn.commit()

    return RedirectResponse(url="/queue", status_code=303)


@app.get("/appeals", response_class=HTMLResponse)
async def appeals_list(request: Request):
    """Appeals review page."""
    # Get pending appeals
    async with db.get_connection() as conn:
        async with conn.execute(
            """
            SELECT a.*, m.content, m.user_id, m.violation_type
            FROM appeals a
            JOIN moderation_cases m ON a.case_id = m.id
            WHERE a.appeal_decision = 'pending'
            ORDER BY a.created_at DESC
            LIMIT 50
            """,
        ) as cursor:
            rows = await cursor.fetchall()
            appeals = [dict(row) for row in rows]

    return templates.TemplateResponse(
        "appeals.html",
        {
            "request": request,
            "appeals": appeals,
        }
    )


@app.get("/appeal/{appeal_id}", response_class=HTMLResponse)
async def appeal_detail(request: Request, appeal_id: str):
    """Appeal detail page."""
    appeal = await db.get_appeal(appeal_id)

    if not appeal:
        raise HTTPException(status_code=404, detail="Appeal not found")

    # Get original case
    original_case = await db.get_case(appeal["case_id"])

    # Get user history
    user_history = await db.get_cases_by_user(original_case["user_id"])

    return templates.TemplateResponse(
        "appeal_detail.html",
        {
            "request": request,
            "appeal": appeal,
            "original_case": original_case,
            "user_history": user_history[:5],
        }
    )


@app.post("/appeal/{appeal_id}/review")
async def submit_appeal_review(
    appeal_id: str,
    decision: str = Form(...),
    reasoning: str = Form(...),
    moderator_id: str = Form(default="moderator_001")
):
    """Submit appeal review decision."""
    await db.resolve_appeal(
        appeal_id=appeal_id,
        decision=decision,
        reasoning=reasoning,
        resolved_by=moderator_id,
    )

    return RedirectResponse(url="/appeals", status_code=303)


@app.get("/metrics", response_class=HTMLResponse)
async def metrics_dashboard(request: Request):
    """Metrics dashboard."""
    stats = await db.get_statistics()
    vs_stats = vector_store.get_collection_stats()

    # Get recent cases for trend analysis
    recent_cases = await db.query_cases(limit=100)

    # Calculate metrics
    if recent_cases:
        violation_breakdown = {}
        for case in recent_cases:
            vtype = case.get("violation_type", "none")
            violation_breakdown[vtype] = violation_breakdown.get(vtype, 0) + 1

        confidence_avg = sum(c["confidence"] for c in recent_cases) / len(recent_cases)
        risk_score_avg = sum(c["risk_score"] for c in recent_cases) / len(recent_cases)
    else:
        violation_breakdown = {}
        confidence_avg = 0
        risk_score_avg = 0

    return templates.TemplateResponse(
        "metrics.html",
        {
            "request": request,
            "stats": stats,
            "vs_stats": vs_stats,
            "violation_breakdown": violation_breakdown,
            "confidence_avg": confidence_avg,
            "risk_score_avg": risk_score_avg,
        }
    )


@app.get("/api/stats")
async def api_stats():
    """API endpoint for statistics."""
    stats = await db.get_statistics()
    return stats


@app.get("/api/queue/{status}")
async def api_queue(status: str = "pending", limit: int = 50):
    """API endpoint for review queue."""
    queue_items = await db.get_review_queue(status=status, limit=limit)
    return {"queue_items": queue_items}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
