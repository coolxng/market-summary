import base64
import datetime
import hashlib
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from zoneinfo import ZoneInfo

from delivery import deliver, failure_publication, morning_publication
from generate_morning import generate_morning_snapshot


REPOSITORY = os.environ.get("GITHUB_REPOSITORY", "coolxng/market-summary")
BRANCH = os.environ.get("GITHUB_BRANCH", "main")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
SITE_URL = os.environ.get("MARKET_SUMMARY_URL", "https://coolxng.github.io/market-summary/")
ARTIFACTS = (Path("morning_snapshot.json"), Path("public/morning/latest.json"))
CENTRAL_TZ = ZoneInfo("America/Chicago")


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
    """Deliver only when a new Morning Tape was committed."""
    if not commit_sha:
        return {}
    return deliver(morning_publication(snapshot, SITE_URL))


def should_publish_now(now=None):
    if os.environ.get("MORNING_TAPE_FORCE", "").strip().lower() in {"1", "true", "yes", "on"}:
        return True
    current = now or datetime.datetime.now(datetime.timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=datetime.timezone.utc)
    local = current.astimezone(CENTRAL_TZ)
    return local.weekday() < 5 and local.hour == 7


def main():
    if not should_publish_now():
        print("Morning Tape DST guard: this UTC slot is not 7 AM America/Chicago; exiting.")
        return

    try:
        require_environment()
        snapshot = generate_morning_snapshot()
        validate_snapshot(snapshot)
        commit_sha = commit_artifacts(snapshot)
        notify(snapshot, commit_sha)
    except Exception as exc:
        deliver(failure_publication(exc, f"{SITE_URL.rstrip('/')}/morning/", service="Morning Tape"))
        raise


if __name__ == "__main__":
    main()
