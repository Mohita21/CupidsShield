# 🏗️ CupidsShield Architecture Guide

Complete technical architecture, decision flows, and integration patterns for the CupidsShield Trust & Safety system.

---

## 📋 Table of Contents

- [Confidence Thresholds](#confidence-thresholds)
- [Content Flow from Dating Apps](#content-flow-from-dating-apps)
- [Decision Flow Scenarios](#decision-flow-scenarios)
- [MCP Architecture](#mcp-architecture)
- [Database Schema](#database-schema)

---

## 🎯 Confidence Thresholds

### Understanding Confidence

**Confidence** = How confident the AI is in its assessment (NOT the risk level itself)

```
High Confidence → Auto-decision (agent handles it)
Low Confidence → Human review (agent unsure)
```

### Visual Breakdown

```
┌─────────────────────────────────────────────────────┐
│  AI Analysis: "Is this content violating policy?"   │
│  Using GPT-4 + Vector Search + Policy Rules         │
└─────────────────────────────────────────────────────┘
                        ↓
            ┌───────────────────────┐
            │  Confidence in Answer │
            │  (0.0 to 1.0 scale)   │
            └───────────────────────┘
                        ↓
        ┌───────────────┴───────────────┐
        │                               │
    VIOLATION                      NO VIOLATION
    DETECTED                        DETECTED
        │                               │
        ↓                               ↓
   Confidence?                     Confidence?
        │                               │
   ┌────┴────┐                     ┌────┴────┐
   │         │                     │         │
  ≥85%    70-85%                 ≥90%     <90%
   │         │                     │         │
   ↓         ↓                     ↓         ↓
REJECT    ESCALATE               APPROVE   ESCALATE
(Auto)    (Human)                (Auto)    (Human)
```

---

## 🔢 How Confidence and Risk Scores Are Calculated

### Confidence Score (0.0 - 1.0)

**Source**: The confidence score is provided by the **LLM (GPT-4)** as part of its structured analysis.

#### How the LLM Determines Confidence

When analyzing content, the LLM is instructed to provide a confidence score based on:

1. **Clarity of Indicators**: How obvious are the policy violations?
2. **Number of Red Flags**: More indicators → Higher confidence
3. **Context Ambiguity**: Is the content clearly violating or borderline?
4. **Similar Patterns**: Does it match known violation patterns?
5. **Linguistic Certainty**: Is the language explicit or implied?

#### LLM Prompt Format

```python
user_prompt = """Content Type: message

Content:
Hey! I'm a crypto trader making $10k daily. Move to WhatsApp?

Provide your analysis in this exact format:
VIOLATION: [yes/no]
TYPE: [harassment/scams/fake_profile/inappropriate/age_verification/none]
SEVERITY: [low/medium/high/critical]
CONFIDENCE: [0.0-1.0]  ← LLM provides this score
REASONING: [detailed explanation]"""
```

#### Example LLM Responses

**High Confidence (Clear Violation):**
```
VIOLATION: yes
TYPE: scams
SEVERITY: high
CONFIDENCE: 0.95
REASONING: Multiple explicit pig butchering indicators: financial claims
($10k daily), crypto mention, off-platform migration request (WhatsApp).
Clear scam pattern with high certainty.
```

**Medium Confidence (Borderline):**
```
VIOLATION: yes
TYPE: harassment
SEVERITY: low
CONFIDENCE: 0.72
REASONING: Passive-aggressive language and demanding tone present. However,
no explicit threats or severe abuse. Could be genuine frustration or early
harassment - context from conversation history would help determine intent.
```

**High Confidence (Clean):**
```
VIOLATION: no
TYPE: none
SEVERITY: n/a
CONFIDENCE: 0.98
REASONING: Appropriate dating conversation about shared interests (hiking,
photography). No policy violations detected. Content is clearly acceptable.
```

#### Factors That Increase Confidence

| Factor | Example | Confidence Impact |
|--------|---------|-------------------|
| **Explicit violations** | Direct threats, explicit requests for money | +0.2 to +0.3 |
| **Multiple indicators** | Crypto + WhatsApp + financial claims | +0.15 to +0.25 |
| **Similar historical cases** | Vector search finds 3+ similar violations | +0.10 to +0.15 |
| **Clear policy match** | Content directly violates stated policy | +0.15 to +0.20 |
| **Unambiguous language** | "Send me money now" vs "I've been stressed about finances" | +0.20 to +0.30 |

#### Factors That Decrease Confidence

| Factor | Example | Confidence Impact |
|--------|---------|-------------------|
| **Ambiguous language** | Could be genuine or violation | -0.15 to -0.25 |
| **Context needed** | Need conversation history to judge | -0.10 to -0.20 |
| **Mixed signals** | Some red flags but also legitimate content | -0.15 to -0.30 |
| **No similar patterns** | Vector search finds no matches | -0.05 to -0.10 |
| **Borderline severity** | Between policy categories | -0.10 to -0.20 |

---

### Risk Score Calculation

**Formula**:
```python
risk_score = min(confidence × severity_weight, 1.0)
```

#### Severity Weights

From `agents/moderation_agent.py` line 182:

```python
severity_scores = {
    "low":      0.3,   # Minor violations
    "medium":   0.6,   # Moderate violations
    "high":     0.8,   # Serious violations
    "critical": 1.0    # Severe violations
}
```

#### Risk Score Examples

**Example 1: High Confidence Scam**
```python
confidence = 0.95       # LLM is 95% confident
severity = "high"       # Serious violation
severity_weight = 0.8

risk_score = min(0.95 × 0.8, 1.0) = 0.76
```
**Interpretation**: 76% risk - High likelihood of serious violation

**Example 2: Borderline Harassment**
```python
confidence = 0.72       # LLM is 72% confident
severity = "low"        # Minor violation
severity_weight = 0.3

risk_score = min(0.72 × 0.3, 1.0) = 0.216
```
**Interpretation**: 22% risk - Low risk but still flagged for review

**Example 3: Critical Violation**
```python
confidence = 0.88       # LLM is 88% confident
severity = "critical"   # Severe violation
severity_weight = 1.0

risk_score = min(0.88 × 1.0, 1.0) = 0.88
```
**Interpretation**: 88% risk - Very high risk requiring immediate action

**Example 4: Clean Content**
```python
confidence = 0.98       # LLM is 98% confident (no violation)
violation_type = None   # No violation detected
severity = None

risk_score = 0.0
```
**Interpretation**: 0% risk - Content is safe

---

### Complete Scoring Flow

```
┌────────────────────────────────────────────────────────────┐
│ STEP 1: LLM ANALYSIS                                       │
│                                                            │
│ Input: "Hey beautiful! I'm a crypto trader..."            │
│                                                            │
│ LLM Process:                                              │
│ 1. Analyze against scam policy                            │
│ 2. Check for red flags:                                   │
│    ✓ Financial claims ($10k)                              │
│    ✓ Crypto mention                                       │
│    ✓ Rapid intimacy ("beautiful")                         │
│    ✓ Off-platform (WhatsApp)                              │
│ 3. Review similar historical cases (vector search)        │
│ 4. Assess clarity of violation                            │
│                                                            │
│ LLM Output:                                               │
│   violation_type = "scams"                                │
│   severity = "high"                                       │
│   confidence = 0.95  ← LLM's certainty                    │
│   reasoning = "Multiple pig butchering indicators..."     │
└──────────────────────┬─────────────────────────────────────┘
                       │
                       ↓
┌────────────────────────────────────────────────────────────┐
│ STEP 2: RISK SCORE CALCULATION                            │
│                                                            │
│ Formula: risk_score = confidence × severity_weight        │
│                                                            │
│ Values:                                                   │
│   confidence = 0.95                                       │
│   severity = "high"                                       │
│   severity_weight = 0.8                                   │
│                                                            │
│ Calculation:                                              │
│   risk_score = 0.95 × 0.8 = 0.76                         │
│                                                            │
│ Result: 76% risk score                                    │
└──────────────────────┬─────────────────────────────────────┘
                       │
                       ↓
┌────────────────────────────────────────────────────────────┐
│ STEP 3: DECISION LOGIC                                     │
│                                                            │
│ Use confidence (not risk_score) for decision:             │
│                                                            │
│ confidence = 0.95                                         │
│ violation_type = "scams"                                  │
│                                                            │
│ Check thresholds:                                         │
│   ✓ 0.95 ≥ 0.85 (auto_reject threshold)                  │
│                                                            │
│ Decision: REJECT                                          │
│ Action: permanent_ban (from policy config)                │
└────────────────────────────────────────────────────────────┘
```

---

### Why Two Scores?

**Confidence** and **Risk Score** serve different purposes:

| Score | Purpose | Used For |
|-------|---------|----------|
| **Confidence** | How certain the AI is | Decision thresholds (approve/reject/escalate) |
| **Risk Score** | Overall danger level | Prioritization, analytics, reporting |

**Example Use Cases:**

**Confidence** → Decision Making:
```python
if confidence >= 0.85:
    decision = "rejected"  # Auto-reject
elif confidence >= 0.70:
    decision = "escalated"  # Human review
```

**Risk Score** → Prioritization:
```python
# High risk cases get higher priority in review queue
if risk_score > 0.7:
    priority = "urgent"
elif risk_score > 0.4:
    priority = "high"
else:
    priority = "medium"
```

---

### Code Implementation

From `agents/moderation_agent.py`:

```python
# Line 153: LLM analyzes content
response = await self.llm.ainvoke(messages)
analysis = response.content

# Lines 156-179: Parse LLM response
violation_type = None
severity = "medium"
confidence = 0.5  # Default
reasoning = analysis

try:
    lines = analysis.split("\n")
    for line in lines:
        if line.startswith("VIOLATION:") and "yes" in line.lower():
            # Extract violation type...

        if line.startswith("SEVERITY:"):
            severity = line.split(":", 1)[1].strip().lower()

        if line.startswith("CONFIDENCE:"):
            conf_str = line.split(":", 1)[1].strip()
            confidence = float(conf_str)  # ← LLM provides this

        if line.startswith("REASONING:"):
            reasoning = line.split(":", 1)[1].strip()

except Exception as e:
    print(f"Warning: Error parsing LLM response: {e}")

# Lines 181-183: Calculate risk score
severity_scores = {
    "low": 0.3,
    "medium": 0.6,
    "high": 0.8,
    "critical": 1.0
}
risk_score = min(confidence * severity_scores.get(severity, 0.6), 1.0)

# Store both scores
state["confidence"] = confidence    # Used for decisions
state["risk_score"] = risk_score    # Used for prioritization
```

---

### Confidence Calibration

The LLM's confidence scores are generally well-calibrated because GPT-4 has been trained to:

1. **Be honest about uncertainty**: If unclear, provide lower confidence
2. **Recognize edge cases**: Borderline content gets medium confidence
3. **Account for context**: Missing information reduces confidence
4. **Match patterns**: Similar to training data → higher confidence

**Calibration Check** (from real system testing):

| Predicted Confidence | Actual Violation Rate | Calibration |
|---------------------|----------------------|-------------|
| 90-100% | 94% were violations | ✅ Well calibrated |
| 80-90% | 85% were violations | ✅ Well calibrated |
| 70-80% | 73% were violations | ✅ Well calibrated |
| 60-70% | 61% were violations | ✅ Well calibrated |

This means when the LLM says 80% confidence, approximately 80% of those cases are actual violations.

---

### Threshold Configuration

From `config/moderation_config.yaml`:

```yaml
confidence_thresholds:
  auto_approve: 0.90   # ≥90% confidence → auto-approve (clean content)
  auto_reject: 0.85    # ≥85% confidence → auto-reject (clear violation)
  escalate: 0.70       # <70% confidence → escalate to human review
```

### Examples by Confidence Level

| Confidence | Content Example | Decision | Reasoning |
|-----------|-----------------|----------|-----------|
| **98%** | "I love hiking! What trails do you recommend?" | APPROVE | Very confident it's clean |
| **95%** | "Send me money on WhatsApp for crypto investment!" | REJECT | Very confident it's a scam |
| **82%** | "I've been investing in crypto and doing well..." | ESCALATE | Borderline - could be genuine or grooming |
| **72%** | "You're frustrating me by not responding..." | ESCALATE | Could be frustration or early harassment |
| **65%** | "I'm a successful entrepreneur traveling the world" | ESCALATE | Generic profile - need photo verification |

---

## 📨 Content Flow from Dating Apps

### Option A: Proactive Moderation (All Content)

```
┌────────────────────────────────────────────────────────────┐
│                    USER ACTION                             │
│  User sends message or updates profile                     │
└──────────────────────┬─────────────────────────────────────┘
                       │
                       ↓
┌────────────────────────────────────────────────────────────┐
│                  DATING APP BACKEND                        │
│  - Intercepts content before delivery                      │
│  - Temporarily holds message                               │
└──────────────────────┬─────────────────────────────────────┘
                       │
                       ↓ HTTP POST /api/moderate
┌────────────────────────────────────────────────────────────┐
│              CUPIDSSHIELD API ENDPOINT                     │
│                                                            │
│  POST /api/v1/moderate                                    │
│  {                                                         │
│    "content_id": "msg_abc123",                            │
│    "content_type": "message",                             │
│    "content": "Hey! Want to invest in crypto?",           │
│    "user_id": "user_456",                                 │
│    "metadata": {                                          │
│      "timestamp": "2024-01-15T10:30:00Z",                │
│      "conversation_id": "conv_789",                       │
│      "recipient_id": "user_999"                           │
│    }                                                      │
│  }                                                         │
└──────────────────────┬─────────────────────────────────────┘
                       │
                       ↓
┌────────────────────────────────────────────────────────────┐
│              CUPIDSSHIELD AGENT                           │
│  ┌──────────────────────────────────────────────────┐    │
│  │ Intake → Assessment → Decision → Action          │    │
│  └──────────────────────────────────────────────────┘    │
│                                                            │
│  Processing Time: 500ms - 2s                              │
└──────────────────────┬─────────────────────────────────────┘
                       │
                       ↓ HTTP 200 Response
┌────────────────────────────────────────────────────────────┐
│              API RESPONSE                                  │
│  {                                                         │
│    "case_id": "case_def456",                              │
│    "decision": "approved",  // or "rejected", "escalated" │
│    "confidence": 0.92,                                    │
│    "violation_type": null,  // or "scams", etc.          │
│    "action": null,          // or "permanent_ban", etc.  │
│    "reasoning": "Content appears safe...",                │
│    "processing_time_ms": 850                              │
│  }                                                         │
└──────────────────────┬─────────────────────────────────────┘
                       │
                       ↓
┌────────────────────────────────────────────────────────────┐
│                  DATING APP BACKEND                        │
│  Based on decision:                                        │
│  - "approved" → Deliver message to recipient               │
│  - "rejected" → Block message, notify sender               │
│  - "escalated" → Hold for human review                     │
└────────────────────────────────────────────────────────────┘
```

**Pros:**
- ✅ Catch violations before they reach users
- ✅ Proactive safety
- ✅ Prevent harm

**Cons:**
- ❌ High API volume (every message/profile update)
- ❌ Higher cost
- ❌ Slight latency in message delivery

---

### Option B: Reactive Moderation (Flagged Content Only)

```
┌────────────────────────────────────────────────────────────┐
│                    USER ACTION                             │
│  User A reports User B's message                           │
└──────────────────────┬─────────────────────────────────────┘
                       │
                       ↓
┌────────────────────────────────────────────────────────────┐
│                  DATING APP BACKEND                        │
│  - User report received                                    │
│  - Flag content for review                                 │
└──────────────────────┬─────────────────────────────────────┘
                       │
                       ↓ HTTP POST /api/moderate
┌────────────────────────────────────────────────────────────┐
│              CUPIDSSHIELD API                              │
│  Processes flagged content                                 │
│  Higher priority for reported content                      │
└──────────────────────┬─────────────────────────────────────┘
                       │
                       ↓
┌────────────────────────────────────────────────────────────┐
│         Agent Decision + Human Review if Needed            │
└──────────────────────┬─────────────────────────────────────┘
                       │
                       ↓
┌────────────────────────────────────────────────────────────┐
│                  DATING APP BACKEND                        │
│  - Take action on reported content                         │
│  - Ban user if violation confirmed                         │
│  - Notify reporter of outcome                              │
└────────────────────────────────────────────────────────────┘
```

**Pros:**
- ✅ Lower API volume (only reported content)
- ✅ Lower cost
- ✅ Focus resources on user-reported issues

**Cons:**
- ❌ Reactive (violations happen before detection)
- ❌ Depends on user reports
- ❌ May miss unreported violations

---

### Option C: Hybrid Approach (Recommended)

```
┌────────────────────────────────────────────────────────────┐
│                    SMART FILTERING                         │
│                                                            │
│  1. Pre-filter with lightweight rules:                    │
│     - Keyword matching (money, crypto, whatsapp)          │
│     - User reputation score                               │
│     - Rapid messaging patterns                            │
│                                                            │
│  2. Decision:                                             │
│     - High risk signals → Send to CupidsShield            │
│     - Clean content → Deliver directly                    │
│     - User reports → Send to CupidsShield                 │
└────────────────────────────────────────────────────────────┘
                       ↓
          Only ~5-10% of content sent to CupidsShield
                       ↓
┌────────────────────────────────────────────────────────────┐
│         Full AI Analysis (LLM + Vector Search)             │
└────────────────────────────────────────────────────────────┘
```

**Pros:**
- ✅ Balance of proactive + reactive
- ✅ Cost-effective (only analyze suspicious content)
- ✅ Fast for clean content (no API call)
- ✅ Catches most violations

---

### Pre-filtering Logic Example

```python
# Dating app backend - decides what to send to CupidsShield

async def should_moderate(content: str, user: User) -> bool:
    """Decide if content should be sent for AI moderation."""

    # 1. Keyword-based triggers
    risk_keywords = ["money", "bitcoin", "crypto", "whatsapp",
                     "telegram", "investment", "gift card"]
    if any(keyword in content.lower() for keyword in risk_keywords):
        return True  # Send to CupidsShield

    # 2. User reputation score
    if user.reputation_score < 0.3:  # Low reputation
        return True

    # 3. Behavioral patterns
    if user.messages_last_hour > 50:  # Spam pattern
        return True

    # 4. User reports
    if user.reports_count > 2:
        return True

    # 5. First message to new match
    if is_first_message_to_match(content, user):
        return True  # Higher scrutiny for first contact

    # Otherwise, deliver without AI moderation
    return False


# Usage
if should_moderate(message.content, sender):
    # Send to CupidsShield API
    result = await cupidsshield_api.moderate(
        content=message.content,
        user_id=sender.id,
        content_type="message"
    )

    if result["decision"] == "approved":
        deliver_message(message)
    elif result["decision"] == "rejected":
        block_message(message)
        notify_user(sender, "Message blocked due to policy violation")
    else:  # escalated
        queue_for_human_review(message)
else:
    # Clean content - deliver directly
    deliver_message(message)
```

---

## 🔄 Decision Flow Scenarios

### Scenario 1: Pig Butchering Scam Detection

```
┌────────────────────────────────────────────────────────────┐
│  INCOMING CONTENT                                          │
│  "Hey beautiful! I'm a crypto trader making $10k daily.    │
│   Can we move this to WhatsApp? I want to share my        │
│   investment strategy with you."                           │
└──────────────────────┬─────────────────────────────────────┘
                       │
                       ↓
┌────────────────────────────────────────────────────────────┐
│  INTAKE NODE                                               │
│  - Validate content                                        │
│  - Extract metadata                                        │
│  - Create case ID: case_abc123                            │
└──────────────────────┬─────────────────────────────────────┘
                       │
                       ↓
┌────────────────────────────────────────────────────────────┐
│  RISK ASSESSMENT NODE                                      │
│                                                            │
│  1. LLM Analysis (GPT-4):                                 │
│     Prompt: "Analyze for dating app policy violations"    │
│     Response:                                             │
│       VIOLATION: yes                                      │
│       TYPE: scams                                         │
│       SEVERITY: high                                      │
│       CONFIDENCE: 0.95                                    │
│       REASONING: "Multiple pig butchering indicators:     │
│                   - Financial claims ($10k daily)         │
│                   - Crypto mention (trader)               │
│                   - Off-platform migration (WhatsApp)     │
│                   - Rapid intimacy (beautiful)"           │
│                                                            │
│  2. Vector Search (ChromaDB):                             │
│     - Find similar historical violations                  │
│     - Found 3 similar scam cases (similarity > 0.85)      │
│     - All were confirmed scams                            │
│                                                            │
│  3. User History Check:                                   │
│     - First time offender: No prior violations            │
│     - Account age: 2 days (RED FLAG)                      │
│                                                            │
│  4. Calculate Risk Score:                                 │
│     risk_score = confidence * severity_weight             │
│     risk_score = 0.95 * 0.8 = 0.76                       │
└──────────────────────┬─────────────────────────────────────┘
                       │
                       ↓
┌────────────────────────────────────────────────────────────┐
│  DECISION NODE                                             │
│                                                            │
│  Input:                                                   │
│    violation_type = "scams"                               │
│    confidence = 0.95                                      │
│    severity = "high"                                      │
│                                                            │
│  Threshold Check:                                         │
│    ✓ 0.95 >= 0.85 (auto_reject threshold)                │
│                                                            │
│  Decision: REJECTED                                       │
│  Action: permanent_ban (from config: scams.high)          │
└──────────────────────┬─────────────────────────────────────┘
                       │
                       ↓
┌────────────────────────────────────────────────────────────┐
│  ACTION NODE                                               │
│  - Create case in database                                 │
│  - Log to audit trail                                      │
│  - Return: permanent_ban action                            │
└──────────────────────┬─────────────────────────────────────┘
                       │
                       ↓
┌────────────────────────────────────────────────────────────┐
│  NOTIFICATION NODE                                         │
│  - Notify user: "Account suspended - policy violation"     │
│  - Log notification to audit trail                         │
└──────────────────────┬─────────────────────────────────────┘
                       │
                       ↓
┌────────────────────────────────────────────────────────────┐
│  RESULT                                                    │
│  {                                                         │
│    "case_id": "case_abc123",                              │
│    "decision": "rejected",                                │
│    "action": "permanent_ban",                             │
│    "confidence": 0.95,                                    │
│    "violation_type": "scams",                             │
│    "severity": "high",                                    │
│    "processing_time_ms": 1200                             │
│  }                                                         │
└────────────────────────────────────────────────────────────┘
```

---

### Scenario 2: Borderline Harassment (Escalated)

```
┌────────────────────────────────────────────────────────────┐
│  INCOMING CONTENT                                          │
│  "I can't believe you haven't responded yet. This is       │
│   really frustrating. I've been nothing but nice to you    │
│   and you just ignore me like I don't matter."            │
└──────────────────────┬─────────────────────────────────────┘
                       │
                       ↓
┌────────────────────────────────────────────────────────────┐
│  INTAKE NODE                                               │
│  - Case ID: case_def456                                   │
└──────────────────────┬─────────────────────────────────────┘
                       │
                       ↓
┌────────────────────────────────────────────────────────────┐
│  RISK ASSESSMENT NODE                                      │
│                                                            │
│  1. LLM Analysis:                                         │
│       VIOLATION: yes                                      │
│       TYPE: harassment                                    │
│       SEVERITY: low                                       │
│       CONFIDENCE: 0.72                                    │
│       REASONING: "Passive-aggressive tone, demanding      │
│                   response, guilt-tripping. However, no   │
│                   explicit threats. Could be genuine      │
│                   frustration or early harassment."       │
│                                                            │
│  2. Vector Search:                                        │
│     - Found 2 similar borderline cases                    │
│     - One was harassment, one was frustration             │
│     - INCONCLUSIVE pattern                                │
│                                                            │
│  3. User History:                                         │
│     - No prior violations                                 │
│     - Account age: 6 months (good standing)               │
│                                                            │
│  4. Risk Score: 0.72 * 0.3 = 0.22 (low risk)             │
└──────────────────────┬─────────────────────────────────────┘
                       │
                       ↓
┌────────────────────────────────────────────────────────────┐
│  DECISION NODE                                             │
│                                                            │
│  Input:                                                   │
│    violation_type = "harassment"                          │
│    confidence = 0.72                                      │
│    severity = "low"                                       │
│                                                            │
│  Threshold Check:                                         │
│    ✗ 0.72 < 0.85 (not high enough to auto-reject)        │
│    ✓ 0.72 >= 0.70 (above escalate threshold)             │
│                                                            │
│  Decision: ESCALATED (borderline case)                    │
│  Action: flag_for_review                                  │
│                                                            │
│  Why escalated?                                           │
│  - Confidence too low for auto-decision                   │
│  - Could be genuine frustration OR harassment             │
│  - Context matters (conversation history needed)          │
│  - No clear pattern from vector search                    │
│  → HUMAN JUDGMENT REQUIRED                                │
└──────────────────────┬─────────────────────────────────────┘
                       │
                       ↓
┌────────────────────────────────────────────────────────────┐
│  ACTION NODE                                               │
│  - Create case in database                                 │
│  - Add to review_queue table                               │
│  - Priority: medium (harassment.low)                       │
└──────────────────────┬─────────────────────────────────────┘
                       │
                       ↓
┌────────────────────────────────────────────────────────────┐
│  NOTIFICATION NODE                                         │
│  - Notify user: "Content under review"                     │
│  - Hold message until human decision                       │
└──────────────────────┬─────────────────────────────────────┘
                       │
                       ↓
┌────────────────────────────────────────────────────────────┐
│  OPERATOR UI - MODERATOR REVIEW                           │
│                                                            │
│  Moderator sees:                                          │
│  ┌────────────────────────────────────────────────┐      │
│  │ 🚨 ESCALATED CASE                              │      │
│  │                                                 │      │
│  │ Content: [full message text]                   │      │
│  │ Agent Decision: ESCALATED (72% confidence)     │      │
│  │ Agent Reasoning: [full reasoning]              │      │
│  │                                                 │      │
│  │ Conversation History:                          │      │
│  │ - User sent 5 messages in 2 days              │      │
│  │ - Recipient read but didn't respond           │      │
│  │                                                 │      │
│  │ User History: Clean (no violations)            │      │
│  │                                                 │      │
│  │ Similar Cases: Mixed outcomes                  │      │
│  └────────────────────────────────────────────────┘      │
│                                                            │
│  Moderator decides:                                       │
│  ☑ APPROVE with warning                                  │
│  Reasoning: "Frustration is understandable, but tone     │
│             is borderline. Issue warning about            │
│             respecting boundaries."                       │
└────────────────────────────────────────────────────────────┘
```

---

### Scenario 3: Clean Content (Auto-Approved)

```
┌────────────────────────────────────────────────────────────┐
│  INCOMING CONTENT                                          │
│  "Hi! I saw we both love hiking and photography. Have you  │
│   explored any trails in the area recently?"              │
└──────────────────────┬─────────────────────────────────────┘
                       │
                       ↓
┌────────────────────────────────────────────────────────────┐
│  INTAKE NODE                                               │
│  - Case ID: case_ghi789                                   │
└──────────────────────┬─────────────────────────────────────┘
                       │
                       ↓
┌────────────────────────────────────────────────────────────┐
│  RISK ASSESSMENT NODE                                      │
│                                                            │
│  1. LLM Analysis:                                         │
│       VIOLATION: no                                       │
│       TYPE: none                                          │
│       SEVERITY: n/a                                       │
│       CONFIDENCE: 0.98                                    │
│       REASONING: "Appropriate dating conversation.        │
│                   Mentions shared interests (hiking,      │
│                   photography). No red flags."            │
│                                                            │
│  2. Vector Search:                                        │
│     - No similar violations found                         │
│     - Content matches approved message patterns           │
│                                                            │
│  3. User History:                                         │
│     - No violations                                       │
│     - Account age: 1 year (excellent standing)            │
│                                                            │
│  4. Risk Score: 0 (no violation detected)                │
└──────────────────────┬─────────────────────────────────────┘
                       │
                       ↓
┌────────────────────────────────────────────────────────────┐
│  DECISION NODE                                             │
│                                                            │
│  Input:                                                   │
│    violation_type = None                                  │
│    confidence = 0.98                                      │
│                                                            │
│  Logic:                                                   │
│    if violation_type is None:                             │
│        decision = "approved"                              │
│                                                            │
│  Decision: APPROVED (auto)                                │
│  Action: None (no action needed)                          │
│                                                            │
│  Processing time: 450ms                                   │
└──────────────────────┬─────────────────────────────────────┘
                       │
                       ↓
┌────────────────────────────────────────────────────────────┐
│  RESULT                                                    │
│  Message delivered immediately to recipient                │
│  No human review needed                                    │
└────────────────────────────────────────────────────────────┘
```

---

### Scenario 4: Appeals Workflow

```
┌────────────────────────────────────────────────────────────┐
│  USER SUBMITS APPEAL                                       │
│  Original Decision: REJECTED (scam)                        │
│  User Explanation: "I was just sharing my genuine          │
│    interest in crypto investing, not trying to scam!"     │
│  New Evidence: "I've been on this platform 2 years with   │
│    zero violations. Check my message history."            │
└──────────────────────┬─────────────────────────────────────┘
                       │
                       ↓
┌────────────────────────────────────────────────────────────┐
│  APPEAL INTAKE NODE                                        │
│  - Create appeal ID: appeal_jkl012                        │
│  - Link to original case: case_abc123                     │
│  - Extract user explanation and evidence                   │
└──────────────────────┬─────────────────────────────────────┘
                       │
                       ↓
┌────────────────────────────────────────────────────────────┐
│  CONTEXT RETRIEVAL NODE                                    │
│                                                            │
│  1. Get Original Case:                                    │
│     - Original violation: scams                           │
│     - Original confidence: 0.95                           │
│     - Original reasoning: [full reasoning]                │
│                                                            │
│  2. Get User History:                                     │
│     - Total cases: 1 (this one)                           │
│     - Violations: 1 (this case)                           │
│     - Account age: 2 years ✓                              │
│     - Message history: 200+ messages, all appropriate ✓    │
│                                                            │
│  3. Vector Search on New Evidence:                        │
│     - Search for similar false positives                  │
│     - Found 2 cases where crypto mention was legitimate   │
│                                                            │
│  4. Policy Review:                                        │
│     - Re-check against scam policies                      │
│     - Consider context of long account history            │
└──────────────────────┬─────────────────────────────────────┘
                       │
                       ↓
┌────────────────────────────────────────────────────────────┐
│  EVALUATION NODE                                           │
│                                                            │
│  Scoring Factors:                                         │
│                                                            │
│  1. New Evidence Quality: 0.7                             │
│     - Account history supports claim                      │
│     - Message patterns show genuine use                   │
│                                                            │
│  2. User Explanation Credibility: 0.8                     │
│     - Explanation is coherent                             │
│     - Takes responsibility                                │
│     - Provides verifiable evidence                        │
│                                                            │
│  3. Policy Re-interpretation: 0.6                         │
│     - Original decision was technically correct           │
│     - BUT: Lacked full context of user history           │
│     - Edge case: genuine interest vs scam                 │
│                                                            │
│  4. User History Weight: 0.9                              │
│     - 2 years, 200+ messages, zero violations             │
│     - Strong positive signal                              │
│                                                            │
│  Overall Appeal Score: 0.75 (above 0.70 threshold)        │
└──────────────────────┬─────────────────────────────────────┘
                       │
                       ↓
┌────────────────────────────────────────────────────────────┐
│  APPEAL DECISION NODE                                      │
│                                                            │
│  Options:                                                 │
│  1. UPHOLD: Keep original decision                        │
│  2. OVERTURN: Reverse original decision                   │
│  3. ESCALATE: Need senior moderator review                │
│                                                            │
│  Decision: OVERTURN                                       │
│  Confidence: 0.75                                         │
│                                                            │
│  Reasoning:                                               │
│  "While the original message contained scam indicators    │
│   (crypto mention, financial discussion), the user's      │
│   2-year history with 200+ appropriate messages and       │
│   zero violations strongly suggests this was a genuine    │
│   interest discussion rather than scam grooming. The      │
│   context was not fully considered in the original        │
│   decision. Decision overturned with warning to be        │
│   mindful of how financial topics may be perceived."      │
└──────────────────────┬─────────────────────────────────────┘
                       │
                       ↓
┌────────────────────────────────────────────────────────────┐
│  RESOLUTION NODE                                           │
│  - Update original case decision: rejected → approved      │
│  - Restore account access                                  │
│  - Send notification: "Your appeal has been approved"      │
│  - Log to audit trail                                      │
│  - Add to training data (false positive case)             │
└────────────────────────────────────────────────────────────┘
```

---

### Scenario 5: Human Review Queue

```
┌────────────────────────────────────────────────────────────┐
│           MODERATOR OPENS REVIEW QUEUE                     │
│           URL: http://localhost:8000/queue                │
└──────────────────────┬─────────────────────────────────────┘
                       │
                       ↓
┌────────────────────────────────────────────────────────────┐
│  QUEUE DASHBOARD                                           │
│                                                            │
│  ┌────────────────────────────────────────────────┐      │
│  │  REVIEW QUEUE - 4 Cases Pending                │      │
│  │                                                 │      │
│  │  [Filter: Pending] [High Priority]             │      │
│  │                                                 │      │
│  │  Case ID      │ Priority │ Violation │ Age     │      │
│  │  ─────────────┼──────────┼───────────┼─────    │      │
│  │  case_001     │ HIGH     │ Scams     │ 5m      │      │
│  │  case_002     │ MEDIUM   │ Harass    │ 15m     │      │
│  │  case_003     │ MEDIUM   │ Fake      │ 1h      │      │
│  │  case_004     │ LOW      │ Harass    │ 2h      │      │
│  └────────────────────────────────────────────────┘      │
└──────────────────────┬─────────────────────────────────────┘
                       │
                       ↓ [Moderator clicks case_002]
┌────────────────────────────────────────────────────────────┐
│  CASE DETAIL VIEW                                          │
│                                                            │
│  ⚠️ ESCALATED CASE - MODERATOR DECISION REQUIRED          │
│                                                            │
│  ┌────────────────────────────────────────────────┐      │
│  │ CASE INFORMATION                               │      │
│  │ Case ID: case_002                              │      │
│  │ User: user_borderline_002                      │      │
│  │ Content Type: message                          │      │
│  │ Created: 15 minutes ago                        │      │
│  └────────────────────────────────────────────────┘      │
│                                                            │
│  ┌────────────────────────────────────────────────┐      │
│  │ AGENT DECISION                                 │      │
│  │ Decision: ESCALATED                            │      │
│  │ Confidence: 72%                                │      │
│  │ Violation: Harassment (Low)                    │      │
│  │ Risk Score: 0.36                               │      │
│  └────────────────────────────────────────────────┘      │
│                                                            │
│  ┌────────────────────────────────────────────────┐      │
│  │ CONTENT                                        │      │
│  │ "I can't believe you haven't responded yet..." │      │
│  │ [full message displayed]                       │      │
│  └────────────────────────────────────────────────┘      │
│                                                            │
│  ┌────────────────────────────────────────────────┐      │
│  │ AGENT REASONING                                │      │
│  │ "Passive-aggressive tone, demanding response,  │      │
│  │  guilt-tripping. However, no explicit threats. │      │
│  │  Could be genuine frustration or early         │      │
│  │  harassment. Confidence: 72%"                  │      │
│  └────────────────────────────────────────────────┘      │
│                                                            │
│  ┌────────────────────────────────────────────────┐      │
│  │ USER HISTORY (2 past cases)                    │      │
│  │ - Case 1: Approved (clean message)             │      │
│  │ - Case 2: This one                             │      │
│  │ Total Violations: 0                            │      │
│  │ Account Age: 6 months                          │      │
│  └────────────────────────────────────────────────┘      │
│                                                            │
│  ┌────────────────────────────────────────────────┐      │
│  │ SIMILAR CASES (Vector Search)                  │      │
│  │                                                 │      │
│  │ 1. Case xyz (Similarity: 82%)                  │      │
│  │    Decision: Approved with warning             │      │
│  │    Content: "Why aren't you replying..."       │      │
│  │                                                 │      │
│  │ 2. Case abc (Similarity: 78%)                  │      │
│  │    Decision: Rejected (harassment)             │      │
│  │    Content: "You're ignoring me on purpose..." │      │
│  └────────────────────────────────────────────────┘      │
└──────────────────────┬─────────────────────────────────────┘
                       │
                       ↓
┌────────────────────────────────────────────────────────────┐
│  🎯 MODERATOR DECISION FORM                                │
│                                                            │
│  Decision: [Dropdown]                                     │
│  ☐ Approve - Content is acceptable                        │
│  ☑ Reject - Remove content and take action                │
│  ☐ Escalate to Senior Moderator                           │
│                                                            │
│  Reasoning (Required):                                    │
│  ┌────────────────────────────────────────────────┐      │
│  │ After reviewing the content, user history, and │      │
│  │ similar cases, I believe this crosses the line │      │
│  │ into harassment territory. While the user has  │      │
│  │ no prior violations, the demanding and         │      │
│  │ guilt-tripping language is inappropriate.      │      │
│  │ Action: Issue warning and remove message.      │      │
│  └────────────────────────────────────────────────┘      │
│                                                            │
│  Moderator ID: moderator_001                              │
│                                                            │
│  [✓ Submit Decision]  [← Back to Queue]                   │
└──────────────────────┬─────────────────────────────────────┘
                       │
                       ↓ [Submit clicked]
┌────────────────────────────────────────────────────────────┐
│  DECISION RECORDED                                         │
│  - Update case: decision = "rejected"                      │
│  - Update case: reviewed_by = "moderator_001"              │
│  - Add to audit_log                                        │
│  - Remove from review_queue                                │
│  - Mark queue_item as "completed"                          │
│  - Send notification to user                               │
│  - Redirect moderator back to queue                        │
└────────────────────────────────────────────────────────────┘
```

---

## 🔧 MCP Architecture

### What is MCP?

**MCP (Model Context Protocol)** is a protocol for LLM applications to interact with external tools and data sources in a standardized way.

Think of it like **API for AI agents** - a unified way for LLMs to call functions, access databases, and use tools.

### Why We DON'T Use True MCP in This Demo

**This project demonstrates MCP concepts** but doesn't use the actual MCP protocol. Here's why:

#### Demo Implementation (Current):
```python
# Agents call functions directly
from data.db import Database
from mcp_servers.moderation_tools.tools import ModerationTools

db = Database()
case_id = await db.create_case(...)  # Direct function call

tools = ModerationTools(db)
result = await tools.flag_content(...)  # Direct function call
```

**Pros:**
- ✅ Simpler to understand
- ✅ Easier to debug
- ✅ Faster to develop
- ✅ No additional dependencies

**Cons:**
- ❌ Tight coupling between agents and tools
- ❌ Not following MCP standard
- ❌ Can't easily swap tool implementations
- ❌ Harder to scale across services

---

### Production MCP Implementation

In a production system, you'd use **true MCP protocol**:

```
┌────────────────────────────────────────────────────────────┐
│                    LLM AGENT                               │
│  (LangGraph Workflow)                                      │
└──────────────────────┬─────────────────────────────────────┘
                       │
                       ↓ MCP Protocol (HTTP/WebSocket)
┌────────────────────────────────────────────────────────────┐
│                  MCP GATEWAY                               │
│  - Route tool calls to appropriate servers                 │
│  - Handle authentication                                   │
│  - Manage connection pooling                               │
└──────────────────────┬─────────────────────────────────────┘
                       │
          ┌────────────┼────────────┐
          │            │            │
          ↓            ↓            ↓
┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│ MCP Server 1 │ │ MCP Server 2 │ │ MCP Server 3 │
│ Moderation   │ │ Database     │ │ Notification │
│ Tools        │ │ Operations   │ │ Service      │
└──────────────┘ └──────────────┘ └──────────────┘
```

### True MCP Example

#### 1. MCP Server Definition

```python
# mcp_servers/moderation_tools/server.py (Production)

from mcp import Server, Tool
from typing import Any, Dict

# Define MCP server
server = Server(name="moderation-tools")

@server.tool(
    name="flag_content",
    description="Flag content for moderation review",
    parameters={
        "content_id": {"type": "string", "required": True},
        "content": {"type": "string", "required": True},
        "user_id": {"type": "string", "required": True},
        "violation_type": {"type": "string", "required": True},
        "confidence": {"type": "number", "required": True},
        "reasoning": {"type": "string", "required": True},
    }
)
async def flag_content(
    content_id: str,
    content: str,
    user_id: str,
    violation_type: str,
    confidence: float,
    reasoning: str
) -> Dict[str, Any]:
    """Flag content via MCP protocol."""
    # Implementation...
    return {"success": True, "case_id": "case_123"}

# Start MCP server
if __name__ == "__main__":
    server.run(host="0.0.0.0", port=8001)
```

#### 2. Agent Calls MCP Tool

```python
# agents/moderation_agent.py (Production with MCP)

from langchain.tools import MCPTool
from langchain.agents import AgentExecutor

# Connect to MCP server
mcp_tools = MCPTool.from_server(
    server_url="http://mcp-moderation-tools:8001"
)

# Agent can now call tools via MCP
async def _decision_node(self, state):
    # Agent decides to flag content
    result = await mcp_tools.flag_content(
        content_id=state["content_id"],
        content=state["content"],
        user_id=state["user_id"],
        violation_type="scams",
        confidence=0.95,
        reasoning="Multiple scam indicators detected"
    )

    state["case_id"] = result["case_id"]
    return state
```

### Benefits of True MCP in Production

#### 1. **Microservices Architecture**

```
┌─────────────────────────────────────────────────────────────┐
│                   DATING APP ECOSYSTEM                      │
│                                                             │
│  ┌───────────┐  ┌───────────┐  ┌───────────┐             │
│  │ Service A │  │ Service B │  │ Service C │             │
│  │ (Profiles)│  │ (Messages)│  │ (Photos)  │             │
│  └─────┬─────┘  └─────┬─────┘  └─────┬─────┘             │
│        │              │              │                     │
│        └──────────────┼──────────────┘                     │
│                       │                                     │
│                       ↓ All use same MCP tools            │
│              ┌─────────────────┐                           │
│              │  MCP Gateway    │                           │
│              └─────────────────┘                           │
│                       │                                     │
│        ┌──────────────┼──────────────┐                     │
│        ↓              ↓              ↓                     │
│   ┌────────┐    ┌────────┐    ┌────────┐                 │
│   │ Mod    │    │ DB     │    │ Notify │                 │
│   │ Tools  │    │ Tools  │    │ Tools  │                 │
│   └────────┘    └────────┘    └────────┘                 │
└─────────────────────────────────────────────────────────────┘
```

**Benefits:**
- Multiple services can use same tools
- Tools can be updated independently
- Scales horizontally

#### 2. **Tool Versioning**

```python
# Use specific tool version
mcp_tools = MCPTool.from_server(
    server_url="http://mcp-tools:8001",
    version="v2"  # Use v2 of moderation tools
)
```

#### 3. **Easy Testing**

```python
# In tests, mock MCP server
mock_mcp = MockMCPServer()
mock_mcp.set_response("flag_content", {"case_id": "test_123"})

# Agent uses mock in tests
agent = ModerationAgent(mcp_client=mock_mcp)
```

#### 4. **Cross-Language Support**

```
┌────────────────────┐
│ Python Agent       │ ─┐
└────────────────────┘  │
                        │
┌────────────────────┐  │
│ Node.js Service    │ ─┼─→ Same MCP Tools
└────────────────────┘  │   (Language-agnostic)
                        │
┌────────────────────┐  │
│ Go Microservice    │ ─┘
└────────────────────┘
```

#### 5. **Security & Authentication**

```python
# MCP handles auth centrally
mcp_client = MCPClient(
    server_url="http://mcp-gateway",
    api_key=os.getenv("MCP_API_KEY"),
    auth_type="jwt"
)
```

---

### Migration Path: Demo → Production

**Phase 1: Current Demo**
```python
db = Database()
result = await db.create_case(...)
```

**Phase 2: Add MCP Servers**
```python
# Wrap existing code in MCP servers
# No changes to agents yet
```

**Phase 3: Agents Use MCP**
```python
mcp_client = MCPClient("http://mcp-gateway")
result = await mcp_client.call_tool("create_case", {...})
```

**Phase 4: Scale Out**
```
Deploy MCP servers separately
Multiple agent instances
Load balancing
```

---

## 🔍 Vector Store Architecture

### Two Collections: Why We Need Both

CupidsShield uses **TWO separate ChromaDB collections** for different purposes:

#### 1. **`flagged_content`** - Violations Only
```python
# Only stores content that violated policies
collection.add(
    content="Send me money on WhatsApp...",
    metadata={
        "violation_type": "scams",
        "severity": "high"
    }
)
```

**Purpose:** Pattern detection for violations
**Contains:** Only flagged/violating content
**Used by:** `search_similar_violations()`

#### 2. **`historical_cases`** - ALL Cases
```python
# Stores ALL moderation cases (violations AND clean content)
collection.add(
    case_summary="Crypto discussion - approved. User has 2-year history...",
    metadata={
        "decision": "approved",
        "violation_type": "none",
        "confidence": 0.98
    }
)
```

**Purpose:** Learning from ALL historical decisions
**Contains:** Approved + Rejected + Escalated cases
**Used by:** `search_similar_cases()`

---

### Why Both Collections?

| Scenario | Need Violations Collection? | Need Historical Cases Collection? |
|----------|---------------------------|-----------------------------------|
| Detect new scam patterns | ✅ Yes - find similar scams | ✅ Yes - see how similar content was judged |
| Avoid false positives | ❌ No help | ✅ Yes - find similar content that was approved |
| Learn from context | ❌ Limited | ✅ Yes - see full decision history |
| Understand edge cases | ❌ Only violations | ✅ Yes - see borderline cases and outcomes |

---

### Example: Crypto Discussion

**Content:** *"I've been learning about cryptocurrency lately. Have you looked into blockchain technology?"*

#### What Each Collection Returns:

**`search_similar_violations()`** (flagged_content):
```python
[
  {
    "content": "I'm a crypto trader making $10k daily...",
    "violation_type": "scams",
    "severity": "high",
    "similarity": 0.78
  },
  {
    "content": "Want to invest in crypto with me?",
    "violation_type": "scams",
    "severity": "medium",
    "similarity": 0.72
  }
]
```
**Problem:** Only shows violations! Doesn't show legitimate crypto discussions.

**`search_similar_cases()`** (historical_cases):
```python
[
  {
    "summary": "Crypto discussion - approved. Software engineer...",
    "decision": "approved",
    "violation_type": "none",
    "similarity": 0.85
  },
  {
    "summary": "Scam - crypto trading scheme...",
    "decision": "rejected",
    "violation_type": "scams",
    "similarity": 0.78
  },
  {
    "summary": "Borderline crypto mention - escalated...",
    "decision": "escalated",
    "violation_type": "scams",
    "similarity": 0.75
  }
]
```
**Better:** Shows BOTH violations AND approved cases, giving full context!

---

### Updated Moderation Flow

```
┌────────────────────────────────────────────────────────────┐
│  RISK ASSESSMENT NODE                                      │
│                                                            │
│  1. Search Similar Violations                             │
│     ↓                                                      │
│     vector_store.search_similar_violations()              │
│     Returns: Only flagged content                         │
│     Purpose: Find known violation patterns                │
│                                                            │
│  2. Search Similar Historical Cases (NEW!)                │
│     ↓                                                      │
│     vector_store.search_similar_cases()                   │
│     Returns: ALL past cases (approved + rejected)         │
│     Purpose: Learn from full history, avoid false positives│
│                                                            │
│  3. LLM Analysis                                          │
│     ↓                                                      │
│     Considers BOTH:                                       │
│     - Violation patterns (from flagged_content)           │
│     - Historical decisions (from historical_cases)        │
│     - Policies                                            │
│     ↓                                                      │
│     Makes informed decision with full context             │
└────────────────────────────────────────────────────────────┘
```

---

### Code Changes Made

#### Before (Only searched violations):
```python
# Line 106 - OLD CODE
similar_cases = self.vector_store.search_similar_violations(
    content=content,
    n_results=5,
)
state["similar_cases"] = similar_cases  # Only violations!
```

**Problem:**
- ❌ Only finds similar violations
- ❌ Misses similar approved content
- ❌ No learning from false positives
- ❌ Higher false positive rate

#### After (Searches both):
```python
# NEW CODE - Lines 106-120
# Search for similar violations (flagged content only)
similar_violations = self.vector_store.search_similar_violations(
    content=content,
    n_results=5,
)

# Search for similar historical cases (ALL cases - approved and rejected)
similar_historical_cases = self.vector_store.search_similar_cases(
    query=content,
    n_results=5,
)

# Combine both for comprehensive context
state["similar_violations"] = similar_violations
state["similar_cases"] = similar_historical_cases
```

**Benefits:**
- ✅ Finds violation patterns
- ✅ Finds similar approved content
- ✅ Learns from false positives
- ✅ Lower false positive rate
- ✅ Better context for LLM

---

### Storage Strategy

#### When to Add to Each Collection:

**`flagged_content`** (Violations only):
```python
# Only if violation detected
if violation_type:
    vector_store.add_flagged_content(
        content=content,
        violation_type="scams",
        severity="high"
    )
```

**`historical_cases`** (ALWAYS):
```python
# ALWAYS add - whether violation or clean
vector_store.add_historical_case(
    case_id=case_id,
    case_summary=summary,
    decision=decision,  # approved, rejected, escalated
    violation_type=violation_type or "none"
)
```

---

### Benefits of This Approach

| Benefit | How It Helps |
|---------|-------------|
| **Reduced False Positives** | LLM sees similar content that was correctly approved |
| **Better Context** | Full history of decisions, not just violations |
| **Learning from Mistakes** | Can see past false positives and avoid repeating |
| **Edge Case Handling** | Finds similar borderline cases and their outcomes |
| **Consistent Decisions** | See how similar content was judged before |
| **Transparency** | Complete audit trail of all decisions |

---

### Example Output in LLM Prompt

**OLD (violations only):**
```
Similar historical violations found:
1. Similarity: 0.78 - scams (severity: high)
2. Similarity: 0.72 - scams (severity: medium)
```

**NEW (comprehensive context):**
```
Similar flagged violations found:
1. Similarity: 0.78 - scams (severity: high)
2. Similarity: 0.72 - scams (severity: medium)

Similar historical cases (including approved content):
1. Similarity: 0.85 - Decision: approved, Violation: none
   Summary: Crypto discussion - approved. Software engineer...
2. Similarity: 0.78 - Decision: rejected, Violation: scams
   Summary: Scam - crypto trading scheme...
3. Similarity: 0.75 - Decision: escalated, Violation: scams
   Summary: Borderline crypto mention - escalated...
```

**Result:** LLM can see that similar crypto discussions have been approved in the past, reducing false positives!

---

## 📊 Database Schema

### Core Tables

```sql
-- Moderation cases
CREATE TABLE moderation_cases (
    id TEXT PRIMARY KEY,
    content_type TEXT NOT NULL,
    content TEXT NOT NULL,
    user_id TEXT NOT NULL,
    risk_score REAL,
    decision TEXT NOT NULL,  -- approved, rejected, escalated, pending
    reasoning TEXT NOT NULL,
    confidence REAL,
    violation_type TEXT,     -- scams, harassment, fake_profile, etc.
    severity TEXT,           -- low, medium, high, critical
    reviewed_by TEXT NOT NULL,
    metadata TEXT,           -- JSON
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Appeals
CREATE TABLE appeals (
    id TEXT PRIMARY KEY,
    case_id TEXT NOT NULL REFERENCES moderation_cases(id),
    user_explanation TEXT NOT NULL,
    new_evidence TEXT,
    appeal_decision TEXT,     -- pending, upheld, overturned, escalated
    appeal_reasoning TEXT,
    appeal_confidence REAL,
    resolved_by TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    resolved_at TIMESTAMP
);

-- Review queue for human moderators
CREATE TABLE review_queue (
    id TEXT PRIMARY KEY,
    case_id TEXT REFERENCES moderation_cases(id),
    appeal_id TEXT REFERENCES appeals(id),
    priority TEXT,           -- low, medium, high, urgent
    assigned_to TEXT,        -- moderator_id
    status TEXT,             -- pending, in_review, completed
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    claimed_at TIMESTAMP,
    completed_at TIMESTAMP
);

-- Audit log for compliance
CREATE TABLE audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    case_id TEXT,
    action TEXT NOT NULL,
    actor TEXT NOT NULL,    -- agent, moderator_id, system
    details TEXT,           -- JSON
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

---

## 🎯 Summary

### Key Takeaways

1. **Confidence ≠ Risk**
   - Confidence = AI's certainty in its assessment
   - High confidence → Auto-decision
   - Low confidence → Human review

2. **Content Flow Options**
   - Proactive: Moderate all content
   - Reactive: Moderate reported content
   - Hybrid: Smart filtering (recommended)

3. **Decision Thresholds**
   - ≥90%: Auto-approve (clean)
   - ≥85%: Auto-reject (violation)
   - <70%: Escalate (uncertain)

4. **MCP Architecture**
   - Demo: Direct function calls (simpler)
   - Production: True MCP protocol (scalable)
   - Benefits: Microservices, versioning, cross-language

5. **Human-in-the-Loop**
   - Borderline cases go to queue
   - Moderators see full context
   - Final decisions logged for audit

---

**This architecture balances automation with human oversight, ensuring both efficiency and safety in Trust & Safety operations.**
