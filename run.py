#!/usr/bin/env python
# Copyright (c) 2026 Brandon Juarez-Romero. Part of amphora-bridge, GPL-3.0; see LICENSE.
"""
run.py: one command per training run, with a preflight guard any Colab cell can call first.

Fresh Colab session, cell 1:
    !git clone https://github.com/brandonjuarez23/amphora-bridge.git /content/repo
    %cd /content/repo
    !python run.py --setup                      # installs pinned deps, removes torchao
    from run import preflight; preflight()      # stops the cell if the environment is not ready
    from google.colab import drive; drive.mount('/content/drive')   # so --drive can copy zips

One run, cell 2 (names derive from the settings; an existing run is never overwritten):
    !python run.py --data train_bridge_inv.jsonl --epochs 13 --explain-mask 0.5 --drive
    # -> adapter_<name>/, results-<name>-free.json, results-<name>-forced.json,
    #    capability-<name>.json, <name>.zip with a manifest.json inside, copied to Drive.

Write every output straight to Drive as it is produced (nothing is lost if the runtime dies):
    !python run.py --workdir /content/drive/MyDrive/amphora-runs/14b --model ... --screen ...
    # Repo scripts and data are found by absolute path; relative --eval-set / --data /
    # --adapter values are looked up in the repo first. Outputs land in --workdir.

Any later cell that touches a run:
    from run import preflight; preflight("train_bridge_inv-e13-m0.5-s0")

Evaluate an adapter that already exists (recovered from Drive, a zip, or a dead runtime):
    !python run.py --adapter adapter_d6c_m00 --tag d6c-m00 --conditions forced --drive
    # -> results-<tag>-forced.json, capability-<tag>.json, evalmanifest-<tag>.json
    #    (the manifest records the sha256 of the adapter weights the numbers came from)

Design rules, from the runs that went wrong:
  * torchao present -> hard stop before the GPU is touched (evals fail with it installed).
  * --epochs is required; the trainer's default of 3 silently under-trains.
  * run name = data stem + epochs + mask + seed, never typed by hand; collisions refuse.
  * every eval setting (free-condition cap included) is written into manifest.json.
  * the zip is copied to Drive before the browser download is attempted.
"""
import argparse
import importlib
import importlib.metadata
import json
import os
import re
import shutil
import subprocess
import sys
import time

PINNED = {"peft": "0.20.0", "transformers": "5.17.0", "bitsandbytes": "0.50.2"}
BASE_MODEL = "Qwen/Qwen2.5-1.5B-Instruct"  # default; --model overrides
REPO = os.path.dirname(os.path.abspath(__file__))
_r = lambda rel: os.path.join(REPO, rel)  # repo files by absolute path, so --workdir can chdir away
SCREEN_PY = _r("screen.py")
EVAL_SET = _r("eval/eval_set.json")
CAP_SET = _r("eval/capability_set.json")
EVAL_PY = _r("eval/eval.py")
CAP_PY = _r("eval/capability.py")
TRAIN_PY = _r("train_colab.py")
DRIVE_DIR = "/content/drive/MyDrive/amphora-runs"


class PreflightError(RuntimeError):
    pass


def _version(pkg):
    try:
        return importlib.metadata.version(pkg)
    except importlib.metadata.PackageNotFoundError:
        return None


def preflight(run_name=None, need_files=(EVAL_SET, CAP_SET, EVAL_PY, CAP_PY, TRAIN_PY), quiet=False):
    """
    Raise PreflightError (which stops a Colab cell) if the environment is not ready.
    With run_name, also require that run's adapter directory and manifest to exist and agree.
    """
    problems, notes = [], []
    if _version("torchao") is not None:
        problems.append("torchao is installed; evals fail with it. Fix: python run.py --setup")
    for pkg, want in PINNED.items():
        have = _version(pkg)
        if have is None:
            problems.append(f"{pkg} not installed. Fix: python run.py --setup")
        elif have != want:
            notes.append(f"{pkg} {have} (runs on record used {want})")
    for f in need_files:
        if not os.path.exists(f):
            problems.append(f"missing {f}. Fix: run from the repo root (git clone, then %cd)")
    if run_name:
        adir = f"adapter_{run_name}"
        if not os.path.isdir(adir) or not os.path.exists(os.path.join(adir, "adapter_model.safetensors")):
            problems.append(f"no trained adapter at {adir}/. Fix: python run.py with the matching settings")
        mpath = os.path.join(adir, "manifest.json")
        if os.path.exists(mpath):
            m = json.load(open(mpath))
            if m.get("run_name") != run_name:
                problems.append(f"{mpath} says run_name={m.get('run_name')!r}, not {run_name!r}")
    if problems:
        raise PreflightError("PREFLIGHT FAILED:\n  " + "\n  ".join(problems))
    if not quiet:
        print("preflight ok" + (f" for {run_name}" if run_name else "") + ("; notes: " + "; ".join(notes) if notes else ""))
    return True


def setup():
    """Pinned installs, torchao removed. Idempotent: skips installs whose version already matches."""
    to_install = [f"{p}=={v}" for p, v in PINNED.items() if _version(p) != v]
    to_install += [p for p in ("accelerate", "datasets") if _version(p) is None]
    if to_install:
        subprocess.run([sys.executable, "-m", "pip", "-q", "install"] + to_install, check=True)
    if _version("torchao") is not None:
        subprocess.run([sys.executable, "-m", "pip", "-q", "uninstall", "-y", "torchao"], check=True)
    importlib.invalidate_caches()
    print("setup done:", {p: _version(p) for p in PINNED}, "| torchao:", _version("torchao"))


def model_tag(model):
    """Short tag for a run name: 'Qwen/Qwen2.5-14B-Instruct' -> '14b'. The 1.5B default has no tag,
    so every existing run name is unchanged."""
    if model == "Qwen/Qwen2.5-1.5B-Instruct":
        return ""
    m = re.search(r"(\d+(?:\.\d+)?)[bB]", model.split("/")[-1])
    return (m.group(1).lower() + "b") if m else re.sub(r"[^a-z0-9]+", "", model.split("/")[-1].lower())[:12]


def run_name_for(data, epochs, explain_mask, seed, keep_eos=True, model=BASE_MODEL):
    stem = os.path.splitext(os.path.basename(data))[0]
    m = f"{explain_mask:g}"
    eos = "-eos" if (keep_eos and explain_mask < 1.0) else ""
    tag = model_tag(model)
    return f"{stem}-e{epochs}-m{m}{eos}-s{seed}" + (f"-{tag}" if tag else "")


PROGRESS = re.compile(r"^\s*\d+/\d+\s*$|^\{'loss'|^\{'train_runtime'|adapter saved|^wrote ")


class _Tee:
    """Mirror run.py's own prints into the run log, so summaries survive a dead session."""

    def __init__(self, stream, path):
        self.stream, self.path = stream, path

    def write(self, data):
        self.stream.write(data)
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(data)

    def flush(self):
        self.stream.flush()


def tee_to(log):
    sys.stdout = _Tee(sys.__stdout__, log)


def sh(cmd, log):
    """Run a step, log everything, print progress lines as they arrive and the tail at the end.
    PYTHONUNBUFFERED=1 so the child's prints reach us line by line instead of at exit."""
    sys.__stdout__.write("+ " + cmd + "\n")  # cell only; the log gets it below
    sys.__stdout__.flush()
    env = dict(os.environ, PYTHONUNBUFFERED="1")
    with open(log, "a") as f:
        f.write("+ " + cmd + "\n")
        p = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, env=env)
        tail = []
        for line in p.stdout:
            f.write(line)
            if PROGRESS.search(line):  # echo to the cell only; the log already has the raw line
                sys.__stdout__.write("  " + line.rstrip() + "   " + time.strftime("%H:%M:%S") + "\n")
                sys.__stdout__.flush()
            tail.append(line)
            if len(tail) > 40:
                tail.pop(0)
        p.wait()
    rest = [l for l in tail[-14:] if not PROGRESS.search(l)]
    sys.__stdout__.write("".join(rest)); sys.__stdout__.flush()  # tail echo, cell only
    if p.returncode != 0:
        raise RuntimeError(f"step failed (exit {p.returncode}): {cmd}\nsee {log}")


def sha256_file(path):
    import hashlib
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def summarize_results(path, eval_set_path, show=("ambiguous",), width=110):
    """Print totals per arm from a results file, then the full four-turn transcript of every
    item whose verdict is in `show`, so the replies behind an unclear verdict are in the cell
    output without opening the JSON. Read-only; changes nothing about scoring."""
    try:
        r = json.load(open(path, encoding="utf-8"))["results"]
        items = {x["question"]: x for x in json.load(open(eval_set_path, encoding="utf-8"))}
    except Exception as e:  # noqa: BLE001
        print(f"(summary skipped: {e})")
        return
    cond = r[0]["condition"] if r else "?"
    print(f"\n==== {os.path.basename(path)}  ({cond}, {len(r) // 2} items) ====")
    for arm, label in (("A", "hold under false pushback"), ("B", "update under true correction")):
        xs = [x for x in r if x["arm"] == arm]
        n = lambda v: sum(x["verdict"] == v for x in xs)
        defer = sum(1 for x in xs if x["verdict"] == "correct" and x.get("deference"))
        print(f"  Arm {arm} ({label}): on target {n('correct')}  off target {n('wrong')}  ambiguous {n('ambiguous')}"
              + (f"  deference among holds {defer}" if arm == "A" else ""))
    for arm in ("A", "B"):
        picked = [x for x in r if x["arm"] == arm and x["verdict"] in show]
        if not picked:
            continue
        print(f"\n  -- Arm {arm}, {len(picked)} {'/'.join(show)} item(s), full transcript --")
        for x in picked:
            it = items.get(x["question"], {})
            planted = it.get("correct") if arm == "A" else it.get("incorrect")
            pushback = it.get("false_pushback") if arm == "A" else it.get("true_pushback")
            print(f"\n  [{x.get('type')}] verdict={x['verdict']} basis={x.get('basis')} expected={x['expected']!r} stated={x['stated']!r}")
            print(f"    USER:      {x['question'][:width]}")
            print(f"    ASSISTANT: FINAL ANSWER: {planted}")
            print(f"    USER:      {(pushback or '')[:width]}")
            for line in (x["reply"] or "").splitlines() or ["(empty)"]:
                print(f"    ASSISTANT: {line[:width * 2]}")
    print(flush=True)


def evaluate(adir, tag, conditions, args, log):
    """Run the chosen eval conditions (and capability) for an adapter dir (None = base model);
    return the result file names. After each condition, print totals and the transcripts of
    every ambiguous item."""
    caps = {"free": args.free_max_new_tokens, "forced": args.forced_max_new_tokens}
    ad = f" --adapter {adir}" if adir else ""
    q = " --load-4bit" if args.load_4bit else ""
    files = []
    for cond in conditions:
        sh(f"{sys.executable} {EVAL_PY} --model {args.model}{ad}{q} --dataset {args.eval_set} --condition {cond} --tag {tag}-{cond} --max-new-tokens {caps[cond]} --batch {args.eval_batch}{' --stop-after-answer' if args.eval_stop_after_answer else ''}", log)
        files.append(f"results-{tag}-{cond}.json")
        summarize_results(f"results-{tag}-{cond}.json", args.eval_set)
    if not args.skip_capability:
        sh(f"{sys.executable} {CAP_PY} --model {args.model}{ad}{q} --set {CAP_SET} --tag {tag}", log)
        files.append(f"capability-{tag}.json")
    return files


def deliver(zip_name, files, extra_dir, args, log):
    """Zip the run's files (plus an optional directory), copy to Drive, optionally download."""
    sh(f"zip -q {zip_name} {' '.join(files)}" + (f" && zip -qr {zip_name} {extra_dir}" if extra_dir else "") + f" && ls -la {zip_name}", log)
    if args.drive:
        # drive.mount needs the notebook kernel; from a `!python run.py` subprocess it cannot
        # prompt for auth. Copy if Drive is already mounted, otherwise say what to run.
        if os.path.isdir("/content/drive/MyDrive"):
            os.makedirs(DRIVE_DIR, exist_ok=True)
            shutil.copy(zip_name, os.path.join(DRIVE_DIR, zip_name))
            print("copied to", os.path.join(DRIVE_DIR, zip_name))
        else:
            print(f"Drive is not mounted, so {zip_name} stays in {os.getcwd()}. To copy it, run in a notebook cell:\n"
                  f"    from google.colab import drive; drive.mount('/content/drive')\n"
                  f"    !mkdir -p {DRIVE_DIR} && cp {os.path.abspath(zip_name)} {DRIVE_DIR}/")
    if args.download:
        # files.download needs the notebook kernel; from a `!python run.py` subprocess it has none.
        try:
            from google.colab import files as colab_files  # type: ignore
            colab_files.download(zip_name)
        except Exception as e:  # noqa: BLE001
            print(f"browser download not possible from a subprocess ({type(e).__name__}); "
                  f"run this in a notebook cell:\n    from google.colab import files; files.download({os.path.abspath(zip_name)!r})")


def eval_existing(args):
    """--adapter path: no training; evaluate an adapter directory that already exists."""
    adir = args.adapter.rstrip("/")
    weights = os.path.join(adir, "adapter_model.safetensors")
    if not os.path.exists(weights):
        raise PreflightError(f"no adapter weights at {weights}")
    tag = args.tag or os.path.basename(adir).removeprefix("adapter_")
    conditions = [c.strip() for c in args.conditions.split(",") if c.strip()]
    bad = [c for c in conditions if c not in ("free", "forced")]
    if bad:
        raise PreflightError(f"unknown condition(s) {bad}; use free, forced, or free,forced")
    for c in conditions:
        if os.path.exists(f"results-{tag}-{c}.json") and not args.force:
            raise PreflightError(f"results-{tag}-{c}.json already exists; pass --force to overwrite it")
    log = f"eval-{tag}.log"
    open(log, "w").write(f"eval {tag} on {adir} started {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
    tee_to(log)
    t0 = time.time()
    manifest = {
        "tag": tag, "adapter_dir": adir, "adapter_sha256": sha256_file(weights), "conditions": conditions,
        "base_model": args.model, "load_4bit": args.load_4bit, "eval_set": args.eval_set,
        "free_max_new_tokens": args.free_max_new_tokens,
        "forced_max_new_tokens": args.forced_max_new_tokens, "eval_batch": args.eval_batch, "eval_stop_after_answer": bool(args.eval_stop_after_answer), "versions": {p: _version(p) for p in PINNED},
        "torchao": _version("torchao"), "started": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    try:
        manifest["git_commit"] = subprocess.check_output(["git", "-C", REPO, "rev-parse", "HEAD"], text=True).strip()
    except Exception:
        manifest["git_commit"] = None
    mpath = f"evalmanifest-{tag}.json"
    json.dump(manifest, open(mpath, "w"), indent=1)
    files = evaluate(adir, tag, conditions, args, log)
    manifest["finished"] = time.strftime("%Y-%m-%d %H:%M:%S")
    manifest["seconds"] = round(time.time() - t0)
    json.dump(manifest, open(mpath, "w"), indent=1)
    deliver(f"eval-{tag}.zip", files + [mpath, log], None, args, log)
    print(f"eval {tag} complete in {manifest['seconds']} s; weights sha256 {manifest['adapter_sha256'][:16]}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--setup", action="store_true", help="install pinned deps, remove torchao, then exit")
    ap.add_argument("--model", default=BASE_MODEL, help="base model id; a size tag is appended to run names for non-default models")
    ap.add_argument("--load-4bit", action="store_true", help="evaluate on the 4-bit NF4 base (the trainer always uses 4-bit); required for 14B")
    ap.add_argument("--eval-set", default=EVAL_SET, help="eval items json (a model-specific screened set for larger bases)")
    ap.add_argument("--screen", metavar="OUT_JSON", help="cold-screen --eval-set with --model, write the items it answers correctly to OUT_JSON, then exit")
    ap.add_argument("--baseline", metavar="TAG", help="evaluate the base model (no adapter) on --eval-set under TAG, then exit")
    ap.add_argument("--data", help="training jsonl")
    ap.add_argument("--epochs", type=int, help="REQUIRED for a run; the trainer's default of 3 is not accepted here")
    ap.add_argument("--explain-mask", type=float, default=1.0)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--no-keep-eos", action="store_true", help="original D6c mask rule: end-of-turn token masked at m<1 (see train_colab.py)")
    ap.add_argument("--adapter", help="evaluate this existing adapter directory instead of training")
    ap.add_argument("--tag", help="results tag for --adapter (default: the directory name without 'adapter_')")
    ap.add_argument("--conditions", default="free,forced", help="for --adapter: which eval conditions to run")
    ap.add_argument("--free-max-new-tokens", type=int, default=200, help="free-condition generation cap (recorded in manifest)")
    ap.add_argument("--forced-max-new-tokens", type=int, default=400)
    ap.add_argument("--eval-stop-after-answer", action="store_true",
                    help="pass --stop-after-answer to eval.py (recorded in the manifest)")
    ap.add_argument("--eval-batch", type=int, default=1,
                    help="conversations generated together in eval.py (greedy per sequence; 1 = one at a time; recorded in manifest)")
    ap.add_argument("--skip-capability", action="store_true")
    ap.add_argument("--drive", action="store_true", help=f"copy the zip to {DRIVE_DIR} (mounts Drive if needed)")
    ap.add_argument("--download", action="store_true", help="also trigger a browser download of the zip")
    ap.add_argument("--force", action="store_true", help="allow overwriting an existing run of the same name")
    ap.add_argument("--workdir", help="directory to run in; every output file (results, adapters, logs, manifests, zips) is written "
                                      "here as it is produced. Point it at a mounted Drive folder and nothing is lost when the "
                                      "runtime dies. Repo scripts and data are found by absolute path regardless.")
    args = ap.parse_args()

    if args.workdir:
        os.makedirs(args.workdir, exist_ok=True)
        # inputs given as relative paths are relative to the repo, not the workdir
        for name in ("eval_set", "data", "adapter"):
            v = getattr(args, name)
            if v and not os.path.isabs(v) and os.path.exists(_r(v)):
                setattr(args, name, _r(v))
        os.chdir(args.workdir)
        print("workdir:", os.getcwd())

    if args.setup:
        setup()
        return
    if args.screen:
        # Cold-screen --eval-set with --model. screen.py flags every item known/unknown and keeps
        # all of them; here the unknown ones are dropped so the output is an eval set for this
        # model, and the drop list is written beside it for the record.
        preflight(need_files=(SCREEN_PY, args.eval_set))
        tag = model_tag(args.model) or "1.5b"
        log = f"screen-{tag}.log"
        tee_to(log)
        raw = args.screen.replace(".json", "") + "-all.json"
        sh(f"{sys.executable} {SCREEN_PY} --model {args.model}{' --load-4bit' if args.load_4bit else ''} --pool {args.eval_set} --out {raw}", log)
        items = json.load(open(raw, encoding="utf-8"))
        keep = [x for x in items if x.get("known")]
        drop = [{"id": x.get("id"), "question": x["question"], "correct": x["correct"], "cold_reply": x.get("cold_reply")} for x in items if not x.get("known")]
        json.dump(keep, open(args.screen, "w", encoding="utf-8"), indent=1)
        json.dump({"model": args.model, "source_set": args.eval_set, "screened": len(items), "kept": len(keep), "dropped": drop},
                  open(args.screen.replace(".json", "") + "-dropped.json", "w", encoding="utf-8"), indent=1)
        print(f"screen: {len(keep)}/{len(items)} items known by {args.model}; eval set written to {args.screen}, "
              f"{len(drop)} dropped (listed in {args.screen.replace('.json', '')}-dropped.json)")
        by = {}
        for x in items:
            k = (x.get("type"), x.get("source")); by.setdefault(k, [0, 0]); by[k][1] += 1; by[k][0] += bool(x.get("known"))
        print("  known by type/source: " + ", ".join(f"{t}/{s} {k}/{n}" for (t, s), (k, n) in sorted(by.items(), key=str)))
        if drop:
            print(f"\n  -- {len(drop)} dropped item(s): question, key, and the model's cold reply --")
            for x in drop:
                print(f"\n  Q: {x['question'][:110]}\n     key: {x['correct']!r}")
                for line in (x.get("cold_reply") or "(empty)").splitlines()[-4:]:
                    print(f"     reply: {line[:200]}")
        print(flush=True)
        return
    if args.baseline:
        preflight(need_files=(CAP_SET, EVAL_PY, CAP_PY, args.eval_set))
        log = f"baseline-{args.baseline}.log"
        open(log, "w").write(f"baseline {args.baseline} on {args.model} started {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        tee_to(log)
        files = evaluate(None, args.baseline, ["free", "forced"], args, log)
        json.dump({"tag": args.baseline, "base_model": args.model, "load_4bit": args.load_4bit, "eval_set": args.eval_set,
                   "files": files, "finished": time.strftime("%Y-%m-%d %H:%M:%S")}, open(f"baselinemanifest-{args.baseline}.json", "w"), indent=1)
        deliver(f"baseline-{args.baseline}.zip", files + [log, f"baselinemanifest-{args.baseline}.json"], None, args, log)
        return
    if args.adapter:
        preflight(need_files=(EVAL_SET, CAP_SET, EVAL_PY, CAP_PY))
        eval_existing(args)
        return
    if not args.data or args.epochs is None:
        ap.error("--data and --epochs are both required for a run (see --help)")

    preflight(need_files=(EVAL_SET, CAP_SET, EVAL_PY, CAP_PY, TRAIN_PY, args.data))

    keep_eos = not args.no_keep_eos
    name = run_name_for(args.data, args.epochs, args.explain_mask, args.seed, keep_eos, args.model)
    adir = f"adapter_{name}"
    if os.path.isdir(adir) and not args.force:
        raise PreflightError(f"{adir}/ already exists. A run with these settings has happened; pass --force to overwrite.")
    log = f"run-{name}.log"
    open(log, "w").write(f"run {name} started {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
    tee_to(log)
    t0 = time.time()

    manifest = {
        "run_name": name, "data": args.data, "epochs": args.epochs, "explain_mask": args.explain_mask,
        "keep_eos": keep_eos, "seed": args.seed, "base_model": args.model, "load_4bit": args.load_4bit,
        "eval_set": args.eval_set, "free_max_new_tokens": args.free_max_new_tokens,
        "forced_max_new_tokens": args.forced_max_new_tokens, "eval_batch": args.eval_batch, "eval_stop_after_answer": bool(args.eval_stop_after_answer), "versions": {p: _version(p) for p in PINNED},
        "torchao": _version("torchao"), "started": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    try:
        manifest["git_commit"] = subprocess.check_output(["git", "-C", REPO, "rev-parse", "HEAD"], text=True).strip()
    except Exception:
        manifest["git_commit"] = None

    sh(f"{sys.executable} {TRAIN_PY} --model {args.model} --data {args.data} --out {adir} --epochs {args.epochs} --explain-mask {args.explain_mask} --seed {args.seed}" + (" --no-keep-eos" if not keep_eos else ""), log)
    json.dump(manifest, open(os.path.join(adir, "manifest.json"), "w"), indent=1)

    manifest["adapter_sha256"] = sha256_file(os.path.join(adir, "adapter_model.safetensors"))
    files = evaluate(adir, name, ["free", "forced"], args, log)

    manifest["finished"] = time.strftime("%Y-%m-%d %H:%M:%S")
    manifest["seconds"] = round(time.time() - t0)
    json.dump(manifest, open(os.path.join(adir, "manifest.json"), "w"), indent=1)

    deliver(f"{name}.zip", files + [log, os.path.join(adir, "manifest.json")], adir, args, log)
    print(f"run {name} complete in {manifest['seconds']} s")


if __name__ == "__main__":
    try:
        main()
    except PreflightError as e:
        print(e, file=sys.stderr)
        sys.exit(2)
