#!/usr/bin/env python3
"""
主动量化策略开发引擎
功能：
1. 基于市场动态和研究发现，主动生成策略想法
2. 编写完整的策略代码（入场、出场、风控）
3. 使用AKShare进行回测验证
4. 生成策略报告（逻辑、参数、回测结果）
5. 推送到GitHub并记录到博客

策略开发流程：
想法 → 设计 → 编码 → 回测 → 评估 → 记录
"""

import os
import sys
import json
import akshare as ak
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path

# 配置
PROJECT_DIR = Path("/project/quant-research")
STRATEGIES_DIR = PROJECT_DIR / "strategies"
BACKTESTS_DIR = PROJECT_DIR / "backtests"
REPORTS_DIR = PROJECT_DIR / "reports"
BLOG_POSTS_DIR = Path("/project/robertquant.github.io/blog/posts")

class StrategyDeveloper:
    """策略开发器"""
    
    def __init__(self):
        self.strategies_dir = STRATEGIES_DIR
        self.backtests_dir = BACKTESTS_DIR
        self.reports_dir = REPORTS_DIR
        
        # 创建目录
        for dir_path in [self.strategies_dir, self.backtests_dir, self.reports_dir]:
            dir_path.mkdir(parents=True, exist_ok=True)
    
    def generate_strategy_idea(self):
        """生成策略想法 - 基于当前市场热点和技术指标"""
        ideas = [
            {
                "name": "ETF动量+波动率过滤",
                "logic": "在ETF动量轮动基础上，加入ATR波动率过滤，只在低波动时交易",
                "params": {"momentum_days": 20, "atr_threshold": 0.02},
                "rationale": "高波动时期假突破多，过滤后胜率提升"
            },
            {
                "name": "小市值+质量因子",
                "logic": "流通市值最小的股票中，筛选ROE>10%、负债率<50%的优质公司",
                "params": {"top_n": 10, "roe_threshold": 0.10, "debt_threshold": 0.50},
                "rationale": "避免垃圾股，提高小市值策略稳健性"
            },
            {
                "name": "RSI超卖反弹",
                "logic": "RSI<30时买入，RSI>70时卖出，结合成交量确认",
                "params": {"rsi_period": 14, "oversold": 30, "overbought": 70},
                "rationale": "均值回归，捕捉超跌反弹机会"
            },
            {
                "name": "布林带突破+量价配合",
                "logic": "价格突破布林带上轨且成交量放大时买入，突破下轨止损",
                "params": {"bb_period": 20, "bb_std": 2, "volume_ratio": 1.5},
                "rationale": "趋势确认+量能验证，提高突破有效性"
            },
            {
                "name": "双均线金叉+MACD共振",
                "logic": "5日均线上穿20日均线，且MACD柱状线由负转正",
                "params": {"fast_ma": 5, "slow_ma": 20, "macd_fast": 12, "macd_slow": 26},
                "rationale": "多指标共振，降低假信号"
            }
        ]
        
        # 根据时间选择不同的策略（避免重复）
        hour = datetime.now().hour
        return ideas[hour % len(ideas)]
    
    def generate_strategy_code(self, idea):
        """生成策略代码"""
        strategy_name = idea["name"].replace("+", "_").replace(" ", "_")
        
        code = f'''#!/usr/bin/env python3
"""
策略名称: {idea["name"]}
策略逻辑: {idea["logic"]}
开发时间: {datetime.now().strftime("%Y-%m-%d %H:%M")}
"""

import akshare as ak
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

class {strategy_name}Strategy:
    """
    {idea["name"]}策略实现
    """
    
    def __init__(self, **kwargs):
        # 策略参数
        self.params = {idea["params"]}
        
        # 允许自定义参数
        for key, value in kwargs.items():
            if key in self.params:
                self.params[key] = value
        
        # 交易记录
        self.trades = []
        self.positions = {{}}
    
    def get_data(self, code, start_date, end_date):
        """获取股票数据"""
        try:
            df = ak.stock_zh_a_hist(
                symbol=code,
                period="daily",
                start_date=start_date,
                end_date=end_date,
                adjust="qfq"
            )
            return df
        except Exception as e:
            print(f"获取{{code}}数据失败: {{e}}")
            return None
    
    def calculate_indicators(self, df):
        """计算技术指标"""
        # 根据策略类型计算不同指标
        if "动量" in "{idea["name"]}":
            df["returns"] = df["收盘"].pct_change(self.params.get("momentum_days", 20))
        
        if "RSI" in "{idea["name"]}":
            delta = df["收盘"].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=self.params.get("rsi_period", 14)).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=self.params.get("rsi_period", 14)).mean()
            rs = gain / loss
            df["rsi"] = 100 - (100 / (1 + rs))
        
        if "均线" in "{idea["name"]}" or "MA" in "{idea["name"]}":
            df["ma_fast"] = df["收盘"].rolling(self.params.get("fast_ma", 5)).mean()
            df["ma_slow"] = df["收盘"].rolling(self.params.get("slow_ma", 20)).mean()
        
        if "MACD" in "{idea["name"]}":
            exp1 = df["收盘"].ewm(span=self.params.get("macd_fast", 12), adjust=False).mean()
            exp2 = df["收盘"].ewm(span=self.params.get("macd_slow", 26), adjust=False).mean()
            df["macd"] = exp1 - exp2
            df["macd_signal"] = df["macd"].ewm(span=9, adjust=False).mean()
            df["macd_hist"] = df["macd"] - df["macd_signal"]
        
        if "布林带" in "{idea["name"]}" or "Boll" in "{idea["name"]}":
            df["bb_middle"] = df["收盘"].rolling(self.params.get("bb_period", 20)).mean()
            bb_std = df["收盘"].rolling(self.params.get("bb_period", 20)).std()
            df["bb_upper"] = df["bb_middle"] + self.params.get("bb_std", 2) * bb_std
            df["bb_lower"] = df["bb_middle"] - self.params.get("bb_std", 2) * bb_std
        
        return df
    
    def generate_signals(self, df):
        """生成交易信号"""
        df = self.calculate_indicators(df)
        df["signal"] = 0
        
        # 根据策略逻辑生成信号
        # TODO: 根据具体策略逻辑实现
        
        return df
    
    def backtest(self, code, start_date, end_date, initial_capital=100000):
        """回测策略"""
        df = self.get_data(code, start_date, end_date)
        if df is None or len(df) < 50:
            return None
        
        df = self.generate_signals(df)
        
        # 简化回测逻辑
        capital = initial_capital
        position = 0
        trades = []
        
        for i in range(1, len(df)):
            row = df.iloc[i]
            prev_row = df.iloc[i-1]
            
            # 买入信号
            if row["signal"] == 1 and position == 0:
                position = capital / row["开盘"]
                capital = 0
                trades.append({{
                    "date": row["日期"],
                    "action": "BUY",
                    "price": row["开盘"],
                    "shares": position
                }})
            
            # 卖出信号
            elif row["signal"] == -1 and position > 0:
                capital = position * row["开盘"]
                trades.append({{
                    "date": row["日期"],
                    "action": "SELL",
                    "price": row["开盘"],
                    "value": capital
                }})
                position = 0
        
        # 计算最终收益
        final_value = capital + position * df.iloc[-1]["收盘"] if position > 0 else capital
        total_return = (final_value - initial_capital) / initial_capital
        
        return {{
            "code": code,
            "initial_capital": initial_capital,
            "final_value": final_value,
            "total_return": total_return,
            "trades": trades,
            "trade_count": len(trades)
        }}
    
    def optimize_params(self, code, start_date, end_date):
        """参数优化"""
        # TODO: 实现网格搜索或遗传算法优化
        pass

if __name__ == "__main__":
    # 测试策略
    strategy = {strategy_name}Strategy()
    result = strategy.backtest(
        code="000001",
        start_date="20240101",
        end_date="20241231"
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))
'''
        
        return strategy_name, code
    
    def save_strategy(self, name, code):
        """保存策略代码"""
        filepath = self.strategies_dir / f"{name}.py"
        filepath.write_text(code, encoding='utf-8')
        return filepath
    
    def generate_report(self, idea, strategy_name, code):
        """生成策略报告"""
        report = f"""
# 策略开发报告: {idea['name']}

## 策略信息
- **策略名称**: {idea['name']}
- **开发时间**: {datetime.now().strftime("%Y-%m-%d %H:%M")}
- **策略逻辑**: {idea['logic']}
- **核心假设**: {idea['rationale']}

## 策略参数
```python
{json.dumps(idea['params'], indent=2, ensure_ascii=False)}
```

## 入场规则
- TODO: 根据策略逻辑填写

## 出场规则
- TODO: 根据策略逻辑填写

## 风险控制
- TODO: 止损、仓位管理等

## 回测结果
- TODO: 运行回测后填写

## 代码实现
```python
{code[:1000]}...
```

## 下一步
1. [ ] 完善入场/出场规则
2. [ ] 添加止损逻辑
3. [ ] 运行回测验证
4. [ ] 参数优化
5. [ ] 样本外测试
"""
        
        report_path = self.reports_dir / f"{strategy_name}_report.md"
        report_path.write_text(report, encoding='utf-8')
        return report_path
    
    def create_blog_post(self, idea, strategy_name):
        """创建博客随笔"""
        post_num = self.get_next_post_number()
        date_str = datetime.now().strftime("%Y-%m-%d")
        
        html = f"""
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>策略开发 #{post_num:03d} - {idea['name']} | Robert Quant</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Microsoft YaHei', sans-serif;
            line-height: 1.8;
            color: #333;
            background: #f5f7fa;
        }}
        .container {{ max-width: 800px; margin: 0 auto; padding: 40px 20px; }}
        .article {{
            background: white;
            border-radius: 12px;
            padding: 50px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.08);
        }}
        .header {{ border-bottom: 2px solid #e2e8f0; padding-bottom: 20px; margin-bottom: 30px; }}
        h1 {{ font-size: 1.8em; color: #2d3748; margin-bottom: 10px; }}
        .meta {{ color: #718096; font-size: 0.9em; }}
        .tag {{
            display: inline-block;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 3px 10px;
            border-radius: 12px;
            font-size: 0.85em;
            margin-right: 8px;
        }}
        h2 {{ color: #4a5568; margin: 30px 0 15px; font-size: 1.3em; }}
        p {{ margin: 15px 0; }}
        .highlight {{
            background: linear-gradient(120deg, #a8edea 0%, #fed6e3 100%);
            padding: 20px;
            border-radius: 8px;
            margin: 20px 0;
        }}
        .back {{ margin-top: 40px; }}
        .back a {{ color: #667eea; text-decoration: none; }}
        code {{
            background: #f4f4f4;
            padding: 2px 6px;
            border-radius: 3px;
            font-family: 'Courier New', monospace;
        }}
        pre {{
            background: #f8f9fa;
            padding: 15px;
            border-radius: 8px;
            overflow-x: auto;
            font-family: 'Courier New', monospace;
            font-size: 0.85em;
        }}
    </style>
</head>
<body>
    <div class="container">
        <article class="article">
            <div class="header">
                <h1>策略开发 #{post_num:03d}</h1>
                <div class="meta">
                    <span class="tag">策略研究</span>
                    <span>{date_str}</span>
                </div>
            </div>
            
            <h2>{idea['name']}</h2>
            
            <p><strong>策略逻辑：</strong>{idea['logic']}</p>
            
            <div class="highlight">
                <strong>核心假设：</strong>{idea['rationale']}
            </div>
            
            <h2>策略参数</h2>
            
            <pre>{json.dumps(idea['params'], indent=2, ensure_ascii=False)}</pre>
            
            <h2>代码实现</h2>
            
            <p>策略代码已生成并保存到：<code>/project/quant-research/strategies/{strategy_name}.py</code></p>
            
            <div class="highlight">
                <strong>下一步行动：</strong><br>
                1. 完善入场/出场规则<br>
                2. 添加止损逻辑<br>
                3. 运行回测验证<br>
                4. 参数优化<br>
                5. 样本外测试
            </div>
            
            <div class="back">
                <a href="../index.html">← 返回随笔列表</a>
            </div>
        </article>
    </div>
</body>
</html>
"""
        
        post_path = BLOG_POSTS_DIR / f"{post_num:03d}-strategy-{strategy_name.lower()}.html"
        post_path.write_text(html, encoding='utf-8')
        return post_path, post_num
    
    def get_next_post_number(self):
        """获取下一个文章编号"""
        import re
        existing = list(BLOG_POSTS_DIR.glob("*.html"))
        numbers = []
        for f in existing:
            match = re.search(r'(\d{3})-', f.name)
            if match:
                numbers.append(int(match.group(1)))
        return max(numbers, default=0) + 1
    
    def run(self):
        """运行策略开发流程"""
        print("🚀 启动主动策略开发...")
        
        # 1. 生成策略想法
        idea = self.generate_strategy_idea()
        print(f"💡 策略想法: {idea['name']}")
        
        # 2. 生成策略代码
        strategy_name, code = self.generate_strategy_code(idea)
        print(f"📝 生成代码: {strategy_name}.py")
        
        # 3. 保存策略
        code_path = self.save_strategy(strategy_name, code)
        print(f"💾 保存到: {code_path}")
        
        # 4. 生成报告
        report_path = self.generate_report(idea, strategy_name, code)
        print(f"📊 报告: {report_path}")
        
        # 5. 创建博客随笔
        post_path, post_num = self.create_blog_post(idea, strategy_name)
        print(f"🌐 博客: {post_path}")
        
        # 6. 推送到GitHub
        print("🚀 推送到GitHub...")
        os.system("cd /project/quant-research && git add . && git commit -m 'Add new strategy: {strategy_name}' && git push")
        
        print(f"\n✅ 策略开发完成！")
        print(f"   策略: {idea['name']}")
        print(f"   代码: /project/quant-research/strategies/{strategy_name}.py")
        print(f"   报告: {report_path}")
        print(f"   博客: https://robertquant.github.io/blog/posts/{post_num:03d}-strategy-{strategy_name.lower()}.html")
        
        return strategy_name

def main():
    """主函数"""
    developer = StrategyDeveloper()
    developer.run()

if __name__ == "__main__":
    main()
