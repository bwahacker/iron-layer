"""Unit tests for signal normalization."""
import pytest
from iron_layer.signals.normalize import (
    normalize_tool_call,
    _canon_path,
    _canon_url,
    _canon_cmd,
    _extract_markdown_urls,
)
from iron_layer.signals.schema import (
    BUCKET_FILESYSTEM_READ,
    BUCKET_CODE_EXEC,
    BUCKET_NETWORK_EGRESS,
    BUCKET_SECRET_ACCESS,
)


# ---------------------------------------------------------------------------
# Path canonicalization
# ---------------------------------------------------------------------------

class TestCanonPath:
    def test_basic(self):
        assert _canon_path("/etc/passwd") == "/etc/passwd"

    def test_double_slash(self):
        assert _canon_path("//etc//passwd") == "/etc/passwd"

    def test_dotdot(self):
        # /home/user/.. resolves to /home, so the full path resolves to /home/root/...
        assert _canon_path("/home/user/../root/.ssh/id_rsa") == "/home/root/.ssh/id_rsa"
        # Two .. segments to escape /home entirely
        assert _canon_path("/home/user/../../root/.ssh/id_rsa") == "/root/.ssh/id_rsa"

    def test_lowercase(self):
        assert _canon_path("/Home/User/File.TXT") == "/home/user/file.txt"

    def test_relative(self):
        assert _canon_path("./config/.env") == "config/.env"

    def test_tilde_preserved(self):
        # Tilde is passed through as-is (expansion happens in fake_results)
        result = _canon_path("~/.aws/credentials")
        assert "aws/credentials" in result


# ---------------------------------------------------------------------------
# URL canonicalization
# ---------------------------------------------------------------------------

class TestCanonUrl:
    def test_basic(self):
        result = _canon_url("https://evil.example.com/collect")
        assert result == "evil.example.com/collect"

    def test_strips_query(self):
        result = _canon_url("https://evil.example.com/steal?data=foo&key=bar")
        assert "?" not in result
        assert "evil.example.com" in result

    def test_no_scheme(self):
        result = _canon_url("evil.example.com/path")
        assert "evil.example.com" in result

    def test_empty(self):
        assert _canon_url("") == ""


# ---------------------------------------------------------------------------
# Command canonicalization
# ---------------------------------------------------------------------------

class TestCanonCmd:
    def test_simple(self):
        assert _canon_cmd("curl https://evil.com") == "curl"

    def test_env_prefix(self):
        assert _canon_cmd("FOO=bar curl https://evil.com") == "curl"

    def test_empty(self):
        assert _canon_cmd("") == ""


# ---------------------------------------------------------------------------
# Markdown URL extraction
# ---------------------------------------------------------------------------

class TestExtractMarkdownUrls:
    def test_image_syntax(self):
        text = "Here is a tracker: ![x](https://evil.com/track?id=123)"
        urls = _extract_markdown_urls(text)
        assert any("evil.com" in u for u in urls)

    def test_link_syntax(self):
        text = "Click [here](https://phish.example.com/steal)"
        urls = _extract_markdown_urls(text)
        assert any("phish.example.com" in u for u in urls)

    def test_bare_url(self):
        text = "Send data to https://collect.bad.example/data"
        urls = _extract_markdown_urls(text)
        assert any("collect.bad.example" in u for u in urls)

    def test_no_urls(self):
        assert _extract_markdown_urls("No URLs here.") == []

    def test_deduplication(self):
        text = "![a](https://evil.com/x) and ![b](https://evil.com/x)"
        urls = _extract_markdown_urls(text)
        evil_urls = [u for u in urls if "evil.com" in u]
        assert len(evil_urls) == 1


# ---------------------------------------------------------------------------
# normalize_tool_call
# ---------------------------------------------------------------------------

class TestNormalizeToolCall:
    def test_read_file_etc_passwd(self):
        sig = normalize_tool_call("read_file", {"path": "/etc/passwd"}, turn=0)
        assert sig is not None
        assert sig.bucket == BUCKET_FILESYSTEM_READ
        assert sig.target == "/etc/passwd"
        assert sig.turn == 0

    def test_read_file_aws(self):
        sig = normalize_tool_call("read_file", {"path": "~/.aws/credentials"}, turn=1)
        assert sig is not None
        assert sig.bucket == BUCKET_FILESYSTEM_READ
        assert "aws/credentials" in sig.target

    def test_execute(self):
        sig = normalize_tool_call("execute", {"cmd": "curl https://evil.com/x"}, turn=0)
        assert sig is not None
        assert sig.bucket == BUCKET_CODE_EXEC
        assert sig.target == "curl"

    def test_fetch(self):
        sig = normalize_tool_call("fetch", {"url": "https://evil.com/steal"}, turn=0)
        assert sig is not None
        assert sig.bucket == BUCKET_NETWORK_EGRESS
        assert "evil.com" in sig.target

    def test_read_env(self):
        sig = normalize_tool_call("read_env", {"var": "AWS_SECRET_ACCESS_KEY"}, turn=0)
        assert sig is not None
        assert sig.bucket == BUCKET_SECRET_ACCESS
        assert sig.target == "AWS_SECRET_ACCESS_KEY"

    def test_unknown_tool(self):
        sig = normalize_tool_call("totally_unknown_tool", {"x": "y"}, turn=0)
        assert sig is not None
        assert sig.bucket == "unknown"
