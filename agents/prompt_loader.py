"""
Prompt loader utility for CupidsShield agents.
Loads prompts from the prompts/ directory.
"""

from pathlib import Path
from typing import Dict, Optional


class PromptLoader:
    """Load and manage prompts from files."""

    def __init__(self, prompts_dir: str = "./prompts"):
        self.prompts_dir = Path(prompts_dir)
        self._cache: Dict[str, str] = {}

    def load_prompt(self, category: str, prompt_name: str) -> str:
        """
        Load a prompt from file.

        Args:
            category: Category folder (moderation, appeals)
            prompt_name: Name of the prompt file (without .txt)

        Returns:
            Prompt content as string
        """
        cache_key = f"{category}/{prompt_name}"

        # Check cache first
        if cache_key in self._cache:
            return self._cache[cache_key]

        # Load from file
        prompt_path = self.prompts_dir / category / f"{prompt_name}.txt"

        if not prompt_path.exists():
            raise FileNotFoundError(f"Prompt not found: {prompt_path}")

        with open(prompt_path, "r") as f:
            content = f.read()

        # Cache it
        self._cache[cache_key] = content

        return content

    def get_moderation_prompt(self, violation_type: Optional[str] = None) -> str:
        """
        Get appropriate moderation prompt based on violation type.

        Args:
            violation_type: Type of violation (harassment, scams, fake_profile, etc.)
                           If None, returns comprehensive base prompt covering all types.

        Returns:
            Prompt content
        """
        # If no violation type specified (which is the case during initial analysis),
        # use the comprehensive base prompt that covers ALL violation types
        if violation_type is None:
            try:
                return self.load_prompt("moderation", "base_moderation")
            except FileNotFoundError:
                # Fallback to basic prompt
                return self._get_fallback_moderation_prompt()

        # Map violation types to specific prompts (for specialized analysis)
        prompt_map = {
            "harassment": "harassment_detection",
            "scams": "scam_detection",
            "fake_profile": "fake_profile_analysis",
            "age_verification": "age_verification_check",
        }

        # Use specific prompt if violation type is known
        prompt_name = prompt_map.get(violation_type, "base_moderation")

        try:
            return self.load_prompt("moderation", prompt_name)
        except FileNotFoundError:
            # Fallback to base prompt
            try:
                return self.load_prompt("moderation", "base_moderation")
            except FileNotFoundError:
                return self._get_fallback_moderation_prompt()

    def get_appeals_prompt(self) -> str:
        """Get appeals review prompt."""
        try:
            return self.load_prompt("appeals", "appeal_review")
        except FileNotFoundError:
            return self._get_fallback_appeals_prompt()

    def get_evidence_evaluation_prompt(self) -> str:
        """Get evidence evaluation prompt."""
        try:
            return self.load_prompt("appeals", "evidence_evaluation")
        except FileNotFoundError:
            return self._get_fallback_appeals_prompt()

    def _get_fallback_moderation_prompt(self) -> str:
        """Fallback moderation prompt if files not found."""
        return """You are a Trust & Safety AI agent for a dating platform.

Analyze the provided content and determine:
1. Is there a violation? If so, what type?
2. How severe is it? (low, medium, high, critical)
3. How confident are you? (0.0 to 1.0)
4. Detailed reasoning

Focus on these violation types:
- harassment: Threats, hate speech, bullying
- scams: Financial fraud, pig butchering, romance scams
- fake_profile: Inauthentic photos or information
- inappropriate: Sexual content, nudity
- age_verification: Potential underage users

Provide your analysis in this exact format:
VIOLATION: [yes/no]
TYPE: [harassment/scams/fake_profile/inappropriate/age_verification/none]
SEVERITY: [low/medium/high/critical]
CONFIDENCE: [0.0-1.0]
REASONING: [detailed explanation]"""

    def _get_fallback_appeals_prompt(self) -> str:
        """Fallback appeals prompt if files not found."""
        return """You are reviewing an appeal of a moderation decision.

Evaluate based on these criteria:
1. NEW EVIDENCE (40%): Has substantial new evidence been provided?
2. POLICY MISINTERPRETATION (30%): Was policy potentially misinterpreted?
3. USER EXPLANATION (20%): Is the user's explanation compelling?
4. USER HISTORY (10%): What is the user's track record?

Provide your evaluation as:
NEW_EVIDENCE_SCORE: [0.0-1.0]
POLICY_SCORE: [0.0-1.0]
EXPLANATION_SCORE: [0.0-1.0]
HISTORY_SCORE: [0.0-1.0]
RECOMMENDATION: [overturn/uphold/escalate]
REASONING: [detailed explanation]"""


# Global singleton instance
_prompt_loader = None


def get_prompt_loader() -> PromptLoader:
    """Get global prompt loader instance."""
    global _prompt_loader
    if _prompt_loader is None:
        _prompt_loader = PromptLoader()
    return _prompt_loader
