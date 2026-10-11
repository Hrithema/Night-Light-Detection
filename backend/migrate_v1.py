"""Copy your Version 1 files into the new per-region layout (originals are left untouched).

    data/raw        -> data/jharkhand/raw
    data/processed  -> data/jharkhand/processed
    outputs/*       -> outputs/jharkhand/
    models/*.joblib -> models/jharkhand/

Run once:  python migrate_v1.py
"""
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REGION = "jharkhand"

pairs = [
    (ROOT / "data" / "raw", ROOT / "data" / REGION / "raw"),
    (ROOT / "data" / "processed", ROOT / "data" / REGION / "processed"),
]
for src, dst in pairs:
    if src.exists() and not dst.exists():
        shutil.copytree(src, dst)
        print("copied", src, "->", dst)
    elif dst.exists():
        print("skip (already exists):", dst)
    else:
        print("nothing to copy:", src)

out_dst = ROOT / "outputs" / REGION
out_dst.mkdir(parents=True, exist_ok=True)
for f in (ROOT / "outputs").glob("*"):
    if f.is_file():
        shutil.copy2(f, out_dst / f.name)
        print("copied", f.name, "->", out_dst)

mod_dst = ROOT / "models" / REGION
mod_dst.mkdir(parents=True, exist_ok=True)
for f in (ROOT / "models").glob("*.joblib"):
    shutil.copy2(f, mod_dst / f.name)
    print("copied", f.name, "->", mod_dst)

print("\nDone. Your Version 1 files were not changed or deleted.")
