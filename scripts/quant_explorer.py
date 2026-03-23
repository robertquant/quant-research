#!/usr/bin/env python3
"""
量化策略主动探索引擎
功能：
1. 定期扫描市场信号
2. 回测验证新策略想法
3. 生成研究笔记
4. 发现套利机会
"""

import akshare as ak
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json
import os

# 配置
RESEARCH_DIR = os.path.expanduser("~/.openclaw/workspace/quant-research")
NOTES_DIR = f"{RESEARCH_DIR}/notes"
REPORTS_DIR = f"{RESEARCH_DIR}/reports"

# 标的池
WATCHLIST = {
    "stocks": ["600519", "000001", "002594", "300750", "601318", "600036"],
    "etfs": ["510300", "510500", "159915", "512480", "518880"],
    "indices": ["sh000001", "sz399001", "sz399006"]
}

def get_stock_data(code, days=60):
    """获取股票历史数据"""
    try:
        df = ak.stock_zh_a_hist(symbol=code, period="daily", 
                                start_date=(datetime.now() - timedelta(days=days)).strftime("%Y%m%d"),
                                end_date=datetime.now().strftime("%Y%m%d"),
                                adjust="qfq")
        return df
    except Exception as e:
        print(f"获取{code}数据失败: {e}")
        return None

def analyze_trend(code, name=""):
    """分析股票趋势状态"""
    df = get_stock_data(code, days=60)
    if df is None or len(df) < 20:
        return None
    
    # 计算均线
    df['MA5'] = df['收盘'].rolling(5).mean()
    df['MA10'] = df['收盘'].rolling(10).mean()
    df['MA20'] = df['收盘'].rolling(20).mean()
    df['MA60'] = df['收盘'].rolling(60).mean()
    
    # 计算MACD
    exp1 = df['收盘'].ewm(span=12, adjust=False).mean()
    exp2 = df['收盘'].ewm(span=26, adjust=False).mean()
    df['MACD'] = exp1 - exp2
    df['Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
    
    # 计算RSI
    delta = df['收盘'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df['RSI'] = 100 - (100 / (1 + rs))
    
    # 计算波动率（ATR简化版）
    df['TR'] = np.maximum(df['最高'] - df['最低'], 
                          np.maximum(abs(df['最高'] - df['收盘'].shift(1)),
                                   abs(df['最低'] - df['收盘'].shift(1))))
    df['ATR'] = df['TR'].rolling(14).mean()
    
    latest = df.iloc[-1]
    prev = df.iloc[-2] if len(df) > 1 else latest
    
    # 趋势判断
    trend = "震荡"
    if latest['MA5'] > latest['MA20'] and latest['MA20'] > latest['MA60']:
        trend = "上升趋势"
    elif latest['MA5'] < latest['MA20'] and latest['MA20'] < latest['MA60']:
        trend = "下降趋势"
    
    # MACD信号
    macd_signal = "中性"
    if latest['MACD'] > latest['Signal'] and prev['MACD'] <= prev['Signal']:
        macd_signal = "金叉（买入）"
    elif latest['MACD'] < latest['Signal'] and prev['MACD'] >= prev['Signal']:
        macd_signal = "死叉（卖出）"
    elif latest['MACD'] > latest['Signal']:
        macd_signal = "多头"
    else:
        macd_signal = "空头"
    
    # RSI状态
    rsi_status = "中性"
    if latest['RSI'] > 70:
        rsi_status = "超买"
    elif latest['RSI'] < 30:
        rsi_status = "超卖"
    
    return {
        "code": code,
        "name": name,
        "date": latest['日期'],
        "price": round(latest['收盘'], 2),
        "trend": trend,
        "macd_signal": macd_signal,
        "rsi": round(latest['RSI'], 2),
        "rsi_status": rsi_status,
        "volatility": round(latest['ATR'] / latest['收盘'] * 100, 2),  # 百分比波动率
        "ma5": round(latest['MA5'], 2),
        "ma20": round(latest['MA20'], 2),
        "volume_ratio": round(latest['成交量'] / df['成交量'].rolling(20).mean().iloc[-1], 2)
    }

def scan_market_signals():
    """扫描市场信号"""
    print("=" * 60)
    print(f"市场信号扫描 - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 60)
    
    signals = []
    
    for code in WATCHLIST["stocks"]:
        analysis = analyze_trend(code)
        if analysis:
            signals.append(analysis)
            print(f"\n【{analysis['code']}】{analysis.get('name', '')}")
            print(f"  价格: {analysis['price']} | 趋势: {analysis['trend']}")
            print(f"  MACD: {analysis['macd_signal']} | RSI: {analysis['rsi']}({analysis['rsi_status']})")
            print(f"  波动率: {analysis['volatility']}% | 量比: {analysis['volume_ratio']}")
    
    return signals

def generate_daily_note(signals):
    """生成每日研究笔记"""
    today = datetime.now().strftime("%Y-%m-%d")
    filename = f"{NOTES_DIR}/{today}_market_scan.md"
    
    content = f"""# 量化探索笔记 - {today}

## 市场扫描 ({datetime.now().strftime('%H:%M')})

### 技术信号汇总

| 代码 | 价格 | 趋势 | MACD | RSI | 波动率 | 量比 |
|------|------|------|------|-----|--------|------|
"""
    
    for s in signals:
        content += f"| {s['code']} | {s['price']} | {s['trend']} | {s['macd_signal']} | {s['rsi']} | {s['volatility']}% | {s['volume_ratio']} |\n"
    
    content += f"""
### 值得关注的信号

"""
    
    # 找出值得关注的信号
    buy_signals = [s for s in signals if "金叉" in s['macd_signal'] or s['rsi_status'] == "超卖"]
    sell_signals = [s for s in signals if "死叉" in s['macd_signal'] or s['rsi_status'] == "超买"]
    
    if buy_signals:
        content += "**潜在买入信号：**\n"
        for s in buy_signals:
            reason = []
            if "金叉" in s['macd_signal']:
                reason.append("MACD金叉")
            if s['rsi_status'] == "超卖":
                reason.append("RSI超卖")
            content += f"- {s['code']}: 价格{s['price']}, {', '.join(reason)}\n"
        content += "\n"
    
    if sell_signals:
        content += "**潜在卖出信号：**\n"
        for s in sell_signals:
            reason = []
            if "死叉" in s['macd_signal']:
                reason.append("MACD死叉")
            if s['rsi_status'] == "超买":
                reason.append("RSI超买")
            content += f"- {s['code']}: 价格{s['price']}, {', '.join(reason)}\n"
        content += "\n"
    
    content += f"""### 主观思考与下一步

- [ ] 需要深入研究MACD金叉策略的历史胜率
- [ ] 考虑加入成交量确认条件
- [ ] 探索RSI超卖反弹策略的有效性
- [ ] 对比不同周期（日线vs小时线）的信号差异

---
*自动生成于 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*
"""
    
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print(f"\n笔记已保存: {filename}")
    return filename

def quick_backtest_golden_cross(code, short=5, long=20):
    """快速回测双均线策略"""
    df = get_stock_data(code, days=252)  # 一年数据
    if df is None or len(df) < long + 10:
        return None
    
    df['MA_short'] = df['收盘'].rolling(short).mean()
    df['MA_long'] = df['收盘'].rolling(long).mean()
    
    # 生成信号
    df['signal'] = 0
    df.loc[df['MA_short'] > df['MA_long'], 'signal'] = 1  # 多头
    df.loc[df['MA_short'] <= df['MA_long'], 'signal'] = -1  # 空头/观望
    
    # 计算持仓变化
    df['position_change'] = df['signal'].diff()
    
    # 计算收益
    df['daily_return'] = df['收盘'].pct_change()
    df['strategy_return'] = df['signal'].shift(1) * df['daily_return']
    
    # 统计
    total_return = df['strategy_return'].sum()
    buy_hold_return = df['daily_return'].sum()
    trades = len(df[df['position_change'] != 0])
    
    return {
        "code": code,
        "strategy": f"双均线({short},{long})",
        "total_return": round(total_return * 100, 2),
        "buy_hold_return": round(buy_hold_return * 100, 2),
        "trades": trades,
        "avg_return_per_trade": round(total_return / trades * 100, 2) if trades > 0 else 0
    }

def main():
    """主函数"""
    os.makedirs(NOTES_DIR, exist_ok=True)
    os.makedirs(REPORTS_DIR, exist_ok=True)
    
    print("🚀 启动量化探索引擎...")
    
    # 1. 扫描市场信号
    signals = scan_market_signals()
    
    # 2. 生成研究笔记
    if signals:
        note_file = generate_daily_note(signals)
    
    # 3. 快速回测（随机选一只）
    print("\n" + "=" * 60)
    print("快速回测 - 双均线策略")
    print("=" * 60)
    
    test_code = WATCHLIST["stocks"][0]  # 茅台
    result = quick_backtest_golden_cross(test_code)
    if result:
        print(f"\n标的: {result['code']}")
        print(f"策略: {result['strategy']}")
        print(f"策略收益: {result['total_return']}%")
        print(f"买入持有: {result['buy_hold_return']}%")
        print(f"交易次数: {result['trades']}")
    
    print("\n✅ 探索完成")

if __name__ == "__main__":
    main()
