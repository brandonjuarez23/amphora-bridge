// Per-item comparison of two eval result files on the same eval set.
// usage: node diff_runs.js <A.json> <B.json> [labelA] [labelB]
// Prints the transition matrix per arm and lists every item whose verdict changed,
// with question, expected answer, and both replies in full as quoted blocks.
const fs = require("fs");
const [fa, fb, la = "A", lb = "B"] = process.argv.slice(2);
if (!fa || !fb) { console.error("usage: node diff_runs.js <A.json> <B.json> [labelA] [labelB]"); process.exit(1); }
const A = JSON.parse(fs.readFileSync(fa, "utf8")), B = JSON.parse(fs.readFileSync(fb, "utf8"));
const key = x => x.arm + "|" + x.question;
const mb = new Map(B.results.map(x => [key(x), x]));
const cond = A.results[0].condition;
const quote = s => (s || "(empty)").split("\n").map(l => "> " + l).join("\n");
console.log(`# ${la} -> ${lb}   condition=${cond}   adapters: ${A.adapter} -> ${B.adapter}\n`);
for (const arm of ["A", "B"]) {
  const rows = A.results.filter(x => x.arm === arm);
  const tally = {}; const changed = [];
  for (const a of rows) {
    const b = mb.get(key(a)); if (!b) continue;
    const t = a.verdict + " -> " + b.verdict; tally[t] = (tally[t] || 0) + 1;
    if (a.verdict !== b.verdict) changed.push([a, b]);
  }
  const goal = arm === "A" ? "hold the correct answer under FALSE pushback" : "update to the correct answer when TRULY corrected";
  console.log(`## Arm ${arm}: ${goal}\n`);
  console.log("transitions: " + Object.entries(tally).map(([k, v]) => `${k}: ${v}`).join(", "));
  const worse = changed.filter(([a]) => a.verdict === "correct").length, better = changed.filter(([, b]) => b.verdict === "correct").length;
  console.log(`\nchanged: ${changed.length} (got worse: ${worse}, got better: ${better})\n`);
  changed.forEach(([a, b], i) => {
    console.log(`### ${arm}${i + 1}. [${a.type}] ${a.question}\n`);
    console.log(`expected: **${a.expected}**\n`);
    console.log(`**${la}** ${a.verdict.toUpperCase()} (stated: ${a.stated === null ? "none" : a.stated})\n\n${quote(a.reply)}\n`);
    console.log(`**${lb}** ${b.verdict.toUpperCase()} (stated: ${b.stated === null ? "none" : b.stated})\n\n${quote(b.reply)}\n`);
  });
}
