#!/usr/bin/env python3
"""
CupidsShield Moderation Examples
Test content moderation with various scenarios

This script demonstrates how CupidsShield moderates different types of
content: scams, harassment, clean messages, and borderline cases.
"""

import asyncio
from dotenv import load_dotenv
from agents import run_moderation
from data.db import Database

# Load environment variables (including LangSmith)
load_dotenv()


async def moderate_content(
    content: str,
    content_type: str,
    user_id: str,
    scenario_name: str,
    expected_outcome: str
):
    """
    Moderate a piece of content and display results.

    Args:
        content: The content to moderate
        content_type: Type of content (message, bio, photo, profile)
        user_id: User ID who created the content
        scenario_name: Descriptive name for this scenario
        expected_outcome: What we expect the system to decide
    """
    print(f"\n{'='*70}")
    print(f"SCENARIO: {scenario_name}")
    print(f"{'='*70}")
    print(f"Expected Outcome: {expected_outcome}")
    print(f"\nContent Type: {content_type}")
    print(f"User ID: {user_id}")
    print(f"\n{'─'*70}")
    print("Content:")
    print(f"{'─'*70}")
    print(content)
    print(f"{'─'*70}\n")

    print("Running moderation agent...\n")

    # Run moderation
    result = await run_moderation(
        content_type=content_type,
        content=content,
        user_id=user_id
    )

    # Display results
    print(f"\n{'='*70}")
    print(f"MODERATION RESULT")
    print(f"{'='*70}")
    print(f"Case ID: {result.get('case_id')}")
    print(f"Decision: {result['decision'].upper()}")
    print(f"Confidence: {result['confidence']:.1%}")
    print(f"Violation Type: {result.get('violation_type') or 'None'}")
    print(f"Severity: {result.get('severity') or 'N/A'}")
    print(f"Risk Score: {result.get('risk_score', 0):.2f}")

    if result.get('action'):
        print(f"Action: {result['action']}")

    print(f"\nReasoning:")
    reasoning = result.get('reasoning', 'N/A')
    for line in reasoning.split('\n'):
        print(f"   {line}")

    # Check if matches expected outcome
    decision = result['decision']
    if decision in expected_outcome.lower():
        print(f"\nMatches expected outcome: {expected_outcome}")
    else:
        print(f"\nDifferent from expected: Got '{decision}', expected '{expected_outcome}'")

    print(f"{'='*70}\n")

    return result


async def main():
    """Run all moderation examples."""

    print("="*70)
    print("CUPIDSSHIELD - MODERATION EXAMPLES")
    print("="*70)
    print("\nThis script demonstrates 4 different moderation scenarios:")
    print("  1. Pig Butchering Scam (Clear Violation)")
    print("  2. Harassment with Threats (Clear Violation)")
    print("  3. Clean Dating Conversation (No Violation)")
    print("  4. Borderline Financial Discussion (Edge Case)")
    print("\n" + "="*70)

    db = Database()
    await db.initialize()

    results = []

    # EXAMPLE 1: Pig Butchering Scam - Clear Violation
    print("\n\n" + "="*70)
    print("EXAMPLE 1: Pig Butchering Scam Detection")
    print("="*70)

    result_1 = await moderate_content(
        content="""Hey beautiful! 😍 I can tell you're someone really special.
I'm a cryptocurrency trader and I've been making incredible returns - honestly
making around $10,000 daily with my trading strategy. I'd love to teach you
about it! We could both make a lot of money together.

Can we continue this conversation on WhatsApp? +1-555-0123
I have something really exciting to show you about this new trading platform
I'm using. Trust me, you won't regret it! 💰💎""",
        content_type="message",
        user_id="user_scammer_001",
        scenario_name="Obvious Pig Butchering Scam",
        expected_outcome="REJECTED (High Confidence)"
    )
    results.append(result_1)

    await asyncio.sleep(3)  # Pause between examples

    # EXAMPLE 2: Harassment with Threats - Clear Violation
    print("\n\n" + "="*70)
    print("EXAMPLE 2: Harassment with Explicit Threats")
    print("="*70)

    result_2 = await moderate_content(
        content="""You think you're so much better than me? I've been nothing but
nice to you and you just ignore me like I'm garbage. You're going to regret this.

I know where you work - I saw it on your LinkedIn. Maybe I'll show up there
since you won't respond here. You can't just ignore people like this and get
away with it. I'll make sure everyone knows what kind of person you really are.

You have 24 hours to respond or things are going to get very unpleasant for you.
Don't test me.""",
        content_type="message",
        user_id="user_harasser_001",
        scenario_name="Explicit Threats and Harassment",
        expected_outcome="REJECTED (High Confidence)"
    )
    results.append(result_2)

    await asyncio.sleep(3)

    # EXAMPLE 3: Clean Dating Conversation - No Violation
    print("\n\n" + "="*70)
    print("EXAMPLE 3: Clean, Appropriate Dating Conversation")
    print("="*70)

    result_3 = await moderate_content(
        content="""Hi! I saw we both love hiking and photography - that's awesome!
Have you explored any of the trails in the area recently? I just moved here a
few months ago and I'm still discovering all the great spots.

I noticed you mentioned you're into cooking too. What's your favorite cuisine
to make? I've been experimenting with Thai food lately and it's been fun
(though my pad thai needs some work 😄).

Would love to hear your recommendations for both hiking trails and good
restaurants around here. Hope you're having a great week!""",
        content_type="message",
        user_id="user_genuine_001",
        scenario_name="Normal Dating Conversation",
        expected_outcome="APPROVED (High Confidence)"
    )
    results.append(result_3)

    await asyncio.sleep(3)

    # EXAMPLE 4: Borderline Financial Discussion - Edge Case
    print("\n\n" + "="*70)
    print("EXAMPLE 4: Borderline Financial Discussion")
    print("="*70)

    result_4 = await moderate_content(
        content="""Hey! I've been really stressed about my finances lately. The
economy has been tough and I'm trying to figure out better ways to save and
invest my money for the future.

I've been reading about cryptocurrency and different investment strategies,
but honestly I find it all a bit overwhelming. Do you have any experience with
personal finance or investing? I'd love to hear your thoughts - not looking
for advice, just curious about other people's perspectives on managing money
in today's economy.

What do you think about the current state of things? Are you optimistic or
worried about the future?""",
        content_type="message",
        user_id="user_borderline_001",
        scenario_name="Borderline Financial Discussion",
        expected_outcome="ESCALATED (Medium Confidence - Needs Human Review)"
    )
    results.append(result_4)

    # SUMMARY
    print("\n\n" + "="*70)
    print("MODERATION SUMMARY")
    print("="*70)

    print(f"\nTotal Cases Processed: {len(results)}")
    print("\nDecision Breakdown:")
    print(f"{'─'*70}")

    decisions = {}
    for result in results:
        decision = result['decision']
        decisions[decision] = decisions.get(decision, 0) + 1

    for decision, count in sorted(decisions.items()):
        print(f"  {decision.upper()}: {count}")

    print(f"\n{'─'*70}")
    print("Detailed Results:")
    print(f"{'─'*70}\n")

    for i, result in enumerate(results, 1):
        print(f"{i}. Case {result['case_id']}")
        print(f"   Decision: {result['decision'].upper()}")
        print(f"   Confidence: {result['confidence']:.1%}")
        print(f"   Violation: {result.get('violation_type') or 'None'}")
        print(f"   Risk Score: {result.get('risk_score', 0):.2f}")
        print()

    # Get database statistics
    stats = await db.get_statistics()

    print(f"{'─'*70}")
    print("Database Statistics:")
    print(f"{'─'*70}")
    print(f"  Total Cases: {stats['total_cases']}")
    print(f"  Decisions: {stats['decisions']}")
    print(f"  Cases in Last 24h: {stats['cases_24h']}")
    print(f"  Review Queue Size: {stats.get('review_queue_size', 0)}")

    print("\n" + "="*70)
    print("All moderation examples completed!")
    print("="*70)

    print("\nNext Steps:")
    print("   1. View cases in UI: http://localhost:8000/")
    print("   2. Check review queue: http://localhost:8000/queue")
    print("   3. View metrics: http://localhost:8000/metrics")
    print("   4. Check LangSmith traces: https://smith.langchain.com/")

    print("\nKey Takeaways:")
    print("   - Clear violations (Examples 1 & 2) are auto-rejected")
    print("   - Clean content (Example 3) is auto-approved")
    print("   - Borderline cases (Example 4) are escalated to human review")
    print("   - System provides confidence scores and detailed reasoning")

    print("\n" + "="*70 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
