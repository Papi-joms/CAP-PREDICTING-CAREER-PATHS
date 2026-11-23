"""Seed password checks do not require MySQL or real secrets."""

import pytest

from database import seed_demo


@pytest.mark.parametrize("password", ["", "short", "x" * 73, "é" * 37])
def test_invalid_demo_password(monkeypatch, password):
    monkeypatch.setattr(seed_demo, "load_config", lambda: None)
    monkeypatch.setenv("DEMO_STUDENT_PASSWORD", password)
    monkeypatch.setenv("DEMO_COUNSELOR_PASSWORD", "a-different-test-password")
    with pytest.raises(ValueError):
        seed_demo.read_demo_passwords()


def test_distinct_passwords_and_unicode_byte_boundary(monkeypatch):
    monkeypatch.setattr(seed_demo, "load_config", lambda: None)
    monkeypatch.setenv("DEMO_STUDENT_PASSWORD", "é" * 36)
    monkeypatch.setenv("DEMO_COUNSELOR_PASSWORD", "test-counselor-password")
    assert seed_demo.read_demo_passwords()[0] == "é" * 36
    monkeypatch.setenv("DEMO_COUNSELOR_PASSWORD", "é" * 36)
    with pytest.raises(ValueError):
        seed_demo.read_demo_passwords()
