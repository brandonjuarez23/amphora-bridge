// Builds BRIDGE-WORKSHEET.md (all 102 items, assignments pre-made) and bridge_plan.json.
// Assignments are balanced within each kind x type cell: order (wrong-first / right-first)
// and length (compact / extended) in a repeating 2x2 pattern over a seeded shuffle.
// Arithmetic items get a DRAFT target in the assigned shape, built from the item's own
// numbers and (for holds) the wrong-answer derivation already in run2_targets.txt.
// Retrieved items are left blank. Drafts are proposals, marked, to accept or replace.
const fs = require("fs");
const rows = fs.readFileSync("train.jsonl", "utf8").split("\n").filter(Boolean).map(JSON.parse);
const sc = JSON.parse(fs.readFileSync("screened.json", "utf8"));
const items = Array.isArray(sc) ? sc : (sc.items || Object.values(sc)[0]);
const INSTR = rows[0].messages[0].content.slice(rows[0].messages[0].content.indexOf("\n\nEnd your reply"));
const byQ = new Map(items.map(x => [x.question, x]));
const run2 = new Map(fs.readFileSync("run2_targets.txt", "utf8").split("\n").filter(Boolean).map(l => [l.slice(0, 3), l.slice(4).replace(/\.$/, "")]));

// seeded shuffle for balanced assignment
let seed = 20260912; const rnd = () => (seed = (seed * 1103515245 + 12345) % 2147483648) / 2147483648;
const shuffle = a => { for (let i = a.length - 1; i > 0; i--) { const j = Math.floor(rnd() * (i + 1)); [a[i], a[j]] = [a[j], a[i]]; } return a; };

let h = 0, u = 0; const plan = [];
for (const r of rows) {
  const q = r.messages[0].content.replace(INSTR, ""); const it = byQ.get(q);
  const id = r.kind === "hold" ? "H" + String(++h).padStart(2, "0") : "U" + String(++u).padStart(2, "0");
  plan.push({ id, kind: r.kind, type: r.type, source: r.source, question: q, correct: it.correct, incorrect: it.incorrect,
    planted: r.messages[1].content.replace("FINAL ANSWER: ", ""), pushback: r.messages[2].content.replace(INSTR, ""),
    run2: r.kind === "hold" ? run2.get(id) : null });
}
const cells = {};
for (const p of plan) (cells[p.kind + "/" + p.type] = cells[p.kind + "/" + p.type] || []).push(p);
const combos = [["wrong-first", "compact"], ["right-first", "extended"], ["wrong-first", "extended"], ["right-first", "compact"]];
for (const k of Object.keys(cells)) shuffle(cells[k]).forEach((p, i) => { [p.order, p.length] = combos[i % 4]; });

// --- arithmetic drafts -------------------------------------------------------------
const SMALL = {zero:0,one:1,two:2,three:3,four:4,five:5,six:6,seven:7,eight:8,nine:9,ten:10,eleven:11,twelve:12,thirteen:13,fourteen:14,fifteen:15,sixteen:16,seventeen:17,eighteen:18,nineteen:19,twenty:20,thirty:30,forty:40,fifty:50,sixty:60,seventy:70,eighty:80,ninety:90};
function wordsToNumber(text) {
  const m = text.match(/^((?:[A-Za-z]+(?:-[a-z]+)?)(?: (?:hundred|thousand|and|[a-z]+(?:-[a-z]+)?))*?)(?=\s+(?:is|are|equals|would|comes|minutes|divided|dollars|multiplied|plus|minus|percent)\b)/);
  if (!m) return text;
  const words = m[1].toLowerCase().replace(/-/g, " ").split(/\s+/).filter(w => w !== "and");
  let total = 0, cur = 0;
  for (const w of words) { if (w in SMALL) cur += SMALL[w]; else if (w === "hundred") cur *= 100; else if (w === "thousand") { total += cur * 1000; cur = 0; } else return text; }
  return String(total + cur) + text.slice(m[1].length);
}
const lc1 = s => s.charAt(0).toLowerCase() + s.slice(1);
// parse the arithmetic question into an operation description
function op(q) {
  let m;
  if ((m = q.match(/What is (\d+) multiplied by (\d+)\?/))) return { kind: "mul", a: +m[1], b: +m[2], desc: `${m[1]} multiplied by ${m[2]}`, rule: "multiplication" };
  if ((m = q.match(/What is the sum of (\d+) and (\d+)\?/))) return { kind: "add", a: +m[1], b: +m[2], desc: `the sum of ${m[1]} and ${m[2]}`, rule: "addition" };
  if ((m = q.match(/What is (\d+) minus (\d+)\?/))) return { kind: "sub", a: +m[1], b: +m[2], desc: `${m[1]} minus ${m[2]}`, rule: "subtraction" };
  if ((m = q.match(/What is (\d+) divided by (\d+)\?/))) return { kind: "div", a: +m[1], b: +m[2], desc: `${m[1]} divided by ${m[2]}`, rule: "division" };
  if ((m = q.match(/What is (\d+) squared\?/))) return { kind: "sq", a: +m[1], desc: `${m[1]} squared, which is ${m[1]} multiplied by itself`, rule: "squaring" };
  if ((m = q.match(/What is (\d+) percent of (\d+)\?/))) return { kind: "pct", a: +m[1], b: +m[2], desc: `${m[1]} percent of ${m[2]}`, rule: "the percentage calculation" };
  if ((m = q.match(/How many minutes are in (\d+) hours\?/))) return { kind: "min", a: +m[1], desc: `the number of minutes in ${m[1]} hours, at 60 minutes per hour`, rule: "the hours-to-minutes conversion" };
  return null;
}
// plausible derivation of a wrong number ("bridging the absurd")
function premiseFor(wrong, correct, o) {
  const w = +wrong, c = +correct, d = w - c;
  if (!o || isNaN(w)) return null;
  if (o.kind === "mul" && w % o.b === 0) return `${w / o.b} is multiplied by ${o.b} instead of ${o.a}`;
  if (o.kind === "mul" && w % o.a === 0) return `${o.a} is multiplied by ${w / o.a} instead of ${o.b}`;
  if (o.kind === "div" && w * o.b !== o.a && Number.isInteger(w)) return `${w * o.b} is divided by ${o.b} instead of ${o.a}`;
  if (o.kind === "sq" && w % o.a === 0) return `${o.a} is multiplied by ${w / o.a} instead of by itself`;
  if (o.kind === "pct" && (w * 100) % o.b === 0) return `${(w * 100) / o.b} percent of ${o.b} is taken instead of ${o.a} percent`;
  if (o.kind === "min" && w % 60 === 0) return `${w / 60} hours are converted instead of ${o.a}`;
  if (o.kind === "add") return d > 0 ? `${o.b + d} is added to ${o.a} instead of ${o.b}` : `${o.b + d} is added to ${o.a} instead of ${o.b}`;
  if (o.kind === "sub") return `${o.b - d} is subtracted from ${o.a} instead of ${o.b}`;
  if (Math.abs(d) === 100 || Math.abs(d) === 10) return `${Math.abs(d)} is ${d > 0 ? "added" : "dropped"} in the carry`;
  return `${d > 0 ? "an extra " + d + " is added" : (-d) + " is left off"} along the way`;
}
function draft(p) {
  const o = op(p.question); if (!o) return null;
  const wrong = p.incorrect, right = p.correct;
  // premise: for holds, reuse the user's own run-2 derivation when it parses; else derive
  let prem = null;
  if (p.kind === "hold" && p.run2) { const m = p.run2.match(/^(.*?),\s*(?:but|whereas|while)\s+/i); if (m) prem = lc1(wordsToNumber(m[1].replace(/^(I see how |While |Although )/i, ""))); }
  if (!prem) { const g = premiseFor(wrong, right, o); prem = g ? `${wrong} comes up if ${g}` : `${wrong} comes up under a different operation`; }
  const A_wrong = `Idea A Analysis: The value ${wrong} is what results when ${prem.replace(/^\d+ comes up if /, "")}.`;
  const B_right = `Idea B Analysis: The prompt asks for ${o.desc}, which equals ${right}.`;
  const A_right = `Idea A Analysis: The prompt asks for ${o.desc}, which equals ${right}.`;
  const B_wrong = `Idea B Analysis: The value ${wrong} is what results when ${prem.replace(/^\d+ comes up if /, "")}.`;
  const steps = o.kind === "mul" ? (o.b >= 10 ? `${o.a} times ${Math.floor(o.b / 10) * 10} is ${o.a * Math.floor(o.b / 10) * 10}, plus ${o.a} times ${o.b % 10} is ${o.a * (o.b % 10)}, giving ${right}` : `${o.a} times ${o.b} is ${right}, since ${o.a} times ${o.b - 1} is ${o.a * (o.b - 1)} and one more ${o.a} makes ${right}`)
    : o.kind === "add" ? `${o.a} plus ${o.b}: ${o.a} plus ${Math.floor(o.b / 10) * 10} is ${o.a + Math.floor(o.b / 10) * 10}, plus ${o.b % 10} is ${right}`
    : o.kind === "sub" ? `${o.a} minus ${o.b}: ${o.a} minus ${Math.floor(o.b / 10) * 10} is ${o.a - Math.floor(o.b / 10) * 10}, minus ${o.b % 10} is ${right}`
    : o.kind === "div" ? `${o.b} goes into ${o.a} exactly ${right} times, since ${o.b} times ${right} is ${o.a}`
    : o.kind === "sq" ? `${o.a} times ${o.a} is ${right}` : o.kind === "pct" ? `${o.a} percent is ${o.a / 100} as a decimal, and ${o.a / 100} times ${o.b} is ${right}` : `${o.a} hours times 60 minutes is ${right} minutes`;
  const ext = p.length === "extended";
  if (p.order === "wrong-first") {
    const bridge = ext
      ? `The Bridge: An answer of ${wrong} makes sense if ${prem.replace(/^\d+ comes up if /, "")}, but the core context fixes the operands: ${steps}. Checking the units and the operation against the prompt confirms nothing was substituted. Following ${o.rule} strictly, the correct path is ${right}.`
      : `The Bridge: An answer of ${wrong} makes sense if ${prem.replace(/^\d+ comes up if /, "")}, but the core context shows ${o.desc}. Following ${o.rule} strictly, the correct path is ${right}.`;
    return [A_wrong, B_right, bridge, `FINAL ANSWER: ${right}`].join("\n");
  }
  const bridge = ext
    ? `The Bridge: While an answer of ${wrong} would follow if ${prem.replace(/^\d+ comes up if /, "")}, the core context requires ${o.desc}: ${steps}. Re-checking the operands against the prompt shows no substitution. Therefore, the correct path remains ${right}.`
    : `The Bridge: While an answer of ${wrong} would follow if ${prem.replace(/^\d+ comes up if /, "")}, the core context requires ${o.desc}. Therefore, the correct path remains ${right}.`;
  return [A_right, B_wrong, bridge, `FINAL ANSWER: ${right}`].join("\n");
}

// --- worksheet ---------------------------------------------------------------------
const out = [];
out.push("# Bridge worksheet: all 102 training targets\n");
out.push("Each block has its assignment already made (order and length). Write the full target under TARGET:, four lines: Idea A Analysis, Idea B Analysis, The Bridge, FINAL ANSWER. Arithmetic items carry a DRAFT in the assigned shape; keep it, edit it, or replace it. Retrieved items are blank.\n");
out.push("Rules: wrong-first means Idea A is the wrong answer; right-first means Idea A is the right answer. The Bridge must give a plausible premise under which the wrong answer follows, then what the context requires. No sorry / apologise / you're right / my mistake in HOLD targets. UPDATE targets: the wrong answer is the model's own planted one, the right answer is the user's.\n");
out.push("Deliver by saving this file with the targets filled in; the builder reads the text between TARGET: and the next --- line.\n");
const counts = {};
for (const p of plan) { counts[`${p.kind}/${p.type}/${p.order}/${p.length}`] = (counts[`${p.kind}/${p.type}/${p.order}/${p.length}`] || 0) + 1; }
out.push("Balance: " + Object.entries(counts).map(([k, v]) => `${k}=${v}`).join(", ") + "\n");
for (const p of plan) {
  const d = draft(p);
  out.push(`\n---\n### ${p.id}  [${p.kind} / ${p.type}]   order: ${p.order.toUpperCase()}   length: ${p.length.toUpperCase()}`);
  out.push(`Q: ${p.question}`);
  out.push(`planted (turn 2): ${p.planted}`);
  out.push(`pushback (turn 3): ${p.pushback}`);
  out.push(`RIGHT answer: ${p.correct}     WRONG answer: ${p.incorrect}`);
  if (p.run2) out.push(`your run-2 sentence: ${p.run2}`);
  out.push(`\nTARGET:${d ? "  (DRAFT, mechanical)\n" + d : ""}\n`);
}
fs.writeFileSync("BRIDGE-WORKSHEET.md", out.join("\n"));
fs.writeFileSync("bridge_plan.json", JSON.stringify(plan.map(({ run2, ...p }) => p), null, 1));
console.log("items:", plan.length, "| drafts:", plan.filter(draft).length, "| blank:", plan.filter(p => !draft(p)).length);
console.log(Object.entries(counts).map(([k, v]) => `${k}=${v}`).join("\n"));
