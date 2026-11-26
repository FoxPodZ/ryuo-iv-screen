# SPDX-License-Identifier: GPL-3.0-or-later
import json
import shutil
import subprocess
from pathlib import Path

import pytest

from ryuo_screen.media import MediaCatalog, MediaInfo, MediaTools, ToolUnavailable


class Result:
    def __init__(self, stdout="", returncode=0, stderr=""):
        self.stdout = stdout
        self.returncode = returncode
        self.stderr = stderr


def _probe(codec="hevc", pix_fmt="yuv420p", width=2240, height=1080, fmt="mov,mp4", name="clip.mp4"):
    return json.dumps({
        "format": {"filename": name, "format_name": fmt, "duration": "2.5", "size": "1200"},
        "streams": [{"codec_type": "video", "codec_name": codec, "pix_fmt": pix_fmt,
                     "width": width, "height": height}],
    })


def test_catalog_classification_comes_exactly_from_conn_lists():
    catalog = MediaCatalog.from_conn({"media": {
        "preset": ["rYuO_MIKU.mp4", "Factory.PNG"],
        "custom": ["RYUO-user.mp4", "mine.png"],
    }})
    assert catalog.factory == ("rYuO_MIKU.mp4", "Factory.PNG")
    assert catalog.custom == ("RYUO-user.mp4", "mine.png")
    assert catalog.classify("rYuO_MIKU.mp4") == "factory"
    assert catalog.classify("RYUO-user.mp4") == "custom"
    assert catalog.classify("ryuo_miku.mp4") is None


def test_probe_and_conversion_plans_cover_video_and_stills(tmp_path):
    outputs = iter([
        _probe(),
        _probe(codec="h264"),
        _probe(codec="hevc", width=3000),
        _probe(codec="png", pix_fmt="rgba", fmt="image2", name="x.png"),
        _probe(codec="mjpeg", pix_fmt="yuvj420p", fmt="image2", name="x.jpg"),
        _probe(codec="gif", pix_fmt="bgra", fmt="gif", name="x.gif"),
        _probe(codec="hevc", pix_fmt="yuv420p", fmt="matroska", name="x.mkv"),
        _probe(codec="webp", pix_fmt="yuv420p", fmt="image2", name="x.webp"),
    ])
    calls = []

    def run(argv, **kwargs):
        calls.append((argv, kwargs))
        return Result(next(outputs))

    tools = MediaTools(runner=run, which=lambda name: "/usr/bin/" + name)
    files = [tmp_path / name for name in (
        "ok.mp4", "h264.mp4", "wide.mp4", "x.png", "x.jpg", "x.gif",
        "x.mkv", "x.webp",
    )]
    for path in files:
        path.write_bytes(b"\0\0\0\x18ftypisom")
    infos = [tools.probe(path) for path in files]
    plans = [tools.plan(info) for info in infos[:6]]
    assert plans[0].action == "passthrough"
    assert plans[1].action == plans[2].action == plans[5].action == "transcode-video"
    assert plans[3].action == "passthrough"
    assert plans[4].action == "convert-still"
    embedded_png = MediaInfo(
        "embedded.mp4", "mov,mp4", "png", "rgba", 2240, 1080, 1.0, 100,
    )
    assert tools.plan(embedded_png).action == "convert-still"
    with pytest.raises(ValueError, match="unsupported media format"):
        tools.plan(infos[6])
    with pytest.raises(ValueError, match="unsupported media format"):
        tools.plan(infos[7])
    assert all(isinstance(call[0], list) and "shell" not in call[1] for call in calls)


def test_thumbnail_proxy_are_bounded_and_missing_tools_are_explicit(tmp_path):
    calls = []

    def run(argv, **kwargs):
        calls.append((argv, kwargs))
        Path(argv[-1]).touch()
        return Result()

    tools = MediaTools(runner=run, which=lambda name: "/bin/" + name)
    (tmp_path / "in.mp4").write_bytes(b"\0\0\0\x18ftypisom")
    tools.thumbnail(tmp_path / "in.mp4", tmp_path / "thumb.jpg", width=320, height=180)
    tools.proxy(tmp_path / "in.mp4", tmp_path / "proxy.mp4", width=960, height=540)
    assert "scale=320:180" in calls[0][0]
    assert "scale=960:540" in calls[1][0]
    assert "-fs" in calls[0][0]
    assert "-fs" in calls[1][0] and "-t" in calls[1][0]
    with pytest.raises(ValueError):
        tools.thumbnail(tmp_path / "in", tmp_path / "out", width=641, height=180)
    missing = MediaTools(which=lambda name: None)
    assert missing.status() == {"ffprobe": False, "ffmpeg": False}
    with pytest.raises(ToolUnavailable):
        missing.probe(tmp_path / "in.mp4")


@pytest.mark.skipif(
    shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None,
    reason="real FFmpeg/FFprobe tools are not installed",
)
def test_real_ffmpeg_probe_convert_probe_round_trip(tmp_path):
    source = tmp_path / "source.mp4"
    subprocess.run([
        shutil.which("ffmpeg"), "-nostdin", "-loglevel", "error", "-y",
        "-f", "lavfi", "-i", "color=c=blue:s=64x64:r=1",
        "-frames:v", "1", "-c:v", "libx264", "-pix_fmt", "yuv420p",
        str(source),
    ], check=True, timeout=15)
    tools = MediaTools(timeout=30)
    before = tools.probe(source)
    plan = tools.plan(before)
    assert before.codec == "h264" and plan.action == "transcode-video"
    output = tmp_path / "converted.mp4"
    tools.convert(source, output, plan, 32 * 1024 * 1024)
    after = tools.probe(output)
    assert (after.codec, after.pixel_format, after.width, after.height) == (
        "hevc", "yuv420p", 2240, 1080,
    )


@pytest.mark.parametrize("method", ["probe", "thumbnail", "proxy", "convert"])
def test_every_media_reader_uses_only_recognized_local_input(tmp_path, method):
    from ryuo_screen.media import ConversionPlan
    calls = []
    def run(argv, **kwargs):
        calls.append(argv)
        return Result(_probe())
    tools = MediaTools(runner=run, which=lambda x: x)
    source = tmp_path / "upload"
    def invoke():
        if method == "probe":
            return tools.probe(source)
        if method == "convert":
            return tools.convert(source, tmp_path / "out.mp4", ConversionPlan("transcode-video", ".mp4"))
        return getattr(tools, method)(source, tmp_path / "out")
    source.write_bytes(b"unrecognized document")
    with pytest.raises(ValueError, match="unsupported"):
        invoke()
    assert calls == []
    source.write_bytes(b"\0\0\0\x18ftypisom")
    invoke()
    args, = calls
    assert args[args.index("-protocol_whitelist") + 1] == "file"
    assert args[args.index("-f") + 1] == "mov"
    assert args[args.index("-enable_drefs") + 1] == "0"
    assert args[args.index("-use_absolute_path") + 1] == "0"
    if method == "probe":
        assert "-show_entries" in args and "-show_streams" not in args
        assert args[args.index("-select_streams") + 1] == "v:0"


def test_probe_caps_subprocess_output(tmp_path):
    tool = tmp_path / "metadata-tool"
    tool.write_text("#!/usr/bin/env python3\nprint('x' * 100000)\n")
    tool.chmod(0o700)
    source = tmp_path / "upload"
    source.write_bytes(b"GIF89a")
    with pytest.raises(ValueError, match="metadata exceeds"):
        MediaTools(which=lambda _: str(tool)).probe(source)
