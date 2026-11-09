"""Token-based HTML views with explicit review priorities and offline assets."""

from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import textwrap
from collections import Counter
from collections.abc import Mapping, Sequence
from html import escape
from pathlib import Path
from typing import TYPE_CHECKING, Any
from urllib.parse import quote, unquote, urlsplit, urlunsplit

from .assets import SCRIPT, STYLE
from .diagrams import allowed_asset, document_map, embed_svg

if TYPE_CHECKING:
    from markdown_it.token import Token

PRIORITIES = {"blocker": 0, "important": 1, "decision": 2, "nit": 3, "pre-existing": 4}


def metadata(source: str, path: Path) -> tuple[dict[str, str], str]:
    match = re.match(
        r"^\s*<!-- human-review:\s*(\{[^\n]*\})\s*-->\s*\n?", source.lstrip("\ufeff")
    )
    value = json.loads(match[1]) if match else {}
    if not isinstance(value, dict):
        raise TypeError("human-review metadata must be an object")
    kind = next(
        (
            name[:-1]
            for name in ("specs", "plans", "brainstorms", "reviews")
            if name in path.parts
        ),
        "guide",
    )
    kind = {"review.md": "review", "agents.md": "policy", "log.md": "history"}.get(
        path.name.lower(), kind
    )
    result = {
        "kind": value.get("kind", kind),
        "status": value.get("status", "reference"),
    }
    if result["kind"] not in {
        "spec",
        "plan",
        "brainstorm",
        "review",
        "guide",
        "policy",
        "history",
    } or result["status"] not in {
        "reference",
        "draft",
        "active",
        "approved",
        "historical",
        "template",
    }:
        raise ValueError("Unsupported human-review kind or status")
    return result, source[match.end() :] if match else source


def _plain(tokens: Sequence[Token] | None) -> str:
    return "".join(
        " " if token.type in {"softbreak", "hardbreak"} else token.content
        for token in tokens or ()
        if token.type in {"text", "code_inline", "image", "softbreak", "hardbreak"}
    )


def _href(
    value: str, source: Path, root: Path, documents: Mapping[Path, Path] | None
) -> str:
    parts = urlsplit(value)
    if parts.scheme and parts.scheme.lower() not in {"http", "https", "mailto"}:
        return "#"
    if not parts.scheme and not parts.netloc and parts.path:
        target = (source.parent / unquote(parts.path)).resolve()
        if (
            target.is_relative_to(root)
            and target.suffix.lower() == ".md"
            and (documents is None or target in documents)
        ):
            path = quote(
                Path(
                    os.path.relpath(target.with_suffix(".html"), source.parent)
                ).as_posix(),
                safe="/",
            )
            return urlunsplit(("", "", path, parts.query, parts.fragment))
    return value


def document_title(source: str, path: Path) -> str:
    from markdown_it import MarkdownIt

    _, body = metadata(source, path)
    tokens = MarkdownIt("commonmark", {"html": False}).parse(body)
    for index, token in enumerate(tokens):
        if token.type == "heading_open" and token.tag == "h1":
            return _plain(tokens[index + 1].children)
    return path.stem


def render_document(
    source: str,
    *,
    source_path: Path,
    root: Path,
    documents: Mapping[Path, Path] | None = None,
) -> str:
    try:
        from markdown_it import MarkdownIt
    except ImportError as error:
        raise RuntimeError(
            'Install documentation tools: python -m pip install -e ".[docs]"'
        ) from error
    root, source_path = root.resolve(), source_path.resolve()
    info, body_source = metadata(source, source_path)
    md = (
        MarkdownIt("commonmark", {"html": False})
        .enable("table")
        .enable("strikethrough")
    )
    tokens = md.parse(body_source)
    headings: list[dict[str, Any]] = []
    seen: Counter[str] = Counter()
    for index, token in enumerate(tokens):
        if token.type != "heading_open":
            continue
        title = _plain(tokens[index + 1].children)
        base = re.sub(r"[^\w\s-]", "", title.lower()).strip()
        base = re.sub(r"\s+", "-", base) or "section"
        slug = f"{base}-{seen[base]}" if seen[base] else base
        seen[base] += 1
        token.attrSet("id", slug)
        excerpt = ""
        for following in tokens[index + 3 :]:
            if following.type == "heading_open":
                break
            if following.type == "inline":
                excerpt = textwrap.shorten(
                    _plain(following.children), width=240, placeholder="…"
                )
                break
        headings.append(
            {"id": slug, "title": title, "level": int(token.tag[1]), "excerpt": excerpt}
        )
    title = next((h["title"] for h in headings if h["level"] == 1), source_path.stem)

    def visit(children: Sequence[Token]) -> None:
        for token in children:
            if token.type == "link_open":
                token.attrSet(
                    "href",
                    _href(
                        str(token.attrGet("href") or ""), source_path, root, documents
                    ),
                )
            if token.children:
                visit(token.children)

    visit(tokens)
    for index, token in enumerate(tokens):
        if token.type != "list_item_open" or index + 2 >= len(tokens):
            continue
        inline = tokens[index + 2]
        if (
            inline.type != "inline"
            or not inline.children
            or inline.children[0].type != "text"
        ):
            continue
        match = re.match(r"^\[([ xX])\]\s+", inline.children[0].content)
        if match:
            token.meta["source_checked"] = match[1].lower() == "x"
            inline.children[0].content = inline.children[0].content[match.end() :]

    def list_item(
        self: Any, items: Sequence[Token], index: int, options: Any, env: Any
    ) -> str:
        token = items[index]
        html = self.renderToken(items, index, options, env)
        if "source_checked" in token.meta:
            checked = ' checked=""' if token.meta["source_checked"] else ""
            html += f'<input type="checkbox" class="source-check" disabled{checked} aria-label="Source task status"> '
        return str(html)

    def image(
        self: Any, items: Sequence[Token], index: int, options: Any, env: Any
    ) -> str:
        token = items[index]
        value, label = str(token.attrGet("src") or ""), _plain(token.children)
        parts = urlsplit(value)
        if parts.scheme or parts.netloc:
            href = _href(value, source_path, root, documents)
            return f'<a href="{escape(href, quote=True)}">External image: {escape(label)}</a>'
        path = (source_path.parent / unquote(parts.path)).resolve()
        if not allowed_asset(path, root) or not path.is_file():
            return f'<span class="note">Image unavailable: {escape(label)}</span>'
        if path.suffix.lower() == ".svg":
            return embed_svg(path, root, label)
        mime = {
            ".png": "png",
            ".jpg": "jpeg",
            ".jpeg": "jpeg",
            ".gif": "gif",
            ".webp": "webp",
        }.get(path.suffix.lower())
        if not mime:
            return escape(label)
        encoded = base64.b64encode(path.read_bytes()).decode("ascii")
        return f'<img src="data:image/{mime};base64,{encoded}" alt="{escape(label, quote=True)}" style="max-width:100%">'

    md.add_render_rule("list_item_open", list_item)
    md.add_render_rule("image", image)
    header_id = ""
    body_tokens = tokens
    if tokens and tokens[0].type == "heading_open" and tokens[0].tag == "h1":
        header_id = str(tokens[0].attrGet("id") or "")
        body_tokens = tokens[3:]
    content = md.renderer.render(body_tokens, md.options, {})
    active = info["status"] in {"active", "draft"}
    items = []
    if active:
        for heading in headings:
            match = re.match(
                r"^(Blocker|Important|Decision|Nit|Pre-existing):\s+(.+)",
                heading["title"],
                re.IGNORECASE,
            )
            if match:
                items.append(
                    {**heading, "priority": match[1].lower(), "label": match[2]}
                )
    items.sort(key=lambda item: PRIORITIES[item["priority"]])
    cards = "".join(
        f'<li class="review-item {item["priority"]}"><span class="priority">{escape(item["priority"].title())}</span><a href="#{escape(item["id"], quote=True)}">{escape(item["label"])}</a><p>{escape(item["excerpt"])}</p><label><input class="review-check" type="checkbox" data-review-item="true" id="read-{escape(item["id"], quote=True)}">I have read this item</label></li>'
        for item in items
    )
    queue = (
        f'<section class="queue" aria-label="Prioritized review"><h2>Review first</h2><p>Merge blockers first, then Important findings, decisions, Nits and Pre-existing issues.</p><p id="review-count">Read 0 of {len(items)} review items</p><progress id="review-progress" value="0" max="{len(items)}"></progress><ul class="review-items">{cards}</ul><p class="note">Checkmarks track local reading progress. They do not approve, fix or merge anything.</p></section>'
        if items
        else ""
    )
    navigation = "".join(
        f'<a class="depth-{h["level"]}" href="#{escape(h["id"], quote=True)}">{escape(h["title"])}</a>'
        for h in headings
        if h["level"] <= 4
    )
    checksum = hashlib.sha256(source.encode("utf-8")).hexdigest()
    catalogue = Path(
        os.path.relpath(root / "docs/review/index.html", source_path.parent)
    ).as_posix()
    relative = (
        source_path.relative_to(root).as_posix()
        if source_path.is_relative_to(root)
        else source_path.name
    )
    note = (
        "Explicit active review. Start with the prioritized items, then read the supporting sections."
        if active
        else "Reference source. Historical unchecked tasks are not current merge blockers."
    )
    return f'''<!doctype html><html lang="en" data-source="{checksum}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{escape(title)} · Mus project review</title><style>{STYLE}</style></head>
<body><div class="layout"><aside class="sidebar"><a class="brand" href="{escape(catalogue, quote=True)}">Project review desk</a><p class="meta">{escape(info["kind"].title())} / {escape(info["status"].title())}</p><details class="toc" open><summary>Sections</summary><nav aria-label="Document sections">{navigation}</nav></details></aside>
<main><header><span class="badge">{escape(info["status"].title())}</span><h1 id="{escape(header_id, quote=True)}">{escape(title)}</h1><p class="note">{note}</p></header>{queue}{document_map(title, headings)}<article>{content}</article><footer>Source: {escape(relative)}. Markdown remains the authoring source; this HTML is the human review copy.<br>Source SHA-256: {checksum}</footer></main></div><script>{SCRIPT}</script></body></html>'''
