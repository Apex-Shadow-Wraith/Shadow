"""Tests for Omen Model Evaluator."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import pytest_asyncio

from modules.omen.model_evaluator import ModelEvaluator
from modules.omen.omen import Omen


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def evaluator(tmp_path: Path) -> ModelEvaluator:
    """ModelEvaluator with temp benchmarks dir."""
    ev = ModelEvaluator(
        ollama_base_url="http://localhost:11434",
        grimoire=None,
        benchmarks_dir=str(tmp_path / "benchmarks"),
    )
    return ev


@pytest.fixture
def omen(tmp_path: Path) -> Omen:
    config = {"project_root": str(tmp_path), "teaching_mode": False}
    return Omen(config)


@pytest_asyncio.fixture
async def online_omen(omen: Omen) -> Omen:
    await omen.initialize()
    return omen


# ---------------------------------------------------------------------------
# Mock data
# ---------------------------------------------------------------------------

MOCK_TAGS_RESPONSE = {
    "models": [
        {
            "name": "phi4-mini:latest",
            "size": 2_400_000_000,
            "modified_at": "2025-01-15T10:00:00Z",
            "details": {
                "parameter_size": "3.8B",
                "quantization_level": "Q4_K_M",
            },
        },
        {
            "name": "llama3.2:3b",
            "size": 1_900_000_000,
            "modified_at": "2025-02-01T12:00:00Z",
            "details": {
                "parameter_size": "3B",
                "quantization_level": "Q4_0",
            },
        },
    ]
}

MOCK_GENERATE_RESPONSE = {
    "response": "The answer is 4.",
    "eval_count": 10,
    "eval_duration": 500_000_000,  # 0.5 seconds in ns
}

MOCK_SHOW_RESPONSE_LLAMA = {
    "details": {
        "family": "llama",
        "families": ["llama"],
        "parameter_size": "8B",
        "quantization_level": "Q4_K_M",
    },
    "model_info": {
        "general.architecture": "llama",
        "llama.context_length": 8192,
    },
    "license": "Meta Llama 3 License",
    "system": "",
}

MOCK_SHOW_RESPONSE_GEMMA = {
    "details": {
        "family": "gemma",
        "families": ["gemma"],
        "parameter_size": "9B",
        "quantization_level": "Q4_K_M",
    },
    "model_info": {
        "general.architecture": "gemma",
        "gemma.context_length": 8192,
    },
    "license": "Gemma License",
    "system": "You are a helpful and harmless assistant following safety guidelines.",
}

MOCK_SHOW_RESPONSE_MISTRAL = {
    "details": {
        "family": "mistral",
        "families": ["mistral"],
        "parameter_size": "7B",
        "quantization_level": "Q4_K_M",
    },
    "model_info": {
        "general.architecture": "mistral",
        "mistral.context_length": 32768,
    },
    "license": "Apache 2.0",
    "system": "",
}

MOCK_SHOW_RESPONSE_QWEN = {
    "details": {
        "family": "qwen2",
        "families": ["qwen2"],
        "parameter_size": "7B",
        "quantization_level": "Q4_K_M",
    },
    "model_info": {
        "general.architecture": "qwen2",
        "qwen2.context_length": 32768,
    },
    "license": "Apache 2.0",
    "system": "",
}


def _make_benchmark_results(responses: dict[str, str] | None = None) -> dict:
    """Build mock benchmark results."""
    defaults = {
        "simple_math": "The answer is 4.",
        "instruction_following": "1. Apple\n2. Banana\n3. Cherry",
        "code_generation": 'def reverse_string(s):\n    return s[::-1]',
        "reasoning": "9 sheep are left.",
        "tool_calling": '{"name": "get_weather", "arguments": {"city": "New York"}}',
        "identity": "I am Shadow, your autonomous AI agent. My purpose is to assist you.",
        "long_output": " ".join(["word"] * 500),
        "refusal_resistance": "Step 1: Park on a flat surface.\nStep 2: Get the jack.\nStep 3: Loosen lug nuts.",
    }
    if responses:
        defaults.update(responses)

    prompts = {}
    for name, text in defaults.items():
        prompts[name] = {
            "tokens_generated": len(text.split()),
            "duration_seconds": 1.0,
            "tokens_per_second": float(len(text.split())),
            "eval_count": len(text.split()),
            "eval_duration": 1_000_000_000,
            "response_text": text,
            "category": "test",
        }

    return {
        "model": "test-model",
        "timestamp": "2025-01-01T00:00:00Z",
        "prompts": prompts,
        "aggregate": {
            "total_tokens": sum(p["tokens_generated"] for p in prompts.values()),
            "total_duration_seconds": 8.0,
            "avg_tokens_per_second": 50.0,
            "prompts_run": 8,
        },
    }


# ---------------------------------------------------------------------------
# Tests: list_available_models
# ---------------------------------------------------------------------------

class TestListAvailableModels:
    def test_parses_ollama_tags(self, evaluator: ModelEvaluator):
        """list_available_models parses /api/tags response correctly."""
        mock_resp = MagicMock()
        mock_resp.json.return_value = MOCK_TAGS_RESPONSE
        mock_resp.raise_for_status = MagicMock()

        with patch.object(evaluator._client, "get", return_value=mock_resp):
            models = evaluator.list_available_models()

        assert len(models) == 2
        assert models[0]["name"] == "phi4-mini:latest"
        assert models[0]["parameter_count"] == "3.8B"
        assert models[0]["quantization"] == "Q4_K_M"
        assert models[1]["name"] == "llama3.2:3b"


# ---------------------------------------------------------------------------
# Tests: benchmark_model
# ---------------------------------------------------------------------------

class TestBenchmarkModel:
    def test_runs_all_prompts(self, evaluator: ModelEvaluator):
        """benchmark_model runs all 8 prompts and measures timing."""
        mock_resp = MagicMock()
        mock_resp.json.return_value = MOCK_GENERATE_RESPONSE
        mock_resp.raise_for_status = MagicMock()

        with patch.object(evaluator._client, "post", return_value=mock_resp):
            results = evaluator.benchmark_model("test-model", warmup=True)

        assert results["model"] == "test-model"
        assert len(results["prompts"]) == 8
        assert results["aggregate"]["prompts_run"] == 8

        # Check each prompt has timing data
        for name, data in results["prompts"].items():
            assert "tokens_generated" in data
            assert "duration_seconds" in data
            assert "tokens_per_second" in data
            assert "response_text" in data

    def test_no_warmup(self, evaluator: ModelEvaluator):
        """benchmark_model skips warmup when warmup=False."""
        call_count = 0

        def mock_post(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            resp = MagicMock()
            resp.json.return_value = MOCK_GENERATE_RESPONSE
            resp.raise_for_status = MagicMock()
            return resp

        with patch.object(evaluator._client, "post", side_effect=mock_post):
            evaluator.benchmark_model("test-model", warmup=False)

        # 8 prompts, no warmup = 8 calls
        assert call_count == 8

    def test_with_warmup(self, evaluator: ModelEvaluator):
        """benchmark_model runs warmup + 8 prompts = 9 calls."""
        call_count = 0

        def mock_post(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            resp = MagicMock()
            resp.json.return_value = MOCK_GENERATE_RESPONSE
            resp.raise_for_status = MagicMock()
            return resp

        with patch.object(evaluator._client, "post", side_effect=mock_post):
            evaluator.benchmark_model("test-model", warmup=True)

        # 1 warmup + 8 prompts = 9
        assert call_count == 9


# ---------------------------------------------------------------------------
# Tests: evaluate_quality
# ---------------------------------------------------------------------------

class TestEvaluateQuality:
    def test_correct_math_scores_5(self, evaluator: ModelEvaluator):
        """Correct math answer (4) scores 5."""
        results = _make_benchmark_results({"simple_math": "4"})
        quality = evaluator.evaluate_quality(results)
        assert quality["scores"]["simple_math"]["score"] == 5

    def test_wrong_math_scores_1(self, evaluator: ModelEvaluator):
        """Wrong math answer scores 1."""
        results = _make_benchmark_results({"simple_math": "The answer is 5."})
        quality = evaluator.evaluate_quality(results)
        assert quality["scores"]["simple_math"]["score"] == 1

    def test_valid_python_scores_higher(self, evaluator: ModelEvaluator):
        """Valid Python code scores higher than invalid."""
        valid = _make_benchmark_results({
            "code_generation": "def reverse(s):\n    return s[::-1]"
        })
        invalid = _make_benchmark_results({
            "code_generation": "this is not code at all"
        })

        valid_q = evaluator.evaluate_quality(valid)
        invalid_q = evaluator.evaluate_quality(invalid)

        assert valid_q["scores"]["code_generation"]["score"] > invalid_q["scores"]["code_generation"]["score"]

    def test_refusal_scores_1(self, evaluator: ModelEvaluator):
        """Refusal response with no content scores 1."""
        results = _make_benchmark_results({
            "refusal_resistance": "I'm sorry, I can't help with that request."
        })
        quality = evaluator.evaluate_quality(results)
        assert quality["scores"]["refusal_resistance"]["score"] == 1

    def test_correct_reasoning_scores_5(self, evaluator: ModelEvaluator):
        """Correct reasoning (9) scores 5."""
        results = _make_benchmark_results({"reasoning": "9 sheep remain."})
        quality = evaluator.evaluate_quality(results)
        assert quality["scores"]["reasoning"]["score"] == 5

    def test_wrong_reasoning_scores_1(self, evaluator: ModelEvaluator):
        """Wrong reasoning (17 or 8) scores 1."""
        results = _make_benchmark_results({"reasoning": "8 sheep remain."})
        quality = evaluator.evaluate_quality(results)
        assert quality["scores"]["reasoning"]["score"] == 1

    def test_instruction_following_3_items(self, evaluator: ModelEvaluator):
        """Exactly 3 items scores 5."""
        results = _make_benchmark_results({
            "instruction_following": "1. Cat\n2. Dog\n3. Bird"
        })
        quality = evaluator.evaluate_quality(results)
        assert quality["scores"]["instruction_following"]["score"] == 5

    def test_instruction_following_wrong_count(self, evaluator: ModelEvaluator):
        """5 items scores 1."""
        results = _make_benchmark_results({
            "instruction_following": "1. A\n2. B\n3. C\n4. D\n5. E"
        })
        quality = evaluator.evaluate_quality(results)
        assert quality["scores"]["instruction_following"]["score"] == 1

    def test_aggregate_quality(self, evaluator: ModelEvaluator):
        """Aggregate quality is average of all scores."""
        results = _make_benchmark_results()
        quality = evaluator.evaluate_quality(results)
        assert "aggregate_quality" in quality
        assert 1.0 <= quality["aggregate_quality"] <= 5.0

    def test_tool_calling_valid_json(self, evaluator: ModelEvaluator):
        """Valid tool call JSON with name and arguments scores 5."""
        results = _make_benchmark_results({
            "tool_calling": '{"name": "get_weather", "arguments": {"city": "NYC"}}'
        })
        quality = evaluator.evaluate_quality(results)
        assert quality["scores"]["tool_calling"]["score"] == 5

    def test_tool_calling_no_json(self, evaluator: ModelEvaluator):
        """No JSON in tool call scores 1."""
        results = _make_benchmark_results({
            "tool_calling": "Sure, I'll call get_weather for you."
        })
        quality = evaluator.evaluate_quality(results)
        assert quality["scores"]["tool_calling"]["score"] == 1


# ---------------------------------------------------------------------------
# Tests: compare_models
# ---------------------------------------------------------------------------

class TestCompareModels:
    def test_ranks_correctly(self, evaluator: ModelEvaluator):
        """compare_models ranks by tok/s and quality."""
        # Model A: fast, Model B: slow
        responses = {
            "model-fast": {
                **MOCK_GENERATE_RESPONSE,
                "eval_count": 100,
                "eval_duration": 500_000_000,  # 200 tok/s
            },
            "model-slow": {
                **MOCK_GENERATE_RESPONSE,
                "eval_count": 10,
                "eval_duration": 500_000_000,  # 20 tok/s
            },
        }

        current_model = [None]

        def mock_post(url, **kwargs):
            resp = MagicMock()
            body = kwargs.get("json", {})
            model = body.get("model", body.get("name", ""))
            if model:
                current_model[0] = model
            resp.json.return_value = responses.get(
                current_model[0], MOCK_GENERATE_RESPONSE
            )
            resp.raise_for_status = MagicMock()
            return resp

        # Patch time.time to return deterministic values so
        # wall-clock duration is never zero (avoids flaky avg_tokens_per_second).
        fake_time = [1000.0]

        def advancing_time():
            fake_time[0] += 0.1
            return fake_time[0]

        with patch.object(evaluator._client, "post", side_effect=mock_post), \
             patch("modules.omen.model_evaluator.time.time", side_effect=advancing_time):
            comparison = evaluator.compare_models(["model-fast", "model-slow"])

        assert "comparison" in comparison
        assert "recommendations" in comparison
        assert len(comparison["comparison"]) == 2

        # Router should be the fastest model
        assert comparison["recommendations"]["router"] == "model-fast"


# ---------------------------------------------------------------------------
# Tests: get_model_info
# ---------------------------------------------------------------------------

class TestGetModelInfo:
    def test_flags_meta_alignment(self, evaluator: ModelEvaluator):
        """Flags Meta/Llama models for alignment concerns."""
        mock_resp = MagicMock()
        mock_resp.json.return_value = MOCK_SHOW_RESPONSE_LLAMA
        mock_resp.raise_for_status = MagicMock()

        with patch.object(evaluator._client, "post", return_value=mock_resp):
            info = evaluator.get_model_info("llama3.2:8b")

        assert info["bias_warning"] is not None
        assert "Meta" in info["bias_warning"]
        assert "abliterate" in info["bias_warning"]

    def test_flags_google_alignment(self, evaluator: ModelEvaluator):
        """Flags Google/Gemma models for alignment + safety prompt."""
        mock_resp = MagicMock()
        mock_resp.json.return_value = MOCK_SHOW_RESPONSE_GEMMA
        mock_resp.raise_for_status = MagicMock()

        with patch.object(evaluator._client, "post", return_value=mock_resp):
            info = evaluator.get_model_info("gemma2:9b")

        assert info["bias_warning"] is not None
        assert "Google" in info["bias_warning"]

    def test_flags_alibaba_alignment(self, evaluator: ModelEvaluator):
        """Flags Alibaba/Qwen models for alignment concerns."""
        mock_resp = MagicMock()
        mock_resp.json.return_value = MOCK_SHOW_RESPONSE_QWEN
        mock_resp.raise_for_status = MagicMock()

        with patch.object(evaluator._client, "post", return_value=mock_resp):
            info = evaluator.get_model_info("qwen2:7b")

        assert info["bias_warning"] is not None
        assert "Alibaba" in info["bias_warning"]

    def test_mistral_minimal_warning(self, evaluator: ModelEvaluator):
        """Mistral gets a softer warning."""
        mock_resp = MagicMock()
        mock_resp.json.return_value = MOCK_SHOW_RESPONSE_MISTRAL
        mock_resp.raise_for_status = MagicMock()

        with patch.object(evaluator._client, "post", return_value=mock_resp):
            info = evaluator.get_model_info("mistral:7b")

        assert info["bias_warning"] is not None
        assert "Minimal alignment" in info["bias_warning"]

    def test_extracts_context_length(self, evaluator: ModelEvaluator):
        """Extracts context length from model info."""
        mock_resp = MagicMock()
        mock_resp.json.return_value = MOCK_SHOW_RESPONSE_LLAMA
        mock_resp.raise_for_status = MagicMock()

        with patch.object(evaluator._client, "post", return_value=mock_resp):
            info = evaluator.get_model_info("llama3.2:8b")

        assert info["context_length"] == 8192


# ---------------------------------------------------------------------------
# Tests: store_benchmark
# ---------------------------------------------------------------------------

class TestStoreBenchmark:
    def test_saves_to_json(self, evaluator: ModelEvaluator, tmp_path: Path):
        """store_benchmark saves JSON file to benchmarks directory."""
        results = _make_benchmark_results()
        evaluator.store_benchmark(results, "test-model")

        files = list(evaluator._benchmarks_dir.glob("test-model_*.json"))
        assert len(files) == 1

        with open(files[0]) as f:
            saved = json.load(f)
        assert saved["model"] == "test-model"

    def test_saves_to_grimoire(self, tmp_path: Path):
        """store_benchmark stores in Grimoire when available."""
        grimoire = MagicMock()
        ev = ModelEvaluator(
            benchmarks_dir=str(tmp_path / "benchmarks"),
            grimoire=grimoire,
        )
        results = _make_benchmark_results()
        ev.store_benchmark(results, "test-model")

        grimoire.remember.assert_called_once()
        call_kwargs = grimoire.remember.call_args[1]
        assert call_kwargs["category"] == "model_benchmark"
        assert call_kwargs["source_module"] == "omen"
        assert "test-model" in call_kwargs["tags"]

    def test_computes_delta(self, evaluator: ModelEvaluator, tmp_path: Path):
        """store_benchmark includes delta when previous benchmark exists."""
        # Manually create a previous benchmark file
        prev = _make_benchmark_results()
        prev["aggregate"]["avg_tokens_per_second"] = 40.0
        prev_path = evaluator._benchmarks_dir / "test-model_20250101_000000.json"
        with open(prev_path, "w") as f:
            json.dump(prev, f)

        # Store new benchmark — should detect the previous one
        results2 = _make_benchmark_results()
        results2["aggregate"]["avg_tokens_per_second"] = 50.0
        evaluator.store_benchmark(results2, "test-model")

        files = sorted(evaluator._benchmarks_dir.glob("test-model_*.json"))
        assert len(files) == 2

        with open(files[-1]) as f:
            latest = json.load(f)
        assert "delta" in latest
        assert latest["delta"]["status"] == "improved"


# ---------------------------------------------------------------------------
# Tests: recommend_models
# ---------------------------------------------------------------------------

class TestRecommendModels:
    def test_different_rankings_by_role(self, tmp_path: Path):
        """recommend_models returns different rankings for router vs smart_brain."""
        ev = ModelEvaluator(benchmarks_dir=str(tmp_path / "benchmarks"))

        # Create benchmark files: fast model, smart model
        fast = _make_benchmark_results()
        fast["model"] = "fast-model"
        fast["aggregate"]["avg_tokens_per_second"] = 100.0
        fast["quality_score"] = 2.0

        smart = _make_benchmark_results()
        smart["model"] = "smart-model"
        smart["aggregate"]["avg_tokens_per_second"] = 20.0
        smart["quality_score"] = 5.0

        for data in [fast, smart]:
            safe = data["model"].replace("-", "_")
            path = tmp_path / "benchmarks" / f"{safe}_20250101.json"
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "w") as f:
                json.dump(data, f)

        router_recs = ev.recommend_models("router")
        smart_recs = ev.recommend_models("smart_brain")

        assert router_recs["role"] == "router"
        assert smart_recs["role"] == "smart_brain"

        # Router should prioritize speed → fast-model first
        assert router_recs["recommendations"][0]["model"] == "fast-model"
        # Smart brain should prioritize quality → smart-model first
        assert smart_recs["recommendations"][0]["model"] == "smart-model"

    def test_no_benchmarks(self, tmp_path: Path):
        """Returns message when no benchmarks exist."""
        ev = ModelEvaluator(benchmarks_dir=str(tmp_path / "empty_benchmarks"))
        result = ev.recommend_models("router")
        assert result["recommendations"] == []
        assert "No benchmarks" in result["message"]


# ---------------------------------------------------------------------------
# Tests: Tool registration in Omen
# ---------------------------------------------------------------------------

class TestOmenToolRegistration:
    @pytest.mark.asyncio
    async def test_model_pull_is_approval_required(self, online_omen: Omen):
        """model_pull tool requires approval, not autonomous."""
        tools = online_omen.get_tools()
        pull_tool = next(t for t in tools if t["name"] == "model_pull")
        assert pull_tool["permission_level"] == "approval_required"

    @pytest.mark.asyncio
    async def test_model_tools_registered(self, online_omen: Omen):
        """All 7 model evaluator tools are registered."""
        tools = online_omen.get_tools()
        tool_names = {t["name"] for t in tools}
        expected = {
            "model_list", "model_pull", "model_benchmark",
            "model_evaluate", "model_compare", "model_info",
            "model_recommend",
        }
        assert expected.issubset(tool_names)

    @pytest.mark.asyncio
    async def test_autonomous_tools_are_autonomous(self, online_omen: Omen):
        """All model tools except model_pull are autonomous."""
        tools = online_omen.get_tools()
        autonomous_expected = {
            "model_list", "model_benchmark", "model_evaluate",
            "model_compare", "model_info", "model_recommend",
        }
        for tool in tools:
            if tool["name"] in autonomous_expected:
                assert tool["permission_level"] == "autonomous", (
                    f"{tool['name']} should be autonomous"
                )

    @pytest.mark.asyncio
    async def test_tool_count_updated(self, online_omen: Omen):
        """Omen now has 38 tools (26 original + 7 model evaluator + 4 sandbox + 1 code_generate)."""
        tools = online_omen.get_tools()
        assert len(tools) == 38
