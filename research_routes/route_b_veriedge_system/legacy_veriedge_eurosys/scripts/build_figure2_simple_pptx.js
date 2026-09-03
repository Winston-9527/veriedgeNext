const pptxgen = require("pptxgenjs");
const path = require("path");
const fs = require("fs");

const pptx = new pptxgen();
pptx.author = "Codex";
pptx.subject = "Simplified editable Figure 2 layout for VeriEdge";
pptx.title = "VeriEdge Figure 2 Simplified Editable Layout";
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
const withIcons = process.env.FIGURE2_ICONS === "1";
const iconDir = path.join(__dirname, "..", "img", "icons");
const tightIconDir = path.join(iconDir, "figure2_tight");

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
    fontFace: "Arial",
    fontSize: opts.fontSize || 8,
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
      width: opts.width || 1.2,
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
    fontSize: opts.fontSize || 7.2,
    color,
    bold: opts.bold || false,
    align: opts.align || "center",
  });
}

function pngSize(filePath) {
  const buf = fs.readFileSync(filePath);
  return { width: buf.readUInt32BE(16), height: buf.readUInt32BE(20) };
}

function iconSlot(x, y, w, h, iconName) {
  if (withIcons && iconName) {
    const iconPath = path.join(tightIconDir, iconName);
    const { width, height } = pngSize(iconPath);
    const scale = Math.min(w / width, h / height);
    const drawW = width * scale;
    const drawH = height * scale;
    slide.addImage({
      path: iconPath,
      x: x + (w - drawW) / 2,
      y: y + (h - drawH) / 2,
      w: drawW,
      h: drawH,
    });
    return;
  }
  slide.addShape(S.roundRect, {
    x, y, w, h,
    rectRadius: 0.03,
    fill: { color: C.white, transparency: 100 },
    line: { color: C.slot, width: 0.65, dashType: "dash" },
  });
}

function moduleBox({ x, y, w, h, title, subtitle, color = C.black, fill = C.white, slot = true, titleSize = 8.8, icon }) {
  slide.addShape(S.roundRect, {
    x, y, w, h,
    rectRadius: 0.06,
    fill: { color: fill },
    line: { color, width: 1.05 },
  });
  const left = slot ? 0.56 : 0.08;
  if (slot) {
    const slotW = Math.min(0.46, w * 0.25);
    const slotH = Math.min(0.46, h - 0.16);
    iconSlot(x + 0.12, y + (h - slotH) / 2, slotW, slotH, icon);
  }
  addText(title, x + left, y + 0.12, w - left - 0.1, subtitle ? h * 0.38 : h - 0.22, {
    fontSize: titleSize,
    color,
    bold: true,
  });
  if (subtitle) {
    addText(subtitle, x + left, y + h * 0.56, w - left - 0.1, h * 0.28, {
      fontSize: 6.8,
      color: C.black,
    });
  }
}

function sectionTitle(text, x, y, w, color) {
  slide.addShape(S.roundRect, {
    x: x + w * 0.28, y: y - 0.16, w: w * 0.44, h: 0.32,
    rectRadius: 0.02,
    fill: { color: C.white },
    line: { color: C.white, width: 0 },
  });
  addText(text, x, y - 0.13, w, 0.26, {
    fontSize: 14,
    color,
    bold: true,
  });
}

// Two light regions, but no large architectural clutter.
slide.addShape(S.roundRect, {
  x: 0.55, y: 0.48, w: 12.2, h: 1.22,
  rectRadius: 0.08,
  fill: { color: C.orangeLight, transparency: 12 },
  line: { color: C.orange, width: 1.0 },
});
sectionTitle("Coordination metadata", 0.55, 0.48, 12.2, C.orange);

slide.addShape(S.roundRect, {
  x: 0.55, y: 2.06, w: 12.2, h: 4.6,
  rectRadius: 0.08,
  fill: { color: C.blueLight, transparency: 8 },
  line: { color: C.blue, width: 1.0 },
});
sectionTitle("Selective-delivery data plane", 0.55, 2.06, 12.2, C.blue);

// Coordination metadata: only the two records needed by this mechanism.
moduleBox({
  x: 4.3, y: 0.72, w: 2.1, h: 0.55,
  title: "Execution group G_j",
  color: C.orange,
  fill: C.white,
  titleSize: 8.8,
  icon: "icon_allocation_commitment.png",
});
moduleBox({
  x: 6.95, y: 0.72, w: 2.1, h: 0.55,
  title: "Payload commitment com_j",
  color: C.orange,
  fill: C.white,
  titleSize: 8.4,
  icon: "icon_result_trace_commitment.png",
});

// Main selected-delivery path.
moduleBox({
  x: 0.88, y: 3.18, w: 1.28, h: 0.95,
  title: "",
  color: C.blue,
  fill: C.white,
  slot: false,
  titleSize: 9.2,
});
addText("Requester", 0.98, 3.34, 1.08, 0.18, {
  fontSize: 9.2,
  color: C.blue,
  bold: true,
});
iconSlot(1.12, 3.67, 0.5, 0.34, "icon_requester.png");

moduleBox({
  x: 2.75, y: 2.78, w: 2.05, h: 0.82,
  title: "Encrypt once",
  subtitle: "C_j = E_sym(k_j, m_j)",
  color: C.black,
  fill: C.white,
  titleSize: 8.5,
  icon: "icon_targeted_key_release.png",
});

moduleBox({
  x: 5.5, y: 2.78, w: 1.85, h: 0.82,
  title: "IPFS / storage",
  subtitle: "one ciphertext C_j",
  color: C.black,
  fill: C.white,
  titleSize: 8.5,
  icon: "icon_ipfs_storage.png",
});

moduleBox({
  x: 2.75, y: 4.55, w: 2.18, h: 0.86,
  title: "Build access package",
  subtitle: "e_{i,j} = Enc_i(\u2113_j,k_j)",
  color: C.black,
  fill: C.white,
  titleSize: 8.4,
  icon: "icon_targeted_key_release.png",
});

moduleBox({
  x: 8.25, y: 3.18, w: 1.45, h: 0.95,
  title: "Selected\nprovider",
  subtitle: "i \u2208 G_j",
  color: C.blue,
  fill: C.white,
  titleSize: 8.2,
  icon: "icon_provider_group.png",
});

moduleBox({
  x: 10.88, y: 3.18, w: 1.48, h: 0.95,
  title: "Recover & decrypt",
  subtitle: "(\u2113_j,k_j), C_j",
  color: C.black,
  fill: C.white,
  titleSize: 8.0,
  icon: "icon_targeted_key_release.png",
});

moduleBox({
  x: 8.0, y: 5.42, w: 1.78, h: 0.72,
  title: "Non-winner /\nobserver",
  color: C.gray,
  fill: C.grayLight,
  titleSize: 7.6,
  icon: "icon_provider_group.png",
});

moduleBox({
  x: 10.68, y: 5.42, w: 1.78, h: 0.72,
  title: "No access tuple",
  subtitle: "no plaintext recovery",
  color: C.gray,
  fill: C.grayLight,
  titleSize: 7.6,
  icon: "icon_targeted_key_release.png",
});

// Control paths.
addPolyline([[4.3, 1.0], [1.52, 1.0], [1.52, 3.18]], C.black);
label("selected providers", 1.55, 1.18, 1.25, 0.16, C.black);
addPolyline([[5.35, 1.27], [5.35, 1.82], [8.98, 1.82], [8.98, 3.18]], C.black);
label("membership in G_j", 8.35, 1.62, 1.35, 0.16, C.black);
addPolyline([[3.8, 2.78], [3.8, 1.58], [8.0, 1.58], [8.0, 1.27]], C.black);
label("commit com_j", 4.08, 1.68, 0.9, 0.16, C.black);

// Data paths.
addLine(2.16, 3.45, 2.75, 3.45, C.blue);
label("payload m_j", 2.1, 3.22, 0.78, 0.16, C.black);
addLine(4.8, 3.19, 5.5, 3.19, C.blue);
label("upload C_j", 4.82, 2.98, 0.68, 0.16, C.black);
addPolyline([[2.16, 3.9], [2.42, 3.9], [2.42, 4.98], [2.75, 4.98]], C.blue);
label("access tuple", 2.02, 4.76, 0.7, 0.16, C.black);
addPolyline([[4.93, 4.98], [6.5, 4.98], [6.5, 3.9], [8.25, 3.9]], C.blue);
label("access package e_{i,j}", 5.22, 4.75, 1.22, 0.16, C.black);
addPolyline([[7.35, 3.19], [10.88, 3.19], [10.88, 3.45]], C.blue);
label("fetch C_j", 8.0, 2.98, 0.68, 0.16, C.black);
addLine(9.7, 3.68, 10.88, 3.68, C.blue);
label("decrypt", 9.82, 3.46, 0.7, 0.16, C.black);

// Denied path.
addPolyline([[6.42, 3.6], [6.42, 5.78], [8.0, 5.78]], C.gray, { dash: "dash" });
label("ciphertext visible", 6.45, 5.45, 0.92, 0.16, C.gray);
addLine(9.78, 5.78, 10.68, 5.78, C.gray, { dash: "dash" });
label("no e_{i,j}, no k_j", 9.7, 5.55, 0.9, 0.16, C.black);

// Minimal legend.
addLine(3.0, 6.95, 3.5, 6.95, C.black);
label("coordination", 3.6, 6.86, 0.78, 0.16, C.black, { fontSize: 6.8, align: "left" });
addLine(4.9, 6.95, 5.4, 6.95, C.blue);
label("delivery", 5.5, 6.86, 0.62, 0.16, C.black, { fontSize: 6.8, align: "left" });
addLine(6.55, 6.95, 7.05, 6.95, C.gray, { dash: "dash" });
label("denied", 7.15, 6.86, 0.62, 0.16, C.black, { fontSize: 6.8, align: "left" });

pptx.writeFile({ fileName: withIcons ? "figure2_with_icons.pptx" : "figure2_simple_editable_layout.pptx" });
