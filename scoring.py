from __future__ import annotations

from datetime import datetime, timezone


BOOST_KEYWORDS = {
    "aws": 10,
    "azure": 8,
    "gcp": 8,
    "cloud architecture": 10,
    "genai": 10,
    "generative ai": 10,
    "ai/ml": 8,
    "machine learning": 7,
    "bedrock": 9,
    "customer-facing": 8,
    "customer facing": 8,
    "solution design": 8,
    "poc": 7,
    "proof of concept": 7,
    "deployment": 5,
    "integrations": 6,
    "integration": 6,
    "enterprise architecture": 8,
    "technical consulting": 8,
    "pre-sales": 8,
    "presales": 8,
    "customer engineer": 10,
    "solutions engineer": 10,
    "forward deployed engineer": 12,
    "technical gtm": 10,
    "platform": 5,
    "startup": 4,
    "healthcare": 3,
    "life sciences": 3,
    "hcls": 4,
}

PENALTY_KEYWORDS = {
    "salesforce": -24,
    "sap": -24,
    "workday": -24,
    "servicenow": -24,
    "oracle erp": -26,
    "dynamics": -22,
    "hcm": -18,
    "crm admin": -24,
    "backend engineer": -22,
    "backend software engineer": -22,
    "devops administrator": -24,
    "devops admin": -24,
    "technical support": -22,
    "customer support": -22,
    "network engineer": -20,
    "network security": -18,
    "security engineer": -18,
    "soc analyst": -18,
    "business systems": -18,
}

ROLE_PATTERNS = {
    "Solutions Architect": ["solutions architect", "cloud solutions architect"],
    "GenAI Solutions Architect": ["genai solutions architect", "ai solutions architect"],
    "Customer Engineer": ["customer engineer"],
    "Solutions Engineer": ["solutions engineer", "technical solutions engineer"],
    "Platform Architect": ["platform architect"],
    "Forward Deployed Engineer": [
        "forward deployed engineer",
        "forward deployed solutions engineer",
    ],
    "Technical GTM Engineer": ["technical gtm engineer"],
    "Partner Solutions Architect": ["partner solutions architect"],
}

STRATEGIC_COMPANY_RULES = {
    "Anthropic": (25, "AI-first company with strong applied AI and partner-architecture relevance."),
    "Databricks": (24, "Top-tier data and AI platform with strong cloud and field relevance."),
    "Snowflake": (22, "Cloud data platform with strong customer-facing architecture relevance."),
    "MongoDB": (21, "Developer-first data platform with strong architecture relevance."),
    "OpenAI": (25, "Core AI ecosystem company with direct GenAI strategic relevance."),
    "Together AI": (22, "GenAI infrastructure company aligned to platform architecture work."),
    "Cohere": (22, "Modern enterprise AI platform with direct GenAI relevance."),
    "Modal": (20, "Developer cloud infrastructure and AI execution platform."),
    "Datadog": (18, "Cloud-native platform with solid field and partner relevance."),
}

STRATEGIC_KEYWORDS = {
    "ai": (8, "AI-first or GenAI-oriented company."),
    "cloud": (7, "Cloud infrastructure or cloud platform positioning."),
    "data": (6, "Data and analytics platform relevance."),
    "developer": (6, "Developer platform positioning."),
    "health": (5, "Healthcare tech relevance."),
    "analytics": (6, "Analytics platform relevance."),
    "platform": (5, "Platform-oriented company profile."),
    "partner": (5, "Cloud partner ecosystem relevance."),
    "startup": (5, "High-growth startup profile."),
}

NEGATIVE_COMPANY_KEYWORDS = {
    "staffing": (-18, "Staffing-oriented company."),
    "consulting": (-8, "Generic consulting vendor profile."),
    "outsourcing": (-16, "Outsourcing-heavy company profile."),
    "workday": (-20, "ERP/HCM-centric company alignment."),
    "sap": (-20, "ERP-centric company alignment."),
    "salesforce": (-18, "Salesforce-centric company alignment."),
}


# --- Career-stage filtering constants ---

_SENIORITY_HIGH_TITLE_WORDS = frozenset([
    "principal", "staff", "director", "fellow", "distinguished",
])
_SENIORITY_HIGH_TITLE_PHRASES = ("vp ", "vp,", "vp/", "vice president", "head of")
_SENIORITY_HIGH_YEAR_PHRASES = (
    "10+ years", "10+ year", "10 or more years", "12+ years", "15+ years",
    "minimum of 10", "minimum 10 years", "at least 10 years",
)
_SENIORITY_MEDIUM_YEAR_PHRASES = (
    "8+ years", "8 or more years", "minimum 8 years", "at least 8 years",
)

_TARGET_ROLE_PATTERNS = (
    "solutions architect",
    "customer engineer",
    "solutions engineer",
    "genai solutions",
    "ai solutions",
    "technical gtm",
    "forward deployed",
    "platform architect",
)

_HARD_TRANSITION_PATTERNS = (
    "site reliability engineer",
    "platform reliability",
    " sre ",
    "sre/",
    "/sre",
    "infrastructure engineer",
    "platform engineer",
    "devops engineer",
)
_MEDIUM_TRANSITION_PATTERNS = (
    "kubernetes",
    "k8s",
    "platform engineering",
)

_GEO_HIGH_KEYWORDS = (
    "united kingdom",
    "london",
    "manchester",
    "edinburgh",
    "bristol",
    "leeds",
    "birmingham",
    "canada",
    "toronto",
    "vancouver",
    "montreal",
    "ottawa",
    "calgary",
    "australia",
    "sydney",
    "melbourne",
    "brisbane",
    "germany",
    "berlin",
    "munich",
    "frankfurt",
    "ireland",
    "dublin",
    "netherlands",
    "amsterdam",
)

# --- Global Mobility scoring ---

GLOBAL_MOBILITY_COMPANY_SCORES: dict[str, int] = {
    # Big tech — tier 1 (25): global footprint, strong immigration history
    "Google": 25,
    "Amazon": 25,
    "AWS": 25,
    "Microsoft": 25,
    "Meta": 25,
    "Apple": 25,
    # Cloud/AI leaders — tier 1 (23-25): distributed-first, active H1B/Skilled-Worker sponsors
    "Databricks": 25,
    "Snowflake": 25,
    "Cloudflare": 25,
    "Stripe": 25,
    "GitLab": 25,
    "Elastic": 24,
    "NVIDIA": 25,
    "MongoDB": 24,
    "Grafana Labs": 24,
    "Datadog": 24,
    # Strong multinationals — tier 2 (20-23)
    "Anthropic": 23,
    "OpenAI": 23,
    "HashiCorp": 23,
    "Confluent": 23,
    "Cohere": 22,
    "Scale AI": 22,
    "Palo Alto Networks": 22,
    "CrowdStrike": 22,
    "Okta": 22,
    "Twilio": 22,
    "Figma": 22,
    "VMware": 22,
    "Cisco": 22,
    "Mistral": 22,
    "Weaviate": 21,
    "Pulumi": 21,
    "Fivetran": 21,
    "dbt Labs": 21,
    "Aiven": 21,
    "Vercel": 20,
    "Together AI": 20,
    "Notion": 20,
    "Airbyte": 20,
    "Temporal": 20,
    "Coreweave": 20,
    "Pinecone": 20,
    # Scale-ups with partial global presence — tier 3 (14-18)
    "Modal": 18,
    "Thought Machine": 18,
    "Linear": 18,
    "Airtable": 18,
    "Wasabi": 15,
    "Caylent": 14,
}

_MOBILITY_POSITIVE_SIGNALS = (
    "global team",
    "globally distributed",
    "global engineering",
    "distributed workforce",
    "distributed team",
    "internal transfer",
    "internal mobility",
    "relocation support",
    "offices in",
    "multinational",
    "international team",
    "work from anywhere",
    "fully remote",
)

_MOBILITY_NEGATIVE_SIGNALS = (
    "right to work in the uk",
    "must have uk work authorization",
    "uk work authorization required",
    "must be based in the uk",
    "local candidates only",
    "candidates must reside",
    "no visa sponsorship",
    "unable to sponsor",
    "will not sponsor",
    "must be authorized to work without",
)

SOURCE_QUALITY_SCORES: dict[str, int] = {
    "greenhouse.io": 18,
    "boards.greenhouse.io": 18,
    "lever.co": 18,
    "ashbyhq.com": 18,
    "jobs.ashbyhq.com": 18,
    "jobs.ycombinator.com": 18,
    "wellfound.com": 16,
    "otta.com": 16,
    "workable.com": 14,
    "smartrecruiters.com": 14,
    "teamtailor.com": 12,
    "bamboohr.com": 12,
    "linkedin.com": 10,
    "indeed.com": 8,
    "ziprecruiter.com": 6,
    "workday.com": 6,
}


def _seniority_risk(role: str, description: str) -> str:
    role_lower = role.lower()
    desc_lower = description.lower()
    role_words = set(role_lower.replace(",", " ").replace("/", " ").replace("-", " ").split())
    high_title = bool(
        role_words & _SENIORITY_HIGH_TITLE_WORDS
        or any(p in role_lower for p in _SENIORITY_HIGH_TITLE_PHRASES)
    )
    if high_title or any(p in desc_lower for p in _SENIORITY_HIGH_YEAR_PHRASES):
        return "High"
    if any(p in desc_lower for p in _SENIORITY_MEDIUM_YEAR_PHRASES):
        return "Medium"
    return "Low"


def _transition_difficulty(role: str, description: str) -> str:
    combined = f"{role} {description}".lower()
    if any(p in combined for p in _HARD_TRANSITION_PATTERNS):
        return "Hard"
    medium_hits = sum(1 for p in _MEDIUM_TRANSITION_PATTERNS if p in combined)
    if medium_hits >= 2 or (medium_hits >= 1 and "architect" not in combined):
        return "Medium"
    return "Easy"


def _geo_quality(location: str, description: str) -> str:
    loc = (location or "").lower()
    loc_padded = f" {loc} "
    desc = (description or "").lower()
    is_uk = " uk " in loc_padded or ", uk" in loc or "(uk)" in loc or "united kingdom" in loc
    if is_uk or any(kw in loc for kw in _GEO_HIGH_KEYWORDS):
        return "High"
    sponsorship = any(p in desc for p in (
        "visa sponsorship", "sponsorship available", "will sponsor",
        "skilled worker visa", "relocation support", "visa support available",
    ))
    if sponsorship or "remote" in loc:
        return "Medium"
    return "Low"


def _global_mobility_score(company: str, description: str, location: str) -> int:
    company_clean = (company or "").strip()
    if company_clean in GLOBAL_MOBILITY_COMPANY_SCORES:
        return GLOBAL_MOBILITY_COMPANY_SCORES[company_clean]

    desc_lower = (description or "").lower()
    loc_lower = (location or "").lower()
    combined = f"{desc_lower} {loc_lower}"

    score = 5  # base for unknown companies

    pos_hits = sum(1 for p in _MOBILITY_POSITIVE_SIGNALS if p in combined)
    score += min(pos_hits * 2, 8)

    if "remote" in combined:
        score += 2
    if any(p in desc_lower for p in (
        "visa sponsorship", "sponsorship available", "will sponsor",
        "skilled worker visa", "relocation support",
    )):
        score += 3

    # Multinational dual-presence bonus: US + EU/Canada/AU signals in same posting
    has_us = any(kw in combined for kw in (
        "united states", "san francisco", "new york", "seattle",
        "palo alto", "mountain view", "us headquarters",
    ))
    has_intl = any(kw in combined for kw in (
        "canada", "toronto", "united kingdom", "london",
        "europe", "germany", "berlin", "australia", "sydney", "netherlands",
    ))
    if has_us and has_intl:
        score += 5

    neg_hits = sum(1 for p in _MOBILITY_NEGATIVE_SIGNALS if p in combined)
    score -= min(neg_hits * 3, 9)

    return max(0, min(25, score))


def _realistic_match_score(
    role: str, description: str, seniority_risk: str
) -> int:
    combined = f"{role} {description}".lower()
    score = 50

    if any(p in combined for p in _TARGET_ROLE_PATTERNS):
        score += 20
    if "customer-facing" in combined or "customer facing" in combined:
        score += 8
    if "genai" in combined or "generative ai" in combined or "ai solutions" in combined:
        score += 8
    if "forward deployed" in combined or "technical gtm" in combined:
        score += 5
    if any(p in description.lower() for p in (
        "3+ years", "4+ years", "5+ years", "6+ years", "7+ years",
        "3-7 years", "4-8 years",
    )):
        score += 5

    if seniority_risk == "High":
        score -= 30
    elif seniority_risk == "Medium":
        score -= 10

    role_words = set(role.lower().replace(",", " ").replace("/", " ").replace("-", " ").split())
    if role_words & _SENIORITY_HIGH_TITLE_WORDS:
        score -= 10

    if any(p in combined for p in _HARD_TRANSITION_PATTERNS):
        score -= 15
    if ("kubernetes" in combined or "k8s" in combined) and "architect" not in combined:
        score -= 10

    return max(0, min(100, score))


def _source_quality_score(job_url: str) -> int:
    url_lower = (job_url or "").lower()
    for domain, score in SOURCE_QUALITY_SCORES.items():
        if domain in url_lower:
            return score
    return 8


def score_jobs(
    jobs: list[dict[str, str]],
    target_companies: set[str] | None = None,
) -> list[dict[str, str]]:
    tc = {c.strip().lower() for c in (target_companies or set())}
    return [_score_single_job(job, tc) for job in jobs]


def _score_single_job(job: dict[str, str], target_companies: set[str] | None = None) -> dict[str, str]:
    role = job["Role"]
    company = job["Company"]
    description = job.get("Description", "")
    combined = f"{role} {description}".lower()

    boost_hits = [keyword for keyword in BOOST_KEYWORDS if keyword in combined]
    penalty_hits = [keyword for keyword in PENALTY_KEYWORDS if keyword in combined]

    score = 35
    score += sum(BOOST_KEYWORDS[keyword] for keyword in boost_hits)
    score += _role_bonus(role.lower())
    score += _customer_scope_bonus(combined)
    score += _startup_bonus(combined)
    score += _security_network_penalty(combined)
    score += sum(PENALTY_KEYWORDS[keyword] for keyword in penalty_hits)
    work_auth_signal = _work_authorization_signal(combined)
    sponsorship_mentioned = _sponsorship_mentioned(combined)
    citizenship_restriction = _citizenship_restriction(combined)
    clearance_required = _clearance_required(combined)
    visa_risk = _visa_risk(
        combined=combined,
        sponsorship_mentioned=sponsorship_mentioned,
        citizenship_restriction=citizenship_restriction,
        clearance_required=clearance_required,
    )
    score += _visa_score_adjustment(sponsorship_mentioned, visa_risk)
    score = max(0, min(score, 100))
    strategic_company_score, strategic_reason = _strategic_company_score(company, combined)

    role_type = _classify_role_type(role.lower())
    priority = _priority(score)
    if visa_risk == "Restricted":
        priority = "Low"

    why_fit = _why_fit(role_type, boost_hits, combined)
    why_reject = _why_reject(penalty_hits, priority, visa_risk)
    resume_angle = _resume_angle(combined, role_type)
    eligibility_notes = _eligibility_notes(
        work_auth_signal=work_auth_signal,
        sponsorship_mentioned=sponsorship_mentioned,
        citizenship_restriction=citizenship_restriction,
        clearance_required=clearance_required,
        combined=combined,
    )
    apply_recommendation = _apply_recommendation(priority, visa_risk)
    source_quality = _source_quality_score(job.get("Job URL", ""))
    seniority_risk = _seniority_risk(role, description)
    transition_difficulty = _transition_difficulty(role, description)
    geo_quality = _geo_quality(job.get("Location", ""), description)
    realistic_match_score = _realistic_match_score(role, description, seniority_risk)
    global_mobility_score = _global_mobility_score(company, description, job.get("Location", ""))

    # Boost strategic score for user-managed target companies
    if target_companies and company.strip().lower() in target_companies:
        strategic_company_score = min(25, strategic_company_score + 5)
        if not strategic_reason or strategic_reason == "No clear strategic company edge detected.":
            strategic_reason = "User-defined target company."

    return {
        "Job ID": job["Job ID"],
        "Company": job["Company"],
        "Role": job["Role"],
        "Location": job["Location"],
        "Job URL": job["Job URL"],
        "Description": job.get("Description", ""),
        "Source": job["Source"],
        "Posted Date": job["Posted Date"],
        "Fit Score": str(score),
        "Priority": priority,
        "Role Type": role_type,
        "Strategic Company Score": str(strategic_company_score),
        "Strategic Reason": strategic_reason,
        "Why Fit": why_fit,
        "Why Reject": why_reject,
        "Work Authorization Signal": work_auth_signal,
        "Visa Risk": visa_risk,
        "Sponsorship Mentioned": sponsorship_mentioned,
        "Citizenship Restriction": citizenship_restriction,
        "Clearance Required": clearance_required,
        "Eligibility Notes": eligibility_notes,
        "Apply Recommendation": apply_recommendation,
        "Resume Angle": resume_angle,
        "Source Quality Score": str(source_quality),
        "Realistic Match Score": str(realistic_match_score),
        "Seniority Risk": seniority_risk,
        "Transition Difficulty": transition_difficulty,
        "Geo Quality": geo_quality,
        "Global Mobility Score": str(global_mobility_score),
        "Status": "New",
        "Last Updated": datetime.now().isoformat(timespec="seconds"),
    }


def _priority(score: int) -> str:
    if score >= 75:
        return "High"
    if score >= 50:
        return "Medium"
    return "Low"


def _classify_role_type(role: str) -> str:
    for role_type, patterns in ROLE_PATTERNS.items():
        if any(pattern in role for pattern in patterns):
            return role_type
    return "Adjacent"


def _why_fit(role_type: str, boost_hits: list[str], combined: str) -> str:
    reasons: list[str] = []
    if role_type != "Adjacent":
        reasons.append(f"Target role match: {role_type}")
    if boost_hits:
        reasons.append("Keyword hits: " + ", ".join(boost_hits[:5]))
    if "customer" in combined or "stakeholder" in combined:
        reasons.append("Customer-facing scope present")
    if "cloudformation" in combined or "cdk" in combined:
        reasons.append("Infrastructure design tooling overlap")
    return "; ".join(reasons) or "Limited evidence of target architecture scope."


def _why_reject(penalty_hits: list[str], priority: str, visa_risk: str) -> str:
    reasons: list[str] = []
    if penalty_hits:
        reasons.append("Penalty keywords: " + ", ".join(penalty_hits[:5]))
    if visa_risk in {"High", "Restricted"}:
        reasons.append(f"Eligibility risk: {visa_risk}")
    if not reasons:
        return ""
    message = "Penalty keywords: " + ", ".join(penalty_hits[:5])
    if priority == "Low":
        return "; ".join(reasons)
    return "Watchouts despite fit: " + "; ".join(reasons)


def _resume_angle(combined: str, role_type: str) -> str:
    if "genai" in combined or "generative ai" in combined or "bedrock" in combined:
        return "Lead with AWS + GenAI architecture, Bedrock-oriented PoCs, and customer advisory work."
    if role_type in {"Solutions Engineer", "Customer Engineer", "Technical GTM Engineer"}:
        return "Lead with customer discovery, technical storytelling, demos, and solution design."
    if role_type in {"Solutions Architect", "Platform Architect", "Partner Solutions Architect"}:
        return "Lead with AWS architecture, modernization, CDK/CloudFormation, and stakeholder alignment."
    if "forward deployed" in combined:
        return "Lead with ambiguous problem solving, rapid PoCs, deployment ownership, and customer-facing execution."
    return "Lead with cloud architecture, PoCs, modernization, and customer-facing technical leadership."


def _role_bonus(role: str) -> int:
    if any("solutions architect" in role_part for role_part in [role]):
        return 22
    if any(
        pattern in role
        for pattern in (
            "cloud architect",
            "customer engineer",
            "solutions engineer",
            "platform architect",
            "forward deployed",
            "technical gtm",
            "partner solutions architect",
        )
    ):
        return 16
    return 0


def _customer_scope_bonus(combined: str) -> int:
    bonus = 0
    if "customer" in combined:
        bonus += 6
    if "stakeholder" in combined:
        bonus += 4
    if "solution design" in combined:
        bonus += 5
    return bonus


def _startup_bonus(combined: str) -> int:
    if "startup" in combined:
        return 3
    return 0


def _security_network_penalty(combined: str) -> int:
    if "cloud architecture" in combined:
        return 0
    penalty = 0
    if "security" in combined and "architect" not in combined:
        penalty -= 10
    if "network" in combined and "architect" not in combined:
        penalty -= 12
    return penalty


def _work_authorization_signal(combined: str) -> str:
    if any(
        phrase in combined
        for phrase in (
            "candidates must already have work authorization",
            "unrestricted work authorization required",
            "must be authorized to work without sponsorship",
            "must be authorized to work",
            "authorized to work in the",
            "work authorization",
            "eligible to work",
        )
    ):
        return "Authorization language present"
    if any(
        phrase in combined
        for phrase in (
            "uk visa sponsorship",
            "skilled worker visa sponsorship",
            "relocation support",
            "visa support available",
            "visa sponsorship",
            "sponsorship available",
            "will sponsor",
        )
    ):
        return "Sponsorship language present"
    return "Unknown"


def _sponsorship_mentioned(combined: str) -> str:
    if any(
        phrase in combined
        for phrase in (
            "no visa sponsorship",
            "no sponsorship",
            "unable to sponsor",
            "must be authorized to work without sponsorship",
            "will not sponsor now or in the future",
            "candidates must already have work authorization",
            "unrestricted work authorization required",
            "will not sponsor",
            "without sponsorship",
        )
    ):
        return "No"
    if any(
        phrase in combined
        for phrase in (
            "uk visa sponsorship",
            "skilled worker visa sponsorship",
            "relocation support",
            "visa support available",
            "visa sponsorship",
            "sponsorship available",
            "will sponsor",
        )
    ):
        return "Yes"
    return "Unknown"


def _citizenship_restriction(combined: str) -> str:
    if any(
        phrase in combined
        for phrase in (
            "u.s. citizenship required",
            "u.s. citizen",
            "us citizen",
            "green card required",
            "permanent resident required",
            "us person",
            "itar",
            "export control",
            "ear",
            "citizenship required",
            "must be a citizen",
        )
    ):
        return "Yes"
    return "No"


def _clearance_required(combined: str) -> str:
    if any(
        phrase in combined
        for phrase in (
            "public trust",
            "security clearance required",
            "security clearance",
            "active clearance",
            "top secret",
            "secret clearance",
            "ts/sc",
            "ts/sci",
        )
    ):
        return "Yes"
    return "No"


def _visa_risk(
    combined: str,
    sponsorship_mentioned: str,
    citizenship_restriction: str,
    clearance_required: str,
) -> str:
    if citizenship_restriction == "Yes" or clearance_required == "Yes":
        return "Restricted"
    if sponsorship_mentioned == "No":
        return "High"
    if sponsorship_mentioned == "Yes":
        return "Low"
    if any(
        phrase in combined
        for phrase in (
            "must be authorized to work",
            "authorized to work in the",
            "candidates must already have work authorization",
            "unrestricted work authorization required",
            "eligible to work",
        )
    ):
        return "Medium"
    return "Medium"


def _visa_score_adjustment(sponsorship_mentioned: str, visa_risk: str) -> int:
    adjustment = 0
    if sponsorship_mentioned == "Yes":
        adjustment += 10
    if visa_risk == "Medium":
        adjustment -= 5
    elif visa_risk == "High":
        adjustment -= 20
    elif visa_risk == "Restricted":
        adjustment -= 25
    return adjustment


def _eligibility_notes(
    work_auth_signal: str,
    sponsorship_mentioned: str,
    citizenship_restriction: str,
    clearance_required: str,
    combined: str,
) -> str:
    notes: list[str] = []
    if work_auth_signal != "Unknown":
        notes.append(work_auth_signal)
    if sponsorship_mentioned == "Yes":
        notes.append("Sponsorship appears available or discussed")
    elif sponsorship_mentioned == "No":
        notes.append("Posting appears to reject sponsorship")
    if citizenship_restriction == "Yes":
        notes.append("Citizenship, export-control, or permanent-residency restriction detected")
    if clearance_required == "Yes":
        notes.append("Security clearance requirement detected")
    if not notes and "remote" in combined:
        notes.append("No explicit eligibility blockers found in sampled text")
    return "; ".join(notes) or "No explicit eligibility signal detected."


def _apply_recommendation(priority: str, visa_risk: str) -> str:
    if visa_risk in {"High", "Restricted"} or priority == "Low":
        return "Avoid"
    if priority == "High":
        return "Apply"
    if priority == "Medium":
        if visa_risk == "Medium":
            return "Apply"
        return "Maybe"
    return "Avoid"


def _strategic_company_score(company: str, combined: str) -> tuple[int, str]:
    company_clean = (company or "").strip()
    if company_clean in STRATEGIC_COMPANY_RULES:
        return STRATEGIC_COMPANY_RULES[company_clean]

    lower = f"{company_clean} {combined}".lower()
    score = 0
    reasons: list[str] = []
    for keyword, (pts, reason) in STRATEGIC_KEYWORDS.items():
        if keyword in lower:
            score += pts
            reasons.append(reason)
    for keyword, (pts, reason) in NEGATIVE_COMPANY_KEYWORDS.items():
        if keyword in lower:
            score += pts
            reasons.append(reason)
    score = max(0, min(score, 25))
    return score, "; ".join(reasons[:2]) or "No clear strategic company edge detected."


def freshness_score(posted_date: str) -> int:
    dt = _parse_posted_date(posted_date)
    if dt is None:
        return 0
    age_days = (datetime.now(timezone.utc).date() - dt.date()).days
    if age_days <= 3:
        return 10
    if age_days <= 7:
        return 5
    if age_days > 30:
        return -15
    if age_days > 14:
        return -8
    return 0


def _parse_posted_date(value: str) -> datetime | None:
    text = (value or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
