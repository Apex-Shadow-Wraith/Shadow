"""Tests for LoRA Manager — domain-specific adapter selection and stacking."""

import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from modules.shadow.lora_manager import LoRAAdapter, LoRAManager


@pytest.fixture
def tmp_adapters_dir(tmp_path):
    """Create a temporary adapters directory."""
    adapters = tmp_path / "lora_adapters"
    adapters.mkdir()
    return adapters


@pytest.fixture
def manager(tmp_adapters_dir):
    """Create a LoRAManager with a temp adapters directory."""
    with patch.dict("sys.modules", {"modules.shadow.lora_tracker": None}):
        return LoRAManager(adapters_dir=str(tmp_adapters_dir))


@pytest.fixture
def adapter_dir(tmp_adapters_dir):
    """Create a fake adapter directory for registration."""
    d = tmp_adapters_dir / "test_adapter"
    d.mkdir()
    return d


# ── Registration ──────────────────────────────────────────────


class TestRegistration:
    def test_register_valid_path(self, manager, adapter_dir):
        result = manager.register_adapter(
            name="test_adapter",
            path=str(adapter_dir),
            domains=["code", "python"],
            modules=["omen"],
        )
        assert result is True

    def test_register_invalid_path(self, manager):
        result = manager.register_adapter(
            name="ghost",
            path="/nonexistent/path/ghost_adapter",
            domains=["test"],
        )
        assert result is False

    def test_adapter_fields_after_registration(self, manager, adapter_dir):
        manager.register_adapter(
            name="test_adapter",
            path=str(adapter_dir),
            domains=["code"],
            modules=["omen"],
            base_model="gemma4-26b",
            training_data_size=500,
        )
        adapters = manager.list_available()
        assert len(adapters) == 1
        adapter = adapters[0]
        assert adapter.name == "test_adapter"
        assert adapter.path == str(adapter_dir)
        assert adapter.domains == ["code"]
        assert adapter.modules == ["omen"]
        assert adapter.base_model == "gemma4-26b"
        assert adapter.training_data_size == 500
        assert adapter.status == "available"


# ── Selection ─────────────────────────────────────────────────


class TestSelection:
    def test_get_adapter_for_task_domain_match(self, manager, adapter_dir):
        manager.register_adapter(
            name="ethics_lora",
            path=str(adapter_dir),
            domains=["ethics", "values"],
            modules=["cerberus"],
        )
        result = manager.get_adapter_for_task("ethics")
        assert result is not None
        assert result.name == "ethics_lora"

    def test_get_adapter_for_task_unknown(self, manager, adapter_dir):
        manager.register_adapter(
            name="ethics_lora",
            path=str(adapter_dir),
            domains=["ethics"],
        )
        result = manager.get_adapter_for_task("quantum_physics")
        assert result is None

    def test_get_adapter_for_module(self, manager, adapter_dir):
        manager.register_adapter(
            name="ethics_lora",
            path=str(adapter_dir),
            domains=["ethics"],
            modules=["cerberus"],
        )
        result = manager.get_adapter_for_module("cerberus")
        assert result is not None
        assert result.name == "ethics_lora"

    def test_get_adapter_for_unknown_module(self, manager):
        result = manager.get_adapter_for_module("nonexistent")
        assert result is None

    def test_get_adapter_for_task_module_priority(self, manager, tmp_adapters_dir):
        """Module-specific match takes priority over domain match."""
        d1 = tmp_adapters_dir / "domain_adapter"
        d1.mkdir()
        d2 = tmp_adapters_dir / "module_adapter"
        d2.mkdir()

        manager.register_adapter(
            name="domain_adapter",
            path=str(d1),
            domains=["ethics"],
            modules=[],
        )
        manager.register_adapter(
            name="module_adapter",
            path=str(d2),
            domains=[],
            modules=["cerberus"],
        )
        result = manager.get_adapter_for_task("ethics", module="cerberus")
        assert result is not None
        assert result.name == "module_adapter"

    def test_adapter_with_negative_improvement_skipped(self, manager, adapter_dir):
        """Adapters with negative improvement should be skipped."""
        manager.register_adapter(
            name="bad_adapter",
            path=str(adapter_dir),
            domains=["ethics"],
            modules=["cerberus"],
        )

        # Mock tracker with negative improvement profile
        mock_tracker = MagicMock()
        mock_profile = MagicMock()
        mock_profile.total_tasks = 50
        mock_profile.avg_improvement = -0.15
        mock_tracker.get_adapter_profile.return_value = mock_profile
        manager._tracker = mock_tracker

        result = manager.get_adapter_for_task("ethics", module="cerberus")
        assert result is None


# ── Commands ──────────────────────────────────────────────────


class TestCommands:
    def test_load_command_ollama(self, manager):
        adapter = LoRAAdapter(
            name="ethics_lora",
            path="/path/to/ethics_lora",
            domains=["ethics"],
            modules=["cerberus"],
            base_model="gemma4-26b",
            training_data_size=446,
        )
        cmd = manager.get_load_command(adapter, backend="ollama")
        assert cmd["model"] == "gemma4-26b+ethics_lora"
        assert cmd["adapter_path"] == "/path/to/ethics_lora"

    def test_load_command_llama_cpp(self, manager):
        adapter = LoRAAdapter(
            name="cuda_lora",
            path="/path/to/cuda_lora",
            domains=["code"],
            modules=["omen"],
            base_model="gemma4-26b",
            training_data_size=200,
        )
        cmd = manager.get_load_command(adapter, backend="llama.cpp")
        assert cmd["--lora"] == "/path/to/cuda_lora"
        assert cmd["--lora-scale"] == 1.0


# ── Listing ───────────────────────────────────────────────────


class TestListing:
    def test_list_available(self, manager, tmp_adapters_dir):
        for i in range(3):
            d = tmp_adapters_dir / f"adapter_{i}"
            d.mkdir()
            manager.register_adapter(
                name=f"adapter_{i}",
                path=str(d),
                domains=["test"],
            )
        assert len(manager.list_available()) == 3

    def test_list_by_domain(self, manager, tmp_adapters_dir):
        d1 = tmp_adapters_dir / "ethics_adapter"
        d1.mkdir()
        d2 = tmp_adapters_dir / "code_adapter"
        d2.mkdir()

        manager.register_adapter("ethics_adapter", str(d1), domains=["ethics", "values"])
        manager.register_adapter("code_adapter", str(d2), domains=["code", "python"])

        ethics = manager.list_by_domain("ethics")
        assert len(ethics) == 1
        assert ethics[0].name == "ethics_adapter"

        code = manager.list_by_domain("code")
        assert len(code) == 1
        assert code[0].name == "code_adapter"

    def test_get_active_adapter_none(self, manager):
        assert manager.get_active_adapter() is None


# ── State Management ──────────────────────────────────────────


class TestStateManagement:
    def test_set_active(self, manager, adapter_dir):
        manager.register_adapter("test", str(adapter_dir), domains=["test"])
        result = manager.set_active("test")
        assert result is True
        assert manager.get_active_adapter().name == "test"
        assert manager.get_active_adapter().status == "active"

    def test_only_one_active(self, manager, tmp_adapters_dir):
        d1 = tmp_adapters_dir / "a1"
        d1.mkdir()
        d2 = tmp_adapters_dir / "a2"
        d2.mkdir()

        manager.register_adapter("a1", str(d1), domains=["test"])
        manager.register_adapter("a2", str(d2), domains=["test"])

        manager.set_active("a1")
        assert manager.get_active_adapter().name == "a1"

        manager.set_active("a2")
        assert manager.get_active_adapter().name == "a2"
        # Previous adapter should be deactivated
        assert manager._adapters["a1"].status == "available"

    def test_set_active_unknown(self, manager):
        result = manager.set_active("nonexistent")
        assert result is False


# ── Directory Scanning ────────────────────────────────────────


class TestDirectoryScanning:
    def test_scan_discovers_new(self, manager, tmp_adapters_dir):
        # Create new adapter directories after init
        (tmp_adapters_dir / "new_adapter_1").mkdir()
        (tmp_adapters_dir / "new_adapter_2").mkdir()

        discovered = manager.scan_adapters_directory()
        assert "new_adapter_1" in discovered
        assert "new_adapter_2" in discovered

    def test_scan_no_duplicates(self, manager, tmp_adapters_dir):
        d = tmp_adapters_dir / "existing"
        d.mkdir()
        manager.register_adapter("existing", str(d), domains=["test"])

        discovered = manager.scan_adapters_directory()
        assert "existing" not in discovered
        # Should still have exactly one adapter named "existing"
        assert len([a for a in manager.list_available() if a.name == "existing"]) == 1


# ── Pre-Registration ─────────────────────────────────────────


class TestPreRegistration:
    def test_known_adapters_auto_registered(self, tmp_path):
        """Default adapters are registered if their paths exist."""
        adapters_dir = tmp_path / "lora_adapters"
        adapters_dir.mkdir()
        (adapters_dir / "ethics_lora").mkdir()
        (adapters_dir / "anti_sycophancy_lora").mkdir()

        with patch("modules.shadow.lora_manager.LoRAPerformanceTracker", side_effect=ImportError):
            mgr = LoRAManager(adapters_dir=str(adapters_dir))

        names = [a.name for a in mgr.list_available()]
        assert "ethics_lora" in names
        assert "anti_sycophancy_lora" in names

    def test_known_adapters_skipped_if_missing(self, tmp_path):
        """Default adapters are NOT registered if paths don't exist."""
        adapters_dir = tmp_path / "lora_adapters"
        adapters_dir.mkdir()

        with patch("modules.shadow.lora_manager.LoRAPerformanceTracker", side_effect=ImportError):
            mgr = LoRAManager(adapters_dir=str(adapters_dir))

        assert len(mgr.list_available()) == 0


# ── Edge Cases ────────────────────────────────────────────────


class TestEdgeCases:
    def test_no_adapters_directory(self, tmp_path):
        """Graceful empty state when directory doesn't exist."""
        with patch("modules.shadow.lora_manager.LoRAPerformanceTracker", side_effect=ImportError):
            mgr = LoRAManager(adapters_dir=str(tmp_path / "nonexistent"))
        assert len(mgr.list_available()) == 0

    def test_empty_directory(self, tmp_path):
        """No adapters registered from empty directory."""
        adapters_dir = tmp_path / "empty_adapters"
        adapters_dir.mkdir()
        with patch("modules.shadow.lora_manager.LoRAPerformanceTracker", side_effect=ImportError):
            mgr = LoRAManager(adapters_dir=str(adapters_dir))
        assert len(mgr.list_available()) == 0

    def test_multiple_adapters_same_domain(self, manager, tmp_adapters_dir):
        """When multiple adapters match a domain, the first registered is returned."""
        d1 = tmp_adapters_dir / "adapter_a"
        d1.mkdir()
        d2 = tmp_adapters_dir / "adapter_b"
        d2.mkdir()

        manager.register_adapter("adapter_a", str(d1), domains=["ethics"])
        manager.register_adapter("adapter_b", str(d2), domains=["ethics"])

        result = manager.get_adapter_for_task("ethics")
        assert result is not None
        assert result.name == "adapter_a"

    def test_graceful_without_tracker(self, manager, adapter_dir):
        """Selection works fine when tracker is unavailable."""
        assert manager._tracker is None
        manager.register_adapter("test", str(adapter_dir), domains=["ethics"])
        result = manager.get_adapter_for_task("ethics")
        assert result is not None
