# -*- coding: utf-8 -*-
"""
hia_evidence.py
HIA 机制路径支撑证据卡片（WHO 官方来源）

字段说明：
  keys    : 该"决定因素 → 健康结果"机制链的中文关键词
  q       : 初筛题号（Q1~Q10）
  note    : 支撑要点（概括，非 WHO 原文逐字摘录；逐字结论请打开 URL 自取）
  sources : ["标题(年份). WHO. URL", ...]，同一来源可被多条路径复用
  status  : "done" = WHO 官网已取证；"todo" = WHO 官网确无/待核实，转系统综述/meta 补

注：所有 URL 均经实际打开核实域名(who.int / iris.who.int)、年份与主题。

app 接口（被 hia_screen.py / views 调用）：match(pathway) / annotate(pathways) / gaps(pathways)。
匹配按"题号一致 + 关键词双向命中因果链"；status='todo' 的卡片仍挂来源,显示端标"待补强"。
"""

CARDS = [
    # ===================== Q1 传染病与感染性疾病 =====================
    {
        "keys": ["饮用水水质", "饮用水", "供水安全", "地下水", "水污染", "介水传染病"],
        "q": "Q1",
        "note": "以 60 余年证据为基础，确立基于健康的目标、流域到龙头水安全计划与独立监测，"
                "作为各国水质标准的权威依据，核心目标是控制介水病原体风险。",
        "sources": [
            "Guidelines for drinking-water quality: 4th edition incorporating the 1st and 2nd addenda (2022). WHO. https://www.who.int/publications/i/item/9789240045064",
        ],
        "status": "done",
    },
    {
        "keys": ["环境卫生", "卫生设施", "污水处理不足", "粪口途径传染病"],
        "q": "Q1",
        "note": "安全环境卫生对预防感染至关重要；指南汇总卫生设施与健康（含粪口途径传染病）"
                "的证据并给出循证建议。",
        "sources": [
            "Guidelines on sanitation and health (2018). WHO. https://www.who.int/publications/i/item/9789241514705",
            "Sanitation (fact sheet). WHO. https://www.who.int/news-room/fact-sheets/detail/sanitation",
        ],
        "status": "done",
    },
    {
        "keys": ["人口聚集", "居住拥挤", "拥挤", "集体宿舍", "居住密度", "呼吸道传染病传播"],
        "q": "Q1",
        "note": "住房与健康指南专门评估居住拥挤的健康风险（含呼吸道传染病传播）并给出针对拥挤的建议。",
        "sources": [
            "WHO Housing and health guidelines (2018). WHO. https://www.who.int/publications/i/item/9789241550376",
        ],
        "status": "done",
    },
    {
        "keys": ["病媒孳生", "积水", "绿化与水体管理", "媒介传播疾病", "登革热"],
        "q": "Q1",
        "note": "提出强化病媒控制以降低登革热等媒介传播疾病负担的全球对策框架。",
        "sources": [
            "Global vector control response 2017–2030. WHO. https://www.who.int/publications/i/item/9789241512978",
            "Vector-borne diseases (fact sheet). WHO. https://www.who.int/news-room/fact-sheets/detail/vector-borne-diseases",
        ],
        "status": "done",
    },
    {
        "keys": ["食品安全不足", "食源性感染"],
        "q": "Q1",
        "note": "首次全球估计食源性疾病负担，量化不安全食品导致的感染与死亡。",
        "sources": [
            "WHO estimates of the global burden of foodborne diseases: FERG 2007–2015 (2015). WHO. https://www.who.int/publications/i/item/9789241565165",
            "Food safety (fact sheet). WHO. https://www.who.int/news-room/fact-sheets/detail/food-safety",
        ],
        "status": "done",
    },
    {
        "keys": ["人员流动", "交通枢纽", "传染病输入与扩散"],
        "q": "Q1",
        "note": "IHR 为防止疾病跨境输入与扩散提供国际法律框架与口岸/旅行公共卫生措施。",
        "sources": [
            "International Health Regulations (IHR) (health topic). WHO. https://www.who.int/health-topics/international-health-regulations",
        ],
        "status": "done",
    },
    {
        "keys": ["医疗废物", "危险废物处置不当", "感染风险"],
        "q": "Q1",
        "note": "医疗废物管理不当会带来感染等健康风险，需安全处置。",
        "sources": [
            "Health-care waste (fact sheet). WHO. https://www.who.int/news-room/fact-sheets/detail/health-care-waste",
        ],
        "status": "done",
    },

    # ===================== Q2 重点慢性病 =====================
    {
        "keys": ["空气污染", "PM2.5", "NO2", "尾气", "扬尘", "臭氧", "VOCs", "工业排放",
                 "交通排放", "心血管与呼吸系统疾病", "过早死亡"],
        "q": "Q2",
        "note": "更低浓度即可见健康损害；空气污染被认定为缺血性心脏病、卒中、COPD、哮喘、癌症等"
                "的危险因素，每年造成数百万死亡。",
        "sources": [
            "WHO global air quality guidelines: PM, O3, NO2, SO2 and CO (2021). WHO. https://www.who.int/publications/i/item/9789240034228",
            "Ambient (outdoor) air quality and health (fact sheet). WHO. https://www.who.int/news-room/fact-sheets/detail/ambient-(outdoor)-air-quality-and-health",
        ],
        "status": "done",
    },
    {
        "keys": ["家用固体燃料", "替代燃料燃烧", "室内空气污染", "呼吸系统疾病"],
        "q": "Q2",
        "note": "家用燃料燃烧导致室内空气污染并损害呼吸系统健康，提出排放与燃料相关建议。",
        "sources": [
            "WHO guidelines for indoor air quality: household fuel combustion (2014). WHO. https://www.who.int/publications/i/item/9789241548885",
        ],
        "status": "done",
    },
    {
        "keys": ["环境噪声", "噪声", "交通噪声", "高血压", "心血管疾病"],
        "q": "Q2",
        "note": "环境噪声对健康有负面影响（含心血管效应），给出各类噪声源的暴露限值建议。",
        "sources": [
            "Environmental noise guidelines for the European Region (2018). WHO Regional Office for Europe. https://www.who.int/europe/publications/i/item/9789289053563",
        ],
        "status": "done",
    },
    {
        "keys": ["高温", "城市热岛", "热相关疾病", "过早死亡"],
        "q": "Q2",
        "note": "高温暴露加重心血管等疾病并增加过早死亡，需热健康行动计划应对。",
        "sources": [
            "Heat and health (fact sheet). WHO. https://www.who.int/news-room/fact-sheets/detail/climate-change-heat-and-health",
        ],
        "status": "done",
    },
    {
        "keys": ["取暖不足", "室内低温", "能源贫困", "心血管与呼吸系统疾病"],
        "q": "Q2",
        "note": "指南就室内最低温度提出建议，指出室内低温与心血管/呼吸系统疾病风险相关。",
        "sources": [
            "WHO Housing and health guidelines (2018). WHO. https://www.who.int/publications/i/item/9789241550376",
        ],
        "status": "done",
    },
    {
        "keys": ["体力活动不足", "步行性", "步行", "骑行", "主动出行", "久坐",
                 "绿地可达", "心血管", "糖尿病", "肥胖"],
        "q": "Q2",
        "note": "身体活动不足与久坐增加心血管病、糖尿病、肥胖等风险，给出各人群活动量建议。",
        "sources": [
            "WHO guidelines on physical activity and sedentary behaviour (2020). WHO. https://www.who.int/publications/i/item/9789240015128",
        ],
        "status": "done",
    },
    {
        "keys": ["城市绿地可达", "体力活动", "减压", "慢病改善", "健康效益"],
        "q": "Q2",
        "note": "城市绿地通过促进体力活动、减压等带来健康效益，可改善慢性病结局。",
        "sources": [
            "Urban green spaces: a brief for action (2017). WHO Regional Office for Europe. https://www.who.int/europe/publications/i/item/9789289052498",
        ],
        "status": "done",
    },
    {
        "keys": ["膳食", "食物环境", "营养不足", "重点慢性病"],
        "q": "Q2",
        "note": "系统评估膳食与营养因素对主要慢性病的影响，并提出人群层面预防建议。",
        "sources": [
            "Diet, nutrition and the prevention of chronic diseases: report of a joint WHO/FAO expert consultation (TRS 916, 2003). WHO. https://www.who.int/publications/i/item/924120916X",
        ],
        "status": "done",
    },
    {
        "keys": ["住房潮湿", "霉变", "哮喘", "呼吸系统疾病"],
        "q": "Q2",
        "note": "室内潮湿与霉菌与哮喘等呼吸系统疾病相关，建议控制潮湿与霉菌暴露。",
        "sources": [
            "WHO guidelines for indoor air quality: dampness and mould (2009). WHO Regional Office for Europe. https://www.who.int/europe/publications/i/item/9789289041683",
        ],
        "status": "done",
    },
    {
        "keys": ["烟草", "吸烟", "酒精可得性环境", "饮酒", "酗酒", "有害饮酒"],
        "q": "Q2",
        "note": "烟草、有害饮酒是慢性病主要可改变危险因素，FCTC 与控酒战略提出环境/政策层面干预。",
        "sources": [
            "Tobacco (health topic, 含 WHO FCTC 入口). WHO. https://www.who.int/health-topics/tobacco",
            "Alcohol (fact sheet). WHO. https://www.who.int/news-room/fact-sheets/detail/alcohol",
        ],
        "status": "todo",  # TODO: FCTC 正式条约文本专属稳定 URL（fctc.who.int / IRIS）待单独核实
    },

    # ===================== Q3 中毒与伤害 =====================
    {
        "keys": ["道路交通", "交通事故", "道路安全", "道路交通事故", "碰撞", "车祸",
                 "重型货运", "交通伤害", "交通死亡", "头盔", "颅脑损伤"],
        "q": "Q3",
        "note": "全球道路交通伤害负担与风险因素的权威统计与对策。",
        "sources": [
            "Global status report on road safety 2018. WHO. https://www.who.int/publications/i/item/9789241565684",
        ],
        "status": "done",
    },
    {
        "keys": ["危险化学品暴露", "危化品", "化学品", "泄漏", "急性中毒", "伤害"],
        "q": "Q3",
        "note": "化学品暴露可致急性中毒与伤害，WHO/IPCS 提供风险评估与管理框架。",
        "sources": [
            "Chemical safety (health topic, IPCS). WHO. https://www.who.int/health-topics/chemical-safety",
        ],
        "status": "done",
    },
    {
        "keys": ["职业暴露", "工作环境暴露", "职业健康", "职业病", "职业中毒", "工伤"],
        "q": "Q3",
        "note": "量化职业暴露导致的疾病与工伤负担。",
        "sources": [
            "WHO/ILO joint estimates of the work-related burden of disease and injury, 2000–2016 (2021). WHO. https://www.who.int/publications/i/item/9789240034945",
        ],
        "status": "done",
    },
    {
        "keys": ["室内燃烧", "通风不足", "一氧化碳中毒"],
        "q": "Q3",
        "note": "家用燃料不完全燃烧/通风不足产生 CO 等污染物，构成室内空气健康风险。",
        "sources": [
            "WHO guidelines for indoor air quality: household fuel combustion (2014). WHO. https://www.who.int/publications/i/item/9789241548885",
        ],
        "status": "done",
    },
    {
        "keys": ["农药", "化学品可及", "中毒", "自伤"],
        "q": "Q3",
        "note": "限制高危农药等手段可得性是有效的自杀/中毒预防措施。",
        "sources": [
            "Suicide (fact sheet, 含限制手段可得性). WHO. https://www.who.int/news-room/fact-sheets/detail/suicide",
            "Chemical safety (health topic). WHO. https://www.who.int/health-topics/chemical-safety",
        ],
        "status": "done",
    },
    {
        "keys": ["公共空间", "道路设计", "适老化不足", "跌倒", "伤害"],
        "q": "Q3",
        "note": "跌倒是重要伤害原因，环境与适老化设计是关键可改变因素。",
        "sources": [
            "Falls (fact sheet). WHO. https://www.who.int/news-room/fact-sheets/detail/falls",
            "Age-friendly environments (team page). WHO. https://www.who.int/teams/social-determinants-of-health/demographic-change-and-healthy-ageing/age-friendly-environments",
        ],
        "status": "done",
    },

    # ===================== Q4 其他突发公共卫生事件 =====================
    {
        "keys": ["危化品事故", "泄漏", "群体急性暴露事件"],
        "q": "Q4",
        "note": "WHO/IPCS 提供化学事件公共卫生准备与应对框架。",
        "sources": [
            "Chemical safety (health topic, IPCS). WHO. https://www.who.int/health-topics/chemical-safety",
        ],
        "status": "done",
    },
    {
        "keys": ["食品安全事件", "食源性疾病暴发"],
        "q": "Q4",
        "note": "不安全食品可引发食源性疾病暴发，需食品安全体系防控。",
        "sources": [
            "Food safety (fact sheet). WHO. https://www.who.int/news-room/fact-sheets/detail/food-safety",
        ],
        "status": "done",
    },
    {
        "keys": ["饮用水污染事件", "介水疾病暴发"],
        "q": "Q4",
        "note": "水安全计划通过逐步风险管理预防饮用水污染导致的介水疾病暴发。",
        "sources": [
            "Water safety plan manual (WSP manual, 1st ed.). WHO. https://www.who.int/publications/i/item/9789241562638",
        ],
        "status": "done",
    },
    {
        "keys": ["极端高温", "气候事件", "群体性健康事件"],
        "q": "Q4",
        "note": "极端高温可造成群体性超额发病与死亡，需热健康预警系统。",
        "sources": [
            "Heat and health (fact sheet). WHO. https://www.who.int/news-room/fact-sheets/detail/climate-change-heat-and-health",
        ],
        "status": "done",
    },
    {
        "keys": ["大型人群聚集", "突发公共卫生风险"],
        "q": "Q4",
        "note": "大型集会带来传染病及环境健康等多重公共卫生风险，需专门规划与准备。",
        "sources": [
            "Public health for mass gatherings: key considerations (2015). WHO. https://www.who.int/publications/i/item/public-health-for-mass-gatherings-key-considerations",
        ],
        "status": "done",
    },

    # ===================== Q5 人口高质量发展 =====================
    {
        "keys": ["空气暴露", "化学品暴露", "不良出生结局", "生殖健康"],
        "q": "Q5",
        "note": "空气污染与不良出生结局及儿童健康损害相关。",
        "sources": [
            "Air pollution and child health: prescribing clean air (2018). WHO. https://www.who.int/publications/i/item/air-pollution-and-child-health",
        ],
        "status": "done",
    },
    {
        "keys": ["环境条件", "居住条件", "儿童早期发展", "儿童健康"],
        "q": "Q5",
        "note": "环境与居住条件影响儿童早期发展与健康。",
        "sources": [
            "Children's environmental health (health topic). WHO. https://www.who.int/health-topics/children-environmental-health",
        ],
        "status": "done",
    },
    {
        "keys": ["教育", "社会决定因素", "长期健康", "健康素养"],
        "q": "Q5",
        "note": "教育等社会决定因素塑造健康差异与长期健康结局。",
        "sources": [
            "Closing the gap in a generation: health equity through action on the social determinants of health — CSDH final report (2008). WHO. https://www.who.int/publications/i/item/WHO-IER-CSDH-08.1",
        ],
        "status": "done",
    },
    {
        "keys": ["就业", "收入", "社会经济地位", "人口健康", "健康公平"],
        "q": "Q5",
        "note": "就业与收入等社会经济条件是人群健康与健康公平的根本决定因素。",
        "sources": [
            "Closing the gap in a generation — CSDH final report (2008). WHO. https://www.who.int/publications/i/item/WHO-IER-CSDH-08.1",
            "Health equity (health topic). WHO. https://www.who.int/health-topics/health-equity",
        ],
        "status": "done",
    },
    {
        "keys": ["适老环境", "适老设施", "老年健康", "健康老龄化"],
        "q": "Q5",
        "note": "适老环境与设施支持健康老龄化和老年功能发挥。",
        "sources": [
            "Ageing and health (fact sheet). WHO. https://www.who.int/news-room/fact-sheets/detail/ageing-and-health",
            "Age-friendly environments (team page). WHO. https://www.who.int/teams/social-determinants-of-health/demographic-change-and-healthy-ageing/age-friendly-environments",
        ],
        "status": "done",
    },

    # ===================== Q6 健康环境 =====================
    {
        "keys": ["大气质量改变", "环境健康"],
        "q": "Q6",
        "note": "空气质量改变直接影响环境健康，2021 版指南给出污染物暴露限值。",
        "sources": [
            "WHO global air quality guidelines (2021). WHO. https://www.who.int/publications/i/item/9789240034228",
        ],
        "status": "done",
    },
    {
        "keys": ["饮用水水质", "饮用水", "地下水", "水污染", "环境健康"],
        "q": "Q6",
        "note": "饮用水水质是环境健康核心要素，指南提供水质安全管理框架。",
        "sources": [
            "Guidelines for drinking-water quality (2022). WHO. https://www.who.int/publications/i/item/9789240045064",
        ],
        "status": "done",
    },
    {
        "keys": ["食品安全", "环境健康"],
        "q": "Q6",
        "note": "食品安全是环境健康组成部分，不安全食品造成可观疾病负担。",
        "sources": [
            "Food safety (fact sheet). WHO. https://www.who.int/news-room/fact-sheets/detail/food-safety",
        ],
        "status": "done",
    },
    {
        "keys": ["环境噪声", "噪声", "交通噪声", "环境健康", "生活质量"],
        "q": "Q6",
        "note": "环境噪声影响健康与生活质量，给出各噪声源暴露限值建议。",
        "sources": [
            "Environmental noise guidelines for the European Region (2018). WHO Regional Office for Europe. https://www.who.int/europe/publications/i/item/9789289053563",
        ],
        "status": "done",
    },
    {
        "keys": ["土壤污染", "重金属污染", "铅暴露", "环境健康"],
        "q": "Q6",
        "note": "铅等重金属暴露无安全阈值，损害神经发育等健康；化学品安全提供管理框架。",
        "sources": [
            "Lead poisoning (fact sheet). WHO. https://www.who.int/news-room/fact-sheets/detail/lead-poisoning-and-health",
            "Chemical safety (health topic). WHO. https://www.who.int/health-topics/chemical-safety",
        ],
        "status": "done",
    },
    {
        "keys": ["固体废物", "危废处置", "环境卫生"],
        "q": "Q6",
        "note": "危险/医疗废物处置不当带来环境与健康风险；城市生活固废与健康 WHO 无独立旗舰文档。",
        "sources": [
            "Health-care waste (fact sheet). WHO. https://www.who.int/news-room/fact-sheets/detail/health-care-waste",
        ],
        "status": "todo",  # TODO: 城市生活固废与健康 WHO 官网无独立文档，待系统综述/meta 补
    },

    # ===================== Q7 健康生活方式与社会心理健康 =====================
    {
        "keys": ["绿地", "开放空间", "体力活动", "减压", "心理健康"],
        "q": "Q7",
        "note": "城市绿地通过促进体力活动与减压改善身心健康。",
        "sources": [
            "Urban green spaces: a brief for action (2017). WHO Regional Office for Europe. https://www.who.int/europe/publications/i/item/9789289052498",
        ],
        "status": "done",
    },
    {
        "keys": ["步行性", "街道设计", "公共空间设计", "主动出行", "活动方式"],
        "q": "Q7",
        "note": "支持步行/骑行的环境与设计促进主动出行和身体活动。",
        "sources": [
            "WHO guidelines on physical activity and sedentary behaviour (2020). WHO. https://www.who.int/publications/i/item/9789240015128",
        ],
        "status": "done",
    },
    {
        "keys": ["环境噪声", "噪声", "交通噪声", "睡眠干扰", "烦扰", "心理健康", "主观健康"],
        "q": "Q7",
        "note": "环境噪声导致睡眠干扰与烦扰，影响心理与主观健康。",
        "sources": [
            "Environmental noise guidelines for the European Region (2018). WHO Regional Office for Europe. https://www.who.int/europe/publications/i/item/9789289053563",
        ],
        "status": "done",
    },
    {
        "keys": ["社会隔离", "社区凝聚力下降", "心理健康", "幸福感"],
        "q": "Q7",
        "note": "社会因素影响心理健康；CSDH 可部分支撑，WHO 较新 Social connection 委员会报告待核实。",
        "sources": [
            "Closing the gap in a generation — CSDH final report (2008). WHO. https://www.who.int/publications/i/item/WHO-IER-CSDH-08.1",
        ],
        "status": "todo",  # TODO: 核实 WHO 'Social isolation and loneliness / Social connection' 主题页稳定 URL（知识截止后发布）
    },
    {
        "keys": ["拆迁", "人口置换", "社区网络破坏", "心理压力"],
        "q": "Q7",
        "note": "居住环境变动与社区网络破坏构成心理压力源；住房与健康、SDH 提供证据基础。",
        "sources": [
            "WHO Housing and health guidelines (2018). WHO. https://www.who.int/publications/i/item/9789241550376",
            "Closing the gap in a generation — CSDH final report (2008). WHO. https://www.who.int/publications/i/item/WHO-IER-CSDH-08.1",
        ],
        "status": "done",
    },
    {
        "keys": ["经济困难", "可负担性下降", "心理压力", "行为风险"],
        "q": "Q7",
        "note": "经济困难与可负担性下降是心理压力与不良行为风险的社会决定因素。",
        "sources": [
            "Closing the gap in a generation — CSDH final report (2008). WHO. https://www.who.int/publications/i/item/WHO-IER-CSDH-08.1",
        ],
        "status": "done",
    },

    # ===================== Q8 卫生健康投入保障与医疗保险 =====================
    {
        "keys": ["卫生筹资", "投入安排", "公共卫生服务能力", "医疗服务能力"],
        "q": "Q8",
        "note": "卫生筹资安排决定公共卫生与医疗服务的供给能力。",
        "sources": [
            "Health financing (health topic). WHO. https://www.who.int/health-topics/health-financing",
        ],
        "status": "done",
    },
    {
        "keys": ["自付负担", "保障水平", "因病致贫", "服务利用"],
        "q": "Q8",
        "note": "高自付与低保障导致灾难性卫生支出、因病致贫并抑制服务利用。",
        "sources": [
            "Universal health coverage (UHC) (fact sheet). WHO. https://www.who.int/news-room/fact-sheets/detail/universal-health-coverage-(uhc)",
        ],
        "status": "done",
    },
    {
        "keys": ["经济结构", "就业", "参保能力", "缴费能力"],
        "q": "Q8",
        "note": "经济结构与就业状况影响参保与缴费能力，是 UHC 与健康公平的相关因素。",
        "sources": [
            "Closing the gap in a generation — CSDH final report (2008). WHO. https://www.who.int/publications/i/item/WHO-IER-CSDH-08.1",
            "Universal health coverage (UHC) (fact sheet). WHO. https://www.who.int/news-room/fact-sheets/detail/universal-health-coverage-(uhc)",
        ],
        "status": "done",
    },

    # ===================== Q9 优质医疗资源合理配置与利用 =====================
    {
        "keys": ["设施布局", "规划", "医疗资源地理可达性"],
        "q": "Q9",
        "note": "设施布局与规划决定医疗资源地理可及性，是 UHC 服务可及维度的内容。",
        "sources": [
            "Universal health coverage (UHC) (fact sheet). WHO. https://www.who.int/news-room/fact-sheets/detail/universal-health-coverage-(uhc)",
        ],
        "status": "done",
    },
    {
        "keys": ["区域发展不均", "资源配置公平性"],
        "q": "Q9",
        "note": "区域发展不均带来卫生人力与资源配置的公平性问题。",
        "sources": [
            "Health workforce (health topic). WHO. https://www.who.int/health-topics/health-workforce",
            "Health equity (health topic). WHO. https://www.who.int/health-topics/health-equity",
        ],
        "status": "done",
    },
    {
        "keys": ["急救网络", "转诊网络", "资源利用效率", "时效"],
        "q": "Q9",
        "note": "急诊与院前急救/转诊系统影响资源利用效率与救治时效。",
        "sources": [
            "Emergency care (health topic). WHO. https://www.who.int/health-topics/emergency-care",
        ],
        "status": "done",
    },

    # ===================== Q10 医疗卫生服务质量、利用、公平与可及性 =====================
    {
        "keys": ["设施空间布局", "交通可达", "就医地理可及性"],
        "q": "Q10",
        "note": "设施布局与交通可达性决定就医地理可及性，是 UHC 服务覆盖的核心维度。",
        "sources": [
            "Universal health coverage (UHC) (fact sheet). WHO. https://www.who.int/news-room/fact-sheets/detail/universal-health-coverage-(uhc)",
        ],
        "status": "done",
    },
    {
        "keys": ["经济可负担性", "服务利用", "放弃就医"],
        "q": "Q10",
        "note": "经济可负担性低导致灾难性卫生支出与放弃就医，抑制服务利用。",
        "sources": [
            "Universal health coverage (UHC) (fact sheet). WHO. https://www.who.int/news-room/fact-sheets/detail/universal-health-coverage-(uhc)",
        ],
        "status": "done",
    },
    {
        "keys": ["弱势群体", "健康公平", "服务利用差距"],
        "q": "Q10",
        "note": "弱势群体面临服务利用差距，健康公平与社会决定因素提供分析框架。",
        "sources": [
            "Health equity (health topic). WHO. https://www.who.int/health-topics/health-equity",
            "Closing the gap in a generation — CSDH final report (2008). WHO. https://www.who.int/publications/i/item/WHO-IER-CSDH-08.1",
        ],
        "status": "done",
    },
    {
        "keys": ["急救可达", "反应时间", "救治时效", "结局"],
        "q": "Q10",
        "note": "急诊与院前急救系统的反应时间影响救治时效与健康结局。",
        "sources": [
            "Emergency care (health topic). WHO. https://www.who.int/health-topics/emergency-care",
        ],
        "status": "done",
    },
    {
        "keys": ["服务质量", "患者安全", "健康结果"],
        "q": "Q10",
        "note": "医疗服务质量与患者安全直接影响健康结果。",
        "sources": [
            "Quality health services (fact sheet). WHO. https://www.who.int/news-room/fact-sheets/detail/quality-health-services",
        ],
        "status": "done",
    },

    # ============= 扩库(2026-06):WHO 补充 + 本土权威。均经联网核实为现行有效来源。=============
    {
        "keys": ["二噁英", "持久性有机污染物", "焚烧排放", "致癌物"],
        "q": "Q2",
        "note": "二噁英为高毒持久性有机污染物,长期暴露与癌症及生殖、发育、免疫损害相关;"
                "垃圾焚烧等是其排放来源之一,需控制排放。",
        "sources": [
            "Dioxins (fact sheet). WHO. https://www.who.int/news-room/fact-sheets/detail/dioxins-and-their-effects-on-human-health",
        ],
        "status": "done",
    },
    {
        "keys": ["气候变化", "温室气体", "极端天气", "热浪"],
        "q": "Q4",
        "note": "气候变化通过极端高温、极端天气事件等影响人群健康;WHO 估计 2030 年起"
                "每年或导致约 25 万例额外死亡,需纳入突发公共卫生事件应对。",
        "sources": [
            "Climate change (fact sheet). WHO. https://www.who.int/news-room/fact-sheets/detail/climate-change-and-health",
        ],
        "status": "done",
    },
    {
        "keys": ["重金属", "土壤污染", "建设用地", "重金属暴露", "土壤重金属"],
        "q": "Q3",
        "note": "国家标准规定保护人体健康的建设用地土壤污染风险筛选值与管制值;镉、铅、砷等"
                "重金属与有机污染物经土壤、扬尘或食物链暴露可致中毒与慢性健康损害,据此开展风险管控。",
        "sources": [
            "土壤环境质量 建设用地土壤污染风险管控标准(试行) GB 36600-2018. 生态环境部. "
            "https://www.mee.gov.cn/ywgz/fgbz/bz/bzwb/trhj/201807/t20180703_446027.shtml",
        ],
        "status": "done",
    },
    {
        "keys": ["大气污染物", "空气质量", "PM2.5", "大气污染", "环境空气"],
        "q": "Q2",
        "note": "我国现行环境空气质量标准,规定 PM2.5/PM10/SO2/NO2 等浓度限值"
                "(2026 版收紧至接近 WHO 过渡值),是大气污染健康风险管控的国家依据。",
        "sources": [
            "环境空气质量标准 GB 3095-2026. 生态环境部. "
            "https://www.mee.gov.cn/ywgz/fgbz/bz/bzwb/dqhjbh/dqhjzlbz/202602/t20260225_1144419.shtml",
        ],
        "status": "done",
    },
    {
        "keys": ["生活饮用水", "饮用水", "供水", "地下水", "水污染", "水质标准"],
        "q": "Q6",
        "note": "我国现行生活饮用水卫生标准(97 项指标),规定饮用水水质与供水卫生要求,"
                "是保障饮水安全、防控介水健康风险的国家依据。",
        "sources": [
            "生活饮用水卫生标准 GB 5749-2022. 国家标准. "
            "https://openstd.samr.gov.cn/bzgk/std/newGbInfo?hcno=99E9C17E3547A3C0CE2FD1FFD9F2F7BE",
        ],
        "status": "done",
    },
    {
        "keys": ["噪声", "环境噪声", "声环境", "交通噪声", "噪声限值"],
        "q": "Q6",
        "note": "我国现行声环境质量标准,按五类功能区规定环境噪声限值;噪声暴露与睡眠干扰、"
                "心血管等健康影响相关,是噪声污染防控的国家依据。",
        "sources": [
            "声环境质量标准 GB 3096-2008. 生态环境部. "
            "https://www.mee.gov.cn/ywgz/fgbz/bz/bzwb/wlhj/shjzlbz/200809/t20080917_128815.htm",
        ],
        "status": "done",
    },
]  # ← CARDS 列表结束

# 中国开展健康影响评估(HIA)的制度依据(供报告脚注/说明引用,非按题匹配的机制卡)。
INSTITUTIONAL_BASIS = (
    "《“健康中国2030”规划纲要》(中共中央、国务院,2016)提出全面建立健康影响评价评估制度,"
    "系统评估经济社会发展规划与政策、重大工程项目对健康的影响。"
    "https://www.nhc.gov.cn/guihuaxxs/c100132/201610/cef9821abcfc4544bb27e2bc533bd7cf.shtml"
)


# ----------------------- 辅助函数 -----------------------

def cards_by_q(q):
    """按题号筛选卡片，如 cards_by_q('Q2')。"""
    return [c for c in CARDS if c["q"] == q]


def todo_cards():
    """返回所有 WHO 官网确无/待核实（status='todo'）的卡片。"""
    return [c for c in CARDS if c["status"] == "todo"]


def all_sources():
    """去重后的所有来源 URL 列表（便于核对引用）。"""
    seen, out = set(), []
    for c in CARDS:
        for s in c["sources"]:
            if s not in seen:
                seen.add(s)
                out.append(s)
    return out


# ----------------------- 来源分级(证据等级) -----------------------
# 客观依据来源标题判定证据层级(WHO 与国内权威),rank 越小分量越重。
# 注:不臆造内容,仅按来源类型归级,供"证据可溯源"显示与排序用。
_TIER_RULES = [
    (1, "WHO 指南", ("guideline", "guidelines", "manual", "water safety plan")),
    (2, "全球估计/状况报告", ("estimates", "global burden", "global status",
                              "burden of disease")),
    (2, "WHO 报告/共识", ("csdh", "closing the gap", "consultation",
                          "brief for action", "key considerations")),
    (3, "WHO 事实页/主题页", ("fact sheet", "health topic", "(health topic",
                              "team page", "ageing and health")),
]


def source_tier(src):
    """返回单条来源的 (rank, label)。先判国内权威(国标/国家政策),再判 WHO,否则归'其他来源'。"""
    s = src or ""
    sl = s.lower()
    if "GB " in s or "GB/T" in s or "国家标准" in s:        # 国家强制/推荐标准
        return 1, "国家标准"
    if "规划纲要" in s or "国务院" in s or "中共中央" in s:   # 国家级政策/规划
        return 1, "国家政策/规划"
    if "技术导则" in s or "技术指南" in s or "卫生健康委" in s or "疾控" in s:
        return 2, "国内指南/部门"
    for rank, label, keys in _TIER_RULES:
        if any(k in sl for k in keys):
            return rank, label
    if "who" in sl or "世界卫生组织" in s:
        return 2, "WHO 资料"
    return 2, "其他来源"


def card_tier(card):
    """卡片的最高证据等级(取其各来源中分量最重的)。返回 (rank, label)。"""
    best = (3, "WHO 事实页/主题页")
    for s in card.get("sources", []):
        t = source_tier(s)
        if t[0] < best[0]:
            best = t
    return best


# ----------------------- app 匹配接口 -----------------------

# 结果/泛化词停用表:这些是"健康结果"或过于宽泛的词,几乎每条同题路径都含,
# 不能作为"决定因素"匹配依据(否则如"慢性病"会让烟草/酒精卡误中所有 Q2 路径)。
_STOP_KEYS = {
    "慢性病", "重点慢性病", "慢性病发生发展", "健康", "环境健康", "健康结果", "健康效益",
    "健康损害", "健康风险", "疾病", "呼吸系统疾病", "心血管", "心血管疾病", "过早死亡",
    "死亡", "生活质量", "心理健康", "服务利用", "传染病", "感染", "感染风险",
    "中毒", "伤害", "受伤", "中暑", "损害", "突发", "风险", "病",
}

# 同义词组(系统化召回杠杆):同一"决定因素"AI 可能用不同措辞表达。
# 卡片关键词若落在某组,则该组**任一**词出现在因果链中即视为命中——
# 一处维护、所有相关卡片自动受益。组内只放真正同义的"决定因素"词,避免误配。
_SYN_GROUPS = [
    {"道路交通", "交通事故", "道路交通事故", "道路安全", "交通安全", "车祸", "碰撞", "交通伤害"},
    {"空气污染", "大气污染", "大气污染物", "尾气", "机动车尾气", "颗粒物", "PM2.5", "PM10",
     "雾霾", "空气质量", "臭氧", "VOCs", "工业排放", "交通排放", "扬尘", "环境空气"},
    {"环境噪声", "噪声", "噪音", "交通噪声", "施工噪声", "声环境", "噪声污染"},
    {"体力活动", "身体活动", "体育锻炼", "锻炼", "步行", "步行性", "骑行", "主动出行",
     "久坐", "户外活动"},
    {"烟草", "吸烟", "二手烟", "卷烟", "控烟"},
    {"酒精", "饮酒", "酗酒", "有害饮酒", "酒精可得性环境"},
    {"居住拥挤", "拥挤", "集体宿舍", "居住密度", "人口聚集", "群居"},
    {"危险化学品", "危化品", "化学品", "有毒化学品", "危险化学品暴露", "化学品泄漏"},
    {"饮用水", "生活饮用水", "饮用水水质", "地下水", "供水", "水污染", "介水"},
    {"重金属", "土壤污染", "土壤重金属", "重金属污染", "镉", "铅暴露", "砷", "汞污染", "建设用地"},
    {"绿地", "城市绿地", "绿地可达", "公园", "开放空间", "绿化", "绿色空间", "公共空间"},
    {"高温", "热浪", "城市热岛", "极端高温", "热暴露", "热环境"},
    {"社会隔离", "社会孤立", "孤独", "社区凝聚力", "社会支持", "社会网络", "社区网络"},
    {"食品安全", "食源性", "食物中毒", "食品卫生", "食源性感染", "食品安全不足"},
    {"职业暴露", "职业病", "职业健康", "工伤", "工作环境暴露", "职业中毒"},
    {"跌倒", "适老化", "无障碍", "适老化不足", "适老设施", "适老环境"},
    {"室内空气污染", "家用固体燃料", "固体燃料", "替代燃料燃烧", "一氧化碳", "通风不足", "室内燃烧"},
    {"住房潮湿", "潮湿", "霉菌", "霉变"},
    {"收入", "就业", "失业", "经济压力", "社会经济地位", "生计", "可负担性", "经济困难"},
    {"医疗可及性", "就医", "医疗服务可及", "卫生服务可及", "医疗资源地理可达性", "地理可及性"},
    {"二噁英", "持久性有机污染物", "焚烧排放", "焚烧", "垃圾焚烧", "致癌物"},
    {"气候变化", "温室气体", "极端天气", "甲烷", "碳排放"},
    {"病媒孳生", "积水", "蚊蝇孳生", "蚊蝇滋生", "蚊蝇", "鼠害", "病媒", "媒介传播"},
    {"环境卫生", "卫生设施", "污水处理不足", "粪口途径传染病", "给排水"},
]
# term -> 该组全部词(tuple)。卡片 key 命中此索引时,用整组去匹配链文。
_SYN_INDEX = {}
for _g in _SYN_GROUPS:
    _gt = tuple(_g)
    for _t in _g:
        _SYN_INDEX.setdefault(_t, _gt)


def _key_hits(key, text):
    """卡片某关键词是否命中链文:本身或其同义词组任一词出现即算(≥2字、非停用词)。"""
    for t in _SYN_INDEX.get(key, (key,)):
        if len(t) >= 2 and t not in _STOP_KEYS and t in text:
            return True
    return False


def match(pathway):
    """为一条因果路径匹配证据卡片(同题号 + 决定因素关键词/同义词正向命中)。最多 2 张。
    返回 [{note, sources, status, tier}, ...];匹配不到 → []（显示端标'证据待补')。"""
    chain = pathway.get("chain") or []
    det = chain[:-1] if len(chain) > 1 else chain      # 去掉末端健康结果(≈题目),只在决定因素段匹配
    text = " ".join(det)                               # 否则"心血管病"等结果词会误中同题各卡
    qs = f"Q{pathway.get('outcome_q')}"
    out = []
    for c in CARDS:
        if c["q"] != qs:
            continue
        # 仅用"决定因素"关键词(≥2字、非结果/泛化词),经同义词组扩展后正向命中链文。
        if any(_key_hits(k, text) for k in c["keys"] if len(k) >= 2 and k not in _STOP_KEYS):
            out.append({"note": c.get("note", ""), "sources": c["sources"],
                        "status": c.get("status", "done"), "tier": card_tier(c)[1]})
        if len(out) >= 2:
            break
    return out


def annotate(pathways):
    """给每条路径加 cards 字段(可能为空 → 显示端标'机制推断·待专家补证')。"""
    for p in pathways:
        p["cards"] = match(p)
    return pathways


def catalog_lines():
    """供 LLM 语义匹配的卡片目录(编号 + 题号 + 决定因素关键词)。"""
    return [f"C{i} [{c['q']}] {'/'.join(c['keys'])}" for i, c in enumerate(CARDS)]


def card_ref(i):
    """按目录编号取卡片的显示信息(note/sources/status/tier),供匹配后挂到路径上。"""
    c = CARDS[i]
    return {"note": c.get("note", ""), "sources": c["sources"],
            "status": c.get("status", "done"), "q": c["q"], "tier": card_tier(c)[1]}


def gaps(pathways):
    """汇总当前匹配不到证据卡片的(机制链 → 题号)去重清单,供专家批量补卡。
    按"题号 + 终末两级链路"去重(一张卡片大致对应一条终末机制链)。"""
    seen, out = set(), []
    for p in pathways:
        if p.get("cards"):
            continue
        chain, q = p.get("chain") or [], p.get("outcome_q")
        if not chain or not q:
            continue
        sig = (q, "→".join(chain[-2:]))
        if sig in seen:
            continue
        seen.add(sig)
        out.append({"q": q, "chain": list(chain)})
    out.sort(key=lambda g: g["q"])
    return out


if __name__ == "__main__":
    print(f"卡片总数: {len(CARDS)}")
    print(f"已取证(done): {sum(1 for c in CARDS if c['status']=='done')}")
    print(f"待补(todo)  : {sum(1 for c in CARDS if c['status']=='todo')}")
    for c in todo_cards():
        print(f"  [todo] {c['q']} - {'/'.join(c['keys'])}")
