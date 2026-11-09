"""Safe inline SVG and compact document-structure diagrams, without a CDN."""

import re
import textwrap
from html import escape
from pathlib import Path
from xml.etree import ElementTree as ET

_TAGS = {
    "svg",
    "g",
    "rect",
    "path",
    "line",
    "polyline",
    "polygon",
    "circle",
    "ellipse",
    "text",
    "tspan",
    "defs",
    "marker",
    "title",
    "desc",
}
_ATTRS = {
    "viewBox",
    "width",
    "height",
    "x",
    "y",
    "x1",
    "x2",
    "y1",
    "y2",
    "cx",
    "cy",
    "rx",
    "ry",
    "r",
    "d",
    "points",
    "fill",
    "stroke",
    "stroke-width",
    "stroke-dasharray",
    "opacity",
    "font-family",
    "font-size",
    "font-weight",
    "text-anchor",
    "dominant-baseline",
    "transform",
    "id",
    "marker-end",
    "marker-start",
    "markerWidth",
    "markerHeight",
    "refX",
    "refY",
    "orient",
    "preserveAspectRatio",
}


def allowed_asset(path: Path, root: Path) -> bool:
    path, root = path.resolve(), root.resolve()
    return path.is_relative_to(root) and not any(
        part.startswith(".") and part not in {".planning", ".github"}
        for part in path.relative_to(root).parts
    )


def embed_svg(path: Path, root: Path, label: str) -> str:
    resolved = path.resolve()
    if not allowed_asset(resolved, root) or not resolved.is_file():
        return f'<p class="note">Diagram unavailable: {escape(label)}</p>'
    try:
        svg = ET.fromstring(resolved.read_text(encoding="utf-8"))
    except (ET.ParseError, UnicodeError):
        return '<p class="note">Diagram could not be parsed as SVG.</p>'
    if svg.tag.rsplit("}", 1)[-1] != "svg":
        return '<p class="note">Diagram is not an SVG document.</p>'
    for parent in svg.iter():
        for child in list(parent):
            if child.tag.rsplit("}", 1)[-1] not in _TAGS:
                parent.remove(child)
        for name in list(parent.attrib):
            value = parent.attrib[name]
            if (
                name not in _ATTRS
                or "\\" in value
                or "@" in value
                or (
                    "url(" in value.lower()
                    and not re.fullmatch(r"url\(#[\w-]+\)", value)
                )
            ):
                del parent.attrib[name]
    svg.set("role", "img")
    svg.set("aria-label", label)
    ET.register_namespace("", "http://www.w3.org/2000/svg")
    return f'<span class="diagram">{ET.tostring(svg, encoding="unicode")}<span class="diagram-caption">{escape(label)}</span></span>'


def document_map(title: str, headings: list[dict]) -> str:
    sections = [h for h in headings if h["level"] == 2][:10]
    if not sections:
        return ""
    height = 100 + ((len(sections) + 1) // 2) * 75
    nodes = []
    for index, section in enumerate(sections):
        x, y = (20 if index % 2 == 0 else 410), 95 + index // 2 * 75
        labels = textwrap.wrap(section["title"], width=42)[:2]
        text = "".join(
            f'<tspan x="{x + 175}" dy="{0 if line == 0 else 17}">{escape(label)}</tspan>'
            for line, label in enumerate(labels)
        )
        nodes.append(
            f'<path d="M390 65 V{y - 10} H{x + 175} V{y}" fill="none" stroke="#b2c7d5"/><a href="#{escape(section["id"], quote=True)}"><rect x="{x}" y="{y}" width="350" height="52" rx="6" fill="#edf5f9" stroke="#9bb8cc"/><text x="{x + 175}" y="{y + 22}" text-anchor="middle" font-size="13">{text}</text></a>'
        )
    return f'<details class="document-map"><summary>Document map</summary><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 780 {height}" role="img" aria-label="Document section hierarchy"><rect x="180" y="10" width="420" height="55" rx="7" fill="#193f59"/><text x="390" y="43" text-anchor="middle" fill="white" font-size="16">{escape(title[:48])}</text>{"".join(nodes)}</svg></details>'
