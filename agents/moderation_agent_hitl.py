"""
Content Moderation Agent with TRUE Human-in-the-Loop using LangGraph.
Demonstrates workflow interrupts and checkpointing for human review.
"""

import os
import yaml
from typing import Dict, Any, Optional
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
import sys

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from agents.state import ModerationState
from agents.prompt_loader import get_prompt_loader
from data.db import Database
from data.vector_store import VectorStore
from monitoring.tracing import trace_agent_workflow, trace_node


class ModerationAgentWithHITL:
    """
    Content moderation agent with TRUE Human-in-the-Loop.

    Uses LangGraph checkpointing and interrupts to pause workflow
    when human input is needed, then resumes after decision.
    """

    def __init__(
        self,
        db: Database,
        vector_store: VectorStore,
        config_path: str = "./config/moderation_config.yaml",
    ):
        self.db = db
        self.vector_store = vector_store

        # Load configuration
        with open(config_path, "r") as f:
            self.config = yaml.safe_load(f)

        # Initialize LLM
        self.llm = ChatOpenAI(
            model=self.config["agent_config"]["model"],
            temperature=self.config["agent_config"]["temperature"],
            max_tokens=self.config["agent_config"]["max_tokens"],
        )

        # Workflow and checkpointer - initialized async
        self.checkpointer = None
        self.workflow = None
        self._workflow_graph = None

    async def initialize(self):
        """Initialize async components (checkpointer and workflow)."""
        if self.workflow is None:
            # Create in-memory checkpointer
            # NOTE: Checkpoints persist as long as this agent instance is alive
            # The UI server keeps the same agent instance, so checkpoints work across requests
            self.checkpointer = MemorySaver()

            # Build and compile workflow
            self._workflow_graph = self._build_workflow_graph()
            self.workflow = self._workflow_graph.compile(
                checkpointer=self.checkpointer,
                interrupt_before=["human_review"]
            )

    def _build_workflow_graph(self) -> StateGraph:
        """
        Build LangGraph workflow graph (without compilation).
        """
        workflow = StateGraph(ModerationState)

        # Add nodes
        workflow.add_node("intake", self._intake_node)
        workflow.add_node("risk_assessment", self._risk_assessment_node)
        workflow.add_node("make_decision", self._decision_node)
        workflow.add_node("human_review", self._human_review_node)  # HITL node
        workflow.add_node("execute_action", self._action_node)
        workflow.add_node("send_notification", self._notification_node)

        # Set entry point
        workflow.set_entry_point("intake")

        # Add edges
        workflow.add_edge("intake", "risk_assessment")
        workflow.add_edge("risk_assessment", "make_decision")

        # Conditional routing after decision
        workflow.add_conditional_edges(
            "make_decision",
            self._route_after_decision,
            {
                "human_review": "human_review",  # Route to HITL
                "execute_action": "execute_action",  # Auto-approve/reject
            },
        )

        # After human review, continue to action
        workflow.add_edge("human_review", "execute_action")
        workflow.add_edge("execute_action", "send_notification")
        workflow.add_edge("send_notification", END)

        # CRITICAL: Enable checkpointing and interrupt at human_review
        # Use SqliteSaver for persistent checkpoints across processes
        # This must be async, so we'll initialize it when needed
        return workflow

    def _route_after_decision(self, state: ModerationState) -> str:
        """
        Route to human review or direct action based on confidence.
        """
        decision = state.get("decision")
        confidence = state.get("confidence", 0.0)

        # Escalated cases need human review
        if decision == "escalated":
            return "human_review"

        # Also route borderline cases to human review
        # Even if decision was made, low confidence should be reviewed
        if confidence <= 0.75:  # Changed from < 0.70 to <= 0.75
            return "human_review"

        # High confidence cases proceed automatically
        return "execute_action"

    @trace_node(name="intake", node_type="intake")
    async def _intake_node(self, state: ModerationState) -> ModerationState:
        """Intake node: Validate and prepare content for review."""
        if not state.get("content"):
            state["error"] = "No content provided"
            return state

        state["notification_sent"] = False
        print(f"INTAKE: Processing {state['content_type']} from user {state['user_id']}")
        return state

    @trace_node(name="risk_assessment", node_type="assessment")
    async def _risk_assessment_node(self, state: ModerationState) -> ModerationState:
        """Risk assessment node: Analyze content for violations."""
        print(f"RISK ASSESSMENT: Analyzing content...")

        content = state["content"]

        # Search for similar violations and historical cases
        similar_violations = self.vector_store.search_similar_violations(
            content=content,
            n_results=5,
        )
        similar_historical_cases = self.vector_store.search_similar_cases(
            query=content,
            n_results=5,
        )

        state["similar_violations"] = similar_violations
        state["similar_cases"] = similar_historical_cases

        # Get relevant policies
        relevant_policies = self.vector_store.search_relevant_policies(
            query=content,
            n_results=3,
        )
        state["relevant_policies"] = relevant_policies

        # Load prompt
        prompt_loader = get_prompt_loader()
        system_prompt = prompt_loader.get_moderation_prompt()

        # Build context
        context_info = self._build_context_info(state)

        user_prompt = f"""Content Type: {state['content_type']}

Content:
{content}
{context_info}

Provide your analysis in this exact format:
VIOLATION: [yes/no]
TYPE: [harassment/scams/fake_profile/inappropriate/age_verification/none]
SEVERITY: [low/medium/high/critical]
CONFIDENCE: [0.0-1.0]
REASONING: [detailed explanation]"""

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt),
        ]

        response = await self.llm.ainvoke(messages)
        analysis = response.content

        # Parse LLM response
        parsed = self._parse_llm_response(analysis)

        state["violation_type"] = parsed["violation_type"]
        state["severity"] = parsed["severity"]
        state["confidence"] = parsed["confidence"]
        state["risk_score"] = parsed["risk_score"]
        state["reasoning"] = parsed["reasoning"]

        print(f"   Violation: {parsed['violation_type'] or 'None'}")
        print(f"   Severity: {parsed['severity']}")
        print(f"   Confidence: {parsed['confidence']:.2f}")
        print(f"   Risk Score: {parsed['risk_score']:.2f}")

        return state

    @trace_node(name="decision", node_type="decision")
    async def _decision_node(self, state: ModerationState) -> ModerationState:
        """Decision node: Make initial moderation decision."""
        print(f"DECISION: Making moderation decision...")

        confidence = state["confidence"]
        violation_type = state["violation_type"]
        severity = state["severity"]

        thresholds = self.config["confidence_thresholds"]

        # Determine decision based on confidence
        if violation_type is None:
            decision = "approved"
            action = None
            severity = None
        elif confidence >= thresholds["auto_reject"]:
            decision = "rejected"
            policy_rules = self.config["policy_rules"].get(violation_type, {})
            actions = policy_rules.get("actions", {})
            action = actions.get(severity, "permanent_ban")
        elif confidence >= thresholds["escalate"]:
            decision = "escalated"
            action = "flag_for_review"
        else:
            decision = "pending"
            action = "flag_for_review"

        state["decision"] = decision
        state["action"] = action

        print(f"   Initial Decision: {decision}")
        print(f"   Confidence: {confidence:.2f}")

        # Mark if needs human review
        needs_human = decision in ["escalated", "pending"] or confidence < 0.70
        state["needs_human_review"] = needs_human

        if needs_human:
            print(f"   FLAGGED FOR HUMAN REVIEW (confidence: {confidence:.2f})")

        # IMPORTANT: Add flagged content to vector store NOW (before HITL pause)
        # This ensures subsequent runs can find similar violations even if workflow pauses
        if violation_type and confidence >= 0.5:  # Only add if reasonably confident
            try:
                import uuid
                # Use a temporary ID for vector store (actual case created later)
                temp_case_id = f"flagged_{uuid.uuid4().hex[:8]}"

                self.vector_store.add_flagged_content(
                    content=state.get("content", ""),
                    case_id=temp_case_id,
                    violation_type=violation_type,
                    severity=severity or "medium",
                )
                print(f"   Added to flagged content for pattern detection")
            except Exception as e:
                print(f"   Could not add to vector store: {e}")

        return state

    async def _human_review_node(self, state: ModerationState) -> ModerationState:
        """
        Human review node - WORKFLOW PAUSES HERE.

        This node is never executed automatically due to interrupt_before.
        It only runs after human provides input and workflow is resumed.
        """
        print(f"HUMAN REVIEW: Processing moderator input...")

        # Get human input from state (provided when resuming)
        moderator_decision = state.get("moderator_decision")
        moderator_reasoning = state.get("moderator_reasoning")
        moderator_id = state.get("moderator_id", "moderator_001")

        if moderator_decision:
            # Override agent decision with human decision
            state["decision"] = moderator_decision

            # Safely get original reasoning
            original_reasoning = state.get('reasoning', 'N/A')
            state["reasoning"] = f"MODERATOR OVERRIDE: {moderator_reasoning}\n\nOriginal AI reasoning: {original_reasoning}"
            state["reviewed_by"] = moderator_id

            # Update action based on human decision
            if moderator_decision == "rejected":
                state["action"] = "permanent_ban"
            elif moderator_decision == "approved":
                state["action"] = None

            print(f"   Human Decision: {moderator_decision}")
            print(f"   Moderator: {moderator_id}")

        return state

    @trace_node(name="action", node_type="action")
    async def _action_node(self, state: ModerationState) -> ModerationState:
        """Action node: Execute moderation action."""
        print(f"ACTION: Executing moderation action...")

        # Create case in database if it doesn't exist
        # When resuming from HITL, the case might already exist in DB
        if not state.get("case_id"):
            # Safely get all required fields with defaults
            case_id = await self.db.create_case(
                content_type=state.get("content_type", "message"),
                content=state.get("content", ""),
                user_id=state.get("user_id", "unknown"),
                risk_score=state.get("risk_score", 0.0),
                decision=state.get("decision", "pending"),
                reasoning=state.get("reasoning", "No reasoning provided"),
                confidence=state.get("confidence", 0.0),
                violation_type=state.get("violation_type"),
                severity=state.get("severity"),
                reviewed_by=state.get("reviewed_by", "agent"),
                metadata=state.get("metadata", {}),
            )
            state["case_id"] = case_id
            print(f"   Case created in database: {case_id}")
        else:
            # Case already exists (created by demo or previous run)
            # Update it with final decision
            case_id = state["case_id"]
            await self.db.update_case_decision(
                case_id=case_id,
                decision=state.get("decision", "approved"),
                reasoning=state.get("reasoning", "Updated by workflow"),
                reviewed_by=state.get("reviewed_by", "agent")
            )
            print(f"   Case updated in database: {case_id}")

            # Add to vector store if violation found
            if state.get("violation_type"):
                self.vector_store.add_flagged_content(
                    content=state.get("content", ""),
                    case_id=case_id,
                    violation_type=state["violation_type"],
                    severity=state.get("severity", "medium"),
                )

            # Add to historical cases (all cases)
            reasoning = state.get("reasoning", "No reasoning")
            if state.get("violation_type"):
                case_summary = f"{state['violation_type']} violation (severity: {state.get('severity', 'unknown')}). Decision: {state.get('decision', 'unknown')}. {reasoning[:200]}"
            else:
                case_summary = f"Clean content - approved. {reasoning[:200]}"

            self.vector_store.add_historical_case(
                case_id=case_id,
                case_summary=case_summary,
                decision=state.get("decision", "approved"),
                violation_type=state.get("violation_type") or "none",
                metadata={
                    "confidence": state.get("confidence", 0.0),
                    "content_type": state.get("content_type", "message"),
                    "risk_score": state.get("risk_score", 0.0),
                }
            )

        action = state.get("action")

        if action and action != "flag_for_review":
            print(f"   Executing moderation action: {action}")

            # Record the action in audit log
            async with self.db.get_connection() as conn:
                await self.db._log_audit(
                    conn=conn,
                    case_id=state.get("case_id", "unknown"),
                    action=f"moderation_action_{action}",
                    actor=state.get("reviewed_by", "agent"),
                    details={"action": action, "user_id": state.get("user_id", "unknown")},
                )

            print(f"   Action executed: {action}")

        return state

    @trace_node(name="notification", node_type="notification")
    async def _notification_node(self, state: ModerationState) -> ModerationState:
        """Notification node: Notify user of decision."""
        print(f"NOTIFICATION: Sending decision to user...")

        notification_msg = self._generate_notification_message(state)

        # Log notification
        async with self.db.get_connection() as conn:
            await self.db._log_audit(
                conn=conn,
                case_id=state.get("case_id", "unknown"),
                action="user_notification",
                actor="system",
                details={
                    "user_id": state.get("user_id", "unknown"),
                    "decision": state.get("decision", "unknown"),
                    "message": notification_msg[:200],
                },
            )

        state["notification_sent"] = True
        user_id = state.get("user_id", "unknown")
        print(f"   Notification sent to user {user_id}")

        return state

    def _build_context_info(self, state: ModerationState) -> str:
        """Build context information from similar cases and policies."""
        context_info = ""

        similar_violations = state.get("similar_violations", [])
        if similar_violations:
            context_info += "\n\nSimilar flagged violations found:\n"
            for i, case in enumerate(similar_violations[:3], 1):
                context_info += f"{i}. Similarity: {case['similarity_score']:.2f} - {case['metadata'].get('violation_type', 'unknown')} (severity: {case['metadata'].get('severity', 'unknown')})\n"

        similar_historical = state.get("similar_cases", [])
        if similar_historical:
            context_info += "\n\nSimilar historical cases:\n"
            for i, case in enumerate(similar_historical[:3], 1):
                decision = case['metadata'].get('decision', 'unknown')
                violation = case['metadata'].get('violation_type', 'none')
                context_info += f"{i}. Similarity: {case['similarity_score']:.2f} - Decision: {decision}, Violation: {violation}\n"

        relevant_policies = state.get("relevant_policies", [])
        if relevant_policies:
            context_info += "\n\nRelevant policies:\n"
            for i, policy in enumerate(relevant_policies, 1):
                context_info += f"{i}. {policy['policy_text'][:200]}...\n"

        return context_info

    def _parse_llm_response(self, analysis: str) -> Dict[str, Any]:
        """Parse LLM response into structured format."""
        violation_type = None
        severity = None
        confidence = 0.5
        reasoning = analysis

        try:
            lines = analysis.split("\n")
            for line in lines:
                if line.startswith("VIOLATION:") and "yes" in line.lower():
                    for next_line in lines:
                        if next_line.startswith("TYPE:"):
                            violation_type = next_line.split(":", 1)[1].strip()
                            break
                if line.startswith("SEVERITY:"):
                    sev = line.split(":", 1)[1].strip().lower()
                    if sev in ["low", "medium", "high", "critical"]:
                        severity = sev
                if line.startswith("CONFIDENCE:"):
                    conf_str = line.split(":", 1)[1].strip()
                    confidence = float(conf_str)
                if line.startswith("REASONING:"):
                    reasoning = line.split(":", 1)[1].strip()
        except Exception as e:
            print(f"Warning: Error parsing LLM response: {e}")

        # If no violation, ensure severity is None
        if violation_type is None:
            severity = None

        # Calculate risk score
        severity_scores = {"low": 0.3, "medium": 0.6, "high": 0.8, "critical": 1.0}
        risk_score = min(confidence * severity_scores.get(severity, 0.6), 1.0) if severity else 0.0

        return {
            "violation_type": violation_type,
            "severity": severity,
            "confidence": confidence,
            "risk_score": risk_score,
            "reasoning": reasoning
        }

    def _generate_notification_message(self, state: ModerationState) -> str:
        """Generate user-friendly notification message."""
        decision = state.get("decision", "pending")
        violation_type = state.get("violation_type", "content")

        if decision == "approved":
            return "Your content has been reviewed and approved."
        elif decision == "rejected":
            return f"Your content violates our {violation_type} policy and has been removed. Action: {state.get('action', 'removed')}. You may appeal this decision."
        else:
            return "Your content is under review by our moderation team."

    @trace_agent_workflow(name="moderation_workflow_hitl")
    async def run(
        self,
        state: Dict[str, Any],
        thread_id: Optional[str] = None
    ) -> ModerationState:
        """
        Run the moderation workflow with HITL support.

        Args:
            state: Initial state
            thread_id: Thread ID for checkpointing (use case_id)

        Returns:
            Final state (may be interrupted waiting for human input)
        """
        # Initialize workflow if not already done
        await self.initialize()

        print("\n" + "=" * 60)
        print("MODERATION AGENT WITH HITL")
        print("=" * 60)

        # Create config with thread_id for checkpointing and LangSmith metadata
        config = {
            "configurable": {"thread_id": thread_id or state.get("user_id")},
            "metadata": {
                "content_preview": state.get("content", "")[:100],
                "user_id": state.get("user_id"),
                "content_type": state.get("content_type"),
            },
            "tags": ["moderation", state.get("content_type", "message")],
            "run_name": f"Moderate {state.get('content_type', 'content')} from {state.get('user_id', 'unknown')}"
        }

        result = await self.workflow.ainvoke(state, config=config)

        # Add output metadata for LangSmith
        from langsmith import traceable
        if hasattr(traceable, "get_current_run_tree"):
            try:
                run_tree = traceable.get_current_run_tree()
                if run_tree:
                    run_tree.extra = {
                        **run_tree.extra,
                        "decision": result.get("decision"),
                        "confidence": result.get("confidence"),
                        "violation_type": result.get("violation_type"),
                        "reviewed_by": result.get("reviewed_by", "agent"),
                    }
            except:
                pass

        # Check if workflow was interrupted (paused before human_review)
        # When interrupted, notification_sent won't be set (regardless of decision value)
        # Decision can be "escalated" or "pending" depending on confidence
        if not result.get("notification_sent") and result.get("decision") in ["escalated", "pending"]:
            print("=" * 60)
            print("WORKFLOW PAUSED - Waiting for human review")
            print("=" * 60 + "\n")
            result["status"] = "PAUSED_FOR_HUMAN_REVIEW"
        else:
            print("=" * 60)
            print(f"WORKFLOW: {result.get('status', 'COMPLETED')}")
            print("=" * 60 + "\n")

        return result

    async def resume_with_human_input(
        self,
        thread_id: str,
        moderator_decision: str,
        moderator_reasoning: str,
        moderator_id: str = "moderator_001"
    ) -> ModerationState:
        """
        Resume paused workflow with human input.

        Args:
            thread_id: Thread ID of paused workflow
            moderator_decision: Human decision (approved/rejected/escalated)
            moderator_reasoning: Moderator's reasoning
            moderator_id: ID of moderator

        Returns:
            Final workflow state
        """
        # Initialize workflow if not already done
        await self.initialize()

        print("\n" + "=" * 60)
        print("RESUMING WORKFLOW WITH HUMAN INPUT")
        print("=" * 60)
        print(f"Thread ID: {thread_id}")
        print(f"Decision: {moderator_decision}")
        print(f"Moderator: {moderator_id}")
        print()

        config = {
            "configurable": {"thread_id": thread_id},
            "metadata": {
                "moderator_id": moderator_id,
                "moderator_decision": moderator_decision,
                "moderator_reasoning": moderator_reasoning[:100] if moderator_reasoning else "",
            },
            "tags": ["moderation", "hitl_resume", moderator_decision],
            "run_name": f"HITL Resume: {moderator_decision} by {moderator_id}"
        }

        # First, update the state with human input
        # Use as_node="make_decision" to update state as if decision node provided it
        # This ensures the state update is properly attributed
        self.workflow.update_state(
            config,
            {
                "moderator_decision": moderator_decision,
                "moderator_reasoning": moderator_reasoning,
                "moderator_id": moderator_id
            },
            as_node="make_decision"
        )

        # Resume from checkpoint - pass None to continue with updated state
        try:
            result = await self.workflow.ainvoke(None, config=config)

            print("=" * 60)
            print(f"WORKFLOW COMPLETE - Decision: {result.get('decision')}")
            print(f"   Reviewed By: {result.get('reviewed_by')}")
            print(f"   Case ID: {result.get('case_id')}")
            print("=" * 60 + "\n")

            return result
        except Exception as e:
            print(f"ERROR resuming workflow: {e}")
            raise
