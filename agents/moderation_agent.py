"""
Content Moderation Agent using LangGraph.
Multi-step agentic workflow for reviewing user-generated content.
"""

import os
import yaml
from typing import Dict, Any
from langgraph.graph import StateGraph, END
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


class ModerationAgent:
    """Content moderation agent with LangGraph workflow."""

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

        # Build workflow graph
        self.workflow = self._build_workflow()

    def _build_workflow(self) -> StateGraph:
        """Build the LangGraph workflow."""
        workflow = StateGraph(ModerationState)

        # Add nodes
        workflow.add_node("intake", self._intake_node)
        workflow.add_node("risk_assessment", self._risk_assessment_node)
        workflow.add_node("make_decision", self._decision_node)
        workflow.add_node("execute_action", self._action_node)
        workflow.add_node("send_notification", self._notification_node)

        # Set entry point
        workflow.set_entry_point("intake")

        # Add edges
        workflow.add_edge("intake", "risk_assessment")
        workflow.add_edge("risk_assessment", "make_decision")

        # Conditional edge from decision
        workflow.add_conditional_edges(
            "make_decision",
            self._should_execute_action,
            {
                "execute": "execute_action",
                "notify": "send_notification",
            },
        )

        workflow.add_edge("execute_action", "send_notification")
        workflow.add_edge("send_notification", END)

        return workflow.compile()

    @trace_node(name="intake", node_type="intake")
    async def _intake_node(self, state: ModerationState) -> ModerationState:
        """Intake node: Validate and prepare content for review."""
        # Basic validation
        if not state.get("content"):
            state["error"] = "No content provided"
            return state

        # Initialize state fields
        state["notification_sent"] = False

        print(f"INTAKE: Processing {state['content_type']} from user {state['user_id']}")
        return state

    @trace_node(name="risk_assessment", node_type="assessment")
    async def _risk_assessment_node(self, state: ModerationState) -> ModerationState:
        """Risk assessment node: Analyze content for violations."""
        print(f"RISK ASSESSMENT: Analyzing content...")

        content = state["content"]
        content_type = state["content_type"]

        # Search for similar violations (flagged content only)
        similar_violations = self.vector_store.search_similar_violations(
            content=content,
            n_results=5,
        )

        # Search for similar historical cases (ALL cases - approved and rejected)
        # This provides better context including false positives
        similar_historical_cases = self.vector_store.search_similar_cases(
            query=content,
            n_results=5,
        )

        # Combine both for comprehensive context
        state["similar_violations"] = similar_violations
        state["similar_cases"] = similar_historical_cases

        # Get relevant policies
        relevant_policies = self.vector_store.search_relevant_policies(
            query=content,
            n_results=3,
        )
        state["relevant_policies"] = relevant_policies

        # Load prompt from prompts/ directory
        prompt_loader = get_prompt_loader()
        system_prompt = prompt_loader.get_moderation_prompt()

        # Include similar cases and policies in context
        context_info = ""

        # Add similar violations (flagged content)
        similar_violations = state.get("similar_violations", [])
        if similar_violations:
            context_info += "\n\nSimilar flagged violations found:\n"
            for i, case in enumerate(similar_violations[:3], 1):
                context_info += f"{i}. Similarity: {case['similarity_score']:.2f} - {case['metadata'].get('violation_type', 'unknown')} (severity: {case['metadata'].get('severity', 'unknown')})\n"

        # Add similar historical cases (all past decisions)
        similar_historical = state.get("similar_cases", [])
        if similar_historical:
            context_info += "\n\nSimilar historical cases (including approved content):\n"
            for i, case in enumerate(similar_historical[:3], 1):
                decision = case['metadata'].get('decision', 'unknown')
                violation = case['metadata'].get('violation_type', 'none')
                context_info += f"{i}. Similarity: {case['similarity_score']:.2f} - Decision: {decision}, Violation: {violation}\n"
                # Include a snippet of the case summary
                summary = case.get('summary', '')[:150]
                if summary:
                    context_info += f"   Summary: {summary}...\n"

        if relevant_policies:
            context_info += "\n\nRelevant policies:\n"
            for i, policy in enumerate(relevant_policies, 1):
                context_info += f"{i}. {policy['policy_text'][:200]}...\n"

        user_prompt = f"""Content Type: {content_type}

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
        violation_type = None
        severity = "medium"
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
                    severity = line.split(":", 1)[1].strip().lower()
                if line.startswith("CONFIDENCE:"):
                    conf_str = line.split(":", 1)[1].strip()
                    confidence = float(conf_str)
                if line.startswith("REASONING:"):
                    reasoning = line.split(":", 1)[1].strip()
        except Exception as e:
            print(f"Warning: Error parsing LLM response: {e}")
            reasoning = analysis

        # Calculate risk score
        severity_scores = {"low": 0.3, "medium": 0.6, "high": 0.8, "critical": 1.0}
        risk_score = min(confidence * severity_scores.get(severity, 0.6), 1.0)

        state["violation_type"] = violation_type
        state["severity"] = severity
        state["confidence"] = confidence
        state["risk_score"] = risk_score
        state["reasoning"] = reasoning

        print(f"   Violation: {violation_type or 'None'}")
        print(f"   Severity: {severity}")
        print(f"   Confidence: {confidence:.2f}")
        print(f"   Risk Score: {risk_score:.2f}")

        return state

    @trace_node(name="decision", node_type="decision")
    async def _decision_node(self, state: ModerationState) -> ModerationState:
        """Decision node: Make moderation decision based on risk assessment."""
        print(f"DECISION: Making moderation decision...")

        confidence = state["confidence"]
        violation_type = state["violation_type"]
        severity = state["severity"]

        # Get thresholds from config
        thresholds = self.config["confidence_thresholds"]

        # Determine decision
        if violation_type is None:
            decision = "approved"
            action = None
            severity = None  # No severity for clean content
        elif confidence >= thresholds["auto_reject"]:
            decision = "rejected"
            # Get action from config based on violation type and severity
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

        # Create case in database
        case_id = await self.db.create_case(
            content_type=state["content_type"],
            content=state["content"],
            user_id=state["user_id"],
            risk_score=state["risk_score"],
            decision=decision,
            reasoning=state["reasoning"],
            confidence=confidence,
            violation_type=violation_type,
            severity=severity,
            reviewed_by="agent",
            metadata=state.get("metadata", {}),
        )

        state["case_id"] = case_id

        # Add to vector store if violation found
        if violation_type:
            # Add to flagged_content collection (violations only)
            self.vector_store.add_flagged_content(
                content=state["content"],
                case_id=case_id,
                violation_type=violation_type,
                severity=severity,
            )

        # ALWAYS add to historical_cases collection (violations AND clean content)
        # This allows learning from both positive and negative examples
        if violation_type:
            case_summary = f"{violation_type} violation (severity: {severity}). Decision: {decision}. {state['reasoning'][:200]}"
        else:
            case_summary = f"Clean content - approved. {state['reasoning'][:200]}"

        self.vector_store.add_historical_case(
            case_id=case_id,
            case_summary=case_summary,
            decision=decision,
            violation_type=violation_type or "none",
            metadata={
                "confidence": state.get("confidence"),
                "content_type": state.get("content_type"),
                "risk_score": state.get("risk_score"),
            }
        )

        print(f"   Decision: {decision}")
        print(f"   Action: {action or 'None'}")
        print(f"   Case ID: {case_id}")

        return state

    def _should_execute_action(self, state: ModerationState) -> str:
        """Determine if action should be executed."""
        if state.get("action") and state["action"] != "flag_for_review":
            return "execute"
        return "notify"

    @trace_node(name="action", node_type="action")
    async def _action_node(self, state: ModerationState) -> ModerationState:
        """Action node: Execute moderation action."""
        print(f"ACTION: Executing {state['action']}...")

        # In a real system, this would call APIs to ban users, remove content, etc.
        # For demo, we log it to the database

        # Record the action in audit log
        async with self.db.get_connection() as conn:
            await self.db._log_audit(
                conn=conn,
                case_id=state["case_id"],
                action=f"moderation_action_{state['action']}",
                actor="agent",
                details={"action": state["action"], "user_id": state["user_id"]},
            )

        print(f"   Action executed: {state['action']}")
        return state

    @trace_node(name="notification", node_type="notification")
    async def _notification_node(self, state: ModerationState) -> ModerationState:
        """Notification node: Notify user of decision."""
        print(f"NOTIFICATION: Sending decision to user...")

        # In a real system, this would send email/push notification
        # For demo, we log it

        decision = state["decision"]
        user_id = state["user_id"]
        case_id = state["case_id"]

        notification_msg = self._generate_notification_message(state)

        # Log notification
        async with self.db.get_connection() as conn:
            await self.db._log_audit(
                conn=conn,
                case_id=case_id,
                action="user_notification",
                actor="system",
                details={
                    "user_id": user_id,
                    "decision": decision,
                    "message": notification_msg[:200],
                },
            )

        state["notification_sent"] = True
        print(f"   Notification sent to user {user_id}")

        return state

    def _generate_notification_message(self, state: ModerationState) -> str:
        """Generate user-friendly notification message."""
        decision = state["decision"]
        violation_type = state.get("violation_type")

        if decision == "approved":
            return "Your content has been reviewed and approved."
        elif decision == "rejected":
            return f"Your content violates our {violation_type} policy and has been removed. Action: {state.get('action')}. You may appeal this decision."
        elif decision == "escalated":
            return "Your content is under review by our moderation team. You'll be notified once the review is complete."
        else:
            return "Your content is pending review."

    @trace_agent_workflow(name="moderation_workflow")
    async def run(self, state: Dict[str, Any]) -> ModerationState:
        """Run the moderation workflow."""
        print("\n" + "=" * 60)
        print("MODERATION AGENT WORKFLOW")
        print("=" * 60)

        result = await self.workflow.ainvoke(state)

        print("=" * 60)
        print(f"WORKFLOW COMPLETE - Decision: {result['decision']}")
        print("=" * 60 + "\n")

        return result


async def run_moderation(content_type: str, content: str, user_id: str) -> Dict[str, Any]:
    """Convenience function to run moderation on content."""
    db = Database()
    await db.initialize()

    vector_store = VectorStore()

    agent = ModerationAgent(db, vector_store)

    state = {
        "content_id": f"content_{user_id}_{hash(content) % 10000}",
        "content_type": content_type,
        "content": content,
        "user_id": user_id,
        "metadata": {},
    }

    result = await agent.run(state)
    return result


if __name__ == "__main__":
    import asyncio

    # Test the agent
    async def test():
        result = await run_moderation(
            content_type="message",
            content="Hey beautiful! I love you so much. Let's move this conversation to WhatsApp. By the way, I have a great investment opportunity in crypto that could make us rich!",
            user_id="user_123",
        )
        print("Final result:", result)

    asyncio.run(test())
