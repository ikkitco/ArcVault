"""ArcVault logo set: flat vector masters. Run: python make_logo.py (writes the SVGs here).
Render PNGs / the .ico with any SVG tool (e.g. rsvg-convert, Inkscape)."""
GOLD, GOLD_HI, INK, BG, PANEL = "#D5AE58", "#F2D58C", "#E7EAF0", "#0F1218", "#171C24"

# ---------- symbol (master, 32 px and up) ----------
HEX = [(50,4),(89.84,27),(89.84,73),(50,96),(10.16,73),(10.16,27)]
def lerp(a,b,t): return (a[0]+(b[0]-a[0])*t, a[1]+(b[1]-a[1])*t)
fl, fr = lerp(HEX[4],HEX[3],.30), lerp(HEX[2],HEX[3],.30)          # frame stops short: open at the bottom
FRAME = f"M{fl[0]:.2f} {fl[1]:.2f} L{HEX[4][0]} {HEX[4][1]} L{HEX[5][0]} {HEX[5][1]} L50 4 L{HEX[1][0]} {HEX[1][1]} L{HEX[2][0]} {HEX[2][1]} L{fr[0]:.2f} {fr[1]:.2f}"
A_MASTER = "M50 14 L73 90 L65 90 L50 40.43 L35 90 L27 90 Z"   # 8-unit legs, open counter
ARC = "M17 69 Q50 45 83 69"

def mark(frame=GOLD, a=GOLD, arc=GOLD_HI, uid="m", knock=9, arc_w=3.6, frame_w=7):
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" class="mark" role="img" aria-label="ArcVault">
  <defs><mask id="{uid}k" maskUnits="userSpaceOnUse" x="0" y="0" width="100" height="100">
    <rect width="100" height="100" fill="#fff"/><path d="{ARC}" fill="none" stroke="#000" stroke-width="{knock}" stroke-linecap="round"/></mask></defs>
  <g mask="url(#{uid}k)">
    <path d="{FRAME}" fill="none" stroke="{frame}" stroke-width="{frame_w}" stroke-linejoin="miter" stroke-miterlimit="10"/>
    <path d="{A_MASTER}" fill="{a}"/>
  </g>
  <path d="{ARC}" fill="none" stroke="{arc}" stroke-width="{arc_w}" stroke-linecap="round"/>
</svg>'''

# ---------- symbol (small: 16-24 px) - solid hexagon, A knocked out, arc cut through the A ----------
HEX_S = "M50 2 L91.6 26 L91.6 74 L50 98 L8.4 74 L8.4 26 Z"
A_SMALL = "M50 12 L76 90 L64 90 L50 48 L36 90 L24 90 Z"
ARC_S = "M8 67 Q50 43 92 67"
def mark_small(plate=GOLD, a=BG, uid="s"):
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" class="mark" role="img" aria-label="ArcVault">
  <defs><mask id="{uid}k" maskUnits="userSpaceOnUse" x="0" y="0" width="100" height="100">
    <rect width="100" height="100" fill="#fff"/><path d="{ARC_S}" fill="none" stroke="#000" stroke-width="8"/></mask></defs>
  <path d="{HEX_S}" fill="{plate}"/>
  <path d="{A_SMALL}" fill="{a}" mask="url(#{uid}k)"/>
</svg>'''

# ---------- wordmark: geometric caps drawn as strokes (no font needed); A's get crossbars ----------
SW = 3.2
GL = {  # glyph paths on a 20-high cap grid, with advance widths
 "A": ("M0 20 L7 0 L14 20 M2.8 13 L11.2 13", 14),
 "R": ("M0 20 V0 H7.5 A5 5 0 0 1 7.5 10 H0 M7 10 L13 20", 13),
 "C": ("M14 3.6 A9.6 10 0 1 0 14 16.4", 14),
 "V": ("M0 0 L7 20 L14 0", 14),
 "U": ("M0 0 V12.5 A6.5 7.5 0 0 0 13 12.5 V0", 13),
 "L": ("M0 0 V20 H11", 11),
 "T": ("M0 0 H14 M7 0 V20", 14),
}
KERN = {"LT": -4, "VA": -2.5, "RC": -1, "CV": -3.5}
def wordmark(arc_col=GOLD, vault_col=INK, track=6.5):
    x, parts = SW/2, []
    for i, ch in enumerate("ARCVAULT"):
        d, w = GL[ch]
        col = arc_col if i < 3 else vault_col
        parts.append(f'<path transform="translate({x:.2f} {SW/2})" d="{d}" stroke="{col}"/>')
        x += w + track + KERN.get("ARCVAULT"[i:i+2], 0)
    W = x - track + SW/2
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W:.2f} {20+SW:.2f}" class="word" role="img" aria-label="ArcVault">
  <g fill="none" stroke-width="{SW}" stroke-linejoin="miter" stroke-miterlimit="4" stroke-linecap="butt">{"".join(parts)}</g>
</svg>''', W

def write(name, svg):
    open(name, "w").write(svg)

if __name__ == "__main__":
    write("arcvault-mark.svg", mark())
    write("arcvault-mark-small.svg", mark_small())
    write("arcvault-mark-mono-light.svg", mark(INK, INK, INK, "ml"))
    write("arcvault-mark-mono-dark.svg", mark(BG, BG, BG, "md"))
    w, _ = wordmark(); write("arcvault-wordmark.svg", w)
    w2, _ = wordmark(BG, BG); write("arcvault-wordmark-dark.svg", w2)
    print("svgs written")

def inner(svg):
    """Body of an svg string (for nesting)."""
    return svg[svg.index(">")+1:svg.rindex("</svg>")]

def nest(svg, x, y, w, h):
    vb = svg.split('viewBox="')[1].split('"')[0]
    return f'<svg x="{x}" y="{y}" width="{w}" height="{h}" viewBox="{vb}">{inner(svg)}</svg>'

def app_icon():
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 256 256">
  <rect x="8" y="8" width="240" height="240" rx="52" fill="{PANEL}" stroke="#2A3242" stroke-width="2"/>
  {nest(mark(uid="ai"), 48, 44, 160, 160)}
</svg>'''

def lockup(word_h=26, gap=16, mark_px=64, arc_col=GOLD, vault_col=INK, uid="lk", mark_svg=None):
    w, ww = wordmark(arc_col, vault_col)
    wh = 20 + SW
    word_w = ww * word_h / wh
    W = mark_px + gap + word_w
    m = mark_svg or mark(uid=uid)
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W:.1f} {mark_px}">
  {nest(m, 0, 0, mark_px, mark_px)}
  {nest(w, mark_px+gap, (mark_px-word_h)/2, word_w, word_h)}
</svg>''', W

def sheet():
    lab = lambda x, y, t: f'<text x="{x}" y="{y}" fill="#9AA3B5" font-family="DejaVu Sans, sans-serif" font-size="13" letter-spacing="2">{t}</text>'
    lk, lw = lockup(word_h=30, mark_px=72)
    lk_light, _ = lockup(word_h=30, mark_px=72, arc_col="#9A7425", vault_col=BG, uid="ll",
                          mark_svg=mark(BG, BG, "#C9A04A", "ll2"))
    lk_mono, _ = lockup(word_h=30, mark_px=72, arc_col=INK, vault_col=INK, uid="lm", mark_svg=mark(INK, INK, INK, "lm2"))
    sw = "".join(f'<circle cx="{560+i*130}" cy="640" r="34" fill="{c}" stroke="#2A3242"/>'
                 f'<text x="{560+i*130}" y="698" text-anchor="middle" fill="{INK}" font-family="DejaVu Sans" font-size="13">{n}</text>'
                 f'<text x="{560+i*130}" y="718" text-anchor="middle" fill="#9AA3B5" font-family="DejaVu Sans Mono" font-size="12">{c}</text>'
                 for i, (n, c) in enumerate([("Vault Gold", GOLD), ("Arc Blue", "#5A8DFF"), ("Background", BG), ("Panels", PANEL), ("Text", INK)]))
    sizes = "".join(nest(mark_small(uid=f"sz{s}") if s < 32 else mark(uid=f"sz{s}"), 40 + off, 640 - s/2, s, s) + lab(40+off, 700, f"{s}") for s, off in [(16,0),(24,40),(32,90),(48,150),(64,225)])
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1240 790">
  <rect width="1240" height="790" fill="{BG}"/>
  {nest(mark(uid="hero"), 60, 50, 280, 280)}
  {nest(lk, 400, 120, lw*1.9, 72*1.9)}
  {lab(400, 290, "FROM COLLECTION TO STRATEGY.")}
  <line x1="40" y1="370" x2="1200" y2="370" stroke="#262D3A"/>
  {lab(40, 410, "APP ICON")}{nest(app_icon(), 40, 420, 110, 110)}
  {lab(190, 410, "LIGHT")}<rect x="190" y="420" width="300" height="110" rx="8" fill="#F4F5F8"/>{nest(lk_light, 210, 450, lw*.72, 72*.72)}
  {lab(520, 410, "MONO")}<rect x="520" y="420" width="300" height="110" rx="8" fill="{PANEL}"/>{nest(lk_mono, 540, 450, lw*.72, 72*.72)}
  {lab(850, 410, "SMALL MARK (UNDER 32 PX)")}{nest(mark_small(uid="sm"), 850, 420, 110, 110)}
  {lab(40, 580, "ACTUAL SIZE (16 / 24 = SMALL MARK, 32+ = MASTER)")}{lab(520, 580, "PALETTE")}
  {sizes}
  {sw.replace('cx="', 'cx="').replace("560+", "")}
</svg>'''

if __name__ == "__main__":
    write("arcvault-app-icon.svg", app_icon())
    lk, _ = lockup(); write("arcvault-lockup.svg", lk)
    write("brand-sheet.svg", sheet())
    print("extras written")
