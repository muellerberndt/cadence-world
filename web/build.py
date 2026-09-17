"""Build web/index.html from web/page.html with sim/core.js inlined at the CORE marker.

python web/build.py            writes web/index.html
python web/build.py --check    exits 1 if web/index.html is stale
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def build() -> str:
    page = (ROOT / "web" / "page.html").read_text()
    core = (ROOT / "sim" / "core.js").read_text()
    marker = "<!-- CORE -->"
    assert marker in page, "page.html needs the CORE marker"
    return page.replace(marker, "<script>\n" + core + "\n</script>")


if __name__ == "__main__":
    out = ROOT / "web" / "index.html"
    html = build()
    if "--check" in sys.argv:
        sys.exit(0 if out.exists() and out.read_text() == html else 1)
    out.write_text(html)
    print(f"wrote {out} ({len(html)} bytes)")
