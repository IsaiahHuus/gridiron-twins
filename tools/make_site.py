"""Build the GitHub Pages site in docs/ from app/.

    python -I tools/make_site.py

app/index.html is written as a page fragment (the Claude artifact adds the
document shell). This wraps it in a full HTML document with share tags and
copies the stats files next to it.
"""
import glob
import os
import shutil

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP, DOCS = os.path.join(ROOT, "app"), os.path.join(ROOT, "docs")
SITE = "https://isaiahhuus.github.io/gridiron-twins/"
DESC = ("Era-adjusted NFL stats since 2000 for every position, kickers, returners and head coaches. "
        "Find any player's statistical twin, build your own player, and compare anyone head to head.")
ICON = ("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 64 64'%3E"
        "%3Crect width='64' height='64' rx='14' fill='%2313201B'/%3E"
        "%3Cellipse cx='32' cy='32' rx='22' ry='13' transform='rotate(-35 32 32)' fill='%23D9530B'/%3E"
        "%3Cpath d='M24 38l16-12M27 31l4 4M31 28l4 4M35 25l3 3' stroke='%23fff' stroke-width='2.4' stroke-linecap='round'/%3E%3C/svg%3E")
HEAD = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="description" content="{DESC}">
<meta property="og:title" content="Gridiron Twins">
<meta property="og:description" content="{DESC}">
<meta property="og:type" content="website">
<meta property="og:url" content="{SITE}">
<meta property="og:image" content="{SITE}preview.jpg">
<meta name="twitter:card" content="summary_large_image">
<meta name="theme-color" content="#13201B">
<link rel="icon" href="{ICON}">
<style>:root{{color-scheme:light;padding-top:env(safe-area-inset-top,0px);padding-bottom:env(safe-area-inset-bottom,0px)}}
body{{margin:0;font:14px system-ui,sans-serif}}img{{max-width:100%}}[hidden]{{display:none!important}}</style>
"""


def main():
    src = open(os.path.join(APP, "index.html"), encoding="utf-8").read()
    cut = src.index('<header class="top">')
    head, body = src[:cut], src[cut:]
    os.makedirs(DOCS, exist_ok=True)
    with open(os.path.join(DOCS, "index.html"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(HEAD + head.rstrip() + "\n</head>\n<body>\n" + body.rstrip() + "\n</body>\n</html>\n")
    n = 0
    for f in glob.glob(os.path.join(APP, "*-data.js")):
        shutil.copy2(f, os.path.join(DOCS, os.path.basename(f)))
        n += 1
    open(os.path.join(DOCS, ".nojekyll"), "w").close()
    print(f"docs/index.html written, {n} data files copied")


if __name__ == "__main__":
    main()
