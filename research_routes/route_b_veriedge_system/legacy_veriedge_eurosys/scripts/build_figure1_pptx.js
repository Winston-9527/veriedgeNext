const pptxgen = require("pptxgenjs");

const pptx = new pptxgen();
pptx.author = "Codex";
pptx.subject = "Editable Figure 1 layout for VeriEdge";
pptx.title = "VeriEdge Figure 1 Editable Layout";
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
  green: "167A2F",
  greenLight: "F4FBF5",
  black: "111111",
  gray: "D8DEE9",
  grayText: "4A5568",
  white: "FFFFFF",
};

const S = pptx.ShapeType;
const A = pptx.ShapeType.arc;

function addText(text, x, y, w, h, opts = {}) {
  slide.addText(text, {
    x, y, w, h,
    margin: opts.margin ?? 0.02,
    fontFace: opts.fontFace || "Arial",
    fontSize: opts.fontSize || 9.5,
    color: opts.color || C.black,
    bold: opts.bold || false,
    italic: opts.italic || false,
    align: opts.align || "center",
    valign: opts.valign || "mid",
    breakLine: false,
    fit: "shrink",
  });
}

function addPlane(x, y, w, h, color, fill, title, titleY) {
  slide.addShape(S.roundRect, {
    x, y, w, h,
    rectRadius: 0.08,
    fill: { color: fill, transparency: 8 },
    line: { color, width: 1.2 },
  });
  addText(title, x + 0.05, titleY, w - 0.1, 0.25, {
    fontSize: 15,
    color,
    bold: true,
    align: "left",
  });
}

function addModule({ x, y, w, h, title, subtitle, color, fill, iconSlot = true, titleSize = 10.5 }) {
  slide.addShape(S.roundRect, {
    x, y, w, h,
    rectRadius: 0.06,
    fill: { color: fill || C.white },
    line: { color, width: 1.1 },
  });
  if (iconSlot) {
    const slotW = Math.min(w * 0.42, 0.62);
    const slotH = Math.min(h * 0.46, 0.48);
    slide.addShape(S.roundRect, {
      x: x + 0.12,
      y: y + (h - slotH) / 2,
      w: slotW,
      h: slotH,
      rectRadius: 0.03,
      fill: { color: "FFFFFF", transparency: 100 },
      line: { color: "C9D2E3", width: 0.75, dashType: "dash" },
    });
    addText(title, x + slotW + 0.18, y + 0.11, w - slotW - 0.28, subtitle ? h * 0.45 : h - 0.18, {
      fontSize: titleSize,
      color,
      bold: true,
    });
    if (subtitle) {
      addText(subtitle, x + slotW + 0.18, y + h * 0.53, w - slotW - 0.28, h * 0.34, {
        fontSize: 7.5,
        color: C.black,
      });
    }
  } else {
    addText(title, x + 0.08, y + 0.1, w - 0.16, subtitle ? h * 0.42 : h - 0.2, {
      fontSize: titleSize,
      color,
      bold: true,
    });
    if (subtitle) {
      addText(subtitle, x + 0.12, y + h * 0.52, w - 0.24, h * 0.36, {
        fontSize: 7.5,
        color: C.black,
      });
    }
  }
}

function addLine(x1, y1, x2, y2, color, opts = {}) {
  let x = x1;
  let y = y1;
  let w = x2 - x1;
  let h = y2 - y1;
  let beginArrow = opts.beginArrow ? "triangle" : "none";
  let endArrow = opts.endArrow === false ? "none" : "triangle";

  // PowerPoint can mark a file as corrupted when line extents are negative.
  // For horizontal/vertical reverse lines, swap endpoints and put the arrow on
  // the beginning so the visual direction is preserved with positive extents.
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
    x,
    y,
    w,
    h,
    line: {
      color,
      width: opts.width || 1.35,
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
    fontSize: opts.fontSize || 8.2,
    color,
    bold: opts.bold || false,
    align: opts.align || "center",
    italic: opts.italic || false,
  });
}

// Planes
addPlane(0.13, 0.32, 13.05, 1.55, C.orange, C.orangeLight, "On-chain coordination substrate", 0.03);
addPlane(0.13, 2.55, 13.05, 3.05, C.blue, C.blueLight, "Off-chain orchestration, delivery, and execution", 2.58);
addPlane(0.13, 6.02, 8.4, 1.18, C.green, C.greenLight, "Verification plane", 5.76);

// Top modules
addModule({ x: 1.06, y: 0.5, w: 2.45, h: 1.03, title: "Registry & escrow", color: C.orange, fill: C.white });
addModule({ x: 4.8, y: 0.5, w: 1.85, h: 1.03, title: "Allocation\ncommitments", color: C.orange, fill: C.white, titleSize: 10 });
addModule({ x: 7.65, y: 0.5, w: 1.95, h: 1.03, title: "Result / trace\ncommitments", color: C.orange, fill: C.white, titleSize: 10 });
addModule({ x: 10.9, y: 0.5, w: 2.0, h: 1.03, title: "Settlement &\nslashing", color: C.orange, fill: C.white, titleSize: 10 });

// Off-chain modules
addModule({ x: 0.35, y: 3.0, w: 1.78, h: 1.68, title: "Requester", subtitle: "task metadata\nprompt / payload owner", color: C.blue, fill: C.white, titleSize: 10 });
addModule({ x: 4.55, y: 2.92, w: 2.1, h: 0.72, title: "IPFS / ciphertext store", color: C.blue, fill: C.white, titleSize: 9.5 });
addModule({ x: 4.55, y: 3.88, w: 2.1, h: 1.22, title: "Verification-aware\norchestrator", color: C.blue, fill: C.white, titleSize: 9 });
addModule({ x: 7.05, y: 4.28, w: 1.9, h: 0.82, title: "Targeted key\nrelease", color: C.blue, fill: C.white, titleSize: 9 });
slide.addShape(S.roundRect, {
  x: 10.25, y: 2.86, w: 2.7, h: 2.05,
  rectRadius: 0.06,
  fill: { color: C.white },
  line: { color: C.blue, width: 1.1 },
});
addText("Selected provider group", 10.48, 3.02, 2.25, 0.26, {
  fontSize: 10,
  color: C.blue,
  bold: true,
});
addText("collaborative inference", 10.62, 3.38, 1.95, 0.18, {
  fontSize: 7.8,
  color: C.black,
});
["P1", "P2", "P3"].forEach((name, idx) => {
  const x = 10.66 + idx * 0.62;
  slide.addShape(S.roundRect, {
    x, y: 3.64, w: 0.38, h: 0.26,
    rectRadius: 0.03,
    fill: { color: C.white },
    line: { color: C.blue, width: 0.9 },
  });
  addText(name, x + 0.02, 3.67, 0.34, 0.13, {
    fontSize: 7.5,
    color: C.blue,
    bold: true,
  });
  if (idx < 2) addLine(x + 0.38, 3.77, x + 0.62, 3.77, C.black, { width: 0.85 });
});
addText("shard plan & execution trace", 10.62, 4.02, 1.95, 0.18, {
  fontSize: 7.5,
  color: C.black,
});
slide.addShape(S.roundRect, {
  x: 10.56, y: 4.28, w: 1.85, h: 0.42,
  rectRadius: 0.03,
  fill: { color: "FFFFFF", transparency: 100 },
  line: { color: "C9D2E3", width: 0.75, dashType: "dash" },
});

// Verification modules
addModule({ x: 1.55, y: 6.28, w: 1.95, h: 0.62, title: "Routine screening", color: C.green, fill: C.white, titleSize: 8.5 });
addModule({ x: 5.62, y: 6.28, w: 2.15, h: 0.62, title: "TSTC dispute\nverifier", color: C.green, fill: C.white, titleSize: 8.2 });

// On-chain black control path
addLine(3.51, 1.02, 4.8, 1.02, C.black);
addLine(6.65, 1.02, 7.65, 1.02, C.black);
addLine(9.6, 1.02, 10.9, 1.02, C.black);

// Registry inputs
addPolyline([[0.95, 2.55], [0.95, 1.95], [1.52, 1.95], [1.52, 1.53]], C.black);
label("task metadata\n& escrow", 0.25, 1.98, 1.0, 0.35, C.black);
addPolyline([[3.9, 2.55], [3.9, 1.95], [2.65, 1.95], [2.65, 1.53]], C.black);
label("resource ad\n& stake", 3.18, 1.98, 1.0, 0.35, C.black);

// Allocation and result commitments
addPolyline([[5.6, 3.88], [6.9, 3.88], [6.9, 2.0], [5.72, 2.0], [5.72, 1.53]], C.black);
addPolyline([[11.6, 2.86], [11.6, 2.0], [8.75, 2.0], [8.75, 1.53]], C.black);
label("result / execution-trace\ncommitments", 8.9, 2.04, 1.45, 0.36, C.black, { fontSize: 7.4, align: "left" });

// Off-chain control path
addLine(4.55, 4.5, 2.13, 4.5, C.black);
label("execution group G_j", 2.45, 4.28, 1.5, 0.16, C.black);
addLine(6.65, 4.25, 10.25, 4.25, C.black);
label("shard plan", 7.85, 4.03, 1.0, 0.18, C.black);

// Data path
addLine(2.13, 3.32, 4.55, 3.32, C.blue);
label("ciphertext C_j", 2.78, 3.12, 1.25, 0.16, C.blue);
addLine(6.65, 3.32, 10.25, 3.32, C.blue);
label("fetch C_j", 8.1, 3.12, 1.0, 0.16, C.blue);
addPolyline([[2.13, 4.96], [2.13, 5.28], [6.9, 5.28], [6.9, 4.7], [7.05, 4.7]], C.blue);
label("access tuple (\u2113_j, k_j)", 2.6, 5.08, 1.65, 0.18, C.blue);
addLine(8.95, 4.7, 10.25, 4.7, C.blue);
label("key package e_{i,j}", 9.08, 4.5, 1.05, 0.18, C.blue);

// Verification path
addPolyline([[0.95, 4.68], [0.95, 5.65], [2.15, 5.65], [2.15, 6.28]], C.green);
label("screen / trigger", 1.1, 5.72, 1.0, 0.16, C.green);
addLine(3.5, 6.59, 5.62, 6.59, C.green);
label("escalation", 4.15, 6.38, 0.8, 0.16, C.green);
addPolyline([[11.6, 4.91], [11.6, 5.36], [7.77, 5.36], [7.77, 6.59]], C.green);
label("trace / checkpoints", 8.15, 5.52, 1.3, 0.16, C.green);
addPolyline([[6.7, 6.28], [6.7, 5.5], [9.85, 5.5], [9.85, 1.53], [11.6, 1.53]], C.green);
label("verdict &\nlocalization", 9.05, 3.72, 0.95, 0.32, C.green);

// Settlement outcomes
addPolyline([[11.6, 1.53], [11.6, 2.38], [0.12, 2.38], [0.12, 3.65], [0.35, 3.65]], C.orange, { dash: "dash" });
label("refund /\ncompensation", 9.95, 2.18, 1.0, 0.32, C.orange);
addPolyline([[12.1, 1.53], [12.1, 2.35], [12.15, 2.86]], C.orange, { dash: "dash" });
label("payment /\nslashing", 12.25, 2.05, 0.9, 0.32, C.orange);

// Legend
slide.addShape(S.roundRect, {
  x: 10.95, y: 6.02, w: 2.15, h: 1.08,
  rectRadius: 0.04,
  fill: { color: C.white },
  line: { color: "8892A0", width: 0.9 },
});
addLine(11.12, 6.23, 11.72, 6.23, C.black);
label("Control / commit path", 11.82, 6.14, 1.05, 0.18, C.black, { fontSize: 7.2, align: "left" });
addLine(11.12, 6.45, 11.72, 6.45, C.blue);
label("Data / delivery path", 11.82, 6.36, 1.05, 0.18, C.black, { fontSize: 7.2, align: "left" });
addLine(11.12, 6.67, 11.72, 6.67, C.green);
label("Verification path", 11.82, 6.58, 1.05, 0.18, C.black, { fontSize: 7.2, align: "left" });
addLine(11.12, 6.89, 11.72, 6.89, C.orange, { dash: "dash" });
label("Settlement outcomes", 11.82, 6.8, 1.05, 0.18, C.black, { fontSize: 7.2, align: "left" });

pptx.writeFile({ fileName: "figure1_editable_layout.pptx" });
