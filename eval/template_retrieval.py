# -*- coding: utf-8 -*-
"""首段蒸馏 · 向量检索:把验证后模板库做成"措施 → 模板"的语义检索索引。

机制:对每个模板的 action_examples(验证过的真实措施措辞)逐条编码,建成
(向量, 模板) 索引。运行时把政策的一条措施(chain[0])编码,取余弦最近的若干例 →
投票到模板。这样千变万化的措施措辞能语义命中到有限的模板(首段的关键)。

Embedding:本地 BAAI/bge-small-zh-v1.5(中文、小、离线;走 hf-mirror 镜像)。
  生产侧:模板向量离线预算缓存(.npz),运行时只编码查询短句,2G 服务器可承受。

用法:
  python eval/template_retrieval.py            # 建索引 + 跑几个样例查询自检
  代码:from template_retrieval import TemplateRetriever; r=TemplateRetriever(); r.search("公转铁")
"""
import json
import os
import sys

os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")   # 国内镜像
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATES = os.path.join(ROOT, "eval", "templates_validated.json")
INDEX_NPZ = os.path.join(ROOT, "eval", "template_vec_index.npz")
MODEL_NAME = os.environ.get("EMB_MODEL", "BAAI/bge-small-zh-v1.5")

_model = None


def _get_model():
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer(MODEL_NAME)
    return _model


def _encode(texts):
    import numpy as np
    m = _get_model()
    v = m.encode(list(texts), normalize_embeddings=True, batch_size=64,
                 show_progress_bar=False)
    return np.asarray(v, dtype="float32")


class TemplateRetriever:
    def __init__(self, rebuild=False):
        import numpy as np
        self.np = np
        self.templates = json.load(open(TEMPLATES, encoding="utf-8"))
        self.by_id = {t["template_id"]: t for t in self.templates}
        if (not rebuild) and os.path.exists(INDEX_NPZ) and \
                os.path.getmtime(INDEX_NPZ) >= os.path.getmtime(TEMPLATES):
            d = np.load(INDEX_NPZ, allow_pickle=True)
            self.vecs = d["vecs"]
            self.ex_tid = list(d["ex_tid"])
            self.ex_text = list(d["ex_text"])
        else:
            self._build()

    def _build(self):
        ex_tid, ex_text = [], []
        for t in self.templates:
            for a in t.get("action_examples", []):
                if a and len(a.strip()) >= 2:
                    ex_tid.append(t["template_id"])
                    ex_text.append(a.strip())
        vecs = _encode(ex_text)
        self.np.savez(INDEX_NPZ, vecs=vecs,
                      ex_tid=self.np.array(ex_tid, dtype=object),
                      ex_text=self.np.array(ex_text, dtype=object))
        self.vecs, self.ex_tid, self.ex_text = vecs, ex_tid, ex_text
        print("索引建成:%d 例 → %d 模板 → %s" %
              (len(ex_text), len(self.by_id), INDEX_NPZ))

    def search(self, action_text, k=5, per_template_best=True):
        """措施文本 → top-k 模板。返回 [{template_id, hub, outcome_q, direction, score, hit_example}]。"""
        q = _encode([action_text])[0]
        sims = self.vecs @ q                          # 已归一化 → 点积=余弦
        order = self.np.argsort(-sims)
        seen, out = {}, []
        for i in order:
            tid = self.ex_tid[i]
            s = float(sims[i])
            if per_template_best and tid in seen:
                continue
            seen[tid] = True
            t = self.by_id[tid]
            out.append({"template_id": tid, "hub": t["hub"], "hub_name": t.get("hub_name"),
                        "outcome_q": t["outcome_q"], "direction": t["direction"],
                        "score": round(s, 3), "hit_example": self.ex_text[i]})
            if len(out) >= k:
                break
        return out


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    r = TemplateRetriever(rebuild=True)
    tests = ["推进城市公交电动化替代柴油车", "新建乡镇污水处理设施", "老旧小区加装电梯和健身步道",
             "学校食堂明厨亮灶食品安全监管", "调整输配电价格疏导成本", "加强危险化学品企业搬迁改造"]
    print("\n=== 样例检索(措施 → top3 模板)===")
    for q in tests:
        hits = r.search(q, k=3)
        print("\n措施:%s" % q)
        for h in hits:
            print("  %.3f  %s·Q%d·%s  (命中例:%s)" %
                  (h["score"], h["hub"], h["outcome_q"], h["direction"], h["hit_example"][:30]))


if __name__ == "__main__":
    main()
