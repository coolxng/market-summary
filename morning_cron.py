import base64
import hashlib
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from generate_morning import generate_morning_snapshot


REPOSITORY = os.environ.get("GITHUB_REPOSITORY", "coolxng/market-summary")
BRANCH = os.environ.get("GITHUB_BRANCH", "main")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL", "")
SITE_URL = os.environ.get("MARKET_SUMMARY_URL", "https://coolxng.github.io/market-summary/")
ARTIFACTS = (Path("morning_snapshot.json"), Path("public/morning/latest.json"))


def require_environment():
    if not GITHUB_TOKEN:
        raise RuntimeError("Missing required Railway variable: GITHUB_TOKEN")


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
            "User-Agent": "market-summary-morning-cron",
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
    try:
        result = api_request("GET", f"/contents/{encoded_path}?ref={encoded_branch}")
        return result["sha"]
    except RuntimeError as exc:
        if "failed (404)" in str(exc):
            return None
        raise


def create_blob(content):
    result = api_request(
        "POST",
        "/git/blobs",
        {"content": base64.b64encode(content).decode("ascii"), "encoding": "base64"},
    )
    return result["sha"]


def validate_snapshot(snapshot):
    if snapshot.get("report_type") != "morning_tape":
        raise RuntimeError("Morning snapshot has the wrong report_type.")
    quality = snapshot.get("data_quality") or {}
    if int(quality.get("total", 0)) <= 0:
        raise RuntimeError("Morning snapshot did not check any market quotes.")
    if float(quality.get("coverage_pct", 0)) < 40:
        raise RuntimeError("Morning snapshot coverage is too low to publish.")
    for path in ARTIFACTS:
        if not path.exists():
            raise RuntimeError(f"Missing Morning Tape artifact: {path}")


def commit_artifacts(snapshot):
    contents = {path: path.read_bytes() for path in ARTIFACTS}
    changed = [
        path for path, content in contents.items()
        if git_blob_sha(content) != remote_blob_sha(path)
    ]
    if not changed:
        print("Morning Tape is unchanged; no commit needed.")
        return None

    encoded_branch = urllib.parse.quote(BRANCH, safe="")
    ref = api_request("GET", f"/git/ref/heads/{encoded_branch}")
    parent_sha = ref["object"]["sha"]
    parent = api_request("GET", f"/git/commits/{parent_sha}")

    tree_entries = []
    for path, content in contents.items():
        tree_entries.append({
            "path": path.as_posix(),
            "mode": "100644",
            "type": "blob",
            "sha": create_blob(content),
        })

    tree = api_request("POST", "/git/trees", {
        "base_tree": parent["tree"]["sha"],
        "tree": tree_entries,
    })
    commit = api_request("POST", "/git/commits", {
        "message": f"Morning Tape update for {snapshot['market_date']}",
        "author": {"name": "coolxng", "email": "264265684+coolxng@users.noreply.github.com"},
        "committer": {"name": "coolxng", "email": "264265684+coolxng@users.noreply.github.com"},
        "tree": tree["sha"],
        "parents": [parent_sha],
    })
    api_request("PATCH", f"/git/refs/heads/{encoded_branch}", {
        "sha": commit["sha"],
        "force": False,
    })
    print(f"Committed Morning Tape to {REPOSITORY}@{BRANCH}: {commit['sha']}")
    return commit["sha"]


def notify(snapshot, commit_sha):
    if not DISCORD_WEBHOOK_URL or not commit_sha:
        return
    morning_url = f"{SITE_URL.rstrip('/')}/morning/"
    payload = {
        "username": "The Daily Tape",
        "allowed_mentions": {"parse": []},
        "embeds": [{
            "title": "☀️ Morning Tape Ready",
            "url": morning_url,
            "description": (
                f"Premarket setup for **{snapshot['market_date']}** is ready.\n\n"
                f"**[Open Morning Tape →]({morning_url})**"
            ),
            "color": 0xFF5C35,
            "fields": [
                {"name": "Quote coverage", "value": f"{snapshot['data_quality']['coverage_pct']:.1f}%", "inline": True},
                {"name": "Status", "value": snapshot["status"].title(), "inline": True},
            ],
            "footer": {"text": "market-summary • Railway"},
        }],
    }
    request = urllib.request.Request(
        DISCORD_WEBHOOK_URL,
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
        headers={"Content-Type": "application/json", "User-Agent": "market-summary-morning-cron"},
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            response.read()
    except Exception as exc:
        print(f"Warning: Morning Tape Discord notification failed: {exc}")


def main():
    require_environment()
    snapshot = generate_morning_snapshot()
    validate_snapshot(snapshot)
    commit_sha = commit_artifacts(snapshot)
    notify(snapshot, commit_sha)


if __name__ == "__main__":
    main()
