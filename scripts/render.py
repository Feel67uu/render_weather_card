# scripts/render.py — clean 2-column weather card (HiDPI + AA)

from __future__ import annotations
import json, os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Tuple, Dict, Any
from PIL import Image, ImageDraw, ImageFont, ImageFilter

try:
    from zoneinfo import ZoneInfo
except Exception:
    ZoneInfo = None  # fallback на UTC

# --- Paths --------------------------------------------------------------------
ROOT      = Path(__file__).resolve().parents[1]
ASSETS    = ROOT / "assets"
FONTS_DIR = ASSETS / "fonts"
ICONS_DIR = ASSETS / "icons"
OUT_DIR   = ROOT / "weather"

# --- Canvas / layout ----------------------------------------------------------
BASE_W, BASE_H = 1600, 900      # итоговый размер
SCALE          = 2              # рендерим в 2x, затем даунскейл (гладкие края)
W, H           = BASE_W*SCALE, BASE_H*SCALE

# --- Colors -------------------------------------------------------------------
WHITE        = (255, 255, 255, 255)
MUTED        = (210, 222, 235, 255)
PANEL_FILL   = (255, 255, 255, 38)    # «стекло»
PANEL_STROKE = (255, 255, 255, 55)
TEXT_SHADOW  = (0, 0, 0, 140)
BG_TOP       = (16, 22, 36)           # фон-градиент
BG_BOTTOM    = (9, 14, 28)

RU_DOW = ["Пн","Вт","Ср","Чт","Пт","Сб","Вс"]
RU_MON = ["янв","фев","мар","апр","май","июн","июл","авг","сен","окт","ноя","дек"]

# --- Utils --------------------------------------------------------------------
def load_payload() -> Dict[str, Any]:
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

def date_tomorrow_str(today_iso: str, tz: str) -> str:
    try:
        d0 = datetime.strptime(today_iso, "%Y-%m-%d")
    except Exception:
        d0 = datetime.utcnow()
    if ZoneInfo and tz:
        try:
            d0 = d0.replace(tzinfo=ZoneInfo(tz))
        except Exception:
            pass
    d1 = (d0 + timedelta(days=1)).date()
    return f"{RU_DOW[d1.weekday()]}, {d1.day} {RU_MON[d1.month-1]}"

def load_font(size: int, bold=False) -> ImageFont.FreeTypeFont:
    pref = FONTS_DIR / ("Roboto-Bold.ttf" if bold else "Roboto-Regular.ttf")
    if pref.exists():
        return ImageFont.truetype(str(pref), size=size)
    # системные fallback’и
    for cand in FONTS_DIR.glob("*.ttf"):
        try: return ImageFont.truetype(str(cand), size=size)
        except Exception: pass
    try:
        base = "/usr/share/fonts/truetype/dejavu/DejaVuSans"
        return ImageFont.truetype(base + ("-Bold.ttf" if bold else ".ttf"), size=size)
    except Exception:
        return ImageFont.load_default()

def text_size(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont) -> Tuple[int,int]:
    l,t,r,b = draw.textbbox((0,0), text, font=font)
    return r-l, b-t

def paste_center(dst: Image.Image, src: Image.Image, cx: int, cy: int):
    w,h = src.size
    dst.paste(src, (int(cx-w/2), int(cy-h/2)), src if src.mode=="RGBA" else None)

def linear_bg(size, top, bottom) -> Image.Image:
    w,h = size
    strip = Image.new("RGB", (1,h), 0)
    for y in range(h):
        r = top[0] + (bottom[0]-top[0]) * y // max(h-1,1)
        g = top[1] + (bottom[1]-top[1]) * y // max(h-1,1)
        b = top[2] + (bottom[2]-top[2]) * y // max(h-1,1)
        strip.putpixel((0,y), (r,g,b))
    return strip.resize((w,h), Image.BILINEAR)

def rounded_panel(size, radius=32, fill=PANEL_FILL, stroke=PANEL_STROKE, stroke_w=3) -> Image.Image:
    w,h = size
    img = Image.new("RGBA", (w,h), (0,0,0,0))
    d = ImageDraw.Draw(img, "RGBA")
    d.rounded_rectangle((0,0,w-1,h-1), radius=radius, fill=fill, outline=stroke, width=stroke_w)
    return img

def soft_shadow(w,h, radius=30, blur=28, alpha=170) -> Image.Image:
    base = Image.new("RGBA", (w+blur*2, h+blur*2), (0,0,0,0))
    d = ImageDraw.Draw(base,"RGBA")
    d.rounded_rectangle((blur,blur, blur+w-1, blur+h-1), radius=radius, fill=(0,0,0,alpha))
    return base.filter(ImageFilter.GaussianBlur(blur)).crop((blur,blur, blur+w, blur+h))

def draw_text_with_shadow(draw, xy, text, font, fill=WHITE, shadow=TEXT_SHADOW, offset=(0,2), anchor="mm"):
    x,y = xy
    sx, sy = x+offset[0], y+offset[1]
    draw.text((sx,sy), text, font=font, fill=shadow, anchor=anchor)
    draw.text((x,y),   text, font=font, fill=fill,    anchor=anchor)

def icon_path(code: int) -> Path:
    c = int(to_float(code))
    if c in (95,96,99):         name="storm.png"
    elif c in (71,73,75,77,85,86): name="snow.png"
    elif c in (51,53,55,61,63,65,80,81,82): name="rain.png"
    elif c in (0,1):            name="sun.png"
    else:                       name="cloud.png"
    p = ICONS_DIR / name
    return p if p.exists() else ICONS_DIR / "cloud.png"

# мягкий акцент (деликатно, без «кислоты»)
def accent_for(code: int) -> Tuple[int,int,int]:
    c = int(to_float(code))
    if c in (0,1):                      return (255, 200, 70)    # солнечно
    if c in (61,63,65,80,81,82,51,53):  return (105, 155, 230)   # дождь
    if c in (71,73,75,77,85,86):        return (110, 210, 210)   # снег
    if c in (95,96,99):                 return (180, 120, 210)   # гроза
    return (180, 195, 210)                                     # облачно

def load_icon(code: int, height: int) -> Image.Image:
    try:
        im = Image.open(icon_path(code)).convert("RGBA")
    except Exception:
        im = Image.new("RGBA",(256,256),(255,255,255,0))
    w = int(height * im.width / im.height)
    return im.resize((w,height), Image.LANCZOS)

# маленькая «чип-плашка»
def draw_chip(canvas: Image.Image, draw: ImageDraw.ImageDraw, center_xy: Tuple[int,int],
              text: str, font: ImageFont.ImageFont, pad_x=24, pad_y=10, radius=18,
              fg=WHITE, bg_alpha=64, anchor="mm"):
    x,y = center_xy
    tw,th = text_size(draw, text, font)
    bw,bh = tw+pad_x*2, th+pad_y*2
    box = Image.new("RGBA", (bw,bh), (0,0,0,0))
    d2  = ImageDraw.Draw(box,"RGBA")
    d2.rounded_rectangle((0,0,bw-1,bh-1), radius=radius,
                         fill=(255,255,255,bg_alpha), outline=(255,255,255,96), width=2)
    if anchor=="mm":
        ox, oy = int(x-bw/2), int(y-bh/2)
    elif anchor=="mt":
        ox, oy = int(x-bw/2), y
    else:
        ox, oy = x,y
    canvas.paste(box, (ox,oy), box)
    draw.text((ox+pad_x, oy+pad_y), text, font=font, fill=fg)

# --- City card ---------------------------------------------------------------
def draw_city_card(canvas: Image.Image, card_xc: int, top_y: int, card_w: int, card_h: int,
                   city: Dict[str,Any], payload: Dict[str,Any], fonts: Dict[str,ImageFont.ImageFont]):
    d = ImageDraw.Draw(canvas,"RGBA")

    # панель
    shadow = soft_shadow(card_w, card_h, radius=36, blur=32, alpha=160)
    paste_center(canvas, shadow, card_xc, top_y + card_h//2 + 6*SCALE)
    panel = rounded_panel((card_w, card_h), radius=36, fill=PANEL_FILL, stroke=PANEL_STROKE, stroke_w=3)
    paste_center(canvas, panel,  card_xc, top_y + card_h//2)

    # данные
    cur   = (city or {}).get("current") or {}
    daily = (city or {}).get("daily")   or {}
    name  = (city or {}).get("name") or "—"
    code  = cur.get("code", 3)
    ACC   = accent_for(code)

    # заголовок
    title_y = top_y + int(card_h*0.08)
    draw_text_with_shadow(d, (card_xc, title_y), name, fonts["title"], fill=WHITE, anchor="mm")

    # чип с датой под заголовком
    chip_text = date_tomorrow_str(payload.get("date",""), payload.get("tz",""))
    draw_chip(canvas, d, (card_xc, title_y + int(44*SCALE)), chip_text, fonts["small"], anchor="mm")

    # иконка + температура в ряд
    icon_h = int(card_h*0.40)  # крупная, но не перегружает
    icon   = load_icon(code, icon_h)
    icon_x = card_xc - int(card_w*0.20)
    paste_center(canvas, icon, icon_x, top_y + int(card_h*0.48))

    temp_text = fmt_temp(cur.get("temp", 0))
    draw_text_with_shadow(d, (card_xc + int(card_w*0.10), top_y + int(card_h*0.48)),
                          temp_text, fonts["temp"], fill=WHITE, anchor="mm")

    # строка статуса
    status = f"{fmt_wind(cur.get('wind',0))}  •  {fmt_rain(daily.get('precip_prob',0))}"
    d.text((card_xc, top_y + int(card_h*0.68)), status, font=fonts["medium"],
           fill=MUTED, anchor="mm")

    # нижний диапазон — одной аккуратной плашкой
    rng = f"{fmt_temp(daily.get('tmin',0))}…{fmt_temp(daily.get('tmax',0))}"
    draw_chip(canvas, d, (card_xc, top_y + int(card_h*0.86)), rng, fonts["chip"], fg=WHITE, anchor="mm")

# --- Main --------------------------------------------------------------------
def main():
    payload = load_payload()
    job_id  = str(payload.get("job_id") or "no_job").strip()
    cities  = payload.get("cities") or []

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUT_DIR / f"{job_id}.png"

    # фон 2×
    bg = linear_bg((W,H), BG_TOP, BG_BOTTOM).convert("RGBA")

    if len(cities) < 2:
        d = ImageDraw.Draw(bg)
        draw_text_with_shadow(d, (W//2, H//2), "Нет данных", load_font(72*SCALE, True), WHITE, anchor="mm")
        bg.resize((BASE_W,BASE_H), Image.LANCZOS).save(out_path)
        print(f"Saved: {out_path}")
        return

    # шрифты 2×
    fonts = {
        "title":  load_font(int(44*SCALE), bold=True),
        "temp":   load_font(int(120*SCALE), bold=True),
        "medium": load_font(int(36*SCALE), bold=False),
        "small":  load_font(int(28*SCALE), bold=False),
        "chip":   load_font(int(30*SCALE), bold=False),
    }

    # сетка
    margin_x = int(64*SCALE)
    card_w   = int((W - margin_x*3)/2)
    card_h   = int(H * 0.76)
    top_y    = int(H * 0.12)
    xc1      = margin_x + card_w//2
    xc2      = margin_x*2 + card_w + card_w//2

    draw_city_card(bg, xc1, top_y, card_w, card_h, cities[0], payload, fonts)
    draw_city_card(bg, xc2, top_y, card_w, card_h, cities[1], payload, fonts)

    # даунскейл в финальный размер (суперсэмплинг = гладкие края/текст)
    final = bg.resize((BASE_W, BASE_H), Image.LANCZOS)
    final.save(out_path)
    print(f"Saved: {out_path}")

if __name__ == "__main__":
    main()
