"""
Cipher — Math, Logic, and Complex Reasoning
=============================================
Precision over speed. When the answer has to be right, not just fast.

Design Principle: Cipher takes whatever time is needed to get the
answer right. Verify before delivering. Flag uncertainty.

Phase 1: Safe expression evaluation, statistics, unit conversion,
date math, percentages, financial calculations. No LLM — pure computation.
"""

import ast
import calendar
import logging
import math
import operator
import statistics
import time
from datetime import date, datetime, timedelta
from itertools import product
from typing import Any

from modules.base import BaseModule, ModuleStatus, ToolResult

logger = logging.getLogger("shadow.cipher")

# Safe operators for expression evaluation
_SAFE_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}

# Safe math functions
_SAFE_FUNCTIONS = {
    "sqrt": math.sqrt,
    "abs": abs,
    "round": round,
    "sin": math.sin,
    "cos": math.cos,
    "tan": math.tan,
    "log": math.log,
    "log10": math.log10,
    "log2": math.log2,
    "exp": math.exp,
    "ceil": math.ceil,
    "floor": math.floor,
    "pi": math.pi,
    "e": math.e,
}

# Unit conversion tables — all values relative to base unit
_CONVERSIONS: dict[str, dict[str, float]] = {
    "length": {
        "mm": 0.001, "cm": 0.01, "m": 1.0, "km": 1000.0,
        "in": 0.0254, "ft": 0.3048, "yd": 0.9144, "mi": 1609.344,
    },
    "weight": {
        "mg": 0.000001, "g": 0.001, "kg": 1.0,
        "oz": 0.0283495, "lb": 0.453592, "ton": 907.185,
    },
    "volume": {
        "ml": 0.001, "l": 1.0, "gal": 3.78541, "qt": 0.946353,
        "pt": 0.473176, "cup": 0.236588,
        "tbsp": 0.0147868, "tsp": 0.00492892,
        "fl_oz": 0.0295735, "floz": 0.0295735,
    },
    "area": {
        "sqm": 1.0, "sqft": 0.092903, "acre": 4046.86, "hectare": 10000.0,
    },
    "digital": {
        "b": 1.0, "kb": 1024.0, "mb": 1048576.0,
        "gb": 1073741824.0, "tb": 1099511627776.0,
    },
    "time": {
        "sec": 1.0, "s": 1.0, "ms": 0.001, "min": 60.0, "hr": 3600.0,
        "day": 86400.0, "week": 604800.0,
    },
    "speed": {
        "m/s": 1.0, "km/h": 0.277778, "mph": 0.44704, "knot": 0.514444,
    },
}


def _safe_eval(node: ast.AST) -> float:
    """Recursively evaluate an AST node using only safe operations.

    Raises ValueError for unsupported operations.
    """
    if isinstance(node, ast.Expression):
        return _safe_eval(node.body)
    elif isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float)):
            return float(node.value)
        raise ValueError(f"Unsupported constant: {node.value!r}")
    elif isinstance(node, ast.BinOp):
        op_func = _SAFE_OPS.get(type(node.op))
        if op_func is None:
            raise ValueError(f"Unsupported operator: {type(node.op).__name__}")
        left = _safe_eval(node.left)
        right = _safe_eval(node.right)
        return op_func(left, right)
    elif isinstance(node, ast.UnaryOp):
        op_func = _SAFE_OPS.get(type(node.op))
        if op_func is None:
            raise ValueError(f"Unsupported unary operator: {type(node.op).__name__}")
        return op_func(_safe_eval(node.operand))
    elif isinstance(node, ast.Call):
        if isinstance(node.func, ast.Name) and node.func.id in _SAFE_FUNCTIONS:
            func = _SAFE_FUNCTIONS[node.func.id]
            if callable(func):
                args = [_safe_eval(arg) for arg in node.args]
                return float(func(*args))
            return float(func)  # Constants like pi, e
        raise ValueError(f"Unsupported function: {ast.dump(node.func)}")
    elif isinstance(node, ast.Name):
        if node.id in _SAFE_FUNCTIONS:
            val = _SAFE_FUNCTIONS[node.id]
            if not callable(val):
                return float(val)
        raise ValueError(f"Unsupported name: {node.id}")
    else:
        raise ValueError(f"Unsupported expression: {type(node).__name__}")


def _collect_steps(node: ast.AST) -> list[dict[str, Any]]:
    """Walk an AST and collect evaluation steps for compound expressions.

    Returns a list of step dicts with sub_expression and result.
    """
    steps: list[dict[str, Any]] = []

    def _walk(n: ast.AST) -> float:
        result = _safe_eval(n)
        # Only record steps for compound nodes (not leaves)
        if isinstance(n, (ast.BinOp, ast.Call)):
            steps.append({
                "step": len(steps) + 1,
                "sub_expression": ast.unparse(n),
                "result": result,
            })
        return result

    if isinstance(node, ast.Expression):
        _walk(node.body)
    else:
        _walk(node)

    return steps


def _safe_bool_eval(node: ast.AST, variables: dict[str, bool]) -> bool:
    """Evaluate a boolean AST expression safely.

    Only allows: True, False, variable names, and/or/not operators.
    Raises ValueError for anything else.
    """
    if isinstance(node, ast.Expression):
        return _safe_bool_eval(node.body, variables)
    elif isinstance(node, ast.Constant):
        if isinstance(node.value, bool):
            return node.value
        raise ValueError(f"Unsupported constant in boolean expression: {node.value!r}")
    elif isinstance(node, ast.Name):
        if node.id in ("True", "False"):
            return node.id == "True"
        if node.id in variables:
            return variables[node.id]
        raise ValueError(f"Unknown variable: {node.id}")
    elif isinstance(node, ast.BoolOp):
        if isinstance(node.op, ast.And):
            return all(_safe_bool_eval(v, variables) for v in node.values)
        elif isinstance(node.op, ast.Or):
            return any(_safe_bool_eval(v, variables) for v in node.values)
        raise ValueError(f"Unsupported boolean operator: {type(node.op).__name__}")
    elif isinstance(node, ast.UnaryOp):
        if isinstance(node.op, ast.Not):
            return not _safe_bool_eval(node.operand, variables)
        raise ValueError(f"Unsupported unary operator in boolean: {type(node.op).__name__}")
    elif isinstance(node, ast.Compare):
        # Support simple comparisons like A == B
        raise ValueError("Comparisons not supported in Phase 1 truth tables")
    else:
        raise ValueError(f"Unsupported boolean expression: {type(node).__name__}")


def _add_months(d: date, months: int) -> date:
    """Add (or subtract) months to a date, clamping day to valid range."""
    month = d.month - 1 + months
    year = d.year + month // 12
    month = month % 12 + 1
    day = min(d.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def _parse_date(date_str: str) -> date:
    """Parse an ISO date string (YYYY-MM-DD) to a date object."""
    return datetime.strptime(date_str.strip(), "%Y-%m-%d").date()


def _count_business_days(start: date, end: date) -> int:
    """Count weekdays (Mon-Fri) between two dates, inclusive."""
    if start > end:
        start, end = end, start

    total_days = (end - start).days + 1
    full_weeks = total_days // 7
    remaining = total_days % 7

    # Full weeks contribute 5 business days each
    bdays = full_weeks * 5

    # Count business days in the remaining partial week
    start_weekday = start.weekday()
    for i in range(remaining):
        if (start_weekday + full_weeks * 7 + i) % 7 < 5:
            bdays += 1

    return bdays


class Cipher(BaseModule):
    """Math, logic, and complex reasoning specialist.

    Handles calculations, statistics, unit conversion, date math,
    percentages, and financial analysis with precision.
    No LLM needed — pure computation.
    """

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        """Initialize Cipher.

        Args:
            config: Module configuration.
        """
        super().__init__(
            name="cipher",
            description="Math, logic, and complex reasoning — precision over speed",
        )
        self._config = config or {}

    async def initialize(self) -> None:
        """Start Cipher."""
        self.status = ModuleStatus.ONLINE
        self._initialized_at = datetime.now()
        logger.info("Cipher online. Ready for computation.")

    async def execute(self, tool_name: str, params: dict[str, Any]) -> ToolResult:
        """Execute a Cipher tool.

        Args:
            tool_name: Which tool to invoke.
            params: Tool-specific parameters.

        Returns:
            ToolResult with success/failure and content.
        """
        start = time.time()
        try:
            handlers = {
                "calculate": self._calculate,
                "unit_convert": self._unit_convert,
                "date_math": self._date_math,
                "percentage": self._percentage,
                "financial": self._financial,
                "statistics": self._statistics,
                "data_analyze": self._statistics,        # backward compat
                "logic_check": self._logic_check,
                "logic_verify": self._logic_check,       # backward compat
            }

            handler = handlers.get(tool_name)
            if handler is None:
                result = ToolResult(
                    success=False, content=None, tool_name=tool_name,
                    module=self.name, error=f"Unknown tool: {tool_name}",
                )
            else:
                result = handler(params)

            result.execution_time_ms = (time.time() - start) * 1000
            self._record_call(result.success)
            return result

        except Exception as e:
            elapsed = (time.time() - start) * 1000
            self._record_call(False)
            logger.error("Cipher tool '%s' failed: %s", tool_name, e)
            return ToolResult(
                success=False, content=None, tool_name=tool_name,
                module=self.name, error=str(e), execution_time_ms=elapsed,
            )

    async def shutdown(self) -> None:
        """Shut down Cipher."""
        self.status = ModuleStatus.OFFLINE
        logger.info("Cipher offline.")

    def get_tools(self) -> list[dict[str, Any]]:
        """Return Cipher's tool definitions."""
        return [
            {
                "name": "calculate",
                "description": "Evaluate mathematical expressions safely (AST-based, no eval). "
                               "Supports arithmetic, math functions, returns result + steps",
                "parameters": {"expression": "str — math expression to evaluate"},
                "permission_level": "autonomous",
            },
            {
                "name": "unit_convert",
                "description": "Convert between units: length, weight, volume, temperature, "
                               "area, digital, time, speed",
                "parameters": {
                    "value": "float — numeric value to convert",
                    "from_unit": "str — source unit",
                    "to_unit": "str — target unit",
                },
                "permission_level": "autonomous",
            },
            {
                "name": "date_math",
                "description": "Date calculations: add/subtract time, difference between dates, "
                               "day of week, business days",
                "parameters": {
                    "operation": "str — add, subtract, diff, day_of_week, business_days",
                    "date": "str — ISO date (YYYY-MM-DD) for add/subtract/day_of_week",
                    "date1": "str — first date for diff/business_days",
                    "date2": "str — second date for diff/business_days",
                    "days": "int — days to add/subtract",
                    "weeks": "int — weeks to add/subtract",
                    "months": "int — months to add/subtract",
                    "years": "int — years to add/subtract",
                },
                "permission_level": "autonomous",
            },
            {
                "name": "percentage",
                "description": "Percentage operations: X% of Y, what percent, percent change, "
                               "markup, margin",
                "parameters": {
                    "operation": "str — of, what_percent, change, markup, margin",
                    "percent": "float", "value": "float", "total": "float",
                    "old_value": "float", "new_value": "float",
                    "cost": "float", "selling_price": "float",
                },
                "permission_level": "autonomous",
            },
            {
                "name": "financial",
                "description": "Financial math: compound interest, loan payment (PMT), ROI, "
                               "break-even, profit/loss. Not financial advice — just math",
                "parameters": {
                    "operation": "str — compound_interest, pmt, roi, break_even, profit_loss",
                    "principal": "float", "rate": "float",
                    "compounds_per_year": "int", "years": "int",
                    "annual_rate": "float", "gain": "float", "cost": "float",
                    "fixed_costs": "float", "price_per_unit": "float",
                    "variable_cost_per_unit": "float",
                    "revenue": "float", "expenses": "float",
                },
                "permission_level": "autonomous",
            },
            {
                "name": "statistics",
                "description": "Descriptive statistics on a list of numbers: mean, median, mode, "
                               "std_dev, min, max, range, sum, count, percentiles",
                "parameters": {
                    "data": "list[float] — numbers to analyze",
                    "operations": "list[str] — which stats to compute (default: all)",
                },
                "permission_level": "autonomous",
            },
            {
                "name": "logic_check",
                "description": "Boolean logic: truth tables for 2-3 variables, structural "
                               "analysis of premises/conclusions. Full reasoning in Phase 2+",
                "parameters": {
                    "variables": "list[str] — variable names for truth table",
                    "expression": "str — boolean expression for truth table",
                    "premises": "list[str] — premises for structural analysis",
                    "conclusion": "str — conclusion for structural analysis",
                },
                "permission_level": "autonomous",
            },
        ]

    # --- Tool implementations ---

    def _calculate(self, params: dict[str, Any]) -> ToolResult:
        """Evaluate a mathematical expression safely.

        Uses AST parsing with a whitelist of operators. No eval().

        Args:
            params: 'expression' (str) — the math expression to evaluate.
        """
        expression = params.get("expression", "")
        if not expression:
            return ToolResult(
                success=False, content=None, tool_name="calculate",
                module=self.name, error="Expression is required",
            )

        try:
            tree = ast.parse(expression.strip(), mode="eval")
            result = _safe_eval(tree)

            # Handle special float values
            if math.isinf(result):
                return ToolResult(
                    success=False, content=None, tool_name="calculate",
                    module=self.name, error="Result is infinite",
                )
            if math.isnan(result):
                return ToolResult(
                    success=False, content=None, tool_name="calculate",
                    module=self.name, error="Result is not a number",
                )

            # Collect evaluation steps
            steps = _collect_steps(tree)

            return ToolResult(
                success=True,
                content={
                    "expression": expression,
                    "result": result,
                    "steps": steps,
                    "confidence": 1.0,
                },
                tool_name="calculate",
                module=self.name,
            )

        except ZeroDivisionError:
            return ToolResult(
                success=False, content=None, tool_name="calculate",
                module=self.name, error="Division by zero",
            )
        except (ValueError, SyntaxError, TypeError) as e:
            return ToolResult(
                success=False, content=None, tool_name="calculate",
                module=self.name, error=f"Invalid expression: {e}",
            )

    def _unit_convert(self, params: dict[str, Any]) -> ToolResult:
        """Convert a value between units.

        Args:
            params: 'value' (float), 'from_unit' (str), 'to_unit' (str).
        """
        value = params.get("value")
        from_unit = params.get("from_unit", "").lower()
        to_unit = params.get("to_unit", "").lower()

        if value is None:
            return ToolResult(
                success=False, content=None, tool_name="unit_convert",
                module=self.name, error="Value is required",
            )

        if not from_unit or not to_unit:
            return ToolResult(
                success=False, content=None, tool_name="unit_convert",
                module=self.name, error="from_unit and to_unit are required",
            )

        try:
            value = float(value)
        except (ValueError, TypeError):
            return ToolResult(
                success=False, content=None, tool_name="unit_convert",
                module=self.name, error="Value must be a number",
            )

        # Temperature special case
        if from_unit in ("c", "f", "k") and to_unit in ("c", "f", "k"):
            result = self._convert_temperature(value, from_unit, to_unit)
            formula = self._temperature_formula(from_unit, to_unit)
            return ToolResult(
                success=True,
                content={
                    "input_value": value, "from": from_unit, "to": to_unit,
                    "result": result, "formula_used": formula, "confidence": 1.0,
                },
                tool_name="unit_convert",
                module=self.name,
            )

        # Find category
        for category, units in _CONVERSIONS.items():
            if from_unit in units and to_unit in units:
                base_value = value * units[from_unit]
                result = base_value / units[to_unit]
                return ToolResult(
                    success=True,
                    content={
                        "input_value": value, "from": from_unit, "to": to_unit,
                        "result": result, "category": category,
                        "formula_used": f"{value} {from_unit} × ({units[from_unit]} / {units[to_unit]}) = {result} {to_unit}",
                        "confidence": 1.0,
                    },
                    tool_name="unit_convert",
                    module=self.name,
                )

        return ToolResult(
            success=False, content=None, tool_name="unit_convert",
            module=self.name,
            error=f"Cannot convert between '{from_unit}' and '{to_unit}'. "
                  f"Units must be in the same category.",
        )

    @staticmethod
    def _convert_temperature(value: float, from_u: str, to_u: str) -> float:
        """Convert temperature between C, F, and K."""
        if from_u == "f":
            celsius = (value - 32) * 5 / 9
        elif from_u == "k":
            celsius = value - 273.15
        else:
            celsius = value

        if to_u == "f":
            return celsius * 9 / 5 + 32
        elif to_u == "k":
            return celsius + 273.15
        return celsius

    @staticmethod
    def _temperature_formula(from_u: str, to_u: str) -> str:
        """Return the formula string for a temperature conversion."""
        formulas = {
            ("c", "f"): "°F = °C × 9/5 + 32",
            ("f", "c"): "°C = (°F - 32) × 5/9",
            ("c", "k"): "K = °C + 273.15",
            ("k", "c"): "°C = K - 273.15",
            ("f", "k"): "K = (°F - 32) × 5/9 + 273.15",
            ("k", "f"): "°F = (K - 273.15) × 9/5 + 32",
        }
        return formulas.get((from_u, to_u), f"{from_u} → {to_u}")

    def _date_math(self, params: dict[str, Any]) -> ToolResult:
        """Perform date calculations.

        Args:
            params: 'operation' (str), plus operation-specific params.
        """
        operation = params.get("operation", "")
        if not operation:
            return ToolResult(
                success=False, content=None, tool_name="date_math",
                module=self.name, error="Operation is required (add, subtract, diff, day_of_week, business_days)",
            )

        try:
            if operation == "add":
                return self._date_add(params, negate=False)
            elif operation == "subtract":
                return self._date_add(params, negate=True)
            elif operation == "diff":
                return self._date_diff(params)
            elif operation == "day_of_week":
                return self._date_day_of_week(params)
            elif operation == "business_days":
                return self._date_business_days(params)
            else:
                return ToolResult(
                    success=False, content=None, tool_name="date_math",
                    module=self.name,
                    error=f"Unknown operation: {operation}. Use: add, subtract, diff, day_of_week, business_days",
                )
        except ValueError as e:
            return ToolResult(
                success=False, content=None, tool_name="date_math",
                module=self.name, error=f"Date error: {e}",
            )

    def _date_add(self, params: dict[str, Any], negate: bool) -> ToolResult:
        """Add or subtract time from a date."""
        date_str = params.get("date", "")
        if not date_str:
            return ToolResult(
                success=False, content=None, tool_name="date_math",
                module=self.name, error="'date' parameter is required (YYYY-MM-DD)",
            )

        d = _parse_date(date_str)
        sign = -1 if negate else 1

        days = params.get("days", 0) * sign
        weeks = params.get("weeks", 0) * sign
        months = params.get("months", 0) * sign
        years = params.get("years", 0) * sign

        # Apply months and years first (they affect which month/day we're in)
        result_date = _add_months(d, months + years * 12)
        # Then apply days and weeks
        result_date = result_date + timedelta(days=days, weeks=weeks)

        return ToolResult(
            success=True,
            content={
                "original_date": d.isoformat(),
                "result_date": result_date.isoformat(),
                "days_added": days + weeks * 7,
                "months_added": months,
                "years_added": years,
            },
            tool_name="date_math",
            module=self.name,
        )

    def _date_diff(self, params: dict[str, Any]) -> ToolResult:
        """Calculate difference between two dates."""
        date1_str = params.get("date1", "")
        date2_str = params.get("date2", "")
        if not date1_str or not date2_str:
            return ToolResult(
                success=False, content=None, tool_name="date_math",
                module=self.name, error="'date1' and 'date2' are required (YYYY-MM-DD)",
            )

        d1 = _parse_date(date1_str)
        d2 = _parse_date(date2_str)
        delta = d2 - d1
        total_days = delta.days

        return ToolResult(
            success=True,
            content={
                "date1": d1.isoformat(),
                "date2": d2.isoformat(),
                "total_days": total_days,
                "weeks": total_days // 7,
                "remaining_days": total_days % 7,
                "approximate_months": round(total_days / 30.44, 1),
                "approximate_years": round(total_days / 365.25, 2),
            },
            tool_name="date_math",
            module=self.name,
        )

    def _date_day_of_week(self, params: dict[str, Any]) -> ToolResult:
        """Get the day of the week for a date."""
        date_str = params.get("date", "")
        if not date_str:
            return ToolResult(
                success=False, content=None, tool_name="date_math",
                module=self.name, error="'date' parameter is required (YYYY-MM-DD)",
            )

        d = _parse_date(date_str)
        day_name = calendar.day_name[d.weekday()]

        return ToolResult(
            success=True,
            content={
                "date": d.isoformat(),
                "day_of_week": day_name,
                "weekday_number": d.weekday(),
                "is_weekend": d.weekday() >= 5,
            },
            tool_name="date_math",
            module=self.name,
        )

    def _date_business_days(self, params: dict[str, Any]) -> ToolResult:
        """Count business days between two dates."""
        date1_str = params.get("date1", "")
        date2_str = params.get("date2", "")
        if not date1_str or not date2_str:
            return ToolResult(
                success=False, content=None, tool_name="date_math",
                module=self.name, error="'date1' and 'date2' are required (YYYY-MM-DD)",
            )

        d1 = _parse_date(date1_str)
        d2 = _parse_date(date2_str)
        bdays = _count_business_days(d1, d2)

        return ToolResult(
            success=True,
            content={
                "date1": d1.isoformat(),
                "date2": d2.isoformat(),
                "business_days": bdays,
                "total_days": abs((d2 - d1).days) + 1,
                "weekend_days": abs((d2 - d1).days) + 1 - bdays,
            },
            tool_name="date_math",
            module=self.name,
        )

    def _percentage(self, params: dict[str, Any]) -> ToolResult:
        """Perform percentage calculations.

        Args:
            params: 'operation' (str), plus operation-specific params.
        """
        operation = params.get("operation", "")
        if not operation:
            return ToolResult(
                success=False, content=None, tool_name="percentage",
                module=self.name, error="Operation is required (of, what_percent, change, markup, margin)",
            )

        try:
            if operation == "of":
                percent = float(params.get("percent", 0))
                value = float(params.get("value", 0))
                result = (percent / 100) * value
                formula = f"{percent}% of {value} = ({percent}/100) × {value} = {result}"
                return ToolResult(
                    success=True,
                    content={"result": result, "formula": formula},
                    tool_name="percentage", module=self.name,
                )

            elif operation == "what_percent":
                value = float(params.get("value", 0))
                total = float(params.get("total", 0))
                if total == 0:
                    return ToolResult(
                        success=False, content=None, tool_name="percentage",
                        module=self.name, error="Total cannot be zero",
                    )
                result = (value / total) * 100
                formula = f"{value} is {result}% of {total} = ({value}/{total}) × 100"
                return ToolResult(
                    success=True,
                    content={"result": result, "formula": formula},
                    tool_name="percentage", module=self.name,
                )

            elif operation == "change":
                old_value = float(params.get("old_value", 0))
                new_value = float(params.get("new_value", 0))
                if old_value == 0:
                    return ToolResult(
                        success=False, content=None, tool_name="percentage",
                        module=self.name, error="Old value cannot be zero",
                    )
                result = ((new_value - old_value) / old_value) * 100
                direction = "increase" if result > 0 else "decrease" if result < 0 else "no change"
                formula = f"(({new_value} - {old_value}) / {old_value}) × 100 = {result}%"
                return ToolResult(
                    success=True,
                    content={"result": result, "direction": direction, "formula": formula},
                    tool_name="percentage", module=self.name,
                )

            elif operation == "markup":
                cost = float(params.get("cost", 0))
                selling_price = float(params.get("selling_price", 0))
                if cost == 0:
                    return ToolResult(
                        success=False, content=None, tool_name="percentage",
                        module=self.name, error="Cost cannot be zero",
                    )
                result = ((selling_price - cost) / cost) * 100
                formula = f"(({selling_price} - {cost}) / {cost}) × 100 = {result}%"
                return ToolResult(
                    success=True,
                    content={"result": result, "formula": formula},
                    tool_name="percentage", module=self.name,
                )

            elif operation == "margin":
                cost = float(params.get("cost", 0))
                selling_price = float(params.get("selling_price", 0))
                if selling_price == 0:
                    return ToolResult(
                        success=False, content=None, tool_name="percentage",
                        module=self.name, error="Selling price cannot be zero",
                    )
                result = ((selling_price - cost) / selling_price) * 100
                formula = f"(({selling_price} - {cost}) / {selling_price}) × 100 = {result}%"
                return ToolResult(
                    success=True,
                    content={"result": result, "formula": formula},
                    tool_name="percentage", module=self.name,
                )

            else:
                return ToolResult(
                    success=False, content=None, tool_name="percentage",
                    module=self.name,
                    error=f"Unknown operation: {operation}. Use: of, what_percent, change, markup, margin",
                )

        except (ValueError, TypeError) as e:
            return ToolResult(
                success=False, content=None, tool_name="percentage",
                module=self.name, error=f"Invalid input: {e}",
            )

    def _financial(self, params: dict[str, Any]) -> ToolResult:
        """Perform financial calculations.

        All results include a disclaimer — math only, not financial advice.

        Args:
            params: 'operation' (str), plus operation-specific params.
        """
        operation = params.get("operation", "")
        disclaimer = {"disclaimer": "Mathematical calculation only. Not financial advice."}

        if not operation:
            return ToolResult(
                success=False, content=None, tool_name="financial",
                module=self.name,
                error="Operation is required (compound_interest, pmt, roi, break_even, profit_loss)",
                metadata=disclaimer,
            )

        try:
            if operation == "compound_interest":
                principal = float(params.get("principal", 0))
                rate = float(params.get("rate", 0))
                n = int(params.get("compounds_per_year", 12))
                years = float(params.get("years", 0))

                if n <= 0:
                    return ToolResult(
                        success=False, content=None, tool_name="financial",
                        module=self.name, error="Compounds per year must be positive",
                        metadata=disclaimer,
                    )

                amount = principal * (1 + rate / n) ** (n * years)
                interest = amount - principal
                formula = f"A = {principal} × (1 + {rate}/{n})^({n} × {years}) = {amount:.2f}"

                return ToolResult(
                    success=True,
                    content={
                        "final_amount": round(amount, 2),
                        "interest_earned": round(interest, 2),
                        "principal": principal,
                        "formula": formula,
                    },
                    tool_name="financial", module=self.name,
                    metadata=disclaimer,
                )

            elif operation == "pmt":
                principal = float(params.get("principal", 0))
                annual_rate = float(params.get("annual_rate", 0))
                years = float(params.get("years", 0))

                if years <= 0:
                    return ToolResult(
                        success=False, content=None, tool_name="financial",
                        module=self.name, error="Years must be positive",
                        metadata=disclaimer,
                    )

                n = years * 12  # total payments

                if annual_rate == 0:
                    # No interest — simple division
                    monthly = principal / n
                    formula = f"PMT = {principal} / {n} = {monthly:.2f} (0% rate)"
                else:
                    r = annual_rate / 12  # monthly rate
                    monthly = principal * (r * (1 + r) ** n) / ((1 + r) ** n - 1)
                    formula = f"PMT = {principal} × [{r:.6f}(1+{r:.6f})^{n:.0f}] / [(1+{r:.6f})^{n:.0f} - 1] = {monthly:.2f}"

                total_paid = monthly * years * 12
                total_interest = total_paid - principal

                return ToolResult(
                    success=True,
                    content={
                        "monthly_payment": round(monthly, 2),
                        "total_paid": round(total_paid, 2),
                        "total_interest": round(total_interest, 2),
                        "formula": formula,
                    },
                    tool_name="financial", module=self.name,
                    metadata=disclaimer,
                )

            elif operation == "roi":
                gain = float(params.get("gain", 0))
                cost = float(params.get("cost", 0))

                if cost == 0:
                    return ToolResult(
                        success=False, content=None, tool_name="financial",
                        module=self.name, error="Cost cannot be zero",
                        metadata=disclaimer,
                    )

                roi = ((gain - cost) / cost) * 100
                formula = f"ROI = (({gain} - {cost}) / {cost}) × 100 = {roi:.2f}%"

                return ToolResult(
                    success=True,
                    content={"roi_percent": round(roi, 2), "formula": formula},
                    tool_name="financial", module=self.name,
                    metadata=disclaimer,
                )

            elif operation == "break_even":
                fixed_costs = float(params.get("fixed_costs", 0))
                price = float(params.get("price_per_unit", 0))
                variable = float(params.get("variable_cost_per_unit", 0))

                if price == variable:
                    return ToolResult(
                        success=False, content=None, tool_name="financial",
                        module=self.name,
                        error="Price per unit cannot equal variable cost per unit (division by zero)",
                        metadata=disclaimer,
                    )

                units = fixed_costs / (price - variable)
                revenue_at_break_even = units * price
                formula = f"Break-even = {fixed_costs} / ({price} - {variable}) = {units:.1f} units"

                return ToolResult(
                    success=True,
                    content={
                        "break_even_units": round(units, 2),
                        "revenue_at_break_even": round(revenue_at_break_even, 2),
                        "formula": formula,
                    },
                    tool_name="financial", module=self.name,
                    metadata=disclaimer,
                )

            elif operation == "profit_loss":
                revenue = float(params.get("revenue", 0))
                expenses = float(params.get("expenses", 0))
                result = revenue - expenses

                return ToolResult(
                    success=True,
                    content={
                        "profit_loss": round(result, 2),
                        "is_profit": result >= 0,
                        "revenue": revenue,
                        "expenses": expenses,
                        "formula": f"{revenue} - {expenses} = {result}",
                    },
                    tool_name="financial", module=self.name,
                    metadata=disclaimer,
                )

            else:
                return ToolResult(
                    success=False, content=None, tool_name="financial",
                    module=self.name,
                    error=f"Unknown operation: {operation}. Use: compound_interest, pmt, roi, break_even, profit_loss",
                    metadata=disclaimer,
                )

        except (ValueError, TypeError) as e:
            return ToolResult(
                success=False, content=None, tool_name="financial",
                module=self.name, error=f"Invalid input: {e}",
                metadata=disclaimer,
            )

    def _statistics(self, params: dict[str, Any]) -> ToolResult:
        """Run descriptive statistics on a list of numbers.

        Args:
            params: 'data' (list of numbers), 'operations' (list of stat names).
        """
        data = params.get("data", [])
        operations = params.get("operations", [
            "mean", "median", "stdev", "min", "max",
        ])

        if not data:
            return ToolResult(
                success=False, content=None, tool_name="statistics",
                module=self.name, error="Data list is required",
            )

        try:
            numbers = [float(x) for x in data]
        except (ValueError, TypeError) as e:
            return ToolResult(
                success=False, content=None, tool_name="statistics",
                module=self.name, error=f"All data items must be numbers: {e}",
            )

        results: dict[str, Any] = {"count": len(numbers)}

        stat_funcs: dict[str, Any] = {
            "mean": lambda d: statistics.mean(d),
            "median": lambda d: statistics.median(d),
            "mode": lambda d: statistics.mode(d),
            "stdev": lambda d: statistics.stdev(d) if len(d) > 1 else 0.0,
            "std_dev": lambda d: statistics.stdev(d) if len(d) > 1 else 0.0,
            "variance": lambda d: statistics.variance(d) if len(d) > 1 else 0.0,
            "min": lambda d: min(d),
            "max": lambda d: max(d),
            "range": lambda d: max(d) - min(d),
            "sum": lambda d: sum(d),
            "percentile_25": lambda d: statistics.quantiles(d, n=4)[0] if len(d) >= 2 else d[0],
            "percentile_50": lambda d: statistics.median(d),
            "percentile_75": lambda d: statistics.quantiles(d, n=4)[2] if len(d) >= 2 else d[0],
        }

        for op in operations:
            func = stat_funcs.get(op)
            if func is not None:
                try:
                    results[op] = func(numbers)
                except statistics.StatisticsError as e:
                    results[op] = f"Error: {e}"
            else:
                results[op] = f"Unknown operation: {op}"

        return ToolResult(
            success=True,
            content={"data_points": len(numbers), "results": results, "confidence": 1.0},
            tool_name="statistics",
            module=self.name,
        )

    def _logic_check(self, params: dict[str, Any]) -> ToolResult:
        """Check boolean logic or verify premises/conclusions.

        Two modes:
        - Truth table: provide 'variables' and 'expression'
        - Structural analysis: provide 'premises' and 'conclusion'

        Args:
            params: See get_tools() for parameter details.
        """
        variables = params.get("variables", [])
        expression = params.get("expression", "")

        # Truth table mode
        if variables and expression:
            return self._truth_table(variables, expression)

        # Structural analysis mode (backward compat)
        premises = params.get("premises", [])
        conclusion = params.get("conclusion", "")

        if not premises:
            return ToolResult(
                success=False, content=None, tool_name="logic_check",
                module=self.name, error="Provide either (variables + expression) for truth table, "
                                        "or (premises + conclusion) for structural analysis",
            )

        if not conclusion:
            return ToolResult(
                success=False, content=None, tool_name="logic_check",
                module=self.name, error="Conclusion is required",
            )

        # Phase 1: structural analysis only
        analysis = {
            "premises_count": len(premises),
            "conclusion_length": len(conclusion),
            "premises": premises,
            "conclusion": conclusion,
            "structural_valid": len(premises) > 0 and len(conclusion) > 0,
            "note": "Full logical verification requires LLM (Phase 2+). "
                    "Structural check only in Phase 1.",
            "confidence": 0.3,
        }

        return ToolResult(
            success=True,
            content=analysis,
            tool_name="logic_check",
            module=self.name,
        )

    def _truth_table(self, variables: list[str], expression: str) -> ToolResult:
        """Generate a truth table for a boolean expression.

        Args:
            variables: Variable names (2-3 max).
            expression: Boolean expression using and/or/not.
        """
        if len(variables) < 1 or len(variables) > 3:
            return ToolResult(
                success=False, content=None, tool_name="logic_check",
                module=self.name,
                error="Truth tables support 1-3 variables",
            )

        try:
            tree = ast.parse(expression.strip(), mode="eval")
        except SyntaxError as e:
            return ToolResult(
                success=False, content=None, tool_name="logic_check",
                module=self.name, error=f"Invalid boolean expression: {e}",
            )

        rows: list[dict[str, Any]] = []
        try:
            for combo in product([True, False], repeat=len(variables)):
                var_dict = dict(zip(variables, combo))
                result = _safe_bool_eval(tree, var_dict)
                row = {**var_dict, "result": result}
                rows.append(row)
        except ValueError as e:
            return ToolResult(
                success=False, content=None, tool_name="logic_check",
                module=self.name, error=f"Boolean evaluation error: {e}",
            )

        return ToolResult(
            success=True,
            content={
                "expression": expression,
                "variables": variables,
                "truth_table": rows,
                "total_rows": len(rows),
            },
            tool_name="logic_check",
            module=self.name,
        )
