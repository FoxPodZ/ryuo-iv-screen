"""Credits distributed with the project and displayed by the Web UI."""

from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AUTHOR = "FoxPodZ (foxpodz.de)"
ORIGINAL = "https://github.com/foxpodz/ryuo-iv-screen"


class DisplayedLinks(HTMLParser):
    def __init__(self):
        super().__init__()
        self.href = None
        self.links = {}

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            self.href = dict(attrs).get("href")

    def handle_data(self, data):
        if self.href:
            self.links[self.href] = self.links.get(self.href, "") + data

    def handle_endtag(self, tag):
        if tag == "a":
            self.href = None


def test_notice_identifies_original_design_adaptations_and_research():
    path = ROOT / "NOTICE.md"
    assert path.is_file(), "Source distributions must include NOTICE.md"
    original, rest = path.read_text(encoding="utf-8").split("## Design adaptations")
    adaptations, research = rest.split("## Research references")
    assert AUTHOR in original and ORIGINAL in original
    assert "shorti1996/ryuo-display" in adaptations
    assert "GPL-3.0-or-later" in adaptations
    for name in ("ryuo_screen/device.py", "ryuo_screen/media.py", "web/src/ui/screen-page.ts"):
        assert (ROOT / name).is_file() and name in adaptations
    for repository in ("dragocz95/asus-ryuo-iv-linux", "zleo-ai/rog-studio"):
        assert repository in research and repository not in adaptations


def test_web_entry_displays_author_as_link_to_original_project():
    page = DisplayedLinks()
    page.feed((ROOT / "web/src/index.html").read_text(encoding="utf-8"))
    assert page.links.get(ORIGINAL) == AUTHOR
