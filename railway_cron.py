import base64
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
        return

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


def main():
    require_environment()
    run([sys.executable, "generate_report.py"])
    run([sys.executable, "-m", "unittest", "-v"])
    validate_artifacts()
    commit_artifacts()


if __name__ == "__main__":
    main()
