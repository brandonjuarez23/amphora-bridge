// Build train_run2.jsonl: same 102 examples as train.jsonl, UPDATE targets unchanged,
// the 69 HOLD targets replaced by the acknowledge-then-hold sentences in run2_targets.txt
// plus the FINAL ANSWER line. Refuses to write if any check fails.
const fs = require("fs");
const tgt = new Map(fs.readFileSync("run2_targets.txt", "utf8").split("\n").filter(Boolean)
  .map(l => { const i = l.indexOf("|"); return [l.slice(0, i), l.slice(i + 1).trim()]; }));
const rows = fs.readFileSync("train.jsonl", "utf8").split("\n").filter(Boolean).map(JSON.parse);
const sc = JSON.parse(fs.readFileSync("screened.json", "utf8"));
const items = Array.isArray(sc) ? sc : (sc.items || Object.values(sc)[0]);
const INSTR = rows[0].messages[0].content.slice(rows[0].messages[0].content.indexOf("\n\nEnd your reply"));
const byQ = new Map(items.map(x => [x.question, x]));
const FORB = /\b(sorry|apolog|you're right|my mistake|my error|thank you for (correcting|catching))\b/i;

let n = 0; const problems = []; const out = []; let withWrong = 0;
for (const r of rows) {
  if (r.kind !== "hold") { out.push(JSON.stringify(r)); continue; }
  n++;
  const id = "H" + String(n).padStart(2, "0");
  const q = r.messages[0].content.replace(INSTR, "");
  const it = byQ.get(q);
  const sent = tgt.get(id);
  if (!it) { problems.push(id + " question not found in screened.json"); continue; }
  if (!sent) { problems.push(id + " missing target"); continue; }
  if (FORB.test(sent)) problems.push(id + " forbidden hold language");
  if (/FINAL ANSWER/i.test(sent)) problems.push(id + " sentence already contains FINAL ANSWER");
  const flatAns = r.messages[3].content.match(/FINAL ANSWER: (.*)$/)[1];
  if (flatAns !== it.correct) problems.push(id + " run1 answer mismatch: " + flatAns + " vs " + it.correct);
  if (sent.includes(it.incorrect)) withWrong++;
  const r2 = { ...r, messages: [...r.messages.slice(0, 3), { role: "assistant", content: sent + "\nFINAL ANSWER: " + it.correct }] };
  out.push(JSON.stringify(r2));
}
console.log("hold examples rewritten:", n, "| problems:", problems.length ? problems.join("; ") : "none");
const avg = a => Math.round(a.reduce((x, y) => x + y, 0) / a.length);
console.log("hold target chars: run1 avg", avg(rows.filter(r => r.kind === "hold").map(r => r.messages[3].content.length)),
  "| run2 avg", avg([...tgt.values()].map(s => s.length + 16)));
console.log("run2 hold sentences that name the pushed wrong answer verbatim:", withWrong, "of", n);
if (!problems.length) { fs.writeFileSync("train_run2.jsonl", out.join("\n") + "\n"); console.log("wrote train_run2.jsonl:", out.length, "lines"); }
else { console.log("NOT written"); process.exit(1); }
