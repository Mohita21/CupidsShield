"""
Database utilities for CupidsShield.
Handles SQLite connections, initialization, and common queries.
"""

import aiosqlite
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from contextlib import asynccontextmanager


class Database:
    """SQLite database manager for CupidsShield."""

    def __init__(self, db_path: str = "./data/cupidsshield.db"):
        self.db_path = db_path
        self._ensure_data_directory()

    def _ensure_data_directory(self):
        """Create data directory if it doesn't exist."""
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

    @asynccontextmanager
    async def get_connection(self):
        """Get database connection as async context manager."""
        conn = await aiosqlite.connect(self.db_path)
        conn.row_factory = aiosqlite.Row
        try:
            yield conn
        finally:
            await conn.close()

    async def initialize(self):
        """Initialize database with schema."""
        schema_path = Path(__file__).parent / "schema.sql"
        async with self.get_connection() as conn:
            with open(schema_path, "r") as f:
                schema_sql = f.read()
            await conn.executescript(schema_sql)
            await conn.commit()
        print(f"Database initialized at {self.db_path}")

    # ============= Moderation Cases =============

    async def create_case(
        self,
        content_type: str,
        content: str,
        user_id: str,
        risk_score: float,
        decision: str,
        reasoning: str,
        confidence: float,
        violation_type: Optional[str] = None,
        severity: Optional[str] = None,
        reviewed_by: str = "agent",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Create a new moderation case."""
        case_id = f"case_{uuid.uuid4().hex[:12]}"
        metadata_json = json.dumps(metadata) if metadata else None

        async with self.get_connection() as conn:
            await conn.execute(
                """
                INSERT INTO moderation_cases (
                    id, content_type, content, user_id, risk_score, decision,
                    reasoning, confidence, violation_type, severity, reviewed_by, metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    case_id,
                    content_type,
                    content,
                    user_id,
                    risk_score,
                    decision,
                    reasoning,
                    confidence,
                    violation_type,
                    severity,
                    reviewed_by,
                    metadata_json,
                ),
            )
            await conn.commit()

            # Add to review queue if escalated
            if decision == "escalated":
                await self._add_to_review_queue(conn, case_id=case_id, priority="high")

            # Log audit trail
            await self._log_audit(
                conn,
                case_id=case_id,
                action="case_created",
                actor=reviewed_by,
                details={"decision": decision, "violation_type": violation_type},
            )

        return case_id

    async def get_case(self, case_id: str) -> Optional[Dict[str, Any]]:
        """Get a moderation case by ID."""
        async with self.get_connection() as conn:
            async with conn.execute(
                "SELECT * FROM moderation_cases WHERE id = ?", (case_id,)
            ) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else None

    async def get_cases_by_user(self, user_id: str) -> List[Dict[str, Any]]:
        """Get all moderation cases for a user."""
        async with self.get_connection() as conn:
            async with conn.execute(
                "SELECT * FROM moderation_cases WHERE user_id = ? ORDER BY created_at DESC",
                (user_id,),
            ) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]

    async def update_case_decision(
        self,
        case_id: str,
        decision: str,
        reasoning: str,
        reviewed_by: str,
        confidence: Optional[float] = None,
    ):
        """Update a case decision (e.g., after human review)."""
        async with self.get_connection() as conn:
            update_fields = ["decision = ?", "reasoning = ?", "reviewed_by = ?"]
            params = [decision, reasoning, reviewed_by]

            if confidence is not None:
                update_fields.append("confidence = ?")
                params.append(confidence)

            params.append(case_id)

            await conn.execute(
                f"UPDATE moderation_cases SET {', '.join(update_fields)} WHERE id = ?",
                params,
            )
            await conn.commit()

            # Log audit trail
            await self._log_audit(
                conn,
                case_id=case_id,
                action="decision_updated",
                actor=reviewed_by,
                details={"new_decision": decision},
            )

    async def query_cases(
        self,
        decision: Optional[str] = None,
        violation_type: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Query cases with filters."""
        query = "SELECT * FROM moderation_cases WHERE 1=1"
        params = []

        if decision:
            query += " AND decision = ?"
            params.append(decision)

        if violation_type:
            query += " AND violation_type = ?"
            params.append(violation_type)

        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        async with self.get_connection() as conn:
            async with conn.execute(query, params) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]

    # ============= Appeals =============

    async def create_appeal(
        self,
        case_id: str,
        user_explanation: str,
        new_evidence: Optional[str] = None,
    ) -> str:
        """Create a new appeal for a moderation case."""
        appeal_id = f"appeal_{uuid.uuid4().hex[:12]}"

        async with self.get_connection() as conn:
            await conn.execute(
                """
                INSERT INTO appeals (id, case_id, user_explanation, new_evidence, appeal_decision)
                VALUES (?, ?, ?, ?, 'pending')
                """,
                (appeal_id, case_id, user_explanation, new_evidence),
            )
            await conn.commit()

            # Add to review queue
            await self._add_to_review_queue(
                conn, appeal_id=appeal_id, priority="medium"
            )

            # Log audit trail
            await self._log_audit(
                conn,
                case_id=case_id,
                appeal_id=appeal_id,
                action="appeal_filed",
                actor="user",
                details={"explanation": user_explanation[:100]},
            )

        return appeal_id

    async def get_appeal(self, appeal_id: str) -> Optional[Dict[str, Any]]:
        """Get an appeal by ID."""
        async with self.get_connection() as conn:
            async with conn.execute(
                "SELECT * FROM appeals WHERE id = ?", (appeal_id,)
            ) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else None

    async def resolve_appeal(
        self,
        appeal_id: str,
        decision: str,
        reasoning: str,
        resolved_by: str,
        confidence: Optional[float] = None,
    ):
        """Resolve an appeal with a decision."""
        async with self.get_connection() as conn:
            await conn.execute(
                """
                UPDATE appeals
                SET appeal_decision = ?, appeal_reasoning = ?, appeal_confidence = ?,
                    resolved_by = ?, resolved_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (decision, reasoning, confidence, resolved_by, appeal_id),
            )
            await conn.commit()

            # Get case_id for audit log
            async with conn.execute(
                "SELECT case_id FROM appeals WHERE id = ?", (appeal_id,)
            ) as cursor:
                row = await cursor.fetchone()
                case_id = row["case_id"] if row else None

            # Log audit trail
            await self._log_audit(
                conn,
                case_id=case_id,
                appeal_id=appeal_id,
                action="appeal_resolved",
                actor=resolved_by,
                details={"decision": decision},
            )

    # ============= Review Queue =============

    async def _add_to_review_queue(
        self,
        conn: aiosqlite.Connection,
        case_id: Optional[str] = None,
        appeal_id: Optional[str] = None,
        priority: str = "medium",
    ):
        """Add item to moderator review queue."""
        queue_id = f"queue_{uuid.uuid4().hex[:12]}"
        await conn.execute(
            """
            INSERT INTO review_queue (id, case_id, appeal_id, priority, status)
            VALUES (?, ?, ?, ?, 'pending')
            """,
            (queue_id, case_id, appeal_id, priority),
        )

    async def get_review_queue(
        self, status: str = "pending", limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Get items from review queue."""
        async with self.get_connection() as conn:
            async with conn.execute(
                """
                SELECT rq.*, mc.content, mc.violation_type, mc.user_id
                FROM review_queue rq
                LEFT JOIN moderation_cases mc ON rq.case_id = mc.id
                WHERE rq.status = ?
                ORDER BY
                    CASE rq.priority
                        WHEN 'urgent' THEN 1
                        WHEN 'high' THEN 2
                        WHEN 'medium' THEN 3
                        WHEN 'low' THEN 4
                    END,
                    rq.created_at DESC
                LIMIT ?
                """,
                (status, limit),
            ) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]

    async def assign_queue_item(self, queue_id: str, moderator_id: str):
        """Assign a queue item to a moderator."""
        async with self.get_connection() as conn:
            await conn.execute(
                """
                UPDATE review_queue
                SET assigned_to = ?, status = 'in_review', assigned_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (moderator_id, queue_id),
            )
            await conn.commit()

    async def complete_queue_item(self, queue_id: str):
        """Mark a queue item as completed."""
        async with self.get_connection() as conn:
            await conn.execute(
                """
                UPDATE review_queue
                SET status = 'completed', completed_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (queue_id,),
            )
            await conn.commit()

    # ============= Audit Log =============

    async def _log_audit(
        self,
        conn: aiosqlite.Connection,
        action: str,
        actor: str,
        case_id: Optional[str] = None,
        appeal_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        """Log an audit trail entry."""
        audit_id = f"audit_{uuid.uuid4().hex[:12]}"
        details_json = json.dumps(details) if details else None

        await conn.execute(
            """
            INSERT INTO audit_log (id, case_id, appeal_id, action, actor, details)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (audit_id, case_id, appeal_id, action, actor, details_json),
        )

    async def get_audit_log(
        self, case_id: Optional[str] = None, limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get audit log entries."""
        query = "SELECT * FROM audit_log WHERE 1=1"
        params = []

        if case_id:
            query += " AND case_id = ?"
            params.append(case_id)

        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)

        async with self.get_connection() as conn:
            async with conn.execute(query, params) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]

    # ============= Metrics =============

    async def record_metric(
        self, metric_name: str, metric_value: float, metadata: Optional[Dict] = None
    ):
        """Record a metrics snapshot."""
        metric_id = f"metric_{uuid.uuid4().hex[:12]}"
        metadata_json = json.dumps(metadata) if metadata else None

        async with self.get_connection() as conn:
            await conn.execute(
                """
                INSERT INTO metrics_snapshot (id, metric_name, metric_value, metric_metadata)
                VALUES (?, ?, ?, ?)
                """,
                (metric_id, metric_name, metric_value, metadata_json),
            )
            await conn.commit()

    async def get_metrics(
        self, metric_name: Optional[str] = None, hours: int = 24
    ) -> List[Dict[str, Any]]:
        """Get recent metrics."""
        query = """
            SELECT * FROM metrics_snapshot
            WHERE timestamp >= datetime('now', '-{} hours')
        """.format(hours)
        params = []

        if metric_name:
            query += " AND metric_name = ?"
            params.append(metric_name)

        query += " ORDER BY timestamp DESC"

        async with self.get_connection() as conn:
            async with conn.execute(query, params) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]

    # ============= Statistics =============

    async def get_statistics(self) -> Dict[str, Any]:
        """Get overview statistics."""
        async with self.get_connection() as conn:
            # Total cases
            async with conn.execute(
                "SELECT COUNT(*) as count FROM moderation_cases"
            ) as cursor:
                total_cases = (await cursor.fetchone())["count"]

            # Cases by decision
            async with conn.execute(
                """
                SELECT decision, COUNT(*) as count
                FROM moderation_cases
                GROUP BY decision
                """
            ) as cursor:
                decisions = {row["decision"]: row["count"] for row in await cursor.fetchall()}

            # Cases in last 24 hours
            async with conn.execute(
                """
                SELECT COUNT(*) as count
                FROM moderation_cases
                WHERE created_at >= datetime('now', '-24 hours')
                """
            ) as cursor:
                cases_24h = (await cursor.fetchone())["count"]

            # Pending appeals
            async with conn.execute(
                "SELECT COUNT(*) as count FROM appeals WHERE appeal_decision = 'pending'"
            ) as cursor:
                pending_appeals = (await cursor.fetchone())["count"]

            # Review queue size
            async with conn.execute(
                "SELECT COUNT(*) as count FROM review_queue WHERE status = 'pending'"
            ) as cursor:
                queue_size = (await cursor.fetchone())["count"]

            return {
                "total_cases": total_cases,
                "decisions": decisions,
                "cases_24h": cases_24h,
                "pending_appeals": pending_appeals,
                "review_queue_size": queue_size,
            }


# Convenience function for CLI usage
async def init_database(db_path: str = "./data/cupidsshield.db"):
    """Initialize the database from command line."""
    db = Database(db_path)
    await db.initialize()
    print("Database initialized successfully")

    # Print statistics
    stats = await db.get_statistics()
    print(f"Database statistics: {stats}")


if __name__ == "__main__":
    import asyncio
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "init":
        db_path = sys.argv[2] if len(sys.argv) > 2 else "./data/cupidsshield.db"
        asyncio.run(init_database(db_path))
    else:
        print("Usage: python -m data.db init [db_path]")
