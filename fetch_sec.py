"""Download the SEC source data into data/raw (the first step of a full refresh).

The SEC requires automated requests to identify a contact in the User-Agent header. Set it once per shell:
    PowerShell:  $env:SEC_USER_AGENT = "Your Name your@email.com"
    bash:        export SEC_USER_AGENT="Your Name your@email.com"
then run:  py -3.12 fetch_sec.py

Fetches: XBRL company facts for Shell and BP, Shell's latest Form 20-F (for the segment note), and a plain-text
version of that filing for extract_segments.py.
"""
import html
import os
import re
import sys
import requests

UA = os.environ.get("SEC_USER_AGENT")
if not UA or "@" not in UA:
    sys.exit("Set SEC_USER_AGENT to 'Name email@example.com' first (the SEC rejects anonymous requests).")
H = {"User-Agent": UA, "Accept-Encoding": "gzip, deflate"}
CIK = {"shell": "0001306965", "bp": "0000313807"}
os.makedirs("data/raw", exist_ok=True)


def get(url: str) -> requests.Response:
    r = requests.get(url, headers=H, timeout=240)
    r.raise_for_status()
    return r


for name, cik in CIK.items():
    r = get(f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json")
    open(f"data/raw/{name}_companyfacts.json", "wb").write(r.content)
    print(f"{name}: company facts {len(r.content) / 1e6:.1f} MB")

sub = get(f"https://data.sec.gov/submissions/CIK{CIK['shell']}.json").json()["filings"]["recent"]
idx = next(i for i, f in enumerate(sub["form"]) if f == "20-F")
acc, doc, period = sub["accessionNumber"][idx].replace("-", ""), sub["primaryDocument"][idx], sub["reportDate"][idx]
r = get(f"https://www.sec.gov/Archives/edgar/data/{int(CIK['shell'])}/{acc}/{doc}")
year = period[:4]
open(f"data/raw/shell_20f_{year}.htm", "wb").write(r.content)
txt = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", r.text)))
open(f"data/raw/shell_20f_{year}.txt", "w", encoding="utf8").write(txt)
print(f"shell: 20-F for {period} ({len(r.content) / 1e6:.1f} MB) -> data/raw/shell_20f_{year}.txt")
if year != "2025":
    print("note: extract_segments.py reads shell_20f_2025.txt and the FY2023-25 tables; update it for a newer filing.")
