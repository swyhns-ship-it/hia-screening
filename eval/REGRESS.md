# HIA 引擎回归测试套件

固化的金标准评测,**每次改引擎(提示词/门控/证据卡)后跑一遍,自动出假阴/假阳率并与基线对比**,防止"修 A 坏 B"。

## 三步用法
```bash
# ① 跑全量(调 DeepSeek,约 100 份;out/ 已 gitignore)
.venv/Scripts/python.exe eval/run_eval.py "E:\projects\test"

# ② 算分 + 与基线对比(标出 ✅已修复 / ⚠新增问题)
.venv/Scripts/python.exe eval/score.py

# ③ 确认本版更好后,把当前结果固化为新基线
.venv/Scripts/python.exe eval/score.py --save-baseline
```

## 组成
- `labels.py` — 金标准标签(A 应有路径 / B 应≈0 / X 边界不计率 / C 抽取失败跳过)。**改判定口径或新增样本就改这里。**
- `run_eval.py` — 批量跑引擎,产 `out/*.json|md` + `out/_SUMMARY.md`。
- `score.py` — 读 out + labels,算混淆矩阵;有 `baseline.json` 则 diff 出判定变化的样本。
- `baseline.json` — 基线快照(随仓库),每份的 路径数+判定。
- `_ground_truth.md` — 人工标注依据(给人读,labels.py 是其机器版)。

## 判定口径(labels.py)
- **假阴** = A 正样本却 0 路径(漏报实体减排/环境/民生政策)。
- **假阳** = B 负样本却 ≥`FALSE_POS_MIN`(默认2)条(给纯程序/价格/金融政策硬造健康路径)。
- **边界 X** 不计入率,只在基线 diff 里监控其变化(节能审查/低空经济/油气设施/能效水效目录等)。
- 率只在 A/B 高置信样本上算,所以可信。

## 维护
- 测试集默认 `E:\projects\test`(100 份发改委政策,本机)。换集时同步更新 `labels.py` 关键词。
- 新增政策样本:放进测试目录 → 在 `labels.py` 归类 → 重跑 ②③。
- 边界判断有争议的,先归 X(只监控不计率),积累后再决定 A/B。
