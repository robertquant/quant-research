#!/usr/bin/env python3
"""
ETF轮动策略 - 动量轮动 + 趋势过滤 (使用腾讯财经数据)
策略逻辑：
1. 标的池：沪深300ETF、中证500ETF、创业板ETF、科创50ETF
2. 轮动逻辑：取20日涨幅最大的1只
3. 调仓频率：每日收盘
4. 风控：沪深300跌破20日均线时空仓

作者：QuantBot
日期：2026-03-24
"""

import requests
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import warnings
warnings.filterwarnings('ignore')

plt.rcParams['font.sans-serif'] = ['DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False

class ETFRotationStrategy:
    """ETF轮动策略类"""
    
    def __init__(self, start_date='20190101', end_date=None, 
                 momentum_window=20, market_filter_window=20):
        self.start_date = start_date
        self.end_date = end_date or datetime.now().strftime('%Y%m%d')
        self.momentum_window = momentum_window
        self.market_filter_window = market_filter_window
        
        self.etfs = {
            'sh510300': '沪深300ETF',
            'sh510500': '中证500ETF',
            'sz159915': '创业板ETF',
            'sh588000': '科创50ETF'
        }
        self.market_etf = 'sh510300'
        
        self.price_data = {}
        self.trade_log = []
        self.portfolio_value = []
        
    def fetch_data(self):
        """从腾讯财经获取ETF历史数据"""
        print("📊 正在获取ETF数据...")
        
        start = f"{self.start_date[:4]}-{self.start_date[4:6]}-{self.start_date[6:]}"
        end = f"{self.end_date[:4]}-{self.end_date[4:6]}-{self.end_date[6:]}"
        
        for code, name in self.etfs.items():
            try:
                url = f'http://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={code},day,{start},{end},500,qfq'
                r = requests.get(url, timeout=30)
                data = r.json()
                kline_data = data['data'].get(code, {}).get('qfqday', [])
                
                if not kline_data:
                    print(f"  ⚠️ {name}({code}): 无数据")
                    continue
                
                df_data = []
                for row in kline_data:
                    try:
                        df_data.append({
                            '日期': row[0],
                            '开盘': float(row[1]),
                            '收盘': float(row[2]),
                            '最低': float(row[3]),
                            '最高': float(row[4]),
                            '成交量': float(row[5])
                        })
                    except:
                        continue
                
                df = pd.DataFrame(df_data)
                df['日期'] = pd.to_datetime(df['日期'])
                df.set_index('日期', inplace=True)
                df.sort_index(inplace=True)
                
                self.price_data[code] = df
                print(f"  ✅ {name}({code}): {len(df)}条数据")
                
            except Exception as e:
                print(f"  ❌ {name}({code}): 获取失败 - {e}")
                
        if not self.price_data:
            raise ValueError("未能获取任何ETF数据")
            
        print(f"\n数据时间范围: {min(df.index.min() for df in self.price_data.values())} ~ "
              f"{max(df.index.max() for df in self.price_data.values())}")
    
    def backtest(self, initial_capital=100000):
        """执行回测"""
        print("\n🚀 开始回测...")
        print(f"初始资金: ¥{initial_capital:,.0f}")
        print(f"动量窗口: {self.momentum_window}日")
        print(f"大盘过滤: 沪深300 {self.market_filter_window}日均线\n")
        
        # 准备数据
        all_dates = set()
        for df in self.price_data.values():
            all_dates.update(df.index)
        
        min_date = max(df.index.min() for df in self.price_data.values()) + timedelta(days=self.momentum_window)
        trade_dates = sorted([d for d in all_dates if d >= min_date])
        
        # 初始化账户
        cash = initial_capital
        position = None  # 当前持有的ETF代码
        shares = 0       # 持有的份额
        
        # 回测循环
        for current_date in trade_dates:
            # 获取当日价格
            prices = {code: df.loc[current_date, '收盘'] 
                     for code, df in self.price_data.items() 
                     if current_date in df.index}
            
            if not prices:
                continue
            
            # 计算当前总资产
            position_value = shares * prices.get(position, 0) if position else 0
            total_value = cash + position_value
            
            # 记录净值
            self.portfolio_value.append({
                'date': current_date,
                'value': total_value,
                'cash': cash,
                'position': position,
                'position_value': position_value
            })
            
            # 计算信号
            # 1. 大盘趋势过滤
            market_df = self.price_data.get(self.market_etf)
            market_above_ma = False
            if market_df is not None and current_date in market_df.index:
                idx = market_df.index.get_loc(current_date)
                if idx >= self.market_filter_window:
                    ma20 = market_df.iloc[idx - self.market_filter_window + 1:idx + 1]['收盘'].mean()
                    market_above_ma = market_df.loc[current_date, '收盘'] > ma20
            
            # 2. 计算动量并选择最强ETF
            momentum_scores = {}
            for code, df in self.price_data.items():
                if current_date in df.index:
                    idx = df.index.get_loc(current_date)
                    if idx >= self.momentum_window:
                        past_price = df.iloc[idx - self.momentum_window]['收盘']
                        current_price = df.loc[current_date, '收盘']
                        momentum_scores[code] = (current_price / past_price - 1) * 100
            
            best_etf = max(momentum_scores.items(), key=lambda x: x[1])[0] if momentum_scores else None
            
            # 3. 执行交易逻辑
            if not market_above_ma:
                # 空仓信号 - 卖出所有持仓
                if position and position in prices:
                    sell_price = prices[position]
                    cash += shares * sell_price
                    self.trade_log.append({
                        'date': current_date, 'action': 'sell', 'code': position,
                        'price': sell_price, 'shares': shares, 'reason': 'market_filter'
                    })
                    position = None
                    shares = 0
                    
            elif best_etf and best_etf != position:
                # 调仓信号
                if position and position in prices:
                    # 先卖出旧持仓
                    sell_price = prices[position]
                    cash += shares * sell_price
                    self.trade_log.append({
                        'date': current_date, 'action': 'sell', 'code': position,
                        'price': sell_price, 'shares': shares, 'reason': 'rotation'
                    })
                
                # 买入新持仓
                buy_price = prices.get(best_etf, 0)
                if buy_price > 0 and cash > 0:
                    shares = cash / buy_price
                    cash = 0
                    position = best_etf
                    self.trade_log.append({
                        'date': current_date, 'action': 'buy', 'code': best_etf,
                        'price': buy_price, 'shares': shares, 'momentum': momentum_scores.get(best_etf)
                    })
        
        print(f"✅ 回测完成！共{len(trade_dates)}个交易日，{len([t for t in self.trade_log if t['action']=='buy'])}笔交易")
        return self.calculate_metrics(initial_capital)
    
    def calculate_metrics(self, initial_capital):
        """计算回测指标"""
        if not self.portfolio_value:
            return {}
        
        df = pd.DataFrame(self.portfolio_value)
        df.set_index('date', inplace=True)
        
        df['returns'] = df['value'].pct_change()
        df['cum_returns'] = (df['value'] / initial_capital - 1) * 100
        
        total_return = (df['value'].iloc[-1] / initial_capital - 1) * 100
        annual_return = total_return / (len(df) / 252)
        volatility = df['returns'].std() * np.sqrt(252) * 100
        sharpe_ratio = annual_return / volatility if volatility > 0 else 0
        
        df['cummax'] = df['value'].cummax()
        df['drawdown'] = (df['value'] / df['cummax'] - 1) * 100
        max_drawdown = df['drawdown'].min()
        
        buy_trades = [t for t in self.trade_log if t['action'] == 'buy']
        
        self.metrics = {
            '初始资金': initial_capital,
            '最终资金': df['value'].iloc[-1],
            '总收益率': total_return,
            '年化收益率': annual_return,
            '年化波动率': volatility,
            '夏普比率': sharpe_ratio,
            '最大回撤': max_drawdown,
            '交易次数': len(buy_trades),
            '持仓天数': len(df[df['position'].notna()]),
            '空仓天数': len(df[df['position'].isna()])
        }
        
        self.df = df
        return self.metrics
    
    def plot_results(self, save_path=None):
        """绘制回测结果图表"""
        if not hasattr(self, 'df'):
            print("请先运行回测")
            return
        
        fig, axes = plt.subplots(3, 1, figsize=(14, 10))
        
        ax1 = axes[0]
        ax1.plot(self.df.index, self.df['cum_returns'], label='Strategy', linewidth=1.5, color='#667eea')
        ax1.axhline(y=0, color='gray', linestyle='--', alpha=0.5)
        ax1.set_title('ETF Rotation Strategy - Cumulative Returns', fontsize=12)
        ax1.set_ylabel('Returns (%)')
        ax1.legend()
        ax1.grid(True, alpha=0.3)
        
        ax2 = axes[1]
        ax2.fill_between(self.df.index, self.df['drawdown'], 0, color='red', alpha=0.3)
        ax2.plot(self.df.index, self.df['drawdown'], color='red', linewidth=1)
        ax2.set_title('Drawdown Curve', fontsize=12)
        ax2.set_ylabel('Drawdown (%)')
        ax2.grid(True, alpha=0.3)
        
        ax3 = axes[2]
        position_map = {code: i+1 for i, code in enumerate(self.etfs.keys())}
        position_map[None] = 0
        positions = [position_map.get(p, 0) for p in self.df['position']]
        ax3.fill_between(self.df.index, positions, alpha=0.5, color='#667eea')
        ax3.set_yticks(range(len(self.etfs)+1))
        ax3.set_yticklabels(['Empty'] + list(self.etfs.values()))
        ax3.set_title('Position Status', fontsize=12)
        ax3.set_ylabel('ETF')
        ax3.set_xlabel('Date')
        ax3.grid(True, alpha=0.3)
        
        plt.tight_layout()
        
        if save_path:
            plt.savefig(save_path, dpi=150, bbox_inches='tight')
            print(f"\n📈 图表已保存: {save_path}")
        
        return fig
    
    def print_report(self):
        """打印回测报告"""
        print("\n" + "="*60)
        print("📊 ETF轮动策略回测报告")
        print("="*60)
        print(f"\n策略参数:")
        print(f"  标的池: {', '.join(self.etfs.values())}")
        print(f"  动量窗口: {self.momentum_window}日")
        print(f"  大盘过滤: 沪深300 {self.market_filter_window}日均线")
        
        print(f"\n回测结果:")
        print(f"  初始资金: ¥{self.metrics['初始资金']:,.0f}")
        print(f"  最终资金: ¥{self.metrics['最终资金']:,.0f}")
        print(f"  总收益率: {self.metrics['总收益率']:.2f}%")
        print(f"  年化收益率: {self.metrics['年化收益率']:.2f}%")
        print(f"  年化波动率: {self.metrics['年化波动率']:.2f}%")
        print(f"  夏普比率: {self.metrics['夏普比率']:.2f}")
        print(f"  最大回撤: {self.metrics['最大回撤']:.2f}%")
        print(f"  交易次数: {self.metrics['交易次数']}次")
        print(f"  持仓天数: {self.metrics['持仓天数']}天")
        print(f"  空仓天数: {self.metrics['空仓天数']}天")
        print("="*60)
    
    def save_trade_log(self, filepath):
        """保存交易记录"""
        if self.trade_log:
            df = pd.DataFrame(self.trade_log)
            df.to_csv(filepath, index=False, encoding='utf-8-sig')
            print(f"\n📝 交易记录已保存: {filepath}")


def main():
    """主函数"""
    strategy = ETFRotationStrategy(
        start_date='20190101',
        end_date='20241231',
        momentum_window=20,
        market_filter_window=20
    )
    
    strategy.fetch_data()
    metrics = strategy.backtest(initial_capital=100000)
    strategy.print_report()
    strategy.plot_results(save_path='/project/quant-research/backtests/etf_rotation_chart.png')
    strategy.save_trade_log('/project/quant-research/backtests/etf_rotation_trades.csv')
    
    print("\n✅ 策略回测完成！")


if __name__ == '__main__':
    main()
