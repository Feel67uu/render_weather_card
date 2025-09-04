# scripts/render.py — v2 “clean & styled” two-city weather card
# - HiDPI рендер (2x) -> даунскейл для антиалиасинга
# - Градиент неба по коду погоды + лёгкая виньетка
# - Стеклянные карточки с мягкой тенью
# - Дата “на завтра” ниже названия города (формат: Чт, 5 сен)
# - Крупная температура с маленьким °C
# - Строка условия (“Небольшой дождь” и т.п.)
# - Нижние «пилюли»: tmin…tmax, ветер, дождь

from __future__ import annotations
import os, json, random
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, Tuple
from PIL import Image, ImageDraw, ImageFont, ImageFilter

try:
    from zoneinfo import ZoneInfo
except Exception:
    ZoneInfo = None  # fallback UTC

ROOT      = Path(__file__).resolve().parents[1]
ASSETS    = ROOT / "assets"
FONTS_DIR = ASSETS / "fonts"
ICONS_DIR = ASSETS / "icons"
OUT_DIR   = ROOT / "weather"

# Итоговый размер и HiDPI-коэф (для гладкости)
BASE_W, BASE_H = 1600, 900
SCALE = 2
W, H  = BASE_W*SCALE, BASE_H*SCALE

# Цвета
WHITE        = (255,255,255,255)
MUTED        = (215,225,236,255)
TEXT_SHADOW  = (0,0,0,140)
GLASS_FILL   = (255,255,255,46)
GLASS_STROKE = (255,255,255,72)

RU_DOW = ["Пн","Вт","Ср","Чт","Пт","Сб","Вс"]
RU_MON = ["янв","фев","мар","апр","май","июн","июл","авг","сен","окт","ноя","дек"]

def load_payload() -> Dict[str,Any]:
    ev_path = os.environ.get("GITHUB_EVENT_PATH")
    if not ev_path or not os.path.exists(ev_path):
        return {}
    with open(ev_path, "r", encoding="utf-8") as f:
        ev = json.load(f)
    return ev.get("client_payload") or {}

def to_float(x, default=0.0) -> float:
    try: return float(x)
    except Exception: return float(default)

def fmt_temp(v) -> str: return f"{int(round(to_float(v))):+d}"
def fmt_temp_full(v) -> str: return f"{int(round(to_float(v))):+d}°C"
def fmt_wind(v) -> str: return f"ветер {int(round(to_float(v)))} м/с"
def fmt_rain(p) -> str: return f"дождь {int(round(to_float(p)))}%"

def tomorrow_label(today_iso: str, tz: str) -> str:
    try:
        d0 = datetime.strptime(today_iso, "%Y-%m-%d")
    except Exception:
        d0 = datetime.utcnow()
    if ZoneInfo and tz:
        try: d0 = d0.replace(tzinfo=ZoneInfo(tz))
        except Exception: pass
    d1 = (d0 + timedelta(days=1)).date()
    return f"{RU_DOW[d1.weekday()]}, {d1.day} {RU_MON[d1.month-1]}"

def condition_ru(code: int) -> str:
    c = int(to_float(code))
    # укрупнённые описания в духе приложений погоды
    if c in (0,1): return "Ясно"
    if c == 2:     return "Переменная облачность"
    if c == 3:     return "Облачно"
    if c in (45,48): return "Туман"
    if c in (51,53,55): return "Морось"
    if c in (61,63,65,80,81,82): return "Небольшой дождь"
    if c in (66,67): return "Ледяной дождь"
    if c in (71,73,75,77,85,86): return "Снег"
    if c in (95,96,99): return "Гроза"
    return "Облачно"

def grad_by_code(code: int) -> Tuple[Tuple[int,int,int], Tuple[int,int,int]]:
    c = int(to_float(code))
    # верх -> низ (небо)
    if c in (0,1):                      return (25,54,109), (10,22,55)    # ясное небо, глубокий синий
    if c in (61,63,65,80,81,82,51,53):  return (28,58,86),  (9,26,43)     # дождливо
    if c in (71,73,75,77,85,86):        return (38,68,108), (13,29,58)    # снежно/холодно
    if c in (95,96,99):                 return (53,38,94),  (20,16,40)    # гроза, фиолет
    return (30,52,84), (11,22,46)                                    # облачно

def load_font(size: int, bold=False) -> ImageFont.FreeTypeFont:
    pref = FONTS_DIR / ("Roboto-Bold.ttf" if bold else "Roboto-Regular.ttf")
    if pref.exists():
        return ImageFont.truetype(str(pref), size=size)
    for cand in FONTS_DIR.glob("*.ttf"):
        try: return ImageFont.truetype(str(cand), size=size)
        except Exception: pass
    try:
        base = "/usr/share/fonts/truetype/dejavu/DejaVuSans"
        return ImageFont.truetype(base + ("-Bold.ttf" if bold else ".ttf"), size=size)
    except Exception:
        return ImageFont.load_default()

def text_size(draw, text, font):
    l,t,r,b = draw.textbbox((0,0), text, font=font)
    return r-l, b-t

def draw_shadow(w,h, radius=40, blur=36, alpha=170):
    base = Image.new("RGBA", (w+blur*2, h+blur*2), (0,0,0,0))
    d = ImageDraw.Draw(base, "RGBA")
    d.rounded_rectangle((blur,blur, blur+w-1, blur+h-1), radius=radius, fill=(0,0,0,alpha))
    return base.filter(ImageFilter.GaussianBlur(blur)).crop((blur,blur, blur+w, blur+h))

def rounded_panel(w,h, radius=40):
    img = Image.new("RGBA", (w,h), (0,0,0,0))
    d = ImageDraw.Draw(img, "RGBA")
    d.rounded_rectangle((0,0,w-1,h-1), radius=radius, fill=GLASS_FILL, outline=GLASS_STROKE, width=3)
    return img

def draw_text_shadowed(draw, xy, text, font, fill=WHITE, shadow=TEXT_SHADOW, anchor="mm", offset=(0,2)):
    x,y = xy
    sx,sy = x+offset[0], y+offset[1]
    draw.text((sx,sy), text, font=font, fill=shadow, anchor=anchor)
    draw.text((x,y),   text, font=font, fill=fill,    anchor=anchor)

def icon_path(code: int) -> Path:
    c = int(to_float(code))
    if c in (95,96,99): name="storm.png"
    elif c in (71,73,75,77,85,86): name="snow.png"
    elif c in (61,63,65,80,81,82,51,53,55): name="rain.png"
    elif c in (0,1): name="sun.png"
    else: name="cloud.png"
    p = ICONS_DIR / name
    return p if p.exists() else ICONS_DIR / "cloud.png"

def load_icon(code: int, height: int) -> Image.Image:
    try:
        im = Image.open(icon_path(code)).convert("RGBA")
    except Exception:
        im = Image.new("RGBA",(256,256),(255,255,255,0))
    w = int(height * im.width / im.height)
    return im.resize((w,height), Image.LANCZOS)

def draw_chip(canvas: Image.Image, draw: ImageDraw.ImageDraw, cx, cy, text, font,
              pad_x=26, pad_y=12, radius=22, fg=WHITE, bg_alpha=64):
    tw,th = text_size(draw, text, font)
    bw,bh = tw+pad_x*2, th+pad_y*2
    pill = Image.new("RGBA", (bw,bh), (0,0,0,0))
    d2 = ImageDraw.Draw(pill, "RGBA")
    d2.rounded_rectangle((0,0,bw-1,bh-1), radius=radius,
                         fill=(255,255,255,bg_alpha), outline=(255,255,255,90), width=2)
    ox,oy = int(cx-bw/2), int(cy-bh/2)
    canvas.paste(pill, (ox,oy), pill)
    draw.text((ox+pad_x, oy+pad_y), text, font=font, fill=fg)

def draw_rain_overlay(bg: Image.Image, intensity=0.12):
    # лёгкие диагональные «дождинки»
    d = ImageDraw.Draw(bg, "RGBA")
    step = int(20*SCALE)
    ln   = int(18*SCALE)
    alpha= int(255*intensity)
    for x in range(-ln, W, step):
        for y in range(0, H, int(40*SCALE)):
            d.line((x, y, x+ln, y+ln), fill=(255,255,255,alpha//6), width=1)

def draw_vignette(bg: Image.Image):
    # мягкая виньетка по краям
    overlay = Image.new("L", (W,H), 0)
    d = ImageDraw.Draw(overlay, "L")
    # большой эллипс с размытием
    margin = int(100*SCALE)
    d.ellipse((margin, margin, W-margin, H-margin), fill=180)
    blur = overlay.filter(ImageFilter.GaussianBlur(int(220*SCALE)))
    mask = Image.eval(blur, lambda p: 255 - p)
    shade = Image.new("RGBA", (W,H), (0,0,0,120))
    bg.paste(shade, (0,0), mask)

def draw_city_card(canvas: Image.Image, cx: int, top: int, cw: int, ch: int,
                   city: Dict[str,Any], payload: Dict[str,Any], fonts: Dict[str,ImageFont.FreeTypeFont]):
    d = ImageDraw.Draw(canvas, "RGBA")

    # панель и тень
    shadow = draw_shadow(cw, ch, radius=int(36*SCALE), blur=int(32*SCALE), alpha=170)
    canvas.paste(shadow, (cx-cw//2, top+int(6*SCALE)), shadow)
    panel = rounded_panel(cw, ch, radius=int(36*SCALE))
    canvas.paste(panel, (cx-cw//2, top), panel)

    # данные
    cur   = (city or {}).get("current") or {}
    daily = (city or {}).get("daily")   or {}
    name  = (city or {}).get("name") or "—"
    code  = int(to_float(cur.get("code", 3)))

    # Заголовок
    title_y = top + int(ch*0.10)
    draw_text_shadowed(d, (cx, title_y), name, fonts["title"], fill=WHITE, anchor="mm")

    # Дата-чип под заголовком
    chip = tomorrow_label(payload.get("date",""), payload.get("tz",""))
    draw_chip(canvas, d, cx, title_y + int(42*SCALE), chip, fonts["small"])

    # Иконка + температура
    icon_h = int(ch*0.38)
    icon   = load_icon(code, icon_h)
    ix     = cx - int(cw*0.22)
    iy     = top + int(ch*0.42)
    canvas.paste(icon, (ix - icon.width//2, iy - icon.height//2), icon)

    # Крупная температура с маленьким °C
    ttext = fmt_temp(cur.get("temp",0))
    # «число»
    draw_text_shadowed(d, (cx + int(cw*0.10), iy), ttext, fonts["temp_num"], fill=WHITE, anchor="mm")
    # «°C»
    deg_y = iy - int(28*SCALE)
    d.text((cx + int(cw*0.10) + int(80*SCALE), deg_y), "°C", font=fonts["temp_unit"], fill=WHITE, anchor="mm")

    # Условие
    cond = condition_ru(code)
    d.text((cx, top + int(ch*0.66)), cond, font=fonts["medium"], fill=MUTED, anchor="mm")

    # Нижняя строка — три «пилюли»
    y_pills = top + int(ch*0.84)
    rng  = f"{fmt_temp_full(daily.get('tmin',0))} … {fmt_temp_full(daily.get('tmax',0))}"
    wnd  = fmt_wind(cur.get('wind',0))
    rain = fmt_rain(daily.get('precip_prob',0))

    draw_chip(canvas, d, cx - int(cw*0.23), y_pills, rng,  fonts["chip"])
    draw_chip(canvas, d, cx,                  y_pills, wnd,  fonts["chip"])
    draw_chip(canvas, d, cx + int(cw*0.23),  y_pills, rain, fonts["chip"])

def main():
    payload = load_payload()
    job_id  = str(payload.get("job_id") or "no_job").strip()
    cities  = payload.get("cities") or []
    tz      = payload.get("tz","")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUT_DIR / f"{job_id}.png"

    # Выберем код погоды первого города для фона (как доминирующий)
    dom_code = int(to_float(((cities or [{}])[0].get("current") or {}).get("code", 3)))
    top_col, bot_col = grad_by_code(dom_code)

    # Градиент неба
    bg = Image.new("RGB", (W,H), 0)
    strip = Image.new("RGB", (1,H))
    for y in range(H):
        r = top_col[0] + (bot_col[0]-top_col[0]) * y // max(H-1,1)
        g = top_col[1] + (bot_col[1]-top_col[1]) * y // max(H-1,1)
        b = top_col[2] + (bot_col[2]-top_col[2]) * y // max(H-1,1)
        strip.putpixel((0,y), (r,g,b))
    bg = strip.resize((W,H), Image.BILINEAR).convert("RGBA")

    # Лёгкая виньетка
    draw_vignette(bg)

    # Если дождь — добавим тонкие диагональные «дождинки»
    if dom_code in (61,63,65,80,81,82,51,53,55):
        draw_rain_overlay(bg, intensity=0.10)

    # Шрифты (HiDPI)
    fonts = {
        "title":     load_font(int(46*SCALE), True),
        "temp_num":  load_font(int(130*SCALE), True),
        "temp_unit": load_font(int(56*SCALE),  True),
        "medium":    load_font(int(36*SCALE)),
        "small":     load_font(int(30*SCALE)),
        "chip":      load_font(int(30*SCALE)),
    }

    if len(cities) < 2:
        d = ImageDraw.Draw(bg, "RGBA")
        draw_text_shadowed(d, (W//2, H//2), "Недостаточно данных", fonts["title"], WHITE, anchor="mm")
        bg.resize((BASE_W,BASE_H), Image.LANCZOS).save(out_path)
        print(f"Saved: {out_path}")
        return

    # Сетка
    margin_x = int(64*SCALE)
    cw = int((W - margin_x*3)/2)
    ch = int(H*0.76)
    top = int(H*0.12)
    cx1 = margin_x + cw//2
    cx2 = margin_x*2 + cw + cw//2

    draw_city_card(bg, cx1, top, cw, ch, cities[0], payload, fonts)
    draw_city_card(bg, cx2, top, cw, ch, cities[1], payload, fonts)

    # Вертикальный делитель между карточками (тонкий и полупрозрачный)
    d = ImageDraw.Draw(bg, "RGBA")
    d.line((W//2, top+int(10*SCALE), W//2, top+ch-int(10*SCALE)), fill=(255,255,255,55), width=int(2*SCALE))

    # Даунскейл в финал
    final = bg.resize((BASE_W, BASE_H), Image.LANCZOS)
    final.save(out_path)
    print(f"Saved: {out_path}")

if __name__ == "__main__":
    main()
