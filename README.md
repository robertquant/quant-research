# Quant Research - 量化策略研究与回测系统

[![GitHub stars](https://img.shields.io/github/stars/robertquant/quant-research?style=social)](https://github.com/robertquant/quant-research/stargazers)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)

> 🎯 **目标**: 建立系统化的A股量化策略研究框架，追求数据驱动、逻辑严谨、风险可控的投资决策

---

## 📊 策略库

### 已验证策略

| 策略名称 | 类型 | 夏普比率 | 年化收益 | 最大回撤 | 状态 |
|---------|------|---------|---------|---------|------|
| **ETF轮动策略 v4.0** | 趋势跟踪 | 0.97 | 33.83% | -27.90% | ✅ 可用 |
| 小市值因子策略 | 多因子 | - | - | - | 🔄 开发中 |
| 可转债双低策略 | 套利 | - | - | - | ⏳ 待开发 |

### 策略详情

#### ETF轮动策略 v4.0
- **核心逻辑**: 30日动量轮动 + 60日均线过滤 + -8%硬止损
- **标的池**: 沪深300/中证500/创业板/科创50 ETF
- **回测周期**: 2015-2026年（11年）
- **胜率**: 47.9% | **盈亏比**: 2.25

[查看详细回测报告 →](backtests/etf_rotation_v4.png)

---

## 🛠️ 技术栈

- **数据获取**: 腾讯财经API（免费稳定）
- **数据处理**: pandas, numpy
- **回测框架**: 自研轻量级框架
- **可视化**: matplotlib
- **缓存系统**: 本地pickle缓存

---

## 🚀 快速开始

### 安装依赖

```bash
pip install pandas numpy matplotlib requests
```

### 运行回测

```bash
# ETF轮动策略回测
cd strategies
python3 etf_rotation_v4.py
```

### 使用数据缓存

```python
from data.data_cache import get_data

# 获取沪深300ETF历史数据
df = get_data('sh510300', '20200101', '20241231')
print(df.head())
```

---

## 📁 项目结构

```
quant-research/
├── strategies/          # 策略代码
│   ├── etf_rotation_v4.py      # ETF轮动策略
│   ├── smallcap_quick_test.py  # 小市值因子
│   └── ...
├── backtests/           # 回测结果
│   ├── etf_rotation_v4.png
│   └── ...
├── data/                # 数据模块
│   ├── data_cache.py    # 数据缓存系统
│   └── ...
├── templates/           # 模板
│   ├── strategy_template.md
│   └── journal_template.md
├── notes/               # 研究笔记
└── README.md
```

---

## 📚 研究随笔

基于探索过程中的思考与发现：

- [腾讯财经：被忽视的免费量化数据源](https://robertquant.github.io/blog/posts/013-tencent-finance.html)
- [AKShare：Python开源金融数据接口库深度调研](https://robertquant.github.io/blog/posts/012-akshare-deep-dive.html)

[查看更多随笔 →](https://robertquant.github.io/blog/)

---

## 🎯 投资目标

基于方案A（稳健型）：
- **年化收益**: 12-18%
- **夏普比率**: >1.5
- **最大回撤**: <10%
- **核心理念**: 市场中性，不赌方向，赚定价偏差

---

## ⚠️ 风险提示

1. **回测不等于实盘**: 历史数据无法完全预测未来
2. **滑点与成本**: 实际交易存在摩擦成本，回测已考虑0.1%双边成本
3. **市场变化**: 策略有效性可能随市场环境变化而衰减
4. **过度拟合风险**: 参数优化需警惕过拟合

---

## 🤝 参与贡献

欢迎提交Issue和PR：
- 策略优化建议
- 新策略实现
- Bug修复
- 文档改进

---

## 📄 开源协议

本项目采用 [MIT License](LICENSE) 开源协议。

---

## 🔗 相关链接

- **个人网站**: [robertquant.github.io](https://robertquant.github.io)
- **研究随笔**: [robertquant.github.io/blog](https://robertquant.github.io/blog)
- **GitHub**: [github.com/robertquant](https://github.com/robertquant)

---

> **免责声明**: 本项目仅供学习研究使用，不构成投资建议。投资有风险，入市需谨慎。

---

*持续探索，迭代优化*  
*Last Updated: 2026-03-24*
