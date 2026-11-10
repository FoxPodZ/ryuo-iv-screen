# SPDX-License-Identifier: GPL-3.0-or-later
import hashlib

import pytest

from ryuo_screen.auth import PasswordVerifier, SessionStore


class Clock:
    def __init__(self):
        self.value = 100.0

    def __call__(self):
        return self.value


def test_scrypt_verifiers_use_random_salts_and_never_contain_plaintext():
    first = PasswordVerifier.hash("correct horse battery staple")
    second = PasswordVerifier.hash("correct horse battery staple")

    assert first != second
    assert "correct horse battery staple" not in first
    assert PasswordVerifier.verify("correct horse battery staple", first) is True
    assert PasswordVerifier.verify("wrong", first) is False


def test_malformed_verifier_still_runs_one_bounded_scrypt(monkeypatch):
    calls = []

    def fake_scrypt(password, *, salt, n, r, p, dklen, maxmem=0):
        calls.append((bytes(password), bytes(salt), n, r, p, dklen, maxmem))
        return b"x" * dklen

    monkeypatch.setattr(hashlib, "scrypt", fake_scrypt)

    assert PasswordVerifier.verify("guess", "not-a-verifier") is False
    assert len(calls) == 1
    assert calls[0][2:6] == (16384, 8, 1, 32)


def test_invalid_or_oversized_passwords_are_bounded_and_still_verify_once(monkeypatch):
    calls = []

    def fake_scrypt(password, *, salt, n, r, p, dklen, maxmem=0):
        calls.append(bytes(password))
        return b"x" * dklen

    monkeypatch.setattr(hashlib, "scrypt", fake_scrypt)

    assert PasswordVerifier.verify("\ud800", "not-a-verifier") is False
    assert calls == [b""]
    with pytest.raises(ValueError, match="long"):
        PasswordVerifier.hash("x" * 2048)


def test_sessions_rotate_expire_and_keep_only_a_bounded_set():
    clock = Clock()
    sessions = SessionStore(max_sessions=2, lifetime=10.0, clock=clock)

    first = sessions.create()
    second = sessions.create()
    third = sessions.create()
    assert sessions.get(first.token) is None
    assert sessions.get(second.token) == second
    assert sessions.get(third.token) == third

    rotated = sessions.rotate(second.token)
    assert sessions.get(second.token) is None
    assert sessions.get(rotated.token) == rotated
    assert rotated.token != second.token
    assert rotated.csrf_token != second.csrf_token

    sessions.logout(rotated.token)
    assert sessions.get(rotated.token) is None

    clock.value += 11.0
    assert sessions.get(third.token) is None
    assert sessions.diagnostics() == {"active": 0, "capacity": 2}
    assert third.token not in repr(sessions.diagnostics())
    assert third.csrf_token not in repr(sessions.diagnostics())
    assert third.token not in repr(third)
    assert third.csrf_token not in repr(third)


@pytest.mark.parametrize("max_sessions,lifetime", [(0, 10), (1, 0), (True, 10)])
def test_session_bounds_reject_invalid_values(max_sessions, lifetime):
    with pytest.raises((TypeError, ValueError)):
        SessionStore(max_sessions=max_sessions, lifetime=lifetime)
