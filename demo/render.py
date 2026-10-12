"""Render the XAVI demo film from captured stills.

    py -3.12 demo/render.py        -> demo/XAVI_demo.mp4 (1920x1080, 30 fps, H.264) and demo/XAVI_poster.png

Stark founder-style cut: black title cards in Garamond, real footage with slow push-ins, crossfades between
interaction states, no voice. Run demo/capture.py first.
"""
from __future__ import annotations
import math
from pathlib import Path

import imageio.v2 as imageio
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parent
FR = ROOT / "frames"
W, H, FPS = 1920, 1080, 30
INK, IVORY, GOLD, MUTED = (10, 10, 12), (237, 230, 214), (201, 169, 97), (142, 138, 126)
SERIF = "C:/Windows/Fonts/GARA.TTF"
SANS = "C:/Windows/Fonts/segoeuil.ttf"
SANS_SB = "C:/Windows/Fonts/seguisb.ttf"
LOGO_SEGS = [((2, 6), (62, 66)), ((62, 6), (2, 66)), ((98, 66), (129, 4)), ((129, 4), (160, 66)),
             ((196, 6), (227, 71)), ((227, 71), (258, 6)), ((300, 4), (300, 66))]

_cache: dict = {}


def font(path, size):
    k = (path, size)
    if k not in _cache:
        _cache[k] = ImageFont.truetype(path, size)
    return _cache[k]


def ease(t: float) -> float:
    t = min(max(t, 0.0), 1.0)
    return t * t * (3 - 2 * t)


def load(name: str, max_w: int = 2880) -> Image.Image:
    k = ("img", name)
    if k not in _cache:
        im = Image.open(FR / name).convert("RGB")
        if im.width > max_w:
            im = im.resize((max_w, round(im.height * max_w / im.width)), Image.LANCZOS)
        _cache[k] = im
    return _cache[k]


def spaced(draw, xy, text, fnt, fill, tracking=0.0, anchor_center=False):
    """Draw text with letter-spacing (tracking in em)."""
    x, y = xy
    widths = [draw.textlength(ch, font=fnt) + tracking * fnt.size for ch in text]
    total = sum(widths) - tracking * fnt.size
    if anchor_center:
        x -= total / 2
    for ch, w in zip(text, widths):
        draw.text((x, y), ch, font=fnt, fill=fill)
        x += w
    return total


def logo(scale: float, color=IVORY) -> Image.Image:
    """The XAVI wordmark from the SVG geometry, supersampled for clean anti-aliasing."""
    ss = 4
    w, h = int(306 * scale * ss), int(76 * scale * ss)
    im = Image.new("L", (w, h), 0)
    d = ImageDraw.Draw(im)
    for (x1, y1), (x2, y2) in LOGO_SEGS:
        d.line([(x1 * scale * ss, y1 * scale * ss), (x2 * scale * ss, y2 * scale * ss)], fill=255, width=max(1, int(4.6 * scale * ss)))
    im = im.resize((int(306 * scale), int(76 * scale)), Image.LANCZOS)
    rgba = Image.new("RGBA", im.size, color + (0,))
    rgba.putalpha(im)
    return rgba


def blank() -> Image.Image:
    return Image.new("RGB", (W, H), INK)


def fade(img: Image.Image, a: float) -> Image.Image:
    return img if a >= 1 else Image.blend(blank(), img, max(a, 0.0))


# ───────────────────────── shot types ─────────────────────────
def title_card(eyebrow: str, line: str, dur: float):
    fe, fl = font(SANS_SB, 22), font(SERIF, 84)
    n = int(dur * FPS)
    for i in range(n):
        t = i / FPS
        a_in, a_out = ease(t / 0.45), 1 - ease((t - (dur - 0.3)) / 0.3)
        a = min(a_in, a_out)
        im = blank()
        layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(layer)
        rise = (1 - ease(t / 0.8)) * 14
        spaced(d, (W / 2, H / 2 - 92 + rise), eyebrow, fe, GOLD + (int(255 * a),), tracking=0.32, anchor_center=True)
        tw = d.textlength(line, font=fl)
        d.text((W / 2 - tw / 2, H / 2 - 52 + rise), line, font=fl, fill=IVORY + (int(255 * a),))
        im.paste(layer, (0, 0), layer)
        yield im


def footage(frames: list[str], dur: float, label: str, zoom=(1.0, 1.06), focus=((0.5, 0.45), (0.5, 0.45)), xfade: float = 0.28):
    """Ken Burns over one or more stills; successive stills crossfade (used for interaction sequences)."""
    n = int(dur * FPS)
    k = len(frames)
    seg = dur / k
    fe = font(SANS_SB, 18)
    for i in range(n):
        t = i / FPS
        p = ease(t / dur)
        z = zoom[0] + (zoom[1] - zoom[0]) * p
        fx = focus[0][0] + (focus[1][0] - focus[0][0]) * p
        fy = focus[0][1] + (focus[1][1] - focus[0][1]) * p
        j = min(int(t / seg), k - 1)
        src = load(frames[j])
        within = t - j * seg
        if j + 1 < k and within > seg - xfade:
            src = Image.blend(src, load(frames[j + 1]), ease((within - (seg - xfade)) / xfade))
        cw, ch = src.width / z, src.height / z
        cx = min(max(fx * src.width, cw / 2), src.width - cw / 2)
        cy = min(max(fy * src.height, ch / 2), src.height - ch / 2)
        im = src.crop((round(cx - cw / 2), round(cy - ch / 2), round(cx + cw / 2), round(cy + ch / 2))).resize((W, H), Image.LANCZOS)
        # bottom vignette + section label
        grad = Image.new("L", (1, 220))
        for y in range(220):
            grad.putpixel((0, y), int(200 * (y / 219) ** 1.6))
        im.paste(Image.new("RGB", (W, 220), INK), (0, H - 220), grad.resize((W, 220)))
        d = ImageDraw.Draw(im)
        spaced(d, (96, H - 78), label, fe, GOLD, tracking=0.32)
        a = min(ease(t / 0.3), 1 - ease((t - (dur - 0.3)) / 0.3))
        yield fade(im, a)


def paper(name: str, dur: float, label: str, pan=(0.22, 0.86)):
    """A light document (the Excel export) floating on black, panning top to bottom."""
    src = Image.open(FR / name).convert("RGB")
    tw = 1500
    th = round(src.height * tw / src.width)
    doc = src.resize((tw, th), Image.LANCZOS)
    shadow = Image.new("RGBA", (tw + 120, th + 120), (0, 0, 0, 0))
    ImageDraw.Draw(shadow).rectangle([60, 70, 60 + tw, 70 + th], fill=(0, 0, 0, 200))
    shadow = shadow.filter(ImageFilter.GaussianBlur(28))
    fe = font(SANS_SB, 18)
    n = int(dur * FPS)
    for i in range(n):
        t = i / FPS
        p = ease(t / dur)
        view = pan[0] + (pan[1] - pan[0]) * p            # fraction of the document centred on screen
        y = H / 2 - view * th
        x = (W - tw) / 2
        im = blank()
        im.paste(shadow, (int(x - 60), int(y - 60)), shadow)
        im.paste(doc, (int(x), int(y)))
        grad = Image.new("L", (W, 300))                      # fully black under the label so it never sits on white paper
        gd = ImageDraw.Draw(grad)
        for yy in range(300):
            gd.line([(0, yy), (W, yy)], fill=min(255, int(255 * (yy / 170) ** 1.2)))
        im.paste(Image.new("RGB", (W, 300), INK), (0, H - 300), grad)
        top = Image.new("L", (W, 160))
        tdraw = ImageDraw.Draw(top)
        for yy in range(160):
            tdraw.line([(0, yy), (W, yy)], fill=int(235 * (1 - yy / 159) ** 1.4))
        im.paste(Image.new("RGB", (W, 160), INK), (0, 0), top)
        spaced(ImageDraw.Draw(im), (96, H - 78), label, fe, GOLD, tracking=0.32)
        a = min(ease(t / 0.35), 1 - ease((t - (dur - 0.35)) / 0.35))
        yield fade(im, a)


def intro(dur: float = 5.2):
    lg = logo(1.55)
    fl, fs = font(SERIF, 44), font(SANS, 20)
    n = int(dur * FPS)
    for i in range(n):
        t = i / FPS
        im = blank()
        a_logo = ease((t - 0.5) / 1.3) * (1 - ease((t - (dur - 0.45)) / 0.45))
        a_tag = ease((t - 2.0) / 0.9) * (1 - ease((t - (dur - 0.45)) / 0.45))
        if a_logo > 0:
            l2 = lg.copy()
            l2.putalpha(l2.getchannel("A").point(lambda v: int(v * a_logo)))
            im.paste(l2, ((W - lg.width) // 2, H // 2 - 110), l2)
        if a_tag > 0:
            layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            d = ImageDraw.Draw(layer)
            line = "Corporate valuation, rebuilt from the filings."
            tw = d.textlength(line, font=fl)
            d.text(((W - tw) / 2, H // 2 + 30), line, font=fl, fill=IVORY + (int(255 * a_tag),))
            im.paste(layer, (0, 0), layer)
        yield im


def outro(dur: float = 4.6):
    lg = logo(1.25)
    fs = font(SANS, 20)
    n = int(dur * FPS)
    for i in range(n):
        t = i / FPS
        im = blank()
        a = ease((t - 0.2) / 1.0) * (1 - ease((t - (dur - 0.6)) / 0.6))
        l2 = lg.copy()
        l2.putalpha(l2.getchannel("A").point(lambda v: int(v * a)))
        im.paste(l2, ((W - lg.width) // 2, H // 2 - 70), l2)
        layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(layer)
        spaced(d, (W / 2, H // 2 + 60), "BUILT FROM SEC FILINGS  ·  NOT INVESTMENT ADVICE", fs, MUTED + (int(255 * a * 0.9),), tracking=0.28, anchor_center=True)
        im.paste(layer, (0, 0), layer)
        yield im


def seq(prefix: str, n: int) -> list[str]:
    return [f"{prefix}_{i:02d}.png" for i in range(n + 1)]


def timeline():
    yield from intro()
    yield from title_card("01  ·  SOURCE", "Shell and BP, straight from their SEC filings.", 2.3)
    yield from footage(["s01_overview.png"], 5.0, "OVERVIEW  ·  SHELL PLC", zoom=(1.0, 1.07), focus=((0.5, 0.42), (0.5, 0.38)))
    yield from title_card("02  ·  LIVE", "Change one assumption. Watch everything move.", 2.3)
    yield from footage(seq("s02_slider", 8), 7.0, "EBIT MARGIN  +2PP", zoom=(1.0, 1.05), focus=((0.45, 0.33), (0.42, 0.30)), xfade=0.35)
    yield from title_card("03  ·  RISK", "Ten thousand futures, not one guess.", 2.3)
    yield from footage(["s04_risk.png"], 5.0, "MONTE CARLO  ·  10,000 PATHS", zoom=(1.0, 1.07), focus=((0.5, 0.5), (0.5, 0.45)))
    yield from title_card("04  ·  BUYOUT", "What a private-equity buyer could pay.", 2.3)
    yield from footage(seq("s05_buyout", 7) + ["s05b_sources.png"], 7.0, "CARVE-OUT LBO  ·  SHELL MARKETING", zoom=(1.0, 1.05), focus=((0.5, 0.35), (0.5, 0.4)), xfade=0.3)
    yield from title_card("05  ·  MERGER", "What a merger is really worth.", 2.3)
    yield from footage(seq("s06_deal", 5) + ["s06b_eps.png"], 7.0, "SHELL ACQUIRES BP", zoom=(1.0, 1.05), focus=((0.5, 0.4), (0.5, 0.45)), xfade=0.35)
    yield from title_card("06  ·  PORTFOLIO", "Thirteen assets, seen in sterling.", 2.3)
    yield from footage(["s07_frontier.png", "s07b_backtest.png"], 6.0, "EFFICIENT FRONTIER  ·  WALK-FORWARD BACKTEST", zoom=(1.0, 1.06), focus=((0.5, 0.5), (0.5, 0.5)), xfade=0.5)
    yield from title_card("07  ·  PROOF", "1,082 live formulas. Every number reconciles.", 2.3)
    yield from paper("xl_Checks.png", 6.5, "EXCEL  ·  WORKBOOK VS PYTHON ENGINE")
    yield from footage(["s08_audit.png"], 4.0, "AUDIT  ·  86 OF 86 CHECKS PASS", zoom=(1.02, 1.12), focus=((0.5, 0.7), (0.5, 0.74)))
    yield from outro()


def main():
    out = ROOT / "XAVI_demo.mp4"
    writer = imageio.get_writer(str(out), fps=FPS, codec="libx264", quality=None, macro_block_size=8,
                                ffmpeg_params=["-crf", "16", "-preset", "slow", "-pix_fmt", "yuv420p", "-movflags", "+faststart"])
    n = 0
    poster = None
    for im in timeline():
        writer.append_data(np.asarray(im))
        n += 1
        if n == int(3.6 * FPS):
            poster = im
        if n % 300 == 0:
            print(f"  {n / FPS:5.1f}s rendered")
    writer.close()
    if poster is not None:
        poster.save(ROOT / "XAVI_poster.png")
    print(f"wrote {out} ({n / FPS:.1f}s, {n} frames, {out.stat().st_size / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
