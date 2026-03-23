# 量化主动探索体系 - 架构说明

## 已搭建的组件

### 1. 目录结构
```
quant-research/
├── README.md           # 研究方向和配置
├── scripts/
│   └── quant_explorer.py   # 核心探索引擎 ⭐
├── notes/              # 研究笔记（每日自动生成）
├── reports/            # 回测报告
└── backtests/          # 回测数据
```

### 2. 核心功能（quant_explorer.py）
- **市场扫描**: 自动分析MACD、RSI、均线、波动率
- **信号识别**: 金叉/死叉、超买/超卖
- **自动笔记**: 生成Markdown格式的研究笔记
- **快速回测**: 双均线策略历史验证

### 3. 心跳任务（HEARTBEAT.md）
已配置定期自动执行：
- 交易日盘中扫描信号
- 收盘后策略验证
- 周度策略研究

## 使用方式

### 手动触发探索
```bash
cd ~/.openclaw/workspace/quant-research
python3 scripts/quant_explorer.py
```

### 查看生成的笔记
```bash
ls -la ~/.openclaw/workspace/quant-research/notes/
```

### 回测现有策略
```bash
cd ~/.openclaw/workspace/skills/quant-trading
python3 scripts/golden_cross.py --code 600519 --start 20240101 --end 20241231
python3 scripts/macd_strategy.py --code 002594 --days 180
python3 scripts/scan_signals.py --strategy all
```

## 下一步扩展方向

### 短期（1-2周）
1. **策略参数优化**: 网格搜索最佳均线周期
2. **复合策略**: MACD+成交量+RSI组合
3. **ETF轮动**: 宽基指数动量筛选

### 中期（1个月）
1. **可转债双低**: 自动筛选+回测
2. **财报策略**: 超预期事件驱动
3. **波动率策略**: 收敛突破识别

### 长期（持续）
1. **策略组合**: 多策略仓位分配
2. **风险控制**: 动态止损+回撤控制
3. **实盘模拟**: 模拟交易验证

## 研究与思考输出

每次心跳执行后，我会：
1. 生成技术信号扫描笔记
2. 记录策略回测结果
3. 写下主观分析和下一步想法
4. 如果发现明显机会，主动推送给你

## 交互方式

你可以随时问我：
- "帮我看看600519的技术面" → 即时分析
- "回测一下MACD策略在比亚迪上的效果" → 运行回测
- "最近量化研究有什么发现？" → 查看笔记总结
- "我想研究XXX策略" → 添加新研究方向

这个体系会持续运转，默默积累研究数据和洞察。
