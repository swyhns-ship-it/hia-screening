# -*- coding: utf-8 -*-
"""构建首段蒸馏数据集:从 labels_auto.json 过滤出 HIA 对象,按 部门×A/B/X 分层切
80% 开发池 / 20% 留出集。确定性(无随机:每层排序后每 5 个取 1 进留出),可复现。

产物(随仓库,固定):
  eval/dataset_dev.json      开发池(挖模板 + 调提示词/门控)
  eval/dataset_heldout.json  留出集(挖模板/调参时绝不碰,只测泛化;= 新回归基线)
口径:仅保留 hia_object∈{policy,program,project} 且 label≠C;none/C 剔除。
"""
import collections
import io
import json
import os
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LABELS = os.path.join(ROOT, "eval", "labels_auto.json")
DEV = os.path.join(ROOT, "eval", "dataset_dev.json")
HELDOUT = os.path.join(ROOT, "eval", "dataset_heldout.json")
HELDOUT_EVERY = 5     # 每层每 5 个取第 1 个进留出 = 20%


def dept_of(name):
    return name.split("_")[0]


def main():
    labels = json.load(open(LABELS, encoding="utf-8"))
    objs = {k: v for k, v in labels.items()
            if v.get("hia_object") in ("policy", "program", "project") and v["label"] != "C"}
    # 分层:键 = (部门, 标签)
    strata = collections.defaultdict(list)
    for name, v in objs.items():
        strata[(dept_of(name), v["label"])].append(name)
    dev, heldout = {}, {}
    for key, names in strata.items():
        for i, name in enumerate(sorted(names)):       # 排序后确定性取样
            rec = {"hia_object": objs[name]["hia_object"], "label": objs[name]["label"]}
            (heldout if i % HELDOUT_EVERY == 0 else dev)[name] = rec
    json.dump(dev, open(DEV, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    json.dump(heldout, open(HELDOUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    def dist(d):
        c = collections.Counter(v["label"] for v in d.values())
        return "A%d B%d X%d" % (c.get("A", 0), c.get("B", 0), c.get("X", 0))
    print("有效 HIA 对象 %d → 开发池 %d (%s) / 留出集 %d (%s)"
          % (len(objs), len(dev), dist(dev), len(heldout), dist(heldout)))
    print("开发池阳性 A(挖模板用):%d" % sum(1 for v in dev.values() if v["label"] == "A"))
    print("→ %s\n→ %s" % (DEV, HELDOUT))


if __name__ == "__main__":
    main()
