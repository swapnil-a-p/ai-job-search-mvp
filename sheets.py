from __future__ import annotations

import re
from collections.abc import Callable

import gspread
from google.oauth2.service_account import Credentials
from gspread.exceptions import SpreadsheetNotFound, WorksheetNotFound

from config import AppConfig


SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

TAB_HEADERS = {
    "Jobs_Raw": [
        "Job ID",
        "Company",
        "Role",
        "Location",
        "Job URL",
        "Description",
        "Source",
        "Source Actor",
        "Posted Date",
        "Date Added",
    ],
    "Jobs_Scored": [
        "Job ID",
        "Company",
        "Role",
        "Location",
        "Job URL",
        "Source",
        "Posted Date",
        "Fit Score",
        "Source Quality Score",
        "LLM Fit Score",
        "LLM Role Classification",
        "LLM Role Type",
        "LLM Visa Risk",
        "LLM Eligibility Notes",
        "LLM Strategic Summary",
        "LLM Reject Reason",
        "LLM Confidence",
        "Gemini Analyzed",
        "Final Score",
        "Realistic Match Score",
        "Seniority Risk",
        "Transition Difficulty",
        "Geo Quality",
        "Global Mobility Score",
        "Priority",
        "Role Type",
        "Strategic Company Score",
        "Strategic Reason",
        "Why Fit",
        "Why Reject",
        "Work Authorization Signal",
        "Visa Risk",
        "Sponsorship Mentioned",
        "Citizenship Restriction",
        "Clearance Required",
        "Eligibility Notes",
        "Apply Recommendation",
        "Resume Angle",
        "Status",
        "Last Updated",
    ],
    "Referral_Targets": [
        "Company",
        "Role",
        "Target Type",
        "Suggested Search Query",
        "Search URL",
        "Message Draft",
        "Connection Status",
        "Referral Status",
        "Follow-up Date",
        "Notes",
    ],
    "Employee_Targets": [
        "Company",
        "Role",
        "Person Name",
        "Title",
        "LinkedIn URL",
        "Target Type",
        "Match Reason",
        "Priority",
        "Message Draft",
        "Connection Status",
        "Referral Status",
        "Follow-up Date",
        "Notes",
        "Last Updated",
    ],
    "Outreach_Tracker": [
        "Company",
        "Role",
        "Person Name",
        "LinkedIn URL",
        "Target Type",
        "Connection Status",
        "Message Sent",
        "Date Sent",
        "Follow-up Due",
        "Response",
        "Notes",
    ],
    "Resume_Tailoring": [
        "Company",
        "Role",
        "Job URL",
        "Fit Score",
        "Top 3 Matching Stories",
        "ATS Keywords",
        "Resume Angle",
        "Interview Positioning Notes",
        "Resume Version",
        "Notes",
    ],
    "Target_Companies": [
        "Company",
        "Priority",
        "Careers URL",
        "Notes",
        "Active",
        "Date Added",
    ],
    "Daily_Shortlist": [
        "Rank",
        "Company",
        "Role",
        "Location",
        "Job URL",
        "Fit Score",
        "Final Score",
        "Realistic Match Score",
        "Seniority Risk",
        "Transition Difficulty",
        "Geo Quality",
        "Global Mobility Score",
        "Priority",
        "Strategic Company Score",
        "Strategic Reason",
        "Visa Risk",
        "Apply Recommendation",
        "Why Fit",
        "Opportunity Summary",
        "Best Referral Search",
        "Message Draft",
        "Next Action",
        "My Decision",
        "Referral Sent?",
        "Applied?",
        "Notes",
    ],
}


class SheetsClient:
    def __init__(self, config: AppConfig) -> None:
        credentials = Credentials.from_service_account_info(
            config.service_account_info(), scopes=SCOPES
        )
        self.client = gspread.authorize(credentials)
        self.spreadsheet = self._open_or_create(config.google_sheet_name, config.google_sheet_url)

    def ensure_all_tabs(self) -> None:
        for tab_name, headers in TAB_HEADERS.items():
            self._ensure_worksheet(tab_name, headers)

    def read_rows(self, tab_name: str) -> list[dict[str, str]]:
        worksheet = self._ensure_worksheet(tab_name, TAB_HEADERS[tab_name])
        values = worksheet.get_all_values()
        if not values:
            return []

        headers = values[0]
        rows: list[dict[str, str]] = []
        for raw_row in values[1:]:
            if not any(cell.strip() for cell in raw_row):
                continue
            padded = raw_row + [""] * (len(headers) - len(raw_row))
            rows.append(dict(zip(headers, padded)))
        return rows

    def replace_rows(self, tab_name: str, rows: list[dict[str, str]]) -> int:
        headers = TAB_HEADERS[tab_name]
        worksheet = self._ensure_worksheet(tab_name, headers)
        matrix = [headers] + [[str(row.get(header, "")) for header in headers] for row in rows]

        required_rows = max(len(matrix), 2)
        required_cols = len(headers)
        if worksheet.row_count < required_rows or worksheet.col_count < required_cols:
            worksheet.resize(rows=required_rows, cols=required_cols)
        worksheet.clear()
        worksheet.update("A1", matrix)
        return len(rows)

    def _open_or_create(self, sheet_name: str, sheet_url: str | None) -> gspread.Spreadsheet:
        if sheet_url:
            return self.client.open_by_url(sheet_url)
        try:
            return self.client.open(sheet_name)
        except SpreadsheetNotFound:
            return self.client.create(sheet_name)

    def _ensure_worksheet(self, tab_name: str, headers: list[str]) -> gspread.Worksheet:
        try:
            worksheet = self.spreadsheet.worksheet(tab_name)
        except WorksheetNotFound:
            worksheet = self.spreadsheet.add_worksheet(title=tab_name, rows=1000, cols=len(headers))

        existing = worksheet.row_values(1)
        if existing != headers:
            worksheet.resize(rows=max(worksheet.row_count, 2), cols=len(headers))
            worksheet.update("A1", [headers])
        return worksheet


_AUTO_GENERATED_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T")
_PURE_NUMERIC_RE = re.compile(r"^\d+$")


def _looks_auto_generated(val: str) -> bool:
    """Return True if val looks like it was auto-populated rather than manually entered."""
    if not val:
        return True
    # Pure integer like "18", "100"
    if _PURE_NUMERIC_RE.match(val):
        return True
    # ISO datetime with time component (e.g. "2024-05-18T00:00:00")
    if _AUTO_GENERATED_DATE_RE.match(val):
        return True
    # Raw URLs should not end up in manual text fields
    if val.startswith("http"):
        return True
    return False


def preserve_fields(
    rows: list[dict[str, str]],
    existing_rows: list[dict[str, str]],
    key_func: Callable[[dict[str, str]], str],
    fields_to_preserve: list[str],
) -> list[dict[str, str]]:
    existing_map = {key_func(row): row for row in existing_rows}
    merged: list[dict[str, str]] = []

    for row in rows:
        prior = existing_map.get(key_func(row), {})
        updated = dict(row)
        for field in fields_to_preserve:
            prior_val = prior.get(field, "")
            if prior_val and not _looks_auto_generated(prior_val):
                # Preserve a real user-entered value
                updated[field] = prior_val
            else:
                # Ensure any auto-generated value that leaked into the current row is blanked
                if _looks_auto_generated(updated.get(field, "")):
                    updated[field] = ""
        merged.append(updated)

    return merged
