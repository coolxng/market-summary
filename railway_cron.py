import base64
import datetime
import hashlib
import json
import os
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


REPOSITORY = os.environ.get("GITHUB_REPOSITORY", "coolxng/market-summary")
BRANCH = os.environ.get("GITHUB_BRANCH", "main")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL", "")
SITE_URL = os.environ.get("MARKET_SUMMARY_URL", "https://coolxng.github.io/market-summary/")
ARTIFACTS = (Path("report_snapshot.json"), Path("public/legacy-report.html"))


def require_environment():
    missing = []
    if not os.environ.get("ANTHROPIC_API_KEY"):
        missing.append("ANTHROPIC_API_KEY")
    if not GITHUB_TOKEN:
        missing.append("GITHUB_TOKEN")
    if missing:
        raise RuntimeError(f"Missing required Railway variables: {', '.join(missing)}")


def run(command):
    print(f"$ {' '.join(command)}", flush=True)
    subprocess.run(command, check=True)


def validate_artifacts():
    snapshot_path, html_path = ARTIFACTS
    if not snapshot_path.exists():
        raise RuntimeError(f"Missing generated artifact: {snapshot_path}")
    if not html_path.exists():
        raise RuntimeError(f"Missing generated artifact: {html_path}")

    snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    assert snapshot["report_type"] == "daily_market_close"
    assert snapshot["session_date"] > snapshot["previous_session_date"]
    assert snapshot["market_data"]["^GSPC"]["end_price"] > 0
    assert snapshot["market_data"]["^IXIC"]["end_price"] > 0
    assert snapshot["market_data"]["^TNX"]["end_price"] > 0
    assert snapshot["daily_market_breadth"]["positive_sector_share"] >= 0
    return snapshot


def api_request(method, path, payload=None):
    url = f"https://api.github.com/repos/{REPOSITORY}{path}"
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {GITHUB_TOKEN}",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "market-summary-railway-cron",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"GitHub API {method} {path} failed ({exc.code}): {body}") from exc


def git_blob_sha(content):
    header = f"blob {len(content)}\0".encode("utf-8")
    return hashlib.sha1(header + content).hexdigest()


def remote_blob_sha(path):
    encoded_path = urllib.parse.quote(path.as_posix(), safe="/")
    encoded_branch = urllib.parse.quote(BRANCH, safe="")
    result = api_request("GET", f"/contents/{encoded_path}?ref={encoded_branch}")
    return result["sha"]


def create_blob(content):
    result = api_request(
        "POST",
        "/git/blobs",
        {
            "content": base64.b64encode(content).decode("ascii"),
            "encoding": "base64",
        },
    )
    return result["sha"]


def commit_artifacts():
    local_contents = {path: path.read_bytes() for path in ARTIFACTS}
    changed = [
        path
        for path, content in local_contents.items()
        if git_blob_sha(content) != remote_blob_sha(path)
    ]

    if not changed:
        print("No new completed market session to commit.")
        return {"updated": False, "commit_sha": None}

    encoded_branch = urllib.parse.quote(BRANCH, safe="")
    ref = api_request("GET", f"/git/ref/heads/{encoded_branch}")
    parent_sha = ref["object"]["sha"]
    parent_commit = api_request("GET", f"/git/commits/{parent_sha}")
    base_tree_sha = parent_commit["tree"]["sha"]

    tree_entries = []
    for path in ARTIFACTS:
        blob_sha = create_blob(local_contents[path])
        tree_entries.append(
            {
                "path": path.as_posix(),
                "mode": "100644",
                "type": "blob",
                "sha": blob_sha,
            }
        )

    tree = api_request(
        "POST",
        "/git/trees",
        {
            "base_tree": base_tree_sha,
            "tree": tree_entries,
        },
    )
    commit = api_request(
        "POST",
        "/git/commits",
        {
            "message": "Automated Daily Market Summary update",
            "tree": tree["sha"],
            "parents": [parent_sha],
        },
    )
    api_request(
        "PATCH",
        f"/git/refs/heads/{encoded_branch}",
        {
            "sha": commit["sha"],
            "force": False,
        },
    )
    print(f"Committed generated artifacts to {REPOSITORY}@{BRANCH}: {commit['sha']}")
    return {"updated": True, "commit_sha": commit["sha"]}


def format_session_date(value):
    try:
        return datetime.date.fromisoformat(str(value)).strftime("%B %-d, %Y")
    except (TypeError, ValueError):
        return str(value)


def discord_post(payload):
    if not DISCORD_WEBHOOK_URL:
        print("DISCORD_WEBHOOK_URL is not set; skipping Discord notification.")
        return False

    request = urllib.request.Request(
        DISCORD_WEBHOOK_URL,
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
        headers={
            "Content-Type": "application/json",
            "User-Agent": "market-summary-railway-cron",
        },
    )

    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            response.read()
        print("Discord notification sent.")
        return True
    except Exception as exc:
        print(f"Warning: Discord notification failed: {exc}", file=sys.stderr)
        return False


def send_success_notification(snapshot, publish_result):
    session_date = format_session_date(snapshot.get("session_date", "Unknown"))
    updated = publish_result["updated"]
    commit_sha = publish_result["commit_sha"]

    if updated:
        title = "📈 Market Summary Updated"
        description = (
            f"**The Daily Tape** for **{session_date}** is live.\n\n"
            f"**[View Market Summary →]({SITE_URL})**"
        )
        color = 0x2ECC71
        status = "Published"
        commit_value = f"`{commit_sha[:7]}`"
    else:
        title = "✅ Market Summary Checked"
        description = (
            "The Railway job completed successfully, but there was no new completed "
            f"market session to publish.\n\n**[View Current Report →]({SITE_URL})**"
        )
        color = 0x95A5A6
        status = "No update needed"
        commit_value = "No new commit"

    payload = {
        "username": "Market Summary",
        "allowed_mentions": {"parse": []},
        "embeds": [
            {
                "title": title,
                "url": SITE_URL,
                "description": description,
                "color": color,
                "fields": [
                    {"name": "Session", "value": session_date, "inline": True},
                    {"name": "Status", "value": status, "inline": True},
                    {"name": "Commit", "value": commit_value, "inline": True},
                ],
                "footer": {"text": "market-summary • Railway"},
                "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            }
        ],
    }
    discord_post(payload)


def send_failure_notification(error):
    error_text = str(error).strip() or error.__class__.__name__
    if len(error_text) > 800:
        error_text = f"{error_text[:797]}..."

    payload = {
        "username": "Market Summary",
        "allowed_mentions": {"parse": []},
        "embeds": [
            {
                "title": "❌ Market Summary Failed",
                "url": SITE_URL,
                "description": (
                    "The Railway market-summary job failed before it could finish publishing.\n\n"
                    f"```text\n{error_text}\n```\n"
                    f"**[Open Last Live Report →]({SITE_URL})**"
                ),
                "color": 0xE74C3C,
                "fields": [
                    {"name": "Status", "value": "Failed", "inline": True},
                    {"name": "Service", "value": "Railway Cron", "inline": True},
                ],
                "footer": {"text": "market-summary • Railway"},
                "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            }
        ],
    }
    discord_post(payload)


def main():
    if os.environ.get("MARKET_SUMMARY_PAUSED", "").strip().lower() in {"1", "true", "yes", "on"}:
        print("Market Summary is paused via MARKET_SUMMARY_PAUSED; exiting without API usage.")
        return

    try:
        require_environment()
        run([sys.executable, "generate_report.py"])
        run([sys.executable, "-m", "unittest", "-v"])
        snapshot = validate_artifacts()
        publish_result = commit_artifacts()
        send_success_notification(snapshot, publish_result)
    except Exception as exc:
        send_failure_notification(exc)
        raise


if __name__ == "__main__":
    main()
