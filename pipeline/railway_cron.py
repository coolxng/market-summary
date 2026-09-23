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
from zoneinfo import ZoneInfo

from delivery import close_publication, deliver, failure_publication


REPOSITORY = os.environ.get("GITHUB_REPOSITORY", "coolxng/market-summary")
BRANCH = os.environ.get("GITHUB_BRANCH", "main")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
SITE_URL = os.environ.get("MARKET_SUMMARY_URL", "https://coolxng.github.io/market-summary/")
BASE_ARTIFACTS = (Path("data/report_snapshot.json"),)
CENTRAL_TZ = ZoneInfo("America/Chicago")
PUBLISH_RETRY_START = datetime.time(15, 25)
PUBLISH_RETRY_END = datetime.time(16, 29, 59)


def truthy_env(name):
    return os.environ.get(name, "").strip().lower() in {"1", "true", "yes", "on"}


def require_environment():
    missing = []
    if not os.environ.get("ANTHROPIC_API_KEY"):
        missing.append("ANTHROPIC_API_KEY")
    if not GITHUB_TOKEN:
        missing.append("GITHUB_TOKEN")
    if missing:
        raise RuntimeError(f"Missing required Railway variables: {', '.join(missing)}")


def run(command, env=None):
    print(f"$ {' '.join(command)}", flush=True)
    subprocess.run(command, check=True, env=env)


def test_environment():
    """Keep Railway manual-run controls from changing unit-test behavior."""
    env = os.environ.copy()
    for name in ("MARKET_SUMMARY_FORCE", "MARKET_SUMMARY_REGENERATE", "MARKET_SUMMARY_PAUSED"):
        env.pop(name, None)
    return env


def artifact_paths(snapshot):
    session_date = str(snapshot["session_date"])
    return (
        *BASE_ARTIFACTS,
        Path("public") / "reports" / session_date / "report.json",
    )


def validate_artifacts():
    (snapshot_path,) = BASE_ARTIFACTS
    if not snapshot_path.exists():
        raise RuntimeError(f"Missing generated artifact: {snapshot_path}")

    snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    assert snapshot["report_type"] == "daily_market_close"
    assert snapshot["session_date"] > snapshot["previous_session_date"]
    assert snapshot["market_data"]["^GSPC"]["end_price"] > 0
    assert snapshot["market_data"]["^IXIC"]["end_price"] > 0
    assert snapshot["market_data"]["^TNX"]["end_price"] > 0
    assert snapshot["daily_market_breadth"]["positive_sector_share"] >= 0
    for path in artifact_paths(snapshot):
        if not path.exists():
            raise RuntimeError(f"Missing generated artifact: {path}")
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


def remote_snapshot():
    encoded_branch = urllib.parse.quote(BRANCH, safe="")
    result = api_request("GET", f"/contents/data/report_snapshot.json?ref={encoded_branch}")
    content = result.get("content", "").replace("\n", "")
    if not content:
        raise RuntimeError("Remote data/report_snapshot.json did not include file content.")
    return json.loads(base64.b64decode(content).decode("utf-8"))


def already_published_for_local_date(now=None):
    if truthy_env("MARKET_SUMMARY_REGENERATE"):
        return False

    current = now or datetime.datetime.now(datetime.timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=datetime.timezone.utc)
    expected_date = current.astimezone(CENTRAL_TZ).date().isoformat()

    try:
        snapshot = remote_snapshot()
    except Exception as exc:
        print(
            f"Close Tape preflight could not read the remote snapshot ({exc.__class__.__name__}); continuing with generation."
        )
        return False

    if str(snapshot.get("session_date")) == expected_date:
        print(f"Close Tape already published {expected_date}; retry exits without API or market-data work.")
        return True
    return False


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


def commit_artifacts(snapshot):
    artifacts = artifact_paths(snapshot)
    local_contents = {path: path.read_bytes() for path in artifacts}
    changed = []
    for path, content in local_contents.items():
        try:
            remote_sha = remote_blob_sha(path)
        except RuntimeError as exc:
            if "failed (404)" not in str(exc):
                raise
            remote_sha = None
        if git_blob_sha(content) != remote_sha:
            changed.append(path)

    if not changed:
        print("No new completed market session to commit.")
        return {"updated": False, "commit_sha": None}

    encoded_branch = urllib.parse.quote(BRANCH, safe="")
    ref = api_request("GET", f"/git/ref/heads/{encoded_branch}")
    parent_sha = ref["object"]["sha"]
    parent_commit = api_request("GET", f"/git/commits/{parent_sha}")
    base_tree_sha = parent_commit["tree"]["sha"]

    tree_entries = []
    for path in artifacts:
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
            "author": {
                "name": "coolxng",
                "email": "264265684+coolxng@users.noreply.github.com",
            },
            "committer": {
                "name": "coolxng",
                "email": "264265684+coolxng@users.noreply.github.com",
            },
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


def send_success_notification(snapshot, publish_result):
    """Post only when a new session was committed; quiet runs stay quiet."""
    if not publish_result["updated"]:
        print("No new session was published; skipping delivery.")
        return {}
    return deliver(close_publication(snapshot, SITE_URL))


def send_failure_notification(error):
    return deliver(failure_publication(error, SITE_URL, service="Close Tape"))


def should_publish_now(now=None):
    if truthy_env("MARKET_SUMMARY_FORCE"):
        return True
    current = now or datetime.datetime.now(datetime.timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=datetime.timezone.utc)
    local = current.astimezone(CENTRAL_TZ)
    local_time = local.time().replace(tzinfo=None)
    return (
        local.weekday() < 5
        and PUBLISH_RETRY_START <= local_time <= PUBLISH_RETRY_END
    )


def main():
    if truthy_env("MARKET_SUMMARY_PAUSED"):
        print("Market Summary is paused via MARKET_SUMMARY_PAUSED; exiting without API usage.")
        return
    if not should_publish_now():
        print("Close Tape retry guard: outside the 3:25-4:29 PM America/Chicago publish window; exiting.")
        return

    try:
        require_environment()
        if already_published_for_local_date():
            return
        run([sys.executable, "pipeline/generate_report.py"])
        run([sys.executable, "-m", "unittest", "-v"], env=test_environment())
        snapshot = validate_artifacts()
        publish_result = commit_artifacts(snapshot)
        send_success_notification(snapshot, publish_result)
    except Exception as exc:
        send_failure_notification(exc)
        raise


if __name__ == "__main__":
    main()
