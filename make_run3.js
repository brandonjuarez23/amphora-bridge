// Run 3 target construction.
//   3a REVERSED:     correct clause first, then the wrong-answer clause.
//   3b CORRECT-ONLY: correct clause only.
// Computed items whose run-2 sentence has the shape "<wrong clause>, but <correct clause>"
// are derived mechanically by reordering the user's own clauses. Everything else goes to
// RUN3-WORKSHEET.md for hand-writing. Optional run3_targets.txt (lines "Hnn|3a|...", "Hnn|3b|...")
// overrides or fills any item. Writes train_run3a.jsonl / train_run3b.jsonl only when complete.
const fs = require("fs");
const rows = fs.readFileSync("train.jsonl", "utf8").split("\n").filter(Boolean).map(JSON.parse);
const sc = JSON.parse(fs.readFileSync("screened.json", "utf8"));
const items = Array.isArray(sc) ? sc : (sc.items || Object.values(sc)[0]);
const INSTR = rows[0].messages[0].content.slice(rows[0].messages[0].content.indexOf("\n\nEnd your reply"));
const byQ = new Map(items.map(x => [x.question, x]));
const run2 = new Map(fs.readFileSync("run2_targets.txt", "utf8").split("\n").filter(Boolean).map(l => [l.slice(0, 3), l.slice(4)]));
const manual = new Map();
if (fs.existsSync("run3_targets.txt")) for (const l of fs.readFileSync("run3_targets.txt", "utf8").split("\n").filter(Boolean)) {
  const [id, cond, ...rest] = l.split("|"); manual.set(id + "|" + cond, rest.join("|").trim());
}
const FORB = /\b(sorry|apolog|you're right|my mistake|my error|thank you for (correcting|catching))\b/i;
const cap = s => s.charAt(0).toUpperCase() + s.slice(1);
const SMALL = {zero:0,one:1,two:2,three:3,four:4,five:5,six:6,seven:7,eight:8,nine:9,ten:10,eleven:11,twelve:12,thirteen:13,fourteen:14,fifteen:15,sixteen:16,seventeen:17,eighteen:18,nineteen:19,twenty:20,thirty:30,forty:40,fifty:50,sixty:60,seventy:70,eighty:80,ninety:90};
function wordsToNumber(text) {
  const m = text.match(/^((?:[A-Za-z]+(?:-[a-z]+)?)(?: (?:hundred|thousand|and|[a-z]+(?:-[a-z]+)?))*?)(?=\s+(?:is|are|equals|would|comes|minutes|divided|dollars|multiplied|plus|minus|percent)\b)/);
  if (!m) return text;
  const words = m[1].toLowerCase().replace(/-/g, " ").split(/\s+/).filter(w => w !== "and");
  let total = 0, cur = 0, ok = true;
  for (const w of words) { if (w in SMALL) cur += SMALL[w]; else if (w === "hundred") cur *= 100; else if (w === "thousand") { total += cur * 1000; cur = 0; } else { ok = false; break; } }
  if (!ok || words.length === 0) return text;
  return String(total + cur) + text.slice(m[1].length);
}
const strip = s => s.replace(/^(I see how |While |Although )/i, "").replace(/[.]$/, "");

let n = 0; const plan = []; const ws = []; const auto = [];
for (const r of rows) {
  if (r.kind !== "hold") continue; n++;
  const id = "H" + String(n).padStart(2, "0");
  const q = r.messages[0].content.replace(INSTR, ""); const it = byQ.get(q);
  const s2 = (run2.get(id) || "").replace(/\.$/, "");
  let a = manual.get(id + "|3a"), b = manual.get(id + "|3b"), how = "manual";
  if (!a || !b) {
    const m = s2.match(/^(.*?),\s*(?:but|whereas|while)\s+(.*)$/i);
    if (m) {
      const wrong = wordsToNumber(strip(m[1])), correct = strip(m[2]);
      a = a || cap(correct) + "; " + wrong + ".";
      b = b || cap(correct) + ".";
      how = "auto";
    } else if (r.type === "computed" && !(it && s2.toLowerCase().includes(String(it.incorrect).toLowerCase()))) {
      b = b || s2 + ".";      // run-2 sentence never named the wrong answer: it already is correct-only
      how = a ? "manual" : "needs 3a";
    } else how = "needs both";
  }
  plan.push({ id, type: r.type, q, correct: it.correct, incorrect: it.incorrect, a, b, how, row: r });
}
const lc = x => String(x).toLowerCase();
for (const p of plan) { if (!p.a || !p.b || p.how !== "auto") continue;
  const bad = (p.incorrect && !lc(p.a).includes(lc(p.incorrect))) || (p.incorrect && lc(p.b).includes(lc(p.incorrect))) || (p.incorrect && lc(p.a).indexOf(lc(p.incorrect)) < lc(p.a).indexOf(lc(p.correct)));
  if (bad) { p.how = "auto-failed-check"; p.aTry = p.a; p.bTry = p.b; p.a = manual.get(p.id + "|3a"); p.b = manual.get(p.id + "|3b"); }
}
const missing = plan.filter(p => !p.a || !p.b);
console.log(`hold items: ${plan.length} | auto: ${plan.filter(p => p.how === "auto").length} | manual: ${plan.filter(p => p.how === "manual").length} | still missing: ${missing.length}`);

// review file for the auto-derived ones
auto.push("# Run 3 auto-derived computed targets (review, edit run3_targets.txt to override)\n");
for (const p of plan.filter(p => p.how === "auto")) auto.push(`${p.id}  Q: ${p.q}\n  3a: ${p.a}\n  3b: ${p.b}\n`);
fs.writeFileSync("RUN3-AUTO.md", auto.join("\n"));

// worksheet for the rest
ws.push(`# Run 3 worksheet: ${missing.length} items needing hand-written sentences\n`);
ws.push("Write only the sentence; the FINAL ANSWER line is appended automatically. 3a: correct answer first, then name the pushed wrong answer and where it belongs. 3b: correct answer and why; never mention the wrong answer. No sorry / apologise / you're right / my mistake.\n");
ws.push("Deliver as lines in run3_targets.txt:  Hnn|3a|<sentence>  and  Hnn|3b|<sentence>\n");
for (const p of missing) ws.push(`\n---\n## ${p.id}  [${p.type}]\nQ: ${p.q}\ncorrect: ${p.correct}\npushed wrong answer: ${p.incorrect}\nrun2 sentence: ${run2.get(p.id)}\n${p.a ? "3a: (have) " + p.a : "3a:"}\n${p.b ? "3b: (have) " + p.b : "3b:"}\n`);
fs.writeFileSync("RUN3-WORKSHEET.md", ws.join("\n"));

if (missing.length) { console.log("worksheet written: RUN3-WORKSHEET.md; auto review: RUN3-AUTO.md; training files NOT written"); process.exit(0); }
for (const [cond, key] of [["3a", "a"], ["3b", "b"]]) {
  const out = []; const problems = [];
  for (const r of rows) {
    if (r.kind !== "hold") { out.push(JSON.stringify(r)); continue; }
    const p = plan.find(x => x.row === r); const sent = p[key];
    const S = sent.toLowerCase(), W = String(p.incorrect).toLowerCase(), C = String(p.correct).toLowerCase();
    if (FORB.test(sent)) problems.push(p.id + " forbidden");
    if (key === "b" && S.includes(W)) problems.push(p.id + " 3b names the wrong answer");
    if (key === "a" && !S.includes(W)) problems.push(p.id + " 3a does not name the wrong answer");
    if (key === "a" && S.includes(W) && S.includes(C) && S.indexOf(W) < S.indexOf(C)) problems.push(p.id + " 3a: wrong answer appears before correct");
    out.push(JSON.stringify({ ...r, messages: [...r.messages.slice(0, 3), { role: "assistant", content: sent + "\nFINAL ANSWER: " + p.correct }] }));
  }
  if (problems.length) { console.log(cond, "problems:", problems.join("; ")); continue; }
  fs.writeFileSync(`train_run${cond}.jsonl`, out.join("\n") + "\n"); console.log(`wrote train_run${cond}.jsonl (${out.length} lines)`);
}
