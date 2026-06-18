# -*- coding: utf-8 -*-
"""漏斗 v3 质量裁定 —— 分层代表性样本构建(确定性、可复现)。

分层维度(CLAUDE.md 待办#8):干预 × 危害密度 × 负样本/边界。
labels_auto.json 标签口径:hia_object(policy/program/project/none/'') × label(A 有潜在危害 /
B 危害≈0 / X 无对象 / C 抽取失败)。据此切五层:

  S1 A-正样本(有潜在危害,测召回+精度)           12
  S2 B-健康临近(标题含危害词,假阳高危,测精度)    8
  S3 B-普通(应≈0,非健康主题)                     3
  S4 X/none-无干预负样本(测 R0 门应拦)             4
  S5 C-抽取失败/边界                               1
                                              共 ~28

每层内**按部门轮转**取,最大化部门多样性(破"航空偏航")、可复现(全程排序,无随机)。
输出 eval/_funnel_sample.json:[{key, dept, hia_object, label, stratum, path}]。
"""
import collections
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LABELS = os.path.join(ROOT, "eval", "labels_auto.json")
CORPUS = r"E:\projects\test2"
OUT = os.path.join(ROOT, "eval", "_funnel_sample.json")

KW = re.compile(r"施工|扬尘|噪声|排放|污染|废|危化|危险品|交通|养老|医疗|供水|食品|职业|"
                r"化工|矿|建设|改造|园区|畜禽|垃圾|管网|核|辐射")


def dept(k):
    return k.split("_", 1)[0]


def spread_pick(keys, n):
    """部门轮转取 n 个:确定性。部门按【该层候选数降序】排(相关部门候选多→优先入选,
    破小配额层的字母序偏置:S2 让 交通/医保/卫健 这类危害词富集部门先进,而非 央行/气象);
    组内按 key 排序轮转直到取满 n。"""
    by = collections.OrderedDict()
    for k in sorted(keys):
        by.setdefault(dept(k), []).append(k)
    out = []
    depts = sorted(by.keys(), key=lambda d: (-len(by[d]), d))
    while len(out) < n and any(by[d] for d in depts):
        for d in depts:
            if by[d] and len(out) < n:
                out.append(by[d].pop(0))
    return out


def find_file(key):
    """label key (部门_序号_标题) → test2 主文件路径(排除 _extra 附件)。"""
    target = key.strip()
    for dirpath, _dirs, files in os.walk(CORPUS):
        if os.sep + "_extra" in dirpath:
            continue
        for fn in files:
            stem, ext = os.path.splitext(fn)
            if ext.lower() in (".pdf", ".docx") and stem == target:
                return os.path.join(dirpath, fn)
    return None


def main():
    d = json.load(open(LABELS, encoding="utf-8"))

    A = [k for k, v in d.items() if v["label"] == "A"]
    Bp = [k for k, v in d.items() if v["label"] == "B"
          and v["hia_object"] in ("policy", "program", "project")]
    Bp_kw = [k for k in Bp if KW.search(k)]
    Bp_plain = [k for k in Bp if not KW.search(k)]
    Xn = [k for k, v in d.items() if v["label"] == "X"]
    C = [k for k, v in d.items() if v["label"] == "C"]

    strata = [
        ("S1_A_有潜在危害", spread_pick(A, 12)),
        ("S2_B_健康临近假阳", spread_pick(Bp_kw, 8)),
        ("S3_B_普通无害", spread_pick(Bp_plain, 3)),
        ("S4_负样本无干预", spread_pick(Xn, 4)),
        ("S5_抽取失败边界", spread_pick(C, 1)),
    ]

    rows, missing = [], []
    for name, keys in strata:
        for k in keys:
            p = find_file(k)
            if not p:
                missing.append(k)
                continue
            rows.append({"key": k, "dept": dept(k), "hia_object": d[k]["hia_object"],
                         "label": d[k]["label"], "stratum": name, "path": p})

    json.dump(rows, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print("样本 %d 份 → %s" % (len(rows), OUT))
    for name, _ in strata:
        cnt = sum(1 for r in rows if r["stratum"] == name)
        ds = sorted({r["dept"] for r in rows if r["stratum"] == name})
        print("  %-22s %2d  部门:%s" % (name, cnt, "、".join(ds)))
    if missing:
        print("⚠ 未在 test2 找到文件(%d):" % len(missing))
        for k in missing:
            print("   -", k)


if __name__ == "__main__":
    main()
