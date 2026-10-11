"""Score a trained model on ANOTHER region's labelled sheet, without retraining.

Usage:
    python evaluate.py --region karnataka --model-region jharkhand \
        --merge industrial,mining,urban_growth=change

The result is the honest test of whether the model transfers to a new place.
It is not comparable with the cross-validation score from training: that one
was measured inside the training region.
"""
import argparse
import warnings

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import classification_report, confusion_matrix, f1_score

from src import config
from src.site_features import load_feature_maps, location_features

warnings.filterwarnings("ignore")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--region", help="region whose labelled sheet you are testing on")
    ap.add_argument("--model-region", default="jharkhand", help="region the model was trained in")
    ap.add_argument("--sheet", default=str(config.PROCESSED_DIR / "label_sheet.csv"))
    ap.add_argument("--merge", action="append", default=[],
                    help="merge labels the same way you did when training")
    args = ap.parse_args()

    model_path = config.ROOT / "models" / args.model_region / "site_classifier.joblib"
    if not model_path.exists():
        raise SystemExit(f"No model at {model_path}. Train it first: "
                         f"python train.py --region {args.model_region} ...")
    bundle = joblib.load(model_path)
    classes = list(bundle["classes"])
    print(f"model trained in '{args.model_region}', classes: {classes}")
    print(f"testing on region '{config.REGION}' using {args.sheet}\n")

    df = pd.read_csv(args.sheet)
    df["label"] = df["label"].astype("string").fillna("").str.strip().str.lower()
    df = df[df["label"] != ""].copy()
    for rule in args.merge:
        src, dst = rule.split("=")
        olds = [x.strip().lower() for x in src.split(",")]
        df["label"] = df["label"].replace({o: dst.strip().lower() for o in olds})
    if df.empty:
        raise SystemExit("No labelled rows in the sheet - label some sites first.")

    unknown = sorted(set(df["label"]) - set(classes))
    if unknown:
        print(f"WARNING: dropping rows with labels the model doesn't know: {unknown}\n"
              "(use --merge the same way you did when training)")
        df = df[df["label"].isin(classes)]
    if df.empty:
        raise SystemExit("No rows left to test on.")

    maps = load_feature_maps()
    X = np.array([location_features(maps, r.lat, r.lon) for r in df.itertuples()])
    y = df["label"].values
    pred = bundle["model"].predict(X)

    print("test rows:", len(df))
    print(df["label"].value_counts().to_string(), "\n")
    print(f"accuracy: {(pred == y).mean():.3f}   macro F1: {f1_score(y, pred, average='macro'):.3f}\n")
    print(classification_report(y, pred, labels=classes, zero_division=0))
    print("confusion matrix (rows = true, cols = predicted):", classes)
    print(confusion_matrix(y, pred, labels=classes))

    if "no_change" in classes:
        is_change = y != "no_change"
        cand = df["candidate"].values != "negative_sample"
        if cand.any() and is_change.any():
            tc, mc = is_change[cand], (pred != "no_change")[cand]
            tp = (mc & tc).sum()
            print("\nAmong FLAGGED sites only:")
            print("  rule : precision", round(float(tc.mean()), 3))
            print("  model: precision", round(tp / max(mc.sum(), 1), 3),
                  "| recall", round(tp / max(tc.sum(), 1), 3))


if __name__ == "__main__":
    main()
