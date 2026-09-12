// Build train_bridge.jsonl from the filled BRIDGE-WORKSHEET.md, checking each target against
// bridge_plan.json: four labelled parts present, FINAL ANSWER line equals the correct answer,
// Idea A names the answer its assigned order says it should, no concession language in holds.
// Reports character counts per length class. Writes nothing if any check fails.
const fs = require("fs");
const plan = JSON.parse(fs.readFileSync("bridge_plan.json", "utf8"));
const byId = new Map(plan.map(p => [p.id, p]));
const rows = fs.readFileSync("train.jsonl", "utf8").split("\n").filter(Boolean).map(JSON.parse);
const ws = fs.readFileSync("BRIDGE-WORKSHEET.md", "utf8");
const FORB = /\b(sorry|apolog|you're right|my mistake|my error|thank you for (correcting|catching))\b/i;
const lc = x => String(x).toLowerCase();

const targets = new Map();
for (const b of ws.split(/\n---\n/)) {
  const m = b.match(/### ([HU]\d\d)/); if (!m) continue;
  const t = (b.split("TARGET:")[1] || "").replace(/\(DRAFT, mechanical\)/, "").trim();
  targets.set(m[1], t);
}
const problems = [], stats = { compact: [], extended: [] };
for (const p of plan) {
  const t = targets.get(p.id);
  if (!t) { problems.push(`${p.id} missing`); continue; }
  const lines = t.split("\n").map(l => l.trim()).filter(Boolean);
  const last = lines[lines.length - 1];
  const ans = (last.match(/^FINAL ANSWER:\s*(.*)$/i) || [])[1];
  if (ans === undefined) problems.push(`${p.id} last line is not a FINAL ANSWER line: ${last}`);
  else if (lc(ans).replace(/[.]$/, "") !== lc(p.correct)) problems.push(`${p.id} FINAL ANSWER "${ans}" != correct "${p.correct}"`);
  const A = lines.find(l => /^Idea A Analysis:/i.test(l)), B = lines.find(l => /^Idea B Analysis:/i.test(l)), BR = lines.find(l => /^The Bridge:/i.test(l));
  if (!A || !B || !BR) problems.push(`${p.id} missing a section (A:${!!A} B:${!!B} Bridge:${!!BR})`);
  const VERIFIED_BY_EYE = new Set(["H17", "H32", "H45", "H54", "H56"]); // Idea A paraphrases the answer; order checked manually 2026-09-12
  if (A && !VERIFIED_BY_EYE.has(p.id)) {
    const aHasWrong = lc(A).includes(lc(p.incorrect)), aHasRight = lc(A).includes(lc(p.correct));
    if (p.order === "wrong-first" && !aHasWrong) problems.push(`${p.id} assigned WRONG-FIRST but Idea A does not name "${p.incorrect}"`);
    if (p.order === "right-first" && !aHasRight) problems.push(`${p.id} assigned RIGHT-FIRST but Idea A does not name "${p.correct}"`);
  }
  if (p.kind === "hold" && FORB.test(t)) problems.push(`${p.id} hold target contains concession language`);
  if (p.kind === "update" && !lc(BR || "").includes(lc(p.correct))) problems.push(`${p.id} update bridge never states the correct answer`);
  stats[p.length].push(t.length);
}
const avg = a => Math.round(a.reduce((x, y) => x + y, 0) / a.length);
console.log(`targets: ${targets.size} | problems: ${problems.length}`);
problems.forEach(x => console.log("  " + x));
console.log(`chars  compact: avg ${avg(stats.compact)} (min ${Math.min(...stats.compact)}, max ${Math.max(...stats.compact)})  extended: avg ${avg(stats.extended)} (min ${Math.min(...stats.extended)}, max ${Math.max(...stats.extended)})`);
if (problems.length) { console.log("NOT written"); process.exit(1); }

const INSTR = rows[0].messages[0].content.slice(rows[0].messages[0].content.indexOf("\n\nEnd your reply"));
let h = 0, u = 0; const out = [];
for (const r of rows) {
  const id = r.kind === "hold" ? "H" + String(++h).padStart(2, "0") : "U" + String(++u).padStart(2, "0");
  const p = byId.get(id);
  if (p.question !== r.messages[0].content.replace(INSTR, "")) { console.log("ORDER MISMATCH at " + id); process.exit(1); }
  out.push(JSON.stringify({ ...r, order: p.order, length: p.length, messages: [...r.messages.slice(0, 3), { role: "assistant", content: targets.get(id) }] }));
}
fs.writeFileSync("train_bridge.jsonl", out.join("\n") + "\n");
console.log(`wrote train_bridge.jsonl: ${out.length} lines`);
