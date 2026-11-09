"""HTML document navigation, explicit review priorities and safe offline diagrams."""

import subprocess
from html.parser import HTMLParser

import pytest

from mus_computer.documentation.render import render_document
from mus_computer.documentation.site import build_documents, discover_documents


class Page(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = []
        self.links = []
        self.text = []
        self.images = []
        self.queue_links = []
        self.in_queue = False

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if tag == "section" and values.get("aria-label") == "Prioritized review":
            self.in_queue = True
        if "id" in values:
            self.ids.append(values["id"])
        if tag == "a":
            self.links.append(values.get("href", ""))
            if self.in_queue:
                self.queue_links.append(values.get("href", ""))
        if tag == "img":
            self.images.append(values.get("src", ""))

    def handle_endtag(self, tag):
        if tag == "section":
            self.in_queue = False

    def handle_data(self, data):
        self.text.append(data)


def parse(source, tmp_path):
    page = Page()
    html = render_document(source, source_path=tmp_path / "REVIEW.md", root=tmp_path)
    page.feed(html)
    return html, page


def test_token_outline_excludes_code_comments_and_handles_duplicate_headings(tmp_path):
    source = "# Design\n## Overview\n```python\n# secret fake heading\n## not a section\n```\n## Overview\n### Details\n"
    _, page = parse(source, tmp_path)
    assert "overview" in page.ids
    assert "overview-1" in page.ids
    assert "details" in page.ids
    assert "secret-fake-heading" not in page.ids
    assert "not-a-section" not in page.ids
    assert "# secret fake heading" in " ".join(page.text)


def test_active_review_orders_explicit_priorities_above_source_order(tmp_path):
    source = '<!-- human-review: {"kind":"review","status":"active"} -->\n# Review\n### Nit: Naming\nSmall issue.\n### Decision: Format\nChoose.\n### Important: Lost output\nImpact.\n### Blocker: Broken load\nFix.\n### Pre-existing: Slow code\nOld.\n'
    html, page = parse(source, tmp_path)
    assert page.queue_links == [
        "#blocker-broken-load",
        "#important-lost-output",
        "#decision-format",
        "#nit-naming",
        "#pre-existing-slow-code",
    ]
    assert "Review first" in " ".join(page.text)
    assert "data-review-item" in html


def test_historical_tasks_do_not_become_current_blockers(tmp_path):
    html, page = parse(
        "# Old plan\n### Important: Past concern\n- [ ] Historical task\n", tmp_path
    )
    assert "data-review-item" not in html
    assert "Reference" in " ".join(page.text)
    assert 'type="checkbox"' in html
    assert "disabled" in html


def test_links_tables_and_unsafe_html_are_handled_without_remote_assets(tmp_path):
    source = "# Doc\n[Other](other.md#part) [Bad](javascript:alert(1))\n<script>alert(2)</script>\n\nA | B\n--- | ---\nx | y\n\n![Remote](https://example.com/image.png)\n"
    html, page = parse(source, tmp_path)
    assert "other.html#part" in page.links
    assert all(not href.startswith("javascript:") for href in page.links)
    assert not page.images
    assert "&lt;script&gt;" in html
    assert "<table>" in html


def test_local_svg_is_embedded_and_unsafe_elements_are_removed(tmp_path):
    (tmp_path / "flow.svg").write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 60"><rect width="90" height="50" onload="alert(1)"/><text x="5" y="20">Flow</text><script>alert(2)</script><foreignObject>Bad</foreignObject></svg>'
    )
    html, _ = parse("# Flow\n![Process](flow.svg)\n", tmp_path)
    assert "<svg" in html
    assert "Flow</text>" in html
    assert "onload=" not in html
    assert "foreignObject" not in html
    assert "alert(2)" not in html


def test_svg_outside_root_is_not_read(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    (tmp_path / "private.svg").write_text(
        '<svg xmlns="http://www.w3.org/2000/svg"><text>Private content</text></svg>'
    )
    html = render_document(
        "# Doc\n![Private](../private.svg)", source_path=root / "doc.md", root=root
    )
    assert "Private content" not in html


def test_discovery_and_build_are_deterministic_and_check_freshness(tmp_path):
    (tmp_path / "docs").mkdir()
    (tmp_path / "README.md").write_text("# Project\n[Spec](docs/spec.md)")
    (tmp_path / "docs/spec.md").write_text("# Spec\n## Scope\nText.")
    (tmp_path / ".claude").mkdir()
    (tmp_path / ".claude/private.md").write_text("# Do not publish")
    paths = discover_documents(tmp_path)
    assert tmp_path / ".claude/private.md" not in paths
    outputs = build_documents(tmp_path)
    assert tmp_path / "docs/spec.html" in outputs
    assert (tmp_path / "docs/review/index.html").exists()
    before = {path: path.read_bytes() for path in outputs}
    assert build_documents(tmp_path, check=True) == outputs
    build_documents(tmp_path)
    assert {path: path.read_bytes() for path in outputs} == before
    (tmp_path / "docs/spec.md").write_text("# Changed")
    with pytest.raises(ValueError, match="stale|missing"):
        build_documents(tmp_path, check=True)


def test_hidden_agent_assets_are_not_embedded(tmp_path):
    private = tmp_path / ".claude"
    private.mkdir()
    (private / "private.svg").write_text(
        '<svg xmlns="http://www.w3.org/2000/svg"><text>Private agent content</text></svg>'
    )
    html, _ = parse("# Doc\n![Hidden](.claude/private.svg)", tmp_path)
    assert "Private agent content" not in html


def test_hook_check_requires_staged_html_for_new_markdown(tmp_path):
    subprocess.run(["git", "init", str(tmp_path)], check=True, capture_output=True)
    (tmp_path / "README.md").write_text("# Project")
    subprocess.run(["git", "-C", str(tmp_path), "add", "README.md"], check=True)
    outputs = build_documents(tmp_path)
    with pytest.raises(ValueError, match="staged"):
        build_documents(tmp_path, check=True, staged=True)
    subprocess.run(
        ["git", "-C", str(tmp_path), "add", *[str(path) for path in outputs]],
        check=True,
    )
    assert build_documents(tmp_path, check=True, staged=True) == outputs


def test_catalogue_prioritizes_active_reviews_and_ignores_code_titles(tmp_path):
    reviews = tmp_path / "docs/reviews"
    reviews.mkdir(parents=True)
    (reviews / "a-old.md").write_text("# Old review")
    (reviews / "z-live.md").write_text(
        '<!-- human-review: {"kind":"review","status":"active"} -->\n# Current review'
    )
    (tmp_path / "docs/code.md").write_text("```python\n# Not a document title\n```")
    build_documents(tmp_path)
    index = (tmp_path / "docs/review/index.html").read_text(encoding="utf-8")
    assert index.index(">Current review</a>") < index.index(">Old review</a>")
    assert ">code</a>" in index
    assert ">Not a document title</a>" not in index


def test_discovery_uses_platform_independent_mixed_case_order(tmp_path):
    (tmp_path / "README.md").write_text("# Root")
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs/README.md").write_text("# Guide")
    (tmp_path / "docs/guide.md").write_text("# Details")
    names = [
        path.relative_to(tmp_path).as_posix() for path in discover_documents(tmp_path)
    ]
    assert names == ["README.md", "docs/README.md", "docs/guide.md"]
