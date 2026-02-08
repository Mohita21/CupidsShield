"""
Moderation tools for CupidsShield MCP server.
Provides tools for content flagging, moderation actions, and case management.
"""

from typing import Dict, Any, Optional, List
from datetime import datetime
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from data.db import Database


class ModerationTools:
    """Tools for content moderation actions."""

    def __init__(self, db: Database):
        self.db = db

    async def flag_content(
        self,
        content_id: str,
        content_type: str,
        content: str,
        user_id: str,
        violation_type: str,
        confidence: float,
        reasoning: str,
        severity: str = "medium",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Flag content for moderation review.

        Args:
            content_id: Unique identifier for the content
            content_type: Type of content (profile, message, photo, bio)
            content: The actual content text
            user_id: User who created the content
            violation_type: Type of violation detected
            confidence: Confidence score (0-1)
            reasoning: Explanation for flagging
            severity: Severity level (low, medium, high, critical)
            metadata: Additional context

        Returns:
            Result with case_id and status
        """
        try:
            # Determine decision based on confidence
            if confidence >= 0.90:
                decision = "rejected"
            elif confidence >= 0.70:
                decision = "escalated"
            else:
                decision = "pending"

            # Calculate risk score (simple heuristic)
            severity_scores = {"low": 0.3, "medium": 0.6, "high": 0.8, "critical": 1.0}
            risk_score = min(confidence * severity_scores.get(severity, 0.6), 1.0)

            # Create case in database
            case_id = await self.db.create_case(
                content_type=content_type,
                content=content,
                user_id=user_id,
                risk_score=risk_score,
                decision=decision,
                reasoning=reasoning,
                confidence=confidence,
                violation_type=violation_type,
                severity=severity,
                reviewed_by="agent",
                metadata=metadata or {},
            )

            return {
                "success": True,
                "case_id": case_id,
                "decision": decision,
                "risk_score": risk_score,
                "message": f"Content flagged and case created: {case_id}",
            }

        except Exception as e:
            return {"success": False, "error": str(e)}

    async def apply_moderation_action(
        self,
        case_id: str,
        action: str,
        reviewed_by: str = "agent",
        justification: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Apply a moderation action to a user.

        Args:
            case_id: Case ID to apply action to
            action: Action to take (warn, temp_ban_24h, temp_ban_7d, permanent_ban, etc.)
            reviewed_by: Who applied the action (agent or moderator_id)
            justification: Additional justification

        Returns:
            Result of action application
        """
        try:
            # Get the case
            case = await self.db.get_case(case_id)
            if not case:
                return {"success": False, "error": f"Case not found: {case_id}"}

            # Update case with action
            metadata = {"action_taken": action, "action_timestamp": datetime.now().isoformat()}
            if justification:
                metadata["justification"] = justification

            # Map action to decision
            decision_map = {
                "warn": "approved",  # Warning issued but content approved
                "temp_ban_24h": "rejected",
                "temp_ban_7d": "rejected",
                "permanent_ban": "rejected",
                "permanent_ban_and_report": "rejected",
            }

            decision = decision_map.get(action, case["decision"])

            await self.db.update_case_decision(
                case_id=case_id,
                decision=decision,
                reasoning=f"{case['reasoning']} | Action: {action}. {justification or ''}",
                reviewed_by=reviewed_by,
            )

            return {
                "success": True,
                "case_id": case_id,
                "action": action,
                "user_id": case["user_id"],
                "message": f"Action '{action}' applied to user {case['user_id']}",
            }

        except Exception as e:
            return {"success": False, "error": str(e)}

    async def get_user_history(
        self, user_id: str, limit: int = 10
    ) -> Dict[str, Any]:
        """
        Get moderation history for a user.

        Args:
            user_id: User ID to look up
            limit: Maximum number of cases to return

        Returns:
            User's moderation history
        """
        try:
            cases = await self.db.get_cases_by_user(user_id)
            cases = cases[:limit]  # Limit results

            # Calculate statistics
            violation_counts = {}
            total_violations = 0
            decisions = {"approved": 0, "rejected": 0, "escalated": 0, "pending": 0}

            for case in cases:
                vtype = case.get("violation_type", "unknown")
                violation_counts[vtype] = violation_counts.get(vtype, 0) + 1

                decision = case.get("decision", "pending")
                decisions[decision] = decisions.get(decision, 0) + 1

                if decision in ["rejected", "escalated"]:
                    total_violations += 1

            return {
                "success": True,
                "user_id": user_id,
                "total_cases": len(cases),
                "total_violations": total_violations,
                "violation_counts": violation_counts,
                "decisions": decisions,
                "recent_cases": [
                    {
                        "case_id": c["id"],
                        "violation_type": c.get("violation_type"),
                        "decision": c["decision"],
                        "severity": c.get("severity"),
                        "created_at": c["created_at"],
                    }
                    for c in cases
                ],
            }

        except Exception as e:
            return {"success": False, "error": str(e)}

    async def create_case(
        self,
        content_type: str,
        content: str,
        user_id: str,
        violation_type: str,
        reasoning: str,
        confidence: float,
        severity: str = "medium",
        decision: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Create a moderation case directly.

        Args:
            content_type: Type of content
            content: Content text
            user_id: User ID
            violation_type: Type of violation
            reasoning: Reasoning for the case
            confidence: Confidence score
            severity: Severity level
            decision: Override decision
            metadata: Additional metadata

        Returns:
            Created case information
        """
        try:
            # Determine decision if not provided
            if not decision:
                if confidence >= 0.90:
                    decision = "approved" if violation_type is None else "rejected"
                elif confidence >= 0.70:
                    decision = "escalated"
                else:
                    decision = "pending"

            # Calculate risk score
            severity_scores = {"low": 0.3, "medium": 0.6, "high": 0.8, "critical": 1.0}
            risk_score = min(confidence * severity_scores.get(severity, 0.6), 1.0)

            case_id = await self.db.create_case(
                content_type=content_type,
                content=content,
                user_id=user_id,
                risk_score=risk_score,
                decision=decision,
                reasoning=reasoning,
                confidence=confidence,
                violation_type=violation_type,
                severity=severity,
                reviewed_by="agent",
                metadata=metadata or {},
            )

            return {
                "success": True,
                "case_id": case_id,
                "decision": decision,
                "risk_score": risk_score,
            }

        except Exception as e:
            return {"success": False, "error": str(e)}

    async def update_case(
        self,
        case_id: str,
        decision: str,
        reasoning: str,
        reviewed_by: str,
        confidence: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Update an existing case decision.

        Args:
            case_id: Case ID to update
            decision: New decision
            reasoning: Updated reasoning
            reviewed_by: Who updated (agent or moderator_id)
            confidence: Updated confidence score

        Returns:
            Update result
        """
        try:
            await self.db.update_case_decision(
                case_id=case_id,
                decision=decision,
                reasoning=reasoning,
                reviewed_by=reviewed_by,
                confidence=confidence,
            )

            return {
                "success": True,
                "case_id": case_id,
                "decision": decision,
                "message": "Case updated successfully",
            }

        except Exception as e:
            return {"success": False, "error": str(e)}
