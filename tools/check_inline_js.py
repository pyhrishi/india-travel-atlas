#!/usr/bin/env python3
"""Syntax-check every inline JavaScript block in the static Atlas HTML."""
from html.parser import HTMLParser
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
HTML = ROOT / "index.html"

class ScriptExtractor(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=False)
        self.blocks = []
        self.current = None
        self.kind = "js"

    def handle_starttag(self, tag, attrs):
        if tag.lower() != "script":
            return
        attrs = dict(attrs)
        if "src" in attrs:
            self.current = None
            return
        mime = (attrs.get("type") or "").lower()
        if mime not in ("", "text/javascript", "application/javascript", "module"):
            self.current = None
            return
        self.kind = "mjs" if mime == "module" else "js"
        self.current = []

    def handle_data(self, data):
        if self.current is not None:
            self.current.append(data)

    def handle_endtag(self, tag):
        if tag.lower() == "script" and self.current is not None:
            self.blocks.append((self.kind, "".join(self.current)))
            self.current = None

parser = ScriptExtractor()
parser.feed(HTML.read_text(encoding="utf-8"))
if not parser.blocks:
    raise SystemExit("No inline JavaScript blocks found")

with tempfile.TemporaryDirectory() as tmp:
    for number, (kind, source) in enumerate(parser.blocks, 1):
        path = Path(tmp) / f"inline-{number}.{kind}"
        path.write_text(source, encoding="utf-8")
        result = subprocess.run(["node", "--check", str(path)], text=True, capture_output=True)
        if result.returncode:
            print(result.stdout, end="")
            print(result.stderr, end="")
            raise SystemExit(f"JavaScript syntax error in inline script block {number}")
print(f"JavaScript syntax OK: {len(parser.blocks)} inline script block(s)")
