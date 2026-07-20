import os
import re
import urllib.error
import urllib.request
from dataclasses import dataclass

_REPO_TREE_RE = re.compile(r"^https?://github\.com/([^/]+)/([^/]+?)(?:\.git)?/tree/(.+?)/?$")
_REPO_ROOT_RE = re.compile(r"^https?://github\.com/([^/]+)/([^/]+?)(?:\.git)?/?$")


class GithubSourceError(Exception):
    """Raised when a GitHub URL cannot be parsed or downloaded."""


@dataclass
class GithubRef:
    owner: str
    repo: str
    ref: str  # branch, tag, commit SHA, or "HEAD" for the repo's default branch


def parse_github_url(url):
    """Parse a GitHub repo-root or /tree/<ref> URL into a GithubRef.

    Only these two shapes are supported (not pull-request URLs):
      https://github.com/<owner>/<repo>
      https://github.com/<owner>/<repo>/tree/<branch-or-tag>
    """
    url = url.strip()

    match = _REPO_TREE_RE.match(url)
    if match:
        owner, repo, ref = match.groups()
        return GithubRef(owner=owner, repo=repo, ref=ref)

    match = _REPO_ROOT_RE.match(url)
    if match:
        owner, repo = match.groups()
        return GithubRef(owner=owner, repo=repo, ref="HEAD")

    raise GithubSourceError(f"Unsupported GitHub URL: {url!r}")


def build_zipball_url(ref):
    return f"https://api.github.com/repos/{ref.owner}/{ref.repo}/zipball/{ref.ref}"


def _http_download(url, dest_path):
    request = urllib.request.Request(url, headers={"User-Agent": "AutoFLC"})
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        request.add_header("Authorization", f"Bearer {token}")

    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            with open(dest_path, "wb") as out_file:
                out_file.write(response.read())
    except urllib.error.HTTPError as e:
        raise GithubSourceError(f"GitHub returned HTTP {e.code} for {url}") from e
    except urllib.error.URLError as e:
        raise GithubSourceError(f"Failed to reach GitHub: {e.reason}") from e


def fetch_github_zip(url, dest_dir, downloader=_http_download):
    """Resolve a GitHub URL and download it as a zip into dest_dir, returning the local path."""
    ref = parse_github_url(url)
    zip_url = build_zipball_url(ref)

    safe_name = re.sub(r"[^\w.-]", "_", f"{ref.owner}_{ref.repo}_{ref.ref}")
    dest_path = os.path.join(dest_dir, f"{safe_name}.zip")

    downloader(zip_url, dest_path)
    return dest_path
