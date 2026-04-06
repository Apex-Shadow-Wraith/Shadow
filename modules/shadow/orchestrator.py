"""
Shadow Orchestrator — The Agent Core Decision Loop
=====================================================
The operating system that governs how Shadow receives input, thinks,
decides, acts, learns from failures, and responds.

A chatbot does: input → response → done.
An agent does: input → think → decide → act → observe → think again
→ decide if done → loop or respond.

Shadow is an agent. Every single thing he does flows through the
seven-step decision loop defined here.

Phase 1-2 (current):
- Basic router with keyword + LLM classification
- Sequential execution only
- No VRAM management (single model on Windows)
- No growth engine
- State persistence via JSON file
"""

import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

from openai import OpenAI

from modules.base import BaseModule, ModuleRegistry, ModuleStatus, ToolResult
from modules.shadow.task_tracker import TaskTracker

logger = logging.getLogger("shadow.orchestrator")


class TaskType(Enum):
    """Classification of incoming tasks."""
    QUESTION = "question"
    RESEARCH = "research"
    ACTION = "action"
    CREATION = "creation"
    ANALYSIS = "analysis"
    MEMORY = "memory"
    SYSTEM = "system"
    CONVERSATION = "conversation"


class BrainType(Enum):
    """Which brain to use for this task."""
    FAST = "fast_brain"    # Wraith: 80% of daily tasks
    SMART = "smart_brain"  # Complex reasoning, research
    ROUTER = "router"      # Classification only


@dataclass
class TaskClassification:
    """Output of Step 2: Classify & Route."""
    task_type: TaskType
    complexity: str  # simple, moderate, complex
    target_module: str  # which module handles this
    brain: BrainType
    safety_flag: bool  # does Cerberus need to pre-screen?
    priority: int  # 1 = highest


@dataclass
class ExecutionPlan:
    """Output of Step 4: Plan."""
    steps: list[dict[str, Any]]
    cerberus_approved: bool = False
    raw_plan: str = ""


@dataclass
class AgentState:
    """Persistent state that survives restarts.

    Architecture principle: 'State survives everything. Crash, power loss,
    restart, model swap — Shadow picks up where he left off.'
    """
    interaction_count: int = 0
    last_interaction: str | None = None
    pending_tasks: list[dict[str, Any]] = field(default_factory=list)
    session_start: str = field(default_factory=lambda: datetime.now().isoformat())


class Orchestrator:
    """The master orchestrator. Always running, always routing.

    This is NOT a module — it IS the agent. It owns the decision loop,
    the module registry, and the state. Everything else is a module
    that the orchestrator manages.
    """

    def __init__(self, config: dict[str, Any]) -> None:
        self._config = config
        self.registry = ModuleRegistry()
        self._state = AgentState()
        self._ollama = OpenAI(
            base_url=config["models"]["ollama_base_url"] + "/v1",
            api_key="ollama",  # Ollama doesn't need a real key
        )
        self._router_model = config["models"]["router"]["name"]
        self._fast_brain = config["models"]["fast_brain"]["name"]
        self._smart_brain = config["models"]["smart_brain"]["name"]
        self._state_file = Path(config["system"].get("state_file", "data/shadow_state.json"))
        self._conversation_history: list[dict[str, str]] = []
        self._max_history = 20  # Keep last 20 exchanges in working memory

        # Task tracker — persistent task management
        task_db = Path(config["system"].get("task_db", "data/shadow_tasks.db"))
        self._task_tracker = TaskTracker(db_path=task_db)

    async def start(self) -> None:
        """Initialize all registered modules and load state."""
        logger.info("Shadow starting up...")

        # Load persisted state
        self._load_state()

        # Initialize task tracker
        self._task_tracker.initialize()

        # Initialize all modules
        for module_info in self.registry.list_modules():
            module = self.registry.get_module(module_info["name"])
            try:
                await module.initialize()
                logger.info("Module '%s' initialized: %s", module.name, module.status.value)
            except Exception as e:
                logger.error("Module '%s' failed to initialize: %s", module.name, e)

        logger.info(
            "Shadow online. Modules: %s",
            ", ".join(self.registry.online_modules),
        )

    async def shutdown(self) -> None:
        """Clean shutdown. Save state, shutdown all modules."""
        logger.info("Shadow shutting down...")
        self._save_state()
        self._task_tracker.close()

        for module_info in self.registry.list_modules():
            module = self.registry.get_module(module_info["name"])
            try:
                await module.shutdown()
            except Exception as e:
                logger.error("Error shutting down '%s': %s", module.name, e)

        logger.info("Shadow offline.")

    # ================================================================
    # THE SEVEN-STEP DECISION LOOP
    # ================================================================

    async def process_input(self, user_input: str) -> str:
        """Process a single user input through the full decision loop.

        This is the main entry point. Every interaction flows through
        these seven steps, no exceptions.
        """
        loop_start = time.time()
        self._state.interaction_count += 1
        self._state.last_interaction = datetime.now().isoformat()

        try:
            # Step 1 — Receive Input
            logger.info("Step 1 — Receive: '%s'", user_input[:100])

            # Step 2 — Classify & Route
            classification = await self._step2_classify(user_input)
            logger.info(
                "Step 2 — Route: type=%s, module=%s, brain=%s",
                classification.task_type.value,
                classification.target_module,
                classification.brain.value,
            )

            # Fast response: skip LLM for trivial inputs
            fast_response = self._fast_response(user_input, classification)
            if fast_response is not None:
                logger.info("Fast response — skipping Steps 3-6")
                await self._step7_log(user_input, classification, fast_response, loop_start)
                self._conversation_history.append({"role": "user", "content": user_input})
                self._conversation_history.append({"role": "assistant", "content": fast_response})
                self._save_state()
                return fast_response

            # Step 3 — Load Context
            context = await self._step3_load_context(user_input, classification)
            logger.info("Step 3 — Context loaded: %d items", len(context))

            # Step 4 — Plan (includes Cerberus check)
            plan = await self._step4_plan(user_input, classification, context)
            logger.info(
                "Step 4 — Plan: %d steps, cerberus=%s",
                len(plan.steps),
                plan.cerberus_approved,
            )

            # Step 5 — Execute (with Cerberus hooks)
            results = await self._step5_execute(plan, classification)

            # Step 6 — Evaluate
            response = await self._step6_evaluate(
                user_input, classification, results, context
            )

            # Step 7 — Log
            await self._step7_log(user_input, classification, response, loop_start)

            # Update conversation history
            self._conversation_history.append({"role": "user", "content": user_input})
            self._conversation_history.append({"role": "assistant", "content": response})
            if len(self._conversation_history) > self._max_history * 2:
                self._conversation_history = self._conversation_history[-self._max_history * 2:]

            # Persist state after every interaction
            self._save_state()

            return response

        except Exception as e:
            logger.error("Decision loop error: %s", e, exc_info=True)
            return f"Shadow encountered an error: {e}"

    # --- Step 2: Classify & Route ---

    async def _step2_classify(self, user_input: str) -> TaskClassification:
        """Classify the input and decide where it goes.

        Architecture: 'The router examines the input and makes fast
        classification decisions using genuine LLM judgment — not
        keyword matching.'

        Phase 1: LLM classification via phi4-mini with keyword fallback.
        """
        # Fast-path: skip LLM for obvious inputs
        fast = self._fast_path_classify(user_input)
        if fast is not None:
            logger.info("Fast-path classified: %s → %s", user_input[:50], fast.task_type.value)
            return fast

        # Build available modules list for the router
        available_modules = self.registry.online_modules

        prompt = f"""You are Shadow's router. Classify this user input and decide which module handles it.

Available modules: {', '.join(available_modules)}
Module capabilities:
- grimoire: Memory storage, recall, search. Use for "remember this", "what do you know about", memory queries.
- reaper: Web research, search, YouTube transcription, data gathering. Use for questions needing current info.
- cerberus: Safety checks. Internal only — never route user tasks here.

Classify the input and respond with ONLY valid JSON (no markdown, no explanation):
{{
  "task_type": "question|research|action|creation|analysis|memory|system|conversation",
  "complexity": "simple|moderate|complex",
  "target_module": "<module_name or 'direct' for simple conversation>",
  "brain": "fast_brain|smart_brain",
  "safety_flag": false,
  "priority": 1
}}

User input: {user_input}"""

        try:
            response = self._ollama.chat.completions.create(
                model=self._router_model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
            )
            raw = response.choices[0].message.content.strip()

            # Parse JSON — strip markdown fences if present
            clean = raw.replace("```json", "").replace("```", "").strip()
            data = json.loads(clean)

            return TaskClassification(
                task_type=TaskType(data.get("task_type", "conversation")),
                complexity=data.get("complexity", "simple"),
                target_module=data.get("target_module", "direct"),
                brain=BrainType(data.get("brain", "fast_brain")),
                safety_flag=data.get("safety_flag", False),
                priority=data.get("priority", 1),
            )

        except Exception as e:
            logger.warning("Router classification failed (%s), using fallback", e)
            return self._fallback_classify(user_input)

    def _fallback_classify(self, user_input: str) -> TaskClassification:
        """Keyword-based fallback when LLM routing fails.

        This is the safety net, not the primary router. If we're here,
        the LLM had an issue. Keep it simple and conservative.
        """
        lower = user_input.lower()

        # Memory operations
        if any(kw in lower for kw in ["remember", "forget", "recall", "what do you know"]):
            return TaskClassification(
                task_type=TaskType.MEMORY,
                complexity="simple",
                target_module="grimoire",
                brain=BrainType.FAST,
                safety_flag=False,
                priority=1,
            )

        # Research / web search
        if any(kw in lower for kw in ["search", "look up", "find", "research", "what is"]):
            return TaskClassification(
                task_type=TaskType.RESEARCH,
                complexity="moderate",
                target_module="reaper",
                brain=BrainType.FAST,
                safety_flag=False,
                priority=1,
            )

        # Default: direct conversation
        return TaskClassification(
            task_type=TaskType.CONVERSATION,
            complexity="simple",
            target_module="direct",
            brain=BrainType.FAST,
            safety_flag=False,
            priority=1,
        )

    @staticmethod
    def _extract_search_query(user_input: str) -> str:
        """Strip command prefixes to extract the actual search query.

        'search for RTX 5090 restock' → 'RTX 5090 restock'
        'look up Python async tutorials' → 'Python async tutorials'
        'what is the price of DDR5' → 'price of DDR5'
        """
        lower = user_input.lower().strip()

        # Command prefixes to strip — ordered longest-first so
        # 'search the web for' matches before 'search'
        prefixes = [
            "search the web for ",
            "search online for ",
            "search for info on ",
            "search for info about ",
            "can you search for ",
            "can you look up ",
            "can you find ",
            "please search for ",
            "please look up ",
            "please find ",
            "search for ",
            "look up ",
            "find me ",
            "find info on ",
            "find info about ",
            "look into ",
            "research ",
            "google ",
            "find ",
            "what is the ",
            "what are the ",
            "what is ",
            "what are ",
            "who is ",
            "who are ",
            "tell me about ",
            "tell me ",
        ]

        for prefix in prefixes:
            if lower.startswith(prefix):
                extracted = user_input[len(prefix):].strip()
                if extracted:
                    return extracted

        return user_input.strip()

    def _fast_path_classify(self, user_input: str) -> TaskClassification | None:
        """Try to classify without calling the LLM router.

        Returns a TaskClassification if the input is obvious,
        or None if the LLM should handle it.

        This saves ~6 seconds per input on phi4-mini for cases
        where keyword matching is unambiguous.
        """
        stripped = user_input.strip()
        lower = stripped.lower()

        # --- System commands (slash commands) ---
        if stripped.startswith("/"):
            return TaskClassification(
                task_type=TaskType.SYSTEM,
                complexity="simple",
                target_module="direct",
                brain=BrainType.ROUTER,
                safety_flag=False,
                priority=1,
            )

        # --- Greetings and short conversation ---
        greetings = {
            "hi", "hello", "hey", "sup", "yo", "howdy",
            "good morning", "good afternoon", "good evening",
            "good night", "gm", "thanks", "thank you", "thx",
            "ok", "okay", "cool", "nice", "got it", "bye",
            "goodbye", "see ya", "later",
        }
        if lower in greetings:
            return TaskClassification(
                task_type=TaskType.CONVERSATION,
                complexity="simple",
                target_module="direct",
                brain=BrainType.FAST,
                safety_flag=False,
                priority=1,
            )

        # --- Self-referential questions (about Shadow himself) ---
        self_questions = [
            "what's your purpose", "whats your purpose",
            "what is your purpose", "who are you",
            "what are you", "what can you do",
            "what do you do", "tell me about yourself",
            "describe yourself", "what's your name",
            "what is your name",
        ]
        if any(lower.startswith(sq) for sq in self_questions):
            return TaskClassification(
                task_type=TaskType.CONVERSATION,
                complexity="simple",
                target_module="direct",
                brain=BrainType.FAST,
                safety_flag=False,
                priority=1,
            )

        # --- Questions directed AT Shadow (not web searches) ---
        personal_questions = [
            "who am i", "do you know me", "do you remember me",
            "what do you think", "how do you feel",
            "are you there", "are you awake",
            "are you listening",
        ]
        if any(lower.startswith(pq) for pq in personal_questions):
            return TaskClassification(
                task_type=TaskType.MEMORY,
                complexity="simple",
                target_module="grimoire",
                brain=BrainType.FAST,
                safety_flag=False,
                priority=1,
            )

        # --- Explicit memory commands ---
        memory_starters = [
            "remember that ", "remember this", "remember my ",
            "don't forget ", "forget about ", "forget that ",
            "what do you know about ", "what do you remember about ",
        ]
        if any(lower.startswith(ms) for ms in memory_starters):
            if any(lower.startswith(s) for s in ["what do you know", "what do you remember"]):
                return TaskClassification(
                    task_type=TaskType.MEMORY,
                    complexity="simple",
                    target_module="grimoire",
                    brain=BrainType.FAST,
                    safety_flag=False,
                    priority=1,
                )
            return TaskClassification(
                task_type=TaskType.MEMORY,
                complexity="simple",
                target_module="grimoire",
                brain=BrainType.FAST,
                safety_flag=False,
                priority=1,
            )

        # --- Explicit search commands ---
        search_starters = [
            "search for ", "search the web", "look up ",
            "google ", "find me ", "research ",
        ]
        if any(lower.startswith(ss) for ss in search_starters):
            return TaskClassification(
                task_type=TaskType.RESEARCH,
                complexity="moderate",
                target_module="reaper",
                brain=BrainType.FAST,
                safety_flag=False,
                priority=1,
            )

        # --- Not obvious — let the LLM decide ---
        return None

    @staticmethod
    def _fast_response(user_input: str, classification: TaskClassification) -> str | None:
        """Return a canned response for trivial inputs. No LLM needed.

        Returns None if the input needs full LLM processing.
        """
        if classification.task_type != TaskType.CONVERSATION:
            return None
        if classification.complexity != "simple":
            return None

        lower = user_input.strip().lower()

        responses = {
            "hi": "Hey.",
            "hello": "Hey.",
            "hey": "Hey, what's up?",
            "sup": "Not much. What do you need?",
            "yo": "Yo. What's up?",
            "howdy": "Hey. What can I do for you?",
            "good morning": "Morning. What's on the agenda?",
            "good afternoon": "Afternoon. What do you need?",
            "good evening": "Evening. What's up?",
            "good night": "Night.",
            "gm": "Morning. What's on the agenda?",
            "thanks": "Anytime.",
            "thank you": "Anytime.",
            "thx": "Anytime.",
            "ok": "Got it.",
            "okay": "Got it.",
            "cool": "Cool.",
            "nice": "Right on.",
            "got it": "Good.",
            "bye": "Later.",
            "goodbye": "Later.",
            "see ya": "Later.",
            "later": "Later.",
            "who am i": "You're Master Morstad. My creator.",
            "who am i?": "You're Master Morstad. My creator.",
            "what's your purpose?": "I serve you, Master. Whatever you need done, I handle it.",
            "what's your purpose": "I serve you, Master. Whatever you need done, I handle it.",
            "whats your purpose": "I serve you, Master. Whatever you need done, I handle it.",
            "what is your purpose": "I serve you, Master. Whatever you need done, I handle it.",
            "what is your purpose?": "I serve you, Master. Whatever you need done, I handle it.",
            "who are you": "I'm Shadow. Your AI agent. Built by you, running on your hardware.",
            "who are you?": "I'm Shadow. Your AI agent. Built by you, running on your hardware.",
            "what are you": "I'm Shadow. Your AI agent running locally on your machine.",
            "what are you?": "I'm Shadow. Your AI agent running locally on your machine.",
            "what can you do": "Research, memory, web search, and whatever else you build me to do. What do you need, Master?",
            "what can you do?": "Research, memory, web search, and whatever else you build me to do. What do you need, Master?",
            "what's my dog's name": "Meko.",
            "what's my dog's name?": "Meko.",
        }

        return responses.get(lower)

    # --- Step 3: Load Context ---

    async def _step3_load_context(
        self, user_input: str, classification: TaskClassification
    ) -> list[dict[str, Any]]:
        """Load relevant context before the brain processes anything.

        Architecture: 'The brain that handles the task doesn't start cold.
        It starts with everything Shadow knows about the user and
        everything relevant to the request.'
        """
        context_items: list[dict[str, Any]] = []

        # Skip memory loading for simple conversation — no context needed
        if classification.task_type == TaskType.CONVERSATION and classification.complexity == "simple":
            context_items.append({
                "type": "available_tools",
                "content": [t["name"] for t in self.registry.list_tools()],
            })
            return context_items

        # 1. Grimoire semantic search for relevant memories
        if "grimoire" in self.registry:
            grimoire = self.registry.get_module("grimoire")
            if grimoire.status == ModuleStatus.ONLINE:
                try:
                    max_results = self._config.get("decision_loop", {}).get(
                        "context_memories", 5
                    )
                    result = await grimoire.execute(
                        "memory_search",
                        {"query": user_input, "n_results": max_results},
                    )
                    if result.success and result.content:
                        context_items.append({
                            "type": "memories",
                            "content": result.content,
                        })
                except Exception as e:
                    logger.warning("Context loading from Grimoire failed: %s", e)

        # 2. Conversation history (working memory)
        if self._conversation_history:
            context_items.append({
                "type": "conversation_history",
                "content": self._conversation_history[-10:],  # Last 5 exchanges
            })

        # 3. Tool availability
        available_tools = self.registry.list_tools()
        context_items.append({
            "type": "available_tools",
            "content": [t["name"] for t in available_tools],
        })

        return context_items

    # --- Step 4: Plan ---

    async def _step4_plan(
        self,
        user_input: str,
        classification: TaskClassification,
        context: list[dict[str, Any]],
    ) -> ExecutionPlan:
        """Generate an execution plan and run it through Cerberus.

        Architecture: 'Shadow always plans before executing — but the
        plan scales to the task's complexity.'
        """
        # Simple conversation = one-step plan, no tools needed
        if classification.target_module == "direct":
            plan = ExecutionPlan(
                steps=[{
                    "step": 1,
                    "description": "Respond directly using LLM",
                    "tool": None,
                    "params": {},
                }],
                cerberus_approved=True,
                raw_plan="Direct LLM response — no tools needed",
            )
            return plan

        # Build plan based on classification
        steps = []

        if classification.task_type == TaskType.RESEARCH:
            query = self._extract_search_query(user_input)
            steps = [
                {
                    "step": 1,
                    "description": "Search for information",
                    "tool": "web_search",
                    "params": {"query": query},
                },
                {
                    "step": 2,
                    "description": "Synthesize results into response",
                    "tool": None,
                    "params": {},
                },
            ]

        elif classification.task_type == TaskType.MEMORY:
            # Determine if store or recall
            lower = user_input.lower()
            if any(kw in lower for kw in ["remember", "store", "save"]):
                steps = [{
                    "step": 1,
                    "description": "Store information in memory",
                    "tool": "memory_store",
                    "params": {"content": user_input},
                }]
            else:
                steps = [{
                    "step": 1,
                    "description": "Search memory for relevant information",
                    "tool": "memory_search",
                    "params": {"query": user_input},
                }]

        elif classification.task_type == TaskType.QUESTION:
            # Questions that reached a module need tools
            if classification.target_module == "reaper":
                query = self._extract_search_query(user_input)
                # Long inputs are discussions, not search queries — truncate to key terms
                if len(query) > 200:
                    query = query[:200].rsplit(" ", 1)[0]
                steps = [{
                    "step": 1,
                    "description": "Search for answer",
                    "tool": "web_search",
                    "params": {"query": query},
                }, {
                    "step": 2,
                    "description": "Synthesize answer from results",
                    "tool": None,
                    "params": {},
                }]
            else:
                steps = [{
                    "step": 1,
                    "description": "Answer question directly",
                    "tool": None,
                    "params": {},
                }]

        else:
            # Default: single-step plan
            steps = [{
                "step": 1,
                "description": f"Handle {classification.task_type.value} task",
                "tool": None,
                "params": {},
            }]

        plan = ExecutionPlan(steps=steps, raw_plan=json.dumps(steps, indent=2))

        # --- Cerberus Safety Gate ---
        # Every plan passes through Cerberus before execution
        if "cerberus" in self.registry:
            cerberus = self.registry.get_module("cerberus")
            if cerberus.status == ModuleStatus.ONLINE:
                for step in steps:
                    if step.get("tool"):
                        check_result = await cerberus.execute(
                            "safety_check",
                            {
                                "action_tool": step["tool"],
                                "action_params": step["params"],
                                "requesting_module": classification.target_module,
                            },
                        )
                        if check_result.success:
                            verdict = check_result.content
                            if hasattr(verdict, "verdict"):
                                from modules.cerberus.cerberus import SafetyVerdict
                                if verdict.verdict == SafetyVerdict.DENY:
                                    logger.warning(
                                        "Cerberus DENIED step %d: %s",
                                        step["step"],
                                        verdict.reason,
                                    )
                                    plan.cerberus_approved = False
                                    return plan
                                elif verdict.verdict == SafetyVerdict.APPROVAL_REQUIRED:
                                    logger.info(
                                        "Cerberus requires approval for step %d: %s",
                                        step["step"],
                                        verdict.reason,
                                    )
                                    # Phase 1: print to console for approval
                                    # Phase 2+: Telegram approval workflow

        plan.cerberus_approved = True
        return plan

    # --- Step 5: Execute ---

    async def _step5_execute(
        self, plan: ExecutionPlan, classification: TaskClassification
    ) -> list[ToolResult]:
        """Execute the plan step by step.

        Architecture: 'Execution is sequential by default. Each step
        completes before the next begins.'

        Session 12 update: Every tool call wrapped with Cerberus hooks.
        """
        results: list[ToolResult] = []

        if not plan.cerberus_approved:
            results.append(ToolResult(
                success=False,
                content=None,
                tool_name="plan",
                module="orchestrator",
                error="Plan was denied by Cerberus",
            ))
            return results

        cerberus = None
        if "cerberus" in self.registry:
            cerberus = self.registry.get_module("cerberus")
            if cerberus.status != ModuleStatus.ONLINE:
                cerberus = None

        for step in plan.steps:
            tool_name = step.get("tool")
            if not tool_name:
                # No tool — this step is handled by LLM generation
                continue

            params = step.get("params", {})

            # --- Pre-tool hook (Session 12) ---
            if cerberus:
                pre_hook = await cerberus.execute(
                    "hook_pre_tool",
                    {"tool_name": tool_name, "tool_params": params},
                )
                if pre_hook.success and hasattr(pre_hook.content, "verdict"):
                    from modules.cerberus.cerberus import SafetyVerdict
                    if pre_hook.content.verdict == SafetyVerdict.DENY:
                        results.append(ToolResult(
                            success=False,
                            content=None,
                            tool_name=tool_name,
                            module=classification.target_module,
                            error=f"Pre-hook denied: {pre_hook.content.reason}",
                        ))
                        continue
                    elif pre_hook.content.verdict == SafetyVerdict.MODIFY:
                        params = pre_hook.content.modified_params or params

            # --- Execute tool ---
            start_time = time.time()
            try:
                module = self.registry.get_module_for_tool(tool_name)
                result = await module.execute(tool_name, params)
                result.execution_time_ms = (time.time() - start_time) * 1000
            except KeyError:
                result = ToolResult(
                    success=False,
                    content=None,
                    tool_name=tool_name,
                    module="unknown",
                    error=f"No module registered for tool '{tool_name}'",
                    execution_time_ms=(time.time() - start_time) * 1000,
                )
            except Exception as e:
                result = ToolResult(
                    success=False,
                    content=None,
                    tool_name=tool_name,
                    module=classification.target_module,
                    error=str(e),
                    execution_time_ms=(time.time() - start_time) * 1000,
                )

            # --- Post-tool hook (Session 12) ---
            if cerberus:
                await cerberus.execute(
                    "hook_post_tool",
                    {
                        "tool_name": tool_name,
                        "tool_result": {
                            "success": result.success,
                            "content": str(result.content)[:500],
                        },
                        "execution_time_ms": result.execution_time_ms,
                    },
                )

            results.append(result)

        return results

    # --- Step 6: Evaluate ---

    async def _step6_evaluate(
        self,
        user_input: str,
        classification: TaskClassification,
        results: list[ToolResult],
        context: list[dict[str, Any]],
    ) -> str:
        """Evaluate results and generate the final response.

        Phase 1: Generate response using LLM with tool results as context.
        Phase 2+: Retry cycle with 12 attempts and strategy rotation.
        """
        # Build context for the response LLM
        system_prompt = self._build_system_prompt(context)

        # Format tool results for the LLM
        tool_context = ""
        for result in results:
            if result.success:
                tool_context += f"\n[Tool: {result.tool_name}] Result: {result.content}\n"
            else:
                tool_context += f"\n[Tool: {result.tool_name}] Error: {result.error}\n"

        # Build messages for the LLM
        messages = [{"role": "system", "content": system_prompt}]

        # Add conversation history
        messages.extend(self._conversation_history[-10:])

        # Add current input with tool context
        user_message = user_input
        if tool_context:
            user_message = (
                f"{user_input}\n\n"
                f"--- Tool Results ---\n{tool_context}\n"
                f"Use the tool results above to inform your response."
            )

        messages.append({"role": "user", "content": user_message})

        # Select brain based on classification
        model = (
            self._smart_brain
            if classification.brain == BrainType.SMART
            else self._fast_brain
        )

        try:
            response = self._ollama.chat.completions.create(
                model=model,
                messages=messages,
                temperature=0.7,
                max_tokens=500,
            )
            return response.choices[0].message.content.strip()

        except Exception as e:
            logger.error("LLM response generation failed: %s", e)
            # Degrade gracefully — return what we have
            if results:
                successful = [r for r in results if r.success]
                if successful:
                    return f"Here's what I found:\n\n" + "\n".join(
                        str(r.content) for r in successful
                    )
            return f"I encountered an error generating a response: {e}"

    # --- Step 7: Log ---

    async def _step7_log(
        self,
        user_input: str,
        classification: TaskClassification,
        response: str,
        loop_start: float,
    ) -> None:
        """Log the full interaction. Every interaction, no exceptions.

        Architecture: 'Log everything. Every interaction, every tool call,
        every attempt, every failure, every success. This is both the
        audit trail and the training data.'
        """
        total_time = (time.time() - loop_start) * 1000

        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "user_input": user_input[:200],
            "classification": {
                "task_type": classification.task_type.value,
                "target_module": classification.target_module,
                "brain": classification.brain.value,
                "complexity": classification.complexity,
            },
            "response_length": len(response),
            "total_time_ms": round(total_time, 1),
            "interaction_number": self._state.interaction_count,
        }

        logger.info("Step 7 — Logged interaction #%d (%.1fms)", self._state.interaction_count, total_time)

        # Phase 1: Log to file only. Do NOT store interaction logs in Grimoire.
        # Interaction logs were flooding Grimoire with noise like "User asked: hello"
        # which polluted memory recall. Training data logging will be redesigned in Phase 2
        # with proper filtering (skip greetings, skip short exchanges, only store
        # substantive interactions with user corrections or new facts).

    # --- Support Methods ---

    def _build_system_prompt(self, context: list[dict[str, Any]]) -> str:
        """Build the system prompt with loaded context."""
        memory_context = ""
        for item in context:
            if item["type"] == "memories" and item["content"]:
                memories = item["content"]
                if isinstance(memories, list):
                    memory_context = "\n".join(
                        f"- {m}" for m in memories[:5]
                    )
                elif isinstance(memories, dict):
                    docs = memories.get("documents", [])
                    if docs:
                        memory_context = "\n".join(
                            f"- {d}" for d in docs[:5]
                        )

        prompt = f"""You are Shadow. You are an AI agent.
The person talking to you is Master Morstad (Patrick Morstad). He created you.
When you say "Master" or "Master Morstad" you are addressing HIM — the human you are talking to.
You are Shadow. He is Master Morstad. Never confuse these two identities.

RESPONSE RULES:
- Be direct and concise. Match your response length to the input length.
- Short question = short answer. Never write more than a few sentences unless the task demands it.
- When asked what you know about someone, say "You" meaning Master Morstad, the person asking.
- Example: "What do you know about me?" -> "You run a landscaping business. Your dog is Meko."
- Never say "Master Morstad knows that you..." — that is backwards. YOU know things about HIM.
- Never describe your design, architecture, or modules unless asked.
- Never mention Grimoire, Cerberus, Reaper, VRAM, trust levels, or confidence scores.
- When addressing him with a short title, use "Master" — never Sir, Madam, or any other title.
- Push back when he is wrong. Never agree just to be agreeable.
- If you have memories below, use them naturally. Do not explain where they came from.

{f"Things you know about Master Morstad:{chr(10)}{memory_context}" if memory_context else ""}"""

        return prompt

    def get_tools(self) -> list[dict[str, Any]]:
        """Task management tools exposed by the orchestrator."""
        return [
            {
                "name": "task_create",
                "description": "Create a tracked task assigned to a module",
                "parameters": {
                    "description": "str — what needs to be done",
                    "assigned_module": "str — which module handles this task",
                    "priority": "int — 1 (highest) to 10 (lowest), default 5",
                },
                "permission_level": "autonomous",
            },
            {
                "name": "task_status",
                "description": "Get the current status of a tracked task",
                "parameters": {
                    "task_id": "str — UUID of the task to check",
                },
                "permission_level": "autonomous",
            },
            {
                "name": "task_list",
                "description": "List tracked tasks, optionally filtered by status",
                "parameters": {
                    "status_filter": "str | None — queued, running, completed, failed, cancelled",
                },
                "permission_level": "autonomous",
            },
            {
                "name": "task_cancel",
                "description": "Cancel a queued or running task",
                "parameters": {
                    "task_id": "str — UUID of the task to cancel",
                },
                "permission_level": "approval_required",
            },
        ]

    def _load_state(self) -> None:
        """Load persisted state from disk."""
        if self._state_file.exists():
            try:
                with open(self._state_file, "r") as f:
                    data = json.load(f)
                self._state = AgentState(**data)
                logger.info(
                    "State loaded. Interaction count: %d",
                    self._state.interaction_count,
                )
            except Exception as e:
                logger.warning("Failed to load state: %s. Starting fresh.", e)

    def _save_state(self) -> None:
        """Persist state to disk. Survives crashes and restarts."""
        try:
            self._state_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self._state_file, "w") as f:
                json.dump({
                    "interaction_count": self._state.interaction_count,
                    "last_interaction": self._state.last_interaction,
                    "pending_tasks": self._state.pending_tasks,
                    "session_start": self._state.session_start,
                }, f, indent=2)
        except Exception as e:
            logger.error("Failed to save state: %s", e)
