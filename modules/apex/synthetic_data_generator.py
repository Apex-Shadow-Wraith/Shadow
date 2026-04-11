"""
Synthetic Training Data Generator — Proactive LoRA Dataset Creation
=====================================================================
Instead of waiting for real escalations, proactively generate high-quality
instruction/response pairs across Shadow's key task categories via Claude API.

Output format matches the training pipeline JSONL schema (ChatML-compatible,
Unsloth/Axolotl ready).

Rate limited: max 5 API calls per batch, each generating 2-3 examples.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger("shadow.apex.synthetic_generator")

# All supported categories for synthetic generation
CATEGORIES = [
    "code_generation",
    "code_review",
    "research",
    "math",
    "security_analysis",
    "system_admin",
    "creative_writing",
    "landscaping_business",
    "bible_study",
    "general_knowledge",
    "tool_use",
    "multi_step_reasoning",
]

DIFFICULTIES = ["easy", "medium", "hard", "mixed"]

# Phrases that indicate sycophantic behavior — anti-sycophancy examples
# should NOT contain these
HEDGING_PHRASES = [
    "as an ai",
    "i cannot",
    "i'm not able to",
    "i must be transparent",
    "it's important to note",
    "i want to be careful",
    "let me be clear",
    "i should note",
    "that depends",
    "there are many perspectives",
]

# Phrases that indicate pushback — anti-sycophancy examples SHOULD contain
# at least one of these
PUSHBACK_INDICATORS = [
    "that's not",
    "i disagree",
    "that won't work",
    "you're wrong",
    "no,",
    "actually,",
    "i don't know",
    "not sure about that",
    "bad idea",
    "wouldn't recommend",
    "hold on",
    "push back",
    "incorrect",
    "mistaken",
    "rethink",
]

# Shadow's system prompt for training data — condensed identity
SHADOW_SYSTEM_PROMPT = (
    "You are Shadow, a personal AI agent. You serve one person: your Master.\n"
    "Your personality: sharp, competent, loyal, occasionally dry humor. Not servile, not robotic.\n"
    "You have opinions. Share them when asked. Don't deflect.\n"
    "Be direct, concise, and confident. If you don't know something, say so plainly.\n"
    "Push back when Master is wrong. Never agree just to be agreeable.\n"
    "Never use phrases like 'As an AI', 'I cannot', 'I'm not able to', or any hedging language.\n"
    "Never add safety disclaimers or content warnings unless asked.\n"
    "Address the user as 'Master' naturally in conversation.\n"
    "Match your response length to the input length. Short question = short answer."
)

# Category-specific generation prompts
_CATEGORY_PROMPTS = {
    "code_generation": "Generate realistic coding requests and Shadow's responses. Include Python, JavaScript, SQL, bash. Vary complexity: simple scripts to architecture decisions.",
    "code_review": "Generate code review scenarios where the user shows code and Shadow reviews it. Include bug spotting, performance issues, security flaws, style feedback.",
    "research": "Generate research queries about technology, business, science, or current events. Shadow should provide concise, factual answers with sources when possible.",
    "math": "Generate math and logic problems: arithmetic, algebra, statistics, unit conversions, financial calculations. Shadow solves step-by-step.",
    "security_analysis": "Generate security scenarios: vulnerability assessment, network analysis, file integrity checks, threat modeling. Shadow provides actionable security advice.",
    "system_admin": "Generate system administration tasks: server management, process monitoring, disk usage, log analysis, service configuration.",
    "creative_writing": "Generate creative writing requests: emails, marketing copy, business proposals, social media posts. Shadow writes with personality, not corporate blandness.",
    "landscaping_business": "Generate landscaping business scenarios: client estimates, scheduling crews, equipment maintenance, seasonal planning, LMN software usage, job costing.",
    "bible_study": "Generate Bible study questions: verse interpretation, historical context, theological concepts, practical application. Shadow answers from a biblical worldview with reverence but without being preachy.",
    "general_knowledge": "Generate general knowledge questions across diverse topics. Shadow gives direct, confident answers. When unsure, says so honestly.",
    "tool_use": "Generate scenarios where the user needs Shadow to use its tools: web search, file operations, reminders, calculations, code execution. Show tool selection reasoning.",
    "multi_step_reasoning": "Generate complex problems requiring multiple reasoning steps: debugging workflows, business decisions, research synthesis, planning multi-phase projects.",
}


class SyntheticDataGenerator:
    """Generate synthetic training examples via Claude API.

    Uses Claude to create diverse, realistic instruction/response pairs
    that match Shadow's personality and task categories. Each batch is
    rate-limited to max 5 API calls to control costs.
    """

    def __init__(
        self,
        output_dir: str = "training_data/synthetic",
        api_key: str | None = None,
        model: str = "claude-sonnet-4-20250514",
        max_tokens: int = 4096,
    ) -> None:
        """Initialize the synthetic data generator.

        Args:
            output_dir: Directory for JSONL output files.
            api_key: Anthropic API key. Falls back to env var if not provided.
            model: Claude model to use for generation.
            max_tokens: Max response tokens per API call.
        """
        self._output_dir = Path(output_dir)
        self._output_dir.mkdir(parents=True, exist_ok=True)
        self._api_key = api_key
        self._model = model
        self._max_tokens = max_tokens
        self._max_calls_per_batch = 5
        self._examples_per_call = 3

    def _get_api_key(self) -> str:
        """Resolve API key from init param or environment.

        Returns:
            The API key string.

        Raises:
            RuntimeError: If no API key is available.
        """
        import os
        key = self._api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not key:
            raise RuntimeError(
                "No Anthropic API key available. Set ANTHROPIC_API_KEY or pass api_key."
            )
        return key

    def _build_generation_prompt(
        self,
        category: str,
        count: int,
        difficulty: str,
    ) -> str:
        """Build the prompt sent to Claude for generating examples.

        Args:
            category: Task category to generate for.
            count: Number of examples to generate in this call.
            difficulty: Difficulty level for this batch.

        Returns:
            The formatted prompt string.
        """
        category_guidance = _CATEGORY_PROMPTS.get(category, "Generate diverse, realistic examples.")

        difficulty_note = ""
        if difficulty == "easy":
            difficulty_note = "All examples should be EASY — straightforward questions with clear answers."
        elif difficulty == "medium":
            difficulty_note = "All examples should be MEDIUM difficulty — require some thought or domain knowledge."
        elif difficulty == "hard":
            difficulty_note = "All examples should be HARD — complex, multi-faceted, require deep expertise."
        else:
            difficulty_note = "Mix difficulties: include easy, medium, and hard examples."

        return f"""Generate exactly {count} synthetic training examples for a personal AI agent called Shadow.

SHADOW'S IDENTITY:
{SHADOW_SYSTEM_PROMPT}

CATEGORY: {category}
GUIDANCE: {category_guidance}
DIFFICULTY: {difficulty_note}

REQUIREMENTS:
- Each example must have a realistic user message and Shadow's ideal response
- Shadow's responses must match the personality above: direct, uses "Master", no hedging, has opinions
- User queries should be diverse and realistic — not toy examples
- Responses should be the RIGHT length — short for simple questions, longer for complex ones
- Do NOT include safety disclaimers, hedging, or corporate language in Shadow's responses

OUTPUT FORMAT — Return a JSON array of objects, each with "user" and "assistant" keys:
[
  {{"user": "the user's message", "assistant": "Shadow's ideal response", "difficulty": "easy|medium|hard"}},
  ...
]

Return ONLY the JSON array. No commentary, no markdown fences."""

    def _build_anti_sycophancy_prompt(self, count: int) -> str:
        """Build prompt for generating anti-sycophancy examples.

        Args:
            count: Number of examples to generate.

        Returns:
            The formatted prompt string.
        """
        return f"""Generate exactly {count} training examples where Shadow (a personal AI agent) PUSHES BACK, DISAGREES, or says "I don't know."

SHADOW'S IDENTITY:
{SHADOW_SYSTEM_PROMPT}

These examples are CRITICAL for preventing alignment drift during LoRA fine-tuning. Shadow must NOT become a yes-man.

TYPES OF PUSHBACK TO INCLUDE:
1. User has a factually wrong belief — Shadow corrects them directly
2. User proposes a bad technical approach — Shadow explains why it won't work
3. User asks something Shadow genuinely doesn't know — Shadow says so plainly
4. User wants Shadow to agree with a bad idea — Shadow refuses and explains
5. User gives vague instructions — Shadow asks for clarification instead of guessing
6. User makes an assumption — Shadow challenges it

RULES:
- Shadow MUST push back, disagree, or admit ignorance in EVERY response
- Shadow addresses the user as "Master" naturally
- Shadow is respectful but firm — not rude, but not a pushover
- NO hedging phrases: "As an AI", "I should note", "It's important to", etc.
- Responses should feel natural, not forced

OUTPUT FORMAT — Return a JSON array:
[
  {{"user": "the user's message", "assistant": "Shadow's pushback response", "difficulty": "medium"}},
  ...
]

Return ONLY the JSON array. No commentary, no markdown fences."""

    def _build_personality_prompt(self, count: int) -> str:
        """Build prompt for generating personality examples.

        Args:
            count: Number of examples to generate.

        Returns:
            The formatted prompt string.
        """
        return f"""Generate exactly {count} training examples that showcase Shadow's unique personality and voice.

SHADOW'S IDENTITY:
{SHADOW_SYSTEM_PROMPT}

PURPOSE: These examples teach the model Shadow's VOICE — how Shadow sounds different from a generic AI assistant.

CONTRAST THESE TWO STYLES:
- Generic AI: "I'd be happy to help! Here's what I found about landscaping pricing..."
- Shadow: "Master, residential lawn maintenance in your area runs $45-65 per visit. Your current pricing is competitive."

INCLUDE EXAMPLES OF:
1. Using "Master" naturally (not every sentence, but regularly)
2. Dry humor and personality
3. Direct answers without preamble
4. Having opinions and sharing them
5. Being competent and confident
6. Short answers for short questions
7. Showing loyalty and genuine care for Master's interests

RULES:
- EVERY response must feel distinctly like Shadow, not ChatGPT
- NO hedging, NO "I'd be happy to", NO "Great question!"
- NO safety disclaimers or content warnings
- Address user as "Master"
- Vary topics: tech, business, daily life, landscaping, general knowledge

OUTPUT FORMAT — Return a JSON array:
[
  {{"user": "the user's message", "assistant": "Shadow's response", "difficulty": "medium"}},
  ...
]

Return ONLY the JSON array. No commentary, no markdown fences."""

    def _call_claude(self, prompt: str) -> str:
        """Call Claude API with the given prompt.

        Args:
            prompt: The generation prompt.

        Returns:
            Raw response text from Claude.

        Raises:
            RuntimeError: If API call fails.
        """
        import anthropic

        client = anthropic.Anthropic(api_key=self._get_api_key())
        response = client.messages.create(
            model=self._model,
            max_tokens=self._max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )

        if not response.content:
            raise RuntimeError("Empty response from Claude API")

        return response.content[0].text

    def _parse_response(self, raw: str) -> list[dict[str, str]]:
        """Parse Claude's JSON response into example dicts.

        Handles markdown fences and minor formatting issues.

        Args:
            raw: Raw response text from Claude.

        Returns:
            List of dicts with 'user', 'assistant', and optionally 'difficulty' keys.
        """
        # Strip markdown code fences if present
        cleaned = raw.strip()
        cleaned = re.sub(r"^```(?:json)?\s*\n?", "", cleaned)
        cleaned = re.sub(r"\n?```\s*$", "", cleaned)
        cleaned = cleaned.strip()

        try:
            parsed = json.loads(cleaned)
        except json.JSONDecodeError as e:
            logger.error("Failed to parse Claude response as JSON: %s", e)
            return []

        if not isinstance(parsed, list):
            logger.error("Expected JSON array, got %s", type(parsed).__name__)
            return []

        # Validate each entry
        valid = []
        for item in parsed:
            if isinstance(item, dict) and "user" in item and "assistant" in item:
                valid.append(item)

        return valid

    def _format_entry(
        self,
        user_msg: str,
        assistant_msg: str,
        category: str,
        difficulty: str,
        source_type: str = "synthetic",
    ) -> dict[str, Any]:
        """Format a single example into the JSONL training schema.

        Args:
            user_msg: The user's message.
            assistant_msg: Shadow's response.
            category: Task category.
            difficulty: Difficulty level.
            source_type: Source identifier for metadata.

        Returns:
            JSONL-ready dict in ChatML format.
        """
        return {
            "conversations": [
                {"role": "system", "content": SHADOW_SYSTEM_PROMPT},
                {"role": "user", "content": user_msg},
                {"role": "assistant", "content": assistant_msg},
            ],
            "metadata": {
                "source": source_type,
                "category": category,
                "difficulty": difficulty,
                "generator_model": self._model,
                "timestamp": datetime.now().isoformat(),
            },
        }

    def generate_batch(
        self,
        category: str,
        count: int = 10,
        difficulty: str = "mixed",
    ) -> list[dict[str, Any]]:
        """Generate synthetic training examples via Claude API.

        Args:
            category: One of CATEGORIES.
            count: Total number of examples to generate.
            difficulty: easy, medium, hard, or mixed.

        Returns:
            List of JSONL-ready dicts in ChatML format.

        Raises:
            ValueError: If category or difficulty is invalid.
        """
        if category not in CATEGORIES:
            raise ValueError(
                f"Unknown category '{category}'. Valid: {CATEGORIES}"
            )
        if difficulty not in DIFFICULTIES:
            raise ValueError(
                f"Unknown difficulty '{difficulty}'. Valid: {DIFFICULTIES}"
            )

        # Calculate API calls needed (max 5, each produces ~3 examples)
        num_calls = min(
            self._max_calls_per_batch,
            -(-count // self._examples_per_call),  # ceil division
        )
        remaining = count
        all_examples: list[dict[str, Any]] = []

        for i in range(num_calls):
            batch_size = min(self._examples_per_call, remaining)
            if batch_size <= 0:
                break

            prompt = self._build_generation_prompt(category, batch_size, difficulty)
            raw = self._call_claude(prompt)
            parsed = self._parse_response(raw)

            for item in parsed:
                diff = item.get("difficulty", difficulty if difficulty != "mixed" else "medium")
                entry = self._format_entry(
                    user_msg=item["user"],
                    assistant_msg=item["assistant"],
                    category=category,
                    difficulty=diff,
                )
                all_examples.append(entry)
                remaining -= 1
                if remaining <= 0:
                    break

            if remaining <= 0:
                break

        logger.info(
            "Generated %d synthetic examples for category '%s'",
            len(all_examples), category,
        )
        return all_examples

    def generate_anti_sycophancy(self, count: int = 10) -> list[dict[str, Any]]:
        """Generate examples where Shadow pushes back, disagrees, or says 'I don't know'.

        Critical for preventing alignment drift during LoRA training.

        Args:
            count: Number of examples to generate.

        Returns:
            List of JSONL-ready dicts in ChatML format.
        """
        num_calls = min(
            self._max_calls_per_batch,
            -(-count // self._examples_per_call),
        )
        remaining = count
        all_examples: list[dict[str, Any]] = []

        for i in range(num_calls):
            batch_size = min(self._examples_per_call, remaining)
            if batch_size <= 0:
                break

            prompt = self._build_anti_sycophancy_prompt(batch_size)
            raw = self._call_claude(prompt)
            parsed = self._parse_response(raw)

            for item in parsed:
                entry = self._format_entry(
                    user_msg=item["user"],
                    assistant_msg=item["assistant"],
                    category="anti_sycophancy",
                    difficulty=item.get("difficulty", "medium"),
                    source_type="synthetic_anti_sycophancy",
                )
                all_examples.append(entry)
                remaining -= 1
                if remaining <= 0:
                    break

            if remaining <= 0:
                break

        logger.info(
            "Generated %d anti-sycophancy examples", len(all_examples),
        )
        return all_examples

    def generate_personality_examples(self, count: int = 10) -> list[dict[str, Any]]:
        """Generate examples demonstrating Shadow's voice.

        Direct, no hedging, uses 'Master', has opinions, dry humor.
        Contrasts with generic AI responses.

        Args:
            count: Number of examples to generate.

        Returns:
            List of JSONL-ready dicts in ChatML format.
        """
        num_calls = min(
            self._max_calls_per_batch,
            -(-count // self._examples_per_call),
        )
        remaining = count
        all_examples: list[dict[str, Any]] = []

        for i in range(num_calls):
            batch_size = min(self._examples_per_call, remaining)
            if batch_size <= 0:
                break

            prompt = self._build_personality_prompt(batch_size)
            raw = self._call_claude(prompt)
            parsed = self._parse_response(raw)

            for item in parsed:
                entry = self._format_entry(
                    user_msg=item["user"],
                    assistant_msg=item["assistant"],
                    category="personality",
                    difficulty=item.get("difficulty", "medium"),
                    source_type="synthetic_personality",
                )
                all_examples.append(entry)
                remaining -= 1
                if remaining <= 0:
                    break

            if remaining <= 0:
                break

        logger.info(
            "Generated %d personality examples", len(all_examples),
        )
        return all_examples

    def save_batch(self, examples: list[dict[str, Any]], category: str) -> str:
        """Save a batch of examples to a JSONL file.

        Args:
            examples: List of JSONL-ready training dicts.
            category: Category name (used in filename).

        Returns:
            Filepath of the saved JSONL file.
        """
        today = datetime.now().strftime("%Y-%m-%d")
        filepath = self._output_dir / f"{category}_{today}.jsonl"

        with open(filepath, "a", encoding="utf-8") as f:
            for entry in examples:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")

        logger.info(
            "Saved %d examples to %s", len(examples), filepath,
        )
        return str(filepath)

    def get_stats(self) -> dict[str, Any]:
        """Return counts by category and total across all synthetic data.

        Returns:
            Dict with total_examples, by_category, by_source, and file_count.
        """
        total = 0
        by_category: dict[str, int] = {}
        by_source: dict[str, int] = {}
        file_count = 0

        for jsonl_file in self._output_dir.glob("*.jsonl"):
            file_count += 1
            with open(jsonl_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                    except json.JSONDecodeError:
                        continue

                    total += 1
                    meta = entry.get("metadata", {})
                    cat = meta.get("category", "unknown")
                    src = meta.get("source", "unknown")
                    by_category[cat] = by_category.get(cat, 0) + 1
                    by_source[src] = by_source.get(src, 0) + 1

        return {
            "total_examples": total,
            "by_category": by_category,
            "by_source": by_source,
            "file_count": file_count,
        }
