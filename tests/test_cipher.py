"""
Tests for Cipher — Math, Logic, and Complex Reasoning
=======================================================
Covers arithmetic, functions, statistics, unit conversion,
error handling, and safety (no eval).
"""

import math
import pytest
from typing import Any

from modules.base import ModuleStatus, ToolResult
from modules.cipher.cipher import Cipher


@pytest.fixture
def cipher() -> Cipher:
    return Cipher()


@pytest.fixture
async def online_cipher(cipher: Cipher) -> Cipher:
    await cipher.initialize()
    return cipher


# --- Lifecycle ---

class TestCipherLifecycle:
    @pytest.mark.asyncio
    async def test_initialize(self, cipher: Cipher):
        await cipher.initialize()
        assert cipher.status == ModuleStatus.ONLINE

    @pytest.mark.asyncio
    async def test_shutdown(self, cipher: Cipher):
        await cipher.initialize()
        await cipher.shutdown()
        assert cipher.status == ModuleStatus.OFFLINE

    def test_get_tools(self, cipher: Cipher):
        tools = cipher.get_tools()
        assert len(tools) == 4
        names = [t["name"] for t in tools]
        assert "calculate" in names
        assert "unit_convert" in names
        assert "data_analyze" in names
        assert "logic_verify" in names


# --- Calculate tests ---

class TestCalculate:
    @pytest.mark.asyncio
    async def test_basic_addition(self, online_cipher: Cipher):
        r = await online_cipher.execute("calculate", {"expression": "2 + 3"})
        assert r.success is True
        assert r.content["result"] == 5.0

    @pytest.mark.asyncio
    async def test_multiplication(self, online_cipher: Cipher):
        r = await online_cipher.execute("calculate", {"expression": "6 * 7"})
        assert r.content["result"] == 42.0

    @pytest.mark.asyncio
    async def test_order_of_operations(self, online_cipher: Cipher):
        r = await online_cipher.execute("calculate", {"expression": "2 + 3 * 4"})
        assert r.content["result"] == 14.0

    @pytest.mark.asyncio
    async def test_parentheses(self, online_cipher: Cipher):
        r = await online_cipher.execute("calculate", {"expression": "(2 + 3) * 4"})
        assert r.content["result"] == 20.0

    @pytest.mark.asyncio
    async def test_exponentiation(self, online_cipher: Cipher):
        r = await online_cipher.execute("calculate", {"expression": "2 ** 10"})
        assert r.content["result"] == 1024.0

    @pytest.mark.asyncio
    async def test_floor_division(self, online_cipher: Cipher):
        r = await online_cipher.execute("calculate", {"expression": "17 // 5"})
        assert r.content["result"] == 3.0

    @pytest.mark.asyncio
    async def test_modulo(self, online_cipher: Cipher):
        r = await online_cipher.execute("calculate", {"expression": "17 % 5"})
        assert r.content["result"] == 2.0

    @pytest.mark.asyncio
    async def test_negative(self, online_cipher: Cipher):
        r = await online_cipher.execute("calculate", {"expression": "-5 + 3"})
        assert r.content["result"] == -2.0

    @pytest.mark.asyncio
    async def test_sqrt(self, online_cipher: Cipher):
        r = await online_cipher.execute("calculate", {"expression": "sqrt(144)"})
        assert r.content["result"] == 12.0

    @pytest.mark.asyncio
    async def test_pi(self, online_cipher: Cipher):
        r = await online_cipher.execute("calculate", {"expression": "pi"})
        assert r.content["result"] == pytest.approx(math.pi)

    @pytest.mark.asyncio
    async def test_trig(self, online_cipher: Cipher):
        r = await online_cipher.execute("calculate", {"expression": "sin(0)"})
        assert r.content["result"] == pytest.approx(0.0)

    @pytest.mark.asyncio
    async def test_division_by_zero(self, online_cipher: Cipher):
        r = await online_cipher.execute("calculate", {"expression": "1 / 0"})
        assert r.success is False
        assert "Division by zero" in r.error

    @pytest.mark.asyncio
    async def test_invalid_expression(self, online_cipher: Cipher):
        r = await online_cipher.execute("calculate", {"expression": "not a math"})
        assert r.success is False

    @pytest.mark.asyncio
    async def test_empty_expression(self, online_cipher: Cipher):
        r = await online_cipher.execute("calculate", {"expression": ""})
        assert r.success is False

    @pytest.mark.asyncio
    async def test_confidence_is_1(self, online_cipher: Cipher):
        r = await online_cipher.execute("calculate", {"expression": "2 + 2"})
        assert r.content["confidence"] == 1.0

    @pytest.mark.asyncio
    async def test_no_eval_injection(self, online_cipher: Cipher):
        r = await online_cipher.execute(
            "calculate", {"expression": "__import__('os').system('echo hacked')"}
        )
        assert r.success is False


# --- Data analysis tests ---

class TestDataAnalyze:
    @pytest.mark.asyncio
    async def test_basic_stats(self, online_cipher: Cipher):
        r = await online_cipher.execute("data_analyze", {
            "data": [10, 20, 30, 40, 50],
        })
        assert r.success is True
        assert r.content["results"]["mean"] == 30.0
        assert r.content["results"]["median"] == 30.0
        assert r.content["results"]["min"] == 10.0
        assert r.content["results"]["max"] == 50.0

    @pytest.mark.asyncio
    async def test_custom_operations(self, online_cipher: Cipher):
        r = await online_cipher.execute("data_analyze", {
            "data": [1, 2, 3, 4, 5],
            "operations": ["sum", "range"],
        })
        assert r.content["results"]["sum"] == 15.0
        assert r.content["results"]["range"] == 4.0

    @pytest.mark.asyncio
    async def test_empty_data_fails(self, online_cipher: Cipher):
        r = await online_cipher.execute("data_analyze", {"data": []})
        assert r.success is False

    @pytest.mark.asyncio
    async def test_non_numeric_fails(self, online_cipher: Cipher):
        r = await online_cipher.execute("data_analyze", {"data": ["a", "b"]})
        assert r.success is False

    @pytest.mark.asyncio
    async def test_single_value_stdev(self, online_cipher: Cipher):
        r = await online_cipher.execute("data_analyze", {
            "data": [42], "operations": ["stdev"],
        })
        assert r.content["results"]["stdev"] == 0.0


# --- Unit conversion tests ---

class TestUnitConvert:
    @pytest.mark.asyncio
    async def test_meters_to_feet(self, online_cipher: Cipher):
        r = await online_cipher.execute("unit_convert", {
            "value": 1, "from_unit": "m", "to_unit": "ft",
        })
        assert r.success is True
        assert r.content["result"] == pytest.approx(3.28084, rel=1e-3)

    @pytest.mark.asyncio
    async def test_kg_to_lb(self, online_cipher: Cipher):
        r = await online_cipher.execute("unit_convert", {
            "value": 1, "from_unit": "kg", "to_unit": "lb",
        })
        assert r.content["result"] == pytest.approx(2.20462, rel=1e-3)

    @pytest.mark.asyncio
    async def test_celsius_to_fahrenheit(self, online_cipher: Cipher):
        r = await online_cipher.execute("unit_convert", {
            "value": 100, "from_unit": "C", "to_unit": "F",
        })
        assert r.content["result"] == pytest.approx(212.0)

    @pytest.mark.asyncio
    async def test_fahrenheit_to_celsius(self, online_cipher: Cipher):
        r = await online_cipher.execute("unit_convert", {
            "value": 32, "from_unit": "F", "to_unit": "C",
        })
        assert r.content["result"] == pytest.approx(0.0)

    @pytest.mark.asyncio
    async def test_gb_to_mb(self, online_cipher: Cipher):
        r = await online_cipher.execute("unit_convert", {
            "value": 1, "from_unit": "gb", "to_unit": "mb",
        })
        assert r.content["result"] == pytest.approx(1024.0)

    @pytest.mark.asyncio
    async def test_incompatible_units_fails(self, online_cipher: Cipher):
        r = await online_cipher.execute("unit_convert", {
            "value": 1, "from_unit": "kg", "to_unit": "m",
        })
        assert r.success is False

    @pytest.mark.asyncio
    async def test_missing_value_fails(self, online_cipher: Cipher):
        r = await online_cipher.execute("unit_convert", {
            "from_unit": "m", "to_unit": "ft",
        })
        assert r.success is False

    @pytest.mark.asyncio
    async def test_missing_units_fails(self, online_cipher: Cipher):
        r = await online_cipher.execute("unit_convert", {"value": 1})
        assert r.success is False


# --- Logic verify tests ---

class TestLogicVerify:
    @pytest.mark.asyncio
    async def test_basic_verification(self, online_cipher: Cipher):
        r = await online_cipher.execute("logic_verify", {
            "premises": ["All men are mortal", "Socrates is a man"],
            "conclusion": "Socrates is mortal",
        })
        assert r.success is True
        assert r.content["structural_valid"] is True

    @pytest.mark.asyncio
    async def test_no_premises_fails(self, online_cipher: Cipher):
        r = await online_cipher.execute("logic_verify", {
            "premises": [], "conclusion": "Something",
        })
        assert r.success is False

    @pytest.mark.asyncio
    async def test_no_conclusion_fails(self, online_cipher: Cipher):
        r = await online_cipher.execute("logic_verify", {
            "premises": ["A is B"], "conclusion": "",
        })
        assert r.success is False


# --- Unknown tool ---

class TestUnknownTool:
    @pytest.mark.asyncio
    async def test_unknown_tool_fails(self, online_cipher: Cipher):
        r = await online_cipher.execute("nonexistent", {})
        assert r.success is False
