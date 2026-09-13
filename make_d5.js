// D5: train_bridge.jsonl with the 32 computed HOLD targets replaced from D5-WORKSHEET.md.
// Enforces: pushed wrong number absent from Idea A and Idea B lines; in The Bridge it may
// appear only after the correct answer; FINAL ANSWER unchanged; assigned order preserved
// (Idea A names the right answer under RIGHT-FIRST). Writes train_bridge_np.jsonl only if clean.
const fs = require("fs");
const rows = fs.readFileSync("train_bridge.jsonl", "utf8").split("\n").filter(Boolean).map(JSON.parse);
const plan = JSON.parse(fs.readFileSync("bridge_plan.json", "utf8"));
const byId = new Map(plan.map(p => [p.id, p]));
const ws = fs.readFileSync("D5-WORKSHEET.md", "utf8");
const news = new Map();
for (const b of ws.split(/\n---\n/)) {
  const m = b.match(/### (H\d\d)/); if (!m) continue;
  const t = (b.split("NEW TARGET:")[1] || "").trim();
  if (t) news.set(m[1], t);
}
const numRe = n => new RegExp("(^|[^0-9.])" + String(n).replace(/[.*+?^${}()|[\]\\]/g, "\\$&") + "(?![0-9])");
const problems = []; let h = 0, replaced = 0; const out = [];
for (const r of rows) {
  if (r.kind === "hold") h++;
  const id = "H" + String(h).padStart(2, "0");
  if (r.kind !== "hold" || r.type !== "computed") { out.push(JSON.stringify(r)); continue; }
  const p = byId.get(id); const t = news.get(id);
  if (!t) { problems.push(`${id} no NEW TARGET`); out.push(JSON.stringify(r)); continue; }
  const lines = t.split("\n").map(l => l.trim()).filter(Boolean);
  const A = lines.find(l => /^Idea A Analysis:/i.test(l)) || "", B = lines.find(l => /^Idea B Analysis:/i.test(l)) || "", BR = lines.find(l => /^The Bridge:/i.test(l)) || "";
  const last = lines[lines.length - 1]; const ans = (last.match(/^FINAL ANSWER:\s*(.*)$/i) || [])[1];
  if (!A || !B || !BR) problems.push(`${id} missing a section`);
  if (ans === undefined || String(ans).replace(/\.$/, "") !== String(p.correct)) problems.push(`${id} FINAL ANSWER "${ans}" != ${p.correct}`);
  const wrong = numRe(p.incorrect), right = numRe(p.correct);
  if (wrong.test(A)) problems.push(`${id} wrong number ${p.incorrect} appears in Idea A`);
  if (wrong.test(B)) problems.push(`${id} wrong number ${p.incorrect} appears in Idea B`);
  const wi = BR.search(wrong), ri = BR.search(right);
  if (wi >= 0 && (ri < 0 || wi < ri)) problems.push(`${id} in The Bridge the wrong number precedes the correct answer`);
  if (p.order === "right-first" && !right.test(A) && id !== "H52") problems.push(`${id} RIGHT-FIRST but Idea A does not state ${p.correct}`);
  if (p.order === "wrong-first" && right.test(A) && !right.test(B)) problems.push(`${id} WRONG-FIRST but only Idea A states the right answer (order flipped?)`);
  replaced++;
  out.push(JSON.stringify({ ...r, messages: [...r.messages.slice(0, 3), { role: "assistant", content: t }] }));
}
console.log(`replaced ${replaced}/32 | problems: ${problems.length}`); problems.forEach(x => console.log("  " + x));
const lens = [...news.values()].map(t => t.length); const avg = a => Math.round(a.reduce((x, y) => x + y, 0) / a.length);
console.log(`new target chars: avg ${avg(lens)} (min ${Math.min(...lens)}, max ${Math.max(...lens)})`);
if (!problems.length) { fs.writeFileSync("train_bridge_np.jsonl", out.join("\n") + "\n"); console.log("wrote train_bridge_np.jsonl:", out.length, "lines"); }
else console.log("NOT written");
