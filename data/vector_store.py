"""
Vector store utilities for CupidsShield using ChromaDB.
Handles embeddings and similarity search for pattern detection.
"""

import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer
from typing import List, Dict, Any, Optional
from pathlib import Path
import uuid


class VectorStore:
    """ChromaDB vector store for moderation pattern detection."""

    def __init__(
        self,
        persist_directory: str = "./data/chromadb",
        embedding_model: str = "all-MiniLM-L6-v2",
    ):
        """
        Initialize vector store.

        Args:
            persist_directory: Directory to persist ChromaDB data
            embedding_model: SentenceTransformer model for embeddings
        """
        self.persist_directory = persist_directory
        self._ensure_persist_directory()

        # Initialize ChromaDB client
        self.client = chromadb.PersistentClient(
            path=persist_directory,
            settings=Settings(
                anonymized_telemetry=False,
                allow_reset=True,
            ),
        )

        # Initialize embedding model
        self.embedding_model = SentenceTransformer(embedding_model)

        # Initialize collections
        self._init_collections()

    def _ensure_persist_directory(self):
        """Create persist directory if it doesn't exist."""
        Path(self.persist_directory).mkdir(parents=True, exist_ok=True)

    def _init_collections(self):
        """Initialize ChromaDB collections."""
        # Collection for flagged content embeddings
        self.flagged_content = self.client.get_or_create_collection(
            name="flagged_content_embeddings",
            metadata={"description": "Embeddings of violating content for pattern matching"},
        )

        # Collection for policy embeddings
        self.policy_embeddings = self.client.get_or_create_collection(
            name="policy_embeddings",
            metadata={"description": "Semantic search over T&S policies"},
        )

        # Collection for historical cases
        self.historical_cases = self.client.get_or_create_collection(
            name="historical_cases",
            metadata={"description": "Case summaries for similar case retrieval"},
        )

    def get_embedding(self, text: str) -> List[float]:
        """
        Generate embedding for text.

        Args:
            text: Input text

        Returns:
            Embedding vector as list of floats
        """
        embedding = self.embedding_model.encode(text, convert_to_tensor=False)
        return embedding.tolist()

    # ============= Flagged Content =============

    def add_flagged_content(
        self,
        content: str,
        case_id: str,
        violation_type: str,
        severity: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Add flagged content to vector store for pattern detection.

        Args:
            content: The flagged content text
            case_id: Associated moderation case ID
            violation_type: Type of violation
            severity: Severity level
            metadata: Additional metadata

        Returns:
            Document ID
        """
        doc_id = f"flagged_{uuid.uuid4().hex[:12]}"
        embedding = self.get_embedding(content)

        meta = {
            "case_id": case_id,
            "violation_type": violation_type,
            "severity": severity,
        }
        if metadata:
            meta.update(metadata)

        self.flagged_content.add(
            embeddings=[embedding],
            documents=[content],
            ids=[doc_id],
            metadatas=[meta],
        )

        return doc_id

    def search_similar_violations(
        self,
        content: str,
        violation_type: Optional[str] = None,
        n_results: int = 5,
        min_distance: float = 0.3,
    ) -> List[Dict[str, Any]]:
        """
        Search for similar violations in the vector store.

        Args:
            content: Content to search for
            violation_type: Filter by violation type
            n_results: Number of results to return
            min_distance: Minimum similarity distance threshold

        Returns:
            List of similar violations with metadata
        """
        embedding = self.get_embedding(content)

        where_filter = None
        if violation_type:
            where_filter = {"violation_type": violation_type}

        results = self.flagged_content.query(
            query_embeddings=[embedding],
            n_results=n_results,
            where=where_filter,
        )

        # Format results
        similar_cases = []
        if results["ids"] and results["ids"][0]:
            for i, doc_id in enumerate(results["ids"][0]):
                distance = results["distances"][0][i] if results["distances"] else 1.0

                # Convert distance to similarity score (0-1 range)
                # Using 1/(1+d) formula which works for unbounded distances
                similarity_score = 1.0 / (1.0 + distance)

                # Filter by minimum distance
                if distance < min_distance:
                    similar_cases.append(
                        {
                            "id": doc_id,
                            "content": results["documents"][0][i],
                            "metadata": results["metadatas"][0][i],
                            "distance": distance,
                            "similarity_score": similarity_score,
                        }
                    )

        return similar_cases

    # ============= Historical Cases =============

    def add_historical_case(
        self,
        case_id: str,
        case_summary: str,
        decision: str,
        violation_type: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Add a case summary to historical cases for retrieval.

        Args:
            case_id: Case ID
            case_summary: Summary of the case and reasoning
            decision: Final decision
            violation_type: Type of violation
            metadata: Additional metadata

        Returns:
            Document ID
        """
        doc_id = f"case_{case_id}"
        embedding = self.get_embedding(case_summary)

        meta = {
            "case_id": case_id,
            "decision": decision,
            "violation_type": violation_type,
        }
        if metadata:
            meta.update(metadata)

        self.historical_cases.add(
            embeddings=[embedding],
            documents=[case_summary],
            ids=[doc_id],
            metadatas=[meta],
        )

        return doc_id

    def search_similar_cases(
        self,
        query: str,
        decision: Optional[str] = None,
        violation_type: Optional[str] = None,
        n_results: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Search for similar historical cases.

        Args:
            query: Search query (content or description)
            decision: Filter by decision
            violation_type: Filter by violation type
            n_results: Number of results to return

        Returns:
            List of similar cases with metadata
        """
        embedding = self.get_embedding(query)

        # Build filter
        where_filter = {}
        if decision:
            where_filter["decision"] = decision
        if violation_type:
            where_filter["violation_type"] = violation_type

        results = self.historical_cases.query(
            query_embeddings=[embedding],
            n_results=n_results,
            where=where_filter if where_filter else None,
        )

        # Format results
        similar_cases = []
        if results["ids"] and results["ids"][0]:
            for i, doc_id in enumerate(results["ids"][0]):
                distance = results["distances"][0][i] if results["distances"] else 1.0
                # Convert distance to similarity (0-1 range)
                similarity_score = 1.0 / (1.0 + distance)

                similar_cases.append(
                    {
                        "id": doc_id,
                        "summary": results["documents"][0][i],
                        "metadata": results["metadatas"][0][i],
                        "distance": distance,
                        "similarity_score": similarity_score,
                    }
                )

        return similar_cases

    # ============= Policy Embeddings =============

    def add_policy(
        self, policy_id: str, policy_text: str, category: str, metadata: Optional[Dict] = None
    ) -> str:
        """
        Add a policy to the policy embeddings collection.

        Args:
            policy_id: Unique policy identifier
            policy_text: Full policy text
            category: Policy category
            metadata: Additional metadata

        Returns:
            Document ID
        """
        doc_id = f"policy_{policy_id}"
        embedding = self.get_embedding(policy_text)

        meta = {"policy_id": policy_id, "category": category}
        if metadata:
            meta.update(metadata)

        self.policy_embeddings.add(
            embeddings=[embedding],
            documents=[policy_text],
            ids=[doc_id],
            metadatas=[meta],
        )

        return doc_id

    def search_relevant_policies(
        self, query: str, category: Optional[str] = None, n_results: int = 3
    ) -> List[Dict[str, Any]]:
        """
        Search for relevant policies based on content.

        Args:
            query: Content to find relevant policies for
            category: Filter by policy category
            n_results: Number of results to return

        Returns:
            List of relevant policies
        """
        embedding = self.get_embedding(query)

        where_filter = None
        if category:
            where_filter = {"category": category}

        results = self.policy_embeddings.query(
            query_embeddings=[embedding],
            n_results=n_results,
            where=where_filter,
        )

        # Format results
        policies = []
        if results["ids"] and results["ids"][0]:
            for i, doc_id in enumerate(results["ids"][0]):
                distance = results["distances"][0][i] if results["distances"] else 1.0
                # Convert distance to relevance score (0-1 range)
                relevance_score = 1.0 / (1.0 + distance)

                policies.append(
                    {
                        "id": doc_id,
                        "policy_text": results["documents"][0][i],
                        "metadata": results["metadatas"][0][i],
                        "relevance_score": relevance_score,
                    }
                )

        return policies

    # ============= Utilities =============

    def get_collection_stats(self) -> Dict[str, int]:
        """Get statistics about collections."""
        return {
            "flagged_content_count": self.flagged_content.count(),
            "historical_cases_count": self.historical_cases.count(),
            "policy_count": self.policy_embeddings.count(),
        }

    def reset_collections(self):
        """Reset all collections (use with caution!)."""
        self.client.delete_collection("flagged_content_embeddings")
        self.client.delete_collection("policy_embeddings")
        self.client.delete_collection("historical_cases")
        self._init_collections()
        print("All collections reset")

    def load_sample_policies(self):
        """Load sample T&S policies for demonstration."""
        policies = [
            {
                "id": "harassment_001",
                "text": "Harassment policy: Any content that threatens, intimidates, or bullies another user is prohibited. This includes but is not limited to: direct threats, hate speech, persistent unwanted contact, and sexual harassment.",
                "category": "harassment",
            },
            {
                "id": "scam_001",
                "text": "Financial scam policy: Users are prohibited from requesting money, gift cards, or financial information. This includes romance scams, investment scams, and any form of financial manipulation. Red flags include: rapid intimacy, requests to move off-platform, sob stories, and investment opportunities.",
                "category": "scam",
            },
            {
                "id": "fake_profile_001",
                "text": "Fake profile policy: Users must use authentic photos and information. Prohibited behaviors include: using stock photos, celebrity images, stolen photos, fake names, misrepresenting age, location, or relationship status.",
                "category": "fake_profile",
            },
            {
                "id": "inappropriate_001",
                "text": "Inappropriate content policy: Sexually explicit content, nudity, and graphic violence are prohibited in profiles, messages, and photos. This includes suggestive poses, sexual solicitation, and adult content.",
                "category": "inappropriate",
            },
            {
                "id": "age_verification_001",
                "text": "Age verification policy: All users must be 18 years or older. Red flags for underage users include: mentions of high school, prom, being under 18 in bio, youthful appearance, or evasive answers about age.",
                "category": "age_verification",
            },
        ]

        for policy in policies:
            self.add_policy(
                policy_id=policy["id"],
                policy_text=policy["text"],
                category=policy["category"],
            )

        print(f"Loaded {len(policies)} sample policies")


# Convenience function for CLI usage
def init_vector_store(persist_directory: str = "./data/chromadb"):
    """Initialize vector store and load sample policies."""
    vs = VectorStore(persist_directory=persist_directory)
    vs.load_sample_policies()

    stats = vs.get_collection_stats()
    print(f"Vector store initialized: {stats}")

    return vs


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "init":
        persist_dir = sys.argv[2] if len(sys.argv) > 2 else "./data/chromadb"
        init_vector_store(persist_dir)
    else:
        print("Usage: python -m data.vector_store init [persist_directory]")
