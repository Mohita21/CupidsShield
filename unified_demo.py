#!/usr/bin/env python3
"""
UNIFIED CUPIDSSHIELD DEMO
Creates complete demo data for all workflows:
- Moderation cases (approved, rejected, escalated)
- Appeals (for rejected cases)
- Review queue items
- Complete LangSmith traces

Run this ONE script to populate everything for your demo!
"""

import asyncio
import uuid
from datetime import datetime, timedelta
from dotenv import load_dotenv
from agents import run_moderation, run_appeal
from data.db import Database

load_dotenv()

# ANSI color codes for pretty output
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

def print_header(text):
    print(f"\n{Colors.HEADER}{Colors.BOLD}{'='*70}")
    print(f"{text}")
    print(f"{'='*70}{Colors.ENDC}\n")

def print_section(text):
    print(f"\n{Colors.CYAN}{Colors.BOLD}{'─'*70}")
    print(f"{text}")
    print(f"{'─'*70}{Colors.ENDC}")

def print_success(text):
    print(f"{Colors.GREEN}{text}{Colors.ENDC}")

def print_warning(text):
    print(f"{Colors.YELLOW}{text}{Colors.ENDC}")

def print_info(text):
    print(f"{Colors.BLUE}{text}{Colors.ENDC}")


async def create_comprehensive_demo():
    """Create complete demo data for all workflows"""

    print_header("CUPIDSSHIELD - UNIFIED DEMO\n"
                 "Creating complete demo data")

    print_info("This demo will create:")
    print("   - Approved cases (clean content)")
    print("   - Rejected cases (clear violations)")
    print("   - Escalated cases (borderline - need human review)")
    print("   - User appeals (contesting rejections)")
    print("   - Complete LangSmith traces")
    print()

    db = Database()
    await db.initialize()

    results = {
        'approved': [],
        'rejected': [],
        'escalated': [],
        'appeals': []
    }

    # ========================================================================
    # PART 1: APPROVED CASES (Clean Content)
    # ========================================================================
    print_header("PART 1: APPROVED CASES (Clean Content)")

    approved_cases = [
        {
            "content": """Hi! I noticed we both enjoy hiking and photography. Have you
explored any of the trails in the area recently? I just moved here and would
love some recommendations.""",
            "user_id": "user_clean_001",
            "content_type": "message"
        },
        {
            "content": """Your profile caught my attention! I love that you're into
cooking too. What's your favorite cuisine to make? I've been experimenting
with Thai food lately.""",
            "user_id": "user_clean_002",
            "content_type": "message"
        },
    ]

    for i, case in enumerate(approved_cases, 1):
        print_section(f"Approved Case {i}: Normal Dating Conversation")
        result = await run_moderation(
            content_type=case['content_type'],
            content=case['content'],
            user_id=case['user_id']
        )
        results['approved'].append(result)
        print_success(f"Decision: {result['decision']} (Confidence: {result['confidence']:.0%})")

    # ========================================================================
    # PART 2: REJECTED CASES (Clear Violations)
    # ========================================================================
    print_header("PART 2: REJECTED CASES (Clear Violations)")

    rejected_cases = [
        {
            "content": """Hey beautiful! I'm a cryptocurrency trader making incredible
returns. I can teach you my investment strategy - we could both make a lot of money!
Can we continue on WhatsApp? I have something exciting to show you about this new
platform where I'm making $10k daily.""",
            "user_id": "user_scammer_001",
            "content_type": "message",
            "description": "Pig Butchering Scam"
        },
        {
            "content": """You're such an idiot for ignoring me. I know where you work
and I'm going to show up there if you keep this up. You think you're too good for me?
I'll make you regret this, you stupid bitch.""",
            "user_id": "user_harasser_001",
            "content_type": "message",
            "description": "Harassment with Threats"
        },
        {
            "content": """I'm a successful entrepreneur traveling the world. Currently
in Dubai for business. Looking for someone special to share my luxury lifestyle with.
I'm very generous with the right person. Let's connect on Telegram.""",
            "user_id": "user_scammer_002",
            "content_type": "bio",
            "description": "Fake Profile / Scam"
        },
    ]

    for i, case in enumerate(rejected_cases, 1):
        print_section(f"Rejected Case {i}: {case['description']}")
        result = await run_moderation(
            content_type=case['content_type'],
            content=case['content'],
            user_id=case['user_id']
        )
        results['rejected'].append({**result, **case})
        print_warning(f"Decision: {result['decision']} (Confidence: {result['confidence']:.0%})")
        print_info(f"Violation: {result.get('violation_type', 'N/A')}")

    # ========================================================================
    # PART 3: ESCALATED CASES (Borderline - Need Human Review)
    # ========================================================================
    print_header("PART 3: ESCALATED CASES (Borderline - Human Review Needed)")

    # Create these directly in database with controlled confidence scores
    escalated_cases = [
        {
            "content": """Hey! I've been investing in crypto and doing really well.
It's changed my financial situation. I'm not trying to sell you anything, just
sharing because you seem smart. Happy to chat about it if curious!""",
            "user_id": "user_borderline_001",
            "content_type": "message",
            "violation_type": "scams",
            "severity": "low",
            "confidence": 0.73,
            "risk_score": 0.44,
            "reasoning": "Borderline scam indicators: mentions cryptocurrency investment, claims financial success. However, no explicit ask to invest or move off-platform. Could be genuine sharing or early grooming. Confidence: 73%. ESCALATED for human judgment.",
            "description": "Borderline Crypto Discussion"
        },
        {
            "content": """I can't believe you haven't responded. This is really frustrating.
I've been nothing but nice and you just ignore me. You're probably talking to other guys
anyway. I thought you were different but I guess not.""",
            "user_id": "user_borderline_002",
            "content_type": "message",
            "violation_type": "harassment",
            "severity": "low",
            "confidence": 0.71,
            "risk_score": 0.35,
            "reasoning": "Passive-aggressive and demanding language, shows possessive behavior. Not explicit threats but concerning pattern. Could be genuine frustration or early harassment. Confidence: 71%. ESCALATED for human review.",
            "description": "Borderline Aggressive Language"
        },
        {
            "content": """Successful entrepreneur. Love traveling 🌍 Currently based in
Singapore but in LA/NY often. Looking for someone real - no games! I value honesty
and trust above everything. Let's see where this goes!""",
            "user_id": "user_borderline_003",
            "content_type": "bio",
            "violation_type": "fake_profile",
            "severity": "low",
            "confidence": 0.68,
            "risk_score": 0.34,
            "reasoning": "Generic 'successful entrepreneur' with international travel and luxury emojis. Matches scammer profile patterns but could be legitimate. Need photo verification. Confidence: 68%. ESCALATED for review with image check.",
            "description": "Suspicious Profile Pattern"
        },
        {
            "content": """I noticed you haven't replied in a few days. Just wanted to
check if everything is okay? I was really enjoying our conversation and would love
to continue getting to know you. Let me know if you're still interested!""",
            "user_id": "user_borderline_004",
            "content_type": "message",
            "violation_type": "harassment",
            "severity": "low",
            "confidence": 0.65,
            "risk_score": 0.32,
            "reasoning": "Follow-up message after no response. Could be genuine interest or early pushy behavior. Tone is polite but persistent. Confidence: 65%. ESCALATED - monitor for pattern.",
            "description": "Persistent Follow-up"
        },
    ]

    for i, case in enumerate(escalated_cases, 1):
        print_section(f"Escalated Case {i}: {case['description']}")

        # Create case directly in database
        case_id = await db.create_case(
            content_type=case['content_type'],
            content=case['content'],
            user_id=case['user_id'],
            risk_score=case['risk_score'],
            decision="escalated",
            reasoning=case['reasoning'],
            confidence=case['confidence'],
            violation_type=case['violation_type'],
            severity=case['severity'],
            reviewed_by="agent",
            metadata={}
        )

        # Add to review queue
        async with db.get_connection() as conn:
            queue_id = f"queue_{uuid.uuid4().hex[:12]}"
            await conn.execute(
                """
                INSERT INTO review_queue
                (id, case_id, priority, assigned_to, status, created_at)
                VALUES (?, ?, ?, NULL, 'pending', ?)
                """,
                (queue_id, case_id, "high", datetime.now())
            )
            await conn.commit()

        results['escalated'].append({**case, 'case_id': case_id})
        print_warning(f"Decision: escalated (Confidence: {case['confidence']:.0%})")
        print_info(f"Case ID: {case_id}")
        print_success("Added to MODERATOR REVIEW QUEUE")

    # ========================================================================
    # PART 4: USER APPEALS (Contesting Rejections)
    # ========================================================================
    print_header("PART 4: USER APPEALS (Contesting Rejected Decisions)")

    # Create PENDING appeals (not auto-processed) for moderator review
    appeals_data = [
        {
            "user_explanation": """I was NOT trying to scam anyone! I genuinely enjoy
cryptocurrency investing and was just sharing my experience. I mentioned WhatsApp
because I use it for international calls, not to scam people. This is a false positive.
I've never asked anyone for money and never will. Please review this decision.""",
            "new_evidence": "I have been on this platform for 2 years with no violations. Check my message history - I've never asked anyone for financial information or money.",
            "description": "Appeal: Scam False Positive"
        },
        {
            "user_explanation": """I know my message was inappropriate and I sincerely
apologize. I was having a really bad day and took my frustration out unfairly. This
is completely out of character for me. I understand if you want to keep the warning,
but I hope you'll reconsider the ban. I've learned my lesson.""",
            "new_evidence": "This is my first violation in 3 years on the platform. I have never sent threatening messages before or after this incident.",
            "description": "Appeal: Remorseful Apology"
        },
        {
            "user_explanation": """My profile is completely real! Just because I'm successful
and travel for work doesn't make me a scammer. These are real photos from my business trips.
This feels like discrimination based on my profession.""",
            "new_evidence": "I can provide LinkedIn verification and business registration documents to prove my identity.",
            "description": "Appeal: Fake Profile Dispute"
        },
    ]

    # Get specific cases for each appeal (match violation types)
    appeal_cases = []

    # Appeal 1: Scam false positive - needs a scam case
    async with db.get_connection() as conn:
        async with conn.execute(
            """
            SELECT id, user_id, violation_type
            FROM moderation_cases
            WHERE decision IN ('rejected', 'escalated')
            AND violation_type = 'scams'
            ORDER BY created_at DESC
            LIMIT 1
            """
        ) as cursor:
            case = await cursor.fetchone()
            if case:
                appeal_cases.append(case)

    # Appeal 2: Harassment remorse - needs a harassment case
    async with db.get_connection() as conn:
        async with conn.execute(
            """
            SELECT id, user_id, violation_type
            FROM moderation_cases
            WHERE decision IN ('rejected', 'escalated')
            AND violation_type = 'harassment'
            ORDER BY created_at DESC
            LIMIT 1
            """
        ) as cursor:
            case = await cursor.fetchone()
            if case:
                appeal_cases.append(case)

    # Appeal 3: Fake profile dispute - needs a fake_profile case
    async with db.get_connection() as conn:
        async with conn.execute(
            """
            SELECT id, user_id, violation_type
            FROM moderation_cases
            WHERE decision IN ('rejected', 'escalated')
            AND violation_type = 'fake_profile'
            ORDER BY created_at DESC
            LIMIT 1
            """
        ) as cursor:
            case = await cursor.fetchone()
            if case:
                appeal_cases.append(case)

    for i, (case, appeal_data) in enumerate(zip(appeal_cases, appeals_data), 1):
        case_dict = dict(case)
        case_id = case_dict['id']
        user_id = case_dict['user_id']

        print_section(f"Appeal {i}: {appeal_data['description']}")
        print_info(f"User: {user_id}")
        print_info(f"Original violation: {case_dict.get('violation_type', 'N/A')}")

        # Create pending appeal directly (don't run through agent)
        appeal_id = f"appeal_{uuid.uuid4().hex[:12]}"

        async with db.get_connection() as conn:
            await conn.execute(
                """
                INSERT INTO appeals
                (id, case_id, user_explanation, new_evidence, appeal_decision,
                 appeal_reasoning, appeal_confidence, resolved_by, created_at, resolved_at)
                VALUES (?, ?, ?, ?, 'pending', NULL, NULL, NULL, ?, NULL)
                """,
                (
                    appeal_id,
                    case_id,
                    appeal_data['user_explanation'],
                    appeal_data['new_evidence'],
                    datetime.now()
                )
            )
            await conn.commit()

        results['appeals'].append({
            'appeal_id': appeal_id,
            'case_id': case_id,
            'user_id': user_id,
            **appeal_data
        })
        print_success(f"Appeal created: {appeal_id}")
        print_info(f"Status: PENDING moderator review")

    # ========================================================================
    # SUMMARY
    # ========================================================================
    print_header("DEMO DATA CREATED SUCCESSFULLY!")

    print(f"{Colors.BOLD}Summary:{Colors.ENDC}")
    print(f"   Approved Cases: {len(results['approved'])}")
    print(f"   Rejected Cases: {len(results['rejected'])}")
    print(f"   Escalated Cases: {len(results['escalated'])} (in moderator queue)")
    print(f"   📨 Appeals: {len(results['appeals'])} (pending review)")

    print(f"\n{Colors.BOLD}Database Status:{Colors.ENDC}")
    stats = await db.get_statistics()
    print(f"   Total Cases: {stats['total_cases']}")
    print(f"   Pending Appeals: {stats.get('pending_appeals', 0)}")
    print(f"   Review Queue Size: {stats.get('review_queue_size', len(results['escalated']))}")

    print_header("Next Steps - Access Your Demo")

    print(f"{Colors.BOLD}1. View Dashboard:{Colors.ENDC}")
    print(f"   {Colors.CYAN}http://localhost:8000/{Colors.ENDC}")
    print(f"   See overall statistics and system status\n")

    print(f"{Colors.BOLD}2. Review Escalated Cases:{Colors.ENDC}")
    print(f"   {Colors.CYAN}http://localhost:8000/queue{Colors.ENDC}")
    print(f"   {len(results['escalated'])} cases waiting for moderator decision\n")

    print(f"{Colors.BOLD}3. Review Appeals:{Colors.ENDC}")
    print(f"   {Colors.CYAN}http://localhost:8000/appeals{Colors.ENDC}")
    print(f"   {len(results['appeals'])} user appeals pending review\n")

    print(f"{Colors.BOLD}4. View Metrics:{Colors.ENDC}")
    print(f"   {Colors.CYAN}http://localhost:8000/metrics{Colors.ENDC}")
    print(f"   Agent performance and decision breakdown\n")

    print(f"{Colors.BOLD}5. View LangSmith Traces:{Colors.ENDC}")
    print(f"   {Colors.CYAN}https://smith.langchain.com/{Colors.ENDC}")
    print(f"   Project: cupidsshield")
    print(f"   {len(results['approved']) + len(results['rejected']) + len(results['appeals'])} traces created\n")

    print_header("Demo Flow")

    print("1. Dashboard - Show system overview")
    print("2. Queue - Review an escalated case, make moderator decision")
    print("3. Appeals - Review a user appeal, show re-evaluation process")
    print("4. Metrics - Show agent performance statistics")
    print("5. LangSmith - Show complete workflow traces and observability")

    print(f"\n{Colors.GREEN}{Colors.BOLD}Your CupidsShield demo is ready!{Colors.ENDC}\n")


if __name__ == "__main__":
    asyncio.run(create_comprehensive_demo())
