"""Visual identity: colours, CSS, HTML helpers and Plotly styling for the dashboard."""
from __future__ import annotations
import pandas as pd

INK = "#0A0A0C"
PANEL = "#111114"
PANEL_HI = "#16161A"
HAIR = "rgba(201,169,97,0.18)"
GOLD = "#C9A961"
GOLD_SOFT = "rgba(201,169,97,0.55)"
IVORY = "#EDE6D6"
MUTED = "#8E8A7E"
WINE = "#9B4A5A"
SLATE = "#5C6270"

LOGO_SVG = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 306 76" role="img" aria-label="XAVI">'
            '<g fill="none" stroke="currentColor" stroke-width="4.6" stroke-linejoin="miter" stroke-miterlimit="12" stroke-linecap="butt"> <path d="M2 6 L62 66 M62 6 L2 66"/> <path d="M98 66 L129 4 L160 66"/> <path d="M196 6 L227 71 L258 6"/> <path d="M300 4 V66"/> </g></svg>')

FONTS = ("@import url('https://fonts.googleapis.com/css2?family=Cormorant+Garamond:wght@400;500;600"
         "&family=Inter:wght@300;400;500;600&display=swap');")

CSS = FONTS + """
:root { --ink:#0A0A0C; --panel:#111114; --panel-hi:#16161A; --hair:rgba(201,169,97,.18);
        --gold:#C9A961; --ivory:#EDE6D6; --muted:#8E8A7E; --wine:#9B4A5A; }
html, body, [class*="css"], .stApp { font-family:'Inter',sans-serif; color:var(--ivory); }
.stApp { background: radial-gradient(1200px 600px at 12% -10%, rgba(201,169,97,.07), transparent 60%),
                    radial-gradient(900px 500px at 100% 0%, rgba(155,74,90,.05), transparent 55%), var(--ink); }
html, body { background:#0A0A0C !important; }
code { color:var(--gold) !important; background:rgba(201,169,97,.08) !important; border-radius:2px; padding:1px 5px; }
div[data-baseweb="select"] > div { background:var(--panel) !important; border:1px solid var(--hair) !important; border-radius:0 !important; }
div[data-baseweb="popover"] ul { background:var(--panel-hi) !important; }
header[data-testid="stHeader"], footer, #MainMenu, [data-testid="stToolbar"], [data-testid="stDecoration"] { display:none !important; }
.block-container { padding:2.2rem 3rem 4rem; max-width:1500px; }

h1,h2,h3,h4 { font-family:'Cormorant Garamond',serif !important; font-weight:500 !important; letter-spacing:.01em; color:var(--ivory); }
.brand { display:flex; align-items:baseline; gap:18px; padding-bottom:18px; border-bottom:1px solid var(--hair); margin-bottom:26px; }
.brand .mark { color:var(--ivory); display:flex; align-items:center; }
.brand .mark svg { height:34px; width:auto; display:block; }
.brand .tag { font-size:.68rem; letter-spacing:.32em; text-transform:uppercase; color:var(--muted); }
.brand .asof { margin-left:auto; font-size:.7rem; letter-spacing:.18em; text-transform:uppercase; color:var(--muted); }

.eyebrow { font-size:.66rem; letter-spacing:.3em; text-transform:uppercase; color:var(--gold); margin:0 0 6px; }
.section { font-family:'Cormorant Garamond',serif; font-size:1.7rem; margin:34px 0 4px; }
.lede { color:var(--muted); font-size:.86rem; line-height:1.65; max-width:880px; margin-bottom:14px; }

.cards { display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:16px; margin:6px 0 10px; }
.card { background:linear-gradient(180deg,var(--panel-hi),var(--panel)); border:1px solid var(--hair); padding:20px 22px 18px; position:relative; }
.card::before { content:""; position:absolute; left:0; top:0; width:34px; height:1px; background:var(--gold); }
.card .k { font-size:.64rem; letter-spacing:.26em; text-transform:uppercase; color:var(--muted); }
.card .v { font-family:'Cormorant Garamond',serif; font-size:2.5rem; line-height:1.1; margin:8px 0 4px; color:var(--ivory); }
.card .v small { font-size:1rem; color:var(--muted); margin-left:4px; font-family:'Inter',sans-serif; }
.card .s { font-size:.76rem; color:var(--muted); }
.card .pos { color:var(--gold); } .card .neg { color:#C98A97; }

.tri { display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:16px; }
.tri .card .v { font-size:2rem; }
.tri .card.on { border-color:var(--gold); box-shadow:0 0 0 1px rgba(201,169,97,.25) inset; }

table.fin { width:100%; border-collapse:collapse; font-size:.82rem; font-variant-numeric:tabular-nums; }
table.fin th { font-weight:500; text-align:right; padding:10px 12px; font-size:.64rem; letter-spacing:.2em; text-transform:uppercase;
               color:var(--gold); border-bottom:1px solid var(--hair); }
table.fin th:first-child { text-align:left; }
table.fin td { padding:8px 12px; text-align:right; border-bottom:1px solid rgba(237,230,214,.05); color:var(--ivory); }
table.fin td:first-child { text-align:left; color:var(--muted); letter-spacing:.02em; min-width:230px; white-space:nowrap; }
table.fin tr.tot td { font-weight:600; color:var(--ivory); border-top:1px solid var(--hair); }
table.fin tr.tot td:first-child { color:var(--ivory); }
table.fin tr:hover td { background:rgba(201,169,97,.04); }
table.fin td.neg { color:#C98A97; }
.wrap { background:var(--panel); border:1px solid var(--hair); padding:10px 14px 14px; overflow-x:auto; }

.note { border-left:1px solid var(--gold); padding:4px 0 4px 16px; color:var(--muted); font-size:.8rem; line-height:1.7; margin:10px 0; }
.note b { color:var(--ivory); font-weight:500; }
.pill { display:inline-block; font-size:.62rem; letter-spacing:.2em; text-transform:uppercase; padding:3px 10px; border:1px solid var(--hair); color:var(--gold); margin-right:8px; }
.pill.ok { color:#B7C79A; border-color:rgba(183,199,154,.35); }
.pill.soon { color:var(--muted); }

section[data-testid="stSidebar"] { background:#0D0D10; border-right:1px solid var(--hair); }
section[data-testid="stSidebar"] .block-container { padding:1.6rem 1.2rem; }
section[data-testid="stSidebar"] label, section[data-testid="stSidebar"] p { font-size:.74rem !important; letter-spacing:.04em; color:var(--muted) !important; }
.sbtitle { font-size:.64rem; letter-spacing:.3em; text-transform:uppercase; color:var(--gold); margin:18px 0 6px; padding-top:14px; border-top:1px solid var(--hair); }
.sbtitle.first { border-top:none; padding-top:0; margin-top:0; }

[role="tab"] p { font-size:.7rem !important; letter-spacing:.24em; text-transform:uppercase; }
/* section navigation: a radio group styled as a tab bar */
.st-key-nav [role="radiogroup"] { gap:0 !important; border-bottom:1px solid var(--hair); margin-bottom:22px; flex-wrap:wrap; }
.st-key-nav [data-testid="stRadioOption"] { padding:12px 18px 11px !important; margin:0 0 -1px 0 !important; cursor:pointer; border-bottom:1px solid transparent; }
.st-key-nav [data-testid="stRadioOption"] > div > div:first-child { display:none !important; }
.st-key-nav [data-testid="stRadioOption"] p { font-size:.7rem !important; letter-spacing:.24em; text-transform:uppercase; color:var(--muted) !important; }
.st-key-nav [data-testid="stRadioOption"]:hover p { color:var(--ivory) !important; }
.st-key-nav [data-testid="stRadioOption"][data-selected="true"] { border-bottom:1px solid var(--gold); }
.st-key-nav [data-testid="stRadioOption"][data-selected="true"] p { color:var(--gold) !important; }
button[data-baseweb="tab"] { font-size:.7rem !important; letter-spacing:.24em; text-transform:uppercase; color:var(--muted); padding:12px 18px; background:transparent; }
button[data-baseweb="tab"][aria-selected="true"] { color:var(--gold) !important; }
div[data-baseweb="tab-highlight"] { background:var(--gold) !important; height:1px !important; }
div[data-baseweb="tab-border"] { background:var(--hair) !important; }
div[data-testid="stExpander"] { border:1px solid var(--hair); background:var(--panel); border-radius:0; }
.stRadio [role="radiogroup"] { gap:6px; }
div[data-testid="stPlotlyChart"] { background:var(--panel); border:1px solid var(--hair); padding:6px 6px 0; }
::-webkit-scrollbar { height:6px; width:6px; } ::-webkit-scrollbar-thumb { background:rgba(201,169,97,.3); }

@media (max-width:1000px) { .cards { grid-template-columns:repeat(2,1fr); } .tri { grid-template-columns:1fr; } .block-container { padding:1.2rem; } }
"""


def style_fig(fig, height: int = 380, legend: bool = False):
    fig.update_layout(
        height=height, margin=dict(l=18, r=18, t=36, b=22), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Inter, sans-serif", color=IVORY, size=12), showlegend=legend,
        legend=dict(orientation="h", y=1.08, x=0, font=dict(size=11, color=MUTED)),
        hoverlabel=dict(bgcolor=PANEL_HI, bordercolor=GOLD, font=dict(family="Inter", color=IVORY, size=12)),
        title=dict(font=dict(family="Cormorant Garamond, serif", size=19, color=IVORY), x=0.012, y=0.96))
    fig.update_xaxes(gridcolor="rgba(237,230,214,0.06)", zerolinecolor="rgba(237,230,214,0.12)",
                     linecolor="rgba(237,230,214,0.15)", tickfont=dict(color=MUTED, size=11))
    fig.update_yaxes(gridcolor="rgba(237,230,214,0.06)", zerolinecolor="rgba(237,230,214,0.12)",
                     linecolor="rgba(237,230,214,0.15)", tickfont=dict(color=MUTED, size=11))
    return fig


def card(label: str, value: str, sub: str = "", unit: str = "", tone: str = "") -> str:
    u = f"<small>{unit}</small>" if unit else ""
    return (f'<div class="card"><div class="k">{label}</div><div class="v {tone}">{value}{u}</div>'
            f'<div class="s">{sub}</div></div>')


def cards(items: list[str], cls: str = "cards", style: str = "") -> str:
    st_ = f' style="{style}"' if style else ""
    return f'<div class="{cls}"{st_}>' + "".join(items) + "</div>"


def fmt(x: float, d: int = 0, pct: bool = False, paren: bool = True) -> str:
    if x is None or (isinstance(x, float) and pd.isna(x)):
        return "–"
    if pct:
        return f"{x*100:.{d}f}%"
    s = f"{abs(x):,.{d}f}"
    return f"({s})" if (x < 0 and paren) else (f"-{s}" if x < 0 else s)


def table_html(df: pd.DataFrame, labels: dict, totals: set = frozenset(), pct_rows: set = frozenset(),
               mult_rows: set = frozenset(), digits: int = 0, row_digits: dict | None = None) -> str:
    head = "<tr><th></th>" + "".join(f"<th>{c}</th>" for c in df.columns) + "</tr>"
    body = []
    for idx, row in df.iterrows():
        cls = ' class="tot"' if idx in totals else ""
        cells = []
        for v in row.values:
            if idx in pct_rows:
                txt = fmt(v, 1, pct=True)
            elif idx in mult_rows:
                txt = "–" if pd.isna(v) else f"{v:.2f}x"
            else:
                txt = fmt(v, (row_digits or {}).get(idx, digits))
            neg = " neg" if (isinstance(v, (int, float)) and v < 0 and idx not in pct_rows) else ""
            cells.append(f'<td class="{neg.strip()}">{txt}</td>')
        body.append(f"<tr{cls}><td>{labels.get(idx, idx)}</td>{''.join(cells)}</tr>")
    return f'<div class="wrap"><table class="fin">{head}{"".join(body)}</table></div>'
