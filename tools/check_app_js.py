#!/usr/bin/env python3
"""Extract inline JavaScript from index.html and ask Node to syntax-check it."""
from html.parser import HTMLParser
import os
import subprocess
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HTML = os.path.join(ROOT, "index.html")


class Scripts(HTMLParser):
    def __init__(self):
        super().__init__()
        self.current = None
        self.blocks = []

    def handle_starttag(self, tag, attrs):
        if tag.lower() != "script":
            return
        attrs = dict(attrs)
        mime = (attrs.get("type") or "").split(";")[0].strip().lower()
        if attrs.get("src") or mime not in ("", "text/javascript", "application/javascript", "module"):
            self.current = None
            return
        self.current = []

    def handle_data(self, data):
        if self.current is not None:
            self.current.append(data)

    def handle_endtag(self, tag):
        if tag.lower() == "script" and self.current is not None:
            code = "".join(self.current)
            if code.strip():
                self.blocks.append(code)
            self.current = None


def main():
    parser = Scripts()
    with open(HTML, encoding="utf-8") as handle:
        parser.feed(handle.read())
    if not parser.blocks:
        raise SystemExit("No inline JavaScript blocks found")
    for i, code in enumerate(parser.blocks, 1):
        with tempfile.NamedTemporaryFile("w", suffix=".js", encoding="utf-8") as handle:
            handle.write(code)
            handle.flush()
            result = subprocess.run(["node", "--check", handle.name], text=True,
                                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        if result.returncode:
            print(f"Inline script {i} failed syntax validation:")
            print(result.stdout)
            raise SystemExit(result.returncode)
    print(f"JavaScript syntax OK: {len(parser.blocks)} inline script blocks")


if __name__ == "__main__":
    main()
