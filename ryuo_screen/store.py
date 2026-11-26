# SPDX-License-Identifier: GPL-3.0-or-later
"""Versioned, atomic persistence for daemon state and named profiles."""

import json
import os
import re
import tempfile
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple, Union

try:  # pragma: no cover - selected by the interpreter version
    import tomllib
except ImportError:  # Python 3.8-3.10
    import tomli as tomllib  # type: ignore

import ryuo_proto as proto
from ryuo_proto import MODE_FULL, MODE_SPLIT, PLAY_MODES, PLAY_SINGLE

from .models import SensorRef


SCHEMA_VERSION = 1
MAX_SLOT_LABEL_LENGTH = 32
STATE_MODE = 0o640
SECRET_MODE = 0o600
_SLUG = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_COLOR = re.compile(r"^#[0-9A-Fa-f]{6}(?:[0-9A-Fa-f]{2})?$")
_RGB_MODES = frozenset(("off", "hue", "thermal"))
_RGB_TARGETS = frozenset(("title", "value", "both"))
_TEMPERATURE_UNITS = frozenset(("Celsius", "Fahrenheit"))


class ProfileConflict(ValueError):
    """A profile slug already exists."""


class ProfileNotFound(KeyError):
    """A requested profile does not exist."""


def _integer(name: str, value: Any, low: int, high: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError("{} must be an integer".format(name))
    if not low <= value <= high:
        raise ValueError("{} must be in {}..{}".format(name, low, high))
    return value


def _string(name: str, value: Any, allow_empty: bool = False) -> str:
    if not isinstance(value, str):
        raise TypeError("{} must be a string".format(name))
    if "\x00" in value:
        raise ValueError("{} cannot contain NUL".format(name))
    if not allow_empty and not value:
        raise ValueError("{} cannot be empty".format(name))
    return value


def _color(name: str, value: Any) -> str:
    value = _string(name, value)
    if not _COLOR.fullmatch(value):
        raise ValueError("{} must be #RRGGBB or #AARRGGBB".format(name))
    return value.upper()


def _sync_directory(directory: Path) -> None:
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
    fd = os.open(str(directory), flags)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _atomic_write_bytes(
    path: Path, payload: bytes, mode: int, exclusive: bool = False
) -> None:
    """Write beside the target, fsync, then publish it atomically."""

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o750)
    fd, temporary = tempfile.mkstemp(
        prefix=".{}.".format(path.name), suffix=".tmp", dir=str(path.parent)
    )
    temporary_path = Path(temporary)
    published = False
    try:
        os.fchmod(fd, mode)
        with os.fdopen(fd, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        if exclusive:
            try:
                os.link(str(temporary_path), str(path))
            except FileExistsError as exc:
                raise ProfileConflict("profile {!r} already exists".format(path.stem)) from exc
            temporary_path.unlink()
        else:
            os.replace(str(temporary_path), str(path))
        published = True
        _sync_directory(path.parent)
    finally:
        if not published and temporary_path.exists():
            temporary_path.unlink()


def _atomic_write_json(
    path: Path, document: Mapping[str, Any], mode: int = STATE_MODE, exclusive: bool = False
) -> None:
    payload = (
        json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
    _atomic_write_bytes(path, payload, mode, exclusive=exclusive)


def write_secret(path: Union[str, Path], secret: str) -> None:
    """Persist an already-derived secret/verifier with owner-only permissions."""

    _string("secret", secret)
    _atomic_write_bytes(Path(path), secret.encode("utf-8"), SECRET_MODE)


@dataclass(frozen=True)
class AppConfig:
    """Static daemon configuration loaded from the system TOML file."""

    config_path: Path = Path("/etc/ryuo-screen/config.toml")
    data_dir: Path = Path("/var/lib/ryuo-screen")
    listen_host: str = "127.0.0.1"
    listen_port: int = 8746
    gpu_provider: str = "auto"
    gpu_selector: Optional[str] = None
    motherboard_sensor: Optional[SensorRef] = None
    lan_enabled: bool = False
    password_verifier: Optional[str] = None
    trusted_proxy: Optional[str] = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "config_path", Path(self.config_path))
        object.__setattr__(self, "data_dir", Path(self.data_dir))
        _string("listen_host", self.listen_host)
        _integer("listen_port", self.listen_port, 1, 65535)
        if self.gpu_provider not in ("auto", "amd", "nvidia"):
            raise ValueError("gpu_provider must be auto, amd or nvidia")
        if self.gpu_selector is not None:
            _string("gpu_selector", self.gpu_selector)
        if self.motherboard_sensor is not None and not isinstance(
            self.motherboard_sensor, SensorRef
        ):
            raise TypeError("motherboard_sensor must be a SensorRef")
        if not isinstance(self.lan_enabled, bool):
            raise TypeError("lan_enabled must be a boolean")
        if self.password_verifier is not None:
            _string("password_verifier", self.password_verifier)
        if self.trusted_proxy is not None:
            _string("trusted_proxy", self.trusted_proxy)

    @property
    def state_path(self) -> Path:
        return self.data_dir / "state.json"

    @property
    def profiles_dir(self) -> Path:
        return self.data_dir / "profiles"

    @property
    def media_dir(self) -> Path:
        return self.data_dir / "media"

    @classmethod
    def load(cls, path: Union[str, Path] = "/etc/ryuo-screen/config.toml") -> "AppConfig":
        config_path = Path(path)
        if not config_path.exists():
            return cls(config_path=config_path)
        with config_path.open("rb") as handle:
            document = tomllib.load(handle)
        if not isinstance(document, dict):
            raise ValueError("configuration root must be a table")

        sensor = document.get("motherboard_sensor")
        motherboard = None
        if sensor is not None:
            if not isinstance(sensor, dict):
                raise TypeError("motherboard_sensor must be a table")
            motherboard = SensorRef.from_dict(sensor)
        security = document.get("security", {})
        if not isinstance(security, dict):
            raise TypeError("security must be a table")
        return cls(
            config_path=config_path,
            data_dir=Path(document.get("data_dir", "/var/lib/ryuo-screen")),
            listen_host=document.get("listen_host", "127.0.0.1"),
            listen_port=document.get("listen_port", 8746),
            gpu_provider=document.get("gpu_provider", "auto"),
            gpu_selector=document.get("gpu_selector"),
            motherboard_sensor=motherboard,
            lan_enabled=document.get("lan_enabled", False),
            password_verifier=security.get("password_verifier"),
            trusted_proxy=security.get("trusted_proxy"),
        )


@dataclass(frozen=True)
class SlotAssignment:
    enabled: bool = False
    measurement_id: str = ""
    widget: str = ""
    label: Optional[str] = None

    def __post_init__(self) -> None:
        if not isinstance(self.enabled, bool):
            raise TypeError("slot enabled must be a boolean")
        _string("slot measurement_id", self.measurement_id, allow_empty=True)
        _string("slot widget", self.widget, allow_empty=True)
        if self.label is not None:
            _string("slot label", self.label)
            if len(self.label) > MAX_SLOT_LABEL_LENGTH:
                raise ValueError(
                    "slot label must be at most {} characters".format(
                        MAX_SLOT_LABEL_LENGTH
                    )
                )
        if self.enabled and (not self.measurement_id or not self.widget):
            raise ValueError("enabled slot requires measurement_id and widget")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "enabled": self.enabled,
            "measurement_id": self.measurement_id,
            "widget": self.widget,
            "label": self.label,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "SlotAssignment":
        if isinstance(value, SlotAssignment):
            return value
        if not isinstance(value, Mapping):
            raise TypeError("slot assignment must be an object")
        allowed = {"enabled", "measurement_id", "widget", "label"}
        unknown = set(value) - allowed
        if unknown:
            raise ValueError("unknown slot fields: {}".format(", ".join(sorted(unknown))))
        return cls(
            enabled=value.get("enabled", False),
            measurement_id=value.get("measurement_id", ""),
            widget=value.get("widget", ""),
            label=value.get("label"),
        )


def _empty_slots() -> Tuple[SlotAssignment, ...]:
    return tuple(SlotAssignment() for _ in range(6))


def _media_zones(value: Any) -> Tuple[Tuple[str, ...], ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise TypeError("media must be a sequence of zones")
    zones: List[Tuple[str, ...]] = []
    for zone in value:
        if isinstance(zone, (str, bytes)) or not isinstance(zone, Sequence):
            raise TypeError("each media zone must be a sequence")
        names = []
        for name in zone:
            name = _string("media filename", name)
            if name in (".", "..") or "/" in name or "\\" in name:
                raise ValueError("media entries must be filenames, not paths")
            names.append(name)
        zones.append(tuple(names))
    if len(zones) not in (1, 2):
        raise ValueError("media must contain one or two zones")
    return tuple(zones)


def _playback_modes(value: Any) -> Tuple[str, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise TypeError("playback_modes must be a sequence")
    modes = tuple(value)
    if not modes or any(mode not in PLAY_MODES for mode in modes):
        raise ValueError("playback mode must be Single, Random or Cycle")
    return modes


def _slots(value: Any) -> Tuple[SlotAssignment, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise TypeError("slots must be a sequence")
    result = tuple(SlotAssignment.from_dict(item) for item in value)
    if len(result) != 6:
        raise ValueError("screen state requires exactly six slots")
    return result


def _selectors(value: Any) -> Dict[str, SensorRef]:
    if not isinstance(value, Mapping):
        raise TypeError("sensor_selectors must be an object")
    result: Dict[str, SensorRef] = {}
    for key, ref in value.items():
        key = _string("sensor selector key", key)
        result[key] = ref if isinstance(ref, SensorRef) else SensorRef.from_dict(ref)
    return result


def _validate_screen(value: Any) -> None:
    if value.screen_mode not in (MODE_FULL, MODE_SPLIT):
        raise ValueError("screen mode must be Full Screen or Screen Splitting")
    expected_zones = 2 if value.screen_mode == MODE_SPLIT else 1
    if len(value.media) != expected_zones:
        raise ValueError("screen mode and media zone count disagree")
    if len(value.playback_modes) != expected_zones:
        raise ValueError("screen mode and playback zone count disagree")
    if any(not zone and mode != PLAY_SINGLE for zone, mode in zip(value.media, value.playback_modes)):
        raise ValueError("empty media zone requires Single playback")
    if len(value.title_colors) != expected_zones or len(value.content_colors) != expected_zones:
        raise ValueError("screen mode and color zone count disagree")


@dataclass(frozen=True)
class ScreenState:
    schema_version: int = SCHEMA_VERSION
    revision: int = 0
    active_profile: Optional[str] = None
    screen_mode: str = MODE_FULL
    media: Tuple[Tuple[str, ...], ...] = ((),)
    playback_modes: Tuple[str, ...] = (PLAY_SINGLE,)
    slots: Tuple[SlotAssignment, ...] = field(default_factory=_empty_slots)
    brightness: int = 85
    temperature_unit: str = "Celsius"
    refresh_interval: float = 1.0
    title_colors: Tuple[str, ...] = ("#E5252B",)
    content_colors: Tuple[str, ...] = ("#FFFFFF",)
    opacity: int = 100
    rgb_mode: str = "off"
    rgb_target: str = "value"
    thermal_source: str = "cpu.temperature"
    sensor_selectors: Mapping[str, SensorRef] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _integer("schema_version", self.schema_version, SCHEMA_VERSION, SCHEMA_VERSION)
        _integer("revision", self.revision, 0, 2 ** 63 - 1)
        if self.active_profile is not None:
            _string("active_profile", self.active_profile)
        object.__setattr__(self, "media", _media_zones(self.media))
        object.__setattr__(self, "playback_modes", _playback_modes(self.playback_modes))
        object.__setattr__(self, "slots", _slots(self.slots))
        _integer("brightness", self.brightness, 0, 102)
        if self.temperature_unit not in _TEMPERATURE_UNITS:
            raise ValueError("temperature_unit must be Celsius or Fahrenheit")
        if isinstance(self.refresh_interval, bool) or not isinstance(
            self.refresh_interval, (int, float)
        ):
            raise TypeError("refresh_interval must be a number")
        if not 0 < float(self.refresh_interval) <= 60:
            raise ValueError("refresh_interval must be in (0, 60]")
        object.__setattr__(
            self, "title_colors", tuple(_color("title color", item) for item in self.title_colors)
        )
        object.__setattr__(
            self,
            "content_colors",
            tuple(_color("content color", item) for item in self.content_colors),
        )
        _integer("opacity", self.opacity, 0, 100)
        if self.rgb_mode not in _RGB_MODES:
            raise ValueError("rgb_mode must be off, hue or thermal")
        if self.rgb_target not in _RGB_TARGETS:
            raise ValueError("rgb_target must be title, value or both")
        _string("thermal_source", self.thermal_source)
        object.__setattr__(self, "sensor_selectors", _selectors(self.sensor_selectors))
        _validate_screen(self)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "revision": self.revision,
            "active_profile": self.active_profile,
            "screen_mode": self.screen_mode,
            "media": [list(zone) for zone in self.media],
            "playback_modes": list(self.playback_modes),
            "slots": [slot.to_dict() for slot in self.slots],
            "brightness": self.brightness,
            "temperature_unit": self.temperature_unit,
            "refresh_interval": self.refresh_interval,
            "title_colors": list(self.title_colors),
            "content_colors": list(self.content_colors),
            "opacity": self.opacity,
            "rgb_mode": self.rgb_mode,
            "rgb_target": self.rgb_target,
            "thermal_source": self.thermal_source,
            "sensor_selectors": {
                key: ref.to_dict() for key, ref in sorted(self.sensor_selectors.items())
            },
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "ScreenState":
        if not isinstance(value, Mapping):
            raise TypeError("screen state must be an object")
        allowed = set(cls().to_dict())
        unknown = set(value) - allowed
        if unknown:
            raise ValueError("unknown state fields: {}".format(", ".join(sorted(unknown))))
        return cls(**dict(value))


def _normalize_saved_playlists(document):
    """Earlier state files could persist an empty Random or Cycle playlist."""
    if not isinstance(document, dict):
        raise TypeError("stored configuration must be an object")
    media = document.get("media", [[]])
    modes = document.get("playback_modes")
    if isinstance(media, list) and isinstance(modes, list) and len(media) == len(modes):
        document["playback_modes"] = [
            PLAY_SINGLE if zone == [] and mode in PLAY_MODES else mode
            for zone, mode in zip(media, modes)
        ]
    return document


class StateStore:
    def __init__(self, path: Union[str, Path]):
        self.path = Path(path)
        self.last_error: Optional[str] = None

    def load(self) -> ScreenState:
        self.last_error = None
        if not self.path.exists():
            return ScreenState()
        try:
            with self.path.open("r", encoding="utf-8") as handle:
                document = json.load(handle)
            if not isinstance(document, dict):
                raise TypeError("state root must be an object")
            document = self._migrate(document)
            state = ScreenState.from_dict(document)
            self._validate_wire(state)
            return state
        except (OSError, UnicodeError, json.JSONDecodeError, TypeError, ValueError, KeyError) as exc:
            self.last_error = "state load failed: {}".format(exc)
            return ScreenState()

    def save(self, state: ScreenState) -> None:
        if not isinstance(state, ScreenState):
            raise TypeError("state must be a ScreenState")
        self._validate_wire(state)
        _atomic_write_json(self.path, state.to_dict(), STATE_MODE)
        self.last_error = None

    @staticmethod
    def _validate_wire(state: ScreenState) -> None:
        # State is persisted before device admission so reconnect can apply it.
        # Therefore reject anything that cannot fit the firmware's single
        # report before the atomic write, using the widest supported sequence.
        proto.request(
            proto.POST,
            proto.RES_CONFIG,
            proto.config_payload_from_state(state),
            seq=2_147_483_647,
        )

    @staticmethod
    def _migrate(document: Mapping[str, Any]) -> Dict[str, Any]:
        migrated = dict(document)
        version = migrated.get("schema_version", 0)
        if isinstance(version, bool) or not isinstance(version, int):
            raise TypeError("state schema version must be an integer")
        if version > SCHEMA_VERSION:
            raise ValueError("unsupported state schema version {}".format(version))
        if version < 0:
            raise ValueError("invalid state schema version {}".format(version))
        if version == 0:
            if "profile" in migrated and "active_profile" not in migrated:
                migrated["active_profile"] = migrated.pop("profile")
            if "assignments" in migrated and "slots" not in migrated:
                migrated["slots"] = migrated.pop("assignments")
            migrated["schema_version"] = 1
        return _normalize_saved_playlists(migrated)


@dataclass(frozen=True)
class Profile:
    slug: str
    name: str
    schema_version: int = SCHEMA_VERSION
    screen_mode: str = MODE_FULL
    media: Tuple[Tuple[str, ...], ...] = ((),)
    playback_modes: Tuple[str, ...] = (PLAY_SINGLE,)
    slots: Tuple[SlotAssignment, ...] = field(default_factory=_empty_slots)
    brightness: int = 85
    temperature_unit: str = "Celsius"
    refresh_interval: float = 1.0
    title_colors: Tuple[str, ...] = ("#E5252B",)
    content_colors: Tuple[str, ...] = ("#FFFFFF",)
    opacity: int = 100
    rgb_mode: str = "off"
    rgb_target: str = "value"
    thermal_source: str = "cpu.temperature"
    sensor_selectors: Mapping[str, SensorRef] = field(default_factory=dict)
    factory: bool = False

    def __post_init__(self) -> None:
        _string("profile slug", self.slug)
        if not _SLUG.fullmatch(self.slug):
            raise ValueError("profile slug must contain lowercase letters, digits and dashes")
        _string("profile name", self.name)
        if not isinstance(self.factory, bool):
            raise TypeError("profile factory must be a boolean")
        state = ScreenState(
            schema_version=self.schema_version,
            screen_mode=self.screen_mode,
            media=self.media,
            playback_modes=self.playback_modes,
            slots=self.slots,
            brightness=self.brightness,
            temperature_unit=self.temperature_unit,
            refresh_interval=self.refresh_interval,
            title_colors=self.title_colors,
            content_colors=self.content_colors,
            opacity=self.opacity,
            rgb_mode=self.rgb_mode,
            rgb_target=self.rgb_target,
            thermal_source=self.thermal_source,
            sensor_selectors=self.sensor_selectors,
        )
        for field_name in (
            "media",
            "playback_modes",
            "slots",
            "title_colors",
            "content_colors",
            "sensor_selectors",
        ):
            object.__setattr__(self, field_name, getattr(state, field_name))

    def to_dict(self) -> Dict[str, Any]:
        state = ScreenState(
            schema_version=self.schema_version,
            screen_mode=self.screen_mode,
            media=self.media,
            playback_modes=self.playback_modes,
            slots=self.slots,
            brightness=self.brightness,
            temperature_unit=self.temperature_unit,
            refresh_interval=self.refresh_interval,
            title_colors=self.title_colors,
            content_colors=self.content_colors,
            opacity=self.opacity,
            rgb_mode=self.rgb_mode,
            rgb_target=self.rgb_target,
            thermal_source=self.thermal_source,
            sensor_selectors=self.sensor_selectors,
        ).to_dict()
        state.pop("revision")
        state.pop("active_profile")
        return {"slug": self.slug, "name": self.name, "factory": self.factory, **state}

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "Profile":
        if isinstance(value, Profile):
            return value
        if not isinstance(value, Mapping):
            raise TypeError("profile must be an object")
        allowed = set(cls("valid", "Valid").to_dict())
        unknown = set(value) - allowed
        if unknown:
            raise ValueError("unknown profile fields: {}".format(", ".join(sorted(unknown))))
        version = value.get("schema_version", SCHEMA_VERSION)
        if version != SCHEMA_VERSION:
            raise ValueError("unsupported profile schema version {}".format(version))
        return cls(**dict(value))


class ProfileStore:
    def __init__(
        self,
        directory: Union[str, Path],
        runtime_secrets: Optional[Mapping[str, str]] = None,
    ):
        self.directory = Path(directory)
        self.runtime_secrets = dict(runtime_secrets or {})
        self._factory = {profile.slug: profile for profile in default_miku_profiles()}

    def _path(self, slug: str) -> Path:
        _string("profile slug", slug)
        if not _SLUG.fullmatch(slug):
            raise ValueError("invalid profile slug")
        return self.directory / "{}.json".format(slug)

    def list(self) -> List[Profile]:
        profiles = [replace(profile) for profile in self._factory.values()]
        for path in sorted(self.directory.glob("*.json")):
            if path.stem in self._factory:
                continue
            try:
                profiles.append(self._read(path))
            except (OSError, UnicodeError, json.JSONDecodeError, TypeError, ValueError, KeyError):
                continue
        return sorted(profiles, key=lambda item: item.slug)

    def get(self, slug: str) -> Profile:
        path = self._path(slug)
        if slug in self._factory:
            return replace(self._factory[slug])
        if not path.is_file():
            raise ProfileNotFound(slug)
        return self._read(path)

    def create(self, profile: Profile) -> Profile:
        profile = Profile.from_dict(profile.to_dict() if isinstance(profile, Profile) else profile)
        self._require_custom_slug(profile.slug)
        _atomic_write_json(
            self._path(profile.slug), profile.to_dict(), STATE_MODE, exclusive=True
        )
        return profile

    def update(self, slug: str, profile: Profile) -> Profile:
        old_path = self._path(slug)
        current = self.get(slug)
        if current.factory:
            raise PermissionError("factory profiles cannot be updated")
        profile = Profile.from_dict(profile.to_dict() if isinstance(profile, Profile) else profile)
        self._require_custom_slug(profile.slug)
        new_path = self._path(profile.slug)
        if new_path == old_path:
            _atomic_write_json(old_path, profile.to_dict(), STATE_MODE)
        else:
            _atomic_write_json(new_path, profile.to_dict(), STATE_MODE, exclusive=True)
            try:
                old_path.unlink()
                _sync_directory(self.directory)
            except Exception:
                # The old profile is retained on a crash/failure; never lose both copies.
                raise
        return profile

    def _require_custom_slug(self, slug: str) -> None:
        if slug in self._factory:
            raise ProfileConflict("profile slug is reserved: {}".format(slug))

    def duplicate(self, slug: str, name: str, new_slug: Optional[str] = None) -> Profile:
        source = self.get(slug)
        destination = new_slug or self.slugify(name)
        return self.create(replace(source, slug=destination, name=name, factory=False))

    def delete(self, slug: str) -> None:
        profile = self.get(slug)
        if profile.factory:
            raise PermissionError("factory profiles cannot be deleted")
        self._path(slug).unlink()
        _sync_directory(self.directory)

    def import_profile(self, document: Union[str, bytes, Mapping[str, Any]]) -> Profile:
        if isinstance(document, bytes):
            document = document.decode("utf-8")
        if isinstance(document, str):
            document = json.loads(document)
        profile = Profile.from_dict(document)
        # Imported data is user-owned, even if it claims the protected factory flag.
        profile = replace(profile, factory=False)
        return self.create(profile)

    def export_profile(self, slug: str) -> str:
        # Export is built only from the typed profile; runtime auth/session data is separate.
        return json.dumps(
            self.get(slug).to_dict(), ensure_ascii=False, indent=2, sort_keys=True
        ) + "\n"

    @staticmethod
    def slugify(name: str) -> str:
        name = _string("profile name", name).lower()
        slug = re.sub(r"[^a-z0-9]+", "-", name).strip("-")
        if not slug:
            raise ValueError("profile name does not contain slug characters")
        return slug

    @staticmethod
    def _read(path: Path) -> Profile:
        with path.open("r", encoding="utf-8") as handle:
            document = json.load(handle)
        profile = Profile.from_dict(_normalize_saved_playlists(document))
        if profile.slug != path.stem:
            raise ValueError("profile slug does not match filename")
        return profile


def default_miku_profiles() -> Tuple[Profile, ...]:
    """Factory examples referencing exact on-device Miku WW filenames."""

    filenames = tuple(
        "Ryuo_IV_MIKU_WW_{:02d}.mp4".format(index) for index in range(1, 5)
    )
    singles = tuple(
        Profile(
            slug="miku-single-{:02d}".format(index),
            name="Miku Single {:02d}".format(index),
            media=((filename,),),
            playback_modes=("Single",),
            factory=True,
        )
        for index, filename in enumerate(filenames, start=1)
    )
    cycle = Profile(
        slug="miku-cycle",
        name="Miku Cycle",
        media=(filenames,),
        playback_modes=("Cycle",),
        factory=True,
    )
    return singles + (cycle,)
