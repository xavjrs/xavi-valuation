"""Capture demo footage: drives the dashboard in headless Chromium at 2x resolution and saves stills, then exports
the Excel Checks/Forecast sheets as stills (needs Microsoft Excel).

    py -3.12 demo/capture.py      (from the financial-model folder)

Starts its own Streamlit server on port 8503, so it never disturbs a dashboard you have open.
"""
from __future__ import annotations
import os
import subprocess
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "demo" / "frames"
OUT.mkdir(parents=True, exist_ok=True)
PORT = 8503
URL = f"http://localhost:{PORT}"
HIDE_SIDEBAR = 'section[data-testid="stSidebar"]{display:none !important}'


def start_server() -> subprocess.Popen:
    proc = subprocess.Popen([sys.executable, "-m", "streamlit", "run", "app.py", "--server.port", str(PORT), "--server.headless", "true"],
                            cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    import urllib.request
    for _ in range(120):
        try:
            urllib.request.urlopen(URL, timeout=1)
            return proc
        except Exception:
            time.sleep(0.5)
    proc.kill()
    raise RuntimeError("Streamlit did not start")


def settle(page, extra: float = 0.8):
    """Wait until Streamlit has finished rerunning and charts have drawn."""
    time.sleep(0.4)
    page.wait_for_function("""() => {
        const s = document.querySelector('[data-testid="stStatusWidget"]');
        const running = s && /running/i.test(s.innerText);
        const spin = document.querySelector('[data-testid="stSpinner"]');
        return !running && !spin;
    }""", timeout=120_000)
    page.wait_for_function("""() => [...document.querySelectorAll('.js-plotly-plot')]
        .filter(p => p.offsetParent !== null).every(p => p.querySelector('svg.main-svg'))""", timeout=120_000)
    time.sleep(extra)


def shot(page, name: str):
    page.screenshot(path=str(OUT / f"{name}.png"))
    print("  saved", name)


def nav(page, section: str):
    page.locator('.st-key-nav [data-testid="stRadioOption"]', has_text=section).first.click()
    settle(page, 1.5)
    page.evaluate("document.querySelector('[data-testid=\"stMain\"]')?.scrollTo(0, 0); window.scrollTo(0,0)")
    time.sleep(0.4)


def scroll_to(page, text: str, offset: int = 24):
    page.evaluate("""([t, off]) => {
        const el = [...document.querySelectorAll('.section, .gtitle')].find(e => e.offsetParent !== null && e.textContent.trim() === t);
        if (!el) return;
        el.scrollIntoView({block: 'start'});
        const sc = document.querySelector('[data-testid="stMain"]') || document.scrollingElement;
        sc.scrollBy(0, -off);
    }""", [text, offset])
    time.sleep(0.8)


def slider(page, label: str):
    return page.locator('[data-testid="stSlider"]', has_text=label).first.locator('input[type="range"]')


def step_slider(page, label: str, key: str, presses: int, name: str | None, every: int = 1):
    """Press an arrow key on a slider `presses` times; save a still every `every` presses (none if name is None)."""
    s = slider(page, label)
    s.focus()
    for i in range(presses):
        s.press(key)
        settle(page, 0.6)
        if name and (i + 1) % every == 0:
            shot(page, f"{name}_{(i + 1) // every:02d}")


def main():
    proc = start_server()
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(viewport={"width": 1920, "height": 1080}, device_scale_factor=2)
            page.goto(URL)
            page.wait_for_selector(".brand", timeout=120_000)
            settle(page, 2.5)

            print("overview")
            hide = page.add_style_tag(content=HIDE_SIDEBAR)
            settle(page, 1.0)
            shot(page, "s01_overview")
            scroll_to(page, "Where the value sits", 140)
            shot(page, "s01b_football")
            page.evaluate("document.querySelector('[data-testid=\"stMain\"]')?.scrollTo(0, 0)")
            hide.evaluate("el => el.remove()")
            settle(page, 1.0)
            shot(page, "s02_slider_00")
            step_slider(page, "EBIT margin adjustment", "ArrowRight", 8, "s02_slider")
            step_slider(page, "EBIT margin adjustment", "ArrowLeft", 8, None)   # back to the base case for every later scene
            assert "2,621" in page.inner_text("body"), "margin slider did not return to the base case"

            hide = page.add_style_tag(content=HIDE_SIDEBAR)
            print("financials")
            nav(page, "Financials")
            shot(page, "s00_financials")
            print("valuation")
            nav(page, "Valuation")
            scroll_to(page, "Sensitivity", 40)
            shot(page, "s03_sensitivity")

            print("risk")
            nav(page, "Risk")
            shot(page, "s04_risk")

            print("buyout")
            nav(page, "Buyout")
            scroll_to(page, "Carve-out buyout", 10)
            shot(page, "s05_buyout_00")
            step_slider(page, "Entry EV / EBITDA", "ArrowLeft", 7, "s05_buyout")
            scroll_to(page, "Sources and uses at close", 30)
            shot(page, "s05b_sources")

            print("deal")
            nav(page, "Deal")
            scroll_to(page, "Shell acquires BP", 10)
            shot(page, "s06_deal_00")
            step_slider(page, "Premium to BP", "ArrowLeft", 20, "s06_deal", every=4)
            scroll_to(page, "Earnings per share (USD)", 70)
            shot(page, "s06b_eps")

            print("portfolio")
            nav(page, "Portfolio")
            scroll_to(page, "Efficient frontier", 30)
            shot(page, "s07_frontier")
            scroll_to(page, "Walk-forward backtest", 30)
            shot(page, "s07b_backtest")

            print("audit")
            nav(page, "Method & data")
            scroll_to(page, "Audit", 30)
            shot(page, "s08_audit")
            browser.close()
    finally:
        proc.kill()
    print("excel")
    subprocess.run(["powershell", "-ExecutionPolicy", "Bypass", "-File", str(ROOT / "demo" / "export_excel_stills.ps1")], check=True)


if __name__ == "__main__":
    main()
