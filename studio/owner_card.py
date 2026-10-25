"""Owner Featured close: the branded logo + phone-number card over the owner's talking head (local, no API calls).

    python -m studio.owner_card mockups <tenant> <out-dir> [--frame still.png]   # one still per card style
    python -m studio.owner_card layers  <tenant> <out-dir> [--style S]           # the two PNG layers for a close

The card sits in the top band of the frame, clear of the presenter's face. Everything business-specific (logo, number,
brand colours, the chosen style) comes from tenants/<tenant>.json; the styles themselves are generic."""
import json, sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from .owner_featured import FORMAT_DIR

CARD_DIR = FORMAT_DIR / "card"
FONTS = CARD_DIR / "fonts"
W, H = 1080, 1920
CARD = (40, 36, 1040, 326)      # card box; its bottom stays above the presenter's hair (Truck 1 close: about y 344)
STYLES = ("bar", "italic", "split")
DEFAULT_STYLE = "split"   # Bobby, 2026-10-24: the Split card is the house style for every business
DEFAULT_COLORS = {"primary": "#102058", "accent": "#C8102E", "card": "#FFFFFF"}


def font(name, size, weight=None):
    f = ImageFont.truetype(str(FONTS / name), size)
    if weight is not None:
        f.set_variation_by_axes([weight])
    return f


def rgb(h, a=255):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4)) + (a,)


def icon(size, color):
    m = Image.open(CARD_DIR / "phone-icon.png").convert("RGBA").resize((size, size), Image.LANCZOS)
    out = Image.new("RGBA", m.size, rgb(color))
    out.putalpha(m.getchannel("A"))
    return out


def shadow(layer, radius=18, offset=(0, 10), alpha=90):
    a = layer.getchannel("A").point(lambda v: v * alpha // 255)
    sh = Image.new("RGBA", layer.size, (0, 0, 0, 0))
    sh.putalpha(a.filter(ImageFilter.GaussianBlur(radius)))
    out = Image.new("RGBA", layer.size, (0, 0, 0, 0))
    out.alpha_composite(sh, offset)
    out.alpha_composite(layer)
    return out


def text_w(d, s, f, spacing=0):
    return sum(d.textlength(c, font=f) for c in s) + spacing * (len(s) - 1)


def draw_spaced(d, xy, s, f, fill, spacing=0):
    x, y = xy
    for c in s:
        d.text((x, y), c, font=f, fill=fill)
        x += d.textlength(c, font=f) + spacing


def logo_on(layer, logo, width, top):
    lg = Image.open(logo).convert("RGBA")
    lg = lg.resize((width, round(lg.height * width / lg.width)), Image.LANCZOS)
    layer.alpha_composite(lg, ((W - width) // 2, top))
    return top + lg.height


def layers(profile, style=DEFAULT_STYLE):
    """Two transparent 1080x1920 layers: the card with the logo, and the number element (animated in separately)."""
    if style not in STYLES:
        raise SystemExit(f"card style must be one of {', '.join(STYLES)}")
    c = {**DEFAULT_COLORS, **(profile.get("brand") or {}).get("colors", {})}
    number = profile["contact_number"]["display"]
    logo = profile["logo"]["file"]
    x0, y0, x1, y1 = CARD
    card = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    num = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(card)
    if style == "split":
        split_y = 222
        d.rounded_rectangle(CARD, 34, fill=rgb(c["card"]))
        d.rounded_rectangle((x0, split_y, x1, y1), 34, fill=rgb(c["primary"]))
        d.rectangle((x0, split_y, x1, split_y + 34), fill=rgb(c["primary"]))
        d.rectangle((x0, split_y, x1, split_y + 7), fill=rgb(c["accent"]))
        logo_on(card, logo, 560, 54)
        n = ImageDraw.Draw(num)
        f = font("Montserrat-VF.ttf", 70, 900)
        tw = text_w(n, number, f, 3)
        ic = 46
        gx = (W - (ic + 22 + tw)) // 2
        cy = (split_y + 7 + y1) // 2
        num.alpha_composite(icon(ic, c["card"]), (int(gx), cy - ic // 2))
        top = n.textbbox((0, 0), number, font=f)
        draw_spaced(n, (gx + ic + 22, cy - (top[1] + top[3]) // 2), number, f, rgb(c["card"]), 3)
    elif style == "bar":
        d.rounded_rectangle(CARD, 34, fill=rgb(c["card"]))
        logo_on(card, logo, 600, 50)
        n = ImageDraw.Draw(num)
        bar = (x0 + 26, 214, x1 - 26, y1 - 18)
        n.rounded_rectangle(bar, (bar[3] - bar[1]) // 2, fill=rgb(c["primary"]))
        r = (bar[3] - bar[1]) - 14
        n.ellipse((bar[0] + 7, bar[1] + 7, bar[0] + 7 + r, bar[1] + 7 + r), fill=rgb(c["accent"]))
        num.alpha_composite(icon(int(r * 0.56), c["card"]), (bar[0] + 7 + int(r * 0.22), bar[1] + 7 + int(r * 0.22)))
        f = font("Montserrat-VF.ttf", 64, 800)
        tw = text_w(n, number, f, 4)
        left = bar[0] + 7 + r
        cx = (left + bar[2]) // 2
        cy = (bar[1] + bar[3]) // 2
        top = n.textbbox((0, 0), number, font=f)
        draw_spaced(n, (cx - tw / 2, cy - (top[1] + top[3]) // 2), number, f, rgb(c["card"]), 4)
    else:   # italic: matches a slanted, sporty logo
        d.rounded_rectangle(CARD, 34, fill=rgb(c["card"]))
        logo_on(card, logo, 580, 46)
        n = ImageDraw.Draw(num)
        f = font("BarlowCondensed-ExtraBoldItalic.ttf", 112)
        tw = text_w(n, number, f, 2)
        badge = 78
        gx = (W - (badge + 24 + tw)) // 2
        cy = 258
        n.rounded_rectangle((gx, cy - badge // 2, gx + badge, cy + badge // 2), 20, fill=rgb(c["accent"]))
        num.alpha_composite(icon(48, c["card"]), (int(gx + 15), cy - 24))
        top = n.textbbox((0, 0), number, font=f)
        tx = gx + badge + 24
        draw_spaced(n, (tx, cy - (top[1] + top[3]) // 2), number, f, rgb(c["primary"]), 2)
        n.polygon([(tx + 10, y1 - 22), (tx + tw + 4, y1 - 22), (tx + tw - 4, y1 - 14), (tx + 2, y1 - 14)], fill=rgb(c["accent"]))
    return shadow(card), num


def save_layers(profile, out, style):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    card, num = layers(profile, style)
    card.save(out / "layer-card-logo.png")
    num.save(out / "layer-number.png")
    return out / "layer-card-logo.png", out / "layer-number.png"


def mockups(profile, out, frame):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    base = Image.open(frame).convert("RGBA").resize((W, H))
    files = []
    for s in STYLES:
        card, num = layers(profile, s)
        im = base.copy()
        im.alpha_composite(card)
        im.alpha_composite(num)
        p = out / f"card-{s}.png"
        im.convert("RGB").save(p)
        files.append(p)
    return files


def load_profile(tenant):
    return json.loads((FORMAT_DIR / "tenants" / f"{tenant}.json").read_text(encoding="utf-8"))


def main(argv=None):
    a = argv if argv is not None else sys.argv[1:]
    if len(a) < 3 or a[0] not in ("mockups", "layers"):
        raise SystemExit(__doc__)
    prof = load_profile(a[1])
    opt = dict(zip(a[3::2], a[4::2]))
    if a[0] == "mockups":
        frame = opt.get("--frame") or str(Path(prof["close"]["dir"]) / "speaker-frame.png")
        print(json.dumps([str(p) for p in mockups(prof, a[2], frame)], indent=1))
    else:
        style = opt.get("--style") or (prof.get("brand") or {}).get("card_style") or DEFAULT_STYLE
        print(json.dumps([str(p) for p in save_layers(prof, a[2], style)], indent=1))


if __name__ == "__main__":
    main()


def compose_close(raw, card_png, number_png, out, logo_in, number_in, duration):
    """The saved-close recipe (truenorth-close-v1): talking head held on its last frame to `duration`, the card slides
    down and fades in at the logo cue, the number rises and fades in at the number cue. Local ffmpeg only."""
    import subprocess
    src = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(raw)],
                               capture_output=True, text=True, check=True).stdout)
    pad = max(0.0, duration - src)
    fc = (f"[0:v]tpad=stop_mode=clone:stop_duration={pad:.3f},fps=30,format=yuv420p[base];"
          f"[1:v]format=rgba,fade=t=in:st={logo_in}:d=0.25:alpha=1[card];"
          f"[2:v]format=rgba,fade=t=in:st={number_in}:d=0.2:alpha=1[num];"
          f"[base][card]overlay=x=0:y='if(lt(t,{logo_in}),0,-28*(1-min(1,(t-{logo_in})/0.3)))':eval=frame[b1];"
          f"[b1][num]overlay=x=0:y='if(lt(t,{number_in}),0,18*(1-min(1,(t-{number_in})/0.25)))':eval=frame,format=yuv420p[v];"
          f"[0:a]apad=whole_dur={duration},aresample=48000[a]")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(raw), "-loop", "1", "-t", str(duration), "-i", str(card_png),
                    "-loop", "1", "-t", str(duration), "-i", str(number_png), "-filter_complex", fc, "-map", "[v]", "-map", "[a]",
                    "-t", str(duration), "-c:v", "libx264", "-crf", "16", "-preset", "slow", "-pix_fmt", "yuv420p",
                    "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-movflags", "+faststart", str(out)], check=True)
    return Path(out)
