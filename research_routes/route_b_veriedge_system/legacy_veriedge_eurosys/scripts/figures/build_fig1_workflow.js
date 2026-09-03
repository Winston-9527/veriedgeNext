const fs = require("fs");
const path = require("path");
const pptxgen = require("pptxgenjs");
const sharp = require("sharp");

const ROOT = path.resolve(__dirname, "..", "..");
const ICON_DIR = path.join(ROOT, "assets", "fig1_icons");
const OUT_DIR = path.join(ROOT, "figures");

const W = 13.5;
const H = 8.2;
const SCALE = 220;

const COLORS = {
  text: "1C2630",
  muted: "5F6C78",
  blue: "1557A6",
  blueFill: "F2F7FF",
  amber: "8A5A16",
  amberFill: "FFF8ED",
  green: "1F7A2E",
  greenFill: "F2FBF3",
  purple: "5B3B93",
  purpleFill: "F7F3FF",
  data: "0B65A3",
  dataFill: "F1F8FF",
  red: "C9252C",
  redFill: "FFF3F4",
  gray: "6F7782",
  grayFill: "F6F7F8",
  line: "D8DEE6",
  white: "FFFFFF",
};

const icons = {
  requester: "requester.svg",
  task: "task-document.svg",
  lock: "lock.svg",
  key: "key.svg",
  shield: "shield.svg",
  gear: "orchestrator-gear.svg",
  discovery: "provider-discovery.svg",
  group: "group-selection.svg",
  shard: "shard-grid.svg",
  commit: "placement-commitment.svg",
  server: "provider-server.svg",
  warning: "warning-triangle.svg",
  ledger: "ledger-chain.svg",
  escrow: "escrow-wallet.svg",
  outcome: "challenge-outcome.svg",
  bank: "settlement-bank.svg",
  verifier: "verifier-scales.svg",
  datastore: "data-store.svg",
  encObject: "encrypted-task-object.svg",
  ciphertext: "ciphertext-storage.svg",
};

function escXml(s) {
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function px(v) {
  return Math.round(v * SCALE * 1000) / 1000;
}

function hex(c) {
  return c.replace("#", "");
}

async function iconData(name, color) {
  const raw = fs.readFileSync(path.join(ICON_DIR, icons[name]), "utf8");
  const svg = raw.replace(/currentColor/g, `#${hex(color)}`);
  const png = await sharp(Buffer.from(svg)).resize(256, 256).png().toBuffer();
  return {
    ppt: `image/png;base64,${png.toString("base64")}`,
    svg: `data:image/png;base64,${png.toString("base64")}`,
  };
}

function textLines(value) {
  return Array.isArray(value) ? value : String(value).split("\n");
}

class FigureBuilder {
  constructor(iconCache) {
    this.iconCache = iconCache;
    this.svg = [];
    this.pptx = new pptxgen();
    this.pptx.author = "VeriEdge";
    this.pptx.subject = "Figure 1 system workflow";
    this.pptx.title = "VeriEdge system model and workflow";
    this.pptx.company = "Anonymous";
    this.pptx.layout = "LAYOUT_WIDE";
    this.pptx.defineLayout({ name: "FIG1", width: W, height: H });
    this.pptx.layout = "FIG1";
    this.slide = this.pptx.addSlide();
    this.slide.background = { color: "FFFFFF" };
  }

  rect(x, y, w, h, opts = {}) {
    const fill = opts.fill || "FFFFFF";
    const stroke = opts.stroke || COLORS.line;
    const sw = opts.sw || 1.2;
    const r = opts.r == null ? 0.12 : opts.r;
    const dash = opts.dash ? ` stroke-dasharray="${opts.dash}"` : "";
    this.slide.addShape(this.pptx.ShapeType.roundRect, {
      x, y, w, h,
      rectRadius: r,
      fill: { color: hex(fill), transparency: opts.fillTrans || 0 },
      line: { color: hex(stroke), width: sw, dashType: opts.dash ? "dash" : "solid" },
    });
    this.svg.push(`<rect x="${px(x)}" y="${px(y)}" width="${px(w)}" height="${px(h)}" rx="${px(r)}" fill="#${hex(fill)}" stroke="#${hex(stroke)}" stroke-width="${sw * 1.4}"${dash}/>`);
  }

  line(x1, y1, x2, y2, opts = {}) {
    const color = opts.color || COLORS.blue;
    const width = opts.width || 1.4;
    const dash = opts.dash ? "dash" : "solid";
    const end = opts.end === false ? null : "triangle";
    const begin = opts.begin || null;
    this.slide.addShape(this.pptx.ShapeType.line, {
      x: x1, y: y1, w: x2 - x1, h: y2 - y1,
      line: {
        color: hex(color),
        width,
        dashType: dash,
        beginArrowType: begin,
        endArrowType: end,
      },
    });
    const marker = end ? ` marker-end="url(#arrow-${hex(color)})"` : "";
    const dashAttr = opts.dash ? ` stroke-dasharray="${px(0.08)},${px(0.06)}"` : "";
    this.svg.push(`<line x1="${px(x1)}" y1="${px(y1)}" x2="${px(x2)}" y2="${px(y2)}" stroke="#${hex(color)}" stroke-width="${width * 1.8}"${dashAttr}${marker} fill="none"/>`);
  }

  polyline(points, opts = {}) {
    for (let i = 0; i < points.length - 1; i += 1) {
      this.line(points[i][0], points[i][1], points[i + 1][0], points[i + 1][1], {
        ...opts,
        end: i === points.length - 2 ? opts.end !== false : false,
      });
    }
  }

  text(value, x, y, w, h, opts = {}) {
    const fontSize = opts.size || 10;
    const color = opts.color || COLORS.text;
    const fontFace = opts.font || "Aptos";
    const bold = !!opts.bold;
    const italic = !!opts.italic;
    const align = opts.align || "left";
    const valign = opts.valign || "top";
    const margin = opts.margin == null ? 0.02 : opts.margin;
    const lines = textLines(value);

    this.slide.addText(lines.join("\n"), {
      x, y, w, h,
      fontFace,
      fontSize,
      color: hex(color),
      bold,
      italic,
      margin,
      breakLine: true,
      fit: "shrink",
      align,
      valign,
      breakLine: true,
    });

    const lineGap = fontSize * 1.24;
    let anchor = "start";
    let tx = x + 0.02;
    if (align === "center") {
      anchor = "middle";
      tx = x + w / 2;
    } else if (align === "right") {
      anchor = "end";
      tx = x + w - 0.02;
    }
    let startY = y + fontSize / 72 + 0.02;
    if (valign === "mid" || valign === "middle") {
      startY = y + h / 2 - ((lines.length - 1) * lineGap) / (2 * 72) + fontSize / 144;
    }
    this.svg.push(`<text x="${px(tx)}" y="${px(startY)}" font-family="${fontFace}, Arial, sans-serif" font-size="${fontSize * SCALE / 72}" fill="#${hex(color)}" text-anchor="${anchor}" font-weight="${bold ? "700" : "400"}" font-style="${italic ? "italic" : "normal"}">`);
    lines.forEach((line, idx) => {
      const dy = idx === 0 ? 0 : lineGap * SCALE / 72;
      this.svg.push(`<tspan x="${px(tx)}" dy="${idx === 0 ? 0 : dy}">${escXml(line)}</tspan>`);
    });
    this.svg.push(`</text>`);
  }

  icon(name, color, x, y, size) {
    const data = this.iconCache[`${name}:${hex(color)}`];
    this.slide.addImage({ data: data.ppt, x, y, w: size, h: size });
    this.svg.push(`<image href="${data.svg}" x="${px(x)}" y="${px(y)}" width="${px(size)}" height="${px(size)}"/>`);
  }

  step(n, x, y, color = COLORS.blue) {
    this.slide.addShape(this.pptx.ShapeType.ellipse, {
      x, y, w: 0.27, h: 0.27,
      fill: { color: hex(color) },
      line: { color: hex(color), transparency: 100 },
    });
    this.slide.addText(String(n), {
      x, y: y + 0.005, w: 0.27, h: 0.24,
      fontFace: "Aptos", fontSize: 8.5,
      bold: true, color: "FFFFFF",
      align: "center", valign: "mid",
      margin: 0,
    });
    this.svg.push(`<circle cx="${px(x + 0.135)}" cy="${px(y + 0.135)}" r="${px(0.135)}" fill="#${hex(color)}"/>`);
    this.svg.push(`<text x="${px(x + 0.135)}" y="${px(y + 0.18)}" font-family="Aptos, Arial, sans-serif" font-size="${8.5 * SCALE / 72}" fill="#FFFFFF" text-anchor="middle" font-weight="700">${n}</text>`);
  }

  card(x, y, w, h, iconName, color, title, subtitle) {
    this.rect(x, y, w, h, { fill: "FFFFFF", stroke: color, sw: 0.8, r: 0.08 });
    this.icon(iconName, color, x + 0.12, y + 0.11, 0.28);
    this.text(title, x + 0.48, y + 0.12, w - 0.58, 0.22, { size: 8.5, color, bold: true, margin: 0 });
    if (subtitle) {
      this.text(subtitle, x + 0.48, y + 0.35, w - 0.58, h - 0.38, { size: 7.2, color: COLORS.muted, margin: 0 });
    }
  }

  panelHeader(x, y, w, iconName, color, title, subtitle) {
    this.icon(iconName, color, x + 0.18, y + 0.16, 0.38);
    this.text(title, x + 0.67, y + 0.12, w - 0.85, 0.32, { size: 13, color, bold: true, margin: 0 });
    if (subtitle) {
      this.text(subtitle, x + 0.67, y + 0.46, w - 0.85, 0.22, { size: 8.3, color: COLORS.muted, italic: true, margin: 0 });
    }
  }

  async write() {
    const markerDefs = [COLORS.blue, COLORS.red, COLORS.green, COLORS.purple].map(c => {
      const id = `arrow-${hex(c)}`;
      return `<marker id="${id}" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto" markerUnits="strokeWidth"><path d="M0,0 L8,4 L0,8 z" fill="#${hex(c)}"/></marker>`;
    }).join("");
    const svgDoc = `<svg xmlns="http://www.w3.org/2000/svg" width="${px(W)}" height="${px(H)}" viewBox="0 0 ${px(W)} ${px(H)}">
<defs>${markerDefs}</defs>
<rect width="100%" height="100%" fill="#FFFFFF"/>
${this.svg.join("\n")}
</svg>`;

    fs.mkdirSync(OUT_DIR, { recursive: true });
    const svgPath = path.join(OUT_DIR, "fig_system_model_workflow_v2.svg");
    const pngPath = path.join(OUT_DIR, "fig_system_model_workflow_v2.png");
    const pptxPath = path.join(OUT_DIR, "fig_system_model_workflow_v2.pptx");
    fs.writeFileSync(svgPath, svgDoc);
    await sharp(Buffer.from(svgDoc)).png().toFile(pngPath);
    await this.pptx.writeFile({ fileName: pptxPath });
    return { svgPath, pngPath, pptxPath };
  }
}

async function build() {
  const neededIconColors = [
    ["requester", COLORS.blue], ["task", COLORS.blue], ["lock", COLORS.blue],
    ["key", COLORS.blue], ["shield", COLORS.blue], ["gear", COLORS.amber],
    ["discovery", COLORS.amber], ["group", COLORS.amber], ["shard", COLORS.amber],
    ["commit", COLORS.amber], ["lock", COLORS.amber], ["server", COLORS.green],
    ["server", COLORS.gray], ["server", COLORS.red], ["warning", COLORS.red], ["ledger", COLORS.purple],
    ["task", COLORS.purple], ["escrow", COLORS.purple], ["outcome", COLORS.purple],
    ["bank", COLORS.purple], ["verifier", COLORS.purple], ["datastore", COLORS.data],
    ["encObject", COLORS.data], ["ciphertext", COLORS.data],
  ];
  const iconCache = {};
  for (const [name, color] of neededIconColors) {
    iconCache[`${name}:${hex(color)}`] = await iconData(name, color);
  }

  const f = new FigureBuilder(iconCache);

  f.rect(0.25, 0.25, 2.55, 3.55, { fill: COLORS.blueFill, stroke: COLORS.blue, sw: 1.3, r: 0.14 });
  f.panelHeader(0.42, 0.32, 2.2, "requester", COLORS.blue, "Requester R", "owns task plaintext");
  f.card(0.48, 1.02, 2.08, 0.52, "task", COLORS.blue, "prepare task", "public descriptor only");
  f.card(0.48, 1.67, 2.08, 0.52, "lock", COLORS.blue, "encrypt payload", "C_j = Enc_k(x_j)");
  f.card(0.48, 2.32, 2.08, 0.62, "key", COLORS.blue, "targeted access", "release e_i,j after commit");
  f.icon("shield", COLORS.blue, 0.48, 3.17, 0.34);
  f.text("outside access-tuple\npath of O", 0.88, 3.19, 1.55, 0.35, { size: 7.2, color: COLORS.muted, margin: 0 });

  f.rect(3.25, 0.25, 3.15, 3.55, { fill: COLORS.amberFill, stroke: COLORS.amber, sw: 1.3, r: 0.14 });
  f.panelHeader(3.42, 0.32, 2.8, "gear", COLORS.amber, "Orchestrator O", "verification-aware control plane");
  f.card(3.52, 1.07, 2.58, 0.43, "discovery", COLORS.amber, "provider discovery", null);
  f.card(3.52, 1.62, 2.58, 0.43, "group", COLORS.amber, "group selection", null);
  f.card(3.52, 2.17, 2.58, 0.43, "shard", COLORS.amber, "shard mapping", null);
  f.card(3.52, 2.72, 2.58, 0.43, "commit", COLORS.amber, "placement commitment", null);
  f.icon("lock", COLORS.amber, 3.55, 3.31, 0.25);
  f.text("No task plaintext or access tuples", 3.86, 3.31, 2.1, 0.25, { size: 7.4, color: COLORS.amber, italic: true, margin: 0 });

  f.rect(7.0, 0.25, 6.25, 4.05, { fill: COLORS.greenFill, stroke: COLORS.green, sw: 1.3, r: 0.14 });
  f.panelHeader(7.18, 0.32, 5.7, "server", COLORS.green, "Provider pool", "P = {P1, ..., Pn}");
  f.rect(7.35, 1.05, 4.35, 1.95, { fill: "FFFFFF", stroke: COLORS.green, sw: 1, r: 0.12, dash: `${px(0.08)} ${px(0.06)}` });
  f.text("selected execution group G_j = {P1, P2, P3}", 7.65, 1.17, 3.75, 0.25, { size: 8.6, color: COLORS.green, bold: true, align: "center", margin: 0 });

  const providerY = 1.55;
  const pW = 0.9;
  const pH = 0.72;
  const pXs = [7.62, 9.08, 10.54];
  ["P1", "P2", "P3"].forEach((p, idx) => {
    const isBad = p === "P3";
    f.rect(pXs[idx], providerY, pW, pH, { fill: isBad ? COLORS.redFill : "F8FFF8", stroke: isBad ? COLORS.red : COLORS.green, sw: 1.1, r: 0.08 });
    f.icon("server", isBad ? COLORS.red : COLORS.green, pXs[idx] + 0.26, providerY + 0.09, 0.34);
    f.text(p, pXs[idx], providerY + 0.49, pW, 0.2, { size: 9.5, color: isBad ? COLORS.red : COLORS.text, bold: true, align: "center", margin: 0 });
  });
  f.icon("warning", COLORS.red, pXs[2] + 0.72, providerY + 0.32, 0.24);
  f.line(8.52, 1.90, 9.08, 1.90, { color: COLORS.text, width: 1, end: false });
  f.line(9.98, 1.90, 10.54, 1.90, { color: COLORS.text, width: 1, end: false });
  f.text("shard-boundary activations", 8.1, 2.47, 2.9, 0.24, { size: 7.4, color: COLORS.green, italic: true, align: "center", margin: 0 });
  f.rect(7.85, 3.28, 1.0, 0.55, { fill: COLORS.grayFill, stroke: COLORS.gray, sw: 0.9, r: 0.08 });
  f.icon("server", COLORS.gray, 8.02, 3.37, 0.25);
  f.text("P4", 8.31, 3.43, 0.36, 0.17, { size: 8.6, color: COLORS.gray, bold: true, margin: 0 });
  f.rect(9.15, 3.28, 1.0, 0.55, { fill: COLORS.grayFill, stroke: COLORS.gray, sw: 0.9, r: 0.08 });
  f.icon("server", COLORS.gray, 9.32, 3.37, 0.25);
  f.text("P5", 9.61, 3.43, 0.36, 0.17, { size: 8.6, color: COLORS.gray, bold: true, margin: 0 });
  f.text("unselected providers\n(no access packages)", 10.34, 3.28, 1.52, 0.42, { size: 7.4, color: COLORS.gray, italic: true, margin: 0 });

  f.rect(11.92, 0.92, 1.05, 0.78, { fill: "FFFFFF", stroke: COLORS.green, sw: 0.9, r: 0.08, dash: `${px(0.08)} ${px(0.06)}` });
  f.text("placement\ndefines\naccountability\nboundary", 12.0, 1.0, 0.88, 0.6, { size: 6.8, color: COLORS.green, italic: true, align: "center", margin: 0 });

  f.rect(0.55, 6.36, 6.5, 1.38, { fill: COLORS.purpleFill, stroke: COLORS.purple, sw: 1.2, r: 0.12 });
  f.icon("ledger", COLORS.purple, 0.82, 6.55, 0.38);
  f.text("Contract / Ledger L", 1.28, 6.54, 2.25, 0.3, { size: 12.3, color: COLORS.purple, bold: true, margin: 0 });
  const ledCards = [
    ["task", "commitments"],
    ["escrow", "escrow"],
    ["outcome", "challenge\noutcome"],
    ["bank", "settlement"],
  ];
  ledCards.forEach(([ic, label], idx) => {
    const x = 0.8 + idx * 1.52;
    f.rect(x, 7.04, 1.28, 0.48, { fill: "FFFFFF", stroke: "D8CCE9", sw: 0.7, r: 0.06 });
    f.icon(ic, COLORS.purple, x + 0.09, 7.13, 0.22);
    f.text(label, x + 0.38, 7.12, 0.8, 0.24, { size: 6.8, color: COLORS.text, margin: 0 });
  });

  f.rect(7.45, 6.36, 5.35, 1.38, { fill: COLORS.dataFill, stroke: COLORS.data, sw: 1.2, r: 0.12 });
  f.icon("datastore", COLORS.data, 7.75, 6.54, 0.38);
  f.text("Off-chain Data Store D", 8.2, 6.54, 2.65, 0.3, { size: 12.3, color: COLORS.data, bold: true, margin: 0 });
  f.rect(7.75, 7.04, 2.1, 0.5, { fill: "FFFFFF", stroke: "C8E1F5", sw: 0.7, r: 0.06 });
  f.icon("encObject", COLORS.data, 7.88, 7.12, 0.24);
  f.text("encrypted task\nobject C_j", 8.2, 7.10, 1.4, 0.28, { size: 6.8, color: COLORS.text, margin: 0 });
  f.rect(10.25, 7.04, 1.95, 0.5, { fill: "FFFFFF", stroke: "C8E1F5", sw: 0.7, r: 0.06 });
  f.icon("ciphertext", COLORS.data, 10.39, 7.12, 0.24);
  f.text("ciphertext\nstorage", 10.72, 7.10, 1.0, 0.28, { size: 6.8, color: COLORS.text, margin: 0 });

  f.rect(5.45, 4.95, 2.3, 0.72, { fill: "FFFFFF", stroke: COLORS.purple, sw: 1.1, r: 0.08 });
  f.icon("verifier", COLORS.purple, 5.65, 5.12, 0.28);
  f.text("Verify(E_j, pi_j, theta_j)", 6.0, 5.15, 1.55, 0.2, { size: 8.6, color: COLORS.purple, bold: true, margin: 0 });
  f.text("TSTC challenge verifier", 6.0, 5.38, 1.5, 0.18, { size: 6.8, color: COLORS.muted, italic: true, margin: 0 });

  // Routine path arrows.
  f.line(2.8, 1.38, 3.25, 1.38, { color: COLORS.blue, width: 1.4 });
  f.step(1, 2.92, 1.07, COLORS.blue);
  f.text("task descriptor", 2.88, 0.92, 0.68, 0.18, { size: 6.6, color: COLORS.blue, margin: 0, align: "center" });

  f.line(7.0, 1.42, 6.4, 1.42, { color: COLORS.blue, width: 1.4 });
  f.step(2, 6.62, 1.11, COLORS.blue);
  f.text("profiles", 6.50, 0.95, 0.52, 0.18, { size: 6.6, color: COLORS.blue, margin: 0, align: "center" });

  f.polyline([[4.85, 3.8], [4.85, 6.36]], { color: COLORS.blue, width: 1.35 });
  f.step(3, 4.58, 4.2, COLORS.blue);
  f.text("placement record\n(G_j, sigma_j, theta_j)", 3.72, 4.46, 1.35, 0.38, { size: 6.3, color: COLORS.blue, margin: 0, align: "center" });

  f.polyline([[1.52, 3.8], [1.52, 5.95], [7.75, 5.95], [7.75, 6.36]], { color: COLORS.blue, width: 1.25 });
  f.step(4, 1.16, 4.86, COLORS.blue);
  f.text("upload encrypted\nobject C_j", 1.68, 5.28, 1.2, 0.34, { size: 6.8, color: COLORS.blue, margin: 0 });

  f.polyline([[2.8, 2.78], [2.95, 2.78], [2.95, 4.42], [7.35, 4.42], [7.35, 2.78]], { color: COLORS.blue, width: 1.25 });
  f.step(5, 7.12, 4.12, COLORS.blue);
  f.text("access packages e_i,j", 6.08, 4.18, 1.15, 0.2, { size: 6.5, color: COLORS.blue, margin: 0, align: "center" });
  f.text("execute sigma_j and return y_j", 9.0, 2.73, 1.85, 0.18, { size: 6.8, color: COLORS.green, italic: true, align: "center", margin: 0 });

  // Challenge path arrows.
  f.polyline([[0.78, 3.8], [0.78, 5.12], [5.45, 5.12]], { color: COLORS.red, width: 1.15, dash: true });
  f.step(6, 0.5, 4.42, COLORS.red);
  f.text("challenge", 0.55, 4.72, 0.62, 0.18, { size: 6.8, color: COLORS.red, italic: true, margin: 0 });

  f.polyline([[11.0, 2.25], [11.0, 4.62], [7.75, 5.12]], { color: COLORS.red, width: 1.15, dash: true });
  f.step(7, 10.68, 4.03, COLORS.red);
  f.text("sketch evidence E_j", 10.12, 4.36, 1.18, 0.2, { size: 6.5, color: COLORS.red, italic: true, margin: 0, align: "center" });

  f.polyline([[6.6, 5.67], [6.6, 6.36]], { color: COLORS.red, width: 1.15, dash: true });
  f.step(8, 6.18, 5.92, COLORS.red);
  f.text("first mismatch b*_j\nsettlement", 5.02, 5.9, 1.0, 0.34, { size: 6.5, color: COLORS.red, italic: true, margin: 0, align: "right" });

  // Legend.
  f.line(3.72, 7.95, 4.52, 7.95, { color: COLORS.blue, width: 1.2 });
  f.text("Routine path", 4.65, 7.86, 1.0, 0.2, { size: 7.2, color: COLORS.text, margin: 0 });
  f.line(6.62, 7.95, 7.42, 7.95, { color: COLORS.red, width: 1.2, dash: true });
  f.text("Challenge path", 7.55, 7.86, 1.1, 0.2, { size: 7.2, color: COLORS.text, margin: 0 });

  const outputs = await f.write();
  console.log(JSON.stringify(outputs, null, 2));
}

build().catch(err => {
  console.error(err);
  process.exit(1);
});
