"""
Appeals Agent using LangGraph.
Multi-step agentic workflow for reviewing user appeals of moderation decisions.
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

from agents.state import AppealsState
from agents.prompt_loader import get_prompt_loader
from data.db import Database
from data.vector_store import VectorStore
from monitoring.tracing import trace_agent_workflow, trace_node


class AppealsAgent:
    """Appeals review agent with LangGraph workflow."""

    def __init__(
        self,
        db: Database,
        vector_store: VectorStore,
        config_path: str = "./config/appeals_config.yaml",
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
        workflow = StateGraph(AppealsState)

        # Add nodes
        workflow.add_node("intake", self._intake_node)
        workflow.add_node("retrieve_context", self._context_retrieval_node)
        workflow.add_node("evaluate", self._evaluation_node)
        workflow.add_node("make_decision", self._decision_node)
        workflow.add_node("resolve", self._resolution_node)

        # Set entry point
        workflow.set_entry_point("intake")

        # Add edges
        workflow.add_edge("intake", "retrieve_context")
        workflow.add_edge("retrieve_context", "evaluate")
        workflow.add_edge("evaluate", "make_decision")
        workflow.add_edge("make_decision", "resolve")
        workflow.add_edge("resolve", END)

        return workflow.compile()

    async def _intake_node(self, state: AppealsState) -> AppealsState:
        """Intake node: Validate appeal and prepare for review."""
        print(f"APPEAL INTAKE: Processing appeal {state.get('appeal_id', 'new')}")

        # Initialize state fields
        state["notification_sent"] = False
        state["case_updated"] = False

        # If no appeal_id, create appeal
        if not state.get("appeal_id"):
            appeal_id = await self.db.create_appeal(
                case_id=state["case_id"],
                user_explanation=state["user_explanation"],
                new_evidence=state.get("new_evidence"),
            )
            state["appeal_id"] = appeal_id
            print(f"   Created appeal: {appeal_id}")

        return state

    @trace_node(name="context_retrieval", node_type="retrieval")
    async def _context_retrieval_node(self, state: AppealsState) -> AppealsState:
        """Context retrieval node: Get original case and user history."""
        print(f"CONTEXT RETRIEVAL: Gathering case information...")

        case_id = state["case_id"]

        # Get original case
        original_case = await self.db.get_case(case_id)
        if not original_case:
            state["error"] = f"Original case not found: {case_id}"
            return state

        state["original_case"] = original_case
        state["original_decision"] = original_case["decision"]
        state["original_reasoning"] = original_case["reasoning"]

        # Get user history
        user_id = original_case["user_id"]
        user_history = await self.db.get_cases_by_user(user_id)
        state["user_history"] = {
            "user_id": user_id,
            "total_cases": len(user_history),
            "cases": user_history[:5],  # Last 5 cases
        }

        # Search for similar cases
        similar_cases = self.vector_store.search_similar_cases(
            query=original_case["content"],
            violation_type=original_case.get("violation_type"),
            n_results=3,
        )
        state["similar_cases"] = similar_cases

        print(f"   Original case: {case_id}")
        print(f"   Original decision: {state['original_decision']}")
        print(f"   User history: {len(user_history)} total cases")
        print(f"   Similar cases found: {len(similar_cases)}")

        return state

    @trace_node(name="evaluation", node_type="assessment")
    async def _evaluation_node(self, state: AppealsState) -> AppealsState:
        """Evaluation node: Evaluate appeal based on criteria."""
        print(f"EVALUATION: Analyzing appeal...")

        # Load prompt from prompts/ directory
        prompt_loader = get_prompt_loader()
        system_prompt = prompt_loader.get_appeals_prompt()

        original_case = state["original_case"]
        user_history = state["user_history"]

        context = f"""ORIGINAL CASE:
Content Type: {original_case['content_type']}
Content: {original_case['content']}
Violation Type: {original_case.get('violation_type', 'N/A')}
Decision: {original_case['decision']}
Original Reasoning: {state['original_reasoning']}
Confidence: {original_case['confidence']:.2f}

USER APPEAL:
Explanation: {state['user_explanation']}
New Evidence: {state.get('new_evidence', 'None provided')}

USER HISTORY:
Total Cases: {user_history['total_cases']}
Recent Violations: {len([c for c in user_history['cases'] if c['decision'] == 'rejected'])}"""

        if state.get("similar_cases"):
            context += "\n\nSIMILAR HISTORICAL CASES:\n"
            for i, case in enumerate(state["similar_cases"][:2], 1):
                context += f"{i}. Decision: {case['metadata'].get('decision', 'unknown')} (similarity: {case['similarity_score']:.2f})\n"

        user_prompt = f"""{context}

Evaluate this appeal and provide scores (0.0 to 1.0) for each criterion:

NEW_EVIDENCE_SCORE: [0.0-1.0]
POLICY_SCORE: [0.0-1.0]
EXPLANATION_SCORE: [0.0-1.0]
HISTORY_SCORE: [0.0-1.0]
RECOMMENDATION: [overturn/uphold/escalate]
REASONING: [detailed explanation]"""

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt),
        ]

        response = await self.llm.ainvoke(messages)
        evaluation = response.content

        # Parse evaluation
        new_evidence_score = 0.0
        policy_score = 0.0
        explanation_score = 0.0
        history_score = 0.0
        reasoning = evaluation

        try:
            lines = evaluation.split("\n")
            for line in lines:
                if line.startswith("NEW_EVIDENCE_SCORE:"):
                    new_evidence_score = float(line.split(":", 1)[1].strip())
                elif line.startswith("POLICY_SCORE:"):
                    policy_score = float(line.split(":", 1)[1].strip())
                elif line.startswith("EXPLANATION_SCORE:"):
                    explanation_score = float(line.split(":", 1)[1].strip())
                elif line.startswith("HISTORY_SCORE:"):
                    history_score = float(line.split(":", 1)[1].strip())
                elif line.startswith("REASONING:"):
                    reasoning = line.split(":", 1)[1].strip()
        except Exception as e:
            print(f"Warning: Error parsing evaluation: {e}")

        # Calculate weighted overall score
        criteria = self.config["evaluation_criteria"]
        overall_score = (
            new_evidence_score * criteria["new_evidence"]["weight"]
            + policy_score * criteria["policy_misinterpretation"]["weight"]
            + explanation_score * criteria["user_explanation"]["weight"]
            + history_score * criteria["user_history"]["weight"]
        )

        state["new_evidence_score"] = new_evidence_score
        state["policy_score"] = policy_score
        state["explanation_score"] = explanation_score
        state["history_score"] = history_score
        state["overall_score"] = overall_score
        state["confidence"] = overall_score  # Use overall score as confidence
        state["reasoning"] = reasoning

        print(f"   New Evidence: {new_evidence_score:.2f}")
        print(f"   Policy Interpretation: {policy_score:.2f}")
        print(f"   User Explanation: {explanation_score:.2f}")
        print(f"   User History: {history_score:.2f}")
        print(f"   Overall Score: {overall_score:.2f}")

        return state

    @trace_node(name="appeal_decision", node_type="decision")
    async def _decision_node(self, state: AppealsState) -> AppealsState:
        """Decision node: Make final decision on appeal."""
        print(f"DECISION: Making appeal decision...")

        overall_score = state["overall_score"]
        thresholds = self.config["confidence_thresholds"]

        # Determine decision based on thresholds
        if overall_score >= thresholds["auto_overturn"]:
            decision = "overturned"
        elif overall_score >= thresholds["escalate"]:
            decision = "escalated"
        else:
            decision = "upheld"

        state["appeal_decision"] = decision

        print(f"   Appeal Decision: {decision}")
        return state

    @trace_node(name="resolution", node_type="action")
    async def _resolution_node(self, state: AppealsState) -> AppealsState:
        """Resolution node: Resolve appeal and update records."""
        print(f"RESOLUTION: Finalizing appeal...")

        appeal_id = state["appeal_id"]
        decision = state["appeal_decision"]
        reasoning = state["reasoning"]
        confidence = state["confidence"]

        # Resolve appeal in database
        await self.db.resolve_appeal(
            appeal_id=appeal_id,
            decision=decision,
            reasoning=reasoning,
            resolved_by="agent",
            confidence=confidence,
        )

        # If overturned, update original case
        if decision == "overturned":
            case_id = state["case_id"]
            await self.db.update_case_decision(
                case_id=case_id,
                decision="approved",
                reasoning=f"Appeal overturned. {reasoning}",
                reviewed_by="agent",
            )
            state["case_updated"] = True
            print(f"   Original case updated: {case_id}")

        # Log to audit trail
        async with self.db.get_connection() as conn:
            await self.db._log_audit(
                conn=conn,
                case_id=state["case_id"],
                appeal_id=appeal_id,
                action=f"appeal_{decision}",
                actor="agent",
                details={
                    "decision": decision,
                    "overall_score": state["overall_score"],
                    "reasoning": reasoning[:200],
                },
            )

        # Send notification (simulated)
        user_id = state["original_case"]["user_id"]
        print(f"   Notification sent to user {user_id}")
        state["notification_sent"] = True

        print(f"   Appeal resolved: {decision}")
        return state

    @trace_agent_workflow(name="appeals_workflow")
    async def run(self, state: Dict[str, Any]) -> AppealsState:
        """Run the appeals workflow."""
        print("\n" + "=" * 60)
        print("APPEALS AGENT WORKFLOW")
        print("=" * 60)

        result = await self.workflow.ainvoke(state)

        print("=" * 60)
        print(f"WORKFLOW COMPLETE - Decision: {result.get('appeal_decision', 'error')}")
        print("=" * 60 + "\n")

        return result


async def run_appeal(case_id: str, user_explanation: str, new_evidence: str = None) -> Dict[str, Any]:
    """Convenience function to run an appeal."""
    db = Database()
    await db.initialize()

    vector_store = VectorStore()

    agent = AppealsAgent(db, vector_store)

    state = {
        "case_id": case_id,
        "user_explanation": user_explanation,
        "new_evidence": new_evidence,
    }

    result = await agent.run(state)
    return result


if __name__ == "__main__":
    import asyncio

    # Test the agent
    async def test():
        # First create a test case to appeal
        from agents.moderation_agent import run_moderation

        # Create a case
        mod_result = await run_moderation(
            content_type="message",
            content="You're ugly and stupid!",
            user_id="user_456",
        )

        case_id = mod_result["case_id"]
        print(f"\n\nNow testing appeal for case: {case_id}\n\n")

        # Appeal it
        appeal_result = await run_appeal(
            case_id=case_id,
            user_explanation="I was responding to someone who called me those names first. This was taken out of context. I normally don't talk like this.",
            new_evidence="The other person messaged me first saying these exact words. I was just repeating what they said to show them how hurtful it was.",
        )

        print("Final appeal result:", appeal_result)

    asyncio.run(test())
