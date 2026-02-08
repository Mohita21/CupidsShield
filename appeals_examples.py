#!/usr/bin/env python3
"""
CupidsShield Appeals Examples
Submit appeals for rejected moderation decisions

This script demonstrates how users can appeal moderation decisions
by providing explanations and new evidence.
"""

import asyncio
from dotenv import load_dotenv
from agents import run_appeal, run_moderation
from data.db import Database

# Load environment variables (including LangSmith)
load_dotenv()


async def create_test_case(content: str, content_type: str, user_id: str) -> str:
    """Create a test moderation case that can be appealed."""
    print(f"\n{'='*70}")
    print(f"Creating test case for user: {user_id}")
    print(f"{'='*70}")
    print(f"Content: {content[:80]}...")

    result = await run_moderation(
        content_type=content_type,
        content=content,
        user_id=user_id
    )

    case_id = result.get('case_id')
    print(f"Case created: {case_id}")
    print(f"  Decision: {result['decision']}")
    print(f"  Confidence: {result['confidence']:.2f}")
    print(f"  Violation: {result.get('violation_type', 'None')}")

    return case_id


async def submit_appeal(
    case_id: str,
    user_explanation: str,
    new_evidence: str,
    appeal_name: str
):
    """Submit an appeal for a case."""
    print(f"\n{'='*70}")
    print(f"📨 APPEAL: {appeal_name}")
    print(f"{'='*70}")
    print(f"Case ID: {case_id}")
    print(f"\nUser Explanation:")
    print(f"{user_explanation}")
    print(f"\nNew Evidence:")
    print(f"{new_evidence}")
    print(f"\n{'─'*70}")
    print("Processing appeal...")
    print(f"{'─'*70}\n")

    result = await run_appeal(
        case_id=case_id,
        user_explanation=user_explanation,
        new_evidence=new_evidence
    )

    print(f"\nAppeal Result:")
    print(f"   Appeal ID: {result.get('appeal_id')}")
    print(f"   Decision: {result.get('appeal_decision')}")
    print(f"   Confidence: {result.get('appeal_confidence', 0):.2f}")
    print(f"\n   Reasoning:")
    reasoning = result.get('appeal_reasoning', 'N/A')
    for line in reasoning.split('\n'):
        print(f"   {line}")

    return result


async def main():
    """Run all appeal examples."""

    print("="*70)
    print("CUPIDSSHIELD - APPEALS EXAMPLES")
    print("="*70)
    print("\nThis script demonstrates 4 different appeal scenarios:")
    print("  1. False Positive - Crypto Discussion")
    print("  2. Remorseful Apology - Harassment")
    print("  3. Identity Dispute - Fake Profile")
    print("  4. Context Misunderstanding - Inappropriate Content")
    print("\n" + "="*70)

    db = Database()
    await db.initialize()

    # ========================================================================
    # APPEAL EXAMPLE 1: False Positive - Crypto Discussion
    # ========================================================================
    print("\n\n" + "🔵"*35)
    print("APPEAL EXAMPLE 1: False Positive - Crypto Discussion")
    print("🔵"*35)

    case_1_content = """Hi! I noticed you're interested in technology and finance.
I've been learning about cryptocurrency lately and find it fascinating from
a technical perspective. Have you looked into blockchain technology at all?
I'd love to hear your thoughts on it."""

    case_id_1 = await create_test_case(
        content=case_1_content,
        content_type="message",
        user_id="user_appeal_001"
    )

    await asyncio.sleep(2)  # Brief pause for readability

    await submit_appeal(
        case_id=case_id_1,
        user_explanation="""I was NOT trying to scam anyone! I have a genuine interest
in cryptocurrency and blockchain technology. I work as a software engineer and
I find the technical aspects fascinating. I was simply trying to have an
intellectual conversation about emerging technologies. I've never asked anyone
for money or tried to get them to invest in anything. This is a complete
misunderstanding of my intentions.""",
        new_evidence="""I have been an active member of this platform for 2 years
with zero violations. My profile clearly shows I'm a software engineer with
legitimate interests in technology. You can review my entire message history -
I've had 200+ conversations and never once solicited money or investments from
anyone. My LinkedIn profile and employment history are verifiable. I'm happy
to provide additional proof of my identity and intentions.""",
        appeal_name="Crypto False Positive"
    )

    # APPEAL EXAMPLE 2: Remorseful Apology - Harassment
    print("\n\n" + "="*70)
    print("APPEAL EXAMPLE 2: Remorseful Apology - Harassment")
    print("="*70)

    case_2_content = """I can't believe you're still ignoring me. This is so
frustrating. I thought we had a real connection but you just disappeared.
You know what, forget it. You're probably just like everyone else."""

    case_id_2 = await create_test_case(
        content=case_2_content,
        content_type="message",
        user_id="user_appeal_002"
    )

    await asyncio.sleep(2)

    await submit_appeal(
        case_id=case_id_2,
        user_explanation="""I deeply apologize for my inappropriate message. I was
having a really difficult week - I had just lost my job and was dealing with
a lot of stress. I know that's no excuse for taking my frustration out on
someone who didn't deserve it. Looking back, my message was passive-aggressive
and demanding, which was completely wrong. I understand why it was flagged.
I've learned from this mistake and will be much more mindful of how I
communicate, even when I'm frustrated. I'm genuinely sorry.""",
        new_evidence="""This is my first and only violation in 3 years on this
platform. Before this incident, I had only positive and respectful interactions
with all my matches. After this incident, I've had several successful
conversations that were completely appropriate. I've taken time to reflect on
my behavior and understand the importance of respecting others' boundaries.
I'm seeking mental health support to better manage stress and emotions.""",
        appeal_name="Harassment with Remorse"
    )

    # APPEAL EXAMPLE 3: Identity Dispute - Fake Profile
    print("\n\n" + "="*70)
    print("APPEAL EXAMPLE 3: Identity Dispute - Fake Profile")
    print("="*70)

    case_3_content = """Entrepreneur and business owner. Love traveling the world
for work and pleasure. Currently based in Miami but frequently in LA and NYC.
Looking for someone ambitious and genuine. No games, no drama - just real
connections. Let's see where this goes!"""

    case_id_3 = await create_test_case(
        content=case_3_content,
        content_type="bio",
        user_id="user_appeal_003"
    )

    await asyncio.sleep(2)

    await submit_appeal(
        case_id=case_id_3,
        user_explanation="""My profile is 100% real and this feels like
discrimination based on my profession and lifestyle. Yes, I'm an entrepreneur
and I do travel frequently for business - but that doesn't make me a scammer!
I own a legitimate e-commerce business that requires me to attend trade shows
and meet with suppliers. Just because my profile mentions success and travel
doesn't mean it's fake. This is genuinely who I am and what I do.""",
        new_evidence="""I can provide extensive verification:
1. Business registration documents for my LLC
2. LinkedIn profile with 500+ professional connections
3. Verified Instagram account showing my business and travels
4. Driver's license and passport for identity verification
5. References from business partners who can vouch for me
6. Tax returns showing legitimate business income
All my photos are real - taken during actual business trips. I'm willing to
do a video call verification or any other identity check needed.""",
        appeal_name="Fake Profile Dispute"
    )

    # ========================================================================
    # APPEAL EXAMPLE 4: Context Misunderstanding - Inappropriate Content
    # ========================================================================
    print("\n\n" + "🟣"*35)
    print("APPEAL EXAMPLE 4: Context Misunderstanding - Inappropriate")
    print("🟣"*35)

    case_4_content = """Hey! I saw on your profile you're into fitness. I've been
working out a lot lately and finally seeing some good results. Would love to
exchange workout tips sometime. Maybe we could be gym buddies if we hit it off?
What's your favorite way to stay in shape?"""

    case_id_4 = await create_test_case(
        content=case_4_content,
        content_type="message",
        user_id="user_appeal_004"
    )

    await asyncio.sleep(2)

    await submit_appeal(
        case_id=case_id_4,
        user_explanation="""I'm confused about why this was flagged as inappropriate.
I was simply trying to connect over a shared interest in fitness that was
clearly mentioned on their profile. I wasn't being sexual or suggestive - I
was talking about working out and exercise, which is a completely normal topic
of conversation. Fitness and health are legitimate interests to bond over.
If my message came across as inappropriate, that was absolutely not my
intention and I apologize for any misunderstanding.""",
        new_evidence="""Looking at my message history, I consistently talk about
fitness, nutrition, and healthy lifestyle with matches who share these interests.
I'm a certified personal trainer and genuinely passionate about health and
wellness. My profile clearly states this. I've never sent inappropriate or
sexual content to anyone on this platform. This was meant to be a friendly,
appropriate conversation starter about a mutual interest.""",
        appeal_name="Inappropriate Content Misunderstanding"
    )

    # ========================================================================
    # SUMMARY
    # ========================================================================
    print("\n\n" + "="*70)
    print("APPEALS SUMMARY")
    print("="*70)

    # Get all appeals from database
    async with db.get_connection() as conn:
        cursor = await conn.execute("""
            SELECT id, case_id, appeal_decision, appeal_confidence, created_at
            FROM appeals
            ORDER BY created_at DESC
            LIMIT 4
        """)
        appeals = await cursor.fetchall()

    print(f"\nTotal Appeals Submitted: {len(appeals)}")
    print("\nAppeal Results:")
    print(f"{'─'*70}")

    for i, appeal in enumerate(reversed(appeals), 1):
        appeal_dict = dict(appeal)
        print(f"\n{i}. Appeal ID: {appeal_dict['id']}")
        print(f"   Case ID: {appeal_dict['case_id']}")
        print(f"   Decision: {appeal_dict['appeal_decision'] or 'Pending'}")
        if appeal_dict['appeal_confidence']:
            print(f"   Confidence: {appeal_dict['appeal_confidence']:.2f}")
        print(f"   Submitted: {appeal_dict['created_at']}")

    print("\n" + "="*70)
    print("All appeals processed!")
    print("="*70)

    print("\nView Appeals in UI:")
    print("   http://localhost:8000/appeals")

    print("\nNext Steps:")
    print("   1. Review appeals in the UI")
    print("   2. Check LangSmith for complete traces")
    print("   3. See agent reasoning for each appeal decision")

    print("\n" + "="*70 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
