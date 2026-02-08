"""
State schemas for CupidsShield agents.
Defines TypedDict states for LangGraph workflows.
"""

from typing import TypedDict, Optional, List, Dict, Any


class ModerationState(TypedDict, total=False):
    """State for the Content Moderation Agent workflow."""

    # Input
    content_id: str
    content_type: str  # 'profile', 'message', 'photo', 'bio'
    content: str
    user_id: str
    metadata: Dict[str, Any]

    # Risk Assessment
    risk_score: float
    confidence: float
    violation_type: Optional[str]
    severity: str
    reasoning: str
    similar_violations: List[Dict[str, Any]]
    similar_cases: List[Dict[str, Any]]
    relevant_policies: List[Dict[str, Any]]

    # Decision
    decision: str  # 'approved', 'rejected', 'escalated'
    action: Optional[str]  # 'warn', 'temp_ban_24h', etc.

    # Human-in-the-Loop (for resumed workflows)
    moderator_decision: Optional[str]
    moderator_reasoning: Optional[str]
    moderator_id: Optional[str]
    reviewed_by: Optional[str]

    # Output
    case_id: str
    notification_sent: bool
    status: Optional[str]  # 'PAUSED_FOR_HUMAN_REVIEW', etc.
    error: Optional[str]


class AppealsState(TypedDict, total=False):
    """State for the Appeals Agent workflow."""

    # Input
    appeal_id: str
    case_id: str
    user_explanation: str
    new_evidence: Optional[str]

    # Context Retrieval
    original_case: Dict[str, Any]
    user_history: Dict[str, Any]
    similar_cases: List[Dict[str, Any]]
    original_reasoning: str
    original_decision: str

    # Evaluation
    has_new_evidence: bool
    policy_misinterpreted: bool
    explanation_valid: bool
    user_history_considered: bool

    new_evidence_score: float
    policy_score: float
    explanation_score: float
    history_score: float

    overall_score: float
    confidence: float

    # Decision
    appeal_decision: str  # 'upheld', 'overturned', 'escalated'
    reasoning: str

    # Output
    notification_sent: bool
    case_updated: bool
    error: Optional[str]
