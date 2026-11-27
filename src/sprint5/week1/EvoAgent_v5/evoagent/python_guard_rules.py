"""Verify simple Python range checks and zero floors removed by a diff."""

import ast
import hashlib
import textwrap

from .models import Finding, Severity


INPUT_RANGE_GUARD_RULE = "COR-REMOVED-INPUT-RANGE-GUARD"
ZERO_FLOOR_RULE = "COR-REMOVED-ZERO-FLOOR"


def scan_removed_guards(hunk):
    deleted = [row for row in hunk if row.side == "-"]
    if not any("raise ValueError" in row.text or "max" in row.text for row in deleted):
        return []
    old_rows = [row for row in hunk if row.side != "+"]
    new_rows = [row for row in hunk if row.side != "-"]
    try:
        old_functions = _functions(old_rows)
        new_functions = _functions(new_rows)
    except (SyntaxError, ValueError, RecursionError):
        return []
    findings = []
    for before, after in zip(old_functions, new_functions):
        if before.name == after.name and _same(before.args, after.args):
            findings.extend(_compare_returns(before, after, old_rows, new_rows))
    return findings


def _functions(rows):
    tree = ast.parse(textwrap.dedent("\n".join(row.text for row in rows)))
    return [node for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))]


def _same(left, right):
    return ast.dump(left) == ast.dump(right)


def _numeric_constant(node):
    return isinstance(node, ast.Constant) and type(node.value) in (int, float)


def _compare_returns(before, after, old_rows, new_rows):
    old_return, new_return = before.body[-1], after.body[-1]
    if not isinstance(old_return, ast.Return) or not isinstance(new_return, ast.Return):
        return []
    wrapped = old_return.value
    removed_floor = (
        isinstance(wrapped, ast.Call) and isinstance(wrapped.func, ast.Name) and wrapped.func.id == "max"
        and len(wrapped.args) == 2 and not wrapped.keywords and _numeric_constant(wrapped.args[0])
        and wrapped.args[0].value == 0 and new_return.value is not None
        and _same(wrapped.args[1], new_return.value)
    )
    if not removed_floor and not _same(old_return, new_return):
        return []

    old_body = before.body[:-1]
    new_body = after.body[:-1]
    guard = None
    bounds = None
    if len(old_body) == len(new_body) + 1:
        index = next((i for i, (old, new) in enumerate(zip(old_body, new_body)) if not _same(old, new)), len(new_body))
        guard = old_body[index]
        bounds = _range_guard(guard, before.args)
        if bounds is None:
            return []
        old_body = old_body[:index] + old_body[index + 1:]
    if len(old_body) != len(new_body) or any(not _same(old, new) for old, new in zip(old_body, new_body)):
        return []
    if bounds is None and not removed_floor:
        return []

    related = [
        {"path": row.old_path if side == "old" else row.path, "line": row.line, "line_side": side}
        for side, marker, node, rows in (("old", "-", before, old_rows), ("new", "+", after, new_rows))
        for row in rows[node.lineno - 1:node.end_lineno] if row.side == marker
    ]
    findings = []
    if bounds is not None:
        parameter, lower, upper = bounds
        old_guard = old_rows[guard.lineno - 1]
        if old_guard.side == "-" and old_rows[guard.body[0].lineno - 1].side == "-":
            findings.append(_finding(
                INPUT_RANGE_GUARD_RULE, old_guard, "old", old_guard, related,
                f"Removed range validation for {parameter}",
                f"{before.name} previously raised ValueError when {parameter} was outside "
                f"[{lower}, {upper}]. Those inputs now reach the calculation.",
                "Restore the input range check or enforce the same contract at this entry point.",
                f"Assert that values just below {lower} and above {upper} raise ValueError.",
            ))
    if removed_floor:
        old_line = old_rows[old_return.lineno - 1]
        new_line = new_rows[new_return.lineno - 1]
        if old_line.side == "-" and new_line.side == "+":
            findings.append(_finding(
                ZERO_FLOOR_RULE, new_line, "new", old_line, related,
                "Removed zero floor allows negative results",
                f"{before.name} used to clamp the return value at zero. With the same expression "
                "returned directly, a negative result now passes through.",
                "Restore the zero floor around the returned expression.",
                "Exercise a negative intermediate result and assert that the return value is zero.",
            ))
    return findings


def _range_guard(node, args):
    if not isinstance(node, ast.If) or node.orelse or len(node.body) != 1:
        return None
    statement = node.body[0]
    if not isinstance(statement, ast.Raise) or not isinstance(statement.exc, ast.Call):
        return None
    exc = statement.exc.func
    if not isinstance(exc, ast.Name) or exc.id != "ValueError":
        return None
    test = node.test
    if not isinstance(test, ast.BoolOp) or not isinstance(test.op, ast.Or) or len(test.values) != 2:
        return None
    parameters = {arg.arg for arg in [*args.posonlyargs, *args.args, *args.kwonlyargs]}
    lower, upper = test.values
    if isinstance(lower, ast.Compare) and isinstance(lower.ops[0], ast.Gt):
        lower, upper = upper, lower
    if not (_bound(lower, ast.Lt, parameters) and _bound(upper, ast.Gt, parameters)):
        return None
    minimum, maximum = lower.comparators[0].value, upper.comparators[0].value
    if lower.left.id != upper.left.id or minimum >= maximum:
        return None
    return lower.left.id, minimum, maximum


def _bound(node, operator, parameters):
    return (isinstance(node, ast.Compare) and len(node.ops) == 1 and isinstance(node.ops[0], operator)
            and isinstance(node.left, ast.Name) and node.left.id in parameters
            and _numeric_constant(node.comparators[0]))


def _finding(rule, anchor, side, previous, related, title, explanation, fix, test):
    path = anchor.old_path if side == "old" else anchor.path
    payload = repr((rule, path, side, anchor.line, anchor.text, previous.text)).encode("utf-8")
    evidence_id = hashlib.sha256(payload).hexdigest()[:16]
    return Finding(rule, Severity.MEDIUM, title, explanation, path, anchor.line,
                   anchor.text.strip()[:240], fix, test, confidence=0.90, line_side=side,
                   evidence_refs=[{
                       "evidence_id": f"local-rule:{evidence_id}", "tool": "local-rule-scanner",
                       "rule_id": rule, "path": path, "line": anchor.line,
                       "old_path": previous.old_path, "old_line": previous.line,
                       "old_code": previous.text.strip()[:240], "related_locations": related,
                   }], source="local-rule-scanner")
