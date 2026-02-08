"""
Notification tools for CupidsShield MCP server.
Handles user notifications, moderator alerts, and audit logging.
"""

from typing import Dict, Any, Optional
from datetime import datetime
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from data.db import Database


class Notifiers:
    """Tools for sending notifications and alerts."""

    def __init__(self, db: Database):
        self.db = db

    async def send_user_notification(
        self,
        user_id: str,
        notification_type: str,
        title: str,
        message: str,
        case_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Send a notification to a user about a moderation decision.

        Args:
            user_id: User ID to notify
            notification_type: Type of notification (decision, appeal_update, warning, etc.)
            title: Notification title
            message: Notification message
            case_id: Related case ID
            metadata: Additional metadata

        Returns:
            Notification result
        """
        try:
            # In a real system, this would integrate with email/push notification service
            # For demo purposes, we'll log it to the audit trail

            notification_data = {
                "user_id": user_id,
                "notification_type": notification_type,
                "title": title,
                "message": message,
                "timestamp": datetime.now().isoformat(),
                "metadata": metadata or {},
            }

            # Log to audit trail
            async with self.db.get_connection() as conn:
                await self.db._log_audit(
                    conn=conn,
                    case_id=case_id,
                    action="user_notification_sent",
                    actor="system",
                    details=notification_data,
                )

            # Simulate notification sent
            print(f"User Notification Sent to {user_id}:")
            print(f"   Type: {notification_type}")
            print(f"   Title: {title}")
            print(f"   Message: {message[:100]}...")
            print()

            return {
                "success": True,
                "user_id": user_id,
                "notification_type": notification_type,
                "message": "Notification sent successfully",
            }

        except Exception as e:
            return {"success": False, "error": str(e)}

    async def send_moderator_alert(
        self,
        alert_type: str,
        priority: str,
        title: str,
        description: str,
        case_id: Optional[str] = None,
        appeal_id: Optional[str] = None,
        assigned_to: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Send an alert to moderators for review.

        Args:
            alert_type: Type of alert (escalation, high_risk, appeal_review, etc.)
            priority: Priority level (low, medium, high, urgent)
            title: Alert title
            description: Alert description
            case_id: Related case ID
            appeal_id: Related appeal ID
            assigned_to: Specific moderator to assign to
            metadata: Additional metadata

        Returns:
            Alert result
        """
        try:
            alert_data = {
                "alert_type": alert_type,
                "priority": priority,
                "title": title,
                "description": description,
                "case_id": case_id,
                "appeal_id": appeal_id,
                "assigned_to": assigned_to,
                "timestamp": datetime.now().isoformat(),
                "metadata": metadata or {},
            }

            # Log to audit trail
            async with self.db.get_connection() as conn:
                await self.db._log_audit(
                    conn=conn,
                    case_id=case_id,
                    appeal_id=appeal_id,
                    action="moderator_alert_sent",
                    actor="system",
                    details=alert_data,
                )

            # Simulate alert sent
            print(f"Moderator Alert ({priority.upper()}):")
            print(f"   Type: {alert_type}")
            print(f"   Title: {title}")
            print(f"   Description: {description[:100]}...")
            if assigned_to:
                print(f"   Assigned to: {assigned_to}")
            print()

            return {
                "success": True,
                "alert_type": alert_type,
                "priority": priority,
                "message": "Alert sent successfully",
            }

        except Exception as e:
            return {"success": False, "error": str(e)}

    async def log_action(
        self,
        action: str,
        actor: str,
        case_id: Optional[str] = None,
        appeal_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Log an action to the audit trail.

        Args:
            action: Action performed
            actor: Who performed the action
            case_id: Related case ID
            appeal_id: Related appeal ID
            details: Additional details

        Returns:
            Log result
        """
        try:
            async with self.db.get_connection() as conn:
                await self.db._log_audit(
                    conn=conn,
                    case_id=case_id,
                    appeal_id=appeal_id,
                    action=action,
                    actor=actor,
                    details=details or {},
                )

            return {
                "success": True,
                "action": action,
                "message": "Action logged successfully",
            }

        except Exception as e:
            return {"success": False, "error": str(e)}

    async def send_decision_notification(
        self,
        user_id: str,
        case_id: str,
        decision: str,
        violation_type: str,
        reasoning: str,
        action_taken: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Send a moderation decision notification to a user.

        Args:
            user_id: User ID
            case_id: Case ID
            decision: Decision made (approved, rejected, escalated)
            violation_type: Type of violation
            reasoning: Reasoning for decision
            action_taken: Action taken (ban, warn, etc.)

        Returns:
            Notification result
        """
        # Generate user-friendly message
        if decision == "rejected":
            title = "Content Moderation Notice"
            if action_taken:
                message = f"""
We've reviewed your content and found it violates our community guidelines regarding {violation_type}.

Action taken: {action_taken}

Reason: {reasoning}

You can appeal this decision within 30 days by providing additional context or evidence.

Case ID: {case_id}
                """.strip()
            else:
                message = f"""
Your content has been removed for violating our {violation_type} policy.

Reason: {reasoning}

You can appeal this decision within 30 days.

Case ID: {case_id}
                """.strip()

        elif decision == "approved":
            title = "Content Approved"
            message = f"""
Your content has been reviewed and approved.

Case ID: {case_id}
            """.strip()

        else:  # escalated
            title = "Content Under Review"
            message = f"""
Your content is under review by our moderation team.

We'll notify you once the review is complete.

Case ID: {case_id}
            """.strip()

        return await self.send_user_notification(
            user_id=user_id,
            notification_type="moderation_decision",
            title=title,
            message=message,
            case_id=case_id,
            metadata={"decision": decision, "violation_type": violation_type},
        )

    async def send_appeal_update(
        self,
        user_id: str,
        appeal_id: str,
        case_id: str,
        decision: str,
        reasoning: str,
    ) -> Dict[str, Any]:
        """
        Send an appeal decision update to a user.

        Args:
            user_id: User ID
            appeal_id: Appeal ID
            case_id: Original case ID
            decision: Appeal decision (upheld, overturned, escalated)
            reasoning: Reasoning for decision

        Returns:
            Notification result
        """
        if decision == "overturned":
            title = "Appeal Approved"
            message = f"""
Good news! Your appeal has been reviewed and approved.

The original moderation decision has been reversed and your content has been restored.

Reason: {reasoning}

Appeal ID: {appeal_id}
Case ID: {case_id}
            """.strip()

        elif decision == "upheld":
            title = "Appeal Decision"
            message = f"""
We've carefully reviewed your appeal. After consideration, we've decided to uphold the original decision.

Reason: {reasoning}

If you have additional evidence, you may contact support.

Appeal ID: {appeal_id}
Case ID: {case_id}
            """.strip()

        else:  # escalated
            title = "Appeal Under Review"
            message = f"""
Your appeal has been escalated to our senior moderation team for additional review.

We'll notify you once a final decision is made. This typically takes 48 hours.

Appeal ID: {appeal_id}
Case ID: {case_id}
            """.strip()

        return await self.send_user_notification(
            user_id=user_id,
            notification_type="appeal_update",
            title=title,
            message=message,
            case_id=case_id,
            metadata={"appeal_id": appeal_id, "decision": decision},
        )
