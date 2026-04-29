"""
Tests for Omen's absorbed Cipher surface (Phase A merge).
==========================================================
These mirror the pre-merge tests/test_cipher.py but exercise the
seven absorbed math/stats/finance/date/logic tools through
Omen.execute() rather than directly against the old Cipher module.
Behavior must be identical: same tool names, same return shapes,
same error semantics.

The two backward-compat aliases (data_analyze → statistics,
logic_verify → logic_check) are also exercised through Omen.
"""

import math
import pytest
from pathlib import Path
from typing import Any

from modules.base import ModuleStatus, ToolResult
from modules.omen.omen import Omen


@pytest.fixture
def omen(tmp_path: Path) -> Omen:
    """Bare Omen instance with a tmp-path-scoped working dir."""
    config = {"project_root": str(tmp_path), "teaching_mode": False}
    return Omen(config)


@pytest.fixture
async def online_omen(omen: Omen) -> Omen:
    """Initialized Omen — Cipher tools dispatch via Omen.execute()."""
    await omen.initialize()
    return omen


# --- Surface check ---


class TestAbsorbedCipherSurface:
    """Verify the 7 absorbed Cipher tools (+2 aliases) are exposed by Omen."""

    def test_all_7_tools_in_get_tools(self, omen: Omen):
        """Omen.get_tools() exposes every absorbed Cipher tool by name."""
        names = {t["name"] for t in omen.get_tools()}
        for tool in ("calculate", "unit_convert", "date_math",
                     "percentage", "financial", "statistics", "logic_check"):
            assert tool in names, f"{tool} missing from Omen.get_tools()"

    def test_absorbed_tools_autonomous(self, omen: Omen):
        """All 7 absorbed Cipher tools have permission_level='autonomous'."""
        absorbed = {"calculate", "unit_convert", "date_math",
                    "percentage", "financial", "statistics", "logic_check"}
        for tool in omen.get_tools():
            if tool["name"] in absorbed:
                assert tool["permission_level"] == "autonomous", (
                    f"{tool['name']} should be autonomous"
                )

    @pytest.mark.asyncio
    async def test_data_analyze_alias_dispatches(self, online_omen: Omen):
        """Backward-compat alias data_analyze → statistics."""
        r = await online_omen.execute("data_analyze", {"data": [1, 2, 3]})
        assert r.success is True
        assert r.content["results"]["mean"] == 2.0

    @pytest.mark.asyncio
    async def test_logic_verify_alias_dispatches(self, online_omen: Omen):
        """Backward-compat alias logic_verify → logic_check."""
        r = await online_omen.execute("logic_verify", {
            "premises": ["A implies B", "A is true"],
            "conclusion": "B is true",
        })
        assert r.success is True
        assert r.content["structural_valid"] is True


# --- Calculate tests ---


class TestCalculate:
    @pytest.mark.asyncio
    async def test_basic_addition(self, online_omen: Omen):
        r = await online_omen.execute("calculate", {"expression": "2 + 3"})
        assert r.success is True
        assert r.content["result"] == 5.0

    @pytest.mark.asyncio
    async def test_multiplication(self, online_omen: Omen):
        r = await online_omen.execute("calculate", {"expression": "6 * 7"})
        assert r.content["result"] == 42.0

    @pytest.mark.asyncio
    async def test_order_of_operations(self, online_omen: Omen):
        r = await online_omen.execute("calculate", {"expression": "2 + 3 * 4"})
        assert r.content["result"] == 14.0

    @pytest.mark.asyncio
    async def test_parentheses(self, online_omen: Omen):
        r = await online_omen.execute("calculate", {"expression": "(2 + 3) * 4"})
        assert r.content["result"] == 20.0

    @pytest.mark.asyncio
    async def test_exponentiation(self, online_omen: Omen):
        r = await online_omen.execute("calculate", {"expression": "2 ** 10"})
        assert r.content["result"] == 1024.0

    @pytest.mark.asyncio
    async def test_floor_division(self, online_omen: Omen):
        r = await online_omen.execute("calculate", {"expression": "17 // 5"})
        assert r.content["result"] == 3.0

    @pytest.mark.asyncio
    async def test_modulo(self, online_omen: Omen):
        r = await online_omen.execute("calculate", {"expression": "17 % 5"})
        assert r.content["result"] == 2.0

    @pytest.mark.asyncio
    async def test_negative(self, online_omen: Omen):
        r = await online_omen.execute("calculate", {"expression": "-5 + 3"})
        assert r.content["result"] == -2.0

    @pytest.mark.asyncio
    async def test_sqrt(self, online_omen: Omen):
        r = await online_omen.execute("calculate", {"expression": "sqrt(144)"})
        assert r.content["result"] == 12.0

    @pytest.mark.asyncio
    async def test_pi(self, online_omen: Omen):
        r = await online_omen.execute("calculate", {"expression": "pi"})
        assert r.content["result"] == pytest.approx(math.pi)

    @pytest.mark.asyncio
    async def test_trig(self, online_omen: Omen):
        r = await online_omen.execute("calculate", {"expression": "sin(0)"})
        assert r.content["result"] == pytest.approx(0.0)

    @pytest.mark.asyncio
    async def test_steps_returned(self, online_omen: Omen):
        r = await online_omen.execute("calculate", {"expression": "2 + 3 * 4"})
        assert r.success is True
        assert "steps" in r.content
        assert isinstance(r.content["steps"], list)
        assert len(r.content["steps"]) > 0

    @pytest.mark.asyncio
    async def test_steps_simple_expression(self, online_omen: Omen):
        r = await online_omen.execute("calculate", {"expression": "sqrt(16)"})
        assert r.content["steps"][0]["result"] == 4.0

    @pytest.mark.asyncio
    async def test_division_by_zero(self, online_omen: Omen):
        r = await online_omen.execute("calculate", {"expression": "1 / 0"})
        assert r.success is False
        assert "Division by zero" in r.error

    @pytest.mark.asyncio
    async def test_natural_language_returns_needs_reasoning(self, online_omen: Omen):
        """Natural language input returns success with needs_reasoning flag."""
        r = await online_omen.execute("calculate", {"expression": "not a math"})
        assert r.success is True
        assert r.content["needs_reasoning"] is True
        assert r.content["result"] is None

    @pytest.mark.asyncio
    async def test_word_problem_returns_needs_reasoning(self, online_omen: Omen):
        """Word problems route to reasoning instead of failing."""
        r = await online_omen.execute(
            "calculate", {"expression": "17 sheep, all but 9 die. How many are left?"}
        )
        assert r.success is True
        assert r.content["needs_reasoning"] is True

    @pytest.mark.asyncio
    async def test_natural_language_with_extractable_math(self, online_omen: Omen):
        """Natural language wrapping a simple expression gets extracted."""
        r = await online_omen.execute(
            "calculate", {"expression": "calculate 2 + 3"}
        )
        assert r.success is True
        assert r.content["result"] == 5.0
        assert "needs_reasoning" not in r.content

    @pytest.mark.asyncio
    async def test_natural_language_what_is(self, online_omen: Omen):
        """'What is 10 * 5' should extract and compute."""
        r = await online_omen.execute(
            "calculate", {"expression": "what is 10 * 5"}
        )
        assert r.success is True
        assert r.content["result"] == 50.0

    @pytest.mark.asyncio
    async def test_currency_symbol_stripped(self, online_omen: Omen):
        """Currency symbols get stripped before evaluation."""
        r = await online_omen.execute(
            "calculate", {"expression": "what is $1200 + $800"}
        )
        assert r.success is True
        assert r.content["result"] == 2000.0

    @pytest.mark.asyncio
    async def test_reasoning_metadata_flag(self, online_omen: Omen):
        """Needs-reasoning results include metadata for orchestrator routing."""
        r = await online_omen.execute(
            "calculate",
            {"expression": "If I have 3 crews and each takes 2 hours, what is the total?"},
        )
        assert r.success is True
        assert r.content["needs_reasoning"] is True
        assert r.metadata.get("needs_reasoning") is True

    @pytest.mark.asyncio
    async def test_empty_expression(self, online_omen: Omen):
        r = await online_omen.execute("calculate", {"expression": ""})
        assert r.success is False

    @pytest.mark.asyncio
    async def test_confidence_is_1(self, online_omen: Omen):
        r = await online_omen.execute("calculate", {"expression": "2 + 2"})
        assert r.content["confidence"] == 1.0

    @pytest.mark.asyncio
    async def test_no_eval_injection(self, online_omen: Omen):
        r = await online_omen.execute(
            "calculate", {"expression": "__import__('os').system('echo hacked')"}
        )
        assert r.success is False

    @pytest.mark.asyncio
    async def test_no_exec_injection(self, online_omen: Omen):
        r = await online_omen.execute(
            "calculate", {"expression": "exec('print(1)')"}
        )
        assert r.success is False

    @pytest.mark.asyncio
    async def test_no_lambda(self, online_omen: Omen):
        r = await online_omen.execute(
            "calculate", {"expression": "(lambda: 1)()"}
        )
        assert r.success is False


# --- Unit conversion tests ---


class TestUnitConvert:
    @pytest.mark.asyncio
    async def test_meters_to_feet(self, online_omen: Omen):
        r = await online_omen.execute("unit_convert", {
            "value": 1, "from_unit": "m", "to_unit": "ft",
        })
        assert r.success is True
        assert r.content["result"] == pytest.approx(3.28084, rel=1e-3)

    @pytest.mark.asyncio
    async def test_kg_to_lb(self, online_omen: Omen):
        r = await online_omen.execute("unit_convert", {
            "value": 1, "from_unit": "kg", "to_unit": "lb",
        })
        assert r.content["result"] == pytest.approx(2.20462, rel=1e-3)

    @pytest.mark.asyncio
    async def test_celsius_to_fahrenheit(self, online_omen: Omen):
        r = await online_omen.execute("unit_convert", {
            "value": 100, "from_unit": "C", "to_unit": "F",
        })
        assert r.content["result"] == pytest.approx(212.0)

    @pytest.mark.asyncio
    async def test_fahrenheit_to_celsius(self, online_omen: Omen):
        r = await online_omen.execute("unit_convert", {
            "value": 32, "from_unit": "F", "to_unit": "C",
        })
        assert r.content["result"] == pytest.approx(0.0)

    @pytest.mark.asyncio
    async def test_kelvin_conversion(self, online_omen: Omen):
        r = await online_omen.execute("unit_convert", {
            "value": 0, "from_unit": "C", "to_unit": "K",
        })
        assert r.content["result"] == pytest.approx(273.15)

    @pytest.mark.asyncio
    async def test_gb_to_mb(self, online_omen: Omen):
        r = await online_omen.execute("unit_convert", {
            "value": 1, "from_unit": "gb", "to_unit": "mb",
        })
        assert r.content["result"] == pytest.approx(1024.0)

    @pytest.mark.asyncio
    async def test_sqft_to_sqm(self, online_omen: Omen):
        r = await online_omen.execute("unit_convert", {
            "value": 100, "from_unit": "sqft", "to_unit": "sqm",
        })
        assert r.success is True
        assert r.content["result"] == pytest.approx(9.2903, rel=1e-3)
        assert r.content["category"] == "area"

    @pytest.mark.asyncio
    async def test_acre_to_hectare(self, online_omen: Omen):
        r = await online_omen.execute("unit_convert", {
            "value": 1, "from_unit": "acre", "to_unit": "hectare",
        })
        assert r.content["result"] == pytest.approx(0.4047, rel=1e-3)

    @pytest.mark.asyncio
    async def test_tbsp_to_tsp(self, online_omen: Omen):
        r = await online_omen.execute("unit_convert", {
            "value": 1, "from_unit": "tbsp", "to_unit": "tsp",
        })
        assert r.success is True
        assert r.content["result"] == pytest.approx(3.0, rel=1e-1)

    @pytest.mark.asyncio
    async def test_fl_oz_to_ml(self, online_omen: Omen):
        r = await online_omen.execute("unit_convert", {
            "value": 1, "from_unit": "fl_oz", "to_unit": "ml",
        })
        assert r.success is True
        assert r.content["result"] == pytest.approx(29.5735, rel=1e-3)

    @pytest.mark.asyncio
    async def test_sec_alias(self, online_omen: Omen):
        r = await online_omen.execute("unit_convert", {
            "value": 120, "from_unit": "sec", "to_unit": "min",
        })
        assert r.success is True
        assert r.content["result"] == pytest.approx(2.0)

    @pytest.mark.asyncio
    async def test_formula_used_in_result(self, online_omen: Omen):
        r = await online_omen.execute("unit_convert", {
            "value": 1, "from_unit": "m", "to_unit": "ft",
        })
        assert "formula_used" in r.content

    @pytest.mark.asyncio
    async def test_incompatible_units_fails(self, online_omen: Omen):
        r = await online_omen.execute("unit_convert", {
            "value": 1, "from_unit": "kg", "to_unit": "m",
        })
        assert r.success is False

    @pytest.mark.asyncio
    async def test_missing_value_fails(self, online_omen: Omen):
        r = await online_omen.execute("unit_convert", {
            "from_unit": "m", "to_unit": "ft",
        })
        assert r.success is False

    @pytest.mark.asyncio
    async def test_missing_units_fails(self, online_omen: Omen):
        r = await online_omen.execute("unit_convert", {"value": 1})
        assert r.success is False


# --- Date math tests ---


class TestDateMath:
    @pytest.mark.asyncio
    async def test_add_days(self, online_omen: Omen):
        r = await online_omen.execute("date_math", {
            "operation": "add", "date": "2026-01-15", "days": 10,
        })
        assert r.success is True
        assert r.content["result_date"] == "2026-01-25"

    @pytest.mark.asyncio
    async def test_add_weeks(self, online_omen: Omen):
        r = await online_omen.execute("date_math", {
            "operation": "add", "date": "2026-01-01", "weeks": 2,
        })
        assert r.content["result_date"] == "2026-01-15"

    @pytest.mark.asyncio
    async def test_add_months_overflow(self, online_omen: Omen):
        """Jan 31 + 1 month should clamp to Feb 28."""
        r = await online_omen.execute("date_math", {
            "operation": "add", "date": "2026-01-31", "months": 1,
        })
        assert r.success is True
        assert r.content["result_date"] == "2026-02-28"

    @pytest.mark.asyncio
    async def test_add_years_leap(self, online_omen: Omen):
        """Feb 29 (leap year) + 1 year should clamp to Feb 28."""
        r = await online_omen.execute("date_math", {
            "operation": "add", "date": "2024-02-29", "years": 1,
        })
        assert r.success is True
        assert r.content["result_date"] == "2025-02-28"

    @pytest.mark.asyncio
    async def test_subtract_days(self, online_omen: Omen):
        r = await online_omen.execute("date_math", {
            "operation": "subtract", "date": "2026-01-15", "days": 5,
        })
        assert r.success is True
        assert r.content["result_date"] == "2026-01-10"

    @pytest.mark.asyncio
    async def test_subtract_months(self, online_omen: Omen):
        r = await online_omen.execute("date_math", {
            "operation": "subtract", "date": "2026-03-31", "months": 1,
        })
        assert r.success is True
        # March 31 - 1 month = Feb 28
        assert r.content["result_date"] == "2026-02-28"

    @pytest.mark.asyncio
    async def test_diff(self, online_omen: Omen):
        r = await online_omen.execute("date_math", {
            "operation": "diff", "date1": "2026-01-01", "date2": "2026-01-31",
        })
        assert r.success is True
        assert r.content["total_days"] == 30

    @pytest.mark.asyncio
    async def test_diff_negative(self, online_omen: Omen):
        """date2 before date1 should give negative days."""
        r = await online_omen.execute("date_math", {
            "operation": "diff", "date1": "2026-01-31", "date2": "2026-01-01",
        })
        assert r.content["total_days"] == -30

    @pytest.mark.asyncio
    async def test_day_of_week(self, online_omen: Omen):
        # 2026-04-05 is a Sunday
        r = await online_omen.execute("date_math", {
            "operation": "day_of_week", "date": "2026-04-05",
        })
        assert r.success is True
        assert r.content["day_of_week"] == "Sunday"
        assert r.content["is_weekend"] is True

    @pytest.mark.asyncio
    async def test_day_of_week_weekday(self, online_omen: Omen):
        # 2026-04-06 is a Monday
        r = await online_omen.execute("date_math", {
            "operation": "day_of_week", "date": "2026-04-06",
        })
        assert r.content["day_of_week"] == "Monday"
        assert r.content["is_weekend"] is False

    @pytest.mark.asyncio
    async def test_business_days(self, online_omen: Omen):
        # Mon Apr 6 to Fri Apr 10, 2026 = 5 business days
        r = await online_omen.execute("date_math", {
            "operation": "business_days", "date1": "2026-04-06", "date2": "2026-04-10",
        })
        assert r.success is True
        assert r.content["business_days"] == 5

    @pytest.mark.asyncio
    async def test_business_days_with_weekend(self, online_omen: Omen):
        # Mon Apr 6 to Mon Apr 13 = 6 business days (skip Sat+Sun)
        r = await online_omen.execute("date_math", {
            "operation": "business_days", "date1": "2026-04-06", "date2": "2026-04-13",
        })
        assert r.content["business_days"] == 6

    @pytest.mark.asyncio
    async def test_invalid_date(self, online_omen: Omen):
        r = await online_omen.execute("date_math", {
            "operation": "add", "date": "not-a-date", "days": 1,
        })
        assert r.success is False

    @pytest.mark.asyncio
    async def test_missing_operation(self, online_omen: Omen):
        r = await online_omen.execute("date_math", {"date": "2026-01-01"})
        assert r.success is False

    @pytest.mark.asyncio
    async def test_missing_date_for_add(self, online_omen: Omen):
        r = await online_omen.execute("date_math", {
            "operation": "add", "days": 5,
        })
        assert r.success is False


# --- Percentage tests ---


class TestPercentage:
    @pytest.mark.asyncio
    async def test_percent_of(self, online_omen: Omen):
        r = await online_omen.execute("percentage", {
            "operation": "of", "percent": 25, "value": 200,
        })
        assert r.success is True
        assert r.content["result"] == 50.0

    @pytest.mark.asyncio
    async def test_what_percent(self, online_omen: Omen):
        r = await online_omen.execute("percentage", {
            "operation": "what_percent", "value": 50, "total": 200,
        })
        assert r.success is True
        assert r.content["result"] == 25.0

    @pytest.mark.asyncio
    async def test_percent_change(self, online_omen: Omen):
        r = await online_omen.execute("percentage", {
            "operation": "change", "old_value": 100, "new_value": 150,
        })
        assert r.success is True
        assert r.content["result"] == 50.0
        assert r.content["direction"] == "increase"

    @pytest.mark.asyncio
    async def test_percent_change_decrease(self, online_omen: Omen):
        r = await online_omen.execute("percentage", {
            "operation": "change", "old_value": 200, "new_value": 150,
        })
        assert r.content["result"] == -25.0
        assert r.content["direction"] == "decrease"

    @pytest.mark.asyncio
    async def test_markup(self, online_omen: Omen):
        r = await online_omen.execute("percentage", {
            "operation": "markup", "cost": 80, "selling_price": 100,
        })
        assert r.success is True
        assert r.content["result"] == 25.0

    @pytest.mark.asyncio
    async def test_margin(self, online_omen: Omen):
        r = await online_omen.execute("percentage", {
            "operation": "margin", "cost": 80, "selling_price": 100,
        })
        assert r.success is True
        assert r.content["result"] == 20.0

    @pytest.mark.asyncio
    async def test_formula_in_result(self, online_omen: Omen):
        r = await online_omen.execute("percentage", {
            "operation": "of", "percent": 10, "value": 50,
        })
        assert "formula" in r.content

    @pytest.mark.asyncio
    async def test_what_percent_zero_total(self, online_omen: Omen):
        r = await online_omen.execute("percentage", {
            "operation": "what_percent", "value": 50, "total": 0,
        })
        assert r.success is False

    @pytest.mark.asyncio
    async def test_change_zero_old_value(self, online_omen: Omen):
        r = await online_omen.execute("percentage", {
            "operation": "change", "old_value": 0, "new_value": 100,
        })
        assert r.success is False

    @pytest.mark.asyncio
    async def test_markup_zero_cost(self, online_omen: Omen):
        r = await online_omen.execute("percentage", {
            "operation": "markup", "cost": 0, "selling_price": 100,
        })
        assert r.success is False

    @pytest.mark.asyncio
    async def test_margin_zero_selling(self, online_omen: Omen):
        r = await online_omen.execute("percentage", {
            "operation": "margin", "cost": 80, "selling_price": 0,
        })
        assert r.success is False

    @pytest.mark.asyncio
    async def test_missing_operation(self, online_omen: Omen):
        r = await online_omen.execute("percentage", {"percent": 10, "value": 100})
        assert r.success is False


# --- Financial tests ---


class TestFinancial:
    @pytest.mark.asyncio
    async def test_compound_interest(self, online_omen: Omen):
        # $1000 at 5% compounded monthly for 10 years
        r = await online_omen.execute("financial", {
            "operation": "compound_interest",
            "principal": 1000, "rate": 0.05,
            "compounds_per_year": 12, "years": 10,
        })
        assert r.success is True
        assert r.content["final_amount"] == pytest.approx(1647.01, rel=1e-3)
        assert r.content["interest_earned"] == pytest.approx(647.01, rel=1e-3)

    @pytest.mark.asyncio
    async def test_pmt(self, online_omen: Omen):
        # $200,000 mortgage at 6% for 30 years
        r = await online_omen.execute("financial", {
            "operation": "pmt",
            "principal": 200000, "annual_rate": 0.06, "years": 30,
        })
        assert r.success is True
        assert r.content["monthly_payment"] == pytest.approx(1199.10, rel=1e-2)

    @pytest.mark.asyncio
    async def test_pmt_zero_rate(self, online_omen: Omen):
        # $12,000 at 0% for 1 year = $1000/month
        r = await online_omen.execute("financial", {
            "operation": "pmt",
            "principal": 12000, "annual_rate": 0, "years": 1,
        })
        assert r.success is True
        assert r.content["monthly_payment"] == pytest.approx(1000.0)

    @pytest.mark.asyncio
    async def test_roi(self, online_omen: Omen):
        r = await online_omen.execute("financial", {
            "operation": "roi", "gain": 15000, "cost": 10000,
        })
        assert r.success is True
        assert r.content["roi_percent"] == 50.0

    @pytest.mark.asyncio
    async def test_break_even(self, online_omen: Omen):
        r = await online_omen.execute("financial", {
            "operation": "break_even",
            "fixed_costs": 10000, "price_per_unit": 50,
            "variable_cost_per_unit": 30,
        })
        assert r.success is True
        assert r.content["break_even_units"] == 500.0

    @pytest.mark.asyncio
    async def test_profit_loss_profit(self, online_omen: Omen):
        r = await online_omen.execute("financial", {
            "operation": "profit_loss", "revenue": 5000, "expenses": 3000,
        })
        assert r.success is True
        assert r.content["profit_loss"] == 2000.0
        assert r.content["is_profit"] is True

    @pytest.mark.asyncio
    async def test_profit_loss_loss(self, online_omen: Omen):
        r = await online_omen.execute("financial", {
            "operation": "profit_loss", "revenue": 3000, "expenses": 5000,
        })
        assert r.content["profit_loss"] == -2000.0
        assert r.content["is_profit"] is False

    @pytest.mark.asyncio
    async def test_disclaimer_metadata(self, online_omen: Omen):
        """Every financial result must include the disclaimer."""
        r = await online_omen.execute("financial", {
            "operation": "profit_loss", "revenue": 100, "expenses": 50,
        })
        assert r.metadata["disclaimer"] == "Mathematical calculation only. Not financial advice."

    @pytest.mark.asyncio
    async def test_disclaimer_on_error_too(self, online_omen: Omen):
        """Even failed financial calls include the disclaimer."""
        r = await online_omen.execute("financial", {
            "operation": "roi", "gain": 100, "cost": 0,
        })
        assert r.success is False
        assert r.metadata["disclaimer"] == "Mathematical calculation only. Not financial advice."

    @pytest.mark.asyncio
    async def test_roi_zero_cost(self, online_omen: Omen):
        r = await online_omen.execute("financial", {
            "operation": "roi", "gain": 100, "cost": 0,
        })
        assert r.success is False

    @pytest.mark.asyncio
    async def test_break_even_zero_margin(self, online_omen: Omen):
        r = await online_omen.execute("financial", {
            "operation": "break_even",
            "fixed_costs": 10000, "price_per_unit": 30,
            "variable_cost_per_unit": 30,
        })
        assert r.success is False

    @pytest.mark.asyncio
    async def test_pmt_zero_years(self, online_omen: Omen):
        r = await online_omen.execute("financial", {
            "operation": "pmt",
            "principal": 10000, "annual_rate": 0.05, "years": 0,
        })
        assert r.success is False

    @pytest.mark.asyncio
    async def test_missing_operation(self, online_omen: Omen):
        r = await online_omen.execute("financial", {"principal": 1000})
        assert r.success is False


# --- Statistics tests ---


class TestStatistics:
    @pytest.mark.asyncio
    async def test_basic_stats(self, online_omen: Omen):
        r = await online_omen.execute("statistics", {
            "data": [10, 20, 30, 40, 50],
        })
        assert r.success is True
        assert r.content["results"]["mean"] == 30.0
        assert r.content["results"]["median"] == 30.0
        assert r.content["results"]["min"] == 10.0
        assert r.content["results"]["max"] == 50.0

    @pytest.mark.asyncio
    async def test_custom_operations(self, online_omen: Omen):
        r = await online_omen.execute("statistics", {
            "data": [1, 2, 3, 4, 5],
            "operations": ["sum", "range"],
        })
        assert r.content["results"]["sum"] == 15.0
        assert r.content["results"]["range"] == 4.0

    @pytest.mark.asyncio
    async def test_percentiles(self, online_omen: Omen):
        r = await online_omen.execute("statistics", {
            "data": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
            "operations": ["percentile_25", "percentile_50", "percentile_75"],
        })
        assert r.success is True
        assert r.content["results"]["percentile_25"] == pytest.approx(2.75, rel=1e-1)
        assert r.content["results"]["percentile_50"] == pytest.approx(5.5)
        assert r.content["results"]["percentile_75"] == pytest.approx(8.25, rel=1e-1)

    @pytest.mark.asyncio
    async def test_percentile_single_value(self, online_omen: Omen):
        """Single data point — percentiles should return that value."""
        r = await online_omen.execute("statistics", {
            "data": [42],
            "operations": ["percentile_25", "percentile_75"],
        })
        assert r.success is True
        assert r.content["results"]["percentile_25"] == 42
        assert r.content["results"]["percentile_75"] == 42

    @pytest.mark.asyncio
    async def test_mode(self, online_omen: Omen):
        r = await online_omen.execute("statistics", {
            "data": [1, 2, 2, 3, 3, 3],
            "operations": ["mode"],
        })
        assert r.content["results"]["mode"] == 3

    @pytest.mark.asyncio
    async def test_empty_data_fails(self, online_omen: Omen):
        r = await online_omen.execute("statistics", {"data": []})
        assert r.success is False

    @pytest.mark.asyncio
    async def test_non_numeric_fails(self, online_omen: Omen):
        r = await online_omen.execute("statistics", {"data": ["a", "b"]})
        assert r.success is False

    @pytest.mark.asyncio
    async def test_single_value_stdev(self, online_omen: Omen):
        r = await online_omen.execute("statistics", {
            "data": [42], "operations": ["stdev"],
        })
        assert r.content["results"]["stdev"] == 0.0

    @pytest.mark.asyncio
    async def test_backward_compat_data_analyze(self, online_omen: Omen):
        """Old 'data_analyze' name should still work via Omen."""
        r = await online_omen.execute("data_analyze", {
            "data": [1, 2, 3],
        })
        assert r.success is True
        assert r.content["results"]["mean"] == 2.0


# --- Logic check tests ---


class TestLogicCheck:
    @pytest.mark.asyncio
    async def test_basic_verification(self, online_omen: Omen):
        r = await online_omen.execute("logic_check", {
            "premises": ["All men are mortal", "Socrates is a man"],
            "conclusion": "Socrates is mortal",
        })
        assert r.success is True
        assert r.content["structural_valid"] is True

    @pytest.mark.asyncio
    async def test_no_premises_fails(self, online_omen: Omen):
        r = await online_omen.execute("logic_check", {
            "premises": [], "conclusion": "Something",
        })
        assert r.success is False

    @pytest.mark.asyncio
    async def test_no_conclusion_fails(self, online_omen: Omen):
        r = await online_omen.execute("logic_check", {
            "premises": ["A is B"], "conclusion": "",
        })
        assert r.success is False

    @pytest.mark.asyncio
    async def test_truth_table_2_vars(self, online_omen: Omen):
        r = await online_omen.execute("logic_check", {
            "variables": ["A", "B"],
            "expression": "A and B",
        })
        assert r.success is True
        assert r.content["total_rows"] == 4
        table = r.content["truth_table"]
        # Only True when both True
        true_rows = [row for row in table if row["result"] is True]
        assert len(true_rows) == 1
        assert true_rows[0]["A"] is True
        assert true_rows[0]["B"] is True

    @pytest.mark.asyncio
    async def test_truth_table_3_vars(self, online_omen: Omen):
        r = await online_omen.execute("logic_check", {
            "variables": ["A", "B", "C"],
            "expression": "A or (B and C)",
        })
        assert r.success is True
        assert r.content["total_rows"] == 8

    @pytest.mark.asyncio
    async def test_truth_table_not(self, online_omen: Omen):
        r = await online_omen.execute("logic_check", {
            "variables": ["A"],
            "expression": "not A",
        })
        assert r.success is True
        table = r.content["truth_table"]
        assert len(table) == 2
        # When A=True, result=False and vice versa
        for row in table:
            assert row["result"] == (not row["A"])

    @pytest.mark.asyncio
    async def test_truth_table_or(self, online_omen: Omen):
        r = await online_omen.execute("logic_check", {
            "variables": ["A", "B"],
            "expression": "A or B",
        })
        assert r.success is True
        table = r.content["truth_table"]
        false_rows = [row for row in table if row["result"] is False]
        assert len(false_rows) == 1  # Only False when both False

    @pytest.mark.asyncio
    async def test_truth_table_invalid_expression(self, online_omen: Omen):
        r = await online_omen.execute("logic_check", {
            "variables": ["A", "B"],
            "expression": "A +++ B",
        })
        assert r.success is False

    @pytest.mark.asyncio
    async def test_truth_table_too_many_vars(self, online_omen: Omen):
        r = await online_omen.execute("logic_check", {
            "variables": ["A", "B", "C", "D"],
            "expression": "A and B",
        })
        assert r.success is False

    @pytest.mark.asyncio
    async def test_backward_compat_logic_verify(self, online_omen: Omen):
        """Old 'logic_verify' name should still work via Omen."""
        r = await online_omen.execute("logic_verify", {
            "premises": ["A implies B", "A is true"],
            "conclusion": "B is true",
        })
        assert r.success is True
        assert r.content["structural_valid"] is True


# --- Module stamp on absorbed tools ---


class TestAbsorbedToolModuleStamp:
    """Absorbed tools should report module="omen" on their ToolResult."""

    @pytest.mark.asyncio
    async def test_calculate_module_stamp(self, online_omen: Omen):
        r = await online_omen.execute("calculate", {"expression": "1 + 1"})
        assert r.module == "omen"

    @pytest.mark.asyncio
    async def test_unit_convert_module_stamp(self, online_omen: Omen):
        r = await online_omen.execute("unit_convert", {
            "value": 1, "from_unit": "m", "to_unit": "ft",
        })
        assert r.module == "omen"

    @pytest.mark.asyncio
    async def test_financial_module_stamp(self, online_omen: Omen):
        r = await online_omen.execute("financial", {
            "operation": "profit_loss", "revenue": 100, "expenses": 50,
        })
        assert r.module == "omen"
