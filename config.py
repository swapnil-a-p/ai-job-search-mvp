from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any

from dotenv import load_dotenv


class ConfigError(ValueError):
    pass


# LinkedIn queries: high-signal roles only — kept short to control cost
DEFAULT_JOB_QUERIES = [
    '"Forward Deployed Engineer" AI',
    '"GenAI Solutions Architect"',
    '"Customer Engineer" cloud',
]

# Google Search: primary discovery engine — broad ATS + startup coverage
DEFAULT_GOOGLE_SEARCH_QUERIES = [
    # Greenhouse (official + boards subdomain)
    'site:greenhouse.io ("solutions architect" OR "customer engineer" OR "forward deployed engineer") (AWS OR cloud OR GenAI)',
    'site:boards.greenhouse.io ("solutions architect" OR "customer engineer" OR "forward deployed engineer") (AWS OR GenAI OR cloud)',
    # Lever
    'site:lever.co ("solutions architect" OR "customer engineer" OR "solutions engineer") (AWS OR cloud OR GenAI)',
    # Ashby
    'site:ashbyhq.com ("solutions architect" OR "customer engineer" OR "forward deployed engineer") (AWS OR cloud OR AI)',
    'site:jobs.ashbyhq.com ("solutions architect" OR "forward deployed engineer" OR "customer engineer") (cloud OR AWS)',
    # Other ATS platforms
    'site:workable.com ("solutions architect" OR "customer engineer") (AWS OR cloud OR GenAI)',
    'site:smartrecruiters.com ("solutions architect" OR "customer engineer" OR "solutions engineer") (AWS OR cloud)',
    # Startup job boards
    'site:jobs.ycombinator.com ("solutions architect" OR "customer engineer" OR "forward deployed engineer")',
    'site:wellfound.com ("solutions architect" OR "customer engineer" OR "forward deployed engineer") (AWS OR cloud)',
    # GenAI / Technical GTM specific — catches roles not in above
    '("genai solutions architect" OR "ai solutions architect" OR "technical gtm engineer" OR "platform architect") (AWS OR cloud) -site:linkedin.com',
]

DEFAULT_EMPLOYEE_ROLE_KEYWORDS = [
    "recruiter",
    "talent acquisition",
    "solutions architect",
    "cloud architect",
    "customer engineer",
    "hiring manager",
    "engineering manager",
    "ai",
    "genai",
    "aws",
]


@dataclass

class AppConfig:
    apify_token: str
    linkedin_jobs_actor_id: str
    google_search_actor_id: str
    linkedin_employees_actor_id: str
    google_sheet_name: str
    google_sheet_url: str | None
    google_service_account_file: str | None
    google_service_account_json: str | None
    gemini_api_key: str | None
    vertex_ai_project: str | None
    vertex_ai_location: str
    debug_llm_all: bool
    gemini_model: str
    gemini_max_jobs: int
    gemini_max_resume_jobs: int
    enable_linkedin_employee_discovery: bool
    jobs_max_results: int
    google_search_max_results: int
    employee_max_results_per_company: int
    linkedin_job_location: str
    linkedin_job_queries: list[str] = field(default_factory=list)
    google_search_queries: list[str] = field(default_factory=list)
    employee_role_keywords: list[str] = field(default_factory=list)
    linkedin_jobs_actor_input_override: dict[str, Any] | None = None
    google_search_actor_input_override: dict[str, Any] | None = None
    linkedin_employees_actor_input_override: dict[str, Any] | None = None
    # Gemini control envs
    enable_gemini: bool = True
    max_gemini_calls_per_run: int = 10
    gemini_only_shortlist: bool = True
    gemini_dry_run: bool = False
    # Employee discovery controls
    max_companies_for_employee_discovery: int = 5
    max_employees_per_company: int = 5
    # Job source toggles
    enable_linkedin_jobs: bool = True
    run_linkedin_jobs_every_n_runs: int = 7
    max_linkedin_queries: int = 3

    @classmethod
    def from_env(cls) -> "AppConfig":
        load_dotenv()

        config = cls(
                        enable_gemini=_bool_env("ENABLE_GEMINI", True),
                        max_gemini_calls_per_run=_int_env("MAX_GEMINI_CALLS_PER_RUN", 10),
                        gemini_only_shortlist=_bool_env("GEMINI_ONLY_SHORTLIST", True),
                        gemini_dry_run=_bool_env("GEMINI_DRY_RUN", False),
                        max_companies_for_employee_discovery=_int_env("MAX_COMPANIES_FOR_EMPLOYEE_DISCOVERY", 5),
                        max_employees_per_company=_int_env("MAX_EMPLOYEES_PER_COMPANY", 5),
                        enable_linkedin_jobs=_bool_env("ENABLE_LINKEDIN_JOBS", True),
                        run_linkedin_jobs_every_n_runs=_int_env("RUN_LINKEDIN_JOBS_EVERY_N_RUNS", 7),
                        max_linkedin_queries=_int_env("MAX_LINKEDIN_QUERIES", 3),
            apify_token=_require_env("APIFY_TOKEN"),
            linkedin_jobs_actor_id=_require_env("LINKEDIN_JOBS_ACTOR_ID"),
            google_search_actor_id=_require_env("GOOGLE_SEARCH_ACTOR_ID"),
            linkedin_employees_actor_id=_require_env("LINKEDIN_EMPLOYEES_ACTOR_ID"),
            google_sheet_name=_require_env("GOOGLE_SHEET_NAME"),
            google_sheet_url=_optional_env("GOOGLE_SHEET_URL"),
            google_service_account_file=_optional_env("GOOGLE_SERVICE_ACCOUNT_FILE"),
            google_service_account_json=_optional_env("GOOGLE_SERVICE_ACCOUNT_JSON"),
            gemini_api_key=_optional_env("GEMINI_API_KEY"),
            vertex_ai_project=_optional_env("GOOGLE_CLOUD_PROJECT"),
            vertex_ai_location=_optional_env("VERTEX_AI_LOCATION", "us-central1") or "us-central1",
            debug_llm_all=_bool_env("DEBUG_LLM_ALL", False),
            gemini_model=_optional_env("GEMINI_MODEL", "gemini-2.5-flash") or "gemini-2.5-flash",
            gemini_max_jobs=_int_env("GEMINI_MAX_JOBS", 12),
            gemini_max_resume_jobs=_int_env("GEMINI_MAX_RESUME_JOBS", 10),
            enable_linkedin_employee_discovery=_bool_env(
                "ENABLE_LINKEDIN_EMPLOYEE_DISCOVERY", False
            ),
            jobs_max_results=_int_env("JOBS_MAX_RESULTS", 50),
            google_search_max_results=_int_env("GOOGLE_SEARCH_MAX_RESULTS", 30),
            employee_max_results_per_company=_int_env("EMPLOYEE_MAX_RESULTS_PER_COMPANY", 10),
            linkedin_job_location=_optional_env("LINKEDIN_JOB_LOCATION", "United States")
            or "United States",
            linkedin_job_queries=_list_env("LINKEDIN_JOB_QUERIES", DEFAULT_JOB_QUERIES),
            google_search_queries=_list_env(
                "GOOGLE_SEARCH_QUERIES", DEFAULT_GOOGLE_SEARCH_QUERIES
            ),
            employee_role_keywords=_list_env(
                "EMPLOYEE_ROLE_KEYWORDS", DEFAULT_EMPLOYEE_ROLE_KEYWORDS
            ),
            linkedin_jobs_actor_input_override=_json_env("LINKEDIN_JOBS_ACTOR_INPUT_JSON"),
            google_search_actor_input_override=_json_env("GOOGLE_SEARCH_ACTOR_INPUT_JSON"),
            linkedin_employees_actor_input_override=_json_env(
                "LINKEDIN_EMPLOYEES_ACTOR_INPUT_JSON"
            ),
        )

        if not config.google_service_account_file and not config.google_service_account_json:
            raise ConfigError(
                "Set GOOGLE_SERVICE_ACCOUNT_FILE or GOOGLE_SERVICE_ACCOUNT_JSON in your .env file."
            )

        return config

    def service_account_info(self) -> dict[str, Any]:
        if self.google_service_account_json:
            try:
                return json.loads(self.google_service_account_json)
            except json.JSONDecodeError as exc:
                raise ConfigError("GOOGLE_SERVICE_ACCOUNT_JSON must be valid JSON.") from exc

        assert self.google_service_account_file is not None
        with open(self.google_service_account_file, "r", encoding="utf-8") as handle:
            return json.load(handle)


def _require_env(name: str) -> str:
    value = _optional_env(name)
    if not value:
        raise ConfigError(f"Missing required environment variable: {name}")
    return value


def _optional_env(name: str, default: str | None = None) -> str | None:
    value = os.getenv(name, default)
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def _bool_env(name: str, default: bool) -> bool:
    value = _optional_env(name)
    if value is None:
        return default
    return value.lower() in {"1", "true", "yes", "y", "on"}


def _int_env(name: str, default: int) -> int:
    value = _optional_env(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError as exc:
        raise ConfigError(f"{name} must be an integer.") from exc


def _json_env(name: str) -> dict[str, Any] | None:
    value = _optional_env(name)
    if value is None:
        return None
    try:
        loaded = json.loads(value)
    except json.JSONDecodeError as exc:
        raise ConfigError(f"{name} must be valid JSON.") from exc
    if not isinstance(loaded, dict):
        raise ConfigError(f"{name} must decode to a JSON object.")
    return loaded


def _list_env(name: str, default: list[str]) -> list[str]:
    value = _optional_env(name)
    if value is None:
        return list(default)

    if value.startswith("["):
        try:
            loaded = json.loads(value)
        except json.JSONDecodeError as exc:
            raise ConfigError(f"{name} must be valid JSON when using array syntax.") from exc
        if not isinstance(loaded, list):
            raise ConfigError(f"{name} must be a JSON array.")
        return [str(item).strip() for item in loaded if str(item).strip()]

    return [line.strip() for line in value.split("||") if line.strip()]
