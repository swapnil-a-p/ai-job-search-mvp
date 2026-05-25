from __future__ import annotations


GENERIC_PROFILE = (
    "I’m currently an AWS Solutions Architect focused on cloud architecture, "
    "GenAI, and customer-facing technical work."
)


def generate_connection_note(
    company: str, role: str, person_name: str | None = None, target_type: str | None = None
) -> str:
    greeting = f"Hi {person_name}," if person_name else "Hi,"

    if target_type in {"Recruiter", "Talent Acquisition"}:
        note = (
            f"{greeting} I came across the {role} opening at {company}. "
            f"{GENERIC_PROFILE} Would love to connect."
        )
    else:
        note = (
            f"{greeting} I came across the {role} opening at {company}. "
            f"{GENERIC_PROFILE} Would love to connect."
        )

    return note[:300]
