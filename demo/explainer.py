"""Narrated explainer, in vertical (9:16) and desktop (16:9) formats.

    py -3.12 demo/explainer.py vertical    -> demo/XAVI_explainer_vertical.mp4  (1080x1920)
    py -3.12 demo/explainer.py desktop     -> demo/XAVI_explainer_desktop.mp4   (1920x1080)
    py -3.12 demo/explainer.py both

The script (what is shown, captions, narration) lives in demo/script.py. Narration is synthesised with a Microsoft
neural voice through edge-tts: the spoken text is sent to Microsoft's online speech service, and each clip is cached in
demo/audio so unchanged lines are not re-synthesised. Every step lasts as long as its narration plus a breath, so voice
and picture stay in sync. Uses the stills from demo/capture.py.
"""
from __future__ import annotations
import asyncio
import hashlib
import subprocess
import sys
import wave
from dataclasses import dataclass
from pathlib import Path

import imageio.v2 as imageio
import imageio_ffmpeg
import numpy as np
from PIL import Image, ImageDraw

from render import FR, INK, IVORY, GOLD, MUTED, SERIF, SANS, SANS_SB, ease, logo, spaced, font
import script as S

ROOT = Path(__file__).resolve().parent
AUDIO = ROOT / "audio"
FPS, SR = 30, 24000
FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
HAIR = (60, 54, 40)
GLUE = "\x00"          # marks punctuation that attaches to the previous word
LEAD, TAIL = 0.45, 0.65  # seconds of picture before and after each spoken line


@dataclass(frozen=True)
class Layout:
    name: str
    W: int
    H: int
    margin: int
    title_xy: tuple
    title_size: int
    panel: tuple            # x, y, width, height of the picture area
    text: tuple             # x, y, width, font size of the caption
    dots_y: int
    card_title: int         # chapter-card title size
    card_wrap: int


VERTICAL = Layout("vertical", 1080, 1920, 60, (60, 180), 76, (0, 400, 1080, 790), (60, 1250, 960, 44), 1810, 92, 900)
DESKTOP = Layout("desktop", 1920, 1080, 90, (90, 128), 70, (40, 240, 1320, 780), (1400, 330, 440, 40), 980, 104, 1500)
L = VERTICAL
_img: dict = {}


# ───────────────────────── voice ─────────────────────────
def clip(text: str) -> np.ndarray:
    """Synthesise (or load from cache) one spoken line; returns mono float32 samples at SR."""
    AUDIO.mkdir(exist_ok=True)
    key = hashlib.sha1(f"{S.VOICE}|{S.RATE}|{text}".encode()).hexdigest()[:16]
    mp3 = AUDIO / f"{key}.mp3"
    if not mp3.exists():
        import edge_tts
        for attempt in range(4):                       # the service occasionally drops a request; retry
            try:
                asyncio.run(edge_tts.Communicate(text, S.VOICE, rate=S.RATE).save(str(mp3)))
                break
            except Exception:
                if attempt == 3:
                    raise
    raw = subprocess.run([FFMPEG, "-v", "error", "-i", str(mp3), "-f", "s16le", "-ac", "1", "-ar", str(SR), "-"],
                         capture_output=True, check=True).stdout
    x = np.frombuffer(raw, np.int16).astype(np.float32) / 32768
    nz = np.flatnonzero(np.abs(x) > 0.004)             # trim the synthesiser's leading/trailing silence
    if len(nz):
        x = x[max(nz[0] - int(0.03 * SR), 0): nz[-1] + int(0.08 * SR)]
    return x


def seconds(x: np.ndarray) -> float:
    return len(x) / SR


# ───────────────────────── drawing helpers ─────────────────────────
def img(name: str) -> Image.Image:
    if name not in _img:
        _img[name] = Image.open(FR / name).convert("RGB")
    return _img[name]


def rich_lines(text: str, width: int, fnt, fnt_b):
    tokens = []
    for i, part in enumerate(text.split("**")):
        for w in part.split():
            glue = bool(tokens) and w[0] in ".,;:!?)"
            tokens.append((GLUE + w if glue else w, i % 2 == 1))
    d = ImageDraw.Draw(Image.new("RGB", (10, 10)))
    lines, cur, cur_w = [], [], 0.0
    space = d.textlength(" ", font=fnt)
    for w, b in tokens:
        glue = w.startswith(GLUE)
        ww = d.textlength(w.lstrip(GLUE), font=fnt_b if b else fnt)
        if cur and not glue and cur_w + space + ww > width:
            lines.append(cur); cur, cur_w = [], 0.0
        cur_w += (space if cur and not glue else 0) + ww
        cur.append((w, b))
    if cur:
        lines.append(cur)
    return lines


def draw_rich(layer: Image.Image, text: str, x: int, y: int, width: int, alpha: float, size: int):
    fnt, fnt_b = font(SANS, size), font(SANS_SB, size)
    d = ImageDraw.Draw(layer)
    space = d.textlength(" ", font=fnt)
    for li, line in enumerate(rich_lines(text, width, fnt, fnt_b)):
        cx = x
        for wi, (w, b) in enumerate(line):
            if w.startswith(GLUE) and wi:
                cx -= space
            w = w.lstrip(GLUE)
            d.text((cx, y + li * size * 1.42), w, font=fnt_b if b else fnt, fill=(GOLD if b else IVORY) + (int(255 * alpha),))
            cx += d.textlength(w, font=fnt_b if b else fnt) + space


def compose_panel(crops: list, seq_img: str | None, highlights: list, layout: str = "stack") -> Image.Image:
    """Arrange the crops in the picture area; dim everything except highlighted boxes, which get a gold frame."""
    PW, PH = L.panel[2] - 80, L.panel[3]
    parts = [(img(seq_img if name == "SEQ" else name).crop(box), box) for name, box in crops]
    gap = 26
    if layout == "row":
        scale = min((PW - gap * (len(parts) - 1)) / sum(p.width for p, _ in parts), PH / max(p.height for p, _ in parts))
        row_w = sum(round(p.width * scale) for p, _ in parts) + gap * (len(parts) - 1)
        positions, xx = [], (L.panel[2] - row_w) // 2
        for p, _ in parts:
            positions.append((xx, (PH - round(p.height * scale)) // 2))
            xx += round(p.width * scale) + gap
    else:
        scale = PW / max(p.width for p, _ in parts)
        total = sum(p.height * scale for p, _ in parts) + gap * (len(parts) - 1)
        if total > PH:
            scale *= (PH - gap * (len(parts) - 1)) / (total - gap * (len(parts) - 1))
        positions, yy = [], (PH - (sum(p.height * scale for p, _ in parts) + gap * (len(parts) - 1))) / 2
        for p, _ in parts:
            positions.append(((L.panel[2] - round(p.width * scale)) // 2, round(yy)))
            yy += round(p.height * scale) + gap
    panel = Image.new("RGB", (L.panel[2], PH), INK)
    rects = []
    for i, (p, box) in enumerate(parts):
        pw, ph = round(p.width * scale), round(p.height * scale)
        x, y = positions[i]
        tile = p.resize((pw, ph), Image.LANCZOS)
        hls = [hb for ci, hb in highlights if ci == i]
        if hls:
            dim = Image.blend(tile, Image.new("RGB", tile.size, INK), 0.55)
            for hb in hls:
                r = (round((hb[0] - box[0]) * scale), round((hb[1] - box[1]) * scale), round((hb[2] - box[0]) * scale), round((hb[3] - box[1]) * scale))
                dim.paste(tile.crop(r), r[:2])
                rects.append((x + r[0], y + r[1], x + r[2], y + r[3]))
            tile = dim
        panel.paste(tile, (x, y))
        ImageDraw.Draw(panel).rectangle([x - 1, y - 1, x + pw, y + ph], outline=HAIR, width=2)
    d = ImageDraw.Draw(panel)
    for r in rects:
        d.rectangle([r[0] - 4, r[1] - 4, r[2] + 4, r[3] + 4], outline=GOLD, width=4)
    return panel


def chrome(im: Image.Image, chapter_no: str, title: str, progress: float, a_title: float):
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, L.W, 5], fill=(30, 28, 24))
    d.rectangle([0, 0, int(L.W * progress), 5], fill=GOLD)
    lg = _img.setdefault("_logo", logo(0.42))
    im.paste(lg, (L.margin, 64), lg)
    if chapter_no:
        spaced(d, (L.W - L.margin - 150, 72), f"{chapter_no} / {len(S.CHAPTERS):02d}", font(SANS_SB, 20), MUTED, tracking=0.3)
    if title:
        layer = Image.new("RGBA", (L.W, 200), (0, 0, 0, 0))
        ImageDraw.Draw(layer).text((L.title_xy[0], 20), title, font=font(SERIF, L.title_size), fill=IVORY + (int(255 * a_title),))
        im.paste(layer, (0, L.title_xy[1] - 20), layer)


def centred_lines(d, lines: list[str], fnt, y0: float, step: float, color, alpha: float):
    for li, s_ in enumerate(lines):
        tw = d.textlength(s_, font=fnt)
        d.text(((L.W - tw) / 2, y0 + li * step), s_, font=fnt, fill=color + (int(255 * alpha),))


# ───────────────────────── segments ─────────────────────────
def seg_intro(dur: float, minutes: int):
    lg = logo(0.95 if L.name == "vertical" else 1.25)
    lines = ["A valuation model of", "Shell and BP, explained."] if L.name == "vertical" else ["A valuation model of Shell and BP, explained."]
    for i in range(int(dur * FPS)):
        t = i / FPS
        a = ease((t - 0.2) / 0.9) * (1 - ease((t - (dur - 0.4)) / 0.4))
        b = ease((t - 0.9) / 0.8) * (1 - ease((t - (dur - 0.4)) / 0.4))
        im = Image.new("RGB", (L.W, L.H), INK)
        l2 = lg.copy(); l2.putalpha(l2.getchannel("A").point(lambda v: int(v * a)))
        im.paste(l2, ((L.W - lg.width) // 2, L.H // 2 - (200 if L.name == "vertical" else 160)), l2)
        layer = Image.new("RGBA", (L.W, L.H), (0, 0, 0, 0))
        d = ImageDraw.Draw(layer)
        centred_lines(d, lines, font(SERIF, 70 if L.name == "vertical" else 64), L.H // 2 - 20, 84, IVORY, b)
        spaced(d, (L.W / 2, L.H // 2 + (230 if L.name == "vertical" else 130)), f"EIGHT CHAPTERS  ·  ABOUT {minutes} MINUTES",
               font(SANS_SB, 22), MUTED + (int(255 * b),), tracking=0.3, anchor_center=True)
        im.paste(layer, (0, 0), layer)
        yield im


def seg_card(ch: dict, dur: float, progress: float):
    for i in range(int(dur * FPS)):
        t = i / FPS
        a = min(ease(t / 0.4), 1 - ease((t - (dur - 0.3)) / 0.3))
        im = Image.new("RGB", (L.W, L.H), INK)
        chrome(im, ch["n"], "", progress, 0)
        layer = Image.new("RGBA", (L.W, L.H), (0, 0, 0, 0))
        d = ImageDraw.Draw(layer)
        spaced(d, (L.W / 2, L.H / 2 - 120), f"CHAPTER {ch['n']}", font(SANS_SB, 24), GOLD + (int(255 * a),), tracking=0.4, anchor_center=True)
        f = font(SERIF, L.card_title)
        lines = [" ".join(w for w, _ in ln) for ln in rich_lines(ch["title"], L.card_wrap, f, f)]
        centred_lines(d, lines, f, L.H / 2 - 60, L.card_title * 1.13, IVORY, a)
        im.paste(layer, (0, 0), layer)
        yield im


def seg_step(ch: dict, si: int, dur: float, prev_panel, t_abs: float, total: float):
    st = ch["steps"][si]
    hls = st.get("hl", [])
    panels = ([compose_panel(st["crops"], s_, hls, st.get("layout", "stack")) for s_ in st["seq"]] if "seq" in st
              else [compose_panel(st["crops"], None, hls, st.get("layout", "stack"))])
    first, last = si == 0, si == len(ch["steps"]) - 1
    tx, ty, tw, ts = L.text
    for i in range(int(dur * FPS)):
        t = i / FPS
        k = len(panels)
        if k > 1:                                         # step through the interaction states like the live UI (hard cuts,
            j = min(int(t / (dur * 0.8) * (k - 1) + 0.5), k - 1)   # so numbers never ghost through each other)
            panel = panels[j]
        else:
            panel = panels[0]
        if prev_panel is not None and t < 0.45:
            panel = Image.blend(prev_panel, panel, ease(t / 0.45))
        a_out = 1 - ease((t - (dur - 0.35)) / 0.35) if last else 1.0
        im = Image.new("RGB", (L.W, L.H), INK)
        chrome(im, ch["n"], ch["title"], (t_abs + t) / total, (ease(t / 0.4) if first else 1.0) * a_out)
        pa = (ease(t / 0.4) if first else 1.0) * a_out
        im.paste(Image.blend(Image.new("RGB", panel.size, INK), panel, pa) if pa < 1 else panel, (L.panel[0], L.panel[1]))
        layer = Image.new("RGBA", (L.W, L.H), (0, 0, 0, 0))
        a_txt = min(ease((t - 0.15) / 0.4), 1 - ease((t - (dur - 0.3)) / 0.3))
        draw_rich(layer, st["text"], tx, ty, tw, a_txt, ts)
        dd = ImageDraw.Draw(layer)
        for k_ in range(len(ch["steps"])):
            c = GOLD if k_ == si else (60, 56, 48)
            dd.ellipse([tx + k_ * 26, L.dots_y, tx + 12 + k_ * 26, L.dots_y + 12], fill=c + (int(255 * a_out),))
        im.paste(layer, (0, 0), layer)
        yield im
    return panels[-1]


def seg_caveat(dur: float):
    tx, _, tw, _ = L.text
    x, y0, width = (60, 640, 960) if L.name == "vertical" else (260, 330, 1400)
    for i in range(int(dur * FPS)):
        t = i / FPS
        a = min(ease(t / 0.5), 1 - ease((t - (dur - 0.5)) / 0.5))
        im = Image.new("RGB", (L.W, L.H), INK)
        layer = Image.new("RGBA", (L.W, L.H), (0, 0, 0, 0))
        d = ImageDraw.Draw(layer)
        d.text((x, y0), S.CAVEAT[0], font=font(SERIF, 96), fill=IVORY + (int(255 * a),))
        d.rectangle([x, y0 + 150, x + 60, y0 + 153], fill=GOLD + (int(255 * a),))
        draw_rich(layer, S.CAVEAT[1], x, y0 + 200, width, a, 46)
        im.paste(layer, (0, 0), layer)
        yield im


def seg_outro(dur: float):
    lg = logo(0.85 if L.name == "vertical" else 1.1)
    for i in range(int(dur * FPS)):
        t = i / FPS
        a = ease((t - 0.2) / 0.9) * (1 - ease((t - (dur - 0.5)) / 0.5))
        im = Image.new("RGB", (L.W, L.H), INK)
        l2 = lg.copy(); l2.putalpha(l2.getchannel("A").point(lambda v: int(v * a)))
        im.paste(l2, ((L.W - lg.width) // 2, L.H // 2 - 60), l2)
        layer = Image.new("RGBA", (L.W, L.H), (0, 0, 0, 0))
        spaced(ImageDraw.Draw(layer), (L.W / 2, L.H // 2 + 80), "BUILT FROM SEC FILINGS", font(SANS_SB, 22), MUTED + (int(255 * a),),
               tracking=0.3, anchor_center=True)
        im.paste(layer, (0, 0), layer)
        yield im


# ───────────────────────── schedule, render, mix ─────────────────────────
def schedule():
    """List of (kind, payload, duration, audio) with every duration set by its narration."""
    print("  synthesising narration…")
    plan = []
    a = clip(S.INTRO_SAY)
    plan.append(("intro", None, max(4.5, seconds(a) + 1.4), a, 1.0))
    for ch in S.CHAPTERS:
        a = clip(ch["say"])
        plan.append(("card", ch, max(2.0, seconds(a) + 0.9), a, 0.35))
        for si, st in enumerate(ch["steps"]):
            a = clip(st["say"])
            plan.append(("step", (ch, si), max(3.0, seconds(a) + LEAD + TAIL), a, LEAD))
    a = clip(S.CAVEAT_SAY)
    plan.append(("caveat", None, max(6.0, seconds(a) + 1.4), a, 0.6))
    plan.append(("outro", None, 4.0, None, 0))
    return plan


def render(layout: Layout):
    global L
    L = layout
    _img.pop("_logo", None)
    plan = schedule()
    total = sum(p[2] for p in plan)
    stem = ROOT / f"XAVI_explainer_{layout.name}"
    silent = stem.with_suffix(".video.mp4")
    writer = imageio.get_writer(str(silent), fps=FPS, codec="libx264", quality=None, macro_block_size=8,
                                ffmpeg_params=["-crf", "17", "-preset", "slow"])
    track = np.zeros(int((total + 1) * SR), np.float32)
    t_abs, frames, prev_panel = 0.0, 0, None
    for kind, payload, dur, audio, offset in plan:
        dur = round(dur * FPS) / FPS
        if audio is not None:
            s0 = int((t_abs + offset) * SR)
            track[s0:s0 + len(audio)] += audio[: len(track) - s0]
        if kind == "intro":
            gen = seg_intro(dur, round(total / 60))
        elif kind == "card":
            gen, prev_panel = seg_card(payload, dur, t_abs / total), None
        elif kind == "step":
            ch, si = payload
            gen = seg_step(ch, si, dur, prev_panel, t_abs, total)
        elif kind == "caveat":
            gen = seg_caveat(dur)
        else:
            gen = seg_outro(dur)
        while True:
            try:
                im = next(gen)
            except StopIteration as stop:
                if kind == "step":
                    prev_panel = stop.value
                break
            writer.append_data(np.asarray(im))
            frames += 1
            if frames % 900 == 0:
                print(f"  {layout.name}: {frames / FPS:5.1f}s rendered")
        t_abs += dur
    writer.close()

    track = track[: int(t_abs * SR)]
    peak = np.abs(track).max()
    if peak > 0:
        track *= 0.89 / peak                               # normalise to about -1 dBFS
    wav = stem.with_suffix(".voice.wav")
    with wave.open(str(wav), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((track * 32767).astype(np.int16).tobytes())
    out = stem.with_suffix(".mp4")
    subprocess.run([FFMPEG, "-y", "-v", "error", "-i", str(silent), "-i", str(wav), "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
                    "-ar", "48000", "-shortest", "-movflags", "+faststart", str(out)], check=True)
    silent.unlink(); wav.unlink()
    print(f"wrote {out} ({t_abs:.1f}s, {out.stat().st_size / 1e6:.1f} MB)")


if __name__ == "__main__":
    which = sys.argv[1] if len(sys.argv) > 1 else "both"
    for lay in ([VERTICAL, DESKTOP] if which == "both" else [VERTICAL if which == "vertical" else DESKTOP]):
        render(lay)
