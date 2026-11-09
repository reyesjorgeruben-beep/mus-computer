"""Build/check offline human documents or render one Markdown source."""

import argparse
from pathlib import Path

from .render import render_document
from .site import build_documents


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("build", "check", "render"))
    parser.add_argument("source", nargs="?", type=Path)
    parser.add_argument(
        "--root", type=Path, default=Path(__file__).resolve().parents[3]
    )
    parser.add_argument(
        "--staged",
        action="store_true",
        help="Also verify staged Markdown has staged HTML",
    )
    args = parser.parse_args()
    if args.command == "render":
        if args.source is None:
            parser.error("render requires a Markdown source")
        output = args.source.with_suffix(".html")
        if output.resolve() == args.source.resolve():
            parser.error("HTML output cannot replace the Markdown authoring source")
        content = render_document(
            args.source.read_text(encoding="utf-8"),
            source_path=args.source,
            root=args.root,
        )
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(content, encoding="utf-8")
        print(output)
    else:
        outputs = build_documents(
            args.root, check=args.command == "check", staged=args.staged
        )
        print(
            f"{len(outputs)} HTML documents {'verified' if args.command == 'check' else 'built'}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
