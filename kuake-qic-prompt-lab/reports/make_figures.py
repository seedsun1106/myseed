# -*- coding: utf-8 -*-
"""复现 reports/figures/ 下的三张图（纯本地，不调用任何模型 API）。

用法（在仓库根目录）：
    python reports/make_figures.py

数据来源：
    results/results_v0.csv ~ results_v3_1.csv   （迭代曲线数值取自各版汇总，见下方常量）
    reports/f1_macro_report.csv                 （11 类 F1）
    results/holdout_errors.csv                  （14 条错题归因）
"""
from __future__ import annotations

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
FIG = ROOT / "reports" / "figures"
FIG.mkdir(parents=True, exist_ok=True)

plt.rcParams["font.sans-serif"] = ["Microsoft YaHei"]
plt.rcParams["axes.unicode_minus"] = False

# 图 1：五版准确率（35.33 / 70.00 / 74.67 / 74.00 / 70.67）+ 72.00% 参考线
VERSIONS = ["V0\n枚举", "V1\n类别定义", "V2\n+8示例", "V3\n+边界规则", "V3.1\n只留1规则"]
ACC = [35.33, 70.00, 74.67, 74.00, 70.67]
fig, ax = plt.subplots(figsize=(10, 5.6))
x = list(range(5))
ax.plot(x, ACC, color="#1f77b4", marker="o", markersize=8, linewidth=2.2, zorder=3, label="开发集准确率")
for xi, v in zip(x, ACC):
    ax.annotate(f"{v:.2f}%", (xi, v), textcoords="offset points", xytext=(0, 11),
                ha="center", fontsize=10, fontweight="bold")
ax.axhline(72.00, color="#d62728", linestyle="--", linewidth=1.8, zorder=2,
           label="留出集验收参考线 72.00%")
ax.annotate("V2 封版 74.67%", xy=(2, 74.67), xytext=(2.45, 82.5),
            fontsize=11, color="#c0392b", fontweight="bold",
            arrowprops=dict(arrowstyle="->", color="#c0392b", lw=1.6))
ax.set_xticks(x, VERSIONS)
ax.set_ylim(28, 88)
ax.set_ylabel("准确率 (%)")
ax.set_title("五版 Prompt 单变量迭代 · 开发集 150 条准确率", fontsize=14, fontweight="bold")
ax.grid(axis="y", alpha=0.35, linestyle=":")
ax.legend(loc="lower right", framealpha=0.95)
fig.tight_layout()
fig.savefig(FIG / "iteration_curve.png", dpi=300)
plt.close(fig)

# 图 2：11 类 F1 双柱（数据取自 reports/f1_macro_report.csv）
rep = pd.read_csv(ROOT / "reports" / "f1_macro_report.csv", encoding="utf-8-sig")
rep = rep[rep["label"] != "MACRO_AVG"]
dev_f1 = rep[rep["dataset"].str.startswith("dev")].set_index("label")["F1"]
ho_f1 = rep[rep["dataset"].str.startswith("holdout")].set_index("label")["F1"]
labels = list(dev_f1.index)
d = [float(dev_f1[l]) for l in labels]
h = [float(ho_f1[l]) for l in labels]
fig, ax = plt.subplots(figsize=(13, 5.8))
xx = list(range(len(labels)))
w = 0.38
b1 = ax.bar([i - w / 2 for i in xx], d, w, label="Dev（results_v2.csv）", color="#1f77b4", zorder=3)
b2 = ax.bar([i + w / 2 for i in xx], h, w, label="Holdout（results_holdout.csv）", color="#ff7f0e", zorder=3)
for bars in (b1, b2):
    for b in bars:
        ax.annotate(f"{b.get_height():.2f}", (b.get_x() + b.get_width() / 2, b.get_height()),
                    textcoords="offset points", xytext=(0, 3), ha="center", fontsize=7.5)
ax.axhline(0.755769, color="#1f77b4", linestyle="--", linewidth=1.2, alpha=0.8, label="Dev macro-F1 75.58%")
ax.axhline(0.710690, color="#ff7f0e", linestyle="--", linewidth=1.2, alpha=0.8, label="Holdout macro-F1 71.07%")
ax.set_xticks(xx, labels, rotation=32, ha="right", fontsize=9)
ax.set_ylim(0, 1.12)
ax.set_ylabel("F1")
ax.set_title("逐类 F1 对照 · V2 封版 Prompt（11 类 one-vs-rest）", fontsize=14, fontweight="bold")
ax.grid(axis="y", alpha=0.3, linestyle=":")
ax.legend(loc="upper right", ncol=2, fontsize=9, framealpha=0.95)
fig.tight_layout()
fig.savefig(FIG / "f1_dev_vs_holdout.png", dpi=300)
plt.close(fig)

# 图 3：HO 14 条错题归因（标注问题 8 / 模型能力 6）
err = pd.read_csv(ROOT / "results" / "holdout_errors.csv", encoding="utf-8-sig")
NOISE_IDS = ["HO-003", "HO-004", "HO-005", "HO-006", "HO-037", "HO-046", "HO-048", "HO-050"]
MODEL_IDS = ["HO-007", "HO-008", "HO-016", "HO-028", "HO-036", "HO-039"]
assert set(err["id"]) == set(NOISE_IDS) | set(MODEL_IDS)
assert not (set(NOISE_IDS) & set(MODEL_IDS)) and len(err) == 14
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5.4))
bars = ax1.bar(["标注问题\n（金标噪声）", "模型能力\n（真实错误）"], [8, 6],
               color=["#7f8c8d", "#c0392b"], width=0.55, zorder=3)
for b in bars:
    ax1.annotate(f"{int(b.get_height())} 条", (b.get_x() + b.get_width() / 2, b.get_height()),
                 textcoords="offset points", xytext=(0, 6), ha="center", fontsize=12, fontweight="bold")
ax1.set_ylim(0, 10)
ax1.set_ylabel("错题条数")
ax1.set_title("黄金留出集 14 条错题归因", fontsize=13, fontweight="bold")
ax1.grid(axis="y", alpha=0.3, linestyle=":")
ax1.text(0.5, -0.30, "预注册 8/8 命中：" + "、".join(NOISE_IDS),
         transform=ax1.transAxes, ha="center", fontsize=8, color="#555555")
b2 = ax2.bar(["原始准确率", "剔除标注噪声后"], [72.0, 88.0],
             color=["#1f77b4", "#27ae60"], width=0.5, zorder=3)
for b, txt in zip(b2, ["72.00%\n36/50", "88.00%\n44/50"]):
    ax2.annotate(txt, (b.get_x() + b.get_width() / 2, b.get_height()),
                 textcoords="offset points", xytext=(0, 5), ha="center", fontsize=11, fontweight="bold")
ax2.set_ylim(0, 105)
ax2.set_ylabel("准确率 (%)")
ax2.set_title("留出集净准确率", fontsize=13, fontweight="bold")
ax2.grid(axis="y", alpha=0.3, linestyle=":")
ax2.text(0.5, 0.30, "剔除标注噪声后净准确率 88%", transform=ax2.transAxes,
         ha="center", fontsize=12, fontweight="bold", color="#c0392b",
         bbox=dict(boxstyle="round,pad=0.4", fc="#fdf2e9", ec="#c0392b", alpha=0.95))
fig.suptitle("期末考试错题归因 · 标注问题 8 / 模型能力 6", fontsize=14, fontweight="bold")
fig.tight_layout(rect=(0, 0.06, 1, 0.94))
fig.text(0.5, 0.015, "剔除标注噪声后净准确率 88%（36 + 8 = 44 / 50）；同一口径下 Dev 逐行审计噪声约 10–13%",
         ha="center", fontsize=9, color="#444444")
fig.savefig(FIG / "error_attribution.png", dpi=300)
plt.close(fig)

print("已生成：", *[str(p.relative_to(ROOT)) for p in sorted(FIG.glob("*.png"))], sep="\n  ")
