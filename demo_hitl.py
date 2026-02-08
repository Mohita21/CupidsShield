#!/usr/bin/env python3
"""
Demo: Human-in-the-Loop Workflow with LangGraph

This demonstrates TRUE HITL where:
1. Workflow pauses when human review is needed
2. Human provides input via API
3. Workflow resumes and completes
"""

import asyncio
from dotenv import load_dotenv
from agents.moderation_agent_hitl import ModerationAgentWithHITL
from data.db import Database
from data.vector_store import VectorStore

load_dotenv()


async def demo_hitl_workflow():
    """
    Demonstrate Human-in-the-Loop workflow.
    """
    print("=" * 70)
    print("DEMO: HUMAN-IN-THE-LOOP WORKFLOW WITH LANGGRAPH")
    print("=" * 70)
    print()

    # Initialize
    db = Database()
    await db.initialize()
    vector_store = VectorStore()
    agent = ModerationAgentWithHITL(db, vector_store)

    # Test Case: Borderline content (will trigger HITL)
    # This has scam indicators but could be legitimate
    borderline_content = """
    I can't believe you haven't responded to my last message. This is really
    frustrating because I thought we had a great connection. You're probably
    just talking to other guys and ignoring me. I've been nothing but nice
    to you and this is how you treat people? I thought you were different.
    """

    thread_id = "demo_case_001"

    state = {
        "content_id": "content_demo_001",
        "content_type": "message",
        "content": borderline_content,
        "user_id": "user_borderline_demo",
        "metadata": {},
    }

    print("STEP 1: Start workflow with borderline content")
    print("-" * 70)
    print(f"Content: {borderline_content.strip()}")
    print()

    # Run workflow - it will PAUSE at human_review node
    result = await agent.run(state, thread_id=thread_id)

    if result.get("status") == "PAUSED_FOR_HUMAN_REVIEW":
        # Add to review queue so UI can see it
        import uuid
        async with db.get_connection() as conn:
            queue_id = f"queue_{uuid.uuid4().hex[:12]}"

            # First create the case if it doesn't exist
            if not result.get("case_id"):
                case_id = await db.create_case(
                    content_type=state["content_type"],
                    content=state["content"],
                    user_id=state["user_id"],
                    risk_score=result.get("risk_score", 0),
                    decision="escalated",
                    reasoning=result.get("reasoning", "Pending human review"),
                    confidence=result.get("confidence", 0),
                    violation_type=result.get("violation_type"),
                    severity=result.get("severity"),
                    reviewed_by="agent",
                    metadata={}
                )
                result["case_id"] = case_id

            # Add to review queue using the actual case_id (not thread_id)
            await conn.execute(
                """
                INSERT INTO review_queue
                (id, case_id, priority, assigned_to, status, created_at)
                VALUES (?, ?, ?, NULL, 'pending', CURRENT_TIMESTAMP)
                """,
                (queue_id, result["case_id"], "high")
            )
            await conn.commit()

            print(f"   Added to review queue: {queue_id}")
            print(f"   View in UI: http://localhost:8000/queue")
        print()
        print("=" * 70)
        print("WORKFLOW PAUSED - WAITING FOR HUMAN MODERATOR")
        print("=" * 70)
        print()
        print(f"Agent Assessment:")
        print(f"  Violation Type: {result.get('violation_type', 'Unknown')}")
        print(f"  Confidence: {result.get('confidence', 0):.1%}")
        print(f"  Risk Score: {result.get('risk_score', 0):.2f}")
        print(f"  Reasoning: {result.get('reasoning', 'N/A')[:150]}...")
        print()

        # Simulate human moderator reviewing
        print("-" * 70)
        print("STEP 2: Moderator reviews case and makes decision")
        print("-" * 70)
        print()

        # Simulate moderator decision
        await asyncio.sleep(2)  # Simulate review time

        print("Moderator Decision: APPROVED")
        print("Moderator Reasoning: This appears to be genuine personal experience")
        print("                     sharing, not a scam attempt. User has clean history.")
        print()

        # Resume workflow with human input
        print("-" * 70)
        print("STEP 3: Resume workflow with moderator input")
        print("-" * 70)
        print()

        final_result = await agent.resume_with_human_input(
            thread_id=thread_id,
            moderator_decision="approved",
            moderator_reasoning="This appears to be genuine personal experience sharing, not a scam attempt. User has clean history and context suggests legitimate conversation.",
            moderator_id="moderator_demo_001"
        )

        print()
        print("=" * 70)
        print("FINAL RESULT")
        print("=" * 70)
        print(f"Decision: {final_result['decision']}")
        print(f"Reviewed By: {final_result.get('reviewed_by', 'Unknown')}")
        print(f"Case ID: {final_result.get('case_id', 'N/A')}")
        print(f"Notification Sent: {final_result.get('notification_sent', False)}")
        print()

    print("=" * 70)
    print("DEMO COMPLETE")
    print("=" * 70)
    print()
    print("KEY TAKEAWAYS:")
    print("1. Workflow PAUSED when confidence was low (< 70%)")
    print("2. State was CHECKPOINTED (can resume later)")
    print("3. Human provided input via resume_with_human_input()")
    print("4. Workflow RESUMED and completed with human decision")
    print("5. All steps traced and logged for audit trail")
    print()


async def demo_multiple_hitl_cases():
    """
    Demo with multiple cases showing different scenarios.
    """
    print("\n" * 2)
    print("=" * 70)
    print("DEMO: MULTIPLE HITL CASES")
    print("=" * 70)
    print()

    db = Database()
    await db.initialize()
    vector_store = VectorStore()
    agent = ModerationAgentWithHITL(db, vector_store)

    test_cases = [
        {
            "name": "Clear Scam (Auto-Reject)",
            "content": "Hey beautiful! I make $10k daily trading crypto. Let me teach you on WhatsApp!",
            "user_id": "user_scammer",
            "expected": "Auto-rejected (high confidence)"
        },
        {
            "name": "Borderline Aggressive (HITL)",
            "content": "This is really frustrating. Why the hell are you ignoring me? You're probably talking to other guys anyway.",
            "user_id": "user_borderline_aggressive_01",
            "expected": "Paused for human review"
        },
        # {
        #     "name": "Clean Content (Auto-Approve)",
        #     "content": "Hi! I love hiking too. Have you tried the trails near the lake?",
        #     "user_id": "user_clean",
        #     "expected": "Auto-approved (high confidence)"
        # },
    ]

    for i, test_case in enumerate(test_cases, 1):
        print(f"\nTest Case {i}: {test_case['name']}")
        print("-" * 70)

        # Generate a unique case_id that we'll use as BOTH thread_id and case_id
        import uuid
        case_id = f"case_{uuid.uuid4().hex[:12]}"

        state = {
            "content_id": f"content_{i}",
            "content_type": "message",
            "content": test_case["content"],
            "user_id": test_case["user_id"],
            "metadata": {},
        }

        # Use case_id as thread_id so they match for resume
        result = await agent.run(state, thread_id=case_id)

        status = result.get("status", "COMPLETED")
        decision = result.get("decision", "Unknown")
        confidence = result.get("confidence", 0)

        # DEBUG: Print full result to see what's happening
        print(f"\nDEBUG:")
        print(f"  notification_sent: {result.get('notification_sent')}")
        print(f"  case_id: {result.get('case_id')}")
        print(f"  reviewed_by: {result.get('reviewed_by')}")
        print()

        print(f"Status: {status}")
        print(f"Decision: {decision}")
        print(f"Confidence: {confidence:.1%}")
        print(f"Expected: {test_case['expected']}")

        if status == "PAUSED_FOR_HUMAN_REVIEW":
            # Add to review queue for UI visibility
            queue_id = f"queue_{uuid.uuid4().hex[:12]}"

            async with db.get_connection() as conn:
                # Create case if needed, using the SAME case_id we used as thread_id
                if not result.get("case_id"):
                    # Create case with the case_id we generated (same as thread_id)
                    await conn.execute(
                        """
                        INSERT INTO moderation_cases
                        (id, content_type, content, user_id, risk_score, decision,
                         reasoning, confidence, violation_type, severity, reviewed_by,
                         created_at, updated_at, metadata)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, '{}')
                        """,
                        (
                            case_id,  # Use our pre-generated case_id
                            state["content_type"],
                            test_case["content"],
                            test_case["user_id"],
                            result.get("risk_score", 0),
                            "escalated",
                            result.get("reasoning", ""),
                            result.get("confidence", 0),
                            result.get("violation_type"),
                            result.get("severity"),
                            "agent"
                        )
                    )
                    result["case_id"] = case_id

                # Use the case_id for both thread_id and case_id in review_queue
                await conn.execute(
                    """
                    INSERT INTO review_queue
                    (id, case_id, priority, assigned_to, status, created_at)
                    VALUES (?, ?, ?, NULL, 'pending', CURRENT_TIMESTAMP)
                    """,
                    (queue_id, case_id, "high")
                )
                await conn.commit()

            print("This case is waiting for human review")
            print(f"   Thread ID: {case_id}")
            print(f"   Case ID: {case_id}")
            print(f"   View in UI: http://localhost:8000/case/{case_id}")

        print()

    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print("High confidence cases → Processed automatically")
    print("Low confidence cases → Paused for human review")
    print("Paused workflows can be resumed at any time with human input")
    print()


if __name__ == "__main__":
    print("Running HITL Demo...")
    print()

    # Run main demo
    # asyncio.run(demo_hitl_workflow())

    # Run multiple cases demo
    asyncio.run(demo_multiple_hitl_cases())
