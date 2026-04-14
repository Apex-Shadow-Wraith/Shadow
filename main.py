"""
Shadow — Main Entry Point
===========================
Run this to start Shadow:
    python main.py

Interactive CLI loop. Type a message, Shadow classifies it, routes
it to the right module, and responds. Type 'quit' or 'exit' to stop.
Type '/status' to see module health. Type '/stats' to see Cerberus stats.

This is Phase 1: Windows development build. The interfaces match the
final Ubuntu architecture — nothing gets rebuilt later.
"""

import asyncio
import logging
import os
import platform
import re
import sys
from difflib import get_close_matches
from pathlib import Path

import yaml

from modules.base import ModuleRegistry, ModuleStatus
from modules.shadow.ollama_supervisor import OllamaSupervisor
from modules.shadow.orchestrator import Orchestrator
from modules.shadow.shadow_module import ShadowModule
from modules.shadow.standing_tasks import StandingTaskScheduler

# Module imports — graceful degradation if any module fails to import.
# Logger not yet configured at import time, so collect failures for later.
_IMPORT_FAILURES: list[tuple[str, str, str]] = []

def _try_import(module_path: str, class_name: str):
    """Import a module class, returning None on failure."""
    try:
        mod = __import__(module_path, fromlist=[class_name])
        return getattr(mod, class_name)
    except Exception as e:
        _IMPORT_FAILURES.append((module_path, class_name, str(e)))
        return None

Apex = _try_import("modules.apex.apex", "Apex")
Cerberus = _try_import("modules.cerberus.cerberus", "Cerberus")
Cipher = _try_import("modules.cipher.cipher", "Cipher")
GrimoireModule = _try_import("modules.grimoire.grimoire_module", "GrimoireModule")
Harbinger = _try_import("modules.harbinger.harbinger", "Harbinger")
Morpheus = _try_import("modules.morpheus.morpheus", "Morpheus")
Nova = _try_import("modules.nova.nova", "Nova")
Omen = _try_import("modules.omen.omen", "Omen")
ReaperModule = _try_import("modules.reaper.reaper_module", "ReaperModule")
Sentinel = _try_import("modules.sentinel.sentinel", "Sentinel")
Void = _try_import("modules.void.void", "Void")
Wraith = _try_import("modules.wraith.wraith", "Wraith")


def setup_logging(level: str = "INFO") -> None:
    """Configure logging. Every interaction is logged from day one."""
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)

    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s | %(name)-20s | %(levelname)-7s | %(message)s",
        datefmt="%H:%M:%S",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(log_dir / "shadow.log", encoding="utf-8"),
        ],
    )


def load_config(config_path: str = "config/shadow_config.yaml") -> dict:
    """Load master configuration."""
    path = Path(config_path)
    if not path.exists():
        print(f"ERROR: Config file not found: {path}")
        print("Run from the Shadow project root (C:\\Shadow)")
        sys.exit(1)

    with open(path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    # Resolve platform auto-detection
    system_cfg = config.get("system", {})
    if system_cfg.get("platform", "").lower() == "auto":
        system_cfg["platform"] = platform.system().lower()  # "windows" or "linux"

    return config


async def startup(config: dict, logger: logging.Logger) -> Orchestrator:
    """Create, wire, and initialize everything in the right order.

    Dependency chain: Reaper needs Grimoire's internal object,
    so Grimoire must initialize first. Sequence:
    1. Create all module instances
    2. Initialize Grimoire (creates the actual Grimoire object)
    3. Wire Grimoire's internal object into Reaper
    4. Initialize Cerberus and Reaper
    5. Register all modules with the orchestrator
    6. Load orchestrator state
    """
    module_configs = config.get("modules", {})

    # Log any import failures detected at module load time
    for mod_path, cls_name, err in _IMPORT_FAILURES:
        logger.warning("Import failed — %s.%s: %s", mod_path, cls_name, err)

    # Step 1: Create module instances (skip any that failed to import)
    # --- Core (always running) ---
    grimoire = GrimoireModule(module_configs.get("grimoire", {})) if GrimoireModule else None
    cerberus = Cerberus(module_configs.get("cerberus", {})) if Cerberus else None

    # --- Operations ---
    wraith_config = dict(module_configs.get("wraith", {}))
    wraith_config.setdefault("timezone", config.get("system", {}).get("timezone", "America/Chicago"))
    wraith = Wraith(wraith_config) if Wraith else None
    reaper = ReaperModule(module_configs.get("reaper", {})) if ReaperModule else None
    harbinger = Harbinger(module_configs.get("harbinger", {})) if Harbinger else None

    # --- Specialized ---
    apex = Apex(module_configs.get("apex", {})) if Apex else None
    cipher = Cipher(module_configs.get("cipher", {})) if Cipher else None
    omen = Omen(module_configs.get("omen", {})) if Omen else None
    sentinel = Sentinel(module_configs.get("sentinel", {})) if Sentinel else None
    void = Void(module_configs.get("void", {})) if Void else None
    nova = Nova(module_configs.get("nova", {})) if Nova else None
    morpheus = Morpheus(module_configs.get("morpheus", {})) if Morpheus else None

    # Step 2: Initialize Grimoire first (Reaper depends on it)
    if grimoire is not None:
        try:
            await grimoire.initialize()
            logger.info("Grimoire initialized: %s", grimoire.status.value)
        except Exception as e:
            logger.error("Grimoire failed to initialize: %s", e)
    else:
        logger.error("Grimoire failed to import — memory system unavailable")

    # Step 3: Wire Grimoire's internal object into Reaper
    if grimoire is not None and grimoire._grimoire is not None and reaper is not None:
        reaper._grimoire_instance = grimoire._grimoire
        logger.info("Reaper wired to Grimoire")
    else:
        logger.warning("Grimoire not available — Reaper will start without memory")

    # Step 4: Initialize remaining modules
    all_modules = [
        m for m in [
            cerberus, wraith, reaper, harbinger,
            apex, cipher, omen, sentinel, void, nova, morpheus,
        ] if m is not None
    ]
    for module in all_modules:
        try:
            await module.initialize()
            logger.info("Module '%s' initialized: %s", module.name, module.status.value)
        except Exception as e:
            logger.error("Module '%s' failed to initialize: %s", module.name, e)

    # Step 5: Create orchestrator and register modules
    orchestrator = Orchestrator(config)
    registerable = ([grimoire] if grimoire else []) + all_modules
    for module in registerable:
        orchestrator.registry.register(module)
        logger.info("Registered module: %s", module.name)

    if _IMPORT_FAILURES:
        logger.error(
            "DEGRADED START: %d module(s) failed to import: %s",
            len(_IMPORT_FAILURES),
            ", ".join(cls for _, cls, _ in _IMPORT_FAILURES),
        )

    # Step 5b: Register ShadowModule (task tracking + health)
    shadow_mod = ShadowModule(
        config={"db_path": config.get("system", {}).get("tasks_db", "data/shadow_tasks.db")},
        registry=orchestrator.registry,
    )
    await shadow_mod.initialize()
    orchestrator.registry.register(shadow_mod)
    logger.info("Registered module: %s", shadow_mod.name)

    # Step 6: Load orchestrator state
    orchestrator._load_state()

    # Step 6b: Initialize task subsystem (tracker → queue → async worker)
    orchestrator._task_tracker.initialize()
    if orchestrator._task_queue is not None:
        try:
            orchestrator._task_queue.initialize()
        except Exception as e:
            logger.warning("PriorityTaskQueue failed to initialize: %s", e)
            orchestrator._task_queue = None

    try:
        from modules.shadow.async_tasks import AsyncTaskQueue as _AsyncTaskQueue
    except ImportError:
        _AsyncTaskQueue = None
        logger.warning("AsyncTaskQueue not available — background tasks disabled")

    if _AsyncTaskQueue is not None and orchestrator._task_queue is not None:
        try:
            orchestrator._async_task_queue = _AsyncTaskQueue(
                task_queue=orchestrator._task_queue,
                task_tracker=orchestrator._task_tracker,
                registry=orchestrator.registry,
            )
            await orchestrator._async_task_queue.start()
            logger.info("AsyncTaskQueue initialized and worker started")
        except Exception as e:
            logger.warning("AsyncTaskQueue failed to initialize: %s", e)
            orchestrator._async_task_queue = None

    # Step 7: Initialize inter-module communication
    try:
        await orchestrator._initialize_communication()
        logger.info("Inter-module communication initialized")
    except Exception as e:
        logger.error("Failed to initialize inter-module communication: %s", e)

    # Step 8: Rebuild tool loader index now that all modules are registered and online
    if orchestrator._tool_loader is not None:
        orchestrator._tool_loader.refresh()
        report = orchestrator._tool_loader.get_loading_report()
        logger.info(
            "Tool loader index rebuilt: %d modules, %d tools",
            len(orchestrator._tool_loader._index),
            report.get("tools_available", 0),
        )

    return orchestrator


# All known CLI commands (without the slash) for fuzzy matching.
# Commands that take arguments list only the base word.
KNOWN_COMMANDS = ["status", "tools", "stats", "tasks", "task", "schedule", "history", "failures", "help", "quit", "exit"]

# Regex: strip everything before the first '/' that is followed by a letter.
_LEADING_GARBAGE_RE = re.compile(r'^[^/]*(/)')


def sanitize_input(raw: str) -> str:
    """Strip GIN log noise and other leading garbage from user input.

    Ollama's GIN debug output sometimes bleeds into the readline buffer,
    turning '/tasks' into '//tasks' or '/[GIN] 2024/...tasks'.  This
    function recovers the intended command by:
      1. Stripping leading whitespace.
      2. Collapsing multiple leading slashes to one.
      3. Removing any non-command characters that precede the first '/'.
    """
    text = raw.strip()
    if not text:
        return text

    # Look for a '/' followed by an alphabetic character — that's a command.
    # This skips date-like slashes in GIN output (e.g. "2024/12/01").
    cmd_match = re.search(r'/([A-Za-z])', text)
    if cmd_match:
        text = text[cmd_match.start():]
    elif text.startswith("/") or (text.find("/") >= 0 and text[0] != "/"):
        # Fallback: extract from first '/' if no alpha follows any slash
        slash_idx = text.find("/")
        if slash_idx > 0:
            text = text[slash_idx:]

    # Collapse multiple leading slashes: "///tasks" -> "/tasks"
    if text.startswith("/"):
        stripped_slashes = text.lstrip("/")
        if stripped_slashes:
            text = "/" + stripped_slashes
        else:
            text = "/"

    return text


def fuzzy_match_command(cmd_body: str) -> str | None:
    """Return the closest known command for *cmd_body*, or None.

    *cmd_body* is the part after '/' and before any space, e.g. 'taks'.
    Uses difflib.get_close_matches with a 0.6 cutoff.
    """
    if cmd_body in KNOWN_COMMANDS:
        return cmd_body  # exact match, no correction needed
    matches = get_close_matches(cmd_body, KNOWN_COMMANDS, n=1, cutoff=0.6)
    return matches[0] if matches else None


def _lookup_task_in_grimoire(orchestrator: Orchestrator, task_id_prefix: str) -> str | None:
    """Search Grimoire for a persisted async task result by task ID prefix.

    Returns the stored result content string, or None if not found.
    """
    if "grimoire" not in orchestrator.registry:
        return None
    grimoire_mod = orchestrator.registry.get_module("grimoire")
    grim = getattr(grimoire_mod, "_grimoire", None)
    if grim is None:
        return None

    import json as _json
    try:
        results = grim.recall_recent(limit=50, source="async_task_result")
        prefix = task_id_prefix.lower()
        for entry in results:
            meta = entry.get("metadata_json", "{}")
            if isinstance(meta, str):
                meta = _json.loads(meta)
            stored_id = meta.get("task_id", "")
            if stored_id.lower().startswith(prefix) or stored_id.lower() == prefix:
                return entry.get("content", "")
    except Exception:
        pass
    return None


# Phrases indicating the user is asking about past task results — NOT new work.
_TASK_RESULT_PHRASES = (
    "what were the results",
    "what are the results",
    "show me the results",
    "what did you find",
    "what did it find",
    "what came back",
    "results of task",
    "result of task",
    "task result",
    "show task result",
    "what happened with task",
    "what happened with the task",
    "status of task",
)


def is_task_result_query(user_input: str) -> str | None:
    """Detect if user is asking about a previous task's results.

    Returns the task ID prefix if found, or None.
    """
    lower = user_input.lower()
    if not any(phrase in lower for phrase in _TASK_RESULT_PHRASES):
        return None

    # Try to extract a hex task-ID prefix (8+ hex chars or UUID fragment)
    match = re.search(r'\b([0-9a-f]{8,}(?:-[0-9a-f]+)*)\b', lower)
    if match:
        return match.group(1)
    return None


async def handle_command(
    command: str,
    orchestrator: Orchestrator,
    standing_scheduler: StandingTaskScheduler | None = None,
) -> bool:
    """Handle slash commands. Returns True if handled, False otherwise."""
    cmd = command.strip().lower()

    if cmd == "/status":
        print("\n--- Module Status ---")
        for mod_info in orchestrator.registry.list_modules():
            status_icon = "+" if mod_info["status"] == "online" else "x"
            print(
                f"  {status_icon} {mod_info['name']:12s} | "
                f"{mod_info['status']:8s} | "
                f"calls: {mod_info['call_count']} | "
                f"success: {mod_info['success_rate']:.0%}"
            )
        print()
        return True

    elif cmd == "/tools":
        print("\n--- Available Tools ---")
        for tool in orchestrator.registry.list_tools():
            print(f"  {tool['name']:25s} | {tool['module']:10s} | {tool['description']}")
        print()
        return True

    elif cmd == "/stats":
        if "cerberus" in orchestrator.registry:
            cerberus = orchestrator.registry.get_module("cerberus")
            stats = cerberus.stats
            print("\n--- Cerberus Stats ---")
            print(f"  Safety checks:   {stats['checks']}")
            print(f"  Denials:         {stats['denials']}")
            print(f"  Denial rate:     {stats['denial_rate']:.1%}")
            print(f"  Audit entries:   {stats['audit_entries']}")
            print(f"  Config hash:     {stats['config_hash']}")
            print()
        else:
            print("Cerberus not loaded.")
        return True

    elif cmd == "/tasks":
        atq = orchestrator.async_task_queue
        if atq is None:
            print("Async task queue not available.")
        else:
            active = atq.list_active_tasks()
            if not active:
                print("\nNo active background tasks.\n")
            else:
                print(f"\n--- Active Tasks ({len(active)}) ---")
                for t in active:
                    tid = t.get("task_id", "?")[:8]
                    status = t.get("status", "?")
                    pri = t.get("priority", "?")
                    desc = t.get("description", "")[:50]
                    print(f"  {tid}  {status:10s}  pri={pri}  {desc}")
                print()
        return True

    elif cmd.startswith("/task "):
        task_id_prefix = cmd.split(maxsplit=1)[1].strip()
        atq = orchestrator.async_task_queue
        if atq is None:
            print("Async task queue not available.")
        else:
            status = atq.get_status(task_id_prefix)
            if status is not None:
                print(f"\n--- Task {task_id_prefix[:8]} ---")
                print(f"  Status:  {status}")
                if status in ("completed", "failed"):
                    result = atq.get_result(task_id_prefix)
                    if result:
                        print(f"  Result:  {result}")
                print()
            else:
                # Task not in queue — check Grimoire for persisted results
                grimoire_result = _lookup_task_in_grimoire(orchestrator, task_id_prefix)
                if grimoire_result is not None:
                    print(f"\n--- Task {task_id_prefix[:8]} (from history) ---")
                    print(f"  Status:  completed")
                    print(f"  Result:  {grimoire_result}")
                    print()
                else:
                    print(f"Task '{task_id_prefix}' not found.")
        return True

    elif cmd.startswith("/history"):
        # /history or /history N
        parts = cmd.split()
        limit = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 20
        if "grimoire" in orchestrator.registry:
            grimoire_mod = orchestrator.registry.get_module("grimoire")
            grim = getattr(grimoire_mod, "_grimoire", None)
            if grim is not None:
                entries = grim.recall_operational(limit=limit, failures_only=False)
                if not entries:
                    print("\nNo operational history yet.\n")
                else:
                    print(f"\n--- Operational History (last {len(entries)}) ---")
                    for entry in entries:
                        print(f"  [{entry.get('created_at', '?')[:19]}] {entry['content']}")
                    print()
            else:
                print("Grimoire not initialized.")
        else:
            print("Grimoire not loaded.")
        return True

    elif cmd.startswith("/failures"):
        parts = cmd.split()
        limit = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 20
        if "grimoire" in orchestrator.registry:
            grimoire_mod = orchestrator.registry.get_module("grimoire")
            grim = getattr(grimoire_mod, "_grimoire", None)
            if grim is not None:
                entries = grim.recall_operational(limit=limit, failures_only=True)
                if not entries:
                    print("\nNo failures or fallbacks recorded.\n")
                else:
                    print(f"\n--- Failures & Fallbacks (last {len(entries)}) ---")
                    for entry in entries:
                        print(f"  [{entry.get('created_at', '?')[:19]}] {entry['content']}")
                    print()
            else:
                print("Grimoire not initialized.")
        else:
            print("Grimoire not loaded.")
        return True

    elif cmd.startswith("/schedule"):
        if standing_scheduler is None:
            print("Standing task scheduler not available.")
            return True
        parts = command.strip().split()
        if len(parts) >= 3 and parts[1].lower() == "run":
            task_name = parts[2].lower()
            print(f"  Running standing task: {task_name}...")
            result = standing_scheduler.run_task(task_name)
            print(f"  {result}")
        else:
            print(standing_scheduler.get_schedule_info())
        return True

    elif cmd == "/help":
        print("\n--- Shadow Commands ---")
        print("  /status           Module health overview")
        print("  /tools            List all available tools")
        print("  /stats            Cerberus safety statistics")
        print("  /schedule         Show standing task schedule")
        print("  /schedule run <t> Manually trigger a standing task")
        print("  /tasks            List active background tasks")
        print("  /task <id>        Check background task status")
        print("  /history          Show recent interaction history")
        print("  /failures         Show recent failures and fallbacks")
        print("  /help             Show this help")
        print("  quit              Shut down Shadow")
        print()
        return True

    return False


async def main() -> None:
    """Main entry point. Load config, start Shadow, run the loop."""
    print("=" * 60)
    print("  SHADOW — Personal AI Agent")
    print("  Phase 1 - Windows Development Build")
    print("=" * 60)
    print()

    # Suppress Ollama GIN HTTP debug logs that corrupt the CLI
    os.environ.setdefault("OLLAMA_LOG_LEVEL", "warn")
    print("  Ollama log level set to:", os.environ["OLLAMA_LOG_LEVEL"])

    # Load config
    config = load_config()
    setup_logging(config.get("system", {}).get("log_level", "INFO"))
    logger = logging.getLogger("shadow")

    # Start everything
    orchestrator = await startup(config, logger)

    # Grimoire storage self-test — verify the full store path works
    if "grimoire" in orchestrator.registry:
        grimoire_mod = orchestrator.registry.get_module("grimoire")
        try:
            grim = getattr(grimoire_mod, "_grimoire", None)
            if grim is None:
                logger.error("Grimoire self-test FAILED: _grimoire attribute is None")
            else:
                test_id = grim.remember(
                    content="Shadow startup self-test",
                    category="system",
                    source="self_test",
                    source_module="shadow",
                    trust_level=0.1,
                )
                if test_id:
                    logger.info("Grimoire self-test PASSED: stored memory %s", test_id)
                    # Clean up test memory
                    try:
                        grim.forget(test_id)
                    except Exception:
                        pass  # cleanup is best-effort
                else:
                    logger.error("Grimoire self-test FAILED: remember() returned None")
        except Exception as e:
            logger.error("Grimoire self-test FAILED: %s", e, exc_info=True)
    else:
        logger.warning("Grimoire not in registry — self-test skipped")

    # Start Ollama supervisor — ensure the AI runtime stays alive
    harbinger_mod = orchestrator.registry.get_module("harbinger") if "harbinger" in orchestrator.registry else None
    ollama_supervisor = OllamaSupervisor(
        check_interval=30,
        max_retries=5,
        ollama_bin=config.get("system", {}).get("ollama_bin", "ollama"),
        harbinger=harbinger_mod,
    )

    # Try one health check at startup; if Ollama is down, attempt a restart
    if not await ollama_supervisor.health_check():
        logger.warning("Ollama not responding at startup — attempting restart")
        restarted = await ollama_supervisor.restart_ollama()
        if restarted:
            logger.info("Ollama restored at startup")
        else:
            logger.error("Ollama could not be started — local models unavailable")

    await ollama_supervisor.start()

    # Start standing task scheduler — recurring background work
    standing_scheduler = StandingTaskScheduler(orchestrator.registry, logger)
    standing_scheduler.start(loop=asyncio.get_running_loop())

    online_count = len(orchestrator.registry.online_modules)
    print(f"\nShadow online. {online_count} modules active.")
    print("Type a message to begin. '/help' for commands. 'quit' to exit.\n")

    # Interactive loop
    try:
        while True:
            try:
                loop = asyncio.get_event_loop()
                raw_input = (await loop.run_in_executor(None, input, "You > "))
            except EOFError:
                break

            user_input = sanitize_input(raw_input)
            if not user_input:
                continue

            # Catch quit/exit BEFORE orchestrator — including /quit and /exit
            lower = user_input.lower().strip()
            if lower in ("quit", "exit", "q", "/quit", "/exit"):
                break

            # Handle slash commands (with fuzzy matching)
            if user_input.startswith("/"):
                # Extract the command word (e.g. "/taks 5" -> "taks")
                parts = user_input[1:].split(maxsplit=1)
                cmd_word = parts[0].lower() if parts else ""
                corrected = fuzzy_match_command(cmd_word)

                if corrected and corrected != cmd_word:
                    # Rebuild the command with the corrected word
                    suffix = f" {parts[1]}" if len(parts) > 1 else ""
                    user_input = f"/{corrected}{suffix}"
                    print(f"  (corrected from /{cmd_word} → /{corrected})")

                handled = await handle_command(user_input, orchestrator, standing_scheduler)
                if handled:
                    continue

            # Check if user is asking about a previous task's results
            task_id_match = is_task_result_query(user_input)
            if task_id_match:
                grimoire_result = _lookup_task_in_grimoire(orchestrator, task_id_match)
                if grimoire_result is not None:
                    print(f"\nShadow > Here are the results for task {task_id_match[:8]}:\n{grimoire_result}\n")
                    continue

            # Process through the decision loop
            print()
            response = await orchestrator.process_input(user_input)
            if not response:
                print("Shadow > [No response generated — the model returned empty output.]\n")
            else:
                print(f"Shadow > {response}\n")

    except KeyboardInterrupt:
        print("\n\nInterrupt received.")

    # Shutdown
    print("\nShutting down...")
    standing_scheduler.stop()
    await ollama_supervisor.stop()
    await orchestrator.shutdown()
    print("Shadow offline. State saved.")


if __name__ == "__main__":
    asyncio.run(main())
