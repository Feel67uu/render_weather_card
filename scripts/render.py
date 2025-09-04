import sys, json, os
from PIL import Image, ImageDraw, ImageFont

payload = json.loads(sys.argv[1])
job_id = str(payload.get("job_id", "noid"))
texts  = payload.get("texts", {})
icons  = payload.get("icons", {})

BASE_IMG = "assets/base_weather_plain_panel.png"
ICON1    = f"assets/icons/{icons.get('c1','_none.png')}"
ICON2    = f"assets/icons/{icons.get('c2','_none.png')}"

FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FONT_REG  = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"

img = Image.open(BASE_IMG).convert("RGBA")
draw = ImageDraw.Draw(img)

f_head = ImageFont.truetype(FONT_BOLD, 46)
f_big  = ImageFont.truetype(FONT_BOLD, 58)

draw.text((120,  60), texts.get("head",""),  fill=(255,255,255,255), font=f_head)
draw.text((100, 240), texts.get("left",""),  fill=(255,255,255,255), font=f_big)
draw.text((720, 240), texts.get("right",""), fill=(255,255,255,255), font=f_big)

def paste_icon(path, xy, size):
    if os.path.exists(path):
        ic = Image.open(path).convert("RGBA")
        if size: ic = ic.resize(size, Image.LANCZOS)
        img.paste(ic, xy, ic)

paste_icon(ICON1, (100, 110), (120,120))
paste_icon(ICON2, (720, 110), (120,120))

os.makedirs("weather", exist_ok=True)
out_path = f"weather/{job_id}.png"
img.save(out_path, "PNG")
print("saved:", out_path)
