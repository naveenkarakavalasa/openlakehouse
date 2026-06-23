import pytest

from openlakehouse.core.errors import IdentityResolutionError
from openlakehouse.identity.resolver import IdentityResolver


def test_resolves_from_explicit_identity():
    resolver = IdentityResolver(identity="claude-desktop-analyst")
    assert resolver.current_identity() == "claude-desktop-analyst"


def test_resolves_from_env_var(monkeypatch):
    monkeypatch.setenv(IdentityResolver.ENV_VAR, "claude-code-admin")
    resolver = IdentityResolver()
    assert resolver.current_identity() == "claude-code-admin"


def test_missing_identity_raises(monkeypatch):
    monkeypatch.delenv(IdentityResolver.ENV_VAR, raising=False)
    with pytest.raises(IdentityResolutionError):
        IdentityResolver()
