# 问题身份归一化：将已知规则映射到标准 CWE，供评测匹配使用，避免把同一行的不同问题混为一谈。

"""Canonical finding identities shared by review and evaluation code."""

import re
from typing import Any, Dict, Iterable, List, Set, Tuple


# The evaluator compares canonical CWE identities, not reviewer-specific rule names.
RULE_TO_CWE = {
    "SEC-EVAL": "CWE-95",
    "SEC-SUBPROCESS-SHELL": "CWE-78",
    "SEC-HARDCODED-SECRET": "CWE-798",
    "SEC-SQL-CONCAT": "CWE-89",
    "REL-EMPTY-EXCEPT": "CWE-703",
    "REL-DEBUG-PRINT": "CWE-532",
    "SEC-PATH-TRAVERSAL": "CWE-22",
    "SEC-YAML-LOAD": "CWE-502",
    "SEC-WEAK-HASH": "CWE-328",
    "SEC-INSECURE-TEMPFILE": "CWE-377",
    "SEC-WEAK-RANDOM": "CWE-330",
    "REL-UNBOUNDED-RETRY": "CWE-835",
    "SEC-ASSERT-AUTH": "CWE-617",
    "SEC-INSECURE-COOKIE": "CWE-614",
    "SEC-PICKLE-LOAD": "CWE-502",
    "REL-FLOAT-MONEY": "CWE-682",
    "REL-NAIVE-DATETIME": "CWE-367",
    "REL-BLOCKING-ASYNC": "CWE-400",
    "REL-NONATOMIC-WRITE": "CWE-362",
    "COR-ZERO-DIVISOR-GUARD": "CWE-369",
    "SEC-OPEN-REDIRECT": "CWE-601",
    "SEC-LOG-FORGING": "CWE-117",
}

# Worker 可选择的稳定问题分类。CWE 仅用于确有标准弱点映射的规则；
# 正确性、兼容性和测试类问题不强行套用 CWE。
_RULE_DESCRIPTIONS = {
    "SEC-EVAL": "Dynamic code execution through eval or exec.",
    "SEC-SUBPROCESS-SHELL": "Command execution through a shell.",
    "SEC-HARDCODED-SECRET": "Credential or secret committed in source.",
    "SEC-SQL-CONCAT": "SQL built by string interpolation or concatenation.",
    "SEC-PATH-TRAVERSAL": "Untrusted path can escape the intended root.",
    "SEC-YAML-LOAD": "Unsafe deserialization through a permissive YAML loader.",
    "SEC-WEAK-HASH": "Security-sensitive use of a weak digest.",
    "SEC-INSECURE-TEMPFILE": "Predictable or unsafe temporary-file handling.",
    "SEC-WEAK-RANDOM": "Security-sensitive use of non-cryptographic randomness.",
    "SEC-ASSERT-AUTH": "Authorization or authentication enforced only by assert.",
    "SEC-INSECURE-COOKIE": "Sensitive cookie lacks required transport protection.",
    "SEC-PICKLE-LOAD": "Unsafe deserialization through pickle.",
    "SEC-OPEN-REDIRECT": "Untrusted redirect target.",
    "SEC-LOG-FORGING": "Untrusted data can forge or corrupt log records.",
    "SEC-AUTHORIZATION": "Missing or incorrect authorization boundary.",
    "SEC-INPUT-VALIDATION": "Security-relevant input is insufficiently validated.",
    "SEC-INJECTION": "Untrusted data reaches an interpreter or command sink.",
    "SEC-SENSITIVE-DATA": "Sensitive data can be exposed or retained unsafely.",
    "SEC-UNSAFE-DESERIALIZATION": "Untrusted serialized data can instantiate unsafe values.",
    "REL-EMPTY-EXCEPT": "Failure is swallowed or converted into false success.",
    "REL-DEBUG-PRINT": "Debug output can leak data or pollute service logs.",
    "REL-UNBOUNDED-RETRY": "Retry or polling loop has no effective bound.",
    "REL-FLOAT-MONEY": "Binary floating point is used for monetary state.",
    "REL-NAIVE-DATETIME": "Timezone-naive time is used in a distributed boundary.",
    "REL-BLOCKING-ASYNC": "Blocking operation runs on an asynchronous execution path.",
    "REL-NONATOMIC-WRITE": "Durable state update is not atomic.",
    "COR-STATE-TRANSITION": "Change introduces an invalid state transition.",
    "COR-BOUNDARY-CONDITION": "Boundary or empty-input behavior is incorrect.",
    "COR-ZERO-DIVISOR-GUARD": "A removed zero-divisor guard exposes an unchanged division.",
    "COR-REMOVED-INPUT-RANGE-GUARD": "A removed range check allows previously rejected input through.",
    "COR-REMOVED-ZERO-FLOOR": "A removed zero floor allows an unchanged expression to return a negative value.",
    "COR-DATA-INTEGRITY": "Change can corrupt, drop, or partially persist data.",
    "COR-INVARIANT": "A required program or business invariant can be violated.",
    "API-COMPATIBILITY": "Externally observable API or schema compatibility break.",
    "REL-ERROR-HANDLING": "Error handling loses failure state or required context.",
    "REL-CONCURRENCY": "Concurrency ordering or synchronization is unsafe.",
    "REL-RESOURCE-LIFETIME": "Resource is leaked, reused, or released at the wrong time.",
    "REL-IDEMPOTENCY": "Retry or duplicate delivery can repeat a side effect.",
    "REL-TIMEOUT-RETRY": "Timeout or retry policy can amplify or hide failure.",
    "REL-OBSERVABILITY": "Material failure lacks an actionable operational signal.",
    "REL-PERFORMANCE": "Change introduces material unbounded or repeated work.",
    "DB-DATA-INTEGRITY": "Database change can violate durable data integrity.",
    "DB-TRANSACTION": "Transaction boundary permits partial or inconsistent state.",
    "DB-UNBOUNDED-QUERY": "Query can return or process an unbounded result set.",
    "TEST-COVERAGE": "Changed behavior lacks a meaningful regression or failure-path test.",
    "QUALITY-UNFINISHED": "Production behavior contains an unfinished TODO or placeholder.",
}

_SECURITY_RULES = {name for name in _RULE_DESCRIPTIONS if name.startswith("SEC-")}
_SHARED_RULES = {"DB-DATA-INTEGRITY", "DB-TRANSACTION"}
_SCANNER_ONLY_RULES = {"COR-REMOVED-INPUT-RANGE-GUARD", "COR-REMOVED-ZERO-FLOOR"}

RULE_CATALOG: Dict[str, Dict[str, Any]] = {
    name: {
        "rule_id": name,
        "cwe": RULE_TO_CWE.get(name),
        "description": description,
        "workers": (
            () if name in _SCANNER_ONLY_RULES else
            ("security", "correctness-reliability")
            if name in _SHARED_RULES else
            ("security",) if name in _SECURITY_RULES else
            ("correctness-reliability",)
        ),
    }
    for name, description in _RULE_DESCRIPTIONS.items()
}

_CWE_RE = re.compile(r"^CWE-[0-9]+$", re.IGNORECASE)
_RULE_ID_RE = re.compile(r"^[A-Z][A-Z0-9_-]{1,79}$")
_DECLARED_RULE_RE = re.compile(
    r"\b(?:SEC|REL|COR|DB|API|PERF|OBS|TEST|QUALITY|CODE)-[A-Z0-9][A-Z0-9_-]{1,79}\b"
)


# 将 CWE 或已知规则标识转换为统一的 CWE 编号。
def canonical_cwe(rule_id: Any = "", cwe: Any = "") -> str:
    """Return a canonical CWE, preferring the trusted rule mapping."""
    rule = str(rule_id or "").strip().upper()
    mapped = RULE_TO_CWE.get(rule, "")
    if mapped:
        return mapped.upper()
    explicit = str(cwe or "").strip().upper()
    return explicit if _CWE_RE.fullmatch(explicit) else ""


# 检查标识是否满足支持的 CWE 格式。
def is_valid_cwe(value: Any) -> bool:
    """Validate the transport format for an explicit CWE value."""
    return bool(_CWE_RE.fullmatch(str(value or "").strip()))


def worker_rule_catalog(worker: str) -> List[dict]:
    """Return the compact, role-scoped taxonomy exposed to one Worker."""
    return [
        {
            "rule_id": item["rule_id"], "cwe": item["cwe"],
            "description": item["description"],
        }
        for item in RULE_CATALOG.values()
        if worker in item["workers"]
    ]


def extract_declared_rule_ids(texts: Iterable[str]) -> Set[str]:
    """Extract project-specific rule IDs explicitly declared by active Skills."""
    values: Set[str] = set()
    for text in texts:
        values.update(_DECLARED_RULE_RE.findall(str(text or "").upper()))
    return {value for value in values if _RULE_ID_RE.fullmatch(value)}


def normalize_worker_identity(
    rule_id: Any, cwe: Any, worker: str, allowed_custom_rules: Iterable[str] = (),
) -> Tuple[str, str, bool]:
    """Normalize model taxonomy output and reject undeclared invented identities.

    Known catalog rules use their program-owned CWE mapping. Project-specific rules
    are accepted only when an active Skill declares them, and do not inherit a
    model-supplied CWE. Everything else is downgraded to a role-specific
    UNCLASSIFIED identity.
    """
    candidate = str(rule_id or "").strip().upper()
    catalog = RULE_CATALOG.get(candidate)
    if catalog and worker in catalog["workers"]:
        return candidate, str(catalog.get("cwe") or ""), True
    allowed = {str(value).strip().upper() for value in allowed_custom_rules}
    if candidate in allowed and _RULE_ID_RE.fullmatch(candidate):
        return candidate, "", True
    fallback = (
        "UNCLASSIFIED-SECURITY"
        if worker == "security" else "UNCLASSIFIED-CORRECTNESS"
    )
    return fallback, "", False


# 优先使用明确的 CWE，其次映射已知规则，生成问题匹配身份。
def canonical_identity(rule_id: Any = "", cwe: Any = "") -> str:
    """Return the scoring identity, with a legacy rule fallback.

    Known rules and explicit CWE values are scored by CWE. Unknown legacy rule
    IDs remain matchable only against the exact same legacy ID; an arbitrary
    model-generated ID cannot match a CWE-labelled truth.
    """
    value = canonical_cwe(rule_id, cwe)
    if value:
        return value
    rule = str(rule_id or "").strip().upper()
    return "RULE:" + rule if rule else ""
