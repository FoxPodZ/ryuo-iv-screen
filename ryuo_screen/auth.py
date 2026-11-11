# SPDX-License-Identifier: GPL-3.0-or-later
"""Local/LAN access policy, password verification and bounded sessions."""

from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import ipaddress
import secrets
import socket
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Mapping, Optional, Sequence, Tuple
from urllib.parse import urlsplit

from aiohttp import web

from .store import AppConfig


_SCRYPT_N = 16384
_SCRYPT_R = 8
_SCRYPT_P = 1
_SCRYPT_LENGTH = 32
_SCRYPT_MAXMEM = 64 * 1024 * 1024
_MAX_PASSWORD_BYTES = 1024
_DUMMY_SALT = b"ryuo-screen-invalid-verifier"
_DUMMY_DIGEST = b"\x00" * _SCRYPT_LENGTH
_MUTATING = frozenset(("POST", "PUT", "PATCH", "DELETE"))
_BODY_METHODS = frozenset(("POST", "PUT", "PATCH"))
_FORWARDED_HEADERS = frozenset(
    ("Forwarded", "X-Forwarded-For", "X-Forwarded-Host", "X-Forwarded-Proto")
)
_SINGLETON_SECURITY_HEADERS = {
    b"host": "Host",
    b"origin": "Origin",
    b"forwarded": "Forwarded",
    b"x-forwarded-for": "X-Forwarded-For",
    b"x-forwarded-host": "X-Forwarded-Host",
    b"x-forwarded-proto": "X-Forwarded-Proto",
}


def _b64encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _b64decode(value: str) -> bytes:
    if not isinstance(value, str):
        raise TypeError("base64 value must be a string")
    padding = "=" * ((4 - len(value) % 4) % 4)
    return base64.urlsafe_b64decode((value + padding).encode("ascii"))


class PasswordVerifier:
    """Encode and verify a fixed, bounded scrypt password format."""

    @staticmethod
    def hash(password: str) -> str:
        if not isinstance(password, str):
            raise TypeError("password must be a string")
        if not password or "\x00" in password:
            raise ValueError("password cannot be empty or contain NUL")
        try:
            password_bytes = password.encode("utf-8")
        except UnicodeEncodeError as exc:
            raise ValueError("password must be valid Unicode") from exc
        if len(password_bytes) > _MAX_PASSWORD_BYTES:
            raise ValueError("password is too long")
        salt = secrets.token_bytes(16)
        digest = hashlib.scrypt(
            password_bytes,
            salt=salt,
            n=_SCRYPT_N,
            r=_SCRYPT_R,
            p=_SCRYPT_P,
            dklen=_SCRYPT_LENGTH,
            maxmem=_SCRYPT_MAXMEM,
        )
        return "scrypt${}${}${}${}${}".format(
            _SCRYPT_N, _SCRYPT_R, _SCRYPT_P, _b64encode(salt), _b64encode(digest)
        )

    @staticmethod
    def _parse(encoded: Optional[str]) -> Tuple[bytes, bytes, bool]:
        try:
            if not isinstance(encoded, str):
                raise ValueError("not a string")
            algorithm, n_value, r_value, p_value, salt_value, digest_value = (
                encoded.split("$")
            )
            if algorithm != "scrypt":
                raise ValueError("wrong algorithm")
            if (int(n_value), int(r_value), int(p_value)) != (
                _SCRYPT_N,
                _SCRYPT_R,
                _SCRYPT_P,
            ):
                raise ValueError("unsupported parameters")
            salt = _b64decode(salt_value)
            digest = _b64decode(digest_value)
            if len(salt) < 16 or len(salt) > 64 or len(digest) != _SCRYPT_LENGTH:
                raise ValueError("invalid lengths")
            return salt, digest, True
        except (TypeError, ValueError, UnicodeError, base64.binascii.Error):
            return _DUMMY_SALT, _DUMMY_DIGEST, False

    @classmethod
    def valid_format(cls, encoded: Optional[str]) -> bool:
        return cls._parse(encoded)[2]

    @classmethod
    def verify(cls, password: str, encoded: Optional[str]) -> bool:
        salt, expected, valid = cls._parse(encoded)
        password_valid = isinstance(password, str) and "\x00" not in password
        try:
            password_bytes = password.encode("utf-8") if password_valid else b""
        except UnicodeEncodeError:
            password_bytes = b""
            password_valid = False
        if len(password_bytes) > _MAX_PASSWORD_BYTES:
            password_bytes = b""
            password_valid = False
        actual = hashlib.scrypt(
            password_bytes,
            salt=salt,
            n=_SCRYPT_N,
            r=_SCRYPT_R,
            p=_SCRYPT_P,
            dklen=_SCRYPT_LENGTH,
            maxmem=_SCRYPT_MAXMEM,
        )
        matched = hmac.compare_digest(actual, expected)
        return bool(valid and password_valid and matched)


@dataclass(frozen=True)
class Session:
    token: str = field(repr=False)
    csrf_token: str = field(repr=False)
    created_at: float
    expires_at: float


class SessionStore:
    """An in-memory, expiring, count-bounded session set."""

    def __init__(
        self,
        max_sessions: int = 32,
        lifetime: float = 12 * 60 * 60,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if isinstance(max_sessions, bool) or not isinstance(max_sessions, int):
            raise TypeError("max_sessions must be an integer")
        if max_sessions <= 0:
            raise ValueError("max_sessions must be positive")
        if isinstance(lifetime, bool) or not isinstance(lifetime, (int, float)):
            raise TypeError("lifetime must be numeric")
        if lifetime <= 0:
            raise ValueError("lifetime must be positive")
        if not callable(clock):
            raise TypeError("clock must be callable")
        self.max_sessions = max_sessions
        self.lifetime = float(lifetime)
        self._clock = clock
        self._sessions: "OrderedDict[str, Session]" = OrderedDict()
        self._lock = threading.Lock()

    def _prune_locked(self, now: float) -> None:
        expired = [
            token for token, session in self._sessions.items()
            if session.expires_at <= now
        ]
        for token in expired:
            self._sessions.pop(token, None)

    def create(self) -> Session:
        now = float(self._clock())
        session = Session(
            secrets.token_urlsafe(32),
            secrets.token_urlsafe(32),
            now,
            now + self.lifetime,
        )
        with self._lock:
            self._prune_locked(now)
            while len(self._sessions) >= self.max_sessions:
                self._sessions.popitem(last=False)
            self._sessions[session.token] = session
        return session

    def get(self, token: Optional[str]) -> Optional[Session]:
        if not isinstance(token, str) or not token:
            return None
        now = float(self._clock())
        with self._lock:
            self._prune_locked(now)
            return self._sessions.get(token)

    def rotate(self, token: Optional[str]) -> Session:
        self.logout(token)
        return self.create()

    def logout(self, token: Optional[str]) -> None:
        if not isinstance(token, str) or not token:
            return
        with self._lock:
            self._sessions.pop(token, None)

    def remaining(self, session: Session) -> float:
        """Return the truthful remaining lifetime for a still-active session."""
        if not isinstance(session, Session):
            raise TypeError("session must be a Session")
        now = float(self._clock())
        with self._lock:
            self._prune_locked(now)
            current = self._sessions.get(session.token)
            if current is None or current != session:
                return 0.0
            return max(0.0, current.expires_at - now)

    def diagnostics(self) -> Dict[str, int]:
        now = float(self._clock())
        with self._lock:
            self._prune_locked(now)
            return {"active": len(self._sessions), "capacity": self.max_sessions}


def _host_without_port(value: str) -> str:
    if not isinstance(value, str) or not value or any(
        ord(character) < 32 or character.isspace() for character in value
    ):
        raise ValueError("invalid Host header")
    if any(character in value for character in "/\\?#@"):
        raise ValueError("invalid Host header")

    def validate_port(raw: str) -> None:
        if not raw or not raw.isdigit():
            raise ValueError("invalid Host port")
        port = int(raw)
        if port < 1 or port > 65535:
            raise ValueError("invalid Host port")

    if value.startswith("["):
        end = value.find("]")
        if end < 0:
            raise ValueError("invalid IPv6 Host header")
        host = value[1:end]
        try:
            ipaddress.IPv6Address(host.split("%", 1)[0])
        except ValueError as exc:
            raise ValueError("invalid IPv6 Host header") from exc
        suffix = value[end + 1 :]
        if suffix:
            if not suffix.startswith(":"):
                raise ValueError("invalid Host port")
            validate_port(suffix[1:])
        return host.lower()
    if value.count(":") == 1:
        host, port = value.rsplit(":", 1)
        if port.isdigit():
            validate_port(port)
            value = host
    if ":" in value:
        # Bare IPv6 authorities are forbidden; RFC 3986 requires brackets.
        raise ValueError("IPv6 Host header must be bracketed")
    if not value:
        raise ValueError("Host cannot be empty")
    return value.lower().rstrip(".")


def _is_loopback(value: str) -> bool:
    if value.lower().rstrip(".") == "localhost":
        return True
    try:
        return ipaddress.ip_address(value).is_loopback
    except ValueError:
        return False


def _is_wildcard(value: str) -> bool:
    try:
        return ipaddress.ip_address(value).is_unspecified
    except ValueError:
        return value in ("", "*")


@dataclass
class SecurityPolicy:
    bind_host: str
    bind_port: int
    lan_enabled: bool
    verifier: Optional[str] = field(repr=False)
    sessions: SessionStore = field(default_factory=SessionStore)
    trusted_proxies: Tuple[Any, ...] = ()
    cookie_name: str = "ryuo_session"
    _verify_semaphore: Optional[asyncio.Semaphore] = field(
        default=None, init=False, repr=False
    )

    @classmethod
    def from_config(
        cls, config: AppConfig, sessions: Optional[SessionStore] = None
    ) -> "SecurityPolicy":
        if not isinstance(config, AppConfig):
            raise TypeError("config must be an AppConfig")
        networks = []
        if config.trusted_proxy:
            for value in config.trusted_proxy.split(","):
                value = value.strip()
                if not value:
                    raise ValueError("trusted proxy CIDRs cannot be empty")
                try:
                    networks.append(ipaddress.ip_network(value, strict=False))
                except ValueError as exc:
                    raise ValueError("invalid trusted proxy CIDR") from exc
        if config.password_verifier is not None and not PasswordVerifier.valid_format(
            config.password_verifier
        ):
            raise ValueError("LAN access requires a valid password verifier")
        if config.lan_enabled and not config.password_verifier and not networks:
            raise ValueError(
                "LAN access requires a password verifier or trusted proxy"
            )
        return cls(
            config.listen_host,
            config.listen_port,
            config.lan_enabled,
            config.password_verifier,
            sessions or SessionStore(),
            tuple(networks),
        )

    @property
    def requires_authentication(self) -> bool:
        return self.lan_enabled and PasswordVerifier.valid_format(self.verifier)

    @property
    def proxy_only(self) -> bool:
        return (
            self.lan_enabled
            and not self.requires_authentication
            and bool(self.trusted_proxies)
        )

    def validate_bind(self, host: str) -> None:
        if _is_loopback(host):
            return
        if not self.lan_enabled:
            raise ValueError("LAN bind requires explicit lan_enabled policy")
        if not self.requires_authentication and not self.trusted_proxies:
            raise ValueError(
                "LAN bind requires a valid password verifier or trusted proxy"
            )

    def trusts_proxy(self, remote: Optional[str]) -> bool:
        if not remote:
            return False
        try:
            address = ipaddress.ip_address(remote.split("%", 1)[0])
        except ValueError:
            return False
        return any(address in network for network in self.trusted_proxies)

    def forwarded_client(self, value: str, remote: Optional[str]) -> str:
        if not isinstance(value, str) or not value.strip() or remote is None:
            raise ValueError("forwarded client chain is required")
        raw_addresses = [item.strip() for item in value.split(",")]
        if not raw_addresses or any(not item for item in raw_addresses):
            raise ValueError("invalid forwarded client chain")
        addresses = []
        for item in raw_addresses:
            try:
                addresses.append(ipaddress.ip_address(item.split("%", 1)[0]))
            except ValueError as exc:
                raise ValueError("invalid forwarded client") from exc
        try:
            peer = ipaddress.ip_address(remote.split("%", 1)[0])
        except ValueError as exc:
            raise ValueError("invalid proxy peer") from exc
        chain = addresses + [peer]
        while chain and any(chain[-1] in network for network in self.trusted_proxies):
            chain.pop()
        # If every hop is trusted, the left-most forwarded address is still
        # the best available client identity. Never select an earlier,
        # attacker-supplied address after the first untrusted hop.
        return str(chain[-1] if chain else addresses[0])

    def allows_host(self, host: str, from_trusted_proxy: bool = False) -> bool:
        normalized = _host_without_port(host)
        if not self.lan_enabled:
            return _is_loopback(normalized)
        if from_trusted_proxy:
            return True
        if _is_loopback(normalized):
            return True
        try:
            address = ipaddress.ip_address(normalized)
        except ValueError:
            return normalized == self.bind_host.lower().rstrip(".") and not _is_wildcard(
                self.bind_host
            )
        return not (address.is_unspecified or address.is_multicast)

    def diagnostics(self) -> Dict[str, Any]:
        return {
            "lanEnabled": self.lan_enabled,
            "authenticationRequired": self.requires_authentication,
            "trustedProxyCount": len(self.trusted_proxies),
            "sessions": self.sessions.diagnostics(),
        }

    async def verify_password(self, password: str) -> bool:
        semaphore = self._verify_semaphore
        if semaphore is None:
            semaphore = asyncio.Semaphore(2)
            self._verify_semaphore = semaphore
        async with semaphore:
            loop = asyncio.get_running_loop()
            return await loop.run_in_executor(
                None, PasswordVerifier.verify, password, self.verifier
            )


SECURITY_KEY = (
    web.AppKey("ryuo_screen_security", SecurityPolicy)
    if hasattr(web, "AppKey")
    else "ryuo_screen_security"
)
SESSION_KEY = (
    web.RequestKey("ryuo_screen_request_session", object)
    if hasattr(web, "RequestKey")
    else "ryuo_screen_request_session"
)
SCHEME_KEY = (
    web.RequestKey("ryuo_screen_effective_scheme", str)
    if hasattr(web, "RequestKey")
    else "ryuo_screen_effective_scheme"
)
LOCAL_KEY = (
    web.RequestKey("ryuo_screen_local_request", bool)
    if hasattr(web, "RequestKey")
    else "ryuo_screen_local_request"
)


def _json_error(status: int, error: str, message: str) -> web.Response:
    return web.json_response({"error": error, "message": message}, status=status)


def _is_unix_request(request: web.Request) -> bool:
    transport = request.transport
    if transport is None:
        return False
    sock = transport.get_extra_info("socket")
    return bool(sock is not None and getattr(sock, "family", None) == socket.AF_UNIX)


def _origin_matches(origin: str, host: str, scheme: str) -> bool:
    try:
        parsed = urlsplit(origin)
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            return False
        if parsed.username is not None or parsed.password is not None:
            return False
        if parsed.path not in ("", "/") or parsed.query or parsed.fragment:
            return False
        origin_host = parsed.hostname
        if origin_host is None:
            return False
        host_name = _host_without_port(host)
        if origin_host.lower().rstrip(".") != host_name:
            return False
        origin_port = parsed.port
        if origin_port is None:
            origin_port = 443 if parsed.scheme == "https" else 80
        if host.startswith("["):
            end = host.find("]")
            suffix = host[end + 1 :]
            host_port = int(suffix[1:]) if suffix.startswith(":") else None
        elif host.count(":") == 1 and host.rsplit(":", 1)[1].isdigit():
            host_port = int(host.rsplit(":", 1)[1])
        else:
            host_port = None
        if host_port is None:
            host_port = 443 if scheme == "https" else 80
        return parsed.scheme == scheme and origin_port == host_port
    except (TypeError, ValueError):
        return False


def _reject_duplicate_security_headers(request: web.Request) -> None:
    """Reject ambiguous raw fields before the multidict selects a value."""
    seen = set()
    for raw_name, _raw_value in request.raw_headers:
        normalized = raw_name.lower()
        display_name = _SINGLETON_SECURITY_HEADERS.get(normalized)
        if display_name is None:
            continue
        if normalized in seen:
            raise PermissionError("duplicate {} header".format(display_name))
        seen.add(normalized)


def _forwarded_context(
    request: web.Request, policy: SecurityPolicy
) -> Tuple[str, str, bool, Optional[str]]:
    if "Forwarded" in request.headers:
        raise PermissionError("standard Forwarded header is not supported")
    has_forwarded = any(name in request.headers for name in _FORWARDED_HEADERS)
    trusted = policy.trusts_proxy(request.remote)
    if has_forwarded and not trusted:
        raise PermissionError("forwarded headers require a trusted proxy")
    host = request.headers.get("Host", "")
    scheme = request.scheme
    client = request.remote
    if trusted:
        forwarded_host = request.headers.get("X-Forwarded-Host")
        forwarded_proto = request.headers.get("X-Forwarded-Proto")
        forwarded_for = request.headers.get("X-Forwarded-For")
        if (forwarded_host is not None or forwarded_proto is not None) and forwarded_for is None:
            raise PermissionError("forwarded client is required")
        if forwarded_host is not None:
            if "," in forwarded_host:
                raise PermissionError("ambiguous forwarded host")
            host = forwarded_host.strip()
        if forwarded_proto is not None:
            if "," in forwarded_proto or forwarded_proto.strip() not in ("http", "https"):
                raise PermissionError("invalid forwarded protocol")
            scheme = forwarded_proto.strip()
        if forwarded_for is not None:
            try:
                client = policy.forwarded_client(forwarded_for, request.remote)
            except ValueError as exc:
                raise PermissionError("invalid forwarded client") from exc
    return host, scheme, trusted, client


@web.middleware
async def security_middleware(request: web.Request, handler):
    policy: SecurityPolicy = request.app[SECURITY_KEY]
    try:
        _reject_duplicate_security_headers(request)
        host, scheme, trusted, client = _forwarded_context(request, policy)
        if not policy.allows_host(host, from_trusted_proxy=trusted):
            raise PermissionError("Host is not allowed")
        origin = request.headers.get("Origin")
        if origin is not None and not _origin_matches(origin, host, scheme):
            raise PermissionError("Origin does not match Host")
    except (PermissionError, ValueError) as exc:
        return _json_error(403, "forbidden", str(exc))

    request[SCHEME_KEY] = scheme
    local_request = bool(client and _is_loopback(client.split("%", 1)[0]))
    request[LOCAL_KEY] = local_request
    if request.method in _BODY_METHODS:
        content_type = request.content_type.lower()
        expected_type = (
            "application/octet-stream"
            if request.path == "/api/v1/media/upload"
            else "application/json"
        )
        if content_type != expected_type:
            return _json_error(415, "unsupported_media_type", "request body type is not allowed")

    if _is_unix_request(request) or local_request or not policy.requires_authentication:
        if policy.proxy_only and not (_is_unix_request(request) or local_request or trusted):
            return _json_error(403, "forbidden", "request must arrive through a trusted proxy")
        request[SESSION_KEY] = None
        return await handler(request)

    token = request.cookies.get(policy.cookie_name)
    session = policy.sessions.get(token)
    request[SESSION_KEY] = session
    public = request.path in (
        "/api/v1/auth/login",
        "/api/v1/auth/status",
    )
    public_static = (
        request.method in ("GET", "HEAD")
        and (request.path == "/" or request.path.startswith("/assets/"))
    )
    if public or public_static:
        return await handler(request)
    if session is None:
        return _json_error(401, "authentication_required", "authentication is required")
    if request.method in _MUTATING:
        supplied = request.headers.get("X-CSRF-Token", "")
        if not hmac.compare_digest(supplied, session.csrf_token):
            return _json_error(403, "csrf_failed", "a valid CSRF token is required")
    return await handler(request)


async def auth_status(request: web.Request) -> web.Response:
    policy: SecurityPolicy = request.app[SECURITY_KEY]
    if (
        not policy.requires_authentication
        or _is_unix_request(request)
        or request.get(LOCAL_KEY, False)
    ):
        return web.json_response(
            {"required": False, "authenticated": True, "csrfToken": None}
        )
    session = request.get(SESSION_KEY)
    return web.json_response(
        {
            "required": True,
            "authenticated": session is not None,
            "csrfToken": session.csrf_token if session is not None else None,
            "expiresIn": policy.sessions.remaining(session) if session is not None else 0.0,
        }
    )


async def auth_login(request: web.Request) -> web.Response:
    policy: SecurityPolicy = request.app[SECURITY_KEY]
    if (
        not policy.requires_authentication
        or _is_unix_request(request)
        or request.get(LOCAL_KEY, False)
    ):
        return web.json_response(
            {"required": False, "authenticated": True, "csrfToken": None}
        )
    try:
        document = await request.json()
    except Exception:
        document = {}
    password = document.get("password") if isinstance(document, Mapping) else None
    if not await policy.verify_password(
        password if isinstance(password, str) else ""
    ):
        return _json_error(401, "invalid_credentials", "invalid credentials")
    previous = request.cookies.get(policy.cookie_name)
    session = policy.sessions.rotate(previous)
    response = web.json_response(
        {
            "required": True,
            "authenticated": True,
            "csrfToken": session.csrf_token,
            "expiresIn": policy.sessions.remaining(session),
        }
    )
    response.set_cookie(
        policy.cookie_name,
        session.token,
        max_age=int(policy.sessions.lifetime),
        httponly=True,
        secure=request.get(SCHEME_KEY) == "https",
        samesite="Strict",
        path="/",
    )
    return response


async def auth_logout(request: web.Request) -> web.Response:
    policy: SecurityPolicy = request.app[SECURITY_KEY]
    token = request.cookies.get(policy.cookie_name)
    policy.sessions.logout(token)
    response = web.json_response({"authenticated": False})
    response.del_cookie(
        policy.cookie_name,
        path="/",
        secure=request.get(SCHEME_KEY) == "https",
        httponly=True,
        samesite="Strict",
    )
    return response


__all__ = [
    "PasswordVerifier",
    "SECURITY_KEY",
    "SecurityPolicy",
    "Session",
    "SessionStore",
    "auth_login",
    "auth_logout",
    "auth_status",
    "security_middleware",
]
