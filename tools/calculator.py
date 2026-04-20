"""Safe calculator tool for arithmetic expressions."""

from __future__ import annotations

import ast
import math
from typing import Any, Dict


class CalculatorTool:
    """Evaluate arithmetic expressions without using eval."""

    @staticmethod
    def schema() -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "expression": {"type": "string"},
                "precision": {"type": "integer", "minimum": 0, "maximum": 12},
            },
            "required": ["expression"],
            "additionalProperties": False,
        }

    async def run(self, args: Dict[str, Any]) -> Dict[str, Any]:
        expression = str(args.get("expression", "")).strip()
        if not expression:
            raise ValueError("Calculator 'expression' is required.")

        precision = args.get("precision")
        if precision is not None:
            precision = int(precision)
            if precision < 0 or precision > 12:
                raise ValueError("'precision' must be between 0 and 12.")

        value = _SafeCalculator().evaluate(expression)
        if precision is not None and isinstance(value, float):
            value = round(value, precision)

        return {
            "expression": expression,
            "result": value,
        }


class _SafeCalculator(ast.NodeVisitor):
    allowed_binops = {
        ast.Add: lambda left, right: left + right,
        ast.Sub: lambda left, right: left - right,
        ast.Mult: lambda left, right: left * right,
        ast.Div: lambda left, right: left / right,
        ast.FloorDiv: lambda left, right: left // right,
        ast.Mod: lambda left, right: left % right,
        ast.Pow: lambda left, right: left ** right,
    }
    allowed_unary = {
        ast.UAdd: lambda value: +value,
        ast.USub: lambda value: -value,
    }
    allowed_funcs = {
        "abs": abs,
        "round": round,
        "min": min,
        "max": max,
        "sum": sum,
        "sqrt": math.sqrt,
        "ceil": math.ceil,
        "floor": math.floor,
    }

    def evaluate(self, expression: str) -> float | int:
        parsed = ast.parse(expression, mode="eval")
        return self.visit(parsed.body)

    def visit_Constant(self, node: ast.Constant):
        if isinstance(node.value, (int, float)):
            return node.value
        raise ValueError("Only numeric constants are allowed in calculator expressions.")

    def visit_Num(self, node: ast.Num):  # pragma: no cover - compatibility path
        return node.n

    def visit_BinOp(self, node: ast.BinOp):
        operator_type = type(node.op)
        if operator_type not in self.allowed_binops:
            raise ValueError(f"Operator '{operator_type.__name__}' is not supported.")
        left = self.visit(node.left)
        right = self.visit(node.right)
        return self.allowed_binops[operator_type](left, right)

    def visit_UnaryOp(self, node: ast.UnaryOp):
        operator_type = type(node.op)
        if operator_type not in self.allowed_unary:
            raise ValueError(f"Unary operator '{operator_type.__name__}' is not supported.")
        return self.allowed_unary[operator_type](self.visit(node.operand))

    def visit_Call(self, node: ast.Call):
        if not isinstance(node.func, ast.Name):
            raise ValueError("Only direct function calls are allowed.")
        function_name = node.func.id
        if function_name not in self.allowed_funcs:
            raise ValueError(f"Function '{function_name}' is not supported.")

        arguments = [self.visit(arg) for arg in node.args]
        if node.keywords:
            raise ValueError("Keyword arguments are not supported in calculator expressions.")

        return self.allowed_funcs[function_name](*arguments)

    def visit_List(self, node: ast.List):
        return [self.visit(element) for element in node.elts]

    def visit_Tuple(self, node: ast.Tuple):
        return tuple(self.visit(element) for element in node.elts)

    def visit_Expression(self, node: ast.Expression):  # pragma: no cover - defensive path
        return self.visit(node.body)

    def generic_visit(self, node):
        raise ValueError(f"Unsupported expression element: {type(node).__name__}")