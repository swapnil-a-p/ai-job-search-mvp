from __future__ import annotations

from datetime import datetime

from message_generator import generate_connection_note


def attach_employee_message_drafts(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    now = datetime.now().date().isoformat()
    enriched: list[dict[str, str]] = []
    for row in rows:
        updated = dict(row)
        updated["Message Draft"] = generate_connection_note(
            company=row.get("Company", ""),
            role=row.get("Role") or "target role",
            person_name=row.get("Person Name") or None,
            target_type=row.get("Target Type"),
        )
        updated["Last Updated"] = now
        enriched.append(updated)
    return enriched
