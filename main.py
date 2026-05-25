from __future__ import annotations

import json
import logging
import pathlib
from datetime import datetime

from apify_workflow_client import JobSearchApifyClient
from config import AppConfig
from employee_targets import attach_employee_message_drafts
from llm_analyzer import GeminiAnalyzer
from normalizer import employee_key_from_row, job_key_from_row, normalize_employees, normalize_jobs
from referral_targets import build_daily_shortlist, generate_referral_targets, referral_key
from scoring import score_jobs
from sheets import SheetsClient, preserve_fields


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
LOGGER = logging.getLogger(__name__)

STATE_FILE = pathlib.Path("state/run_counter.json")

_TODAY = datetime.now().date().isoformat()

DEFAULT_TARGET_COMPANIES = [
    {"Company": "Anthropic", "Priority": "High", "Careers URL": "", "Notes": "AI-first company", "Active": "Yes", "Date Added": _TODAY},
    {"Company": "Databricks", "Priority": "High", "Careers URL": "", "Notes": "Data + AI platform", "Active": "Yes", "Date Added": _TODAY},
    {"Company": "Snowflake", "Priority": "High", "Careers URL": "", "Notes": "Cloud data platform", "Active": "Yes", "Date Added": _TODAY},
    {"Company": "MongoDB", "Priority": "High", "Careers URL": "", "Notes": "Developer-first data platform", "Active": "Yes", "Date Added": _TODAY},
    {"Company": "Together AI", "Priority": "High", "Careers URL": "", "Notes": "GenAI infrastructure", "Active": "Yes", "Date Added": _TODAY},
    {"Company": "OpenAI", "Priority": "High", "Careers URL": "", "Notes": "Core AI ecosystem", "Active": "Yes", "Date Added": _TODAY},
    {"Company": "Scale AI", "Priority": "Medium", "Careers URL": "", "Notes": "AI data platform", "Active": "Yes", "Date Added": _TODAY},
    {"Company": "Wasabi", "Priority": "Medium", "Careers URL": "", "Notes": "Cloud storage", "Active": "Yes", "Date Added": _TODAY},
    {"Company": "Thought Machine", "Priority": "Medium", "Careers URL": "", "Notes": "Cloud-native banking", "Active": "Yes", "Date Added": _TODAY},
    {"Company": "Caylent", "Priority": "Medium", "Careers URL": "", "Notes": "AWS-focused consultancy", "Active": "Yes", "Date Added": _TODAY},
    {"Company": "Cohere", "Priority": "High", "Careers URL": "", "Notes": "Enterprise AI platform", "Active": "Yes", "Date Added": _TODAY},
    {"Company": "Datadog", "Priority": "Medium", "Careers URL": "", "Notes": "Cloud-native monitoring", "Active": "Yes", "Date Added": _TODAY},
    {"Company": "Modal", "Priority": "Medium", "Careers URL": "", "Notes": "Developer cloud infrastructure", "Active": "Yes", "Date Added": _TODAY},
]


def load_run_state() -> dict:
    if STATE_FILE.exists():
        try:
            with STATE_FILE.open() as f:
                return json.load(f)
        except (json.JSONDecodeError, KeyError, OSError):
            pass
    return {"total_runs": 0, "linkedin_last_run": 0}


def save_run_state(state: dict) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with STATE_FILE.open("w") as f:
        json.dump(state, f, indent=2)


def main() -> None:
    config = AppConfig.from_env()
    sheets = SheetsClient(config)
    sheets.ensure_all_tabs()

    # Run counter + LinkedIn throttle
    state = load_run_state()
    state["total_runs"] += 1
    runs_since_linkedin = state["total_runs"] - state["linkedin_last_run"]
    should_run_linkedin = (
        config.enable_linkedin_jobs
        and runs_since_linkedin >= config.run_linkedin_jobs_every_n_runs
    )
    LOGGER.info(
        "Run #%d | LinkedIn: %s (last ran %d runs ago, threshold=%d)",
        state["total_runs"],
        "YES" if should_run_linkedin else "SKIP",
        runs_since_linkedin,
        config.run_linkedin_jobs_every_n_runs,
    )

    # Read + seed Target_Companies
    existing_targets = sheets.read_rows("Target_Companies")
    if not existing_targets:
        LOGGER.info(
            "Target_Companies is empty. Seeding with %d default companies.",
            len(DEFAULT_TARGET_COMPANIES),
        )
        sheets.replace_rows("Target_Companies", DEFAULT_TARGET_COMPANIES)
        existing_targets = DEFAULT_TARGET_COMPANIES

    active_targets: set[str] = {
        row["Company"].strip().lower()
        for row in existing_targets
        if row.get("Active", "").strip().lower() in {"yes", "true", "1", "y"}
    }
    active_target_names = [
        row["Company"].strip()
        for row in existing_targets
        if row.get("Active", "").strip().lower() in {"yes", "true", "1", "y"}
    ]
    LOGGER.info(
        "Active target companies (%d): %s",
        len(active_target_names),
        ", ".join(active_target_names),
    )

    apify = JobSearchApifyClient(config)
    raw_apify_items = apify.run_job_discovery(
        run_linkedin=should_run_linkedin,
        target_companies=active_target_names,
    )

    if should_run_linkedin:
        state["linkedin_last_run"] = state["total_runs"]
    save_run_state(state)

    raw_jobs = normalize_jobs(raw_apify_items)
    LOGGER.info("Normalized %s unique jobs from %s raw items.", len(raw_jobs), len(raw_apify_items))

    existing_scored = sheets.read_rows("Jobs_Scored")
    existing_referrals = sheets.read_rows("Referral_Targets")
    existing_employee_targets = sheets.read_rows("Employee_Targets")
    existing_shortlist = sheets.read_rows("Daily_Shortlist")
    existing_resume_tailoring = sheets.read_rows("Resume_Tailoring")

    scored_jobs = score_jobs(raw_jobs, target_companies=active_targets)
    # Build shortlist candidate pool (top 15 by rules score)
    shortlist_candidates = build_daily_shortlist(scored_jobs)
    shortlist_pool = shortlist_candidates[:15]
    llm = GeminiAnalyzer(config)
    # Gemini analyzes max 10 from shortlist pool
    scored_jobs = llm.enrich_jobs(scored_jobs, shortlist_jobs=shortlist_pool)
    scored_jobs = preserve_fields(
        scored_jobs,
        existing_scored,
        key_func=job_key_from_row,
        fields_to_preserve=["Status"],
    )

    # Rebuild shortlist after LLM scoring for correct ranking
    daily_shortlist = build_daily_shortlist(scored_jobs)
    referral_targets = generate_referral_targets(daily_shortlist)
    referral_targets = preserve_fields(
        referral_targets,
        existing_referrals,
        key_func=referral_key,
        fields_to_preserve=["Connection Status", "Referral Status", "Follow-up Date", "Notes"],
    )
    daily_shortlist = preserve_fields(
        daily_shortlist,
        existing_shortlist,
        key_func=lambda row: job_key_from_row(
            {"Company": row.get("Company", ""), "Role": row.get("Role", ""), "Job URL": row.get("Job URL", "")}
        ),
        fields_to_preserve=["My Decision", "Referral Sent?", "Applied?", "Notes"],
    )
    resume_tailoring = llm.enrich_resume_tailoring(daily_shortlist)
    resume_tailoring = preserve_fields(
        resume_tailoring,
        existing_resume_tailoring,
        key_func=lambda row: job_key_from_row(
            {"Company": row.get("Company", ""), "Role": row.get("Role", ""), "Job URL": row.get("Job URL", "")}
        ),
        fields_to_preserve=["Resume Version", "Notes"],
    )

    employee_targets: list[dict[str, str]] = []
    if config.enable_linkedin_employee_discovery:
        top_shortlist = daily_shortlist[:config.max_companies_for_employee_discovery]
        shortlist_companies = _unique_companies_ordered(top_shortlist)
        shortlist_job_map = {job["Company"].strip().lower(): job for job in top_shortlist}
        LOGGER.info(
            "Employee discovery enabled. Querying %d shortlisted companies: %s",
            len(shortlist_companies),
            ", ".join(shortlist_companies),
        )
        try:
            employee_items = apify.run_employee_discovery(shortlist_companies)
        except Exception as exc:
            LOGGER.error("Employee discovery actor failed: %s. Continuing without employee targets.", exc)
            employee_items = []
        employee_targets = normalize_employees(
            employee_items,
            shortlist_job_map,
            max_per_company=config.max_employees_per_company,
        )
        employee_targets = attach_employee_message_drafts(employee_targets)
        LOGGER.info(
            "Employee discovery: %d companies queried | %d raw profiles returned | %d profiles kept | %d profiles skipped",
            len(shortlist_companies),
            len(employee_items),
            len(employee_targets),
            max(0, len(employee_items) - len(employee_targets)),
        )
        employee_targets = preserve_fields(
            employee_targets,
            existing_employee_targets,
            key_func=employee_key_from_row,
            fields_to_preserve=["Connection Status", "Referral Status", "Follow-up Date", "Notes"],
        )
    else:
        LOGGER.info("Employee discovery disabled. Skipping LinkedIn employee actor.")

    raw_count = sheets.replace_rows("Jobs_Raw", raw_jobs)
    scored_count = sheets.replace_rows("Jobs_Scored", scored_jobs)
    referral_count = sheets.replace_rows("Referral_Targets", referral_targets)
    employee_count = sheets.replace_rows("Employee_Targets", employee_targets)
    shortlist_count = sheets.replace_rows("Daily_Shortlist", daily_shortlist)
    outreach_count = len(sheets.read_rows("Outreach_Tracker"))
    resume_count = sheets.replace_rows("Resume_Tailoring", resume_tailoring)

    LOGGER.info("Wrote %s rows to Jobs_Raw.", raw_count)
    LOGGER.info("Wrote %s rows to Jobs_Scored.", scored_count)
    LOGGER.info("Wrote %s rows to Referral_Targets.", referral_count)
    LOGGER.info("Wrote %s rows to Employee_Targets.", employee_count)
    LOGGER.info("Wrote %s rows to Daily_Shortlist.", shortlist_count)
    LOGGER.info("Preserved Outreach_Tracker with %s existing rows.", outreach_count)
    LOGGER.info("Wrote %s rows to Resume_Tailoring.", resume_count)

    # End-of-run summary
    google_jobs = sum(
        1 for j in raw_jobs
        if "google" in j.get("Source", "").lower() or "search" in j.get("Source Actor", "").lower()
    )
    linkedin_jobs = sum(1 for j in raw_jobs if "linkedin" in j.get("Source", "").lower())
    LOGGER.info(
        "=== RUN SUMMARY === Run #%d | LinkedIn: %s | "
        "Jobs fetched: %d total (%d Google/search, %d LinkedIn) | "
        "Gemini: %d calls, %d cached, %d skipped, %d not analyzed | "
        "Shortlist: %d jobs",
        state["total_runs"],
        "Yes" if should_run_linkedin else "No",
        len(raw_jobs),
        google_jobs,
        linkedin_jobs,
        llm.gemini_calls,
        llm.cache_hits,
        llm.skipped_due_to_limit,
        llm.not_analyzed_count,
        shortlist_count,
    )


def _unique_companies_ordered(jobs: list[dict[str, str]]) -> list[str]:
    seen: set[str] = set()
    companies: list[str] = []
    for job in jobs:
        company = job["Company"].strip()
        key = company.lower()
        if company and key not in seen:
            seen.add(key)
            companies.append(company)
    return companies


if __name__ == "__main__":
    main()
