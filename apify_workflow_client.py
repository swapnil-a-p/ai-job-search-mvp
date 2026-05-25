from __future__ import annotations

import logging
from typing import Any

import requests

from config import AppConfig


LOGGER = logging.getLogger(__name__)


class JobSearchApifyClient:
    BASE_URL = "https://api.apify.com/v2"

    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self.session = requests.Session()
        self.session.headers.update({"Accept": "application/json"})

    def run_job_discovery(
        self,
        run_linkedin: bool = False,
        target_companies: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []

        google_items = self._run_google_search_queries()
        items.extend(google_items)

        if target_companies:
            target_items = self._run_target_company_queries(target_companies)
            items.extend(target_items)

        if run_linkedin:
            linkedin_items = self._run_linkedin_job_queries()
            items.extend(linkedin_items)

        return items

    def _run_linkedin_job_queries(self) -> list[dict[str, Any]]:
        if self.config.linkedin_jobs_actor_input_override:
            return self._call_actor(
                self.config.linkedin_jobs_actor_id,
                self.config.linkedin_jobs_actor_input_override,
                actor_label="LinkedIn Jobs Scraper",
            )

        queries = self.config.linkedin_job_queries[: self.config.max_linkedin_queries]
        all_items: list[dict[str, Any]] = []
        per_query_limit = max(1, self.config.jobs_max_results // max(len(queries), 1))

        for query in queries:
            actor_input = {
                "keywords": query,
                "location": self.config.linkedin_job_location,
                "maxJobs": per_query_limit,
                "sortOrder": "date",
                "publishedAt": "r604800",
            }
            items = self._call_actor(
                self.config.linkedin_jobs_actor_id,
                actor_input,
                actor_label=f"LinkedIn Jobs Scraper [{query}]",
            )
            all_items.extend(items)

        return all_items

    def _run_google_search_queries(self) -> list[dict[str, Any]]:
        if self.config.google_search_actor_input_override:
            return self._call_actor(
                self.config.google_search_actor_id,
                self.config.google_search_actor_input_override,
                actor_label="Google Search Results Scraper",
            )

        all_items: list[dict[str, Any]] = []
        for query in self.config.google_search_queries:
            actor_input = {
                "queries": query,
                "maxResults": self.config.google_search_max_results,
                "csvFriendlyOutput": True,
                "mobileResults": False,
            }
            items = self._call_actor(
                self.config.google_search_actor_id,
                actor_input,
                actor_label=f"Google Search Results Scraper [{query}]",
            )
            all_items.extend(items)

        return all_items

    def _run_target_company_queries(self, target_companies: list[str]) -> list[dict[str, Any]]:
        if not target_companies:
            return []

        ROLE_TERMS = (
            '"solutions architect" OR "customer engineer" OR '
            '"forward deployed engineer" OR "solutions engineer"'
        )
        BATCH_SIZE = 5
        all_items: list[dict[str, Any]] = []

        for i in range(0, len(target_companies), BATCH_SIZE):
            batch = target_companies[i : i + BATCH_SIZE]
            company_terms = " OR ".join(f'"{c}"' for c in batch)
            query = f"({company_terms}) ({ROLE_TERMS}) (job OR careers)"
            actor_input = {
                "queries": query,
                "maxResults": self.config.google_search_max_results,
                "csvFriendlyOutput": True,
                "mobileResults": False,
            }
            items = self._call_actor(
                self.config.google_search_actor_id,
                actor_input,
                actor_label=f"Target Company Search [{', '.join(batch)}]",
            )
            all_items.extend(items)

        return all_items

    def run_employee_discovery(self, companies: list[str]) -> list[dict[str, Any]]:
        if not companies:
            return []

        LOGGER.info(
            "Employee discovery: querying %d companies: %s",
            len(companies),
            ", ".join(companies),
        )
        return self._call_actor(
            self.config.linkedin_employees_actor_id,
            self._linkedin_employees_input(companies),
            actor_label="LinkedIn Company Employees Scraper",
        )

    def _call_actor(
        self, actor_id: str, actor_input: dict[str, Any], actor_label: str
    ) -> list[dict[str, Any]]:
        LOGGER.info("Running %s (%s)", actor_label, actor_id)
        url = f"{self.BASE_URL}/acts/{actor_id}/runs"
        response = self.session.post(
            url,
            params={"token": self.config.apify_token},
            json=actor_input,
            timeout=300,
        )
        response.raise_for_status()
        run = response.json()["data"]
        run_id = run["id"]

        finished = self._wait_for_run(run_id)
        dataset_id = finished.get("defaultDatasetId")
        if not dataset_id:
            raise RuntimeError(f"{actor_label} did not return a default dataset ID.")

        items = self._dataset_items(dataset_id)
        LOGGER.info(
            "%s completed. Dataset %s returned %s items.",
            actor_label,
            dataset_id,
            len(items),
        )
        return items

    def _wait_for_run(self, run_id: str) -> dict[str, Any]:
        url = f"{self.BASE_URL}/actor-runs/{run_id}"
        wait_seconds = 999
        response = self.session.get(
            url,
            params={"token": self.config.apify_token, "waitForFinish": wait_seconds},
            timeout=330,
        )
        response.raise_for_status()
        run = response.json()["data"]
        if run.get("status") not in {"SUCCEEDED", "TIMED-OUT"}:
            raise RuntimeError(f"Apify run {run_id} finished with status {run.get('status')}.")
        return run

    def _dataset_items(self, dataset_id: str) -> list[dict[str, Any]]:
        url = f"{self.BASE_URL}/datasets/{dataset_id}/items"
        response = self.session.get(
            url,
            params={
                "token": self.config.apify_token,
                "clean": "true",
                "format": "json",
            },
            timeout=180,
        )
        response.raise_for_status()
        return response.json()

    def _linkedin_jobs_input(self) -> dict[str, Any]:
        if self.config.linkedin_jobs_actor_input_override:
            return self.config.linkedin_jobs_actor_input_override

        return {
            "keywords": self.config.linkedin_job_queries[0] if self.config.linkedin_job_queries else "",
            "location": self.config.linkedin_job_location,
            "maxJobs": self.config.jobs_max_results,
            "sortOrder": "date",
            "publishedAt": "r604800",
        }

    def _google_search_input(self) -> dict[str, Any]:
        if self.config.google_search_actor_input_override:
            return self.config.google_search_actor_input_override

        return {
            "queries": self.config.google_search_queries[0] if self.config.google_search_queries else "",
            "maxResults": self.config.google_search_max_results,
            "csvFriendlyOutput": True,
            "mobileResults": False,
        }

    def _linkedin_employees_input(self, companies: list[str]) -> dict[str, Any]:
        if self.config.linkedin_employees_actor_input_override:
            override = dict(self.config.linkedin_employees_actor_input_override)
            override.setdefault("targets", companies)
            override.setdefault("maxEmployees", self.config.max_employees_per_company)
            return override

        return {
            "targets": companies,
            "maxEmployees": self.config.max_employees_per_company,
        }
