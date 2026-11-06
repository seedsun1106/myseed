# -*- coding: utf-8 -*-
"""从 dataset.xlsx 的「黄金留出集」sheet 导出 holdout.csv 并核对。

导出列：id,input,expected（expected 为映射后的英文 code）
核对项：50 行、id 唯一、与开发集 150 条零重叠
附加核对：expected 全在 11 类枚举、input 非空、标签与 dev.txt 金标准一致
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

BASE_DIR = Path(__file__).resolve().parent
XLSX = BASE_DIR / "dataset.xlsx"
HOLDOUT_SHEET = "黄金留出集"
DEV_SHEET = "export"          # 仅用于「零重叠」核对
DEV_TXT = BASE_DIR / "dev.txt"  # 仅用于附加核对
OUT = BASE_DIR / "holdout.csv"

LABEL_MAP = {
    "治疗方案": "method",
    "病情诊断": "diagnosis",
    "疾病表述": "disease_express",
    "就医建议": "advice",
    "注意事项": "attention",
    "医疗费用": "price",
    "后果表述": "result",
    "指标解读": "metric_explain",
    "病因分析": "cause",
    "功效作用": "effect",
    "其他": "other",
}
VALID_LABELS = set(LABEL_MAP.values())

EXPECTED_IDS = [f"HO-{i:03d}" for i in range(1, 51)]


def main() -> None:
    if not XLSX.exists():
        sys.exit(f"错误：找不到 {XLSX}")

    # 唯一一次读取黄金留出集 sheet；不读其他 sheet 的内容（除零重叠核对用的 export）
    ho = pd.read_excel(XLSX, sheet_name=HOLDOUT_SHEET, dtype=str)
    ho.columns = [str(c).strip() for c in ho.columns]
    needed = ["用例编号", "query原文", "官方标签(金标准)", "英文code"]
    missing = [c for c in needed if c not in ho.columns]
    if missing:
        sys.exit(f"错误：「{HOLDOUT_SHEET}」缺少列 {missing}，实际表头 {list(ho.columns)}")

    df = pd.DataFrame({
        "id": ho["用例编号"].fillna("").astype(str).str.strip(),
        "input": ho["query原文"].fillna("").astype(str),  # query 原文，不做 strip
        # 按要求从中文标签映射，而不是直接抄 sheet 自带的英文code列
        "expected": ho["官方标签(金标准)"].fillna("").astype(str).str.strip().map(LABEL_MAP),
    })
    # 与 sheet 自带英文code 列交叉校验（双保险）
    sheet_code = ho["英文code"].fillna("").astype(str).str.strip()
    mismatch = df["expected"].fillna("") != sheet_code
    if mismatch.any():
        sys.exit(f"错误：{int(mismatch.sum())} 行中文映射结果与 sheet 自带英文code 不一致")

    # 只保留 HO-001~050
    df = df[df["id"].str.match(r"^HO-\d{3}$")].copy()
    df = df[df["id"].isin(EXPECTED_IDS)].copy()
    df = df.reset_index(drop=True)

    # 未知标签 / 空 query 直接判失败，不产出脏数据
    if df["expected"].isna().any():
        bad = df.loc[df["expected"].isna(), ["id", "input"]].to_dict("records")
        sys.exit(f"错误：存在无法映射的中文标签：{bad}")
    if (df["input"].str.strip() == "").any():
        sys.exit("错误：存在空的 query 原文")

    df[["id", "input", "expected"]].to_csv(OUT, index=False, encoding="utf-8-sig")

    # ---------------- 核对 ----------------
    back = pd.read_csv(OUT, dtype=str, encoding="utf-8-sig")
    print(f"已生成：{OUT}")
    print(f"列：{list(back.columns)}")

    print("\n[核对 1] 行数 = 50 ?")
    print(f"  实际 {len(back)} 行 -> {'通过' if len(back) == 50 else '不通过'}")

    print("\n[核对 2] id 唯一且恰为 HO-001~050 ?")
    uniq = back["id"].is_unique
    exact = sorted(back["id"].tolist()) == EXPECTED_IDS
    print(f"  唯一：{uniq} | 恰为 HO-001~050：{exact} -> {'通过' if uniq and exact else '不通过'}")

    print("\n[核对 3] 与开发集 150 条零重叠 ?")
    dev = pd.read_excel(XLSX, sheet_name=DEV_SHEET, dtype=str)
    dev = dev[dev["id"].fillna("").astype(str).str.strip().str.startswith(("DT-", "DB-"))]
    dev_ids = set(dev["id"].fillna("").astype(str).str.strip())
    dev_q = set(dev["input"].fillna("").astype(str))
    dev_q_strip = {q.strip() for q in dev_q}
    ho_ids = set(back["id"].astype(str))
    ho_q = set(back["input"].astype(str))
    id_ov = ho_ids & dev_ids
    q_ov = ho_q & dev_q
    qs_ov = {q.strip() for q in ho_q} & dev_q_strip
    print(f"  开发集条数：{len(dev)}（DT-/DB- 过滤后）")
    print(f"  id 重叠：{len(id_ov)} | query 精确重叠：{len(q_ov)} | query strip 后重叠：{len(qs_ov)}")
    print(f"  -> {'通过（零重叠）' if not (id_ov or q_ov or qs_ov) else '不通过'}")
    if q_ov:
        print(f"  重叠 query：{sorted(q_ov)[:10]}")

    # ---------------- 附加核对 ----------------
    print("\n[附加] expected 合法性与标签可信度")
    print(f"  expected 全部在 11 类枚举内：{set(back['expected']).issubset(VALID_LABELS)}")
    print(f"  expected 分布：{back['expected'].value_counts().to_dict()}")
    print(f"  input 无空值：{(back['input'].fillna('').str.strip() != '').all()}")
    if DEV_TXT.exists():
        gold: dict[str, set[str]] = {}
        for line in DEV_TXT.read_text(encoding="utf-8").splitlines():
            if "\t" not in line:
                continue
            q, lab = line.split("\t", 1)
            code = LABEL_MAP.get(lab.strip())
            if code:
                gold.setdefault(q.strip(), set()).add(code)
        hit = same = miss = notfound = 0
        for r in back.itertuples(index=False):
            labels = gold.get(str(r.input).strip())
            if labels is None:
                notfound += 1
            elif r.expected in labels:
                hit += 1
                same += 1
            else:
                miss += 1
        print(f"  与 dev.txt 金标准标签一致：{same}/{len(back)} | 不一致 {miss} | dev.txt 中找不到 {notfound}")

    ok = (
        len(back) == 50
        and uniq and exact
        and not (id_ov or q_ov or qs_ov)
        and set(back["expected"]).issubset(VALID_LABELS)
    )
    print(f"\n总核对结论：{'全部通过' if ok else '存在不通过项'}")
    if not ok:
        sys.exit(1)


if __name__ == "__main__":
    main()
