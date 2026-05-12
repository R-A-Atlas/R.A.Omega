"""UI porter helper."""

from __future__ import annotations


def component_port_plan(component: str, source: str, target: str) -> dict[str, str]:
    return {"component": component, "source": source, "target": target, "status": "planned"}
