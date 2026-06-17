# -*- coding: utf-8 -*-
"""健康决定因素枢纽词表(SDH hubs)—— 首段蒸馏与末段证据之间的【稳定接口/连接键】。

设计哲学(见会话架构讨论):
  一条政策措施经"很长的链"影响健康,但所有链几乎都收敛着穿过一小撮**决定因素枢纽**,
  再落到固定的 10 个结果。任务劈成:
    · 首段(措施→哪个枢纽):无限、易变 → 靠模型 + 语料【蒸馏】,不手搭;
    · 末段(枢纽→结果 + 证据):有限、可锚定 → 手工维护。
  本文件 = 两段之间的**接口**(带稳定 ID 的枢纽)。

★枢纽的来源(v3:框架驱动,破除"卡片/国标反推枢纽"):
  枢纽**不再由现有证据卡反推**(卡有盲区、还会再补)。改为**自上而下从权威框架导出**:
  - 社会骨架(物质生活工作条件 / 社会心理 / 行为生物 / 卫生系统):**WHO CSDH 框架原文**
    (Solar & Irwin 2010, §5.6.1–5.6.4)逐节列举的具体内容。
  - 环境暴露介质(CSDH 仅以"physical environment"一笔带过、未细列):用**WHO 环境健康 /
    GBD 全球疾病负担环境与职业风险因子清单**补齐(空气/水/噪声/土壤/化学品/辐射/高温/气候…)。
  → 证据卡/国标退化为"挂到框架枢纽上的证据";某枢纽暂无卡 = 待补清单,**不反过来删枢纽**。

CSDH 分层:
  · **中间性决定因素**(触发型):物质环境 / 行为生物 / 社会心理 / 卫生系统。
  · **结构性决定因素**(社会经济地位:收入/教育/就业):影响健康须先穿过中间性 → 标 triggering=False。
  · CSDH §5.6.6 的"社会资本/社会凝聚"贯穿性决定因素:**本工具按决定不纳入**(概念有争议)。
  · CSDH §5.6.3 的生物因素"年龄/性别":属正交属性 → 并入 POPULATIONS,不作枢纽。

★门控规则(由 CSDH 因果结构导出,替代旧 _SYS_EXPAND 的 0a/0b 散文式硬凑):
  **一条健康影响路径成立,当且仅当它最终落到某个【触发型(中间性)枢纽】、且机制具体可锚定原文。
  只改变结构性因素(价格/税费/金融/笼统收入就业)而不触及任何中间性决定因素的政策 → ≈0。**

字段:id(稳定·勿改) / name / layer(CSDH 层) / triggering / outcomes(Q1–Q10) / aliases / tracks。
v3 为框架驱动草案,待领域(HIA)专家精修;尚未接入引擎(线上行为不变)。
"""
import re

VOCAB_VERSION = "2026-06-17-v3-csdh+gbd"

OUTCOMES = {
    "Q1": "传染病", "Q2": "重点慢病", "Q3": "中毒伤害", "Q4": "突发公卫",
    "Q5": "人口发展", "Q6": "健康环境", "Q7": "生活方式/心理",
    "Q8": "卫生投入/医保", "Q9": "优质医疗资源", "Q10": "服务质量/可及",
}

LAYERS = ["物质环境", "行为生物", "社会心理", "卫生系统", "结构性"]
INTERMEDIARY = {"物质环境", "行为生物", "社会心理", "卫生系统"}

# 正交脆弱人群属性(含 CSDH 生物因素的年龄/性别;不是决定因素,路径用 population 字段标)
POPULATIONS = [
    {"id": "CHILD", "name": "儿童", "aliases": ["儿童", "婴幼儿", "青少年", "学生"]},
    {"id": "ELDERLY", "name": "老年人", "aliases": ["老年人", "老人", "高龄", "失能老人"]},
    {"id": "MATERNAL", "name": "孕产妇/育龄妇女", "aliases": ["孕产妇", "孕妇", "育龄妇女", "母婴"]},
    {"id": "OUTDOOR_WORKER", "name": "户外劳动者",
     "aliases": ["户外劳动者", "户外工作者", "环卫工", "建筑工人", "快递员", "骑手"]},
    {"id": "LOW_INCOME", "name": "低收入人群",
     "aliases": ["低收入", "低收入人群", "贫困人口", "困难群众"]},
    {"id": "CHRONIC", "name": "慢病患者", "aliases": ["慢病患者", "慢性病患者", "基础疾病人群"]},
    {"id": "DISABLED", "name": "残障人士", "aliases": ["残障", "残疾人", "残障人士"]},
    {"id": "SEX", "name": "性别(女性/男性)", "aliases": ["女性", "男性", "妇女"]},
]

HUBS = [
    # ============ 物质环境(中间性·触发)============
    # — A. CSDH §5.6.1 明列的"生活与工作条件" —
    {"id": "HOUSING", "name": "住房条件", "layer": "物质环境", "outcomes": ["Q2", "Q6"],
     "tracks": "both",
     "aliases": ["住房", "居住条件", "房屋结构", "住房潮湿", "潮湿", "霉菌", "霉变",
                 "室内低温", "取暖不足", "建筑材料", "危房", "棚户", "老旧小区"]},
    {"id": "CROWDING", "name": "居住拥挤", "layer": "物质环境", "outcomes": ["Q1"],
     "tracks": "WHO",
     "aliases": ["居住拥挤", "拥挤", "居住密度", "人口聚集", "人群聚集", "人群密度",
                 "聚集密度", "集体宿舍", "人员流动", "人口流动"]},
    {"id": "SANITATION", "name": "环境卫生与给排水", "layer": "物质环境", "outcomes": ["Q1", "Q6"],
     "tracks": "both",
     "aliases": ["环境卫生", "卫生设施", "给排水", "污水处理", "污水排放", "厕所", "户厕",
                 "洗手设施", "粪口途径", "公共场所卫生", "通风"]},
    {"id": "FOOD", "name": "食物供给与安全", "layer": "物质环境",
     "outcomes": ["Q1", "Q2", "Q4", "Q6"], "tracks": "both",
     "aliases": ["食品安全", "食物供给", "食物可及", "食源性", "食物中毒", "食品卫生",
                 "食源性疾病", "营养供给", "膳食供给", "食品安全事件"]},
    {"id": "WORK_ENV", "name": "工作环境与职业危害", "layer": "物质环境",
     "outcomes": ["Q2", "Q3"], "tracks": "both",
     "aliases": ["职业暴露", "职业病", "职业健康", "工伤", "工作环境", "职业中毒",
                 "工效学", "粉尘", "尘肺", "职业噪声", "化学性危害", "生物性危害"]},
    # — B. CSDH 仅以"physical environment"带过 → WHO 环境健康 / GBD 环境职业风险 补齐 —
    {"id": "AIR", "name": "大气污染", "layer": "物质环境", "outcomes": ["Q2", "Q5", "Q6"],
     "tracks": "both",
     "aliases": ["空气污染", "大气污染", "大气污染物", "PM2.5", "PM10", "NO2", "SO2",
                 "臭氧", "VOCs", "尾气", "机动车尾气", "交通排放", "工业排放", "颗粒物",
                 "雾霾", "空气质量", "环境空气", "扬尘"]},
    {"id": "INDOOR_AIR", "name": "室内/家用空气污染", "layer": "物质环境",
     "outcomes": ["Q2", "Q3", "Q6"], "tracks": "both",
     "aliases": ["室内空气污染", "家用固体燃料", "固体燃料", "室内燃烧", "一氧化碳",
                 "一氧化碳中毒", "甲醛", "氡", "装修污染"]},
    {"id": "NOISE", "name": "环境噪声与振动", "layer": "物质环境",
     "outcomes": ["Q2", "Q6", "Q7"], "tracks": "both",
     "aliases": ["噪声", "噪音", "环境噪声", "交通噪声", "施工噪声", "声环境", "噪声污染",
                 "睡眠干扰", "烦扰", "环境振动", "振动"]},
    {"id": "WATER", "name": "饮用水与水污染", "layer": "物质环境", "outcomes": ["Q1", "Q6"],
     "tracks": "both",
     "aliases": ["饮用水", "生活饮用水", "饮用水水质", "供水", "供水安全", "地下水",
                 "地表水", "水污染", "介水", "介水传染病", "海水", "近岸海域"]},
    {"id": "SOIL", "name": "土壤与重金属污染", "layer": "物质环境", "outcomes": ["Q5", "Q6"],
     "tracks": "both",
     "aliases": ["土壤污染", "土壤重金属", "重金属", "重金属污染", "镉", "铅暴露", "铅",
                 "砷", "汞污染", "建设用地"]},
    {"id": "CHEM", "name": "危险化学品", "layer": "物质环境", "outcomes": ["Q3", "Q4", "Q5"],
     "tracks": "both",
     "aliases": ["危险化学品", "危化品", "化学品", "有毒化学品", "化学品暴露", "化学品泄漏",
                 "泄漏", "危化品事故", "急性中毒", "持久性有机污染物", "农药"]},
    {"id": "RADIATION", "name": "电离与非电离辐射", "layer": "物质环境", "outcomes": ["Q6"],
     "tracks": "both",
     "aliases": ["电磁", "电磁辐射", "电磁环境", "辐射", "电离辐射", "放射性", "放射防护",
                 "核安全"]},
    {"id": "HEAT", "name": "高温与非最适温度", "layer": "物质环境", "outcomes": ["Q2", "Q4"],
     "tracks": "WHO",
     "aliases": ["高温", "热浪", "城市热岛", "极端高温", "热暴露", "热环境", "热相关疾病",
                 "极端低温", "寒潮"]},
    {"id": "CLIMATE", "name": "气候变化与温室气体", "layer": "物质环境", "outcomes": ["Q4"],
     "tracks": "WHO",
     "aliases": ["气候变化", "温室气体", "极端天气", "甲烷", "碳排放", "气候事件"]},
    {"id": "WASTE", "name": "固体废物与危废", "layer": "物质环境",
     "outcomes": ["Q1", "Q2", "Q6"], "tracks": "both",
     "aliases": ["固体废物", "危险废物", "危废处置", "医疗废物", "垃圾焚烧", "焚烧排放",
                 "二噁英", "致癌物", "垃圾处理"]},
    {"id": "VECTOR", "name": "病媒孳生", "layer": "物质环境", "outcomes": ["Q1"],
     "tracks": "WHO",
     "aliases": ["病媒孳生", "积水", "蚊蝇孳生", "蚊蝇", "鼠害", "病媒", "媒介传播",
                 "媒介传播疾病", "登革热"]},
    {"id": "ODOR", "name": "恶臭与异味", "layer": "物质环境", "outcomes": ["Q6", "Q7"],
     "tracks": "both", "aliases": ["恶臭", "臭气", "异味", "恶臭污染"]},
    {"id": "GREEN", "name": "绿地与开放空间", "layer": "物质环境", "outcomes": ["Q2", "Q7"],
     "tracks": "WHO",
     "aliases": ["绿地", "城市绿地", "绿地可达", "公园", "开放空间", "绿化", "绿色空间",
                 "公共空间"]},
    # — C. 建成环境安全(物质环境 → 伤害)—
    {"id": "ROAD", "name": "道路交通安全", "layer": "物质环境", "outcomes": ["Q3"],
     "tracks": "both",
     "aliases": ["道路交通", "交通事故", "道路交通事故", "道路安全", "交通安全", "车祸",
                 "碰撞", "交通伤害", "交通死亡", "头盔", "道路设计", "疲劳驾驶", "颅脑损伤"]},
    {"id": "BUILT_SAFETY", "name": "建成环境安全(适老/无障碍/消防)", "layer": "物质环境",
     "outcomes": ["Q3"], "tracks": "both",
     "aliases": ["适老化", "无障碍", "适老设施", "适老环境", "跌倒", "建筑防火", "消防",
                 "火灾", "防火", "建筑安全"]},

    # ============ 行为生物(中间性·触发)============ CSDH §5.6.3:仅吸烟/膳食/饮酒/缺乏运动
    {"id": "TOBACCO", "name": "烟草", "layer": "行为生物", "outcomes": ["Q2"],
     "tracks": "WHO", "aliases": ["烟草", "吸烟", "二手烟", "卷烟", "控烟"]},
    {"id": "ALCOHOL", "name": "酒精", "layer": "行为生物", "outcomes": ["Q2"],
     "tracks": "WHO", "aliases": ["酒精", "饮酒", "酗酒", "有害饮酒"]},
    {"id": "DIET", "name": "膳食与营养", "layer": "行为生物", "outcomes": ["Q2"],
     "tracks": "WHO", "aliases": ["膳食", "营养", "营养不足", "饮食", "肥胖", "高盐", "高糖"]},
    {"id": "PA", "name": "体力活动", "layer": "行为生物", "outcomes": ["Q2", "Q7"],
     "tracks": "WHO",
     "aliases": ["体力活动", "身体活动", "体育锻炼", "锻炼", "步行", "步行性", "骑行",
                 "主动出行", "久坐", "户外活动"]},

    # ============ 社会心理(中间性·触发)============ CSDH §5.6.2(不含社会资本/凝聚)
    {"id": "STRESS", "name": "心理社会应激", "layer": "社会心理", "outcomes": ["Q7"],
     "tracks": "WHO",
     "aliases": ["心理压力", "心理社会应激", "慢性应激", "负性生活事件", "精神压力",
                 "焦虑", "减压", "主观幸福"]},
    {"id": "JOB_STRAIN", "name": "工作压力与就业不安全", "layer": "社会心理", "outcomes": ["Q7"],
     "tracks": "WHO",
     "aliases": ["工作压力", "job strain", "就业不安全", "不稳定就业", "职业紧张",
                 "工作不稳定", "失业焦虑"]},
    {"id": "FINANCIAL_STRESS", "name": "财务压力与可负担性", "layer": "社会心理", "outcomes": ["Q7"],
     "tracks": "WHO",
     "aliases": ["财务压力", "高负债", "债务", "经济压力", "可负担性", "可负担性下降",
                 "经济困难", "拆迁", "人口置换"]},
    {"id": "SOCIAL_SUPPORT", "name": "社会支持与社会排斥", "layer": "社会心理", "outcomes": ["Q7"],
     "tracks": "WHO",
     "aliases": ["社会支持", "社会排斥", "社会隔离", "社会孤立", "孤独", "社会网络",
                 "社区网络", "社会融入"]},
    {"id": "CONTROL", "name": "控制感", "layer": "社会心理", "outcomes": ["Q7"],
     "tracks": "WHO", "aliases": ["控制感", "自主性", "掌控感", "无力感"]},
    {"id": "VIOLENCE", "name": "暴力与暴力威胁", "layer": "社会心理", "outcomes": ["Q3", "Q7"],
     "tracks": "WHO", "aliases": ["暴力", "暴力威胁", "家庭暴力", "人身安全", "治安"]},

    # ============ 卫生系统(中间性·触发)============ CSDH §5.6.4
    {"id": "ACCESS", "name": "卫生服务可及性", "layer": "卫生系统", "outcomes": ["Q9", "Q10"],
     "tracks": "WHO",
     "aliases": ["医疗可及性", "就医", "医疗服务可及", "卫生服务可及", "地理可及性",
                 "就医地理可达", "急救可达", "交通可达", "放弃就医", "设施布局"]},
    {"id": "HEALTH_INVEST", "name": "卫生健康投入保障", "layer": "卫生系统", "outcomes": ["Q8"],
     "tracks": "WHO",
     "aliases": ["卫生投入", "卫生筹资", "财政卫生支出", "政府卫生支出", "公共卫生投入",
                 "卫生健康保障", "投入安排", "保障水平"]},
    {"id": "INSURANCE", "name": "医疗保险与防灾难性支出", "layer": "卫生系统", "outcomes": ["Q8"],
     "tracks": "WHO",
     "aliases": ["医保", "医疗保险", "参保", "参保能力", "报销", "自付负担", "缴费能力",
                 "因病致贫", "灾难性卫生支出"]},
    {"id": "QUALITY", "name": "服务质量与回应性", "layer": "卫生系统", "outcomes": ["Q10"],
     "tracks": "WHO",
     "aliases": ["服务质量", "患者安全", "医疗服务能力", "公共卫生服务能力", "诊疗质量",
                 "回应性", "服务利用"]},
    {"id": "EQUITY", "name": "资源按需分配与健康公平", "layer": "卫生系统",
     "outcomes": ["Q5", "Q10"], "tracks": "WHO",
     "aliases": ["健康公平", "按需分配", "服务利用差距", "公平可及", "健康不平等"]},
    {"id": "REGIONAL", "name": "优质资源配置与区域均衡", "layer": "卫生系统", "outcomes": ["Q9"],
     "tracks": "WHO",
     "aliases": ["优质医疗资源配置", "区域发展不均", "资源下沉", "分级诊疗", "资源均衡"]},
    {"id": "EMERGENCY", "name": "突发公共卫生应对", "layer": "卫生系统", "outcomes": ["Q4"],
     "tracks": "WHO",
     "aliases": ["突发公共卫生", "群体性健康事件", "群体急性暴露", "公共卫生应急",
                 "疫情应对", "监测预警"]},

    # ============ 结构性(社会经济地位·非触发)============ 须穿到中间性才成路径
    {"id": "INCOME", "name": "收入与就业", "layer": "结构性", "triggering": False,
     "outcomes": ["Q5", "Q8"], "tracks": "WHO",
     "aliases": ["收入", "就业", "失业", "社会经济地位", "生计", "收入水平"]},
    {"id": "EDU", "name": "教育(受教育程度)", "layer": "结构性", "triggering": False,
     "outcomes": ["Q5"], "tracks": "WHO",
     "aliases": ["教育", "受教育", "教育水平", "辍学", "健康素养"]},
]


# ----------------------- 索引 / 接口函数 -----------------------
_BY_ID = {h["id"]: h for h in HUBS}
_ALIAS_INDEX = {}
_ALIAS_COLLISIONS = []
for _h in HUBS:
    for _a in [_h["name"]] + _h["aliases"]:
        if _a in _ALIAS_INDEX and _ALIAS_INDEX[_a] != _h["id"]:
            _ALIAS_COLLISIONS.append((_a, _ALIAS_INDEX[_a], _h["id"]))
        _ALIAS_INDEX[_a] = _h["id"]
_ALIASES_BY_LEN = sorted(_ALIAS_INDEX.keys(), key=len, reverse=True)

_POP_INDEX = {}
for _p in POPULATIONS:
    for _a in [_p["name"]] + _p["aliases"]:
        _POP_INDEX[_a] = _p["id"]
_POP_BY_LEN = sorted(_POP_INDEX.keys(), key=len, reverse=True)


def hub(hub_id):
    return _BY_ID.get(hub_id)


def is_triggering(hub_id):
    h = _BY_ID.get(hub_id)
    return bool(h) and h.get("triggering", True)


def layer_of(hub_id):
    h = _BY_ID.get(hub_id)
    return h["layer"] if h else None


def resolve(text):
    t = str(text or "")
    for a in _ALIASES_BY_LEN:
        if a in t:
            return _ALIAS_INDEX[a]
    return None


def resolve_all(chain):
    out = []
    for node in chain or []:
        hid = resolve(node)
        if hid and hid not in out:
            out.append(hid)
    return out


def resolve_population(text):
    t = str(text or "")
    for a in _POP_BY_LEN:
        if a in t:
            return _POP_INDEX[a]
    return None


def chain_triggers(chain):
    """★门控判据:该链是否落到至少一个【触发型(中间性)枢纽】。
    只命中结构性枢纽(收入/教育/就业)而无任何中间性枢纽 → False(纯结构性,应≈0)。"""
    return any(is_triggering(h) for h in resolve_all(chain))


def outcomes_of(hub_id):
    h = _BY_ID.get(hub_id)
    return list(h["outcomes"]) if h else []


def hubs_for_outcome(q):
    qs = q if isinstance(q, str) else f"Q{q}"
    return [h["id"] for h in HUBS if qs in h["outcomes"]]


def validate():
    problems = []
    if _ALIAS_COLLISIONS:
        problems.append(f"别名冲突 {len(_ALIAS_COLLISIONS)}: {_ALIAS_COLLISIONS[:5]}")
    for h in HUBS:
        if h["layer"] not in LAYERS:
            problems.append(f"{h['id']} layer 非法 {h['layer']}")
        if not h.get("outcomes"):
            problems.append(f"{h['id']} 无 outcomes")
        for q in h["outcomes"]:
            if q not in OUTCOMES:
                problems.append(f"{h['id']} 题号非法 {q}")
        if h.get("tracks") not in ("WHO", "GB", "both"):
            problems.append(f"{h['id']} tracks 非法 {h.get('tracks')}")
    covered = {q for h in HUBS if h.get("triggering", True) for q in h["outcomes"]}
    missing = [q for q in OUTCOMES if q not in covered]
    if missing:
        problems.append(f"无【触发型】枢纽覆盖的结果题: {missing}")
    return problems


if __name__ == "__main__":
    import sys
    import collections
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    probs = validate()
    by_layer = collections.Counter(h["layer"] for h in HUBS)
    n_trig = sum(1 for h in HUBS if h.get("triggering", True))
    print(f"决定因素枢纽词表 {VOCAB_VERSION}:{len(HUBS)} 枢纽"
          f"(触发 {n_trig}/非触发 {len(HUBS)-n_trig}),{len(_ALIAS_INDEX)} 别名,"
          f"{len(POPULATIONS)} 类脆弱人群")
    print("按 CSDH 层:", dict(by_layer))
    cov = {f"{q}{OUTCOMES[q]}": len([h for h in hubs_for_outcome(q) if is_triggering(h)])
           for q in OUTCOMES}
    print("各结果题被【触发型】枢纽覆盖数:", cov)
    print("自检:", "✓ 通过" if not probs else "✗\n  " + "\n  ".join(probs))
