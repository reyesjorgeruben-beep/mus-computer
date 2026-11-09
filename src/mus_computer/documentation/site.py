"""Deterministic public document discovery, generation and freshness checking."""

from __future__ import annotations

import os
import subprocess
from collections import defaultdict
from html import escape
from pathlib import Path

from .assets import STYLE
from .render import document_title, metadata, render_document


def discover_documents(root: Path) -> list[Path]:
    root = root.resolve()
    try:
        names = (
            subprocess.check_output(
                [
                    "git",
                    "ls-files",
                    "--cached",
                    "--others",
                    "--exclude-standard",
                    "-z",
                    "--",
                    "*.md",
                ],
                cwd=root,
                stderr=subprocess.DEVNULL,
            )
            .decode("utf-8")
            .split("\0")
        )
        candidates = [root / name for name in names if name]
    except (OSError, subprocess.CalledProcessError):
        candidates = list(root.glob("*.md")) + list((root / "docs").rglob("*.md"))
    return sorted(
        {
            path.resolve()
            for path in candidates
            if path.is_file()
            and path.resolve().is_relative_to(root)
            and not any(
                part.startswith(".") and part not in {".planning", ".github"}
                for part in path.relative_to(root).parts
            )
            and not any(
                part in {"training_runs", "node_modules", "__pycache__"}
                for part in path.relative_to(root).parts
            )
        },
        key=lambda path: path.relative_to(root).as_posix(),
    )


def _catalogue(root: Path, sources: list[Path]) -> str:
    output = root / "docs/review/index.html"
    groups: dict[str, list[tuple[bool, str]]] = defaultdict(list)
    for path in sources:
        source = path.read_text(encoding="utf-8")
        info, _ = metadata(source, path)
        name = document_title(source, path)
        href = Path(
            os.path.relpath(path.with_suffix(".html"), output.parent)
        ).as_posix()
        groups[info["kind"]].append(
            (
                info["status"] not in {"active", "draft"},
                f'<li><a href="{escape(href, quote=True)}">{escape(name)}</a><br><span class="meta">{escape(path.relative_to(root).as_posix())} · {escape(info["status"])}</span></li>',
            )
        )
    sections = "".join(
        f"<article><h2>{escape(kind.title())}</h2><ul>{''.join(html for _, html in sorted(items, key=lambda item: item[0]))}</ul></article>"
        for kind, items in sorted(
            groups.items(), key=lambda group: (group[0] != "review", group[0])
        )
    )
    return f'<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Project review desk</title><style>{STYLE}</style></head><body><main><header><p class="meta">Mus computer / human documents</p><h1>Project review desk</h1><p>Start with active reviews. Specs, brainstorms, plans and reference material have navigable HTML copies; historical tasks keep their original status.</p><p>{len(sources)} documents. No login or network required.</p></header><div class="catalogue">{sections}</div></main></body></html>'


def build_documents(
    root: Path, *, check: bool = False, staged: bool = False
) -> list[Path]:
    root = root.resolve()
    sources = discover_documents(root)
    documents = {path: path.with_suffix(".html") for path in sources}
    expected = {
        output: render_document(
            path.read_text(encoding="utf-8"),
            source_path=path,
            root=root,
            documents=documents,
        )
        for path, output in documents.items()
    }
    expected[root / "docs/review/index.html"] = _catalogue(root, sources)
    if staged:
        indexed = set(
            subprocess.check_output(["git", "ls-files", "--cached", "-z"], cwd=root)
            .decode("utf-8")
            .split("\0")
        )
        changed = (
            subprocess.check_output(
                [
                    "git",
                    "diff",
                    "--cached",
                    "--name-only",
                    "-z",
                    "--diff-filter=ACMR",
                    "--",
                    "*.md",
                ],
                cwd=root,
            )
            .decode("utf-8")
            .split("\0")
        )
        missing = [
            name
            for name in changed
            if name
            and root / name in documents
            and Path(name).with_suffix(".html").as_posix() not in indexed
        ]
        if missing:
            raise ValueError(
                "HTML counterparts must be staged with Markdown: " + ", ".join(missing)
            )
    if any(not path.resolve().is_relative_to(root) for path in expected):
        raise ValueError("HTML output must stay inside the document root")
    stale = [
        path
        for path, content in expected.items()
        if not path.is_file() or path.read_text(encoding="utf-8") != content
    ]
    if check and stale:
        raise ValueError(
            "HTML documents are stale or missing; run make docs: "
            + ", ".join(str(path.relative_to(root)) for path in stale)
        )
    if not check:
        for path in stale:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(expected[path], encoding="utf-8")
    return list(expected)
