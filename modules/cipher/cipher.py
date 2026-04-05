"""
Cipher — Math, Logic, and Complex Reasoning
=============================================
Precision over speed. When the answer has to be right, not just fast.

Design Principle: Cipher takes whatever time is needed to get the
answer right. Verify before delivering. Flag uncertainty.

Phase 1: Safe expression evaluation, statistics, unit conversion,
financial calculations. No LLM — pure computation.
"""

import ast
import logging
import math
import operator
import statistics
import time
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

# Unit conversion tables
_CONVERSIONS: dict[str, dict[str, float]] = {
    "length": {
        "m": 1.0, "km": 1000.0, "cm": 0.01, "mm": 0.001,
        "in": 0.0254, "ft": 0.3048, "yd": 0.9144, "mi": 1609.344,
    },
    "weight": {
        "kg": 1.0, "g": 0.001, "mg": 0.000001,
        "lb": 0.453592, "oz": 0.0283495, "ton": 907.185,
    },
    "volume": {
        "l": 1.0, "ml": 0.001, "gal": 3.78541, "qt": 0.946353,
        "pt": 0.473176, "cup": 0.236588, "floz": 0.0295735,
    },
    "digital": {
        "b": 1.0, "kb": 1024.0, "mb": 1048576.0,
        "gb": 1073741824.0, "tb": 1099511627776.0,
    },
    "time": {
        "s": 1.0, "ms": 0.001, "min": 60.0, "hr": 3600.0,
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


class Cipher(BaseModule):
    """Math, logic, and complex reasoning specialist.

    Handles calculations, statistics, unit conversion, and financial
    analysis with precision. No LLM needed — pure computation.
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
                "logic_verify": self._logic_verify,
                "data_analyze": self._data_analyze,
                "unit_convert": self._unit_convert,
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
                "description": "Run mathematical computation with full precision",
                "parameters": {"expression": "str"},
                "permission_level": "autonomous",
            },
            {
                "name": "logic_verify",
                "description": "Check logical consistency of a reasoning chain",
                "parameters": {"premises": "list", "conclusion": "str"},
                "permission_level": "autonomous",
            },
            {
                "name": "data_analyze",
                "description": "Statistical analysis on structured data",
                "parameters": {"data": "list", "operations": "list"},
                "permission_level": "autonomous",
            },
            {
                "name": "unit_convert",
                "description": "Convert between units",
                "parameters": {"value": "float", "from_unit": "str", "to_unit": "str"},
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

            return ToolResult(
                success=True,
                content={
                    "expression": expression,
                    "result": result,
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

    def _logic_verify(self, params: dict[str, Any]) -> ToolResult:
        """Verify logical consistency of premises and a conclusion.

        Phase 1: Basic structural checks. Phase 2+: LLM reasoning.

        Args:
            params: 'premises' (list of str), 'conclusion' (str).
        """
        premises = params.get("premises", [])
        conclusion = params.get("conclusion", "")

        if not premises:
            return ToolResult(
                success=False, content=None, tool_name="logic_verify",
                module=self.name, error="At least one premise is required",
            )

        if not conclusion:
            return ToolResult(
                success=False, content=None, tool_name="logic_verify",
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
            "confidence": 0.3,  # Low confidence for structural-only check
        }

        return ToolResult(
            success=True,
            content=analysis,
            tool_name="logic_verify",
            module=self.name,
        )

    def _data_analyze(self, params: dict[str, Any]) -> ToolResult:
        """Run statistical analysis on a list of numbers.

        Args:
            params: 'data' (list of numbers), 'operations' (list of stat names).
        """
        data = params.get("data", [])
        operations = params.get("operations", [
            "mean", "median", "stdev", "min", "max",
        ])

        if not data:
            return ToolResult(
                success=False, content=None, tool_name="data_analyze",
                module=self.name, error="Data list is required",
            )

        # Validate all items are numbers
        try:
            numbers = [float(x) for x in data]
        except (ValueError, TypeError) as e:
            return ToolResult(
                success=False, content=None, tool_name="data_analyze",
                module=self.name, error=f"All data items must be numbers: {e}",
            )

        results: dict[str, Any] = {"count": len(numbers)}

        stat_funcs: dict[str, Any] = {
            "mean": lambda d: statistics.mean(d),
            "median": lambda d: statistics.median(d),
            "mode": lambda d: statistics.mode(d),
            "stdev": lambda d: statistics.stdev(d) if len(d) > 1 else 0.0,
            "variance": lambda d: statistics.variance(d) if len(d) > 1 else 0.0,
            "min": lambda d: min(d),
            "max": lambda d: max(d),
            "range": lambda d: max(d) - min(d),
            "sum": lambda d: sum(d),
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
            tool_name="data_analyze",
            module=self.name,
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
            return ToolResult(
                success=True,
                content={
                    "value": value, "from": from_unit, "to": to_unit,
                    "result": result, "confidence": 1.0,
                },
                tool_name="unit_convert",
                module=self.name,
            )

        # Find category
        for category, units in _CONVERSIONS.items():
            if from_unit in units and to_unit in units:
                # Convert via base unit
                base_value = value * units[from_unit]
                result = base_value / units[to_unit]
                return ToolResult(
                    success=True,
                    content={
                        "value": value, "from": from_unit, "to": to_unit,
                        "result": result, "category": category, "confidence": 1.0,
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
        # Convert to Celsius first
        if from_u == "f":
            celsius = (value - 32) * 5 / 9
        elif from_u == "k":
            celsius = value - 273.15
        else:
            celsius = value

        # Convert from Celsius to target
        if to_u == "f":
            return celsius * 9 / 5 + 32
        elif to_u == "k":
            return celsius + 273.15
        return celsius
