"""
Problem Fingerprinting — classify problems by structural shape for cross-domain solution transfer.

A CUDA memory layout optimization and a database index optimization have the same
fingerprint (optimization) so the approach transfers across domains.
"""

import hashlib
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone


PROBLEM_SHAPES = {
    "transformation": "Convert X from form A to form B",
    "optimization": "Make X faster/smaller/cheaper while preserving Y",
    "search": "Find X that satisfies conditions Y in space Z",
    "constraint_satisfaction": "Find assignment of variables that satisfies all constraints",
    "classification": "Determine which category X belongs to",
    "generation": "Create new X that has properties Y",
    "diagnosis": "Determine why X is broken/slow/wrong",
    "comparison": "Evaluate differences between X and Y",
    "aggregation": "Combine multiple X into summary Y",
    "decomposition": "Break X into manageable parts",
    "mapping": "Establish correspondence between X and Y",
    "scheduling": "Arrange tasks/resources in time to optimize Z",
    "verification": "Confirm whether X satisfies property Y",
    "repair": "Fix X so it satisfies property Y again",
}

# Keywords that signal each problem shape
SHAPE_KEYWORDS = {
    "transformation": ["convert", "transform", "translate", "format", "parse", "encode", "decode"],
    "optimization": ["optimize", "improve", "faster", "reduce", "minimize", "maximize", "efficient"],
    "search": ["find", "search", "locate", "lookup", "query", "retrieve", "filter"],
    "constraint_satisfaction": ["satisfy", "constraint", "requirement", "must", "within limits"],
    "classification": ["classify", "categorize", "determine type", "which kind", "identify"],
    "generation": ["create", "generate", "write", "build", "compose", "design"],
    "diagnosis": ["debug", "why", "broken", "error", "diagnose", "troubleshoot", "root cause"],
    "comparison": ["compare", "difference", "versus", "vs", "contrast", "better"],
    "aggregation": ["summarize", "combine", "merge", "aggregate", "total", "collect"],
    "decomposition": ["break down", "split", "decompose", "separate", "extract parts"],
    "mapping": ["map", "associate", "link", "correspond", "relate"],
    "scheduling": ["schedule", "plan", "arrange", "order", "sequence", "timeline"],
    "verification": ["verify", "check", "validate", "confirm", "test", "prove"],
    "repair": ["fix", "repair", "patch", "correct", "resolve", "restore"],
}

# Keywords for input/output type detection
INPUT_OUTPUT_KEYWORDS = {
    "code": ["function", "class", "def", "variable", "compile", "code", "script", "method", "module"],
    "data": ["table", "csv", "json", "database", "numbers", "dataset", "rows", "columns", "records"],
    "text": ["write", "essay", "email", "document", "paragraph", "article", "letter", "report"],
    "decision": ["should", "recommend", "choose", "decide", "pick", "select", "which"],
}

# Keywords for complexity indicators
COMPLEXITY_KEYWORDS = {
    "multi-step": ["then", "after", "next", "step"],
    "iterative": ["repeat", "until", "loop", "iterate"],
    "recursive": ["recursive", "nested", "sub-problem"],
    "parallel": ["parallel", "concurrent", "simultaneously"],
}


@dataclass
class ProblemFingerprint:
    """Structural fingerprint of a problem, independent of domain."""

    primary_shape: str
    secondary_shapes: list = field(default_factory=list)
    input_type: str = "mixed"
    output_type: str = "mixed"
    complexity_indicators: list = field(default_factory=list)
    constraints: list = field(default_factory=list)
    domain: str = "general"
    fingerprint_hash: str = ""


class ProblemFingerprinter:
    """Classify problems by structural shape for cross-domain solution transfer."""

    CONSTRAINT_KEYWORDS = {
        "time": ["time", "deadline", "fast", "slow", "latency", "timeout", "seconds", "minutes"],
        "memory": ["memory", "ram", "space", "storage", "bytes", "buffer", "cache"],
        "accuracy": ["accuracy", "precision", "exact", "correct", "error rate", "tolerance"],
        "format": ["format", "schema", "structure", "layout", "template", "specification"],
    }

    def __init__(self, grimoire=None):
        """Initialize with optional Grimoire for solution storage/retrieval."""
        self.grimoire = grimoire

    def fingerprint(self, task: str, task_type: str = None) -> ProblemFingerprint:
        """
        Classify a task by structural shape using rule-based keyword analysis.

        Args:
            task: The task description to fingerprint.
            task_type: Optional hint about task type.

        Returns:
            ProblemFingerprint with structural classification.
        """
        if not task or not task.strip():
            fp = ProblemFingerprint(
                primary_shape="generation",
                secondary_shapes=[],
                input_type="mixed",
                output_type="mixed",
                complexity_indicators=[],
                constraints=[],
                domain="general",
            )
            fp.fingerprint_hash = self._compute_hash(fp)
            return fp

        task_lower = task.lower()

        # Score each shape by keyword matches
        shape_scores = {}
        for shape, keywords in SHAPE_KEYWORDS.items():
            score = 0
            for keyword in keywords:
                if keyword in task_lower:
                    score += 1
            if score > 0:
                shape_scores[shape] = score

        # Determine primary and secondary shapes
        if shape_scores:
            sorted_shapes = sorted(shape_scores.items(), key=lambda x: x[1], reverse=True)
            primary_shape = sorted_shapes[0][0]
            secondary_shapes = [s[0] for s in sorted_shapes[1:]]
        else:
            primary_shape = "generation"
            secondary_shapes = []

        # Detect input type
        input_type = self._detect_io_type(task_lower)

        # Detect output type — use task_type hint if provided
        if task_type and task_type in INPUT_OUTPUT_KEYWORDS:
            output_type = task_type
        else:
            output_type = self._detect_io_type(task_lower)

        # Detect complexity indicators
        complexity_indicators = self._detect_complexity(task_lower)

        # Detect constraints
        constraints = self._detect_constraints(task_lower)

        # Detect domain
        domain = self._detect_domain(task_lower)

        fp = ProblemFingerprint(
            primary_shape=primary_shape,
            secondary_shapes=secondary_shapes,
            input_type=input_type,
            output_type=output_type,
            complexity_indicators=complexity_indicators,
            constraints=constraints,
            domain=domain,
        )
        fp.fingerprint_hash = self._compute_hash(fp)
        return fp

    def find_similar_solutions(self, fingerprint: ProblemFingerprint, n_results: int = 5) -> list:
        """
        Search Grimoire for solutions with matching fingerprint or similar shape.

        Cross-domain matching is the whole point — never filter by domain.

        Args:
            fingerprint: The problem fingerprint to match against.
            n_results: Maximum number of results to return.

        Returns:
            List of dicts with matching solutions, ranked by shape match strength.
        """
        if not self.grimoire:
            return []

        results = []

        # Search by fingerprint hash first (exact structural match)
        try:
            hash_results = self.grimoire.recall(
                query=f"fingerprint:{fingerprint.fingerprint_hash} shape:{fingerprint.primary_shape}",
                n_results=n_results,
                category="fingerprinted_solution",
            )
            results.extend(hash_results)
        except Exception:
            pass

        # Also search by primary shape description for broader matches
        if len(results) < n_results:
            try:
                shape_desc = PROBLEM_SHAPES.get(fingerprint.primary_shape, fingerprint.primary_shape)
                shape_results = self.grimoire.recall(
                    query=f"{fingerprint.primary_shape} problem: {shape_desc}",
                    n_results=n_results - len(results),
                    category="fingerprinted_solution",
                )
                # Deduplicate by ID
                existing_ids = {r.get("id") for r in results}
                for r in shape_results:
                    if r.get("id") not in existing_ids:
                        results.append(r)
            except Exception:
                pass

        # Rank by shape match strength, recency, trust
        results = self._rank_results(results, fingerprint)

        return results[:n_results]

    def store_with_fingerprint(self, solution: str, task: str,
                                fingerprint: ProblemFingerprint, grimoire=None) -> str:
        """
        Store a solution in Grimoire with fingerprint metadata.

        Args:
            solution: The solution text to store.
            task: The original task description.
            fingerprint: The problem fingerprint.
            grimoire: Optional Grimoire override (uses self.grimoire if None).

        Returns:
            Document ID from Grimoire.
        """
        store = grimoire or self.grimoire
        if not store:
            return ""

        metadata = {
            "primary_shape": fingerprint.primary_shape,
            "secondary_shapes": ",".join(fingerprint.secondary_shapes),
            "fingerprint_hash": fingerprint.fingerprint_hash,
            "domain": fingerprint.domain,
            "input_type": fingerprint.input_type,
            "output_type": fingerprint.output_type,
            "complexity_indicators": ",".join(fingerprint.complexity_indicators),
            "constraints": ",".join(fingerprint.constraints),
            "original_task": task,
            "stored_at": datetime.now(timezone.utc).isoformat(),
        }

        try:
            doc_id = store.remember(
                content=solution,
                source_module="problem_fingerprint",
                category="fingerprinted_solution",
                tags=["fingerprinted", fingerprint.primary_shape, fingerprint.domain],
                metadata=metadata,
            )
            return doc_id
        except Exception:
            return ""

    def get_cross_domain_matches(self, task: str) -> list:
        """
        Fingerprint a task and find solutions from different domains.

        Combined convenience: fingerprint -> find_similar_solutions -> filter cross-domain.

        Args:
            task: The task description to find cross-domain solutions for.

        Returns:
            List of dicts with cross-domain matches and adaptation hints.
        """
        fp = self.fingerprint(task)
        similar = self.find_similar_solutions(fp)

        cross_domain = []
        for result in similar:
            result_domain = ""
            if isinstance(result.get("metadata"), dict):
                result_domain = result["metadata"].get("domain", "")
            elif isinstance(result.get("metadata"), str):
                # Handle serialized metadata
                try:
                    import json
                    meta = json.loads(result["metadata"])
                    result_domain = meta.get("domain", "")
                except (json.JSONDecodeError, TypeError):
                    pass

            # Only include cross-domain matches
            if result_domain and result_domain != fp.domain:
                shape_desc = PROBLEM_SHAPES.get(fp.primary_shape, fp.primary_shape)
                result["adaptation_hint"] = (
                    f"This {result_domain} solution uses the same "
                    f"{fp.primary_shape} pattern: {shape_desc}"
                )
                cross_domain.append(result)

        return cross_domain

    def get_fingerprint_stats(self) -> dict:
        """
        Get distribution of problem shapes and cross-domain match stats.

        Returns:
            Dict with shape distribution, cross-domain success rate, and common shapes per domain.
        """
        stats = {
            "shape_distribution": {shape: 0 for shape in PROBLEM_SHAPES},
            "cross_domain_match_rate": 0.0,
            "shapes_per_domain": {},
            "total_fingerprinted": 0,
        }

        if not self.grimoire:
            return stats

        try:
            all_solutions = self.grimoire.recall(
                query="fingerprinted solution",
                n_results=100,
                category="fingerprinted_solution",
            )
        except Exception:
            return stats

        if not all_solutions:
            return stats

        stats["total_fingerprinted"] = len(all_solutions)
        cross_domain_matches = 0

        for sol in all_solutions:
            meta = sol.get("metadata", {})
            if isinstance(meta, str):
                try:
                    import json
                    meta = json.loads(meta)
                except (json.JSONDecodeError, TypeError):
                    meta = {}

            shape = meta.get("primary_shape", "generation")
            domain = meta.get("domain", "general")

            if shape in stats["shape_distribution"]:
                stats["shape_distribution"][shape] += 1

            if domain not in stats["shapes_per_domain"]:
                stats["shapes_per_domain"][domain] = {}
            if shape not in stats["shapes_per_domain"][domain]:
                stats["shapes_per_domain"][domain][shape] = 0
            stats["shapes_per_domain"][domain][shape] += 1

            # Check for cross-domain usage
            fp_hash = meta.get("fingerprint_hash", "")
            orig_domain = meta.get("domain", "")
            if orig_domain and orig_domain != "general":
                cross_domain_matches += 1

        if stats["total_fingerprinted"] > 0:
            stats["cross_domain_match_rate"] = cross_domain_matches / stats["total_fingerprinted"]

        return stats

    # ── Private helpers ──

    def _detect_io_type(self, task_lower: str) -> str:
        """Detect input/output type from task keywords."""
        scores = {}
        for io_type, keywords in INPUT_OUTPUT_KEYWORDS.items():
            score = sum(1 for kw in keywords if kw in task_lower)
            if score > 0:
                scores[io_type] = score

        if scores:
            return max(scores, key=scores.get)
        return "mixed"

    def _detect_complexity(self, task_lower: str) -> list:
        """Detect complexity indicators from task keywords."""
        indicators = []
        for indicator, keywords in COMPLEXITY_KEYWORDS.items():
            for kw in keywords:
                if kw in task_lower:
                    indicators.append(indicator)
                    break
        return indicators

    def _detect_constraints(self, task_lower: str) -> list:
        """Detect constraint types from task keywords."""
        constraints = []
        for constraint, keywords in self.CONSTRAINT_KEYWORDS.items():
            for kw in keywords:
                if kw in task_lower:
                    constraints.append(constraint)
                    break
        return constraints

    def _detect_domain(self, task_lower: str) -> str:
        """Detect the problem domain from task content."""
        domain_keywords = {
            "database": ["database", "sql", "query", "table", "index", "schema", "postgresql", "mysql", "sqlite"],
            "web": ["html", "css", "javascript", "react", "vue", "angular", "frontend", "backend", "api", "http"],
            "gpu": ["cuda", "gpu", "vram", "tensor", "kernel", "shader", "graphics"],
            "networking": ["network", "tcp", "udp", "socket", "packet", "dns", "firewall", "port"],
            "ml": ["model", "training", "inference", "neural", "embedding", "dataset", "epoch", "gradient"],
            "devops": ["deploy", "docker", "container", "kubernetes", "ci/cd", "pipeline", "terraform"],
            "security": ["encrypt", "decrypt", "auth", "token", "vulnerability", "exploit", "firewall"],
            "business": ["invoice", "estimate", "client", "crew", "schedule", "revenue", "profit", "cost"],
            "python": ["python", "pip", "pytest", "django", "flask", "pandas", "numpy"],
        }

        scores = {}
        for domain, keywords in domain_keywords.items():
            score = sum(1 for kw in keywords if kw in task_lower)
            if score > 0:
                scores[domain] = score

        if scores:
            return max(scores, key=scores.get)
        return "general"

    def _compute_hash(self, fp: ProblemFingerprint) -> str:
        """Compute deterministic hash from structural properties (not domain)."""
        hash_input = (
            f"{fp.primary_shape}|"
            f"{','.join(sorted(fp.secondary_shapes))}|"
            f"{fp.input_type}|{fp.output_type}|"
            f"{','.join(sorted(fp.complexity_indicators))}|"
            f"{','.join(sorted(fp.constraints))}"
        )
        return hashlib.sha256(hash_input.encode()).hexdigest()[:16]

    def _rank_results(self, results: list, fingerprint: ProblemFingerprint) -> list:
        """Rank results by shape match strength, recency, and trust."""
        def score_result(result):
            score = 0.0
            meta = result.get("metadata", {})
            if isinstance(meta, str):
                try:
                    import json
                    meta = json.loads(meta)
                except (json.JSONDecodeError, TypeError):
                    meta = {}

            # Exact hash match is strongest signal
            if meta.get("fingerprint_hash") == fingerprint.fingerprint_hash:
                score += 10.0

            # Primary shape match
            if meta.get("primary_shape") == fingerprint.primary_shape:
                score += 5.0

            # Secondary shape overlap
            result_secondary = meta.get("secondary_shapes", "")
            if isinstance(result_secondary, str):
                result_secondary = [s.strip() for s in result_secondary.split(",") if s.strip()]
            overlap = set(result_secondary) & set(fingerprint.secondary_shapes)
            score += len(overlap) * 1.0

            # Trust level
            trust = result.get("trust_level", 0.5)
            if isinstance(trust, (int, float)):
                score += trust

            # Relevance from vector search
            relevance = result.get("relevance", 0.0)
            if isinstance(relevance, (int, float)):
                score += relevance * 2.0

            return score

        return sorted(results, key=score_result, reverse=True)
