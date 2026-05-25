# Security Notes

This repository is intended to stay public-safe.

## Rules

- Never commit `.env`, service-account JSON files, or any exported cloud credential.
- Keep `GCP/` local-only and untracked.
- Treat Google Sheets URLs, actor tokens, and service-account material as secrets.
- Keep cache and runtime state out of git.

## Expected Local-Only Artifacts

- `.env`
- `GCP/*.json`
- `cache/`
- `state/`

## Before Sharing the Repo

1. Confirm `.env` and service-account files are untracked.
2. Rotate any credential that may have been exposed previously.
3. Verify that sample configuration files only contain placeholders.
4. Review git history if there is any chance credentials were ever committed.
