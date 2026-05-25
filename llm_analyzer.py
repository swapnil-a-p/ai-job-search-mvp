from __future__ import annotations

import hashlib
import json
import logging
import os
import re
from typing import Any

import vertexai
from google.oauth2 import service_account
from vertexai.generative_models import GenerationConfig, GenerativeModel

from config import AppConfig


LOGGER = logging.getLogger(__name__)

PROFILE_CONTEXT = """
You are evaluating jobs for an AWS Solutions Architect with experience in cloud architecture, GenAI initiatives,
customer-facing technical engagements, PoCs, CDK, CloudFormation, modernization, solution design,
technical storytelling, and stakeholder engagement.

Strong target roles:
- Solutions Architect
- Cloud Architect
- Customer Engineer
- Solutions Engineer
- GenAI Solutions Architect
- AI Solutions Architect
- Platform Architect
- Forward Deployed Engineer / FDE-style roles
- Technical GTM Engineer

Avoid roles centered on:
- SAP
- Workday
- Salesforce
- ServiceNow
- Oracle ERP
- HCM
- CRM admin
- pure backend SWE
- pure DevOps admin
- pure support
""".strip()


class GeminiAnalyzer:
    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self._model: GenerativeModel | None = None

        if config.vertex_ai_project:
            credentials = service_account.Credentials.from_service_account_info(
                config.service_account_info(),
                scopes=["https://www.googleapis.com/auth/cloud-platform"],
            )
            vertexai.init(
                project=config.vertex_ai_project,
                location=config.vertex_ai_location,
                credentials=credentials,
            )
            self._model = GenerativeModel(config.gemini_model)
            LOGGER.info(
                "Vertex AI initialized: project=%s location=%s model=%s",
                config.vertex_ai_project,
                config.vertex_ai_location,
                config.gemini_model,
            )

        self.cache_path = os.path.join("cache", "gemini_cache.json")
        self._load_cache()
        self.gemini_calls = 0
        self.cache_hits = 0
        self.skipped_due_to_limit = 0
        self.not_analyzed_count = 0
        self.candidate_pool_size = 0
        self.log_msgs: list[str] = []

    def _load_cache(self) -> None:
        try:
            with open(self.cache_path, "r", encoding="utf-8") as f:
                self.cache = json.load(f)
        except Exception:
            self.cache = {}

    def _save_cache(self) -> None:
        try:
            os.makedirs(os.path.dirname(self.cache_path), exist_ok=True)
            with open(self.cache_path, "w", encoding="utf-8") as f:
                json.dump(self.cache, f, indent=2)
        except Exception as e:
            LOGGER.error("Failed to save Gemini cache: %s", e)

    def _cache_key(self, job: dict[str, str]) -> str:
        key_str = f"{job.get('Company','')}|{job.get('Role','')}|{job.get('Job URL','')}|{job.get('Description','')}"
        return hashlib.sha256(key_str.encode("utf-8")).hexdigest()

    def enrich_jobs(
        self,
        scored_jobs: list[dict[str, str]],
        shortlist_jobs: list[dict[str, str]] | None = None,
    ) -> list[dict[str, str]]:
        config = self.config

        if config.gemini_only_shortlist and shortlist_jobs is not None:
            candidate_jobs = shortlist_jobs
        else:
            candidate_jobs = scored_jobs

        self.candidate_pool_size = len(candidate_jobs)
        max_calls = config.max_gemini_calls_per_run

        all_eligible = [job for job in candidate_jobs if self._should_analyze(job)]
        self.skipped_due_to_limit = max(0, len(all_eligible) - max_calls)
        eligible_jobs = all_eligible[:max_calls]
        eligible_keys = {self._job_key(job) for job in eligible_jobs}

        enriched: list[dict[str, str]] = []
        not_analyzed_count = 0

        for job in scored_jobs:
            job_key = self._job_key(job)

            if job_key not in eligible_keys:
                not_analyzed_count += 1
                enriched.append(self._not_analyzed_fields(job))
                continue

            cache_key = self._cache_key(job)

            if cache_key in self.cache:
                llm_fields = self.cache[cache_key]
                valid, reason = self._validate_llm_fields(llm_fields)
                if valid:
                    self.cache_hits += 1
                    self.log_msgs.append(f"Vertex AI cache hit: {job.get('Company')} | {job.get('Role')}")
                    enriched.append(self._merge_job(job, llm_fields, gemini_analyzed="Cached"))
                else:
                    self.log_msgs.append(
                        f"Vertex AI stale cache (fallback): {job.get('Company')} | {job.get('Role')} | {reason}"
                    )
                    enriched.append(self._fallback_fields(job, reason=f"Stale cache: {reason}"))
                continue

            if config.gemini_dry_run:
                self.log_msgs.append(f"[DRY RUN] would analyze: {job.get('Company')} | {job.get('Role')}")
                not_analyzed_count += 1
                enriched.append(self._not_analyzed_fields(job))
                continue

            if not config.enable_gemini:
                self.log_msgs.append(f"LLM disabled: {job.get('Company')} | {job.get('Role')}")
                not_analyzed_count += 1
                enriched.append(self._not_analyzed_fields(job))
                continue

            try:
                llm_fields = self._analyze_job(job)
                valid, reason = self._validate_llm_fields(llm_fields)
                if valid:
                    self.cache[cache_key] = llm_fields
                    self._save_cache()
                    self.gemini_calls += 1
                    self.log_msgs.append(f"Vertex AI call: {job.get('Company')} | {job.get('Role')}")
                    enriched.append(self._merge_job(job, llm_fields, gemini_analyzed="Yes"))
                else:
                    self.log_msgs.append(
                        f"Vertex AI INVALID response (fallback): {job.get('Company')} | {job.get('Role')} | {reason}"
                    )
                    enriched.append(self._fallback_fields(job, reason=reason))
            except Exception as exc:
                LOGGER.exception("Vertex AI enrichment failed for %s | %s", job.get("Company"), job.get("Role"))
                enriched.append(self._fallback_fields(job, reason=str(exc)[:120]))

        self.not_analyzed_count = not_analyzed_count

        for msg in self.log_msgs:
            LOGGER.info(msg)

        self._log_cost_summary()

        return enriched

    def _log_cost_summary(self) -> None:
        LOGGER.info("--- Vertex AI Cost Summary ---")
        LOGGER.info("  Shortlist candidate pool size: %d", self.candidate_pool_size)
        LOGGER.info("  Vertex AI calls made: %d", self.gemini_calls)
        LOGGER.info("  Cache hits: %d", self.cache_hits)
        LOGGER.info("  Skipped (over max limit): %d", self.skipped_due_to_limit)
        LOGGER.info("  Not analyzed: %d", self.not_analyzed_count)

    def _validate_llm_fields(self, llm_fields: dict) -> tuple[bool, str]:
        try:
            classification = str(llm_fields.get("role_classification", "")).strip()
            score = int(float(llm_fields.get("llm_fit_score", 0)))
            if classification == "Strong Fit" and score < 70:
                return False, "Strong Fit but score < 70"
            if classification == "Possible Fit" and not (45 <= score <= 74):
                return False, "Possible Fit but score not 45-74"
            if classification == "Weak Fit" and not (20 <= score <= 44):
                return False, "Weak Fit but score not 20-44"
            if classification == "Reject" and not (0 <= score <= 25):
                return False, "Reject but score not 0-25"
        except Exception as e:
            return False, f"Exception in validation: {e}"
        return True, ""

    def enrich_resume_tailoring(self, shortlisted_jobs: list[dict[str, str]]) -> list[dict[str, str]]:
        analysis_budget = self._resume_analysis_budget()
        eligible_keys = {
            self._job_key(job)
            for job in self._select_jobs_for_resume_tailoring(shortlisted_jobs, analysis_budget)
        }
        rows: list[dict[str, str]] = []
        for job in shortlisted_jobs:
            row = {
                "Company": job["Company"],
                "Role": job["Role"],
                "Job URL": job["Job URL"],
                "Fit Score": job.get("Final Score", job.get("Fit Score", "")),
                "Top 3 Matching Stories": "",
                "ATS Keywords": "",
                "Resume Angle": job.get("Resume Angle", ""),
                "Interview Positioning Notes": "",
                "Resume Version": "",
                "Notes": "",
            }
            if self._job_key(job) not in eligible_keys:
                rows.append(row)
                continue
            try:
                row.update(self._analyze_resume_tailoring(job))
            except Exception as exc:
                LOGGER.exception("Vertex AI resume tailoring failed for %s | %s", job.get("Company"), job.get("Role"))
                LOGGER.error("Vertex AI resume tailoring error: %s", exc)
            rows.append(row)
        return rows

    def _should_analyze(self, job: dict[str, str]) -> bool:
        if not self.config.vertex_ai_project:
            return False
        if self.config.debug_llm_all:
            return True
        try:
            return int(job.get("Fit Score", "0") or 0) >= 35
        except ValueError:
            return False

    def _resume_analysis_budget(self) -> int | None:
        if self.config.debug_llm_all:
            return None
        return max(self.config.gemini_max_resume_jobs, 0)

    def _select_jobs_for_resume_tailoring(
        self,
        shortlisted_jobs: list[dict[str, str]],
        analysis_budget: int | None,
    ) -> list[dict[str, str]]:
        if not self.config.vertex_ai_project:
            return []
        ranked_jobs = sorted(shortlisted_jobs, key=self._resume_sort_key, reverse=True)
        if analysis_budget is None:
            return ranked_jobs
        return ranked_jobs[:analysis_budget]

    def _resume_sort_key(self, job: dict[str, str]) -> tuple[int, int, int]:
        return (
            self._as_int(job.get("Final Score", job.get("Fit Score"))),
            self._priority_rank(job.get("Priority", "Low")),
            self._as_int(job.get("Strategic Company Score")),
        )

    def _priority_rank(self, value: str) -> int:
        return {"High": 3, "Medium": 2, "Low": 1}.get(value, 0)

    def _as_int(self, value: Any) -> int:
        try:
            return int(float(str(value or 0)))
        except ValueError:
            return 0

    def _job_key(self, job: dict[str, str]) -> tuple[str, str, str]:
        return (
            str(job.get("Company", "")).strip().lower(),
            str(job.get("Role", "")).strip().lower(),
            str(job.get("Job URL", "")).strip().lower(),
        )

    def _not_analyzed_fields(self, job: dict[str, str]) -> dict[str, str]:
        merged = dict(job)
        merged.update(
            {
                "LLM Fit Score": "",
                "LLM Role Classification": "Not Analyzed",
                "LLM Role Type": "",
                "LLM Visa Risk": "",
                "LLM Eligibility Notes": "",
                "LLM Strategic Summary": "",
                "LLM Reject Reason": "",
                "LLM Confidence": "",
                "Gemini Analyzed": "No",
                "Final Score": job.get("Fit Score", ""),
            }
        )
        return merged

    def _fallback_fields(self, job: dict[str, str], reason: str = "") -> dict[str, str]:
        merged = dict(job)
        merged.update(
            {
                "LLM Fit Score": "",
                "LLM Role Classification": "Not Analyzed",
                "LLM Role Type": "",
                "LLM Visa Risk": "",
                "LLM Eligibility Notes": "",
                "LLM Strategic Summary": "",
                "LLM Reject Reason": reason,
                "LLM Confidence": "",
                "Gemini Analyzed": "Fallback",
                "Final Score": job.get("Fit Score", ""),
            }
        )
        return merged

    def _merge_job(
        self,
        job: dict[str, str],
        llm_fields: dict[str, Any],
        gemini_analyzed: str = "Yes",
    ) -> dict[str, str]:
        rules_score = int(job.get("Fit Score", "0") or 0)
        llm_score = int(llm_fields.get("llm_fit_score", rules_score) or rules_score)
        use_llm = True
        try:
            classification = str(llm_fields.get("role_classification", "")).strip()
            if classification == "Strong Fit" and llm_score < 70:
                use_llm = False
            if classification == "Possible Fit" and not (45 <= llm_score <= 74):
                use_llm = False
            if classification == "Weak Fit" and not (20 <= llm_score <= 44):
                use_llm = False
            if classification == "Reject" and not (0 <= llm_score <= 25):
                use_llm = False
        except Exception:
            use_llm = False
        final_score = round((llm_score * 0.6) + (rules_score * 0.4)) if use_llm else rules_score
        merged = dict(job)
        merged.update(
            {
                "LLM Fit Score": str(llm_score),
                "LLM Role Classification": str(llm_fields.get("role_classification", "")),
                "LLM Role Type": str(llm_fields.get("role_type", "")),
                "LLM Visa Risk": str(llm_fields.get("visa_risk", "")),
                "LLM Eligibility Notes": str(llm_fields.get("eligibility_notes", "")),
                "LLM Strategic Summary": str(llm_fields.get("strategic_summary", "")),
                "LLM Reject Reason": str(llm_fields.get("reject_reason", "")),
                "LLM Confidence": str(llm_fields.get("confidence", 0.0)),
                "Gemini Analyzed": gemini_analyzed,
                "Final Score": str(final_score),
            }
        )
        return merged

    def _analyze_job(self, job: dict[str, str]) -> dict[str, Any]:
        prompt = f"""
{PROFILE_CONTEXT}

Return JSON only:
{{
  "llm_fit_score": 0,
  "role_classification": "Strong Fit | Possible Fit | Weak Fit | Reject",
  "role_type": "Cloud SA | GenAI SA | Customer Engineer | Solutions Engineer | FDE-style | Technical GTM | ERP/SaaS Specialist | Pure SWE | Support | Other",
  "visa_risk": "Low | Medium | High | Restricted",
  "sponsorship_mentioned": true,
  "citizenship_restriction": false,
  "clearance_required": false,
  "eligibility_notes": "short explanation",
  "strategic_summary": "one sentence explaining why this role is or is not worth my time",
  "reject_reason": "short reason if weak/reject",
  "confidence": 0.0
}}

Visa logic:
- Restricted: US citizenship, green card, US person, ITAR, EAR, export control, active clearance, secret, top secret, TS/SCI, public trust
- High: no sponsorship, unable to sponsor, must be authorized without sponsorship, unrestricted work authorization required
- Favorable: sponsorship available, visa support available, UK/Canada/Australia/Germany sponsorship, skilled worker sponsorship, relocation support

Job:
Company: {job.get("Company")}
Role: {job.get("Role")}
Location: {job.get("Location")}
Posted Date: {job.get("Posted Date")}
Description: {job.get("Description")}
""".strip()
        return self._generate_json(prompt)

    def _analyze_resume_tailoring(self, job: dict[str, str]) -> dict[str, str]:
        prompt = f"""
{PROFILE_CONTEXT}

Return JSON only:
{{
  "Top 3 Matching Stories": "3 concise bullet-like phrases separated by |",
  "ATS Keywords": "comma-separated keywords",
  "Resume Angle": "1 sentence",
  "Interview Positioning Notes": "1-2 sentence guidance"
}}

Job:
Company: {job.get("Company")}
Role: {job.get("Role")}
Location: {job.get("Location")}
Description: {job.get("Description")}
Why Fit: {job.get("Why Fit")}
Strategic Summary: {job.get("LLM Strategic Summary", job.get("Opportunity Summary", ""))}
""".strip()
        return self._generate_json(prompt)

    def _generate_json(self, prompt: str) -> dict[str, Any]:
        if self._model is None:
            raise RuntimeError(
                "Vertex AI model not initialized. Set GOOGLE_CLOUD_PROJECT in your .env."
            )
        response = self._model.generate_content(
            prompt,
            generation_config=GenerationConfig(
                response_mime_type="application/json",
            ),
        )
        return self._parse_json(response.text)

    def _parse_json(self, text: str) -> dict[str, Any]:
        cleaned = text.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:json)?", "", cleaned).strip()
            cleaned = re.sub(r"```$", "", cleaned).strip()
        return json.loads(cleaned)
