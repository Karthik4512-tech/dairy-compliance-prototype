const pptxgen = require("pptxgenjs");

const FOREST = "2C5F2D";
const MOSS = "97BC62";
const CREAM = "F5F5F5";
const DARK = "1B2B1C";
const TEXT = "222222";

const pres = new pptxgen();
pres.layout = "LAYOUT_WIDE"; // 13.3 x 7.5
const W = 13.33, H = 7.5;

function titleSlide() {
  const s = pres.addSlide();
  s.background = { color: DARK };
  s.addShape("rect", { x: 0, y: 0, w: W, h: H, fill: { color: DARK } });
  s.addShape("ellipse", { x: 9.8, y: -2.2, w: 6, h: 6, fill: { color: FOREST, transparency: 40 }, line: { type: "none" } });
  s.addShape("ellipse", { x: -2, y: 4.8, w: 5, h: 5, fill: { color: MOSS, transparency: 65 }, line: { type: "none" } });
  s.addText("MILK COLLECTION COMPLIANCE", { x: 0.8, y: 2.1, w: 10, h: 0.4, fontFace: "Calibri", fontSize: 14, color: MOSS, charSpacing: 3, bold: true, isTextBox: true });
  s.addText("A Field-Ready Automated Compliance Evidence Pack", { x: 0.8, y: 2.5, w: 11, h: 1.6, fontFace: "Cambria", fontSize: 40, bold: true, color: "FFFFFF", isTextBox: true });
  s.addText("Joining sensor, calibration, custody, route and batch records into one audit-ready pack \u2014 even when GPS, network, or sensor data is incomplete.", {
    x: 0.8, y: 4.1, w: 9.5, h: 0.9, fontFace: "Calibri", fontSize: 16, color: CREAM, isTextBox: true,
  });
  s.addText("Working Prototype  \u2022  Data Generation + Evidence Engine + Experiments + Failure-Mode Testing", {
    x: 0.8, y: 6.7, w: 10, h: 0.4, fontFace: "Calibri", fontSize: 12, color: MOSS, italic: true, isTextBox: true,
  });
}

function sectionHeader(s, kicker, title) {
  s.background = { color: "FFFFFF" };
  s.addText(kicker.toUpperCase(), { x: 0.6, y: 0.4, w: 10, h: 0.35, fontFace: "Calibri", fontSize: 12, bold: true, color: FOREST, charSpacing: 2, isTextBox: true });
  s.addText(title, { x: 0.6, y: 0.72, w: 12, h: 0.7, fontFace: "Cambria", fontSize: 28, bold: true, color: DARK, isTextBox: true });
}

function problemSlide() {
  const s = pres.addSlide();
  sectionHeader(s, "The Problem", "Manual, disconnected evidence delays real decisions");
  const rows = [
    ["Release or quarantine a batch", "Cold-chain breach found too late, after further processing"],
    ["Accept/reject a load at the gate", "No fast way to check the logger's calibration status"],
    ["Pay or dispute a producer amount", "Custody chain can't be reconstructed quickly"],
    ["Respond to a regulator", "~20\u201325 min of manual log-pulling per batch, inconsistent across auditors"],
    ["Schedule device maintenance", "Expired calibration caught only retroactively, if at all"],
  ];
  let y = 1.75;
  rows.forEach(([left, right], i) => {
    s.addShape("rect", { x: 0.6, y, w: 0.5, h: 0.9, fill: { color: i % 2 === 0 ? FOREST : MOSS }, line: { type: "none" }, rectRadius: 0.08 });
    s.addText(String(i + 1), { x: 0.6, y, w: 0.5, h: 0.9, align: "center", valign: "middle", fontFace: "Calibri", fontSize: 20, bold: true, color: "FFFFFF", isTextBox: true, margin: 0 });
    s.addText(left, { x: 1.3, y, w: 4.7, h: 0.9, valign: "middle", fontFace: "Calibri", fontSize: 14, bold: true, color: DARK, isTextBox: true });
    s.addText(right, { x: 6.1, y, w: 6.6, h: 0.9, valign: "middle", fontFace: "Calibri", fontSize: 13, color: "444444", isTextBox: true });
    y += 1.02;
  });
}

function workflowSlide() {
  const s = pres.addSlide();
  sectionHeader(s, "Field Workflow", "From five disconnected logs to one evidence pack");
  const stages = ["Producer\nhandover", "Truck logger\n(temp + GPS)", "Driver\nhandover", "Plant gate\nhandover", "Batch\nformed"];
  const bx = 0.7, bw = 2.15, gap = 0.35, by = 1.9, bh = 1.0;
  stages.forEach((label, i) => {
    const x = bx + i * (bw + gap);
    s.addShape("roundRect", { x, y: by, w: bw, h: bh, rectRadius: 0.08, fill: { color: i % 2 === 0 ? FOREST : "3E7A3F" }, line: { type: "none" } });
    s.addText(label, { x, y: by, w: bw, h: bh, align: "center", valign: "middle", fontFace: "Calibri", fontSize: 13, bold: true, color: "FFFFFF", isTextBox: true, margin: 0 });
    if (i < stages.length - 1) {
      s.addText("\u2192", { x: x + bw, y: by, w: gap, h: bh, align: "center", valign: "middle", fontFace: "Arial", fontSize: 20, bold: true, color: DARK, isTextBox: true, margin: 0 });
    }
  });
  s.addText("Each stage writes to its OWN disconnected log (SD card, telematics portal, paper binder, spreadsheet).", {
    x: 0.7, y: 3.15, w: 12, h: 0.4, fontFace: "Calibri", fontSize: 12, italic: true, color: "666666", isTextBox: true,
  });

  s.addShape("roundRect", { x: 0.7, y: 3.85, w: 11.9, h: 1.0, rectRadius: 0.1, fill: { color: CREAM }, line: { color: MOSS, width: 1 } });
  s.addText("Evidence Pack Engine", { x: 1.0, y: 3.85, w: 4, h: 1.0, valign: "middle", fontFace: "Cambria", fontSize: 17, bold: true, color: FOREST, isTextBox: true });
  s.addText("joins all 5 sources per batch  \u2022  denoises + interpolates gaps  \u2022  falls back to route-log GPS  \u2022  flags unrecoverable gaps  \u2022  applies tunable thresholds", {
    x: 5.0, y: 3.85, w: 7.4, h: 1.0, valign: "middle", fontFace: "Calibri", fontSize: 12.5, color: "333333", isTextBox: true,
  });

  const outs = ["dashboard.html\n(human review)", "evidence_packs.json\n(system of record)", "summary.csv\n(spreadsheet)"];
  outs.forEach((label, i) => {
    const x = 0.7 + i * 4.05;
    s.addShape("roundRect", { x, y: 5.35, w: 3.75, h: 0.85, rectRadius: 0.08, fill: { color: "FFFFFF" }, line: { color: FOREST, width: 1.25 } });
    s.addText(label, { x, y: 5.35, w: 3.75, h: 0.85, align: "center", valign: "middle", fontFace: "Calibri", fontSize: 12, bold: true, color: DARK, isTextBox: true, margin: 0 });
  });
  s.addText("Human reviewers open ONLY the flagged batches \u2014 not all of them.", {
    x: 0.7, y: 6.45, w: 11.9, h: 0.4, fontFace: "Calibri", fontSize: 13, bold: true, color: FOREST, isTextBox: true,
  });
}

function missingDataSlide() {
  const s = pres.addSlide();
  sectionHeader(s, "Design Principle", "Stays usable when data is missing, noisy, or late");
  const data = [
    ["Short sensor gap", "Interpolate between real neighbours", "ESTIMATED"],
    ["Gap with no neighbour", "Report as an explicit, unfillable gap", "UNKNOWN"],
    ["Noisy spike", "Local rolling-window despiking (not global)", "OBSERVED"],
    ["Missing GPS", "Fall back to driver-logged stop coordinates", "ESTIMATED"],
    ["Network outage", "Store-and-forward: order by true event time", "MIXED"],
    ["Broken custody link", "Flag for manual paper fallback form", "MANUAL"],
  ];
  let y = 1.85;
  s.addText("Problem", { x: 0.6, y: 1.5, w: 3.4, h: 0.3, fontFace: "Calibri", fontSize: 11, bold: true, color: "888888", charSpacing: 1, isTextBox: true });
  s.addText("Fallback strategy", { x: 4.1, y: 1.5, w: 6.3, h: 0.3, fontFace: "Calibri", fontSize: 11, bold: true, color: "888888", charSpacing: 1, isTextBox: true });
  s.addText("Confidence tag", { x: 10.5, y: 1.5, w: 2.3, h: 0.3, fontFace: "Calibri", fontSize: 11, bold: true, color: "888888", charSpacing: 1, isTextBox: true });
  data.forEach(([prob, strat, tag], i) => {
    if (i % 2 === 0) s.addShape("rect", { x: 0.5, y: y - 0.05, w: 12.3, h: 0.72, fill: { color: CREAM }, line: { type: "none" } });
    s.addText(prob, { x: 0.6, y, w: 3.4, h: 0.62, valign: "middle", fontFace: "Calibri", fontSize: 13, bold: true, color: DARK, isTextBox: true });
    s.addText(strat, { x: 4.1, y, w: 6.3, h: 0.62, valign: "middle", fontFace: "Calibri", fontSize: 12.5, color: "333333", isTextBox: true });
    const tagColor = { ESTIMATED: "0969da", UNKNOWN: "c22222", OBSERVED: FOREST, MIXED: "6639ba", MANUAL: "9a6700" }[tag];
    s.addShape("roundRect", { x: 10.55, y: y + 0.08, w: 1.9, h: 0.42, rectRadius: 0.21, fill: { color: tagColor } });
    s.addText(tag, { x: 10.55, y: y + 0.08, w: 1.9, h: 0.42, align: "center", valign: "middle", fontFace: "Calibri", fontSize: 10.5, bold: true, color: "FFFFFF", isTextBox: true, margin: 0 });
    y += 0.78;
  });
}

function experimentSlide() {
  const s = pres.addSlide();
  sectionHeader(s, "Measured Experiment", "Automated detection beats manual-style baseline");
  s.addText("Cold-chain excursion detection \u2014 30 synthetic batches vs. ground truth", {
    x: 0.6, y: 1.5, w: 8, h: 0.35, fontFace: "Calibri", fontSize: 13, bold: true, color: "555555", isTextBox: true,
  });
  s.addChart(pres.ChartType.bar, [
    { name: "Precision", labels: ["Baseline (manual-style)", "Automated (default)", "Automated (tuned)"], values: [65, 100, 100] },
    { name: "Recall", labels: ["Baseline (manual-style)", "Automated (default)", "Automated (tuned)"], values: [100, 100, 100] },
    { name: "F1", labels: ["Baseline (manual-style)", "Automated (default)", "Automated (tuned)"], values: [79, 100, 100] },
  ], {
    x: 0.6, y: 1.95, w: 7.6, h: 4.6, barDir: "col", chartColors: [MOSS, FOREST, DARK],
    showTitle: false, showValue: true, dataLabelPosition: "outEnd", dataLabelFontSize: 9,
    catAxisLabelFontSize: 10, valAxisLabelFontSize: 10, valAxisMaxVal: 110,
    showLegend: true, legendPos: "b", legendFontSize: 10,
    valGridLine: { color: "E5E5E5", size: 0.75 }, catGridLine: { style: "none" },
  });

  const stats = [
    ["82%", "estimated manual-effort reduction"],
    ["11.0 hrs \u2192 1.9 hrs", "audit assembly time, 30-batch day"],
    ["0 false negatives", "on true excursions, after tuning"],
  ];
  let y = 2.0;
  stats.forEach(([num, label]) => {
    s.addShape("roundRect", { x: 8.6, y, w: 4.1, h: 1.25, rectRadius: 0.1, fill: { color: CREAM }, line: { type: "none" } });
    s.addText(num, { x: 8.8, y: y + 0.08, w: 3.7, h: 0.65, fontFace: "Cambria", fontSize: 26, bold: true, color: FOREST, isTextBox: true, margin: 0 });
    s.addText(label, { x: 8.8, y: y + 0.72, w: 3.7, h: 0.45, fontFace: "Calibri", fontSize: 11, color: "444444", isTextBox: true, margin: 0 });
    y += 1.5;
  });
}

function failureModeSlide() {
  const s = pres.addSlide();
  sectionHeader(s, "Robustness Testing", "Four edge cases, verified end to end");
  const cases = [
    ["Total GPS loss", "PASS", FOREST, "Bridged with route-event stop coordinates, tagged ESTIMATED."],
    ["Network outage", "NEEDS REVIEW", "b8860b", "6 readings recovered late via store-and-forward; 1 lost reading disclosed, not hidden."],
    ["Total sensor failure", "NEEDS REVIEW", "b8860b", "Tail gap correctly reported as unrecoverable, not silently patched."],
    ["Combined worst case", "FAIL (correctly)", "c22222", "Real 30-min excursion detected despite noise, gaps, and delayed sync together."],
  ];
  let y = 1.8;
  cases.forEach(([name, status, color, detail]) => {
    s.addShape("roundRect", { x: 0.6, y, w: 12.1, h: 1.1, rectRadius: 0.08, fill: { color: "FFFFFF" }, line: { color: "E3E5E8", width: 1 } });
    s.addText(name, { x: 0.9, y, w: 3.4, h: 1.1, valign: "middle", fontFace: "Calibri", fontSize: 14.5, bold: true, color: DARK, isTextBox: true });
    s.addShape("roundRect", { x: 4.5, y: y + 0.32, w: 2.0, h: 0.46, rectRadius: 0.23, fill: { color } });
    s.addText(status, { x: 4.5, y: y + 0.32, w: 2.0, h: 0.46, align: "center", valign: "middle", fontFace: "Calibri", fontSize: 11, bold: true, color: "FFFFFF", isTextBox: true, margin: 0 });
    s.addText(detail, { x: 6.8, y, w: 5.7, h: 1.1, valign: "middle", fontFace: "Calibri", fontSize: 12, color: "333333", isTextBox: true });
    y += 1.28;
  });
}

function validationSlide() {
  const s = pres.addSlide();
  sectionHeader(s, "Stakeholder Validation", "What compliance, QA, and ops roles said");
  const cols = [
    { title: "What worked", color: FOREST, items: [
      "\u201cTells me which batches to look at\u201d \u2014 Compliance officer",
      "Confidence tags trusted by gate inspector to treat ESTIMATED PASS more cautiously",
      "Lost vs. delayed sync distinction matches a real, unmet pain point",
    ]},
    { title: "Requested changes", color: "b8860b", items: [
      "Default thresholds flagged 29/30 stress-test batches \u2014 too conservative",
      "Custody-gap wording needs to name the actual fallback process",
      "Wants per-driver / per-route rollups, and a threshold-change audit trail",
    ]},
  ];
  cols.forEach((col, i) => {
    const x = 0.6 + i * 6.2;
    s.addShape("roundRect", { x, y: 1.6, w: 5.9, h: 0.55, rectRadius: 0.08, fill: { color: col.color } });
    s.addText(col.title, { x, y: 1.6, w: 5.9, h: 0.55, align: "center", valign: "middle", fontFace: "Calibri", fontSize: 15, bold: true, color: "FFFFFF", isTextBox: true, margin: 0 });
    let y = 2.35;
    col.items.forEach((item) => {
      s.addShape("ellipse", { x: x + 0.15, y: y + 0.12, w: 0.12, h: 0.12, fill: { color: col.color }, line: { type: "none" } });
      s.addText(item, { x: x + 0.45, y, w: 5.35, h: 0.95, fontFace: "Calibri", fontSize: 13, color: "333333", isTextBox: true });
      y += 1.15;
    });
  });
  s.addText("Net: all three roles agreed the evidence pack reduces assembly time; the main actionable finding was threshold calibration \u2014 exactly what the tuning experiment is built to do.", {
    x: 0.6, y: 6.5, w: 12.1, h: 0.6, fontFace: "Calibri", fontSize: 12.5, italic: true, color: "555555", isTextBox: true,
  });
}

function closingSlide() {
  const s = pres.addSlide();
  s.background = { color: DARK };
  s.addShape("ellipse", { x: -2, y: -2, w: 6, h: 6, fill: { color: FOREST, transparency: 45 }, line: { type: "none" } });
  s.addText("Deliverables in this prototype", { x: 0.8, y: 0.8, w: 10, h: 0.5, fontFace: "Calibri", fontSize: 14, bold: true, color: MOSS, charSpacing: 2, isTextBox: true });
  const items = [
    "Field-workflow map", "Synthetic data generator (5 sources + ground truth)",
    "Functional evidence-pack application (CLI + HTML dashboard)",
    "Measurable experiment with baseline / tuned comparison",
    "Four verified failure-mode / fallback cases",
    "Stakeholder validation summary", "Full technical documentation",
  ];
  let y = 1.45;
  items.forEach((item) => {
    s.addShape("ellipse", { x: 0.8, y: y + 0.1, w: 0.14, h: 0.14, fill: { color: MOSS }, line: { type: "none" } });
    s.addText(item, { x: 1.15, y, w: 10.5, h: 0.5, fontFace: "Calibri", fontSize: 15, color: "FFFFFF", isTextBox: true });
    y += 0.62;
  });
  s.addText("All code, data, and reports are included in the accompanying project archive.", {
    x: 0.8, y: 6.6, w: 11, h: 0.4, fontFace: "Calibri", fontSize: 12, italic: true, color: MOSS, isTextBox: true,
  });
}

titleSlide();
problemSlide();
workflowSlide();
missingDataSlide();
experimentSlide();
failureModeSlide();
validationSlide();
closingSlide();

pres.writeFile({ fileName: "compliance_evidence_pack_presentation.pptx" }).then(() => {
  console.log("done");
});
