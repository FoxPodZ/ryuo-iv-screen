# SPDX-License-Identifier: GPL-3.0-or-later
"""Media membership reported by the current HID connection."""

from dataclasses import dataclass
from typing import Any, Dict, Mapping, Optional, Sequence, Tuple


@dataclass(frozen=True)
class MediaCatalog:
    factory: Tuple[str, ...] = ()
    custom: Tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "factory", self._names("factory", self.factory))
        object.__setattr__(self, "custom", self._names("custom", self.custom))

    @staticmethod
    def _names(label: str, values: Sequence[str]) -> Tuple[str, ...]:
        if isinstance(values, (str, bytes)) or not isinstance(values, Sequence):
            raise TypeError("{} media list must be a sequence".format(label))
        result = []
        for value in values:
            if not isinstance(value, str):
                raise TypeError("{} media names must be strings".format(label))
            result.append(value)
        return tuple(result)

    @classmethod
    def from_conn(cls, descriptor: Mapping[str, Any]) -> "MediaCatalog":
        if not isinstance(descriptor, Mapping):
            raise TypeError("conn descriptor must be an object")
        media = descriptor.get("media")
        if not isinstance(media, Mapping):
            raise TypeError("conn media listing must be an object")
        if "preset" not in media or "custom" not in media:
            raise ValueError("conn media listing must include preset and custom")
        return cls(media["preset"], media["custom"])

    def resolve_playlists(self, zones: Sequence[Sequence[str]]) -> Tuple[Tuple[str, ...], ...]:
        """Return the listing's exact spelling for the firmware's path lookup."""
        names = set(self.factory + self.custom)
        by_case = {}
        for name in names:
            by_case.setdefault(name.casefold(), []).append(name)
        resolved = []
        errors = []
        for index, zone in enumerate(zones, start=1):
            items = []
            for name in zone:
                matches = [name] if name in names else by_case.get(name.casefold(), [])
                if len(matches) == 1:
                    items.append(matches[0])
                else:
                    reason = "ambiguous" if matches else "missing"
                    errors.append("zone {}: {} ({})".format(index, name, reason))
            resolved.append(tuple(items))
        if errors:
            raise ValueError("Profile media: " + "; ".join(errors))
        return tuple(resolved)

    def classify(self, name: str) -> Optional[str]:
        if name in self.factory:
            return "factory"
        if name in self.custom:
            return "custom"
        return None

    def to_dict(self) -> Dict[str, Any]:
        return {"factory": list(self.factory), "custom": list(self.custom)}
