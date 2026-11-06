# -*- coding: utf-8 -*-
"""KUAKE-QIC 黄金留出集评测脚本（智谱 GLM，V2 Prompt）。

用法：
    python eval_batch.py              # 全量
    python eval_batch.py --limit 10   # 只跑前 10 条
数据源：holdout.csv（50 条，列 id,input,expected，expected 已是英文 code）。
断点续跑：results_holdout.csv 中已有的 id 自动跳过。
密钥：从环境变量 ZHIPU_API_KEY 读取，脚本内不硬编码。
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

import pandas as pd
from zhipuai import ZhipuAI

# ------------------------------ 固定配置 ------------------------------
BASE_DIR = Path(__file__).resolve().parent
DEFAULT_DATA = BASE_DIR / "holdout.csv"
RESULTS_PATH = BASE_DIR / "results_holdout.csv"

# xlsx（开发集）读取配置：只读这一个 sheet；读取后校验表头，绝不读取其他 sheet 的内容
SHEET_NAME = "export"
REQUIRED_COLUMNS = ["id", "input", "expected", "category"]
# CSV（黄金留出集 holdout.csv）读取配置：三列，id 以 HO- 开头，expected 已是英文 code
HOLDOUT_COLUMNS = ["id", "input", "expected"]

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

MODEL = "glm-5.3-flash"
TEMPERATURE = 0.1
REASONING_EFFORT = "low"

# V2 Prompt：13 行类别定义 + 8 条判定示例（833 字符 / 22 行）
PROMPT_V0 = """你是医疗搜索query分类器。将输入的query分为以下11类之一。只输出JSON：{"label": "英文code"}
类别定义：
- method 治疗方案：询问怎么治疗、怎么处理、用什么药、做什么手术等具体做法
- diagnosis 病情诊断：描述自身症状后询问得了什么病、是不是某种病
- disease_express 疾病表述：询问某种疾病的症状、表现、能否治愈
- advice 就医建议：询问去哪里看病、挂什么科、哪家医院或医生好
- attention 注意事项：询问患病、用药或孕期等特殊时期能否做某事、有何禁忌
- price 医疗费用：询问治疗、检查、手术的花费
- result 后果表述：询问某种情况或行为会导致什么后果、危害、影响
- metric_explain 指标解读：询问化验、体检指标数值的含义、是否正常
- cause 病因分析：询问疾病或现象的成因
- effect 功效作用：询问某种药、食物、疗法的作用、效果、副作用
- other 其他：单纯陈述情况、意图不明、或以上类别都不适用时
判定示例：
query: 高血压是什么原因引起的 → {"label": "cause"}
query: 我最近总是头晕，晚上躺下更明显，这是怎么回事 → {"label": "diagnosis"}
query: 痔疮用什么药能治好 → {"label": "method"}
query: 痔疮去医院该挂哪个科 → {"label": "advice"}
query: 孕妇不小心吃了两片去痛片，对胎儿有没有影响 → {"label": "result"}
query: 长期吃板蓝根有什么副作用 → {"label": "effect"}
query: 去年做过阑尾炎手术，现在恢复得挺好的 → {"label": "other"}
query: 有没有宝妈家孩子也这样啊，来说说 → {"label": "other"}"""

MAX_RETRY = 2           # 单条失败自动重试 2 次
RETRY_WAIT = 3.0        # 重试间隔 3 秒
CALL_INTERVAL = 0.6     # 每次调用间隔 0.6 秒
RAW_LIMIT = 500         # raw_response 截断长度
PROGRESS_EVERY = 10     # 每处理 10 条打印一次进度
FORMAT_ERROR = "FORMAT_ERROR"

CSV_COLUMNS = ["id", "input", "expected", "predicted", "correct", "raw_response"]


class FatalAuthError(Exception):
    """密钥/权限类错误，继续跑没有意义，直接中止。"""


# ------------------------------ 数据读取 ------------------------------
def load_dataset(data_path: Path, sheet_name: str) -> pd.DataFrame:
    """读取评测数据，按数据源格式分流：
    - xlsx（开发集）：只读指定 sheet，表头须为 id,input,expected,category，过滤 DT-/DB- 开头，
      expected 中文标签映射为英文 code。
    - csv（黄金留出集 holdout.csv）：表头须为 id,input,expected，过滤 HO- 开头，
      expected 已是英文 code（只校验合法性），无 category 列时置空（汇总显示 N/A）。
    """
    if not data_path.exists():
        sys.exit(f"错误：找不到数据文件 {data_path}")

    is_csv = data_path.suffix.lower() in (".csv", ".tsv")
    if is_csv:
        df = pd.read_csv(data_path, dtype=str, encoding="utf-8-sig")
        required, prefixes = HOLDOUT_COLUMNS, ("HO-",)
    else:
        # 唯一一次 pandas 读取 xlsx：sheet_name 明确指定，不碰其他 sheet
        df = pd.read_excel(data_path, sheet_name=sheet_name, dtype=str)
        required, prefixes = REQUIRED_COLUMNS, ("DT-", "DB-")

    cols = [str(c).strip() for c in df.columns]
    if cols != required:
        sys.exit(
            f"错误：{data_path.name} 的表头是 {cols}，不是 {required}。"
            f" 可用 --sheet 指定正确的 sheet。"
        )
    df.columns = required
    df = df[required].copy()

    # 读取后过滤：只保留用例 id（留出集 HO-，开发集 DT-/DB-）
    ids = df["id"].fillna("").astype(str).str.strip()
    keep = ids.str.startswith(prefixes)
    df = df[keep].copy()
    df["id"] = ids[keep]

    # expected：CSV 已是英文 code，只校验；xlsx 为中文标签，按映射表转换
    lab = df["expected"].fillna("").astype(str).str.strip()
    unknown = ~lab.isin(VALID_LABELS if is_csv else LABEL_MAP)
    if unknown.any():
        bad = df.loc[unknown, ["id", "expected"]].to_dict("records")
        print(f"警告：{int(unknown.sum())} 行 expected 不在 11 类枚举中，已跳过：{bad}")
        df = df[~unknown].copy()
        lab = lab[~unknown]
    df["expected_code"] = lab if is_csv else lab.map(LABEL_MAP)

    # 留出集不区分 typical/boundary，补空 category 让汇总显示 N/A
    if "category" in df.columns:
        df["category"] = df["category"].fillna("").astype(str).str.strip()
    else:
        df["category"] = ""
    df["input"] = df["input"].fillna("").astype(str)  # 用户消息用原文，不做 strip
    return df.reset_index(drop=True)


# ------------------------------ 断点续跑 ------------------------------
def load_existing():
    if not RESULTS_PATH.exists():
        return [], set()
    try:
        old = pd.read_csv(RESULTS_PATH, encoding="utf-8-sig", dtype=str, keep_default_na=False)
    except Exception as exc:
        print(f"警告：读取 {RESULTS_PATH.name} 失败（{exc}），本次从头开始。")
        return [], set()
    if not set(CSV_COLUMNS).issubset(old.columns):
        sys.exit(f"错误：{RESULTS_PATH.name} 的列不符合预期，应包含 {CSV_COLUMNS}")
    rows = old[CSV_COLUMNS].to_dict("records")
    return rows, set(old["id"].astype(str))


def save_results(rows):
    """整表重写，保证 utf-8-sig 的 BOM 只在文件开头出现一次。"""
    pd.DataFrame(rows, columns=CSV_COLUMNS).to_csv(
        RESULTS_PATH, index=False, encoding="utf-8-sig"
    )


# ------------------------------ 模型调用 ------------------------------
def call_model(client: ZhipuAI, query: str) -> str:
    resp = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": PROMPT_V0},
            {"role": "user", "content": query},
        ],
        temperature=TEMPERATURE,
        # SDK 无顶层 reasoning_effort 参数，通过 extra_body 透传到 API
        extra_body={"reasoning_effort": REASONING_EFFORT},
    )
    content = resp.choices[0].message.content
    return content if isinstance(content, str) else ("" if content is None else str(content))


def parse_label(raw: str) -> str:
    """从模型输出解析 JSON 的 label 字段；失败或非法标签抛异常。"""
    if not raw or not raw.strip():
        raise ValueError("空响应")
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    obj = None
    try:
        obj = json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{[^{}]*\}", text, re.S)
        if match:
            try:
                obj = json.loads(match.group(0))
            except json.JSONDecodeError:
                pass
    if not isinstance(obj, dict):
        raise ValueError(f"无法解析JSON：{text[:80]!r}")
    label = obj.get("label")
    if not isinstance(label, str) or label.strip() not in VALID_LABELS:
        raise ValueError(f"label 非法或不在11类枚举内：{label!r}")
    return label.strip()


def predict_one(client: ZhipuAI, query: str):
    """返回 (predicted, raw_response, error)。失败重试 2 次，最终记 FORMAT_ERROR。"""
    last_raw, last_err = "", ""
    for attempt in range(MAX_RETRY + 1):
        raw = ""
        try:
            raw = call_model(client, query)
            return parse_label(raw), raw, ""
        except Exception as exc:
            last_raw, last_err = raw, f"{type(exc).__name__}: {exc}"
        if attempt < MAX_RETRY:
            print(f"    第 {attempt + 1} 次失败（{last_err[:120]}），{RETRY_WAIT}s 后重试")
            time.sleep(RETRY_WAIT)

    # 鉴权类错误属于全局问题，中止整轮避免空跑
    if re.search(r"401|403|unauthor|api.?key|鉴权|认证|余额|权限", last_err, re.I):
        raise FatalAuthError(last_err)
    return FORMAT_ERROR, (last_raw or f"[ERROR] {last_err}"), last_err


# ------------------------------ 汇总 ------------------------------
def print_summary(rows, all_df: pd.DataFrame):
    if not rows:
        print("没有可汇总的结果。")
        return
    out = pd.DataFrame(rows, columns=CSV_COLUMNS)
    out["correct"] = pd.to_numeric(out["correct"], errors="coerce").fillna(0).astype(int)
    total = len(out)
    hit = int(out["correct"].sum())

    print("\n" + "=" * 62)
    # 本次汇总为 holdout 考试（黄金留出集 50 条）；以下仅为静态文案，未重跑模型
    print("基线评测汇总")
    print("=" * 62)
    print("本次汇总：holdout 黄金留出集（期末考试）")
    print(f"总条数：{total}    正确：{hit}    总体准确率：{hit / total:.2%}")

    cat_map = dict(zip(all_df["id"], all_df["category"]))
    out["category"] = out["id"].map(cat_map).fillna("unknown")
    for cat in ("typical", "boundary"):
        sub = out[out["category"] == cat]
        if len(sub):
            n, c = len(sub), int(sub["correct"].sum())
            print(f"{cat:<10}准确率：{c / n:.2%}  ({c}/{n})")
        else:
            print(f"{cat:<10}准确率：N/A  (0 条)")

    fmt = int((out["predicted"] == FORMAT_ERROR).sum())
    print(f"FORMAT_ERROR：{fmt} 条")

    print("\n各 expected 标签分组准确率：")
    grouped = out.groupby("expected")["correct"].agg(["size", "sum"])
    grouped = grouped.sort_values("size", ascending=False)
    for label, r in grouped.iterrows():
        n, c = int(r["size"]), int(r["sum"])
        print(f"  {label:<16} {c:>3}/{n:<3} = {c / n:.2%}")
    print("=" * 62)
    print(f"结果文件：{RESULTS_PATH}")


# ------------------------------ 主流程 ------------------------------
def main():
    parser = argparse.ArgumentParser(description="KUAKE-QIC 批量评测")
    parser.add_argument("--limit", type=int, default=None, help="只跑前 N 条；不传则全量")
    parser.add_argument("--xlsx", "--data", dest="data_path", type=str,
                        default=str(DEFAULT_DATA), help="数据文件路径（默认 holdout.csv）")
    parser.add_argument("--sheet", type=str, default=SHEET_NAME, help="xlsx 数据源四列表头所在的 sheet 名")
    args = parser.parse_args()

    api_key = os.environ.get("ZHIPU_API_KEY")
    if not api_key:
        sys.exit("错误：环境变量 ZHIPU_API_KEY 未设置。请先设置后再运行（脚本不会硬编码密钥）。")

    all_df = load_dataset(Path(args.data_path), args.sheet)
    run_df = all_df.head(args.limit) if args.limit is not None else all_df
    rows, done_ids = load_existing()
    todo = run_df[~run_df["id"].isin(done_ids)]

    print(f"模型：{MODEL} | temperature={TEMPERATURE} | reasoning_effort={REASONING_EFFORT}")
    print(f"数据集：{len(run_df)} 条 | 已存在结果跳过：{len(run_df) - len(todo)} 条 | 本次待跑：{len(todo)} 条")
    if len(todo) == 0:
        print("无待跑用例，直接汇总。")
        print_summary(rows, all_df)
        return

    client = ZhipuAI(api_key=api_key)
    processed = 0
    aborted = False
    for row in todo.itertuples(index=False):
        try:
            predicted, raw, err = predict_one(client, row.input)
        except FatalAuthError as exc:
            print(f"\n鉴权/权限错误，中止本轮：{exc}")
            aborted = True
            break
        correct = 1 if predicted == row.expected_code else 0
        rows.append({
            "id": row.id,
            "input": row.input,
            "expected": row.expected_code,
            "predicted": predicted,
            "correct": correct,
            "raw_response": str(raw)[:RAW_LIMIT],
        })
        save_results(rows)  # 每条即落盘，支持随时中断续跑
        processed += 1
        if err:
            print(f"  [{row.id}] {predicted}（{err[:100]}）")
        if processed % PROGRESS_EVERY == 0 or processed == len(todo):
            done_hits = sum(1 for r in rows if str(r["correct"]) == "1")
            print(f"进度：{processed}/{len(todo)}  已完成结果 {len(rows)} 条，累计正确 {done_hits} 条")
        time.sleep(CALL_INTERVAL)

    if aborted:
        print("本轮中止，已完成的条目已保存，设置好密钥后重跑会自动续跑。")
    print_summary(rows, all_df)


if __name__ == "__main__":
    main()
