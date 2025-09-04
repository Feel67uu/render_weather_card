# scripts/render.py  — airy/glass версия
from __future__ import annotations
import json, os
from datetime import datetime, timedelta
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageOps

try:
    from zoneinfo import ZoneInfo
except Exception:
    ZoneInfo = None

ROOT       = Path(__file__).resolve().parents[1]
ASSETS     = ROOT / "assets"
FONTS_DIR  = ASSETS / "fonts"
ICONS_DIR  = ASSETS / "icons"
PANEL_PATH = None  # не используем тёмную плашку, рисуем градиент

WHITE = (255, 255, 255, 255)
GLASS_FILL = (255, 255, 255, 26)      # ~10% белого
GLASS_STROKE = (255, 255, 255, 40)
SHADOW = (0, 0, 0, 180)

RU_DOW = ["Пн","Вт","Ср","Чт","Пт","Сб","Вс"]
RU_MON = ["янв","фев","мар","апр","май","июн","июл","авг","сен","окт","ноя","дек"]

def load_payload() -> dict:
    path = os.environ.get("GITHUB_EVENT_PATH")
    if not path or not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        evt = json.load(f)
    return evt.get("client_payload") or {}

def ru_date_tomorrow(today_iso: str, tz: str) -> str:
    try:
        dt = datetime.strptime(today_iso, "%Y-%m-%d")
    except Exception:
        dt = datetime.utcnow()
    if ZoneInfo and tz:
        try: dt = dt.replace(tzinfo=ZoneInfo(tz))
        except Exception: pass
    d = (dt + timedelta(days=1)).date()
    return f"{RU_DOW[d.weekday()]}, {d.day} {RU_MON[d.month-1]}"

def to_float(x, default=0.0): 
    try: return float(x)
    except Exception: return float(default)

def fmt_temp(v) -> str: return f"{int(round(to_float(v))):+d}°C"
def fmt_wind(v) -> str: return f"ветер {int(round(to_float(v)))}"
def fmt_rain(p) -> str:  return f"дождь {int(round(to_float(p)))}%"

def load_font(size: int, bold=False):
    pref = FONTS_DIR / ("Roboto-Bold.ttf" if bold else "Roboto-Regular.ttf")
    if pref.exists():
        return ImageFont.truetype(str(pref), size=size)
    for cand in FONTS_DIR.glob("*.ttf"):
        try: return ImageFont.truetype(str(cand), size=size)
        except Exception: pass
    # системные fallback
    try:
        base = "/usr/share/fonts/truetype/dejavu/DejaVuSans"
        return ImageFont.truetype(base + ("-Bold.ttf" if bold else ".ttf"), size=size)
    except Exception:
        return ImageFont.load_default()

def icon_path(code: int) -> Path:
    c = int(to_float(code))
    if c in (95,96,99):      name="storm.png"
    elif c in (71,73,75,77,85,86): name="snow.png"
    elif c in (51,53,55,61,63,65,80,81,82): name="rain.png"
    elif c in (0,1):         name="sun.png"
    else:                    name="cloud.png"
    p = ICONS_DIR / name
    return p if p.exists() else ICONS_DIR / "cloud.png"

def accent_from_code(code: int):
    c = int(to_float(code))
    if c in (0,1):                      # sunny
        return (255, 194, 41)           # amber
    if c in (61,63,65,80,81,82,51,53):  # rain/drizzle
        return (74, 144, 226)           # blue
    if c in (71,73,75,77,85,86):        # snow
        return (72, 209, 204)           # cyan
    if c in (95,96,99):                 # storm
        return (171, 71, 188)           # purple
    return (147, 170, 190)              # cloudy blue-gray

def linear_gradient(size, top=(16,22,34), bottom=(9,16,30)):
    w,h = size
    grad = Image.new("RGB", (1,h), 0)
    top = tuple(top); bottom = tuple(bottom)
    for y in range(h):
        r = top[0]   + (bottom[0]-top[0])   * y//max(h-1,1)
        g = top[1]   + (bottom[1]-top[1])   * y//max(h-1,1)
        b = top[2]   + (bottom[2]-top[2])   * y//max(h-1,1)
        grad.putpixel((0,y), (r,g,b))
    return grad.resize((w,h), Image.BILINEAR)

def rounded_rect(size, radius, fill, outline=None, outline_w=2):
    w,h = size
    img = Image.new("RGBA", (w,h), (0,0,0,0))
    d = ImageDraw.Draw(img, "RGBA")
    d.rounded_rectangle((0,0,w-1,h-1), radius=radius, fill=fill, outline=outline, width=outline_w)
    return img

def drop_shadow(box_img, blur=16, shift=(0,8)):
    w,h = box_img.size
    shadow = Image.new("RGBA", (w+blur*2, h+blur*2), (0,0,0,0))
    sdraw  = ImageDraw.Draw(shadow)
    sdraw.rounded_rectangle((blur,blur, blur+w-1, blur+h-1), radius=24, fill=SHADOW)
    return shadow.filter(ImageFilter.GaussianBlur(blur)).crop((blur-shift[0], blur-shift[1], blur-shift[0]+w, blur-shift[1]+h))

def paste_center(dst, src, cx, cy):
    w,h = src.size
    dst.paste(src, (int(cx-w/2), int(cy-h/2)), src if src.mode=="RGBA" else None)

def draw_chip(draw, pos, text, font, fg, bg_alpha=60, pad_x=18, pad_y=8, radius=16, anchor="mm"):
    # рисуем чип (закруглённая плашка)
    x,y = pos
    tw, th = draw.textbbox((0,0), text, font=font)[2:]
    bw, bh = tw+pad_x*2, th+pad_y*2
    box = Image.new("RGBA", (bw,bh), (0,0,0,0))
    ImageDraw.Draw(box).rounded_rectangle((0,0,bw-1,bh-1), radius=radius, fill=(fg[0],fg[1],fg[2],bg_alpha))
    # позиционирование по anchor
    if anchor=="mm":
        ox, oy = int(x-bw/2), int(y-bh/2)
    elif anchor=="lm":
        ox, oy = x, int(y-bh/2)
    elif anchor=="rm":
        ox, oy = int(x-bw), int(y-bh/2)
    else:
        ox, oy = x, y
    canvas = draw.im
    canvas.paste(box, (ox,oy), box)
    draw.text((ox+pad_x, oy+pad_y), text, font=font, fill=WHITE)

def draw_city(canvas: Image.Image, cx: int, top_y: int, city: dict, payload: dict, fonts: dict):
    W,H = canvas.size
    d = ImageDraw.Draw(canvas, "RGBA")

    # карточка-стекло
    card_w = int(W*0.44)
    card_h = int(H*0.68)
    card   = rounded_rect((card_w, card_h), radius=28, fill=GLASS_FILL, outline=GLASS_STROKE, outline_w=2)
    shadow = drop_shadow(card, blur=24, shift=(0,12))
    paste_center(canvas, shadow, cx, top_y + card_h//2 + 6)
    paste_center(canvas, card,   cx, top_y + card_h//2)

    cur  = city.get("current") or {}
    code = cur.get("code", 3)
    ACC  = accent_from_code(code)

    # Заголовки
    title = (city.get("name") or "—").strip()
    d.text((cx, top_y+24), title, fill=WHITE, font=fonts["title"], anchor="mt")
    d.text((cx, top_y+24+fonts["title_lead"]), ru_date_tomorrow(payload.get("date",""), payload.get("tz","")),
           fill=WHITE, font=fonts["small"], anchor="mt")

    # Иконка
    try:
        ico = Image.open(icon_path(code)).convert("RGBA")
    except Exception:
        ico = Image.new("RGBA",(256,256),(255,255,255,0))
    ih = int(H*0.22); iw = int(ih*ico.width/ico.height)
    ico = ico.resize((iw,ih), Image.LANCZOS)
    paste_center(canvas, ico, cx, top_y+int(card_h*0.42))

    # Температура — крупно, цветом акцента
    temp_txt = fmt_temp(cur.get("temp", 0))
    d.text((cx, top_y+int(card_h*0.60)), temp_txt, fill=ACC, font=fonts["temp"], anchor="mm")

    # Подпись о ветре
    wind_txt = fmt_wind(cur.get("wind", 0))
    d.text((cx, top_y+int(card_h*0.67)), wind_txt, fill=WHITE, font=fonts["medium"], anchor="mm")

    # Низ: чипы «мин…макс» и «дождь %»
    daily = city.get("daily") or {}
    range_txt = f"{fmt_temp(daily.get('tmin',0))}…{fmt_temp(daily.get('tmax',0))}"
    rain_txt  = fmt_rain(daily.get('precip_prob',0))
    gap = int(W*0.03)
    draw_chip(d, (cx-gap, top_y+int(card_h*0.83)), range_txt, fonts["chip"], ACC, anchor="rm")
    draw_chip(d, (cx+gap, top_y+int(card_h*0.83)), rain_txt,  fonts["chip"], ACC, anchor="lm")

def main():
    payload = load_payload()
    job_id  = str(payload.get("job_id") or "no_job").strip()
    cities  = payload.get("cities") or []

    out_dir = ROOT / "weather"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{job_id}.png"

    # холст и фон-градиент
    W,H = 1600, 900
    bg  = linear_gradient((W,H), top=(15,22,40), bottom=(9,14,28))  # тёмный небесный
    img = bg.convert("RGBA")

    if len(cities) < 2:
        d = ImageDraw.Draw(img)
        d.text((W//2,H//2),"Нет данных", fill=WHITE, font=load_font(64, True), anchor="mm")
        img.save(out_path); print(f"Saved: {out_path}"); return

    # шрифты
    fonts = {
        "title":      load_font(int(H*0.060), bold=True),
        "title_lead": int(H*0.050),
        "temp":       load_font(int(H*0.115), bold=True),
        "medium":     load_font(int(H*0.045), bold=False),
        "small":      load_font(int(H*0.038), bold=False),
        "chip":       load_font(int(H*0.036), bold=False),
    }

    top_y = int(H*0.08)
    draw_city(img, W//4,     top_y, cities[0], payload, fonts)
    draw_city(img, 3*W//4,   top_y, cities[1], payload, fonts)

    img.save(out_path)
    print(f"Saved: {out_path}")

if __name__ == "__main__":
    main()
