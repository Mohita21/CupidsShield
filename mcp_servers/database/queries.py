"""
Database query tools for CupidsShield MCP server.
Provides database access and vector similarity search.
"""

from typing import Dict, Any, Optional, List
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from data.db import Database
from data.vector_store import VectorStore


class DatabaseQueries:
    """Tools for database queries and vector search."""

    def __init__(self, db: Database, vector_store: VectorStore):
        self.db = db
        self.vector_store = vector_store

    async def query_cases(
        self,
        decision: Optional[str] = None,
        violation_type: Optional[str] = None,
        limit: int = 100,
    ) -> Dict[str, Any]:
        """
        Query moderation cases with filters.

        Args:
            decision: Filter by decision (approved, rejected, escalated, pending)
            violation_type: Filter by violation type
            limit: Maximum results to return

        Returns:
            List of matching cases
        """
        try:
            cases = await self.db.query_cases(
                decision=decision, violation_type=violation_type, limit=limit
            )

            return {
                "success": True,
                "count": len(cases),
                "cases": cases,
            }

        except Exception as e:
            return {"success": False, "error": str(e)}

    async def get_case(self, case_id: str) -> Dict[str, Any]:
        """
        Get a specific case by ID.

        Args:
            case_id: Case ID to retrieve

        Returns:
            Case details
        """
        try:
            case = await self.db.get_case(case_id)

            if not case:
                return {"success": False, "error": f"Case not found: {case_id}"}

            return {
                "success": True,
                "case": case,
            }

        except Exception as e:
            return {"success": False, "error": str(e)}

    async def get_appeal(self, appeal_id: str) -> Dict[str, Any]:
        """
        Get an appeal by ID.

        Args:
            appeal_id: Appeal ID to retrieve

        Returns:
            Appeal details
        """
        try:
            appeal = await self.db.get_appeal(appeal_id)

            if not appeal:
                return {"success": False, "error": f"Appeal not found: {appeal_id}"}

            return {
                "success": True,
                "appeal": appeal,
            }

        except Exception as e:
            return {"success": False, "error": str(e)}

    async def create_appeal(
        self,
        case_id: str,
        user_explanation: str,
        new_evidence: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Create a new appeal for a case.

        Args:
            case_id: Case ID to appeal
            user_explanation: User's explanation
            new_evidence: Additional evidence

        Returns:
            Created appeal information
        """
        try:
            appeal_id = await self.db.create_appeal(
                case_id=case_id,
                user_explanation=user_explanation,
                new_evidence=new_evidence,
            )

            return {
                "success": True,
                "appeal_id": appeal_id,
                "message": f"Appeal created: {appeal_id}",
            }

        except Exception as e:
            return {"success": False, "error": str(e)}

    async def resolve_appeal(
        self,
        appeal_id: str,
        decision: str,
        reasoning: str,
        resolved_by: str = "agent",
        confidence: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Resolve an appeal with a decision.

        Args:
            appeal_id: Appeal ID to resolve
            decision: Decision (upheld, overturned, escalated)
            reasoning: Reasoning for decision
            resolved_by: Who resolved it
            confidence: Confidence score

        Returns:
            Resolution result
        """
        try:
            await self.db.resolve_appeal(
                appeal_id=appeal_id,
                decision=decision,
                reasoning=reasoning,
                resolved_by=resolved_by,
                confidence=confidence,
            )

            return {
                "success": True,
                "appeal_id": appeal_id,
                "decision": decision,
                "message": "Appeal resolved successfully",
            }

        except Exception as e:
            return {"success": False, "error": str(e)}

    async def update_case_status(
        self,
        case_id: str,
        decision: str,
        reasoning: str,
        reviewed_by: str,
        confidence: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Update a case status/decision.

        Args:
            case_id: Case ID to update
            decision: New decision
            reasoning: Updated reasoning
            reviewed_by: Who updated it
            confidence: Updated confidence

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

    async def search_similar_cases(
        self,
        content: str,
        violation_type: Optional[str] = None,
        n_results: int = 5,
    ) -> Dict[str, Any]:
        """
        Search for similar cases using vector similarity.

        Args:
            content: Content to find similar cases for
            violation_type: Filter by violation type
            n_results: Number of results to return

        Returns:
            Similar cases with similarity scores
        """
        try:
            # Search in vector store
            similar_cases = self.vector_store.search_similar_violations(
                content=content,
                violation_type=violation_type,
                n_results=n_results,
            )

            # Enrich with full case data
            enriched_cases = []
            for similar in similar_cases:
                case_id = similar["metadata"].get("case_id")
                if case_id:
                    case = await self.db.get_case(case_id)
                    if case:
                        enriched_cases.append(
                            {
                                "case": case,
                                "similarity_score": similar["similarity_score"],
                                "distance": similar["distance"],
                            }
                        )

            return {
                "success": True,
                "count": len(enriched_cases),
                "similar_cases": enriched_cases,
            }

        except Exception as e:
            return {"success": False, "error": str(e)}

    async def get_review_queue(
        self, status: str = "pending", limit: int = 50
    ) -> Dict[str, Any]:
        """
        Get items from the moderator review queue.

        Args:
            status: Filter by status (pending, in_review, completed)
            limit: Maximum items to return

        Returns:
            Queue items
        """
        try:
            queue_items = await self.db.get_review_queue(status=status, limit=limit)

            return {
                "success": True,
                "count": len(queue_items),
                "queue_items": queue_items,
            }

        except Exception as e:
            return {"success": False, "error": str(e)}

    async def get_audit_log(
        self, case_id: Optional[str] = None, limit: int = 100
    ) -> Dict[str, Any]:
        """
        Get audit log entries.

        Args:
            case_id: Filter by case ID
            limit: Maximum entries to return

        Returns:
            Audit log entries
        """
        try:
            log_entries = await self.db.get_audit_log(case_id=case_id, limit=limit)

            return {
                "success": True,
                "count": len(log_entries),
                "audit_log": log_entries,
            }

        except Exception as e:
            return {"success": False, "error": str(e)}

    async def get_statistics(self) -> Dict[str, Any]:
        """
        Get database statistics.

        Returns:
            Statistics summary
        """
        try:
            stats = await self.db.get_statistics()

            # Add vector store stats
            vector_stats = self.vector_store.get_collection_stats()
            stats["vector_store"] = vector_stats

            return {
                "success": True,
                "statistics": stats,
            }

        except Exception as e:
            return {"success": False, "error": str(e)}

    async def search_relevant_policies(
        self, content: str, category: Optional[str] = None, n_results: int = 3
    ) -> Dict[str, Any]:
        """
        Search for relevant T&S policies for content.

        Args:
            content: Content to find policies for
            category: Filter by policy category
            n_results: Number of results

        Returns:
            Relevant policies
        """
        try:
            policies = self.vector_store.search_relevant_policies(
                query=content, category=category, n_results=n_results
            )

            return {
                "success": True,
                "count": len(policies),
                "policies": policies,
            }

        except Exception as e:
            return {"success": False, "error": str(e)}
