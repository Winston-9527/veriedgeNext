const pptxgen = require("pptxgenjs");

const pptx = new pptxgen();
pptx.author = "Codex";
pptx.subject = "Editable Figure 2 layout for VeriEdge";
pptx.title = "VeriEdge Figure 2 Editable Layout";
pptx.company = "VeriEdge";
pptx.lang = "en-US";
pptx.layout = "LAYOUT_WIDE";
pptx.theme = {
  headFontFace: "Arial",
  bodyFontFace: "Arial",
  lang: "en-US",
};

const slide = pptx.addSlide();
slide.background = { color: "FFFFFF" };

const C = {
  orange: "F05A24",
  orangeLight: "FFF3ED",
  blue: "0B4DBB",
  blueLight: "F4F8FF",
  black: "111111",
  gray: "6B7280",
  grayLight: "F7F7F8",
  slot: "C9D2E3",
  white: "FFFFFF",
};

const S = pptx.ShapeType;

function addText(text, x, y, w, h, opts = {}) {
  slide.addText(text, {
    x, y, w, h,
    margin: opts.margin ?? 0.02,
    fontFace: opts.fontFace || "Arial",
    fontSize: opts.fontSize || 8.5,
    color: opts.color || C.black,
    bold: opts.bold || false,
    italic: opts.italic || false,
    align: opts.align || "center",
    valign: opts.valign || "mid",
    fit: "shrink",
  });
}

function addLine(x1, y1, x2, y2, color, opts = {}) {
  let x = x1;
  let y = y1;
  let w = x2 - x1;
  let h = y2 - y1;
  let beginArrow = opts.beginArrow ? "triangle" : "none";
  let endArrow = opts.endArrow === false ? "none" : "triangle";

  const isHorizontal = Math.abs(h) < 1e-6;
  const isVertical = Math.abs(w) < 1e-6;
  if ((isHorizontal && w < 0) || (isVertical && h < 0)) {
    x = x2;
    y = y2;
    w = Math.abs(w);
    h = Math.abs(h);
    beginArrow = opts.endArrow === false ? "none" : "triangle";
    endArrow = opts.beginArrow ? "triangle" : "none";
  }

  slide.addShape(S.line, {
    x, y, w, h,
    line: {
      color,
      width: opts.width || 1.25,
      beginArrowType: beginArrow,
      endArrowType: endArrow,
      dashType: opts.dash || "solid",
    },
  });
}

function addPolyline(points, color, opts = {}) {
  for (let i = 0; i < points.length - 1; i += 1) {
    addLine(points[i][0], points[i][1], points[i + 1][0], points[i + 1][1], color, {
      width: opts.width,
      dash: opts.dash,
      endArrow: i === points.length - 2,
    });
  }
}

function label(text, x, y, w, h, color = C.black, opts = {}) {
  addText(text, x, y, w, h, {
    fontSize: opts.fontSize || 7.6,
    color,
    bold: opts.bold || false,
    align: opts.align || "center",
    italic: opts.italic || false,
  });
}

function addPlane(x, y, w, h, color, fill, title, opts = {}) {
  slide.addShape(S.roundRect, {
    x, y, w, h,
    rectRadius: opts.radius ?? 0.08,
    fill: { color: fill, transparency: opts.transparency ?? 7 },
    line: { color, width: opts.width ?? 1.15 },
  });
  const titleW = opts.titleW || Math.min(w * 0.42, 3.4);
  const titleX = x + (w - titleW) / 2;
  const titleY = y - 0.18;
  slide.addShape(S.roundRect, {
    x: titleX, y: titleY, w: titleW, h: 0.32,
    rectRadius: 0.02,
    fill: { color: C.white },
    line: { color: C.white, width: 0 },
  });
  addText(title, x, y - 0.18, w, 0.28, {
    fontSize: opts.titleSize || 15,
    color,
    bold: true,
    align: "center",
  });
}

function addIconSlot(x, y, w, h) {
  slide.addShape(S.roundRect, {
    x, y, w, h,
    rectRadius: 0.03,
    fill: { color: C.white, transparency: 100 },
    line: { color: C.slot, width: 0.75, dashType: "dash" },
  });
}

function addModule({ x, y, w, h, title, subtitle, color, fill, iconSlot = true, titleSize = 9.4, textAlign = "center" }) {
  slide.addShape(S.roundRect, {
    x, y, w, h,
    rectRadius: 0.06,
    fill: { color: fill || C.white },
    line: { color, width: 1.05 },
  });
  if (iconSlot) {
    const slotW = Math.min(w * 0.34, 0.58);
    const slotH = Math.min(h * 0.48, 0.45);
    addIconSlot(x + 0.12, y + (h - slotH) / 2, slotW, slotH);
    addText(title, x + slotW + 0.2, y + 0.11, w - slotW - 0.28, subtitle ? h * 0.42 : h - 0.2, {
      fontSize: titleSize,
      color,
      bold: true,
      align: textAlign,
    });
    if (subtitle) {
      addText(subtitle, x + slotW + 0.2, y + h * 0.55, w - slotW - 0.28, h * 0.3, {
        fontSize: 7.1,
        color: C.black,
        align: textAlign,
      });
    }
  } else {
    addText(title, x + 0.08, y + 0.11, w - 0.16, subtitle ? h * 0.42 : h - 0.2, {
      fontSize: titleSize,
      color,
      bold: true,
      align: textAlign,
    });
    if (subtitle) {
      addText(subtitle, x + 0.12, y + h * 0.53, w - 0.24, h * 0.32, {
        fontSize: 7.1,
        color: C.black,
        align: textAlign,
      });
    }
  }
}

// Planes
addPlane(0.42, 0.35, 12.45, 1.7, C.orange, C.orangeLight, "Coordination metadata", {
  titleSize: 15,
});
addPlane(0.25, 2.38, 12.85, 4.78, C.blue, C.blueLight, "Selective-delivery data plane", {
  titleSize: 15,
});

// Coordination metadata.
addModule({
  x: 5.25, y: 0.55, w: 2.85, h: 0.62,
  title: "Execution group G_j",
  color: C.orange,
  fill: C.white,
  titleSize: 10.2,
});
addModule({
  x: 5.25, y: 1.38, w: 2.85, h: 0.58,
  title: "On-chain payload\ncommitment",
  color: C.orange,
  fill: C.white,
  titleSize: 9.6,
});

// Data plane modules.
addModule({
  x: 0.55, y: 3.55, w: 1.45, h: 1.55,
  title: "",
  color: C.blue,
  fill: C.white,
  iconSlot: false,
  titleSize: 10.2,
});
addText("Requester", 0.66, 3.86, 1.24, 0.22, {
  fontSize: 10.2,
  color: C.blue,
  bold: true,
});
addIconSlot(0.86, 4.38, 0.46, 0.38);
addModule({
  x: 2.82, y: 3.10, w: 2.32, h: 1.02,
  title: "Encrypt payload",
  subtitle: "C_j = E_sym(k_j, m_j)",
  color: C.black,
  fill: C.white,
  titleSize: 8.9,
});
addModule({
  x: 2.86, y: 5.06, w: 2.24, h: 0.92,
  title: "Build access tuple",
  subtitle: "(\u2113_j, k_j)",
  color: C.black,
  fill: C.white,
  titleSize: 8.9,
});
addModule({
  x: 6.18, y: 3.10, w: 2.18, h: 1.02,
  title: "IPFS / storage",
  subtitle: "single ciphertext object",
  color: C.black,
  fill: C.white,
  titleSize: 8.9,
});
addModule({
  x: 7.65, y: 4.42, w: 1.62, h: 1.37,
  title: "Selected provider",
  subtitle: "i \u2208 G_j",
  color: C.blue,
  fill: C.white,
  titleSize: 9.0,
});
addModule({
  x: 10.78, y: 4.20, w: 1.95, h: 1.32,
  title: "Recover (\u2113_j, k_j),",
  subtitle: "fetch C_j, decrypt",
  color: C.black,
  fill: C.white,
  titleSize: 8.7,
});

// Denied path modules.
addModule({
  x: 7.45, y: 6.05, w: 1.9, h: 0.78,
  title: "Non-winner /\nobserver",
  color: C.gray,
  fill: C.grayLight,
  titleSize: 8.1,
});
addModule({
  x: 10.58, y: 6.05, w: 2.05, h: 0.78,
  title: "No access tuple,",
  subtitle: "no plaintext recovery",
  color: C.gray,
  fill: C.grayLight,
  titleSize: 8.1,
});

// PPD intuition callout.
slide.addShape(S.roundRect, {
  x: 2.28, y: 6.18, w: 3.25, h: 0.66,
  rectRadius: 0.05,
  fill: { color: C.white },
  line: { color: C.blue, width: 0.9 },
});
addIconSlot(2.45, 6.31, 0.36, 0.26);
addText("PPD intuition:", 2.95, 6.25, 1.2, 0.18, {
  fontSize: 8.6,
  color: C.blue,
  bold: true,
  align: "left",
});
addText("publish ciphertext once;\nrelease only per-winner access material.", 2.95, 6.43, 2.35, 0.28, {
  fontSize: 7.1,
  color: C.black,
  align: "left",
});

// Coordination/control paths.
addPolyline([[5.25, 0.86], [2.0, 0.86], [2.0, 3.55]], C.black);
label("selected providers", 1.83, 1.16, 1.25, 0.18, C.black);
addPolyline([[8.1, 0.86], [9.05, 0.86], [9.05, 4.42]], C.black);
label("membership in G_j", 8.84, 1.16, 1.35, 0.18, C.black);
addPolyline([[3.98, 3.10], [3.98, 2.25], [6.68, 2.25], [6.68, 1.96]], C.black);
label("commit H(m_j)", 3.72, 2.42, 1.08, 0.18, C.black);

// Data and delivery paths.
addLine(2.0, 3.55, 2.82, 3.55, C.blue);
label("payload m_j", 2.05, 3.33, 0.72, 0.16, C.black);
addPolyline([[2.0, 4.74], [2.42, 4.74], [2.42, 5.52], [2.86, 5.52]], C.blue);
label("session key k_j", 1.77, 5.39, 0.92, 0.16, C.black);
addLine(5.14, 3.58, 6.18, 3.58, C.blue);
label("single upload\nof C_j", 5.28, 3.2, 0.72, 0.32, C.black);
addPolyline([[7.0, 4.12], [7.0, 4.78], [5.1, 4.78], [5.1, 5.26]], C.blue);
label("locator \u2113_j", 5.45, 4.54, 0.8, 0.18, C.black);
addPolyline([[5.1, 5.52], [6.45, 5.52], [6.45, 5.08], [7.65, 5.08]], C.blue);
label("small encrypted\npackage e_{i,j}", 5.45, 5.14, 1.25, 0.32, C.black);
addPolyline([[8.36, 3.58], [10.78, 3.58], [10.78, 4.65]], C.blue);
label("ciphertext\nfetch", 8.72, 3.22, 0.82, 0.3, C.black);
addLine(9.27, 5.08, 10.78, 5.08, C.blue);
label("decrypt with\n(\u2113_j,k_j)", 9.45, 4.74, 1.0, 0.32, C.black);

// Denied/inaccessible paths.
addPolyline([[7.25, 4.12], [7.25, 5.32], [7.45, 6.44]], C.gray, { dash: "dash" });
label("ciphertext\nvisible", 7.02, 5.34, 0.78, 0.28, C.gray);
addLine(9.35, 6.44, 10.58, 6.44, C.gray, { dash: "dash" });
label("no e_{i,j},\nno k_j", 9.55, 6.12, 0.85, 0.32, C.black);

// Legend.
addLine(2.35, 7.28, 2.9, 7.28, C.black);
label("Control / coordination path", 3.0, 7.18, 1.45, 0.18, C.black, { fontSize: 7.0, align: "left" });
addLine(5.25, 7.28, 5.8, 7.28, C.blue);
label("Data / delivery path", 5.9, 7.18, 1.2, 0.18, C.black, { fontSize: 7.0, align: "left" });
addLine(7.55, 7.28, 8.1, 7.28, C.gray, { dash: "dash" });
label("Denied / inaccessible path", 8.2, 7.18, 1.55, 0.18, C.black, { fontSize: 7.0, align: "left" });

pptx.writeFile({ fileName: "figure2_editable_layout.pptx" });
