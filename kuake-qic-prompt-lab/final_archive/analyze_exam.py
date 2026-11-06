# -*- coding: utf-8 -*-
"""期末考收尾分析（纯本地计算，不调用模型）。

1) 从 results_holdout.csv 拉出全部错题（correct==0），输出 id,input,expected,predicted 四列
2) 对 dev(results_v2.csv) 与 holdout(results_holdout.csv) 各算 per-class P/R/F1 与 macro-F1

口径：
- 类别全集固定为 11 个英文 code（两份数据的 expected/predicted 均落在其中，无 FORMAT_ERROR）
- 每个类别按 one-vs-rest 统计 TP/FP/FN
  P = TP/(TP+FP), R = TP/(TP+FN), F1 = 2PR/(P+R)，分母为 0 时该项记 0
- macro-F1 = 11 个类别 F1 的算术平均（含 F1=0 的类别，不做加权、不剔除）
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

BASE_DIR = Path(__file__).resolve().parent
LABELS = [
    "method", "diagnosis", "disease_express", "advice", "attention", "price",
    "result", "metric_explain", "cause", "effect", "other",
]

ERRORS_CSV = BASE_DIR / "holdout_errors.csv"
F1_CSV = BASE_DIR / "f1_macro_report.csv"


def per_class(df: pd.DataFrame) -> pd.DataFrame:
    exp = df["expected"].astype(str)
    pred = df["predicted"].astype(str)
    rows = []
    for c in LABELS:
        tp = int(((exp == c) & (pred == c)).sum())
        fp = int(((exp != c) & (pred == c)).sum())
        fn = int(((exp == c) & (pred != c)).sum())
        p = tp / (tp + fp) if tp + fp else 0.0
        r = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * p * r / (p + r) if p + r else 0.0
        rows.append({"label": c, "support": tp + fn, "pred_count": tp + fp,
                     "TP": tp, "FP": fp, "FN": fn, "P": p, "R": r, "F1": f1})
    return pd.DataFrame(rows)


def main() -> None:
    hold = pd.read_csv(BASE_DIR / "results_holdout.csv", encoding="utf-8-sig")
    dev = pd.read_csv(BASE_DIR / "results_v2.csv", encoding="utf-8-sig")

    # ---------- 1) 错题清单 ----------
    err = hold[hold["correct"] == 0][["id", "input", "expected", "predicted"]].copy()
    err.to_csv(ERRORS_CSV, index=False, encoding="utf-8-sig")
    print(f"=== 1) holdout 错题清单：{len(err)} 条 ===")
    print(f"（holdout 共 {len(hold)} 条，正确 {int(hold['correct'].sum())} 条 -> 错 {len(err)} 条）")
    print(f"单独输出文件：{ERRORS_CSV}\n")
    for r in err.itertuples(index=False):
        print(f"{r.id} | {r.expected} -> {r.predicted} | {r.input}")

    # ---------- 2) per-class P/R/F1 + macro-F1 ----------
    all_rows = []
    for name, df in [("dev (results_v2.csv)", dev), ("holdout (results_holdout.csv)", hold)]:
        pc = per_class(df)
        macro_f1 = pc["F1"].mean()
        macro_p = pc["P"].mean()
        macro_r = pc["R"].mean()
        print(f"\n=== 2) {name}  per-class P/R/F1 ===")
        print(f"{'label':<16} {'sup':>4} {'pred':>4} {'TP':>4} {'FP':>4} {'FN':>4} {'P':>8} {'R':>8} {'F1':>8}")
        for r in pc.itertuples(index=False):
            print(f"{r.label:<16} {r.support:>4} {r.pred_count:>4} {r.TP:>4} {r.FP:>4} {r.FN:>4} "
                  f"{r.P:>8.4f} {r.R:>8.4f} {r.F1:>8.4f}")
        print(f"{'macro avg':<16} {'':>4} {'':>4} {'':>4} {'':>4} {'':>4} "
              f"{macro_p:>8.4f} {macro_r:>8.4f} {macro_f1:>8.4f}")
        # 内部一致性校验：所有类别 TP 之和 == 正确条数
        tp_sum = int(pc["TP"].sum())
        print(f"校验：ΣTP = {tp_sum} / 正确条数 = {int(df['correct'].sum())} -> "
              f"{'一致' if tp_sum == int(df['correct'].sum()) else '不一致'}；"
              f"accuracy = {df['correct'].mean():.4f}")
        print(f">>> macro-F1 = {macro_f1:.4f}  ({macro_f1 * 100:.2f}%)")

        for r in pc.itertuples(index=False):
            all_rows.append({"dataset": name, "label": r.label, "support": r.support,
                             "pred_count": r.pred_count, "TP": r.TP, "FP": r.FP, "FN": r.FN,
                             "P": round(r.P, 6), "R": round(r.R, 6), "F1": round(r.F1, 6)})
        all_rows.append({"dataset": name, "label": "MACRO_AVG", "support": len(df),
                         "pred_count": "", "TP": "", "FP": "", "FN": "",
                         "P": round(macro_p, 6), "R": round(macro_r, 6),
                         "F1": round(macro_f1, 6)})

    pd.DataFrame(all_rows).to_csv(F1_CSV, index=False, encoding="utf-8-sig")
    d_dev = per_class(dev)["F1"].mean()
    d_hold = per_class(hold)["F1"].mean()
    print(f"\n=== 对照 ===")
    print(f"dev macro-F1     = {d_dev:.4f} ({d_dev*100:.2f}%)")
    print(f"holdout macro-F1 = {d_hold:.4f} ({d_hold*100:.2f}%)")
    print(f"差值 = {(d_hold - d_dev):+.4f} ({(d_hold - d_dev)*100:+.2f} 个百分点)")
    print(f"\n汇总表已存：{F1_CSV}")


if __name__ == "__main__":
    main()
