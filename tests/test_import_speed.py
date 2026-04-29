"""
Import Speed Tests
==================
Measures cold-import time for each Shadow module.
Flags any module importing slower than 500ms.
"""

import importlib
import sys
import time

import pytest

# All module paths to test
MODULE_PATHS = [
    "modules.apex.apex",
    "modules.cerberus.cerberus",
    "modules.cerberus.injection_detector",
    "modules.cerberus.reversibility",
    "modules.cerberus.watchdog",
    # Phase A: absorbed Sentinel security surface lives under cerberus.
    "modules.cerberus.security.core",
    "modules.cerberus.security.analyzer",
    "modules.cerberus.security.threat_intelligence",
    "modules.cipher.cipher",
    "modules.grimoire.grimoire",
    "modules.harbinger.harbinger",
    "modules.harbinger.safety_report",
    "modules.morpheus.morpheus",
    "modules.nova.nova",
    "modules.omen.omen",
    "modules.reaper.reaper_module",
    "modules.shadow.shadow_module",
    "modules.shadow.orchestrator",
    "modules.shadow.task_tracker",
    "modules.shadow.growth_engine",
    "modules.wraith.wraith",
]

# Modules known to have heavy deps (chromadb, psutil)
KNOWN_HEAVY = {
    "modules.grimoire.grimoire",
    # The absorbed security surface pulls in the firewall analyzer +
    # threat-intelligence modules through SecuritySurface composition.
    "modules.cerberus.security.core",
    "modules.shadow.orchestrator",
}

THRESHOLD_MS = 500


@pytest.fixture()
def clean_module_cache():
    """Remove target modules from sys.modules for cold-import measurement."""
    saved = {}
    yield saved
    # Restore after test
    for mod_name, mod_obj in saved.items():
        if mod_obj is not None:
            sys.modules[mod_name] = mod_obj
        else:
            sys.modules.pop(mod_name, None)


@pytest.mark.slow
@pytest.mark.parametrize("module_path", MODULE_PATHS)
def test_import_speed(module_path, clean_module_cache):
    """Each module should import in under 500ms (cold import)."""
    # Save and remove from cache for cold measurement
    if module_path in sys.modules:
        clean_module_cache[module_path] = sys.modules.pop(module_path)
    else:
        clean_module_cache[module_path] = None

    start = time.perf_counter()
    importlib.import_module(module_path)
    elapsed_ms = (time.perf_counter() - start) * 1000

    threshold = 3000 if module_path in KNOWN_HEAVY else THRESHOLD_MS
    assert elapsed_ms < threshold, (
        f"{module_path} took {elapsed_ms:.0f}ms to import "
        f"(threshold: {threshold}ms)"
    )
