#!/usr/bin/env python3
"""Write details for every merged pull request to a CSV file."""

import argparse
import csv
import json
import sys
from datetime import datetime
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


OWNER = "hingoman25"
REPOSITORY = "git-test-repo"
API_URL = f"https://api.github.com/repos/{OWNER}/{REPOSITORY}/pulls"
PER_PAGE = 100
CSV_COLUMNS = (
    "pull_request_number",
    "author",
    "author_profile_url",
    "merged_by",
    "merged_by_profile_url",
    "additions",
    "deletions",
    "created_at",
    "merged_at",
    "time_to_merge",
)


def fetch_json(url: str) -> Any:
    request = Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "merged-pull-request-fetcher",
        },
    )
    with urlopen(request, timeout=30) as response:
        return json.load(response)


def merged_pull_requests() -> list[dict[str, Any]]:
    """Fetch details for every merged pull request."""
    merged: list[dict[str, Any]] = []
    page = 1

    while True:
        pull_requests = fetch_json(
            f"{API_URL}?state=closed&per_page={PER_PAGE}&page={page}"
        )

        if not isinstance(pull_requests, list):
            raise ValueError("GitHub API returned an unexpected response")

        for pull_request in pull_requests:
            if not isinstance(pull_request, dict) or not pull_request.get("merged_at"):
                continue
            number = pull_request.get("number")
            if not isinstance(number, int):
                raise ValueError("GitHub API response did not include a valid PR number")
            details = fetch_json(f"{API_URL}/{number}")
            if not isinstance(details, dict):
                raise ValueError("GitHub API returned unexpected PR details")
            merged.append(details)

        if len(pull_requests) < PER_PAGE:
            return sorted(
                merged,
                key=lambda pull_request: pull_request.get("merged_at", ""),
                reverse=True,
            )
        page += 1


def account_values(account: Any) -> tuple[str, str]:
    if not isinstance(account, dict):
        return "", ""
    return str(account.get("login") or ""), str(account.get("html_url") or "")


def pull_request_row(pull_request: dict[str, Any]) -> list[Any]:
    created_at = pull_request.get("created_at")
    merged_at = pull_request.get("merged_at")
    if not isinstance(created_at, str) or not isinstance(merged_at, str):
        raise ValueError("GitHub API response did not include PR timestamps")

    merge_duration = datetime.fromisoformat(
        merged_at.replace("Z", "+00:00")
    ) - datetime.fromisoformat(created_at.replace("Z", "+00:00"))

    author, author_url = account_values(pull_request.get("user"))
    merged_by, merged_by_url = account_values(pull_request.get("merged_by"))
    return [
        pull_request.get("number", ""),
        author,
        author_url,
        merged_by,
        merged_by_url,
        pull_request.get("additions", ""),
        pull_request.get("deletions", ""),
        created_at,
        merged_at,
        str(merge_duration),
    ]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Export merged pull request details to CSV."
    )
    parser.add_argument(
        "--output",
        default="merged_pull_requests.csv",
        help="CSV output path (default: merged_pull_requests.csv)",
    )
    args = parser.parse_args()

    try:
        pull_requests = merged_pull_requests()
        rows = [pull_request_row(pull_request) for pull_request in pull_requests]
        with open(args.output, "w", encoding="utf-8", newline="") as csv_file:
            writer = csv.writer(csv_file)
            writer.writerow(CSV_COLUMNS)
            writer.writerows(rows)
    except (
        HTTPError,
        URLError,
        TimeoutError,
        json.JSONDecodeError,
        OSError,
        ValueError,
    ) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    print(f"Wrote {len(rows)} merged pull requests to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
