# AI Career Intelligence Workflow MVP

> **Branch: `vertex-ai`** — This branch replaces the Gemini REST API calls with the [Vertex AI SDK](https://cloud.google.com/vertex-ai/docs/python-sdk/use-vertex-ai-python-sdk) (`google-cloud-aiplatform`). Auth is handled via a GCP service account rather than an API key. See the `main` branch for the original Gemini REST API implementation.

This workspace runs Apify actors locally, normalizes and scores jobs with a rules engine + Gemini on Vertex AI, generates a daily shortlist, produces referral search targets, optionally discovers company employees, and writes all outputs to Google Sheets.

## Workflow

1. Seed `Target_Companies` tab on first run (13 default companies); subsequent runs read active entries from the sheet
2. Run Google Search Results Scraper for each configured query (every run)
3. Run targeted Google searches for active `Target_Companies` (every run)
4. Optionally run LinkedIn Jobs Scraper — throttled to once every N runs via a local run counter (`state/run_counter.json`)
5. Normalize both datasets into one job schema and deduplicate by `Company + Role + Job URL`
6. Score jobs with the rules engine (keyword boosts/penalties, visa risk, seniority risk, transition difficulty, geo quality, global mobility, source quality, strategic company score)
7. Build a shortlist candidate pool (top 15 by rules score) and send to Gemini for LLM enrichment (fit score, role classification, visa analysis, strategic summary)
8. Compute `Final Score` as a weighted blend: 60% LLM score + 40% rules score
9. Build `Daily_Shortlist` (top 10 actionable jobs re-ranked by Realistic Match Score + Global Mobility Score + Final Score)
10. Generate `Referral_Targets` from the shortlist
11. Run Gemini resume tailoring analysis for the top shortlisted jobs
12. Optionally run LinkedIn Company Employees Scraper for top shortlisted companies
13. Write all outputs to Google Sheets while preserving manual statuses

## Files

- `main.py` — orchestration and run counter logic
- `config.py` — all environment variable parsing and defaults
- `apify_workflow_client.py` — Apify REST API client (per-query actor runs, polling, dataset fetch)
- `apify_client.py` — legacy client (kept for reference)
- `normalizer.py` — raw item → unified job/employee schema
- `scoring.py` — rules-based scoring engine
- `llm_analyzer.py` — Gemini enrichment (job fit + resume tailoring), with local disk cache
- `referral_targets.py` — shortlist building and referral target generation
- `employee_targets.py` — employee target filtering and message drafting
- `message_generator.py` — connection note templates
- `sheets.py` — Google Sheets read/write with tab management
- `.env.example`

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Fill `.env` with:

**Required:**
- `APIFY_TOKEN`
- `LINKEDIN_JOBS_ACTOR_ID`
- `GOOGLE_SEARCH_ACTOR_ID`
- `LINKEDIN_EMPLOYEES_ACTOR_ID`
- `GOOGLE_SHEET_NAME`
- `GOOGLE_SERVICE_ACCOUNT_FILE` or `GOOGLE_SERVICE_ACCOUNT_JSON`

**Optional:**
- `GOOGLE_SHEET_URL` — bypass Drive lookup and open a known sheet directly
- `GOOGLE_CLOUD_PROJECT` — your GCP project ID; enables Vertex AI LLM enrichment. If unset, all jobs get `Gemini Analyzed=No`
- `VERTEX_AI_LOCATION` — Vertex AI region, default `us-central1`
- `GEMINI_MODEL` — model name passed to Vertex AI `GenerativeModel`, defaults to `gemini-2.5-flash`
- Auth reuses `GOOGLE_SERVICE_ACCOUNT_FILE`/`GOOGLE_SERVICE_ACCOUNT_JSON` — grant the service account the **Vertex AI User** IAM role in your GCP project
- `ENABLE_GEMINI` — `true`/`false`, default `true`
- `GEMINI_DRY_RUN` — `true` skips live Gemini calls (useful for testing), default `false`
- `DEBUG_LLM_ALL` — `true` forces Gemini analysis on all jobs regardless of score, default `false`
- `MAX_GEMINI_CALLS_PER_RUN` — max live Gemini API calls per run, default `10`
- `GEMINI_MAX_JOBS` — max jobs eligible for job enrichment, default `12`
- `GEMINI_MAX_RESUME_JOBS` — max jobs analyzed for resume tailoring, default `10`
- `GEMINI_ONLY_SHORTLIST` — `true` limits Gemini to shortlist candidates only, default `true`
- `ENABLE_LINKEDIN_JOBS` — `true`/`false`, default `true`
- `RUN_LINKEDIN_JOBS_EVERY_N_RUNS` — LinkedIn actor runs once every N total runs, default `7`
- `MAX_LINKEDIN_QUERIES` — cap on LinkedIn queries per run, default `3`
- `JOBS_MAX_RESULTS` — max LinkedIn results per query, default `50`
- `GOOGLE_SEARCH_MAX_RESULTS` — max Google search results per query, default `30`
- `EMPLOYEE_MAX_RESULTS_PER_COMPANY` — max employee profiles fetched per company, default `10`
- `MAX_COMPANIES_FOR_EMPLOYEE_DISCOVERY` — max shortlisted companies to run employee discovery on, default `5`
- `MAX_EMPLOYEES_PER_COMPANY` — max employee profiles kept per company after filtering, default `5`
- `LINKEDIN_JOB_LOCATION` — defaults to `United States`

If your Google Sheet already exists, share it with the service account email as `Editor`.

## Default Queries

LinkedIn job queries default to (3 high-signal, cost-controlled):

- `"Forward Deployed Engineer" AI`
- `"GenAI Solutions Architect"`
- `"Customer Engineer" cloud`

Google search queries default to (broad ATS + startup coverage):

- `site:greenhouse.io ("solutions architect" OR "customer engineer" OR "forward deployed engineer") (AWS OR cloud OR GenAI)`
- `site:boards.greenhouse.io ("solutions architect" OR "customer engineer" OR "forward deployed engineer") (AWS OR GenAI OR cloud)`
- `site:lever.co ("solutions architect" OR "customer engineer" OR "solutions engineer") (AWS OR cloud OR GenAI)`
- `site:ashbyhq.com ("solutions architect" OR "customer engineer" OR "forward deployed engineer") (AWS OR cloud OR AI)`
- `site:jobs.ashbyhq.com ("solutions architect" OR "forward deployed engineer" OR "customer engineer") (cloud OR AWS)`
- `site:workable.com ("solutions architect" OR "customer engineer") (AWS OR cloud OR GenAI)`
- `site:smartrecruiters.com ("solutions architect" OR "customer engineer" OR "solutions engineer") (AWS OR cloud)`
- `site:jobs.ycombinator.com ("solutions architect" OR "customer engineer" OR "forward deployed engineer")`
- `site:wellfound.com ("solutions architect" OR "customer engineer" OR "forward deployed engineer") (AWS OR cloud)`
- `("genai solutions architect" OR "ai solutions architect" OR "technical gtm engineer" OR "platform architect") (AWS OR cloud) -site:linkedin.com`

Override them in `.env` with JSON arrays or `||`-separated strings:
- `LINKEDIN_JOB_QUERIES`
- `GOOGLE_SEARCH_QUERIES`
- `EMPLOYEE_ROLE_KEYWORDS`

## Notes On Actor Inputs

Actors are called per-query (one actor run per search query) rather than in a single batch. This gives cleaner per-source item counts and allows per-query result limits.

- LinkedIn jobs actor: `keywords`, `location`, `maxJobs`, `sortOrder`, `publishedAt`
- Google search actor: `queries`, `maxResults`, `csvFriendlyOutput`, `mobileResults`
- Employee discovery: `targets`, `maxEmployees`

Override entire actor inputs via:

- `LINKEDIN_JOBS_ACTOR_INPUT_JSON`
- `GOOGLE_SEARCH_ACTOR_INPUT_JSON`
- `LINKEDIN_EMPLOYEES_ACTOR_INPUT_JSON`

Those overrides take precedence over all defaults.

## Output Tabs

The script creates and maintains:

- `Jobs_Raw` — all normalized jobs before scoring
- `Jobs_Scored` — scored jobs with rules + LLM fields
- `Daily_Shortlist` — top 10 actionable jobs ranked by Realistic Match Score, Global Mobility Score, and Final Score
- `Referral_Targets` — referral search targets generated from the shortlist
- `Employee_Targets` — LinkedIn employee profiles for top shortlisted companies (when discovery is enabled)
- `Outreach_Tracker` — manually managed outreach log (never overwritten)
- `Resume_Tailoring` — Gemini-generated resume tailoring guidance per shortlisted job
- `Target_Companies` — user-managed list of priority companies; seeded with 13 defaults on first run

`Jobs_Scored` includes rules-based scoring columns:

- `Fit Score` — raw rules engine score
- `Source Quality Score` — signal quality of the job posting source (ATS domain)
- `Realistic Match Score` — career-stage fit based on seniority and transition difficulty
- `Seniority Risk` — Low / Medium / High based on title words and years-required language
- `Transition Difficulty` — Easy / Medium / Hard based on role overlap with target patterns
- `Geo Quality` — Low / Medium / High based on location and sponsorship signals
- `Global Mobility Score` — 0–25 company-level immigration/relocation signal
- `Strategic Company Score` — 0–25 strategic relevance of the company
- `Work Authorization Signal`, `Visa Risk`, `Sponsorship Mentioned`, `Citizenship Restriction`, `Clearance Required`, `Eligibility Notes`, `Apply Recommendation`

`Jobs_Scored` also includes LLM columns (populated when Gemini is enabled):

- `LLM Fit Score` — Gemini 0–100 fit score
- `LLM Role Classification` — Strong Fit / Possible Fit / Weak Fit / Reject / Not Analyzed
- `LLM Role Type` — role category from Gemini
- `LLM Visa Risk` — Gemini visa assessment
- `LLM Eligibility Notes` — Gemini eligibility summary
- `LLM Strategic Summary` — one-sentence strategic rationale
- `LLM Reject Reason` — reason for weak/reject classification
- `LLM Confidence` — Gemini confidence score
- `Gemini Analyzed` — Yes / Cached / Fallback / No
- `Final Score` — weighted blend: 60% LLM + 40% rules (falls back to rules score when Gemini not used)

Preserved fields on rerun:

- `Jobs_Scored.Status`
- `Daily_Shortlist.My Decision`, `Daily_Shortlist.Referral Sent?`, `Daily_Shortlist.Applied?`, `Daily_Shortlist.Notes`
- `Referral_Targets.Connection Status`, `Referral_Targets.Referral Status`, `Referral_Targets.Follow-up Date`, `Referral_Targets.Notes`
- `Employee_Targets.Connection Status`, `Employee_Targets.Referral Status`, `Employee_Targets.Follow-up Date`, `Employee_Targets.Notes`
- `Resume_Tailoring.Resume Version`, `Resume_Tailoring.Notes`

The script does not auto-apply, auto-message, or scrape LinkedIn profiles unless employee discovery is explicitly enabled.

## LLM Response Cache

Vertex AI responses are cached locally at `cache/gemini_cache.json` keyed by a SHA-256 hash of `Company + Role + Job URL + Description`. Cache hits skip live Vertex AI calls and are logged as `Gemini Analyzed=Cached`. Delete the file to force re-analysis.

## Run

```bash
python main.py
```

The script logs:

- run number and LinkedIn throttle decision
- active target companies loaded from `Target_Companies`
- actor runs, item counts fetched, normalized job counts
- Gemini cost summary (calls made, cache hits, skipped, not analyzed)
- rows written per tab
- end-of-run summary with job source breakdown and shortlist count
