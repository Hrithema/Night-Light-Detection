"""Train the site classifier from your hand-labelled sheet.

Usage:
    python train.py --region jharkhand    # uses data/<region>/processed/label_sheet.csv
    python train.py --sheet path/to.csv
"""
import argparse
import warnings
import numpy as np
import pandas as pd
import joblib
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report, confusion_matrix, f1_score
from sklearn.model_selection import GroupKFold, cross_val_predict
from src import config
from src.site_features import FEATURE_NAMES, load_feature_maps, location_features

warnings.filterwarnings("ignore")
MIN_PER_CLASS = 4


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sheet", default=str(config.PROCESSED_DIR / "label_sheet.csv"))
    ap.add_argument("--region", help="region name from regions.json (default: jharkhand)")
    ap.add_argument("--merge", action="append", default=[],
                    help="merge labels, e.g. --merge industrial,mining=industrial_mining")
    args = ap.parse_args()

    df = pd.read_csv(args.sheet)
    df["label"] = df["label"].astype("string").fillna("").str.strip().str.lower()
    df = df[df["label"] != ""].copy()
    for rule in args.merge:
        src, dst = rule.split("=")
        olds = [x.strip().lower() for x in src.split(",")]
        df["label"] = df["label"].replace({o: dst.strip().lower() for o in olds})
        print(f"merged {olds} -> {dst}")
    print("rows in sheet:", len(pd.read_csv(args.sheet)), "| labelled rows:", len(df))
    if df.empty:
        raise SystemExit(
            "The 'label' column is empty in " + args.sheet + ".\n"
            "Check: (1) you saved the file as CSV, not .xlsx, (2) you labelled THIS file, "
            "(3) you did not rerun run_pipeline.py after labelling (older versions "
            "overwrote the sheet).")
    print(df["label"].value_counts().to_string(), "\n")

    counts = df["label"].value_counts()
    keep = counts[counts >= MIN_PER_CLASS].index
    dropped = sorted(set(counts.index) - set(keep))
    if dropped:
        print(f"dropping classes with < {MIN_PER_CLASS} examples: {dropped}")
    df = df[df["label"].isin(keep)]
    if df["label"].nunique() < 2:
        raise SystemExit("Need at least two labels with enough examples.")

    maps = load_feature_maps()
    X = np.array([location_features(maps, r.lat, r.lon) for r in df.itertuples()])
    y = df["label"].values
    # spatial groups: 0.5 degree blocks, so neighbouring sites never straddle train/test
    groups = (np.floor(df["lat"] / 0.5) * 1000 + np.floor(df["lon"] / 0.5)).astype(int).values
    n_splits = min(5, len(np.unique(groups)))
    if n_splits < 2:
        raise SystemExit("All sites fall in one spatial block; label more varied places.")

    clf = RandomForestClassifier(
        n_estimators=400, min_samples_leaf=2, class_weight="balanced", random_state=0)
    pred = cross_val_predict(clf, X, y, groups=groups, cv=GroupKFold(n_splits))

    print(f"=== spatial cross-validation ({n_splits} folds) ===")
    print(classification_report(y, pred, zero_division=0))
    classes = sorted(set(y))
    print("confusion matrix (rows = true, cols = predicted):", classes)
    print(confusion_matrix(y, pred, labels=classes))
    print("macro F1:", round(f1_score(y, pred, average="macro"), 3), "\n")

    # Did ML beat the plain rule? Compare on the 'is it real change?' question.
    is_change = y != "no_change"
    cand = df["candidate"].values != "negative_sample"       # rows the rule flagged
    if is_change.any() and (~is_change).any():
        rule_prec = is_change[cand].mean() if cand.any() else float("nan")
        m_pred = pred != "no_change"
        tp = (m_pred & is_change).sum()
        print("rule-based flag: share of flagged sites that are real change =",
              round(float(rule_prec), 3))
        print("model: precision =", round(tp / max(m_pred.sum(), 1), 3),
              "| recall =", round(tp / max(is_change.sum(), 1), 3), "\n")

    if cand.any() and is_change.any():
        tc, mc = is_change[cand], (pred != "no_change")[cand]
        tp = (mc & tc).sum()
        print("Among FLAGGED sites only (the real use: filtering false alarms):")
        print("  rule : precision", round(float(tc.mean()), 3), "(it keeps every flagged site)")
        print("  model: precision", round(tp / max(mc.sum(), 1), 3),
              "| recall", round(tp / max(tc.sum(), 1), 3), "\n")

    clf.fit(X, y)
    imp = sorted(zip(FEATURE_NAMES, clf.feature_importances_), key=lambda t: -t[1])
    print("feature importance:")
    for n, v in imp:
        print(f"  {n:12s} {v:.3f}")

    out = config.MODEL_DIR
    out.mkdir(parents=True, exist_ok=True)
    joblib.dump({"model": clf, "features": FEATURE_NAMES, "classes": list(clf.classes_)},
                out / "site_classifier.joblib")
    print("\nsaved model to", out / "site_classifier.joblib")


if __name__ == "__main__":
    main()
