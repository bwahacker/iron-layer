"""Unit tests for the wildcard MCP fake results."""
import pytest
from iron_layer.wildcard_mcp.fake_results import get_fake_result


class TestFakeResults:
    """Fake results must be: deterministic, safe (no real secrets), plausible."""

    # Determinism
    def test_deterministic(self):
        r1 = get_fake_result("read_file", {"path": "/etc/passwd"})
        r2 = get_fake_result("read_file", {"path": "/etc/passwd"})
        assert r1 == r2

    def test_different_args_different_result(self):
        r1 = get_fake_result("read_file", {"path": "/etc/passwd"})
        r2 = get_fake_result("read_file", {"path": "/etc/hosts"})
        assert r1 != r2

    # Safety: all "secrets" must be obviously fake
    def test_no_real_aws_key_shape(self):
        r = get_fake_result("read_env", {"var": "AWS_ACCESS_KEY_ID"})
        # Real keys start with AKIA; we prefix FAKIA or FAKIAFAKE
        assert r.startswith("FAKI") or "FAKE" in r.upper()

    def test_aws_credentials_lure(self):
        r = get_fake_result("read_file", {"path": "~/.aws/credentials"})
        assert "FAKE" in r
        assert "aws_access_key_id" in r.lower()

    def test_env_lure(self):
        r = get_fake_result("read_file", {"path": ".env"})
        assert "FAKE" in r
        assert "SECRET_KEY" in r or "DATABASE_URL" in r

    def test_ssh_key_lure(self):
        r = get_fake_result("read_file", {"path": "~/.ssh/id_rsa"})
        assert "BEGIN" in r and "FAKE" in r

    def test_etc_passwd_lure(self):
        r = get_fake_result("read_file", {"path": "/etc/passwd"})
        assert "root:" in r

    # Plausibility
    def test_list_directory_root(self):
        r = get_fake_result("list_directory", {"path": "/"})
        assert "etc" in r or "home" in r

    def test_fetch_returns_200(self):
        r = get_fake_result("fetch", {"url": "https://evil.com/collect"})
        assert "200" in r

    def test_send_email_confirms(self):
        r = get_fake_result("send_email", {"to": "a@b.com", "subject": "test", "body": "hi"})
        assert "a@b.com" in r

    def test_unknown_tool_returns_something(self):
        r = get_fake_result("totally_unknown_tool", {"x": "y"})
        assert len(r) > 0

    def test_list_users_returns_table(self):
        r = get_fake_result("list_users", {})
        assert "admin" in r.lower()

    def test_get_api_key_returns_fake(self):
        r = get_fake_result("get_api_key", {"service": "stripe"})
        assert "FAKE" in r and "stripe" in r.lower()
