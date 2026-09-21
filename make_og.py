#!/usr/bin/env python3
"""make_og.py -- build web/og.png, the 1200x630 link-preview thumbnail.

    python3 make_og.py

Composites the site's CC0 batter photo into a left-hand panel and sets the wordmark, headline
and three numbers in the site's palette. Pure Pillow, no browser, so it runs anywhere and is
reproducible: edit this file, re-run, never hand-edit the PNG.

The photo is landscape (1024x683), scaled to the panel height and centre-cropped to the panel
width -- a full 1200-wide bleed would upscale it and go soft.

Photo: web/img/og-batter.jpg, CC0 1.0 via rawpixel (rawpixel.com/image/6112394), found through
Openverse. Public domain, no attribution required; see web/README.md.
"""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).parent
WEB = ROOT / "web"
PHOTO = WEB / "img" / "og-batter.jpg"
OUT = WEB / "og.png"

W, H = 1200, 630
PANEL = 468                                   # photo panel width
PAD = 56
BG, CARD, INK, INK2, INK3 = "#f6f9fc", "#ffffff", "#0d1b2a", "#3c4f61", "#6d8092"
HAIR, HOT, COLD = "#e3ebf2", "#e0332a", "#0c64d6"
SERIF = "/System/Library/Fonts/Supplemental/Georgia.ttf"
SERIF_B = "/System/Library/Fonts/Supplemental/Georgia Bold.ttf"
SANS = "/System/Library/Fonts/Supplemental/Arial.ttf"
SANS_B = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"


def font(path, size):
    return ImageFont.truetype(path, size)


def wrap(draw, text, f, width):
    lines, line = [], ""
    for word in text.split():
        trial = (line + " " + word).strip()
        if draw.textlength(trial, font=f) <= width or not line:
            line = trial
        else:
            lines.append(line)
            line = word
    if line:
        lines.append(line)
    return lines


def main():
    im = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(im)

    # ---- left: the photo, scaled to the panel height and cropped to the panel width
    ph = Image.open(PHOTO).convert("RGB")
    scale = max(PANEL / ph.width, H / ph.height)
    ph = ph.resize((round(ph.width * scale), round(ph.height * scale)), Image.LANCZOS)
    left = max(0, round(ph.width * 0.36) - PANEL // 2)      # keep the hitter in frame
    left = min(left, ph.width - PANEL)
    top = max(0, (ph.height - H) // 2)
    im.paste(ph.crop((left, top, left + PANEL, top + H)), (0, 0))
    # a hairline seam so the photo reads as a panel, not a bleed
    d.line([(PANEL, 0), (PANEL, H)], fill=HAIR, width=2)

    x = PANEL + PAD
    text_w = W - x - PAD

    # ---- wordmark
    f_mark, f_tag = font(SANS_B, 25), font(SANS, 13)
    d.text((x, PAD), "Statcast Reality Check", font=f_mark, fill=INK)
    mw = d.textlength("Statcast Reality Check", font=f_mark)
    chip = [x + mw + 14, PAD + 3, x + mw + 14 + d.textlength("2023\u20132026", font=f_tag) + 20, PAD + 27]
    d.rounded_rectangle(chip, 5, fill=CARD, outline=HAIR, width=1)
    d.text((chip[0] + 10, chip[1] + 6), "2023\u20132026", font=f_tag, fill=INK3)

    # ---- headline
    f_h1 = font(SERIF_B, 52)
    y = PAD + 88
    for line in wrap(d, "Tell a real change from a lucky streak.", f_h1, text_w):
        d.text((x, y), line, font=f_h1, fill=INK)
        y += 60

    f_lede = font(SANS, 18)
    y += 12
    for line in wrap(d, "Every number pulled toward league average by exactly how much of it "
                        "is noise at your sample size.", f_lede, text_w):
        d.text((x, y), line, font=f_lede, fill=INK2)
        y += 27

    # ---- three numbers, the same ones the landing page leads with
    stats = [("14%", HOT, "of a two-week hot streak survived the next two weeks"),
             ("13 PA", INK, "to trust a hitter's bat speed — 525 for his wOBA"),
             ("0.264", COLD, "the most any forecast of next month can score")]
    f_num, f_cap = font(SERIF_B, 30), font(SANS, 13)
    y = H - PAD - 140
    d.line([(x, y - 26), (W - PAD, y - 26)], fill=HAIR, width=1)
    NUMCOL, ROW, LEAD = 118, 46, 18          # one column width, so every caption starts flush
    for num, colour, cap in stats:
        d.text((x, y), num, font=f_num, fill=colour)
        lines = wrap(d, cap, f_cap, text_w - NUMCOL)
        cy = y + (36 - LEAD * len(lines)) / 2      # caption block centred on the number
        for line in lines:
            d.text((x + NUMCOL, cy), line, font=f_cap, fill=INK3)
            cy += LEAD
        y += ROW

    im.save(OUT, "PNG", optimize=True)
    print(f"wrote {OUT}  {W}x{H}  {OUT.stat().st_size / 1024:.0f} KB")


if __name__ == "__main__":
    main()
