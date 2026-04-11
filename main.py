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
import platform
import sys
from pathlib import Path

import yaml

from modules.base import ModuleRegistry, ModuleStatus
from modules.apex.apex import Apex
from modules.cerberus.cerberus import Cerberus
from modules.cipher.cipher import Cipher
from modules.grimoire.grimoire_module import GrimoireModule
from modules.harbinger.harbinger import Harbinger
from modules.morpheus.morpheus import Morpheus
from modules.nova.nova import Nova
from modules.omen.omen import Omen
from modules.reaper.reaper_module import ReaperModule
from modules.sentinel.sentinel import Sentinel
from modules.shadow.orchestrator import Orchestrator
from modules.shadow.shadow_module import ShadowModule
from modules.void.void import Void
from modules.wraith.wraith import Wraith


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

    # Step 1: Create module instances
    # --- Core (always running) ---
    grimoire = GrimoireModule(module_configs.get("grimoire", {}))
    cerberus = Cerberus(module_configs.get("cerberus", {}))

    # --- Operations ---
    wraith_config = dict(module_configs.get("wraith", {}))
    wraith_config.setdefault("timezone", config.get("system", {}).get("timezone", "America/Chicago"))
    wraith = Wraith(wraith_config)
    reaper = ReaperModule(module_configs.get("reaper", {}))
    harbinger = Harbinger(module_configs.get("harbinger", {}))

    # --- Specialized ---
    apex = Apex(module_configs.get("apex", {}))
    cipher = Cipher(module_configs.get("cipher", {}))
    omen = Omen(module_configs.get("omen", {}))
    sentinel = Sentinel(module_configs.get("sentinel", {}))
    void = Void(module_configs.get("void", {}))
    nova = Nova(module_configs.get("nova", {}))
    morpheus = Morpheus(module_configs.get("morpheus", {}))

    # Step 2: Initialize Grimoire first (Reaper depends on it)
    try:
        await grimoire.initialize()
        logger.info("Grimoire initialized: %s", grimoire.status.value)
    except Exception as e:
        logger.error("Grimoire failed to initialize: %s", e)

    # Step 3: Wire Grimoire's internal object into Reaper
    if grimoire._grimoire is not None:
        reaper._grimoire_instance = grimoire._grimoire
        logger.info("Reaper wired to Grimoire")
    else:
        logger.warning("Grimoire not available — Reaper will start without memory")

    # Step 4: Initialize remaining modules
    all_modules = [
        cerberus, wraith, reaper, harbinger,
        apex, cipher, omen, sentinel, void, nova, morpheus,
    ]
    for module in all_modules:
        try:
            await module.initialize()
            logger.info("Module '%s' initialized: %s", module.name, module.status.value)
        except Exception as e:
            logger.error("Module '%s' failed to initialize: %s", module.name, e)

    # Step 5: Create orchestrator and register modules
    orchestrator = Orchestrator(config)
    for module in [grimoire] + all_modules:
        orchestrator.registry.register(module)
        logger.info("Registered module: %s", module.name)

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


async def handle_command(command: str, orchestrator: Orchestrator) -> bool:
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

    elif cmd == "/help":
        print("\n--- Shadow Commands ---")
        print("  /status    Module health overview")
        print("  /tools     List all available tools")
        print("  /stats     Cerberus safety statistics")
        print("  /help      Show this help")
        print("  quit       Shut down Shadow")
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

    # Load config
    config = load_config()
    setup_logging(config.get("system", {}).get("log_level", "INFO"))
    logger = logging.getLogger("shadow")

    # Start everything
    orchestrator = await startup(config, logger)

    online_count = len(orchestrator.registry.online_modules)
    print(f"\nShadow online. {online_count} modules active.")
    print("Type a message to begin. '/help' for commands. 'quit' to exit.\n")

    # Interactive loop
    try:
        while True:
            try:
                user_input = input("You > ").strip()
            except EOFError:
                break

            if not user_input:
                continue

            if user_input.lower() in ("quit", "exit", "q"):
                break

            # Handle slash commands
            if user_input.startswith("/"):
                handled = await handle_command(user_input, orchestrator)
                if handled:
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
    await orchestrator.shutdown()
    print("Shadow offline. State saved.")


if __name__ == "__main__":
    asyncio.run(main())
