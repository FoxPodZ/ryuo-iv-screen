# SPDX-License-Identifier: GPL-3.0-or-later
"""Sample NVIDIA GPUs through nvidia-smi."""

import csv
import math
import shutil
import subprocess
import time
from dataclasses import dataclass
from typing import Callable, Iterator, List, Optional, Sequence, Tuple, Union

from ..models import Measurement, SensorDescriptor, SensorRef, TelemetrySnapshot

_GPU_METRICS = (
    ("temperature.gpu", "gpu.temperature", "GPU temperature", "°C"),
    ("utilization.gpu", "gpu.load", "GPU load", "%"),
    ("power.draw", "gpu.power", "GPU power", "W"),
    ("clocks.current.graphics", "gpu.clock.core", "GPU core clock", "MHz"),
    ("fan.speed", "gpu.fan", "GPU fan", "%"),
)
_VRAM_METRICS = (
    ("memory.used", "gpu.vram.used", "GPU VRAM used", "B"),
    ("memory.total", "gpu.vram.total", "GPU VRAM total", "B"),
)


@dataclass(frozen=True)
class _Gpu:
    index: int
    uuid: str
    name: str
    fields: Sequence[str]


class NvidiaProvider:
    """Select a GPU by exact UUID or reported index, or use the first result."""

    provider_id = "nvidia"

    def __init__(
        self, selector: Optional[Union[int, str]] = None, *,
        executable: Optional[str] = None,
        runner: Optional[Callable[..., subprocess.CompletedProcess]] = None,
        include_vram: bool = True, clock: Callable[[], float] = time.time,
    ) -> None:
        self._selector = selector
        self._executable = executable
        self._runner = runner
        self._clock = clock
        self._metrics = _GPU_METRICS + (_VRAM_METRICS if include_vram else ())
        self.selected_name: Optional[str] = None

    def probe(self) -> Sequence[SensorDescriptor]:
        gpus, _ = self._query()
        selected = self._select(gpus)
        return [
            SensorDescriptor(
                self._ref(gpu, key), key, label, unit,
                available=value is not None,
                source="nvidia-smi: " + field,
                metadata={"index": gpu.index, "uuid": gpu.uuid, "name": gpu.name,
                          "selected": gpu == selected},
                error=error,
            )
            for gpu in gpus
            for (field, key, label, unit), (value, error) in self._readings(gpu)
        ]

    def sample(self) -> TelemetrySnapshot:
        sampled_at = self._clock()
        gpus, error = self._query()
        gpu = self._select(gpus)
        self.selected_name = gpu.name if gpu is not None else None
        if gpu is None:
            if error is None:
                error = ("No GPUs returned by nvidia-smi" if self._selector is None else
                         "Configured NVIDIA GPU {} is unavailable".format(self._selector))
            return TelemetrySnapshot({}, sampled_at, {self.provider_id: error})

        return TelemetrySnapshot({
            key: Measurement(
                self._ref(gpu, key), key, value, unit, sampled_at,
                available=value is not None, error=error,
            )
            for (_, key, _, unit), (value, error) in self._readings(gpu)
        }, sampled_at)

    def _ref(self, gpu: _Gpu, key: str) -> SensorRef:
        return SensorRef(self.provider_id, gpu.uuid, key)

    def _select(self, gpus: Sequence[_Gpu]) -> Optional[_Gpu]:
        if self._selector is None:
            return next(iter(gpus), None)
        selector = str(self._selector).strip()
        if selector.isascii() and selector.isdigit():
            index = selector.lstrip("0") or "0"
            return next((gpu for gpu in gpus if str(gpu.index) == index), None)
        return next((gpu for gpu in gpus if gpu.uuid == selector), None)

    def _query(self) -> Tuple[List[_Gpu], Optional[str]]:
        if self._executable is None:
            self._executable = shutil.which("nvidia-smi")
        if self._executable is None:
            return [], "nvidia-smi executable not found"

        fields = ("index", "uuid", "name") + tuple(field for field, _, _, _ in self._metrics)
        try:
            run = self._runner or subprocess.run
            result = run(
                [self._executable, "--query-gpu=" + ",".join(fields),
                 "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=2,
            )
        except subprocess.TimeoutExpired:
            return [], "nvidia-smi timed out"
        except (OSError, UnicodeError, subprocess.SubprocessError) as exc:
            return [], "nvidia-smi: {}".format(exc)

        if result.returncode != 0:
            return [], "nvidia-smi exited with status {}: {}".format(
                result.returncode, result.stderr.strip(),
            )
        gpus = []
        for row in csv.reader(result.stdout.splitlines(), skipinitialspace=True):
            if len(row) != len(fields):
                continue
            index, uuid, name, *values = (field.strip() for field in row)
            if index.isascii() and index.isdigit() and uuid.startswith("GPU-"):
                gpus.append(_Gpu(int(index), uuid, name, values))
        return gpus, None

    def _readings(
        self, gpu: _Gpu,
    ) -> Iterator[Tuple[Tuple[str, str, str, str],
                        Tuple[Optional[Union[int, float]], Optional[str]]]]:
        for metric, raw in zip(self._metrics, gpu.fields):
            field, _, _, unit = metric
            try:
                if unit == "B":
                    mib = int(raw)
                    if mib < 0:
                        raise ValueError("negative VRAM")
                    value = mib * 1024 ** 2
                else:
                    value = float(raw)
                    if not math.isfinite(value):
                        raise ValueError("non-finite value")
            except ValueError:
                yield metric, (None, "{} is unavailable: {}".format(field, raw))
            else:
                yield metric, (value, None)
