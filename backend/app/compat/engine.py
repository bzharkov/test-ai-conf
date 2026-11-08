from __future__ import annotations

from typing import Any

from app.compat.rules import RULES
from app.domain import Build, Issue

RULE_TITLES = {code: title for code, title, _ in RULES}
RULE_TITLES["MISSING_DATA"] = "Полнота данных о комплектующих"
_FULL_ONLY = {"NO_VIDEO"}


def check_build(build: Build, partial: bool = False) -> list[Issue]:
    """Run all rules. With partial=True rules that need a finished build are skipped."""
    issues: list[Issue] = []
    for code, _, fn in RULES:
        if partial and code in _FULL_ONLY:
            continue
        issues.extend(fn(build))
    return issues


def has_errors(issues: list[Issue]) -> bool:
    return any(i.severity == "error" for i in issues)


def rule_report(build: Build, issues: list[Issue] | None = None) -> list[dict[str, Any]]:
    """Per-rule status list for the UI: ok / warning / error."""
    issues = check_build(build) if issues is None else issues
    report = []
    for code, title in RULE_TITLES.items():
        mine = [i for i in issues if i.code == code]
        if code == "MISSING_DATA" and not mine:
            status = "ok"
        elif any(i.severity == "error" for i in mine):
            status = "error"
        elif mine:
            status = "warning"
        else:
            status = "ok"
        report.append(
            {
                "code": code,
                "title": title,
                "status": status,
                "messages": [i.message_ru for i in mine],
            }
        )
    return report
