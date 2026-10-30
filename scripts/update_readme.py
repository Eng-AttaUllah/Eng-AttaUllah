"""Update the auto-generated activity block in README.md with live GitHub data.

Fetches the authenticated user's contribution calendar via the GraphQL API,
computes the current streak, and rewrites the <!-- README-AUTO-START --> ... END
block in README.md with today's date, current streak, and yearly contributions.
"""

import json
import os
import re
import urllib.request
from datetime import datetime, timedelta, timezone

README_PATH = "README.md"
START_MARKER = "<!-- README-AUTO-START -->"
END_MARKER = "<!-- README-AUTO-END -->"


def graphql(query, token):
    """Run a GitHub GraphQL query and return the parsed JSON payload."""
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": query}).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {token}",
            "User-Agent": "readme-updater-action",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        body = json.loads(resp.read().decode("utf-8"))
    if "errors" in body:
        raise RuntimeError(f"GraphQL errors: {body['errors']}")
    return body


def fetch_contribution_days(token, login):
    """Return a list of (date_str, contributionCount) for the past year."""
    query = """
    {
      user(login: "%s") {
        contributionsCollection {
          contributionCalendar {
            totalContributions
            weeks {
              contributionDays {
                date
                contributionCount
              }
            }
          }
        }
      }
    }
    """ % login
    data = graphql(query, token)
    calendar = data["data"]["user"]["contributionsCollection"]["contributionCalendar"]
    days = []
    for week in calendar["weeks"]:
        for day in week["contributionDays"]:
            days.append((day["date"], day["contributionCount"]))
    return days, calendar["totalContributions"]


def compute_streak(days):
    """Current streak: consecutive days (ending at the most recent active day)
    with at least one contribution."""
    daymap = {date: count for date, count in days}
    today = datetime.now(timezone.utc).date()

    # Walk back to find the most recent day that actually had a contribution.
    cursor = today
    while cursor.isoformat() not in daymap or daymap[cursor.isoformat()] == 0:
        cursor -= timedelta(days=1)

    # Count consecutive contributing days backwards from there.
    streak = 0
    while daymap.get(cursor.isoformat(), 0) > 0:
        streak += 1
        cursor -= timedelta(days=1)
    return streak


def build_block(date_str, streak, total):
    return (
        f"{START_MARKER}\n"
        f"🗓️ **Last updated:** {date_str} (UTC)\n"
        f"🔥 **Current streak:** {streak} day{'s' if streak != 1 else ''}\n"
        f"📝 **Contributions this year:** {total}\n"
        f"{END_MARKER}"
    )


def main():
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        raise RuntimeError("GITHUB_TOKEN environment variable is required")

    # The repo owner/login is the first part of GITHUB_REPOSITORY (owner/name).
    repo = os.getenv("GITHUB_REPOSITORY", "")
    login = repo.split("/")[0] if repo else "Eng-AttaUllah"

    with open(README_PATH, "r", encoding="utf-8") as f:
        content = f.read()

    days, total = fetch_contribution_days(token, login)
    streak = compute_streak(days)
    date_str = datetime.now(timezone.utc).strftime("%B %d, %Y")

    block = build_block(date_str, streak, total)
    new_content = re.sub(
        re.escape(START_MARKER) + r".*?" + re.escape(END_MARKER),
        block,
        content,
        flags=re.DOTALL,
    )

    if new_content == content:
        print("README content unchanged; nothing to write.")
        return

    with open(README_PATH, "w", encoding="utf-8") as f:
        f.write(new_content)

    print(f"Updated README: date={date_str}, streak={streak}, total_contributions={total}")


if __name__ == "__main__":
    main()
