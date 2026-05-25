from __future__ import annotations

import hashlib
import re
from datetime import datetime
from urllib.parse import urlparse
from typing import Any

import pandas as pd


COMPANY_CORRECTIONS = {
    "mongodb": "MongoDB",
    "togetherai": "Together AI",
    "distyl": "Distyl AI",
    "norm ai": "Norm AI",
    "rdccareers": "Realtor.com",
    "go cloudforce": "Cloudforce",
    "thinkahead": "AHEAD",
    "bigly labs": "Bigly Labs",
}

ROLE_PREFIX_PATTERNS = [
    r"^job application for\s+",
    r"^careers?\s*[-:]\s*",
    r"^apply for\s+",
    r"^opening:\s*",
]

COMPANY_NOISE_PATTERNS = [
    r"^x,\s*",
    r"^jobs?\s+at\s+",
    r"\bcareers?\b",
    r"\bjob application\b",
]


def normalize_jobs(items: list[dict[str, Any]]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []

    for item in items:
        normalized_rows = _normalize_single_job(item)
        rows.extend(normalized_rows)

    if not rows:
        return []

    frame = pd.DataFrame(rows)
    frame["_dedupe_key"] = (
        frame["Company"].fillna("").str.lower().str.strip()
        + "||"
        + frame["Role"].fillna("").str.lower().str.strip()
        + "||"
        + frame["Job URL"].fillna("").str.lower().str.strip()
    )
    frame = frame.drop_duplicates(subset=["_dedupe_key"], keep="first").drop(columns=["_dedupe_key"])
    frame = frame.sort_values(by=["Company", "Role", "Posted Date", "Job ID"], ascending=True)
    return frame.fillna("").to_dict(orient="records")


def normalize_employees(
    items: list[dict[str, Any]],
    shortlist_job_map: dict[str, dict[str, str]],
    max_per_company: int = 5,
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for item in items:
        company = _pick_text(item, "companyName", "company", "organization", "target")
        name = _pick_text(item, "fullName", "name", "employeeName")
        title = _pick_text(item, "title", "headline", "jobTitle", "position")
        linkedin_url = _pick_text(item, "linkedinUrl", "profileUrl", "url")

        if not company or not name:
            continue

        shortlist_job = shortlist_job_map.get(company.lower().strip(), {})
        role = shortlist_job.get("Role", "")
        target_type = classify_employee_target_type(title)

        rows.append(
            {
                "Company": company,
                "Role": role,
                "Person Name": name,
                "Title": title or "Unknown",
                "LinkedIn URL": linkedin_url,
                "Target Type": target_type,
                "Match Reason": _match_reason(title, target_type),
                "Priority": _priority_for_target(target_type),
                "Message Draft": "",
                "Connection Status": "Not Started",
                "Referral Status": "Not Started",
                "Follow-up Date": "",
                "Notes": "",
                "Last Updated": "",
            }
        )

    if not rows:
        return []

    frame = pd.DataFrame(rows)

    # Deduplicate primarily by LinkedIn URL; fall back to company+name
    frame["_dedupe_key"] = frame["LinkedIn URL"].fillna("").str.lower().str.strip()
    no_url_mask = frame["_dedupe_key"] == ""
    frame.loc[no_url_mask, "_dedupe_key"] = (
        frame.loc[no_url_mask, "Company"].fillna("").str.lower().str.strip()
        + "||"
        + frame.loc[no_url_mask, "Person Name"].fillna("").str.lower().str.strip()
    )
    frame = frame.drop_duplicates(subset=["_dedupe_key"], keep="first").drop(columns=["_dedupe_key"])

    # Sort by company then priority (1 = highest value) before capping
    frame["_pri"] = pd.to_numeric(frame["Priority"], errors="coerce").fillna(9)
    frame = frame.sort_values(["Company", "_pri"]).drop(columns=["_pri"])

    # Cap profiles per company
    frame["_rank"] = frame.groupby("Company").cumcount()
    frame = frame[frame["_rank"] < max_per_company].drop(columns=["_rank"])

    return frame.fillna("").to_dict(orient="records")


def job_key_from_row(row: dict[str, str]) -> str:
    return _build_key(row.get("Company", ""), row.get("Role", ""), row.get("Job URL", ""))


def employee_key_from_row(row: dict[str, str]) -> str:
    linkedin_url = (row.get("LinkedIn URL") or "").strip().lower()
    if linkedin_url:
        return linkedin_url
    return _build_key(row.get("Company", ""), row.get("Person Name", ""))


def _normalize_single_job(item: dict[str, Any]) -> list[dict[str, str]]:
    if item.get("organicResults"):
        return _normalize_google_search_payload(item)

    role = _pick_text(item, "title", "jobTitle", "position", "role")
    company = _pick_text(item, "companyName", "company", "companyNameFromQuery", "organization")
    location = _pick_text(item, "location", "jobLocation", "formattedLocation", "city")
    job_url = _pick_text(item, "jobUrl", "url", "link", "applyUrl", "vacancyUrl")
    description = _pick_text(item, "description", "jobDescription", "snippet", "text")
    posted_date = _pick_text(item, "postedAt", "postedDate", "datePosted", "createdAt")
    source = _infer_source(item)
    source_actor = _infer_source_actor(item)

    if not role or not company:
        title = _pick_text(item, "title")
        if title and _looks_like_google_job_result(item):
            company, role = _split_google_title(title)
            job_url = job_url or _pick_text(item, "organicUrl", "displayedUrl")
            description = description or _pick_text(item, "description", "snippet")
            location = location or "Unknown"

    if not role or not company:
        return []

    description = _strip_html(description)
    job_url = _clean_url(job_url)
    posted_date = _normalize_date(posted_date)
    company = _normalize_company_name(company)
    role = _clean_role_title(role)
    job_id = _pick_text(item, "id", "jobId") or _derived_job_id(company, role, job_url)

    return [
        {
            "Job ID": job_id,
            "Company": company,
            "Role": role,
            "Location": location or "Unknown",
            "Job URL": job_url,
            "Description": description,
            "Source": source,
            "Source Actor": source_actor,
            "Posted Date": posted_date,
            "Date Added": datetime.now().date().isoformat(),
        }
    ]


def _normalize_google_search_payload(item: dict[str, Any]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    organic_results = item.get("organicResults") or []
    query_term = _flatten_value(item.get("searchQuery", {}).get("term"))

    for result in organic_results:
        title = _pick_text(result, "title")
        description = _pick_text(result, "description")
        job_url = _pick_text(result, "url")
        posted_date = _pick_text(result, "date")
        role, company = _parse_google_result_title(title, job_url)
        if not role or not company:
            continue

        rows.append(
            {
                "Job ID": _derived_job_id(company, role, job_url),
                "Company": company,
                "Role": role,
                "Location": _infer_location_from_text(description),
                "Job URL": job_url,
                "Description": description,
                "Source": "Google Search",
                "Source Actor": "Google Search Results Scraper",
                "Posted Date": _normalize_date(posted_date),
                "Date Added": datetime.now().date().isoformat(),
            }
        )

    return rows


def _infer_source(item: dict[str, Any]) -> str:
    source = _pick_text(item, "source", "sourceName", "engine")
    if source:
        return source
    url = _pick_text(item, "url", "jobUrl", "organicUrl")
    if "linkedin.com" in url:
        return "LinkedIn"
    if url:
        return "Google Search"
    return "Apify"


def _infer_source_actor(item: dict[str, Any]) -> str:
    source_actor = _pick_text(item, "sourceActor")
    if source_actor:
        return source_actor
    source = _infer_source(item)
    if source == "LinkedIn":
        return "LinkedIn Jobs Scraper"
    if source == "Google Search":
        return "Google Search Results Scraper"
    return "Apify Actor"


_TARGET_PRIORITY: dict[str, str] = {
    "Recruiter / Talent Acquisition": "1",
    "Hiring Manager": "2",
    "Technical Peer": "3",
    "Ex-AWS": "3",
    "Cloud/AI Adjacent": "4",
    "Other": "5",
}


def classify_employee_target_type(title: str) -> str:
    lower = (title or "").lower()
    if any(kw in lower for kw in ("recruiter", "talent acquisition", "sourcer", "recruiting")):
        return "Recruiter / Talent Acquisition"
    if "hiring manager" in lower or (
        any(kw in lower for kw in ("manager", "director", "head of", "vp ", "vice president"))
        and any(kw in lower for kw in ("engineer", "architect", "product", "cloud", "ai", "technical", "solution", "platform"))
    ):
        return "Hiring Manager"
    if any(kw in lower for kw in ("solutions architect", "cloud architect", "customer engineer", "solutions engineer")):
        return "Technical Peer"
    if any(kw in lower for kw in ("ex-aws", "former aws", "ex amazon web services", "previously at aws")):
        return "Ex-AWS"
    if any(kw in lower for kw in ("aws", "cloud", "genai", "generative ai", "machine learning", "platform")):
        return "Cloud/AI Adjacent"
    return "Other"


def _priority_for_target(target_type: str) -> str:
    return _TARGET_PRIORITY.get(target_type, "5")


def _match_reason(title: str, target_type: str) -> str:
    if not title or title == "Unknown":
        return f"{target_type} — no title available."
    return f"{target_type}; title: {title}"


def _pick_text(payload: dict[str, Any], *candidates: str) -> str:
    for candidate in candidates:
        value = payload.get(candidate)
        flattened = _flatten_value(value)
        if flattened:
            return flattened
    return ""


def _flatten_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, dict):
        for candidate in ("name", "title", "label", "value", "text", "url"):
            nested = value.get(candidate)
            flattened = _flatten_value(nested)
            if flattened:
                return flattened
        return ""
    if isinstance(value, list):
        values = [_flatten_value(item) for item in value]
        return ", ".join(item for item in values if item)
    return str(value).strip()


def _strip_html(text: str) -> str:
    if not text:
        return ""
    without_tags = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", without_tags).strip()


def _normalize_date(value: str) -> str:
    value = (value or "").strip()
    if not value:
        return ""
    return value


def _clean_url(url: str) -> str:
    return (url or "").strip()


def _derived_job_id(company: str, role: str, url: str) -> str:
    raw = f"{company}|{role}|{url}"
    return hashlib.md5(raw.encode("utf-8")).hexdigest()[:12]


def _build_key(*parts: str) -> str:
    return "||".join(_normalize_key_text(part) for part in parts)


def _normalize_key_text(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip().lower()


def _looks_like_google_job_result(item: dict[str, Any]) -> bool:
    url = _pick_text(item, "url", "organicUrl", "jobUrl")
    return bool(url) and any(host in url for host in ("greenhouse", "lever", "ashby"))


def _split_google_title(title: str) -> tuple[str, str]:
    for separator in (" - ", " | ", " at "):
        if separator in title:
            left, right = title.split(separator, 1)
            role = left.strip()
            company = right.strip()
            if role and company:
                return company, role
    return "", title.strip()


def _parse_google_result_title(title: str, job_url: str) -> tuple[str, str]:
    title = _clean_role_title(title)
    if not title:
        return "", ""

    for marker in (" at ", " @ "):
        if marker in title:
            role, company = title.split(marker, 1)
            return _clean_role_title(role), _normalize_company_name(company.strip().strip("."))

    if title.lower().startswith("job application for ") and " at " in title.lower():
        lowered = title.lower()
        idx = lowered.rfind(" at ")
        role = title[len("Job Application for ") : idx].strip()
        company = title[idx + 4 :].strip().strip(".")
        return _clean_role_title(role), _normalize_company_name(company)

    if " - " in title:
        left, right = title.split(" - ", 1)
        if _looks_like_company_name(left):
            return _clean_role_title(right), _normalize_company_name(left)
        return _clean_role_title(left), _normalize_company_name(right)

    company = _company_from_job_url(job_url)
    if company:
        if _looks_like_generic_title(title):
            return "", ""
        return _clean_role_title(title), _normalize_company_name(company)

    return "", ""


def _company_from_job_url(job_url: str) -> str:
    parsed = urlparse(job_url or "")
    path_parts = [part for part in parsed.path.split("/") if part]
    if not path_parts:
        return ""

    company_slug = path_parts[0]
    if company_slug == "jobs" and len(path_parts) > 1:
        company_slug = path_parts[1]
    return _slug_to_name(company_slug)


def _slug_to_name(slug: str) -> str:
    parts = re.split(r"[-_]+", slug)
    return _normalize_company_name(" ".join(part.capitalize() for part in parts if part))


def _looks_like_company_name(text: str) -> bool:
    words = text.strip().split()
    return 0 < len(words) <= 4 and any(char.isupper() for char in text)


def _looks_like_generic_title(text: str) -> bool:
    lower = text.lower()
    return any(
        phrase in lower
        for phrase in (
            "open positions",
            "find your role",
            "careers",
            "jobs at",
        )
    )


def _infer_location_from_text(text: str) -> str:
    cleaned = (text or "").lower()
    if "remote" in cleaned:
        return "Remote"
    if "hybrid" in cleaned:
        return "Hybrid"
    if "on-site" in cleaned or "onsite" in cleaned:
        return "On-site"
    return "Unknown"


def _normalize_company_name(company: str) -> str:
    cleaned = (company or "").strip()
    for pattern in COMPANY_NOISE_PATTERNS:
        cleaned = re.sub(pattern, " ", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" -,:.;")
    cleaned = cleaned.title()
    return COMPANY_CORRECTIONS.get(cleaned.lower(), cleaned)


def _clean_role_title(role: str) -> str:
    cleaned = (role or "").strip()
    for pattern in ROLE_PREFIX_PATTERNS:
        cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\.\.\.+", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" -,:.;")
    return cleaned
