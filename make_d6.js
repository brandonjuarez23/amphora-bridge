// D3: 33 hold + 33 update from train_bridge.jsonl, holds subsampled round-robin across
// type/order/length cells with a fixed seed. Output train_bridge_d6.jsonl.
const fs=require("fs");
const rows=fs.readFileSync("train_bridge_np.jsonl","utf8").split("\n").filter(Boolean).map(JSON.parse);
const holds=rows.filter(r=>r.kind==="hold"), ups=rows.filter(r=>r.kind==="update");
let seed=33; const rnd=()=> (seed=(seed*1103515245+12345)%2147483648)/2147483648;
const cellOf=r=>r.type+"/"+r.order+"/"+r.length;
const cells={}; holds.forEach(r=>(cells[cellOf(r)]=cells[cellOf(r)]||[]).push(r));
for (const k of Object.keys(cells)) cells[k].sort(()=>rnd()-0.5);
const keep=[]; const keys=Object.keys(cells); let i=0;
while (keep.length<33) { const k=keys[i%keys.length]; if (cells[k].length) keep.push(cells[k].pop()); i++; }
const out=[...keep, ...ups].sort(()=>rnd()-0.5);
fs.writeFileSync("train_bridge_d6.jsonl", out.map(r=>JSON.stringify(r)).join("\n")+"\n");
console.log("wrote train_bridge_d6.jsonl:", out.length, "lines");
