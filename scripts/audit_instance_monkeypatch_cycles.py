from __future__ import annotations

import argparse
import ast
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Candidate:
    path: Path
    line: int
    owner: str
    target: str
    kind: str
    detail: str


def _expr_text(node: ast.AST) -> str:
    try:
        return ast.unparse(node)
    except Exception:  # noqa: BLE001 - diagnostic only
        return node.__class__.__name__


def _root_name(node: ast.AST) -> str | None:
    current = node
    while isinstance(current, ast.Attribute):
        current = current.value
    return current.id if isinstance(current, ast.Name) else None


def _assigned_names(function: ast.FunctionDef | ast.AsyncFunctionDef) -> set[str]:
    names = {
        argument.arg
        for argument in (
            *function.args.posonlyargs,
            *function.args.args,
            *function.args.kwonlyargs,
        )
    }
    if function.args.vararg is not None:
        names.add(function.args.vararg.arg)
    if function.args.kwarg is not None:
        names.add(function.args.kwarg.arg)

    class Visitor(ast.NodeVisitor):
        def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
            if node is function:
                for statement in node.body:
                    self.visit(statement)

        def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
            if node is function:
                for statement in node.body:
                    self.visit(statement)

        def visit_Lambda(self, node: ast.Lambda) -> None:
            return

        def visit_Name(self, node: ast.Name) -> None:
            if isinstance(node.ctx, (ast.Store, ast.Del)):
                names.add(node.id)

    Visitor().visit(function)
    return names


def _closure_loads(function: ast.FunctionDef | ast.AsyncFunctionDef) -> set[str]:
    local = _assigned_names(function)
    loaded: set[str] = set()

    class Visitor(ast.NodeVisitor):
        def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
            if node is function:
                for statement in node.body:
                    self.visit(statement)

        def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
            if node is function:
                for statement in node.body:
                    self.visit(statement)

        def visit_Lambda(self, node: ast.Lambda) -> None:
            return

        def visit_Name(self, node: ast.Name) -> None:
            if isinstance(node.ctx, ast.Load) and node.id not in local:
                loaded.add(node.id)

    Visitor().visit(function)
    return loaded


def _direct_nested_functions(
    function: ast.FunctionDef | ast.AsyncFunctionDef,
) -> dict[str, ast.FunctionDef | ast.AsyncFunctionDef]:
    nested: dict[str, ast.FunctionDef | ast.AsyncFunctionDef] = {}

    class Visitor(ast.NodeVisitor):
        def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
            if node is function:
                for statement in node.body:
                    self.visit(statement)
                return
            nested[node.name] = node

        def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
            if node is function:
                for statement in node.body:
                    self.visit(statement)
                return
            nested[node.name] = node

        def visit_Lambda(self, node: ast.Lambda) -> None:
            return

    Visitor().visit(function)
    return nested


def _target_attributes(statement: ast.Assign | ast.AnnAssign) -> list[ast.Attribute]:
    targets: list[ast.expr]
    if isinstance(statement, ast.Assign):
        targets = list(statement.targets)
    else:
        targets = [statement.target]
    return [target for target in targets if isinstance(target, ast.Attribute)]


def _value(statement: ast.Assign | ast.AnnAssign) -> ast.expr | None:
    return statement.value


def _is_method_type_call(node: ast.AST) -> bool:
    if not isinstance(node, ast.Call):
        return False
    func = node.func
    return (isinstance(func, ast.Name) and func.id == "MethodType") or (
        isinstance(func, ast.Attribute) and func.attr == "MethodType"
    )


def _owner_name(stack: list[ast.AST]) -> str:
    names = [
        node.name
        for node in stack
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
    ]
    return ".".join(names) if names else "<module>"


def audit_file(path: Path) -> list[Candidate]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    candidates: list[Candidate] = []
    stack: list[ast.AST] = []
    nested_scopes: list[dict[str, ast.FunctionDef | ast.AsyncFunctionDef]] = []

    class Visitor(ast.NodeVisitor):
        def visit_ClassDef(self, node: ast.ClassDef) -> None:
            stack.append(node)
            self.generic_visit(node)
            stack.pop()

        def _visit_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
            stack.append(node)
            nested_scopes.append(_direct_nested_functions(node))
            for statement in node.body:
                self.visit(statement)
            nested_scopes.pop()
            stack.pop()

        def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
            self._visit_function(node)

        def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
            self._visit_function(node)

        def visit_Assign(self, node: ast.Assign) -> None:
            self._inspect_assignment(node)
            self.generic_visit(node)

        def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
            self._inspect_assignment(node)
            self.generic_visit(node)

        def _nested_function(
            self,
            name: str,
        ) -> ast.FunctionDef | ast.AsyncFunctionDef | None:
            for scope in reversed(nested_scopes):
                candidate = scope.get(name)
                if candidate is not None:
                    return candidate
            return None

        def _inspect_assignment(self, statement: ast.Assign | ast.AnnAssign) -> None:
            value = _value(statement)
            if value is None:
                return
            owner = _owner_name(stack)
            for target in _target_attributes(statement):
                target_text = _expr_text(target)
                target_root = _root_name(target) or "?"
                if _is_method_type_call(value):
                    candidates.append(
                        Candidate(
                            path,
                            statement.lineno,
                            owner,
                            target_text,
                            "MethodType",
                            _expr_text(value),
                        )
                    )
                    continue

                if isinstance(value, ast.Name):
                    nested = self._nested_function(value.id)
                    if nested is not None:
                        loads = sorted(_closure_loads(nested))
                        candidates.append(
                            Candidate(
                                path,
                                statement.lineno,
                                owner,
                                target_text,
                                "nested-closure",
                                f"closure={value.id}; free_loads={','.join(loads)}",
                            )
                        )
                        continue

                value_root = _root_name(value)
                if isinstance(value, ast.Attribute) and value_root in {
                    "self",
                    "controller",
                    "lifecycle",
                    "review",
                    "guard",
                }:
                    candidates.append(
                        Candidate(
                            path,
                            statement.lineno,
                            owner,
                            target_text,
                            "bound-method",
                            f"target_root={target_root}; value={_expr_text(value)}",
                        )
                    )

    Visitor().visit(tree)
    return candidates


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Inventory instance monkey-patches that can participate in Python "
            "reference cycles."
        )
    )
    parser.add_argument("root", nargs="?", default="src/pixelscope")
    args = parser.parse_args()
    root = Path(args.root)
    candidates: list[Candidate] = []
    for path in sorted(root.rglob("*.py")):
        candidates.extend(audit_file(path))

    print("INSTANCE_MONKEYPATCH_CYCLE_AUDIT")
    print(f"ROOT={root}")
    print(f"CANDIDATES={len(candidates)}")
    for item in candidates:
        print(
            f"{item.path}:{item.line}: {item.kind}: {item.target} "
            f"[{item.owner}] {item.detail}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
