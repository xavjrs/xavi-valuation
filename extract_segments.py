"""Extract Shell's segment note (Note 7) from the FY2025 Form 20-F into data/clean/shell_segments.csv.

Source: data/raw/shell_20f_2025.htm (downloaded from SEC EDGAR). Every extracted row is validated: the six
segment values must sum to the reported Total column, and the totals must tie to the group figures in
data/clean/shell_annual.csv.
"""
import html
import re
import pandas as pd

SEGMENTS = ["Integrated Gas", "Upstream", "Marketing", "Chemicals and Products",
            "Renewables and Energy Solutions", "Corporate"]
YEARS = [2025, 2024, 2023]

ROWS = {  # output name -> label as printed in the filing
    "revenue_third_party": "Third-party",
    "revenue_inter_segment": "Inter-segment",
    "jv_share": "Share of profit/(loss) of joint ventures and associates",
    "purchases": "Third-party and inter-segment purchases",
    "opex": "Operating expenses, of which:",
    "dda": "Depreciation, depletion and amortisation charge, of which:",
    "impairment_losses": "Impairment losses",
    "impairment_reversals": "Impairment reversals",
    "interest_expense": "Interest expense",
    "tax": "Taxation charge/(credit)",
    "income": "Income/(loss) for the period",
    "ccs_adjustment_pre_tax": "Current cost of supplies adjustment before taxation",
    "adjusted_earnings": r"Adjusted Earnings(?= [\d(—])",
}
TOKEN = re.compile(r"\(\s*\d[\d,]*\s*\)|\d[\d,]*|—")


def to_num(tok: str) -> float:
    if tok == "—":
        return 0.0
    neg = tok.startswith("(")
    v = float(re.sub(r"[^\d]", "", tok))
    return -v if neg else v


def numbers_after(section: str, label: str, n: int = 7) -> list[float]:
    m = re.search(label if label.startswith("Adjusted") else re.escape(label), section)
    if not m:
        raise ValueError(f"label not found: {label}")
    tail = re.sub(r"\[[A-D]\]", " ", section[m.end(): m.end() + 260])
    toks = TOKEN.findall(tail)[:n]
    if len(toks) < n:
        raise ValueError(f"too few numbers after {label}")
    return [to_num(t) for t in toks]


def main():
    txt = open("data/raw/shell_20f_2025.txt", encoding="utf8").read()
    note_start = txt.index("7. Segment information General information")
    note = txt[note_start: note_start + 40_000]

    heads = [m for m in re.finditer(r"(\d{4}) \$ million Integrated Gas Upstream Marketing", note)]
    income_tables = {int(m.group(1)): note[m.start(): heads[i + 1].start() if i + 1 < len(heads) else m.start() + 6000]
                     for i, m in enumerate(heads[:3])}
    assert sorted(income_tables) == sorted(YEARS), income_tables.keys()

    cap = [numbers_after(note[m.start():], "Capital expenditure") for m in re.finditer(r"Capital expenditure \d", note)]
    capex_tables = dict(zip(YEARS, cap[:3]))  # appear in order 2025, 2024, 2023 (verified by totals below)

    recs, problems = [], []
    group = pd.read_csv("data/clean/shell_annual.csv", index_col=0)
    for y in YEARS:
        vals = {name: numbers_after(income_tables[y], lab) for name, lab in ROWS.items()}
        vals["capex"] = capex_tables[y]
        for name, v in vals.items():
            seg_sum, total = sum(v[:6]), v[6]
            if abs(seg_sum - total) > 2:   # rounding tolerance of $2m
                problems.append(f"{y} {name}: segments sum {seg_sum:,.0f} vs total {total:,.0f}")
            for seg, x in zip(SEGMENTS + ["Total"], v):
                recs.append(dict(year=y, segment=seg, metric=name, usd_m=x))
        # tie-outs to the group statements extracted from XBRL
        ties = {"revenue_third_party": group.loc["revenue", str(y)], "capex": group.loc["capex", str(y)],
                "dda": group.loc["da", str(y)], "tax": group.loc["tax", str(y)], "income": group.loc["net_income", str(y)]}
        for k, g in ties.items():
            if abs(vals[k][6] - g) > 2:
                problems.append(f"{y} {k}: segment total {vals[k][6]:,.0f} vs group {g:,.0f}")
    df = pd.DataFrame(recs)
    df.to_csv("data/clean/shell_segments.csv", index=False)
    print(f"rows: {len(df)}   validation problems: {len(problems)}")
    for p in problems:
        print("  !", p)
    piv = df[(df.year == 2025)].pivot(index="metric", columns="segment", values="usd_m")[SEGMENTS + ["Total"]]
    print(piv.to_string(float_format=lambda x: f"{x:,.0f}"))


if __name__ == "__main__":
    main()
