import base64
import json
import os
import re
import ssl
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


DEFAULT_REPOSITORY_URL = "https://github.com/ottandras-cmyk/TSPC_AD.git"
DEFAULT_RELEASE_BRANCH = "copilot/ad-tracker-v1.27-20261030"
APP_ROOT = Path(__file__).resolve().parents[1]
EXCLUDED_DIRECTORIES = {
    ".git",
    ".pytest_cache",
    ".venv",
    "__pycache__",
    "backups",
    "csv_imports",
    "data",
    "exports",
    "screenshots",
    "venv",
}
EXCLUDED_FILES = {
    "AI_SYSTEM_CODEBASE_BUNDLE.md",
    "AI_SYSTEM_CODEBASE_BUNDLE_masked.md",
    "ai_knowledge_base.json",
    "settings.json",
}
REMOTE_FILES_TO_REMOVE = {
    "app/docs/ai_knowledge_base.json",
    "app/docs/AI_SYSTEM_CODEBASE_BUNDLE.md",
    "app/docs/AI_SYSTEM_CODEBASE_BUNDLE_masked.md",
}
EXCLUDED_SUFFIXES = {
    ".csv",
    ".db",
    ".dump",
    ".key",
    ".log",
    ".pem",
    ".pyc",
    ".pyo",
    ".sql",
    ".sqlite",
    ".sqlite3",
    ".tsv",
}
SECRET_PATTERNS = (
    re.compile(rb"(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})"),
    re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(rb"AKIA[0-9A-Z]{16}"),
    re.compile(rb"\b[0-9]{6,12}:[A-Za-z0-9_-]{30,}\b"),
)
VERSION_PATTERN = re.compile(r"^v?(\d+)\.(\d+)(?:\.(\d+))?$")
MAX_TREE_CONTENT_BYTES = 20 * 1024 * 1024


class GitHubReleaseError(Exception):
    pass


def _repository_parts(repository_url: str) -> tuple[str, str]:
    parsed = urllib.parse.urlparse(repository_url)
    if parsed.scheme != "https" or parsed.hostname != "github.com":
        raise GitHubReleaseError("Csak GitHub HTTPS repository használható.")
    if parsed.username or parsed.password:
        raise GitHubReleaseError("A repository URL ne tartalmazzon hitelesítő adatot.")
    parts = parsed.path.strip("/").removesuffix(".git").split("/")
    if len(parts) != 2 or not all(re.fullmatch(r"[A-Za-z0-9_.-]+", part) for part in parts):
        raise GitHubReleaseError("Érvénytelen GitHub repository URL.")
    return parts[0], parts[1]


def _api_request(
    owner: str,
    repository: str,
    token: str,
    endpoint: str,
    data: dict | None = None,
    method: str = "GET",
) -> dict | list:
    url = f"https://api.github.com/repos/{owner}/{repository}/{endpoint.lstrip('/')}"
    payload = json.dumps(data).encode("utf-8") if data is not None else None
    request = urllib.request.Request(
        url,
        data=payload,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json",
            "User-Agent": "AD-Tracker",
            "X-GitHub-Api-Version": "2022-11-28",
        },
        method=method,
    )
    try:
        with urllib.request.urlopen(request, timeout=30, context=ssl.create_default_context()) as response:
            response_body = response.read().decode("utf-8")
            return json.loads(response_body) if response_body else {}
    except urllib.error.HTTPError as error:
        try:
            details = json.loads(error.read().decode("utf-8")).get("message", error.reason)
        except (json.JSONDecodeError, UnicodeDecodeError):
            details = error.reason
        raise GitHubReleaseError(f"GitHub API hiba ({error.code}): {details}") from error
    except (urllib.error.URLError, TimeoutError) as error:
        raise GitHubReleaseError(f"Nem érhető el a GitHub API: {error}") from error


def _latest_version_tag(owner: str, repository: str, token: str) -> tuple[str, str]:
    best: tuple[tuple[int, int, int], str, str] | None = None
    for page in range(1, 11):
        tags = _api_request(owner, repository, token, f"tags?per_page=100&page={page}")
        if not isinstance(tags, list):
            raise GitHubReleaseError("A GitHub verziócímke-listája érvénytelen választ adott.")
        if not tags:
            break
        for tag in tags:
            name = tag.get("name", "")
            match = VERSION_PATTERN.fullmatch(name)
            if not match:
                continue
            version = tuple(int(part or 0) for part in match.groups())
            commit_sha = tag.get("commit", {}).get("sha")
            if commit_sha and (best is None or version > best[0]):
                best = (version, name, commit_sha)
        if len(tags) < 100:
            break
    if best is None:
        raise GitHubReleaseError("Nem található vX.Y formátumú kiadási címke a repositoryban.")
    return best[1], best[2]


def inspect_remote_release(repository_url: str, token: str, branch: str) -> dict:
    owner, repository = _repository_parts(repository_url)
    version, tag_commit = _latest_version_tag(owner, repository, token)
    encoded_branch = urllib.parse.quote(branch, safe="/")
    try:
        branch_ref = _api_request(owner, repository, token, f"git/ref/heads/{encoded_branch}")
        branch_commit = branch_ref["object"]["sha"]
    except GitHubReleaseError as error:
        if "hiba (404)" not in str(error).lower():
            raise
        branch_commit = tag_commit
    return {
        "repository": f"{owner}/{repository}",
        "branch": branch,
        "latest_version": version,
        "latest_tag_commit": tag_commit,
        "branch_commit": branch_commit,
    }


def _next_version(version: str) -> str:
    match = VERSION_PATTERN.fullmatch(version)
    if not match:
        raise GitHubReleaseError(f"Nem növelhető verziócímke: {version}")
    major, minor, patch = (int(part or 0) for part in match.groups())
    if match.group(3) is None:
        minor += 1
        return f"v{major}.{minor:02d}"
    return f"v{major}.{minor}.{patch + 1}"


def _existing_remote_paths(
    owner: str,
    repository: str,
    token: str,
    base_tree_sha: str,
    paths: set[str],
) -> set[str]:
    trees_by_sha = {}
    existing_paths = set()

    def get_tree_entries(tree_sha: str) -> dict[str, dict]:
        if tree_sha not in trees_by_sha:
            response = _api_request(owner, repository, token, f"git/trees/{tree_sha}")
            trees_by_sha[tree_sha] = {
                entry["path"]: entry
                for entry in response.get("tree", [])
                if isinstance(entry, dict) and isinstance(entry.get("path"), str)
            }
        return trees_by_sha[tree_sha]

    for path in paths:
        tree_sha = base_tree_sha
        parts = path.split("/")
        for index, part in enumerate(parts):
            entry = get_tree_entries(tree_sha).get(part)
            if entry is None:
                break
            if index == len(parts) - 1:
                if entry.get("type") == "blob":
                    existing_paths.add(path)
                break
            if entry.get("type") != "tree" or not entry.get("sha"):
                break
            tree_sha = entry["sha"]
    return existing_paths


def _collect_tree_entries(
    new_version: str,
    remote_files_to_remove: set[str] | None = None,
) -> list[dict]:
    entries = []
    total_bytes = 0
    unsafe_files = []
    for current_root, directories, filenames in os.walk(APP_ROOT, followlinks=False):
        directories[:] = [
            name
            for name in directories
            if name not in EXCLUDED_DIRECTORIES
            and not (Path(current_root) / name).is_symlink()
        ]
        for filename in filenames:
            file_path = Path(current_root) / filename
            relative_path = file_path.relative_to(APP_ROOT)
            if (
                filename in EXCLUDED_FILES
                or filename == ".env"
                or filename.startswith(".env.")
                or filename.endswith(".env")
                or filename.endswith(".local.json")
                or relative_path.as_posix() == "app/git_version.txt"
                or file_path.suffix.lower() in EXCLUDED_SUFFIXES
                or file_path.is_symlink()
            ):
                continue
            content = file_path.read_bytes()
            if any(pattern.search(content) for pattern in SECRET_PATTERNS):
                unsafe_files.append(relative_path.as_posix())
                continue
            try:
                text_content = content.decode("utf-8")
            except UnicodeDecodeError:
                total_bytes += len(content)
                entries.append(
                    {
                        "path": f"app/{relative_path.as_posix()}",
                        "mode": "100644",
                        "type": "blob",
                        "binary_content": content,
                    }
                )
                continue
            total_bytes += len(content)
            entries.append(
                {
                    "path": f"app/{relative_path.as_posix()}",
                    "mode": "100644",
                    "type": "blob",
                    "content": text_content,
                }
            )
    if unsafe_files:
        paths = ", ".join(unsafe_files[:5])
        raise GitHubReleaseError(f"Lehetséges titkot tartalmazó fájl(ok), feltöltés megszakítva: {paths}")
    if total_bytes > MAX_TREE_CONTENT_BYTES:
        raise GitHubReleaseError("A forrásfájlok összmérete meghaladja a GitHub API 20 MB-os védelmi korlátját.")

    entries.extend(
        {
            "path": path,
            "mode": "100644",
            "type": "blob",
            "sha": None,
        }
        for path in sorted(remote_files_to_remove or set())
    )
    version_content = f"{new_version}\n"
    entries.append(
        {
            "path": "app/app/git_version.txt",
            "mode": "100644",
            "type": "blob",
            "content": version_content,
        }
    )
    entries.append(
        {
            "path": "git_version.txt",
            "mode": "100644",
            "type": "blob",
            "content": version_content,
        }
    )
    return entries


def push_release(
    repository_url: str,
    token: str,
    branch: str,
    comment: str = "",
) -> dict:
    if not token or token.startswith("•••"):
        raise GitHubReleaseError("Hiányzik vagy érvénytelen a GitHub Personal Access Token.")
    if (
        not branch
        or branch == "main"
        or not re.fullmatch(r"[A-Za-z0-9._/-]+", branch)
        or ".." in branch
        or "//" in branch
    ):
        raise GitHubReleaseError("A távoli main ág védelme érdekében kiadási ágat kell megadni.")

    owner, repository = _repository_parts(repository_url)
    latest_version, tagged_commit_sha = _latest_version_tag(owner, repository, token)
    new_version = _next_version(latest_version)
    new_tag_ref = f"git/ref/tags/{urllib.parse.quote(new_version, safe='')}"
    try:
        _api_request(owner, repository, token, new_tag_ref)
    except GitHubReleaseError as error:
        if "hiba (404)" not in str(error).lower():
            raise
    else:
        raise GitHubReleaseError(f"A {new_version} címke már létezik; frissítse a verzióellenőrzést és próbálja újra.")

    encoded_branch = urllib.parse.quote(branch, safe="/")
    try:
        branch_ref = _api_request(owner, repository, token, f"git/ref/heads/{encoded_branch}")
        parent_sha = branch_ref["object"]["sha"]
    except GitHubReleaseError as error:
        if "hiba (404)" not in str(error).lower():
            raise
        _api_request(
            owner,
            repository,
            token,
            "git/refs",
            {"ref": f"refs/heads/{branch}", "sha": tagged_commit_sha},
            method="POST",
        )
        parent_sha = tagged_commit_sha
    else:
        comparison = _api_request(
            owner,
            repository,
            token,
            f"compare/{tagged_commit_sha}...{parent_sha}",
        )
        ahead_by = comparison.get("ahead_by", 0)
        behind_by = comparison.get("behind_by", 0)
        if behind_by and not ahead_by:
            _api_request(
                owner,
                repository,
                token,
                f"git/refs/heads/{encoded_branch}",
                {"sha": tagged_commit_sha, "force": False},
                method="PATCH",
            )
            parent_sha = tagged_commit_sha
        elif behind_by:
            raise GitHubReleaseError(
                f"A(z) {branch} ág eltér a legújabb ({latest_version}) verzióvonaltól; "
                "automatikus felülírás helyett kézi összevezetés szükséges."
            )

    parent_commit = _api_request(owner, repository, token, f"git/commits/{parent_sha}")
    base_tree_sha = parent_commit.get("tree", {}).get("sha")
    if not base_tree_sha:
        raise GitHubReleaseError("A távoli kiadási ág commitjában nem található Git-fa.")

    remote_files_to_remove = _existing_remote_paths(
        owner,
        repository,
        token,
        base_tree_sha,
        REMOTE_FILES_TO_REMOVE,
    )
    tree_entries = _collect_tree_entries(new_version, remote_files_to_remove)
    for entry in tree_entries:
        binary_content = entry.pop("binary_content", None)
        if binary_content is not None:
            blob = _api_request(
                owner,
                repository,
                token,
                "git/blobs",
                {
                    "content": base64.b64encode(binary_content).decode("ascii"),
                    "encoding": "base64",
                },
                method="POST",
            )
            entry["sha"] = blob["sha"]
    tree = _api_request(
        owner,
        repository,
        token,
        "git/trees",
        {"base_tree": base_tree_sha, "tree": tree_entries},
        method="POST",
    )
    commit_message = comment.strip() or f"AD Tracker release {new_version}"
    commit = _api_request(
        owner,
        repository,
        token,
        "git/commits",
        {
            "message": f"{new_version}: {commit_message}",
            "tree": tree["sha"],
            "parents": [parent_sha],
        },
        method="POST",
    )
    commit_sha = commit["sha"]
    _api_request(
        owner,
        repository,
        token,
        f"git/refs/heads/{encoded_branch}",
        {"sha": commit_sha, "force": False},
        method="PATCH",
    )

    try:
        tag_object = _api_request(
            owner,
            repository,
            token,
            "git/tags",
            {
                "tag": new_version,
                "message": f"{new_version}: {commit_message}",
                "object": commit_sha,
                "type": "commit",
                "tagger": {
                    "name": "AD Tracker System",
                    "email": "adtracker@tspc.hu",
                    "date": datetime.now(timezone.utc).isoformat(),
                },
            },
            method="POST",
        )
        _api_request(
            owner,
            repository,
            token,
            "git/refs",
            {"ref": f"refs/tags/{new_version}", "sha": tag_object["sha"]},
            method="POST",
        )
    except GitHubReleaseError as error:
        raise GitHubReleaseError(
            f"A {branch} ág frissült ({commit_sha[:7]}), de a {new_version} címke létrehozása nem sikerült: {error}"
        ) from error

    return {
        "status": "SUCCESS",
        "version": new_version,
        "commit_sha": commit_sha,
        "branch": branch,
        "repository": f"{owner}/{repository}",
        "previous_version": latest_version,
        "message": f"Sikeres feltöltés: {new_version} a(z) {owner}/{repository} repository {branch} ágára.",
    }
