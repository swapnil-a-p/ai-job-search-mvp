from __future__ import annotations

from urllib.parse import quote_plus

from message_generator import generate_connection_note
from scoring import freshness_score


TARGET_TEMPLATES = [
    ("Recruiter / Talent Acquisition", 'site:linkedin.com/in "{company}" ("Recruiter" OR "Talent Acquisition")'),
    ("Technical Peer", 'site:linkedin.com/in "{company}" ("Solutions Architect" OR "Customer Engineer" OR "Solutions Engineer")'),
    ("Cloud/AI Adjacent", 'site:linkedin.com/in "{company}" ("AWS" OR "Cloud Architect" OR "GenAI")'),
]


def generate_referral_targets(shortlist_jobs: list[dict[str, str]]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for job in shortlist_jobs:
        company = job["Company"]
        role = job["Role"]
        for target_type, query_template in TARGET_TEMPLATES:
            query = query_template.format(company=company)
            rows.append(
                {
                    "Company": company,
                    "Role": role,
                    "Target Type": target_type,
                    "Suggested Search Query": query,
                    "Search URL": f"https://www.google.com/search?q={quote_plus(query)}",
                    "Message Draft": generate_connection_note(
                        company=company,
                        role=role,
                        person_name=None,
                        target_type=target_type,
                    ),
                    "Connection Status": "Not Started",
                    "Referral Status": "Not Started",
                    "Follow-up Date": "",  # Always blank by default
                    "Notes": "",  # Always blank by default
                }
            )
    return rows


def best_referral_for_job(job: dict[str, str]) -> tuple[str, str]:
    company = job["Company"]
    role = job["Role"]
    target_type, query_template = TARGET_TEMPLATES[0]
    query = query_template.format(company=company)
    return (
        f"https://www.google.com/search?q={quote_plus(query)}",
        generate_connection_note(company=company, role=role, person_name=None, target_type=target_type),
    )


def build_daily_shortlist(scored_jobs: list[dict[str, str]]) -> list[dict[str, str]]:
    candidates = [
        job
        for job in scored_jobs
        if job.get("Apply Recommendation") in {"Apply", "Maybe"}
        and job.get("Priority") in {"High", "Medium"}
        and job.get("Visa Risk") != "Restricted"
        and job.get("Seniority Risk") != "High"
    ]
    candidates.sort(
        key=lambda row: (
            -int(row.get("Realistic Match Score", "0") or 0),
            -int(row.get("Global Mobility Score", "0") or 0),
            -int(row.get("Final Score", row.get("Fit Score", "0")) or 0),
            0 if row.get("Visa Risk") == "Low" else 1 if row.get("Visa Risk") == "Medium" else 2,
            -int(row.get("Strategic Company Score", "0") or 0),
            -freshness_score(row.get("Posted Date", "")),
            row.get("Company", ""),
        )
    )

    shortlist: list[dict[str, str]] = []
    for rank, job in enumerate(candidates[:10], start=1):
        best_search_url, message_draft = best_referral_for_job(job)
        shortlist.append(
            {
                "Rank": str(rank),
                "Company": job["Company"],
                "Role": job["Role"],
                "Location": job["Location"],
                "Job URL": job["Job URL"],
                "Fit Score": job["Fit Score"],
                "Final Score": job.get("Final Score", job["Fit Score"]),
                "Realistic Match Score": job.get("Realistic Match Score", ""),
                "Seniority Risk": job.get("Seniority Risk", ""),
                "Transition Difficulty": job.get("Transition Difficulty", ""),
                "Geo Quality": job.get("Geo Quality", ""),
                "Global Mobility Score": job.get("Global Mobility Score", ""),
                "Priority": job["Priority"],
                "Strategic Company Score": job.get("Strategic Company Score", ""),
                "Strategic Reason": job.get("Strategic Reason", ""),
                "Visa Risk": job["Visa Risk"],
                "Apply Recommendation": job["Apply Recommendation"],
                "Why Fit": job["Why Fit"],
                "Opportunity Summary": job.get("LLM Strategic Summary") or _opportunity_summary(job),
                "Best Referral Search": best_search_url,
                "Message Draft": message_draft,
                "Next Action": _next_action(job, rank),
                "My Decision": "",
                "Referral Sent?": "",
                "Applied?": "",
                "Notes": "",
            }
        )
    return shortlist


def _next_action(job: dict[str, str], rank: int) -> str:
    if job.get("Apply Recommendation") == "Avoid":
        return "Avoid"
    if rank <= 3:
        return "Request referral"
    return "Review JD + tailor resume"


def _opportunity_summary(job: dict[str, str]) -> str:
    company_reason = job.get("Strategic Reason", "").lower()
    role_type = job.get("Role Type", "role")
    if "ai" in company_reason:
        company_frame = "at a high-growth AI company"
    elif "cloud" in company_reason or "platform" in company_reason:
        company_frame = "at a strong cloud/platform company"
    else:
        company_frame = "at a strategically relevant company"
    return (
        f"Strong {role_type.lower()} and customer-facing architecture fit {company_frame} "
        f"with near-term upside worth attention."
    )


def referral_key(row: dict[str, str]) -> str:
    return "||".join(
        [
            row.get("Company", "").strip().lower(),
            row.get("Role", "").strip().lower(),
            row.get("Target Type", "").strip().lower(),
            row.get("Suggested Search Query", "").strip().lower(),
        ]
    )
