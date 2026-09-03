from pathlib import Path

from reportlab.pdfgen import canvas


OUT_DIR = Path(__file__).resolve().parents[2] / "figures" / "icons_pdf"
SIZE = 48
STROKE = 2.2

COLORS = {
    "blue": "#1557A6",
    "brown": "#8A560D",
    "green": "#1F7A2E",
    "red": "#C9252C",
    "purple": "#5B3B93",
    "gray": "#6F7782",
    "dark": "#1C2630",
}


def p(x, y):
    return x * SIZE, y * SIZE


def style(c, color, width=STROKE):
    c.setStrokeColor(color)
    c.setFillColor(color)
    c.setLineWidth(width)
    c.setLineCap(1)
    c.setLineJoin(1)


def nofill(c):
    c.setFillColorRGB(1, 1, 1, alpha=0)


def line(c, x1, y1, x2, y2):
    c.line(*p(x1, y1), *p(x2, y2))


def rect(c, x, y, w, h, r=0.06, fill=0):
    c.roundRect(x * SIZE, y * SIZE, w * SIZE, h * SIZE, r * SIZE, stroke=1, fill=fill)


def circle(c, x, y, r, fill=0):
    c.circle(x * SIZE, y * SIZE, r * SIZE, stroke=1, fill=fill)


def path_poly(c, pts, close=True, fill=0):
    path = c.beginPath()
    path.moveTo(*p(*pts[0]))
    for pt in pts[1:]:
        path.lineTo(*p(*pt))
    if close:
        path.close()
    c.drawPath(path, stroke=1, fill=fill)


def make_icon(name, color, draw_fn):
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / f"{name}.pdf"
    c = canvas.Canvas(str(out), pagesize=(SIZE, SIZE))
    style(c, COLORS[color])
    draw_fn(c)
    c.showPage()
    c.save()


def draw_requester(c):
    circle(c, 0.5, 0.68, 0.12)
    c.arc(0.25 * SIZE, 0.16 * SIZE, 0.75 * SIZE, 0.58 * SIZE, 28, 152)
    line(c, 0.35, 0.26, 0.65, 0.26)


def draw_document(c):
    path_poly(c, [(0.28, 0.15), (0.28, 0.85), (0.62, 0.85), (0.78, 0.69), (0.78, 0.15)])
    path_poly(c, [(0.62, 0.85), (0.62, 0.69), (0.78, 0.69)], close=False)
    line(c, 0.38, 0.58, 0.66, 0.58)
    line(c, 0.38, 0.46, 0.66, 0.46)
    line(c, 0.38, 0.34, 0.58, 0.34)


def draw_lock(c):
    rect(c, 0.25, 0.18, 0.50, 0.38, 0.07)
    c.arc(0.34 * SIZE, 0.39 * SIZE, 0.66 * SIZE, 0.86 * SIZE, 0, 180)
    line(c, 0.34, 0.56, 0.34, 0.46)
    line(c, 0.66, 0.56, 0.66, 0.46)
    line(c, 0.50, 0.37, 0.50, 0.30)


def draw_key(c):
    circle(c, 0.30, 0.58, 0.10)
    line(c, 0.38, 0.50, 0.78, 0.20)
    line(c, 0.60, 0.34, 0.66, 0.43)
    line(c, 0.70, 0.26, 0.76, 0.35)


def draw_shield_check(c):
    path_poly(c, [(0.50, 0.88), (0.78, 0.75), (0.75, 0.39), (0.50, 0.14), (0.25, 0.39), (0.22, 0.75)])
    line(c, 0.36, 0.50, 0.46, 0.39)
    line(c, 0.46, 0.39, 0.66, 0.62)


def draw_orchestrator(c):
    circle(c, 0.50, 0.50, 0.15)
    for x1, y1, x2, y2 in [
        (0.50, 0.10, 0.50, 0.22), (0.50, 0.78, 0.50, 0.90),
        (0.10, 0.50, 0.22, 0.50), (0.78, 0.50, 0.90, 0.50),
        (0.22, 0.22, 0.31, 0.31), (0.69, 0.69, 0.78, 0.78),
        (0.22, 0.78, 0.31, 0.69), (0.69, 0.31, 0.78, 0.22),
    ]:
        line(c, x1, y1, x2, y2)
    for x, y in [(0.50, 0.10), (0.50, 0.90), (0.10, 0.50), (0.90, 0.50)]:
        circle(c, x, y, 0.025, fill=1)


def draw_search(c):
    circle(c, 0.42, 0.58, 0.18)
    line(c, 0.56, 0.44, 0.78, 0.22)


def draw_group(c):
    for x, y, r in [(0.50, 0.62, 0.10), (0.30, 0.54, 0.08), (0.70, 0.54, 0.08)]:
        circle(c, x, y, r)
    c.arc(0.31 * SIZE, 0.19 * SIZE, 0.69 * SIZE, 0.50 * SIZE, 15, 165)
    c.arc(0.12 * SIZE, 0.18 * SIZE, 0.46 * SIZE, 0.45 * SIZE, 28, 142)
    c.arc(0.54 * SIZE, 0.18 * SIZE, 0.88 * SIZE, 0.45 * SIZE, 38, 152)


def draw_grid(c):
    for i in range(3):
        for j in range(3):
            c.rect((0.22 + 0.19 * i) * SIZE, (0.22 + 0.19 * j) * SIZE, 0.16 * SIZE, 0.16 * SIZE, stroke=1, fill=0)


def draw_commit(c):
    draw_document(c)
    line(c, 0.46, 0.27, 0.54, 0.20)
    line(c, 0.54, 0.20, 0.69, 0.36)


def draw_server(c):
    for y in [0.62, 0.43, 0.24]:
        rect(c, 0.22, y, 0.56, 0.13, 0.03)
        circle(c, 0.30, y + 0.065, 0.018, fill=1)
        line(c, 0.43, y + 0.065, 0.68, y + 0.065)


def draw_warning(c):
    path_poly(c, [(0.50, 0.86), (0.86, 0.20), (0.14, 0.20)])
    line(c, 0.50, 0.63, 0.50, 0.39)
    circle(c, 0.50, 0.29, 0.025, fill=1)


def draw_balance(c):
    line(c, 0.50, 0.78, 0.50, 0.24)
    line(c, 0.32, 0.24, 0.68, 0.24)
    line(c, 0.25, 0.66, 0.75, 0.66)
    line(c, 0.30, 0.66, 0.20, 0.42)
    line(c, 0.30, 0.66, 0.40, 0.42)
    line(c, 0.70, 0.66, 0.60, 0.42)
    line(c, 0.70, 0.66, 0.80, 0.42)
    c.arc(0.14 * SIZE, 0.35 * SIZE, 0.46 * SIZE, 0.50 * SIZE, 180, 360)
    c.arc(0.54 * SIZE, 0.35 * SIZE, 0.86 * SIZE, 0.50 * SIZE, 180, 360)


def draw_link(c):
    c.roundRect(0.18 * SIZE, 0.40 * SIZE, 0.35 * SIZE, 0.22 * SIZE, 0.11 * SIZE, stroke=1, fill=0)
    c.roundRect(0.47 * SIZE, 0.38 * SIZE, 0.35 * SIZE, 0.22 * SIZE, 0.11 * SIZE, stroke=1, fill=0)
    line(c, 0.38, 0.50, 0.62, 0.50)


def draw_wallet(c):
    rect(c, 0.20, 0.25, 0.62, 0.46, 0.07)
    rect(c, 0.58, 0.39, 0.26, 0.18, 0.05)
    circle(c, 0.68, 0.48, 0.018, fill=1)


def draw_clipboard(c):
    rect(c, 0.28, 0.18, 0.44, 0.60, 0.05)
    rect(c, 0.38, 0.70, 0.24, 0.12, 0.04)
    line(c, 0.40, 0.52, 0.47, 0.45)
    line(c, 0.47, 0.45, 0.62, 0.60)


def draw_bank(c):
    path_poly(c, [(0.18, 0.62), (0.50, 0.82), (0.82, 0.62)])
    line(c, 0.22, 0.22, 0.78, 0.22)
    for x in [0.30, 0.50, 0.70]:
        line(c, x, 0.58, x, 0.30)
    line(c, 0.20, 0.58, 0.80, 0.58)
    line(c, 0.24, 0.30, 0.76, 0.30)


def draw_database(c):
    c.ellipse(0.24 * SIZE, 0.68 * SIZE, 0.76 * SIZE, 0.86 * SIZE, stroke=1, fill=0)
    line(c, 0.24, 0.77, 0.24, 0.30)
    line(c, 0.76, 0.77, 0.76, 0.30)
    c.arc(0.24 * SIZE, 0.50 * SIZE, 0.76 * SIZE, 0.68 * SIZE, 180, 360)
    c.arc(0.24 * SIZE, 0.28 * SIZE, 0.76 * SIZE, 0.46 * SIZE, 180, 360)


def draw_encrypted_object(c):
    draw_document(c)
    rect(c, 0.43, 0.18, 0.28, 0.22, 0.04)
    c.arc(0.48 * SIZE, 0.32 * SIZE, 0.66 * SIZE, 0.54 * SIZE, 0, 180)
    line(c, 0.48, 0.40, 0.48, 0.34)
    line(c, 0.66, 0.40, 0.66, 0.34)


def draw_provider_group(c):
    for x in [0.24, 0.50, 0.76]:
        rect(c, x - 0.09, 0.43, 0.18, 0.18, 0.04)
        circle(c, x, 0.52, 0.018, fill=1)
    line(c, 0.33, 0.52, 0.41, 0.52)
    line(c, 0.59, 0.52, 0.67, 0.52)


def draw_chip(c):
    rect(c, 0.30, 0.30, 0.40, 0.40, 0.04)
    rect(c, 0.40, 0.40, 0.20, 0.20, 0.02)
    for x in [0.20, 0.80]:
        for y in [0.36, 0.50, 0.64]:
            line(c, x, y, 0.30 if x < 0.5 else 0.70, y)
    for y in [0.20, 0.80]:
        for x in [0.36, 0.50, 0.64]:
            line(c, x, y, x, 0.30 if y < 0.5 else 0.70)


def draw_ciphertext_storage(c):
    draw_database(c)
    line(c, 0.36, 0.18, 0.64, 0.18)


ICONS = [
    ("requester", "blue", draw_requester),
    ("document", "blue", draw_document),
    ("lock", "blue", draw_lock),
    ("key", "blue", draw_key),
    ("shield_check", "blue", draw_shield_check),
    ("orchestrator", "brown", draw_orchestrator),
    ("search", "brown", draw_search),
    ("group", "brown", draw_group),
    ("shard_grid", "brown", draw_grid),
    ("placement_commit", "brown", draw_commit),
    ("orchestrator_lock", "brown", draw_lock),
    ("server_green", "green", draw_server),
    ("server_red", "red", draw_server),
    ("server_gray", "gray", draw_server),
    ("warning_triangle", "red", draw_warning),
    ("verifier_balance", "purple", draw_balance),
    ("ledger_link", "purple", draw_link),
    ("escrow_wallet", "purple", draw_wallet),
    ("challenge_clipboard", "purple", draw_clipboard),
    ("settlement_bank", "purple", draw_bank),
    ("data_store", "blue", draw_database),
    ("encrypted_object", "blue", draw_encrypted_object),
    ("ciphertext_storage", "blue", draw_ciphertext_storage),
    ("provider_group", "blue", draw_provider_group),
    ("chip", "blue", draw_chip),
]


def make_contact_sheet():
    out = OUT_DIR / "fig1_icon_sheet.pdf"
    cols = 5
    cell = 88
    rows = (len(ICONS) + cols - 1) // cols
    c = canvas.Canvas(str(out), pagesize=(cols * cell, rows * cell))
    for idx, (name, color, draw_fn) in enumerate(ICONS):
        col = idx % cols
        row = rows - 1 - idx // cols
        c.saveState()
        c.translate(col * cell + 20, row * cell + 34)
        style(c, COLORS[color], width=2.0)
        draw_fn(c)
        c.restoreState()
        c.setFillColor("#1C2630")
        c.setFont("Helvetica", 7)
        c.drawCentredString(col * cell + cell / 2, row * cell + 14, name.replace("_", "-"))
    c.showPage()
    c.save()


def main():
    for name, color, draw_fn in ICONS:
        make_icon(name, color, draw_fn)
    make_contact_sheet()
    print(f"Wrote {len(ICONS)} icons to {OUT_DIR}")


if __name__ == "__main__":
    main()
