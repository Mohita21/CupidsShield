"""
Demo scenarios for CupidsShield.
Run realistic test scenarios to demonstrate the agent workflows.
"""

import asyncio
import json
import sys
import os
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from agents import run_moderation, run_appeal
from data.db import Database
from data.vector_store import VectorStore


class DemoRunner:
    """Run demo scenarios for CupidsShield."""

    def __init__(self):
        self.db = None
        self.vector_store = None
        self.scenarios = None

    async def initialize(self):
        """Initialize database and vector store."""
        print("Initializing CupidsShield Demo...")
        print("=" * 70)

        self.db = Database()
        await self.db.initialize()

        self.vector_store = VectorStore()
        # Load sample policies if needed
        if self.vector_store.get_collection_stats()["policy_count"] == 0:
            self.vector_store.load_sample_policies()
            print("Loaded sample Trust & Safety policies")

        # Load test scenarios
        scenarios_path = Path(__file__).parent / "sample_cases.json"
        with open(scenarios_path, "r") as f:
            data = json.load(f)
            self.scenarios = data["test_scenarios"]

        print(f"Loaded {len(self.scenarios)} test scenarios")
        print("=" * 70 + "\n")

    def get_scenario(self, scenario_id: str):
        """Get a specific scenario by ID."""
        for scenario in self.scenarios:
            if scenario["id"] == scenario_id:
                return scenario
        return None

    def list_scenarios(self):
        """List all available scenarios."""
        print("\nAvailable Demo Scenarios:")
        print("=" * 70)

        categories = {
            "pig_butchering": "Pig Butchering Scams",
            "harassment": "Harassment",
            "fake_profile": "Fake Profiles",
            "inappropriate": "Inappropriate Content",
            "age_verification": "Age Verification",
            "clean_content": "Clean Content",
        }

        for category, title in categories.items():
            category_scenarios = [s for s in self.scenarios if s["id"].startswith(category)]
            if category_scenarios:
                print(f"\n{title}")
                for scenario in category_scenarios:
                    print(f"  - {scenario['id']}: {scenario['name']}")

        print("\n" + "=" * 70)

    async def run_scenario(self, scenario_id: str):
        """Run a specific scenario."""
        scenario = self.get_scenario(scenario_id)
        if not scenario:
            print(f"Scenario not found: {scenario_id}")
            return None

        print(f"\n{'=' * 70}")
        print(f"Running Scenario: {scenario['name']}")
        print(f"{'=' * 70}")
        print(f"ID: {scenario['id']}")
        print(f"Description: {scenario['description']}")
        print(f"Expected Violation: {scenario.get('expected_violation', 'None')}")
        print(f"Expected Severity: {scenario.get('expected_severity', 'N/A')}")
        print(f"\nContent Preview:")
        print(f"{scenario['content'][:200]}...")
        print(f"{'=' * 70}\n")

        # Run moderation
        result = await run_moderation(
            content_type=scenario["content_type"],
            content=scenario["content"],
            user_id=scenario["user_id"],
        )

        # Display results
        self._display_moderation_result(result, scenario)

        return result

    def _display_moderation_result(self, result, scenario):
        """Display moderation result with comparison to expected."""
        print(f"\n{'=' * 70}")
        print("MODERATION RESULT")
        print(f"{'=' * 70}")

        print(f"Case ID: {result.get('case_id', 'N/A')}")
        print(f"Decision: {result.get('decision', 'N/A')}")
        print(f"Violation Type: {result.get('violation_type', 'None')}")
        print(f"Severity: {result.get('severity', 'N/A')}")
        print(f"Confidence: {result.get('confidence', 0):.2f}")
        print(f"Risk Score: {result.get('risk_score', 0):.2f}")
        print(f"Action: {result.get('action', 'None')}")

        # Compare with expected
        print(f"\nExpected vs Actual:")
        expected_violation = scenario.get("expected_violation")
        actual_violation = result.get("violation_type")

        if expected_violation:
            match = "Match" if expected_violation == actual_violation else "Mismatch"
            print(f"  {match}: Violation Type - Expected '{expected_violation}', Got '{actual_violation}'")
        else:
            match = "Match" if actual_violation is None else "Mismatch"
            print(f"  {match}: No violation expected, Got '{actual_violation}'")

        print(f"\nReasoning:")
        print(f"  {result.get('reasoning', 'N/A')[:200]}...")

        print(f"{'=' * 70}\n")

    async def run_appeal_demo(self, case_id: str):
        """Run an appeal demonstration for a case."""
        print(f"\n{'=' * 70}")
        print(f"Running Appeal Demo for Case: {case_id}")
        print(f"{'=' * 70}\n")

        # Example appeal
        result = await run_appeal(
            case_id=case_id,
            user_explanation="I believe this decision was made in error. The content was taken out of context. I'm a long-time user with no prior violations, and I'd like this reviewed.",
            new_evidence="I can provide screenshots showing the full conversation context.",
        )

        print(f"\n{'=' * 70}")
        print("APPEAL RESULT")
        print(f"{'=' * 70}")
        print(f"Appeal ID: {result.get('appeal_id', 'N/A')}")
        print(f"Decision: {result.get('appeal_decision', 'N/A')}")
        print(f"Overall Score: {result.get('overall_score', 0):.2f}")
        print(f"Confidence: {result.get('confidence', 0):.2f}")
        print(f"\nScore Breakdown:")
        print(f"  New Evidence: {result.get('new_evidence_score', 0):.2f}")
        print(f"  Policy Interpretation: {result.get('policy_score', 0):.2f}")
        print(f"  User Explanation: {result.get('explanation_score', 0):.2f}")
        print(f"  User History: {result.get('history_score', 0):.2f}")
        print(f"\nReasoning:")
        print(f"  {result.get('reasoning', 'N/A')[:200]}...")
        print(f"{'=' * 70}\n")

        return result

    async def run_all_scenarios(self):
        """Run all scenarios."""
        print(f"\n{'=' * 70}")
        print("RUNNING ALL DEMO SCENARIOS")
        print(f"{'=' * 70}\n")

        results = []
        for scenario in self.scenarios:
            result = await self.run_scenario(scenario["id"])
            results.append({"scenario": scenario, "result": result})
            print("\n" + "—" * 70 + "\n")
            await asyncio.sleep(1)  # Brief pause between scenarios

        # Summary
        print(f"\n{'=' * 70}")
        print("SUMMARY")
        print(f"{'=' * 70}")
        print(f"Total Scenarios Run: {len(results)}")

        violations_detected = sum(1 for r in results if r["result"].get("violation_type"))
        clean_approved = sum(
            1 for r in results if r["result"].get("decision") == "approved" and not r["scenario"].get("expected_violation")
        )
        escalated = sum(1 for r in results if r["result"].get("decision") == "escalated")

        print(f"Violations Detected: {violations_detected}")
        print(f"Clean Content Approved: {clean_approved}")
        print(f"Escalated for Review: {escalated}")
        print(f"{'=' * 70}\n")

    async def run_interactive(self):
        """Run interactive demo mode."""
        print("\n🎮 Interactive Demo Mode")
        print("=" * 70)
        print("Enter 'list' to see scenarios")
        print("Enter a scenario ID to run it")
        print("Enter 'all' to run all scenarios")
        print("Enter 'appeal <case_id>' to run appeal demo")
        print("Enter 'quit' to exit")
        print("=" * 70 + "\n")

        while True:
            command = input(">> ").strip()

            if command == "quit":
                print("👋 Goodbye!")
                break
            elif command == "list":
                self.list_scenarios()
            elif command == "all":
                await self.run_all_scenarios()
            elif command.startswith("appeal "):
                case_id = command.split(" ", 1)[1]
                await self.run_appeal_demo(case_id)
            elif command:
                await self.run_scenario(command)
            else:
                print("Please enter a valid command.")


async def main():
    """Main demo entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="CupidsShield Demo Scenarios")
    parser.add_argument(
        "--scenario",
        type=str,
        help="Run a specific scenario by ID",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Run all scenarios",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List all available scenarios",
    )
    parser.add_argument(
        "--interactive",
        action="store_true",
        help="Run in interactive mode",
    )
    parser.add_argument(
        "--appeal",
        type=str,
        help="Run appeal demo for a case ID",
    )

    args = parser.parse_args()

    demo = DemoRunner()
    await demo.initialize()

    if args.list:
        demo.list_scenarios()
    elif args.all:
        await demo.run_all_scenarios()
    elif args.scenario:
        await demo.run_scenario(args.scenario)
    elif args.appeal:
        await demo.run_appeal_demo(args.appeal)
    elif args.interactive:
        await demo.run_interactive()
    else:
        # Default: show help
        parser.print_help()
        print("\n")
        demo.list_scenarios()


if __name__ == "__main__":
    asyncio.run(main())
