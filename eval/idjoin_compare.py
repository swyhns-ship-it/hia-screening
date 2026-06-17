# -*- coding: utf-8 -*-
"""ID-join 匹配 vs 旧关键词匹配 对比(非破坏性,不改线上)。
ID-join:路径链节点 → 决定因素枢纽ID(determinants.resolve);卡片 keys → 枢纽ID;
  因果轨=同题号+共享枢纽,基准轨=共享枢纽(跨题号)。理应更精准(减少 substring 误配)、
  召回不降(靠枢纽别名扩展)。"""
import sys, glob, json, os
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import determinants as D, hia_evidence as ev


def card_hubs(card):
    hubs = []
    for k in card["keys"]:
        h = D.resolve(k)
        if h and h not in hubs:
            hubs.append(h)
    return hubs


def match_by_hub(pathway):
    chain = pathway.get("chain") or []
    path_hubs = set(D.resolve_all(chain))
    qs = "Q%s" % pathway.get("outcome_q")
    causal, benchmark = [], []
    if not path_hubs:
        return []
    for c in ev.CARDS:
        ch = set(card_hubs(c))
        if not ch or path_hubs.isdisjoint(ch):
            continue
        kind = ev.card_kind(c)
        if kind == "因果":
            if c["q"] == qs:
                causal.append(c)
        else:
            benchmark.append(c)
    return causal[:2] + benchmark[:2]


def sig(cards):
    return {tuple(c["sources"]) if isinstance(c, dict) else tuple(c.get("sources", []))
            for c in cards}


def main():
    paths = []
    for f in glob.glob(os.path.join(os.path.dirname(__file__), "out", "*.json")):
        paths += json.load(open(f, encoding="utf-8")).get("res", {}).get("pathways", [])
    kw_has = ij_has = same = ij_more = ij_less = ij_diff = 0
    examples_added, examples_removed = [], []
    for p in paths:
        kw = ev.match(p)                      # 旧:关键词
        ij = match_by_hub(p)                  # 新:ID-join
        ks, is_ = sig(kw), sig([{"sources": c["sources"]} for c in ij])
        if kw:
            kw_has += 1
        if ij:
            ij_has += 1
        if ks == is_:
            same += 1
        else:
            if is_ - ks:
                ij_more += 1
            if ks - is_:
                ij_less += 1
            if (is_ - ks) and (ks - is_):
                ij_diff += 1
            ch = " → ".join(p.get("chain", []))
            for s in (is_ - ks):
                if len(examples_added) < 8:
                    examples_added.append((ch[:50], s[0][:40]))
            for s in (ks - is_):
                if len(examples_removed) < 8:
                    examples_removed.append((ch[:50], s[0][:40]))
    n = len(paths)
    print("路径 %d" % n)
    print("有卡:关键词 %d (%d%%) | ID-join %d (%d%%)" %
          (kw_has, kw_has * 100 // n, ij_has, ij_has * 100 // n))
    print("两法完全一致 %d (%d%%);ID-join 多挂 %d、少挂 %d、改挂 %d" %
          (same, same * 100 // n, ij_more, ij_less, ij_diff))
    print("\nID-join 新增的卡(关键词漏的,看是否合理召回):")
    for ch, s in examples_added:
        print("  + [%s] %s" % (ch, s))
    print("\nID-join 去掉的卡(关键词多配的,看是否本就误配):")
    for ch, s in examples_removed:
        print("  - [%s] %s" % (ch, s))


if __name__ == "__main__":
    main()
