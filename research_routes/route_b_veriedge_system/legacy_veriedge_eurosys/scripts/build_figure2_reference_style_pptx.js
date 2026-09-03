const pptxgen = require("pptxgenjs");
const path = require("path");
const fs = require("fs");

const pptx = new pptxgen();
pptx.author = "Codex";
pptx.subject = "Reference-style Figure 2 for VeriEdge";
pptx.title = "VeriEdge Figure 2 Reference Style";
pptx.company = "VeriEdge";
pptx.lang = "en-US";
pptx.defineLayout({ name: "FIGURE", width: 12, height: 8.25 });
pptx.layout = "FIGURE";
pptx.theme = {
  headFontFace: "Arial",
  bodyFontFace: "Arial",
  lang: "en-US",
};

const slide = pptx.addSlide();
slide.background = { color: "FFFFFF" };

const C = {
  orange: "F05A24",
  orangeLight: "FFF5EF",
  blue: "0B4DBB",
  blueLight: "F4F8FF",
  black: "111111",
  gray: "6B7280",
  grayLight: "F7F7F8",
  white: "FFFFFF",
};

const S = pptx.ShapeType;
const iconDir = path.join(__dirname, "..", "img", "icons", "figure2_tight");

function shadow(opacity = 0.14) {
  return { type: "outer", color: "000000", opacity, blur: 4, offset: 1.2, angle: 45 };
}

function text(text, x, y, w, h, opts = {}) {
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

function pngSize(filePath) {
  const buf = fs.readFileSync(filePath);
  return { width: buf.readUInt32BE(16), height: buf.readUInt32BE(20) };
}

function icon(name, x, y, w, h) {
  const file = path.join(iconDir, name);
  const { width, height } = pngSize(file);
  const s = Math.min(w / width, h / height);
  const dw = width * s;
  const dh = height * s;
  slide.addImage({ path: file, x: x + (w - dw) / 2, y: y + (h - dh) / 2, w: dw, h: dh });
}

function line(x1, y1, x2, y2, color, opts = {}) {
  let x = x1;
  let y = y1;
  let w = x2 - x1;
  let h = y2 - y1;
  let beginArrow = opts.beginArrow ? "triangle" : "none";
  let endArrow = opts.endArrow === false ? "none" : "triangle";
  const isH = Math.abs(h) < 1e-6;
  const isV = Math.abs(w) < 1e-6;
  if ((isH && w < 0) || (isV && h < 0)) {
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
      width: opts.width || 1.35,
      beginArrowType: beginArrow,
      endArrowType: endArrow,
      dashType: opts.dash || "solid",
    },
  });
}

function poly(points, color, opts = {}) {
  for (let i = 0; i < points.length - 1; i += 1) {
    line(points[i][0], points[i][1], points[i + 1][0], points[i + 1][1], color, {
      width: opts.width,
      dash: opts.dash,
      endArrow: i === points.length - 2,
    });
  }
}

function label(labelText, x, y, w, h, color = C.black, opts = {}) {
  text(labelText, x, y, w, h, {
    fontSize: opts.fontSize || 7.4,
    color,
    align: opts.align || "center",
    bold: opts.bold || false,
  });
}

function plane(x, y, w, h, color, fill, title) {
  slide.addShape(S.roundRect, {
    x, y, w, h,
    rectRadius: 0.12,
    fill: { color: fill, transparency: 10 },
    line: { color, width: 0.95 },
  });
  slide.addShape(S.roundRect, {
    x: x + w * 0.34, y: y - 0.16, w: w * 0.32, h: 0.32,
    rectRadius: 0.02,
    fill: { color: C.white },
    line: { color: C.white, width: 0 },
  });
  text(title, x, y - 0.13, w, 0.25, {
    fontSize: 14,
    color,
    bold: true,
  });
}

function box({ x, y, w, h, title, subtitle, color = C.black, fill = C.white, titleSize = 9, iconName, iconW = 0.44, iconH = 0.44, muted = false }) {
  slide.addShape(S.roundRect, {
    x, y, w, h,
    rectRadius: 0.06,
    fill: { color: fill },
    line: { color, width: 1.05, dashType: muted ? "dash" : "solid" },
    shadow: shadow(muted ? 0.06 : 0.12),
  });
  const ix = x + 0.14;
  const iy = y + (h - iconH) / 2;
  if (iconName) icon(iconName, ix, iy, iconW, iconH);
  const left = iconName ? iconW + 0.28 : 0.12;
  text(title, x + left, y + 0.1, w - left - 0.12, subtitle ? h * 0.38 : h - 0.2, {
    fontSize: titleSize,
    color,
    bold: true,
  });
  if (subtitle) {
    text(subtitle, x + left, y + h * 0.55, w - left - 0.12, h * 0.3, {
      fontSize: 7.1,
      color: muted ? C.gray : C.black,
    });
  }
}

function requesterBox() {
  slide.addShape(S.roundRect, {
    x: 0.48, y: 3.48, w: 1.28, h: 1.5,
    rectRadius: 0.06,
    fill: { color: C.white },
    line: { color: C.blue, width: 1.1 },
    shadow: shadow(0.12),
  });
  icon("icon_requester.png", 0.72, 3.72, 0.78, 0.48);
  text("Requester", 0.58, 4.38, 1.08, 0.22, { fontSize: 11, color: C.blue, bold: true });
}

function noAccessBox() {
  slide.addShape(S.roundRect, {
    x: 9.15, y: 5.95, w: 1.9, h: 0.82,
    rectRadius: 0.06,
    fill: { color: C.white },
    line: { color: C.gray, width: 0.95, dashType: "dash" },
    shadow: shadow(0.06),
  });
  text("⊘", 9.32, 6.07, 0.42, 0.42, { fontSize: 22, color: C.gray, bold: true });
  text("No access tuple,", 9.78, 6.07, 1.1, 0.22, { fontSize: 8.2, color: C.gray, bold: true });
  text("no plaintext recovery", 9.78, 6.34, 1.1, 0.18, { fontSize: 7.0, color: C.black });
}

function selectedProviderBox() {
  slide.addShape(S.roundRect, {
    x: 6.58, y: 4.08, w: 1.46, h: 1.38,
    rectRadius: 0.06,
    fill: { color: C.white },
    line: { color: C.blue, width: 1.05 },
    shadow: shadow(0.12),
  });
  icon("icon_server_gpu_cluster_v2.png", 6.84, 4.28, 0.92, 0.38);
  text("Selected provider", 6.7, 4.76, 1.22, 0.2, {
    fontSize: 8.5,
    color: C.blue,
    bold: true,
  });
  text("i ∈ G_j", 6.82, 5.15, 0.98, 0.16, {
    fontSize: 7.2,
    color: C.black,
  });
}

// Layer backgrounds.
plane(0.58, 0.35, 10.86, 1.78, C.orange, C.orangeLight, "Coordination metadata");
plane(0.26, 2.48, 11.48, 4.72, C.blue, C.blueLight, "Selective-delivery data plane");

// Coordination metadata records.
box({
  x: 4.55, y: 0.62, w: 2.38, h: 0.62,
  title: "Execution group G_j",
  color: C.orange,
  fill: C.white,
  titleSize: 10,
  iconName: "icon_allocation_commitment.png",
  iconW: 0.42,
  iconH: 0.42,
});
box({
  x: 4.4, y: 1.45, w: 2.68, h: 0.62,
  title: "On-chain payload\ncommitment",
  color: C.orange,
  fill: C.white,
  titleSize: 9.4,
  iconName: "icon_result_trace_commitment.png",
  iconW: 0.42,
  iconH: 0.42,
});

// Main protocol nodes.
requesterBox();
box({
  x: 2.55, y: 3.05, w: 2.1, h: 0.9,
  title: "Encrypt payload",
  subtitle: "C_j = E_sym(k_j,m_j)",
  color: C.black,
  fill: C.white,
  titleSize: 8.8,
  iconName: "icon_targeted_key_release.png",
  iconW: 0.48,
  iconH: 0.48,
});
box({
  x: 5.35, y: 3.05, w: 1.92, h: 0.9,
  title: "IPFS / storage",
  subtitle: "single ciphertext object",
  color: C.black,
  fill: C.white,
  titleSize: 8.7,
  iconName: "icon_ipfs_storage.png",
  iconW: 0.48,
  iconH: 0.48,
});
box({
  x: 2.62, y: 4.82, w: 2.12, h: 0.9,
  title: "Build access tuple",
  subtitle: "(ℓ_j,k_j)",
  color: C.black,
  fill: C.white,
  titleSize: 8.8,
  iconName: "icon_targeted_key_release.png",
  iconW: 0.48,
  iconH: 0.48,
});
selectedProviderBox();
box({
  x: 9.05, y: 3.95, w: 1.58, h: 1.08,
  title: "Recover (ℓ_j,k_j),",
  subtitle: "fetch C_j, decrypt",
  color: C.black,
  fill: C.white,
  titleSize: 8.4,
  iconName: "icon_targeted_key_release.png",
  iconW: 0.45,
  iconH: 0.45,
});
box({
  x: 6.25, y: 5.95, w: 1.72, h: 0.82,
  title: "Non-winner /\nobserver",
  color: C.gray,
  fill: C.white,
  titleSize: 7.6,
  iconName: "icon_provider_group.png",
  iconW: 0.52,
  iconH: 0.22,
  muted: true,
});
noAccessBox();

// PPD intuition.
slide.addShape(S.roundRect, {
  x: 1.94, y: 6.12, w: 3.45, h: 0.72,
  rectRadius: 0.06,
  fill: { color: C.white },
  line: { color: C.blue, width: 0.85 },
  shadow: shadow(0.07),
});
text("PPD intuition:", 2.75, 6.22, 1.15, 0.18, { fontSize: 8.5, color: C.blue, bold: true, align: "left" });
text("publish ciphertext once;\nrelease only per-winner access material.", 2.75, 6.42, 2.45, 0.28, { fontSize: 7.1, color: C.black, align: "left" });
text("💡", 2.22, 6.24, 0.32, 0.32, { fontSize: 16, color: C.blue });

// Control and coordination paths.
poly([[4.55, 0.93], [2.2, 0.93], [2.2, 3.48], [1.76, 3.48]], C.black);
label("selected winners", 1.78, 1.35, 1.05, 0.16, C.black);
poly([[6.93, 0.93], [8.55, 0.93], [8.55, 4.08], [8.04, 4.08]], C.black);
label("membership in G_j", 8.18, 1.35, 1.22, 0.16, C.black);
poly([[3.6, 3.05], [3.6, 2.2], [5.74, 2.2], [5.74, 1.45]], C.black);
label("commit com_j", 3.72, 2.34, 0.92, 0.16, C.black);

// Data paths.
poly([[1.76, 3.9], [2.08, 3.9], [2.08, 3.5], [2.55, 3.5]], C.blue, { width: 1.5 });
label("payload m_j", 1.78, 3.14, 0.74, 0.16, C.black);
poly([[1.76, 4.55], [2.22, 4.55], [2.22, 5.22], [2.62, 5.22]], C.blue, { width: 1.5 });
label("session key k_j", 1.62, 5.02, 0.9, 0.16, C.black);
line(4.65, 3.5, 5.35, 3.5, C.blue, { width: 1.5 });
label("single upload\nof C_j", 4.72, 3.18, 0.58, 0.28, C.black);
poly([[5.95, 3.95], [5.95, 4.42], [4.74, 4.42], [4.74, 5.12]], C.blue, { width: 1.35 });
label("locator ℓ_j", 4.52, 4.12, 0.75, 0.16, C.black);
poly([[4.74, 5.24], [5.72, 5.24], [5.72, 4.77], [6.58, 4.77]], C.blue, { width: 1.5 });
label("small encrypted\npackage e_{i,j}", 4.88, 4.92, 1.15, 0.28, C.black);
poly([[7.27, 3.5], [8.66, 3.5], [8.66, 4.38], [9.05, 4.38]], C.blue, { width: 1.5 });
label("ciphertext\nfetch", 7.72, 3.16, 0.72, 0.28, C.black);
line(8.04, 4.77, 9.05, 4.77, C.blue, { width: 1.5 });
label("decrypt with\n(ℓ_j,k_j)", 8.18, 4.43, 0.78, 0.28, C.black);

// Denied path.
poly([[6.0, 3.95], [6.0, 5.35], [6.25, 6.32]], C.gray, { dash: "dash", width: 1.35 });
label("ciphertext\nvisible", 5.75, 5.35, 0.7, 0.28, C.gray);
line(7.97, 6.36, 9.15, 6.36, C.gray, { dash: "dash", width: 1.35 });
label("no e_{i,j},\nno k_j", 8.12, 6.08, 0.72, 0.28, C.black);

// Legend.
line(2.15, 7.68, 2.75, 7.68, C.black, { width: 1.35 });
label("Control / coordination path", 2.87, 7.58, 1.55, 0.18, C.black, { fontSize: 7, align: "left" });
line(4.95, 7.68, 5.55, 7.68, C.blue, { width: 1.5 });
label("Data / delivery path", 5.67, 7.58, 1.25, 0.18, C.black, { fontSize: 7, align: "left" });
line(7.1, 7.68, 7.7, 7.68, C.gray, { dash: "dash", width: 1.35 });
label("Denied / inaccessible path", 7.82, 7.58, 1.55, 0.18, C.black, { fontSize: 7, align: "left" });

pptx.writeFile({ fileName: "figure2_reference_style_with_icons.pptx" });
