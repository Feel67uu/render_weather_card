# scripts/render.py
import os, json
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

# ---------- helpers ----------
def load_font(path_candidates, size):
    for p in path_candidates:
        if Path(p).exists():
            try:
                return ImageFont.truetype(str(p), size=size)
            except Exception:
                pass
    return ImageFont.load_default()

def draw_text_centered(draw, xy_center, text, font, fill=(255,255,255,255), stroke=2):
    x, y = xy_center
    w, h = draw.textbbox((0,0), text, font=font, stroke_width=stroke)[2:]
    draw.text((x - w/2, y - h/2), text, font=font, fill=fill,
              stroke_width=stroke, stroke_fill=(0,0,0,160))

def icon_name_by_wmo(code:int)->str:
    if code in (0,):            return "sun"
    if code in (1,2,3,45,48):   return "cloud"
    if 51 <= code <= 67:        return "rain"
    if 71 <= code <= 77:        return "snow"
    if 95 <= code <= 99:        return "storm"
    return "cloud"

def to_float(x):
    try:
        if x is None: return None
        # иногда из Make прилетает строка — приводим
        return float(x)
    except (TypeError, ValueError):
        return None

def fmt_num(x):
    return f"{int(round(x))}" if x is not None else "—"

# ---------- read payload ----------
event_path = os.environ["GITHUB_EVENT_PATH"]
event_obj = json.load(open(event_path, "r"))
payload = event_obj.get("client_payload", {})

job_id = payload.get("job_id", "no_job")
tz     = payload.get("tz","")
date   = payload.get("date","")
cities = payload.get("cities", [])  # ожидаем до 2 городов

# ---------- assets ----------
ROOT   = Path(__file__).resolve().parents[1]
assets = ROOT / "assets"
icons  = assets / "icons"

base_path = assets / "base_weather_plain_panel.png"
base = Image.open(base_path).convert("RGBA")
W, H = base.size

fonts_dir = assets / "fonts"
font_bold  = load_font([
    fonts_dir/"Inter-SemiBold.ttf",
    fonts_dir/"Roboto-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
], size=46)
font_reg   = load_font([
    fonts_dir/"Inter-Regular.ttf",
    fonts_dir/"Roboto-Regular.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
], size=36)
font_small = load_font([
    fonts_dir/"Inter-Regular.ttf",
    fonts_dir/"Roboto-Regular.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
], size=28)

img = base.copy()
draw = ImageDraw.Draw(img)

if date or tz:
    hdr = f"{date} • {tz}".strip(" •")
    draw_text_centered(draw, (W/2, 40), hdr, font_small)

panels = [
    (0, 0, W//2, H),
    (W//2, 0, W, H),
]

def paste_icon(center_xy, icon_name):
    p = icons / f"{icon_name}.png"
    if not p.exists():
        p = icons / "cloud.png"
    ico = Image.open(p).convert("RGBA")
    target_h = int(H * 0.45)
    ratio = target_h / ico.height
    ico = ico.resize((int(ico.width*ratio), target_h), Image.LANCZOS)
    x = int(center_xy[0]-ico.width/2)
    y = int(center_xy[1]-ico.height/2)
    img.alpha_composite(ico, (x,y))

def render_city(panel_box, city):
    L, T, R, B = panel_box
    cx = (L + R)//2

    name = city.get("name","")
    cur  = city.get("current", {}) or {}
    daily= city.get("daily", {}) or {}

    temp = to_float(cur.get("temp"))
    wind = to_float(cur.get("wind"))
    code = int(to_float(cur.get("code")) or 0)

    tmax = to_float(daily.get("tmax"))
    tmin = to_float(daily.get("tmin"))
    pr   = to_float(daily.get("precip"))

    draw_text_centered(draw, (cx, T + 80), name, font_bold)
    paste_icon((cx, T + int(H*0.48)), icon_name_by_wmo(code))

    line1 = f"{fmt_num(temp)}°C  •  wind {fmt_num(wind)}"
    draw_text_centered(draw, (cx, T + int(H*0.78)), line1, font_reg)

    tail = []
    if tmin is not None and tmax is not None:
        tail.append(f"{fmt_num(tmin)}…{fmt_num(tmax)}°C")
    if pr is not None:
        tail.append(f"rain {fmt_num(pr)}%")
    if tail:
        draw_text_centered(draw, (cx, T + int(H*0.90)), "  •  ".join(tail), font_small)

for i, panel in enumerate(panels):
    data = cities[i] if i < len(cities) else {}
    render_city(panel, data)

out_dir = ROOT / "weather"
out_dir.mkdir(parents=True, exist_ok=True)
out_path = out_dir / f"{job_id}.png"
img.save(out_path, format="PNG")
print("Saved", out_path)
