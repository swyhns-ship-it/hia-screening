# -*- coding: utf-8 -*-
"""LLM 辅助金标准自动标注 —— 给评测集每份政策判 A/B/X(C 由抽取层定,不调 API)。

为什么:labels.py 的关键词金标准只认旧 100 份发改委集;新抓的多部门大集文件名不匹配,
几乎全默认 B。本脚本用 DeepSeek 按 HIA 初筛口径逐份判定,产出 labels_auto.json,
供 labels.py 优先采用(见 labels.py 的 expect())。**结果需人工抽检校正**(尤其 A/X 边界)。

口径(与 labels.py / CLAUDE.md 铁律一致):
  A = 政策含**实体环境/行为/暴露改变**(减排/降碳/绿地/食品/职业/道路/水土/适老…),
      应展开健康影响路径;判 0 = 假阴。
  B = 与健康关联很弱或无:纯**程序/财税/金融/价格/定价/交易/数据/统计/认定/评审/人事/
      表彰/任免/标准编号管理**等,即使含"电力/运输/项目"等弱信号词,也应 ≈0;≥2 条 = 假阳。
  X = 边界:有实体或合理核但**易过度展开**(产业目录/经验推广/方法学导则/标准限值/规划纲要),
      不计假阴假阳率,只监控判定漂移。
  C = 抽取失败/扫描件/正文极短(<200 字)—— 由抽取层判,不调 API。

用法:
  EVAL_WORKERS=8 PYTHONIOENCODING=utf-8 python eval/auto_label.py E:/projects/test2
  产物:eval/labels_auto.json  {文件名(无扩展): {"label","reason"}}  断点续跑(已标跳过)。
"""
import concurrent.futures as cf
import glob
import io
import json
import os
import sys
import threading

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import hia_screen as hs  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_JSON = os.path.join(ROOT, "eval", "labels_auto.json")
WORKERS = max(1, int(os.environ.get("EVAL_WORKERS", "1")))
MIN_CHARS = 200            # 与 precheck/labels 口径一致:正文 <200 字归 C
_lock = threading.Lock()

_SYS = """你是健康影响评估(HIA)初筛的金标准标注员。对一份中国政府文件做两步判断,只输出 JSON。

第一步 —— **是不是 HIA 评估对象**(hia_object):HIA 只评估 **policy/program/project**
(政策/规划/工程)这类**干预型**文件。判:
- "policy" 政策制度:办法/规定/条例/政策/制度/指导意见(确立或修改有普遍约束力的干预)
- "program" 规划计划:规划/计划/方案/行动/专项/工程部署
- "project" 具体工程项目:某具体建设/工程/项目
- "none" **非干预型文书**:人事任免/表彰奖励/机构编制/统计公报/会议纪念/行政处罚或批复**个案**/
  纯信息公告/标准编号发布等——这些**不是 HIA 对象**,后续整份剔除。
  ★注意:价格/财税/金融/产业等**真政策**即使健康关联弱,也是 policy(**不是 none**),归下面的 B。

第二步 —— 若是 HIA 对象,判它**是否可能带来不利健康影响(危害)**。
★HIA 初筛只筛**危害**(不利影响),不评效益——"政策对健康有好处"不算 A,**只有可能"损害"健康才算 A**。
不利影响有三类:① 引入新危害/暴露(新建/扩建带来污染、噪声、伤害、职业/危化品暴露、传染病传播条件);
② 削减保护因素(占用绿地、降医保/卫生投入、削弱服务可及、压缩公共空间);③ 扩大健康不公平
(使脆弱群体相对受损更多)。分三类(只在 A/B/X 选一;hia_object=none 时填 "X" 占位):
A(正样本·应有危害路径):政策有上述某类**实体性的不利健康影响**(如新建道路/工程→施工运营期污染噪声伤害;
  削减某项健康保障;某措施使弱势群体受损)。这类**漏判会致命**。
B(负样本·应≈0):**无实质不利健康影响**——纯效益/民生政策(减排/绿地/健身/医疗可及提升,其好处不是危害)、
  以及纯程序/财政/税费/金融/价格/统计/数据/认定/人事/表彰类。**注意:一份好政策(只有益处)应判 B,不是 A。**
X(边界·不计率):有实体内核但不利影响是否成立存疑、或易过度展开(产业目录、经验推广、方法学导则、
  宏观规划、综合改革试点)。拿不准就归 X。

判定铁律:**假阳性比漏报更糟**,但**核心减排/环境/民生政策绝不能误判为 B**。
拿不准 A 还是 B 时,若有任何实体环境/行为改变倾向 → A;若纯属管理程序 → B;两可且偏宏观/目录 → X。

输出:{"hia_object":"policy|program|project|none","label":"A|B|X",
 "reason":"一句中文依据(为何是/不是HIA对象 + 关键措施或为何无健康关联)"}"""


def get_key():
    k = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    if k:
        return k
    try:
        import tomllib
        with open(os.path.join(ROOT, ".streamlit", "secrets.toml"), "rb") as f:
            return (tomllib.load(f).get("deepseek_api_key", "") or "").strip()
    except Exception:
        return ""


def classify_one(path, key):
    name = os.path.splitext(os.path.basename(path))[0]
    with open(path, "rb") as f:
        data = f.read()
    text, info = hs.extract_text(os.path.basename(path), data)
    if info.get("error"):
        return name, {"hia_object": "", "label": "C", "reason": "抽取失败:" + str(info["error"])[:60]}
    if len((text or "").strip()) < MIN_CHARS:
        return name, {"hia_object": "", "label": "C",
                      "reason": "正文极短/疑扫描 %d 字" % len(text or "")}
    user = "文件标题:%s\n\n正文(节选):\n%s" % (name, (text or "")[:6000])
    d = hs._chat_json(_SYS, user, key, max_tokens=300, temps=(0.0, 0.3))
    obj = (d.get("hia_object") or "").strip().lower()
    if obj not in ("policy", "program", "project", "none"):
        obj = "none"   # 异常输出 → 保守归 none(剔除),避免脏样本进数据集
    lab = (d.get("label") or "").strip().upper()
    if lab not in ("A", "B", "X"):
        lab = "X"
    return name, {"hia_object": obj, "label": lab, "reason": (d.get("reason") or "")[:120]}


def load_done():
    if os.path.exists(OUT_JSON):
        try:
            return json.load(open(OUT_JSON, encoding="utf-8"))
        except Exception:
            return {}
    return {}


def save(labels):
    # 原子写:先写临时文件再 os.replace,防"写到一半被中断→主文件损坏丢全部进度",
    # 也避免其它进程读到写一半的残缺 JSON。
    tmp = OUT_JSON + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(labels, f, ensure_ascii=False, indent=2)
    os.replace(tmp, OUT_JSON)


def main():
    key = get_key()
    if not key:
        sys.exit("未找到密钥:设 DEEPSEEK_API_KEY 或 .streamlit/secrets.toml。")
    pol_dir = sys.argv[1] if len(sys.argv) > 1 else r"E:\projects\test2"
    files = sorted(glob.glob(os.path.join(pol_dir, "*.pdf"))
                   + glob.glob(os.path.join(pol_dir, "*.docx")))
    if not files:
        sys.exit("没找到待标文件 @ " + pol_dir)
    labels = load_done()
    todo = [f for f in files if os.path.splitext(os.path.basename(f))[0] not in labels]
    print("待标 %d / 总 %d(已标 %d);并发 %d → %s"
          % (len(todo), len(files), len(labels), WORKERS, OUT_JSON))
    done = [0]

    def work(f):
        try:
            name, lab = classify_one(f, key)
        except Exception as ex:                          # noqa: BLE001
            name = os.path.splitext(os.path.basename(f))[0]
            lab = {"hia_object": "none", "label": "X", "reason": "标注异常:%s" % str(ex)[:60]}
        with _lock:
            labels[name] = lab
            done[0] += 1
            if done[0] % 20 == 0:
                save(labels)
            print("[%d/%d] %s/%s  %s" % (done[0], len(todo),
                  lab.get("hia_object", "?"), lab["label"], name[:40]))

    if WORKERS <= 1:
        for f in todo:
            work(f)
    else:
        with cf.ThreadPoolExecutor(max_workers=WORKERS) as ex:
            list(ex.map(work, todo))
    save(labels)
    # 分布统计
    import collections as _c
    obj_dist = _c.Counter(v.get("hia_object", "?") for v in labels.values())
    # HIA 对象内(非 none、非 C)的 A/B/X 分布
    ab_dist = _c.Counter(v["label"] for v in labels.values()
                         if v.get("hia_object") not in ("none", "") and v["label"] != "C")
    n_obj = sum(c for o, c in obj_dist.items() if o not in ("none", ""))
    print("\n完成 %d 份 → %s" % (len(labels), OUT_JSON))
    print("HIA对象分布:", dict(obj_dist))
    print("HIA对象集(%d 份)内 A/B/X:" % n_obj, dict(ab_dist))


if __name__ == "__main__":
    main()
