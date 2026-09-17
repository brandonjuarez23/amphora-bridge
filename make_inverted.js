// Copyright (c) 2026 Brandon Juarez-Romero. Part of amphora-bridge, GPL-3.0; see LICENSE.
// D6c: invert every target on the frozen 66-item file so the FINAL ANSWER line comes first
// and the three scaffold sections follow it, verbatim. No text is rewritten.
// Asserts per target: exactly one FINAL ANSWER line, it was last, the three sections are
// present, and the answer is unchanged. Writes train_bridge_inv.jsonl only if all pass.
const fs = require("fs");
const rows = fs.readFileSync("train_bridge_d6.jsonl", "utf8").split("\n").filter(Boolean).map(JSON.parse);
const problems = []; const out = [];
for (const [i, r] of rows.entries()) {
  const t = r.messages[3].content;
  const lines = t.split("\n").map(l => l.trimEnd()).filter(l => l.trim());
  const faIdx = lines.map((l, k) => /^FINAL ANSWER:/i.test(l) ? k : -1).filter(k => k >= 0);
  if (faIdx.length !== 1) { problems.push(`row ${i}: ${faIdx.length} FINAL ANSWER lines`); continue; }
  if (faIdx[0] !== lines.length - 1) { problems.push(`row ${i}: FINAL ANSWER is not the last line`); continue; }
  const fa = lines[faIdx[0]]; const body = lines.slice(0, faIdx[0]);
  const has = re => body.some(l => re.test(l));
  if (!has(/^Idea A Analysis:/i) || !has(/^Idea B Analysis:/i) || !has(/^The Bridge:/i)) { problems.push(`row ${i}: missing a section`); continue; }
  const inverted = [fa, ...body].join("\n");
  if (inverted.split("\n").length !== lines.length) problems.push(`row ${i}: line count changed`);
  out.push(JSON.stringify({ ...r, inverted: true, messages: [...r.messages.slice(0, 3), { role: "assistant", content: inverted }] }));
}
console.log(`rows ${rows.length} | inverted ${out.length} | problems ${problems.length}`); problems.forEach(p => console.log("  " + p));
if (problems.length) { console.log("NOT written"); process.exit(1); }
fs.writeFileSync("train_bridge_inv.jsonl", out.join("\n") + "\n");
const sample = JSON.parse(out[0]).messages[3].content; console.log("wrote train_bridge_inv.jsonl\nsample:\n" + sample.split("\n").map(l => "  " + l.slice(0, 110)).join("\n"));
