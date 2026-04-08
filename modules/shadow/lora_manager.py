"""
LoRA Manager — Domain-Specific Adapter Selection & Stacking
=============================================================
Manage and load specialized LoRA adapters per domain at runtime.
When Omen handles a CUDA task, load the CUDA LoRA. When handling
ethics, load the ethics LoRA.

IMPORTANT: This module manages CONFIGURATION and SELECTION of LoRA
adapters. Actual LoRA loading depends on the model server (Ollama/
llama.cpp). Currently Shadow uses Ollama, which has limited runtime
LoRA support. This module builds the infrastructure so that when
proper LoRA support is available, the system is ready.

Feeds into: Shadow orchestrator (adapter recommendations before model calls).
Reads from: LoRA Performance Tracker (skip adapters with negative improvement).
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger("shadow.lora_manager")


@dataclass
class LoRAAdapter:
    """A registered LoRA adapter with metadata."""
    name: str                       # "ethics_lora", "cuda_lora", etc.
    path: str                       # filesystem path to adapter
    domains: list[str]              # ["ethics", "values"]
    modules: list[str]              # ["cerberus"] — which modules use this
    base_model: str                 # which base model this was trained for
    training_data_size: int         # number of training examples
    created_at: float = field(default_factory=time.time)
    last_loaded: float = 0.0
    status: str = "available"       # "available", "loading", "active", "error"


# Pre-configured adapters to auto-register if paths exist
_DEFAULT_ADAPTERS = [
    {
        "name": "ethics_lora",
        "domains": ["ethics", "values", "biblical"],
        "modules": ["cerberus"],
        "base_model": "gemma4-26b",
        "training_data_size": 446,
    },
    {
        "name": "anti_sycophancy_lora",
        "domains": ["communication", "honesty"],
        "modules": ["shadow"],
        "base_model": "gemma4-26b",
        "training_data_size": 400,
    },
]


class LoRAManager:
    """Manage domain-specific LoRA adapter selection and stacking.

    Tracks which adapter SHOULD be loaded, provides the adapter path,
    and lets the model-calling layer handle actual loading.
    """

    def __init__(
        self,
        adapters_dir: str = "models/lora_adapters",
        config: dict | None = None,
    ) -> None:
        self._adapters_dir = Path(adapters_dir)
        self._config = config or {}
        self._adapters: dict[str, LoRAAdapter] = {}
        self._active_adapter: str | None = None

        # Optional performance tracker integration
        self._tracker = None
        try:
            from modules.shadow.lora_tracker import LoRAPerformanceTracker
            tracker_db = self._config.get("tracker_db", "data/lora_performance.db")
            self._tracker = LoRAPerformanceTracker(db_path=tracker_db)
            logger.info("LoRA Performance Tracker connected")
        except Exception:
            logger.debug("LoRA Performance Tracker unavailable — selection without performance data")

        # Auto-register known adapters if paths exist
        self._register_defaults()

        # Scan adapters directory for any additional adapters
        self.scan_adapters_directory()

    def _register_defaults(self) -> None:
        """Register pre-configured adapters if their paths exist."""
        for adapter_def in _DEFAULT_ADAPTERS:
            adapter_path = self._adapters_dir / adapter_def["name"]
            if adapter_path.exists():
                try:
                    self.register_adapter(
                        name=adapter_def["name"],
                        path=str(adapter_path),
                        domains=adapter_def["domains"],
                        modules=adapter_def["modules"],
                        base_model=adapter_def["base_model"],
                        training_data_size=adapter_def["training_data_size"],
                    )
                    logger.info("Auto-registered default adapter: %s", adapter_def["name"])
                except Exception as e:
                    logger.warning("Failed to auto-register %s: %s", adapter_def["name"], e)

    def register_adapter(
        self,
        name: str,
        path: str,
        domains: list[str],
        modules: list[str] | None = None,
        base_model: str = "gemma4-26b",
        training_data_size: int = 0,
    ) -> bool:
        """Register a new LoRA adapter.

        Args:
            name: Unique adapter name.
            path: Filesystem path to adapter files.
            domains: Task domains this adapter covers.
            modules: Which Shadow modules use this adapter.
            base_model: Base model the adapter was trained for.
            training_data_size: Number of training examples.

        Returns:
            True if registration succeeded, False otherwise.
        """
        try:
            adapter_path = Path(path)
            if not adapter_path.exists():
                logger.warning("Adapter path does not exist: %s", path)
                return False

            adapter = LoRAAdapter(
                name=name,
                path=str(adapter_path),
                domains=domains,
                modules=modules or [],
                base_model=base_model,
                training_data_size=training_data_size,
            )
            self._adapters[name] = adapter
            logger.info("Registered LoRA adapter: %s (domains=%s)", name, domains)
            return True
        except Exception as e:
            logger.error("Failed to register adapter %s: %s", name, e)
            return False

    def get_adapter_for_task(
        self, task_type: str, module: str | None = None
    ) -> LoRAAdapter | None:
        """Determine which adapter to load for a given task.

        Priority: module-specific match > domain match > None.
        If LoRA tracker is available, skip adapters with negative improvement.

        Args:
            task_type: The type of task being performed.
            module: Optional module name handling the task.

        Returns:
            Best matching adapter or None.
        """
        try:
            # Try module-specific match first
            if module:
                module_adapter = self.get_adapter_for_module(module)
                if module_adapter and self._check_performance(module_adapter.name, task_type):
                    return module_adapter

            # Fall back to domain match
            domain_matches = self.list_by_domain(task_type)
            for adapter in domain_matches:
                if self._check_performance(adapter.name, task_type):
                    return adapter

            return None
        except Exception as e:
            logger.debug("Adapter selection failed: %s", e)
            return None

    def get_adapter_for_module(self, module_name: str) -> LoRAAdapter | None:
        """Direct module lookup for adapter.

        Args:
            module_name: Name of the Shadow module.

        Returns:
            Matching adapter or None.
        """
        try:
            for adapter in self._adapters.values():
                if module_name in adapter.modules:
                    return adapter
            return None
        except Exception as e:
            logger.debug("Module adapter lookup failed: %s", e)
            return None

    def get_load_command(self, adapter: LoRAAdapter, backend: str = "ollama") -> dict:
        """Generate the command/config needed to load an adapter.

        Args:
            adapter: The adapter to generate a load command for.
            backend: Model server backend ("ollama" or "llama.cpp").

        Returns:
            Command dict for the model-calling layer.
        """
        try:
            if backend == "llama.cpp":
                return {
                    "--lora": adapter.path,
                    "--lora-scale": 1.0,
                }
            # Default: ollama
            return {
                "model": f"{adapter.base_model}+{adapter.name}",
                "adapter_path": adapter.path,
            }
        except Exception as e:
            logger.error("Failed to generate load command: %s", e)
            return {}

    def list_available(self) -> list[LoRAAdapter]:
        """Return all registered adapters."""
        return list(self._adapters.values())

    def list_by_domain(self, domain: str) -> list[LoRAAdapter]:
        """Filter adapters by domain.

        Args:
            domain: Domain to filter by.

        Returns:
            List of adapters matching the domain.
        """
        return [
            adapter for adapter in self._adapters.values()
            if domain in adapter.domains
        ]

    def get_active_adapter(self) -> LoRAAdapter | None:
        """Return the currently active adapter, if any."""
        if self._active_adapter and self._active_adapter in self._adapters:
            return self._adapters[self._active_adapter]
        return None

    def set_active(self, adapter_name: str) -> bool:
        """Mark an adapter as the currently active one.

        Only one adapter can be active at a time (limitation of most
        LoRA implementations).

        Args:
            adapter_name: Name of the adapter to activate.

        Returns:
            True if activation succeeded, False otherwise.
        """
        try:
            if adapter_name not in self._adapters:
                logger.warning("Cannot activate unknown adapter: %s", adapter_name)
                return False

            # Deactivate current adapter
            if self._active_adapter and self._active_adapter in self._adapters:
                self._adapters[self._active_adapter].status = "available"

            # Activate new adapter
            self._adapters[adapter_name].status = "active"
            self._adapters[adapter_name].last_loaded = time.time()
            self._active_adapter = adapter_name
            logger.info("Activated LoRA adapter: %s", adapter_name)
            return True
        except Exception as e:
            logger.error("Failed to activate adapter %s: %s", adapter_name, e)
            return False

    def scan_adapters_directory(self) -> list[str]:
        """Re-scan adapters directory for new adapter files.

        Auto-registers any new adapters found (directories within
        the adapters directory that aren't already registered).

        Returns:
            List of newly discovered adapter names.
        """
        newly_discovered = []
        try:
            if not self._adapters_dir.exists():
                logger.debug("Adapters directory does not exist: %s", self._adapters_dir)
                return newly_discovered

            for item in self._adapters_dir.iterdir():
                if item.is_dir() and item.name not in self._adapters:
                    # Auto-register with minimal metadata
                    adapter = LoRAAdapter(
                        name=item.name,
                        path=str(item),
                        domains=[],
                        modules=[],
                        base_model="unknown",
                        training_data_size=0,
                    )
                    self._adapters[item.name] = adapter
                    newly_discovered.append(item.name)
                    logger.info("Discovered new adapter: %s", item.name)

            return newly_discovered
        except Exception as e:
            logger.warning("Adapter directory scan failed: %s", e)
            return newly_discovered

    def _check_performance(self, adapter_name: str, task_type: str) -> bool:
        """Check if an adapter has positive performance for a task type.

        If the tracker is unavailable, assume the adapter is fine.

        Args:
            adapter_name: Adapter to check.
            task_type: Task type to check performance for.

        Returns:
            True if adapter should be used, False if it has negative improvement.
        """
        if self._tracker is None:
            return True
        try:
            profile = self._tracker.get_adapter_profile(adapter_name)
            if profile.total_tasks == 0:
                return True  # No data yet, give it a chance
            return profile.avg_improvement >= 0
        except Exception:
            return True  # Tracker error, don't block selection
