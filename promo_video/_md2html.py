import sys, markdown, pathlib

src = pathlib.Path(sys.argv[1])
dst = pathlib.Path(sys.argv[2])
title = sys.argv[3] if len(sys.argv) > 3 else src.stem

body = markdown.markdown(
    src.read_text(encoding="utf-8"),
    extensions=["tables", "fenced_code", "toc", "sane_lists"],
)

CSS = """
:root{--bg:#0b1220;--panel:#111a2e;--ink:#e8eefc;--muted:#9fb0d0;--line:#243150;--accent:#38bdf8;--accent2:#34d399}
*{box-sizing:border-box}
html{scroll-behavior:smooth}
body{margin:0;background:linear-gradient(180deg,#0b1220,#0d1526);color:var(--ink);
 font-family:"Segoe UI","Microsoft YaHei",system-ui,sans-serif;line-height:1.75;font-size:16px}
.wrap{max-width:920px;margin:0 auto;padding:48px 28px 96px}
h1{font-size:30px;line-height:1.3;margin:.2em 0 .1em;background:linear-gradient(90deg,#38bdf8,#34d399);
 -webkit-background-clip:text;background-clip:text;color:transparent}
h2{font-size:23px;margin-top:2em;padding-top:.6em;border-top:1px solid var(--line)}
h3{font-size:18px;margin-top:1.4em;color:#cfe0ff}
h1+h2{border-top:none}
p,li{color:#dbe6fb}
a{color:var(--accent);text-decoration:none}
strong{color:#fff}
blockquote{margin:1em 0;padding:.6em 1em;border-left:3px solid var(--accent);
 background:rgba(56,189,248,.07);border-radius:0 8px 8px 0;color:var(--muted)}
code{background:#0a1326;border:1px solid var(--line);border-radius:5px;padding:.1em .4em;
 font-family:"Cascadia Code",Consolas,monospace;font-size:.9em;color:#7dd3fc}
pre{background:#0a1326;border:1px solid var(--line);border-radius:10px;padding:14px 16px;overflow:auto}
pre code{background:none;border:none;padding:0;color:#bcd2ff}
table{border-collapse:collapse;width:100%;margin:1.1em 0;font-size:14.5px;
 background:var(--panel);border:1px solid var(--line);border-radius:10px;overflow:hidden}
th,td{border-bottom:1px solid var(--line);padding:9px 12px;text-align:left;vertical-align:top}
th{background:#16223c;color:#bfe0ff;font-weight:600}
tr:last-child td{border-bottom:none}
tr:hover td{background:rgba(56,189,248,.05)}
hr{border:none;border-top:1px solid var(--line);margin:2em 0}
em{color:var(--muted)}
::selection{background:rgba(52,211,153,.3)}
"""

html = f"""<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title><style>{CSS}</style></head>
<body><div class="wrap">{body}</div></body></html>"""

dst.write_text(html, encoding="utf-8")
print("wrote", dst, len(html), "chars")
