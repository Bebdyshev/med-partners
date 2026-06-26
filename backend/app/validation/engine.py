"""Run the validation rule pipeline over a ValItem."""
from __future__ import annotations

from app.validation.rules import ALL_RULES, ValItem, ValReport


def validate(item: ValItem) -> ValReport:
    report = ValReport()
    for rule in ALL_RULES:
        for warning in rule(item):
            report.warnings.append(warning)
    return report
