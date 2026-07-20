import urllib.error
import urllib.request

import pytest

from autoflc.github_source import (
    GithubSourceError,
    build_zipball_url,
    fetch_github_zip,
    parse_github_url,
)


def test_parse_repo_root():
    ref = parse_github_url("https://github.com/nasa/CS")
    assert ref.owner == "nasa"
    assert ref.repo == "CS"
    assert ref.ref == "HEAD"


def test_parse_repo_root_with_trailing_slash_and_git_suffix():
    ref = parse_github_url("https://github.com/nasa/CS.git/")
    assert ref.owner == "nasa"
    assert ref.repo == "CS"
    assert ref.ref == "HEAD"


def test_parse_tree_url_with_branch():
    ref = parse_github_url("https://github.com/nasa/CS/tree/v7.0.0")
    assert ref.owner == "nasa"
    assert ref.repo == "CS"
    assert ref.ref == "v7.0.0"


def test_parse_invalid_url_raises():
    with pytest.raises(GithubSourceError):
        parse_github_url("https://example.com/nasa/CS")


def test_build_zipball_url():
    ref = parse_github_url("https://github.com/nasa/CS/tree/v7.0.0")
    assert build_zipball_url(ref) == "https://api.github.com/repos/nasa/CS/zipball/v7.0.0"


def test_fetch_github_zip_uses_injected_downloader(tmp_path):
    calls = []

    def fake_downloader(url, dest_path):
        calls.append((url, dest_path))
        with open(dest_path, "wb") as f:
            f.write(b"fake-zip-bytes")

    result_path = fetch_github_zip(
        "https://github.com/nasa/CS/tree/v7.0.0", str(tmp_path), downloader=fake_downloader
    )

    assert len(calls) == 1
    assert calls[0][0] == "https://api.github.com/repos/nasa/CS/zipball/v7.0.0"
    assert result_path == calls[0][1]
    with open(result_path, "rb") as f:
        assert f.read() == b"fake-zip-bytes"


def test_http_download_wraps_http_error(monkeypatch, tmp_path):
    from autoflc.github_source import _http_download

    def fake_urlopen(request, timeout):
        raise urllib.error.HTTPError(request.full_url, 404, "Not Found", hdrs=None, fp=None)

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)

    with pytest.raises(GithubSourceError):
        _http_download("https://api.github.com/repos/owner/repo/zipball/HEAD", str(tmp_path / "out.zip"))
