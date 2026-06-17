# -*- coding: utf-8 -*-
"""金标准标签(回归套件) —— 把 _ground_truth.md 固化成机器可读的判定锚点。
标签:
  A  = 正样本,**应展开**健康路径(≥1条)。判 0 = 假阴性。
  B  = 负样本,应**≈0**(纯程序/财税/信用/价格/电力市场/统计/金融/数据/认定)。≥2条 = 假阳性。
  X  = 边界(有实体或合理核但易过度展开/方法学/目录类) —— **不计入假阴假阳率**,只监控判定变化。
  C  = 抽取失败/扫描件/极短 —— 跳过,不计入。
规则:按 C → X → A 顺序匹配文件名关键词,**默认 B**。匹配=关键词为文件名子串。
判定阈值:出路径 = len(pathways) ≥ 1;假阳 = B 类却 ≥ FALSE_POS_MIN 条。"""

import json as _json
import os as _os

FALSE_POS_MIN = 2          # B 类出 ≥2 条路径视为假阳(容 1 条噪声)

# 大集模式:auto_label.py 产的 labels_auto.json 优先(键=文件名无扩展 → {"label",...})。
# 缺该文件时回落到下方旧 100 份发改委关键词规则,完全向后兼容。
_AUTO = {}
_AUTO_PATH = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "labels_auto.json")
if _os.path.exists(_AUTO_PATH):
    try:
        _AUTO = {k: (v.get("label") if isinstance(v, dict) else v)
                 for k, v in _json.load(open(_AUTO_PATH, encoding="utf-8")).items()}
    except Exception:
        _AUTO = {}

C_KEYS = [                 # 抽取失败/扫描/极短(跳过)
    "政府粮食储备安全风险",
    "能源效率标识的产品目录2025",
    "能源效率标识的产品目录2026",
    "车网互动规模化应用试点的通知发改办能源〔2025〕241号_1-2",
]

X_KEYS = [                 # 边界:不计率,只监控
    "节能审查和碳排放评价", "油气管网设施公平开放", "石油天然气基础设施",
    "电力重大事故隐患", "低空经济及其核心产业统计", "节能降碳中央预算内投资专项",
    "节能宣传周和全国低碳日", "深化智慧城市", "生态保护修复领域中央预算内",
    "生态产品价值实现机制试点", "非化石能源电力消费核算", "水效标识的产品目录",
    "南水北调中线干线工程供水价格", "殡葬服务收费",
    "市场准入负面清单",   # 含真实环境健康管制(禁油烟/保护水源/禁野味)→非纯程序,边界
    "核电厂退役准备",     # 含辐射防护/放射性废物管理→有健康关联,边界
    "车网互动规模化应用试点",  # V2G促进可再生能源消纳→间接减排,弱关联边界(_1-2极短仍归C)
]

A_KEYS = [                 # 正样本:应有路径,漏=假阴
    "新一代煤电升级", "新型储能规模化", "再生材料应用推广", "国家级零碳园区建设名单",
    "开展零碳园区建设", "绿色低碳先进技术示范", "重点行业节能降碳改造攻坚",
    "推进生态综合补偿", "西藏生态安全屏障", "长株潭生态绿心",
    "高质量户外运动目的地", "城际铁路健康可持续", "电动汽车充电设施",
    "可再生能源电力消纳", "煤炭清洁高效利用", "乡村振兴和美乡村",
]


def expect(name):
    """文件名(不含扩展名)→ 期望标签 A/B/X/C。优先 labels_auto.json,再回落关键词规则。"""
    if name in _AUTO and _AUTO[name] in ("A", "B", "X", "C"):
        return _AUTO[name]
    for k in C_KEYS:
        if k in name:
            return "C"
    for k in X_KEYS:
        if k in name:
            return "X"
    for k in A_KEYS:
        if k in name:
            return "A"
    return "B"


def verdict(label, n_path):
    """给定期望标签与实得路径数,返回判定结论。"""
    if label == "C":
        return "skip"
    if label == "X":
        return "border(%d)" % n_path
    if label == "A":
        return "pass" if n_path >= 1 else "假阴"
    # B
    return "假阳" if n_path >= FALSE_POS_MIN else "pass"
