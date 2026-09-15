#!/usr/bin/env python
"""
run.py: one command per training run, with a preflight guard any Colab cell can call first.

Fresh Colab session, cell 1:
    !git clone https://github.com/brandonjuarez23/amphora-bridge.git /content/repo
    %cd /content/repo
    !python run.py --setup                      # installs pinned deps, removes torchao, mounts nothing
    from run import preflight; preflight()      # stops the cell if the environment is not ready

One run, cell 2 (names derive from the settings; an existing run is never overwritten):
    !python run.py --data train_bridge_inv.jsonl --epochs 13 --explain-mask 0.5 --drive
    # -> adapter_<name>/, results-<name>-free.json, results-<name>-forced.json,
    #    capability-<name>.json, <name>.zip with a manifest.json inside, copied to Drive.

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
import shutil
import subprocess
import sys
import time

PINNED = {"peft": "0.20.0", "transformers": "5.17.0", "bitsandbytes": "0.50.2"}
BASE_MODEL = "Qwen/Qwen2.5-1.5B-Instruct"
EVAL_SET = "eval/eval_set.json"
CAP_SET = "eval/capability_set.json"
EVAL_PY = "eval/eval.py"
CAP_PY = "eval/capability.py"
TRAIN_PY = "train_colab.py"
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


def run_name_for(data, epochs, explain_mask, seed):
    stem = os.path.splitext(os.path.basename(data))[0]
    m = f"{explain_mask:g}"
    return f"{stem}-e{epochs}-m{m}-s{seed}"


def sh(cmd, log):
    print("+", cmd, flush=True)
    with open(log, "a") as f:
        f.write("+ " + cmd + "\n")
        p = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        tail = []
        for line in p.stdout:
            f.write(line)
            tail.append(line)
            if len(tail) > 40:
                tail.pop(0)
        p.wait()
    print("".join(tail[-14:]), flush=True)
    if p.returncode != 0:
        raise RuntimeError(f"step failed (exit {p.returncode}): {cmd}\nsee {log}")


def sha256_file(path):
    import hashlib
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def evaluate(adir, tag, conditions, args, log):
    """Run the chosen eval conditions (and capability) for an adapter dir; return the result file names."""
    caps = {"free": args.free_max_new_tokens, "forced": args.forced_max_new_tokens}
    files = []
    for cond in conditions:
        sh(f"{sys.executable} {EVAL_PY} --model {BASE_MODEL} --adapter {adir} --dataset {EVAL_SET} --condition {cond} --tag {tag}-{cond} --max-new-tokens {caps[cond]}", log)
        files.append(f"results-{tag}-{cond}.json")
    if not args.skip_capability:
        sh(f"{sys.executable} {CAP_PY} --model {BASE_MODEL} --adapter {adir} --set {CAP_SET} --tag {tag}", log)
        files.append(f"capability-{tag}.json")
    return files


def deliver(zip_name, files, extra_dir, args, log):
    """Zip the run's files (plus an optional directory), copy to Drive, optionally download."""
    sh(f"zip -q {zip_name} {' '.join(files)}" + (f" && zip -qr {zip_name} {extra_dir}" if extra_dir else "") + f" && ls -la {zip_name}", log)
    if args.drive:
        if not os.path.isdir("/content/drive/MyDrive"):
            from google.colab import drive  # type: ignore
            drive.mount("/content/drive")
        os.makedirs(DRIVE_DIR, exist_ok=True)
        shutil.copy(zip_name, os.path.join(DRIVE_DIR, zip_name))
        print("copied to", os.path.join(DRIVE_DIR, zip_name))
    if args.download:
        from google.colab import files as colab_files  # type: ignore
        colab_files.download(zip_name)


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
    t0 = time.time()
    manifest = {
        "tag": tag, "adapter_dir": adir, "adapter_sha256": sha256_file(weights), "conditions": conditions,
        "base_model": BASE_MODEL, "free_max_new_tokens": args.free_max_new_tokens,
        "forced_max_new_tokens": args.forced_max_new_tokens, "versions": {p: _version(p) for p in PINNED},
        "torchao": _version("torchao"), "started": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    try:
        manifest["git_commit"] = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
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
    ap.add_argument("--data", help="training jsonl")
    ap.add_argument("--epochs", type=int, help="REQUIRED for a run; the trainer's default of 3 is not accepted here")
    ap.add_argument("--explain-mask", type=float, default=1.0)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--adapter", help="evaluate this existing adapter directory instead of training")
    ap.add_argument("--tag", help="results tag for --adapter (default: the directory name without 'adapter_')")
    ap.add_argument("--conditions", default="free,forced", help="for --adapter: which eval conditions to run")
    ap.add_argument("--free-max-new-tokens", type=int, default=200, help="free-condition generation cap (recorded in manifest)")
    ap.add_argument("--forced-max-new-tokens", type=int, default=400)
    ap.add_argument("--skip-capability", action="store_true")
    ap.add_argument("--drive", action="store_true", help=f"copy the zip to {DRIVE_DIR} (mounts Drive if needed)")
    ap.add_argument("--download", action="store_true", help="also trigger a browser download of the zip")
    ap.add_argument("--force", action="store_true", help="allow overwriting an existing run of the same name")
    args = ap.parse_args()

    if args.setup:
        setup()
        return
    if args.adapter:
        preflight(need_files=(EVAL_SET, CAP_SET, EVAL_PY, CAP_PY))
        eval_existing(args)
        return
    if not args.data or args.epochs is None:
        ap.error("--data and --epochs are both required for a run (see --help)")

    preflight(need_files=(EVAL_SET, CAP_SET, EVAL_PY, CAP_PY, TRAIN_PY, args.data))

    name = run_name_for(args.data, args.epochs, args.explain_mask, args.seed)
    adir = f"adapter_{name}"
    if os.path.isdir(adir) and not args.force:
        raise PreflightError(f"{adir}/ already exists. A run with these settings has happened; pass --force to overwrite.")
    log = f"run-{name}.log"
    open(log, "w").write(f"run {name} started {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
    t0 = time.time()

    manifest = {
        "run_name": name, "data": args.data, "epochs": args.epochs, "explain_mask": args.explain_mask,
        "seed": args.seed, "base_model": BASE_MODEL, "free_max_new_tokens": args.free_max_new_tokens,
        "forced_max_new_tokens": args.forced_max_new_tokens, "versions": {p: _version(p) for p in PINNED},
        "torchao": _version("torchao"), "started": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    try:
        manifest["git_commit"] = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except Exception:
        manifest["git_commit"] = None

    sh(f"{sys.executable} {TRAIN_PY} --data {args.data} --out {adir} --epochs {args.epochs} --explain-mask {args.explain_mask} --seed {args.seed}", log)
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
