# scripts/render.py — two-city weather card, frosted glass, RU UI

from __future__ import annotations
import json, os, random
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, Tuple
from PIL import Image, ImageDraw, ImageFont, ImageFilter

try:
    from zoneinfo import ZoneInfo
except Exception:
    ZoneInfo = None

# ---------- paths ----------
ROOT      = Path(__file__).resolve().parents[1]
ASSETS    = ROOT / "assets"
FONTS     = ASSETS / "fonts"
ICONS     = ASSETS / "icons"
OUT       = ROOT / "weather"

# ---------- canvas ----------
BASE_W, BASE_H = 1600, 900
SCALE          = 2
W, H           = BASE_W*SCALE, BASE_H*SCALE

# ---------- colors ----------
WHITE      = (255,255,255,255)
WHITE_MUT  = (220,230,240,255)
MUTED      = (200,210,220,255)
PANEL_STROKE = (255,255,255,90)
TEXT_SHADOW  = (0,0,0,140)

BG_TOP    = (18,28,46)   # night-blue
BG_BOTTOM = (7,13,28)

RU_DOW = ["Пн","Вт","Ср","Чт","Пт","Сб","Вс"]
RU_MON = ["янв","фев","мар","апр","май","июн","июл","авг","сен","окт","ноя","дек"]

# ---------- helpers ----------
def load_payload() -> Dict[str,Any]:
    path = os.environ.get("GITHUB_EVENT_PATH")
    if not path or not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        evt = json.load(f)
    return evt.get("client_payload") or {}

def to_float(x, default=0.0) -> float:
    try: return float(x)
    except Exception: return float(default)

def fmt_temp(v) -> str: return f"{int(round(to_float(v))):+d}°C"
def fmt_wind(v) -> str: return f"ветер {int(round(to_float(v)))} м/с"
def fmt_rain(p) -> str:  return f"дождь {int(round(to_float(p)))}%"

def tomorrow_label(today_iso: str, tz: str) -> str:
    try:
        d0 = datetime.strptime(today_iso, "%Y-%m-%d")
    except Exception:
        d0 = datetime.utcnow()
    if ZoneInfo and tz:
        try: d0 = d0.replace(tzinfo=ZoneInfo(tz))
        except Exception: pass
    d1 = (d0 + timedelta(days=1)).date()
    return f"Завтра, {RU_DOW[d1.weekday()]}, {d1.day} {RU_MON[d1.month-1]}"

def load_font(sz: int, bold=False) -> ImageFont.FreeTypeFont:
    path = FONTS / ("Roboto-Bold.ttf" if bold else "Roboto-Regular.ttf")
    if path.exists():
        return ImageFont.truetype(str(path), sz)
    # fallbacks
    try:
        base = "/usr/share/fonts/truetype/dejavu/DejaVuSans"
        return ImageFont.truetype(base + ("-Bold.ttf" if bold else ".ttf"), sz)
    except Exception:
        return ImageFont.load_default()

def txt_size(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont) -> Tuple[int,int]:
    l,t,r,b = draw.textbbox((0,0), text, font=font)
    return r-l, b-t

def draw_shadowed(draw, xy, text, font, fill=WHITE, shadow=TEXT_SHADOW, anchor="mm", off=(0,2)):
    x,y = xy
    draw.text((x+off[0], y+off[1]), text, font=font, fill=shadow, anchor=anchor)
    draw.text((x, y), text, font=font, fill=fill, anchor=anchor)

def gradient_bg(size, top, bottom) -> Image.Image:
    w,h = size
    strip = Image.new("RGB", (1,h), 0)
    for y in range(h):
        k = y/max(h-1,1)
        r = int(top[0]*(1-k)+bottom[0]*k)
        g = int(top[1]*(1-k)+bottom[1]*k)
        b = int(top[2]*(1-k)+bottom[2]*k)
        strip.putpixel((0,y),(r,g,b))
    return strip.resize((w,h), Image.BILINEAR)

def weather_effect(canvas: Image.Image, code: int):
    """Rain / snow overlay depending on weather code (very subtle)."""
    rnd = random.Random(42)
    layer = Image.new("RGBA", canvas.size, (0,0,0,0))
    d = ImageDraw.Draw(layer, "RGBA")
    if int(to_float(code)) in (71,73,75,77,85,86):  # snow
        n = 250
        for _ in range(n):
            x = rnd.randint(0, W-1); y = rnd.randint(0, H-1)
            a = rnd.randint(20,70)
            r = rnd.randint(2,4)
            d.ellipse((x-r,y-r,x+r,y+r), fill=(255,255,255,a))
    elif int(to_float(code)) in (51,53,55,61,63,65,80,81,82,95,96,99):  # rain / thunder
        n = 280
        for _ in range(n):
            x = rnd.randint(-50, W+50); y = rnd.randint(-50, H+50)
            l = rnd.randint(16,26); a = rnd.randint(18,36)
            d.line((x,y, x+int(l*0.4), y+l), fill=(255,255,255,a), width=2)
    canvas.alpha_composite(layer)

def icon_name(code: int) -> str:
    c = int(to_float(code))
    if c in (95,96,99): return "storm.png"
    if c in (71,73,75,77,85,86): return "snow.png"
    if c in (51,53,55,61,63,65,80,81,82): return "rain.png"
    if c in (0,1): return "sun.png"
    return "cloud.png"

def load_icon(code: int, height: int) -> Image.Image:
    p = ICONS / icon_name(code)
    try:
        im = Image.open(p).convert("RGBA")
    except Exception:
        im = Image.new("RGBA",(256,256),(0,0,0,0))
    w = int(height * im.width / im.height)
    return im.resize((w,height), Image.LANCZOS)

COND_RU = {
    "sun": "Ясно",
    "cloud": "Облачно",
    "rain": "Небольшой дождь",
    "snow": "Снег",
    "storm": "Гроза",
}
def cond_text(code: int) -> str:
    return {
        "sun":   COND_RU["sun"],
        "cloud": COND_RU["cloud"],
        "rain":  COND_RU["rain"],
        "snow":  COND_RU["snow"],
        "storm": COND_RU["storm"],
    }[icon_name(code).split(".")[0]]

# frosted glass panel (blur underlying bg)
def frosted_panel(bg: Image.Image, dst: Image.Image, rect: Tuple[int,int,int,int], radius=40, fill_alpha=70):
    x1,y1,x2,y2 = rect
    crop = bg.crop(rect).filter(ImageFilter.GaussianBlur(18))
    mask = Image.new("L", (x2-x1, y2-y1), 0)
    d = ImageDraw.Draw(mask)
    d.rounded_rectangle((0,0,mask.width-1, mask.height-1), radius=radius, fill=255)
    panel = Image.new("RGBA", (mask.width, mask.height), (255,255,255, fill_alpha))
    frosted = Image.alpha_composite(crop.convert("RGBA"), panel)
    # stroke
    stroke = Image.new("RGBA", frosted.size, (0,0,0,0))
    d2 = ImageDraw.Draw(stroke, "RGBA")
    d2.rounded_rectangle((1,1, stroke.width-2, stroke.height-2), radius=radius, outline=PANEL_STROKE, width=3)
    frosted = Image.alpha_composite(frosted, stroke)
    dst.paste(frosted, (x1,y1), mask)

# ---------- card ----------
def draw_city_card(bg: Image.Image, canvas: Image.Image, rect: Tuple[int,int,int,int],
                   city: Dict[str,Any], payload: Dict[str,Any], fonts: Dict[str,ImageFont.FreeTypeFont]):
    x1,y1,x2,y2 = rect
    cx, cy = (x1+x2)//2, (y1+y2)//2
    w,h = x2-x1, y2-y1
    # frosted panel
    frosted_panel(bg, canvas, rect, radius=int(28*SCALE), fill_alpha=64)
    d = ImageDraw.Draw(canvas,"RGBA")

    # data
    name  = (city or {}).get("name") or "—"
    cur   = (city or {}).get("current") or {}
    daily = (city or {}).get("daily") or {}
    code  = cur.get("code", 3)

    # title + date
    title_y = y1 + int(h*0.12)
    draw_shadowed(d, (cx, title_y), name, fonts["title"], fill=WHITE, anchor="mm")
    date_y  = title_y + int(46*SCALE)
    draw_shadowed(d, (cx, date_y), tomorrow_label(payload.get("date",""), payload.get("tz","")), fonts["small"], fill=WHITE_MUT, anchor="mm", off=(0,1))

    # icon + big temp
    icon_h = int(h*0.42)
    icon   = load_icon(code, icon_h)
    icon_x = x1 + int(w*0.18)
    paste_x = icon_x
    paste_y = y1 + int(h*0.46)
    canvas.paste(icon, (paste_x - icon.width//2, paste_y - icon.height//2), icon)

    big_x = x1 + int(w*0.63)
    big_y = y1 + int(h*0.44)
    draw_shadowed(d, (big_x, big_y), fmt_temp(cur.get("temp",0)), fonts["temp"], fill=WHITE, anchor="mm")

    # condition text
    cond_y = big_y + int(70*SCALE)
    d.text((big_x, cond_y), cond_text(code), font=fonts["medium"], fill=WHITE_MUT, anchor="mm")

    # max/min line
    rng = f"{fmt_temp(daily.get('tmax',0))}  /  {fmt_temp(daily.get('tmin',0))}"
    rng_y = cond_y + int(52*SCALE)
    d.text((big_x, rng_y), rng, font=fonts["medium"], fill=WHITE, anchor="mm")

    # status row
    status = f"{fmt_wind(cur.get('wind',0))}  •  {fmt_rain(daily.get('precip_prob',0))}"
    stat_y = y2 - int(h*0.16)
    d.text((cx, stat_y), status, font=fonts["small"], fill=WHITE_MUT, anchor="mm")

def col_rect(ix: int) -> Tuple[int,int,int,int]:
    margin = int(60*SCALE)
    inner  = int(36*SCALE)
    card_w = (W - margin*2 - inner)//2
    card_h = int(H*0.78)
    top    = int(H*0.12)
    left   = margin + (card_w + inner)*ix
    return (left, top, left+card_w, top+card_h)

# ---------- main ----------
def main():
    payload = load_payload()
    job_id  = str(payload.get("job_id") or "no_job").strip()
    cities  = payload.get("cities") or []
    OUT.mkdir(parents=True, exist_ok=True)
    out_path = OUT / f"{job_id}.png"

    # background with subtle weather effect (by first city code if есть)
    bg = gradient_bg((W,H), BG_TOP, BG_BOTTOM).convert("RGBA")
    if cities:
        code0 = ((cities[0] or {}).get("current") or {}).get("code", 3)
        weather_effect(bg, code0)
    canvas = bg.copy()

    # fonts (2×)
    fonts = {
        "title":  load_font(int(44*SCALE), bold=True),
        "temp":   load_font(int(128*SCALE), bold=True),
        "medium": load_font(int(36*SCALE), bold=False),
        "small":  load_font(int(30*SCALE), bold=False),
    }

    if len(cities) < 2:
        d = ImageDraw.Draw(canvas)
        draw_shadowed(d, (W//2, H//2), "Недостаточно данных", load_font(72*SCALE, True))
    else:
        draw_city_card(bg, canvas, col_rect(0), cities[0], payload, fonts)
        draw_city_card(bg, canvas, col_rect(1), cities[1], payload, fonts)

    final = canvas.resize((BASE_W, BASE_H), Image.LANCZOS)
    final.save(out_path)
    print(f"Saved: {out_path}")

if __name__ == "__main__":
    main()
