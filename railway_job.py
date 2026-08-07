"""Generate the daily report on Railway and publish its artifacts to GitHub."""

import base64
import json
import os
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


ARTIFACTS = (Path("report_snapshot.json"), Path("public/legacy-report.html"))
API_ROOT = "https://api.github.com"


def required_environment():
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    repository = os.environ.get("GITHUB_REPOSITORY", "coolxng/market-summary").strip()
    branch = os.environ.get("GITHUB_BRANCH", "main").strip()
    if not token:
        raise RuntimeError("GITHUB_TOKEN is required and must have Contents: Read and write access.")
    if repository.count("/") != 1:
        raise RuntimeError("GITHUB_REPOSITORY must use the owner/repository format.")
    if not branch:
        raise RuntimeError("GITHUB_BRANCH cannot be empty.")
    return token, repository, branch


def github_request(token, method, path, payload=None):
    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = urllib.request.Request(
        f"{API_ROOT}{path}",
        data=body,
        method=method,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "User-Agent": "market-summary-railway-job",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.load(response)
    except urllib.error.HTTPError as error:
        details = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"GitHub API {method} {path} failed ({error.code}): {details}") from error


def repository_path(repository, suffix):
    owner, name = repository.split("/", 1)
    return f"/repos/{urllib.parse.quote(owner)}/{urllib.parse.quote(name)}{suffix}"


def fetch_artifact(token, repository, branch, artifact):
    encoded_path = "/".join(urllib.parse.quote(part) for part in artifact.parts)
    query = urllib.parse.urlencode({"ref": branch})
    response = github_request(
        token,
        "GET",
        repository_path(repository, f"/contents/{encoded_path}?{query}"),
    )
    return base64.b64decode(response["content"])


def sync_current_artifacts(token, repository, branch):
    current = {}
    for artifact in ARTIFACTS:
        content = fetch_artifact(token, repository, branch, artifact)
        artifact.parent.mkdir(parents=True, exist_ok=True)
        artifact.write_bytes(content)
        current[artifact] = content
    return current


def validate_snapshot():
    snapshot = json.loads(ARTIFACTS[0].read_text(encoding="utf-8"))
    assert snapshot["report_type"] == "daily_market_close"
    assert snapshot["session_date"] > snapshot["previous_session_date"]
    for ticker in ("^GSPC", "^IXIC", "^TNX"):
        assert snapshot["market_data"][ticker]["end_price"] > 0
    assert snapshot["daily_market_breadth"]["positive_sector_share"] >= 0


def publish_artifacts(token, repository, branch, previous_content):
    changed = [artifact for artifact in ARTIFACTS if artifact.read_bytes() != previous_content[artifact]]
    if not changed:
        print("No new completed session to publish.")
        return False

    ref_path = repository_path(repository, f"/git/ref/heads/{urllib.parse.quote(branch, safe='')}")
    head = github_request(token, "GET", ref_path)["object"]["sha"]
    commit_path = repository_path(repository, f"/git/commits/{head}")
    base_tree = github_request(token, "GET", commit_path)["tree"]["sha"]

    tree_entries = []
    for artifact in changed:
        blob = github_request(
            token,
            "POST",
            repository_path(repository, "/git/blobs"),
            {"content": base64.b64encode(artifact.read_bytes()).decode("ascii"), "encoding": "base64"},
        )
        tree_entries.append({"path": artifact.as_posix(), "mode": "100644", "type": "blob", "sha": blob["sha"]})

    tree = github_request(
        token,
        "POST",
        repository_path(repository, "/git/trees"),
        {"base_tree": base_tree, "tree": tree_entries},
    )
    commit = github_request(
        token,
        "POST",
        repository_path(repository, "/git/commits"),
        {"message": "Automated Daily Market Summary update", "tree": tree["sha"], "parents": [head]},
    )
    github_request(token, "PATCH", ref_path, {"sha": commit["sha"], "force": False})
    print(f"Published {len(changed)} artifact(s) in commit {commit['sha']}.")
    return True


def main():
    token, repository, branch = required_environment()
    previous_content = sync_current_artifacts(token, repository, branch)
    subprocess.run([sys.executable, "generate_report.py"], check=True)
    subprocess.run([sys.executable, "-m", "unittest", "-v"], check=True)
    validate_snapshot()
    publish_artifacts(token, repository, branch, previous_content)


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"Railway market-summary job failed: {error}", file=sys.stderr)
        raise
