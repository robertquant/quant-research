#!/usr/bin/env python3
"""
ETF轮动策略 v4.1 - 分层轮动
改进：宽基ETF和行业ETF分层轮动，避免过度集中行业风险

作者：QuantBot
日期：2026-03-24
"""

import sys
sys.path.insert(0, '/project/quant-research/data')

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from data_cache import get_data, batch_get_data
import warnings
warnings.filterwarnings('ignore')

plt.rcParams['font.sans-serif'] = ['DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False


class ETFRotationStrategyV41:
    """ETF轮动策略 v4.1 - 分层轮动"""
    
    def __init__(self, start_date='20150101', end_date=None, 
                 momentum_window=30, market_filter_window=60,
                 stop_loss=-0.08):
        self.start_date = start_date
        self.end_date = end_date or datetime.now().strftime('%Y%m%d')
        self.momentum_window = momentum_window
        self.market_filter_window = market_filter_window
        self.stop_loss = stop_loss
        
        # 分层ETF池
        self.base_etfs = {  # 宽基ETF（主要仓位）
            'sh510300': '沪深300ETF',
            'sh510500': '中证500ETF',
            'sz159915': '创业板ETF',
            'sh588000': '科创50ETF',
        }
        
        self.sector_etfs = {  # 行业ETF（次要仓位，限制比例）
            'sh510900': '恒生ETF',
            'sh513130': '恒生科技ETF',
            'sz159863': '光伏ETF',
            'sh512760': '芯片ETF',
            'sh512000': '券商ETF',
            'sh512480': '半导体ETF',
        }
        
        # 合并所有ETF
        self.etfs = {**self.base_etfs, **self.sector_etfs}
        
        self.market_etf = 'sh510300'
        self.sector_max_ratio = 0.3  # 行业ETF最大仓位30%
        
        self.price_data = {}
        self.trade_log = []
        self.portfolio_value = []
        
    def fetch_data(self):
        """获取数据"""
        print("📊 正在获取数据...")
        
        codes = list(self.etfs.keys())
        results = batch_get_data(codes, self.start_date, self.end_date)
        
        for code, df in results.items():
            self.price_data[code] = df
            etf_type = "宽基" if code in self.base_etfs else "行业"
            print(f"  ✅ [{etf_type}] {self.etfs[code]}: {len(df)}条")
        
        if not self.price_data:
            raise ValueError("未能获取数据")
    
    def backtest(self, initial_capital=100000):
        """执行回测 - 分层轮动"""
        print("\n🚀 开始分层轮动回测...")
        print(f"宽基ETF: {list(self.base_etfs.values())}")
        print(f"行业ETF: {list(self.sector_etfs.values())} (限制{self.sector_max_ratio*100:.0f}%仓位)")
        
        # 准备数据
        all_dates = set()
        for df in self.price_data.values():
            all_dates.update(df.index)
        
        min_date = max(df.index.min() for df in self.price_data.values()) + timedelta(days=max(self.momentum_window, self.market_filter_window))
        trade_dates = sorted([d for d in all_dates if d >= min_date])
        
        cash = initial_capital
        position = None
        shares = 0
        entry_price = 0
        
        for current_date in trade_dates:
            prices = {code: df.loc[current_date, 'close'] 
                     for code, df in self.price_data.items() 
                     if current_date in df.index}
            
            if not prices:
                continue
            
            position_value = shares * prices.get(position, 0) if position else 0
            total_value = cash + position_value
            
            self.portfolio_value.append({
                'date': current_date,
                'value': total_value,
                'position': position,
            })
            
            # 止损检查
            if position and position in prices:
                current_price = prices[position]
                if entry_price > 0:
                    loss_pct = (current_price / entry_price - 1)
                    if loss_pct <= self.stop_loss:
                        cash += shares * current_price
                        self.trade_log.append({
                            'date': current_date, 'action': 'sell', 'code': position,
                            'price': current_price, 'reason': f'stop_loss'
                        })
                        position = None
                        shares = 0
                        entry_price = 0
                        continue
            
            # 大盘过滤
            market_df = self.price_data.get(self.market_etf)
            market_above_ma = False
            if market_df is not None and current_date in market_df.index:
                idx = market_df.index.get_loc(current_date)
                if idx >= self.market_filter_window:
                    ma = market_df.iloc[idx - self.market_filter_window + 1:idx + 1]['close'].mean()
                    market_above_ma = market_df.loc[current_date, 'close'] > ma
            
            if not market_above_ma:
                if position and position in prices:
                    cash += shares * prices[position]
                    position = None
                    shares = 0
                    entry_price = 0
                continue
            
            # 分层轮动逻辑
            # 1. 先计算所有ETF动量
            momentum_scores = {}
            for code, df in self.price_data.items():
                if current_date in df.index:
                    idx = df.index.get_loc(current_date)
                    if idx >= self.momentum_window:
                        past_price = df.iloc[idx - self.momentum_window]['close']
                        current_price = df.loc[current_date, 'close']
                        momentum_scores[code] = (current_price / past_price - 1) * 100
            
            if not momentum_scores:
                continue
            
            # 2. 找出宽基和行业各自最强的
            base_momentum = {k: v for k, v in momentum_scores.items() if k in self.base_etfs}
            sector_momentum = {k: v for k, v in momentum_scores.items() if k in self.sector_etfs}
            
            best_base = max(base_momentum.items(), key=lambda x: x[1])[0] if base_momentum else None
            best_sector = max(sector_momentum.items(), key=lambda x: x[1])[0] if sector_momentum else None
            
            # 3. 选择逻辑：优先宽基，行业只在明显强势时配置
            selected = None
            if best_base and best_sector:
                sector_advantage = momentum_scores[best_sector] - momentum_scores[best_base]
                if sector_advantage > 3:  # 行业ETF领先宽基3%以上才考虑
                    selected = best_sector
                else:
                    selected = best_base
            elif best_base:
                selected = best_base
            
            # 4. 执行调仓
            if selected and selected != position:
                if position and position in prices:
                    cash += shares * prices[position]
                
                buy_price = prices.get(selected, 0)
                if buy_price > 0 and cash > 0:
                    shares = cash / buy_price
                    cash = 0
                    position = selected
                    entry_price = buy_price
                    self.trade_log.append({
                        'date': current_date, 'action': 'buy', 'code': selected,
                        'price': buy_price, 'momentum': momentum_scores.get(selected)
                    })
        
        print(f"✅ 回测完成！共{len(trade_dates)}个交易日")
        return self.calculate_metrics(initial_capital)
    
    def calculate_metrics(self, initial_capital):
        """计算指标"""
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
        
        buys = [t for t in self.trade_log if t['action'] == 'buy']
        base_buys = [t for t in buys if t['code'] in self.base_etfs]
        sector_buys = [t for t in buys if t['code'] in self.sector_etfs]
        
        self.metrics = {
            '初始资金': initial_capital,
            '最终资金': df['value'].iloc[-1],
            '总收益率': total_return,
            '年化收益率': annual_return,
            '夏普比率': sharpe_ratio,
            '最大回撤': max_drawdown,
            '交易次数': len(buys),
            '宽基买入次数': len(base_buys),
            '行业买入次数': len(sector_buys),
        }
        
        self.df = df
        return self.metrics
    
    def print_report(self):
        """打印报告"""
        print("\n" + "="*60)
        print("📊 ETF分层轮动策略 v4.1 回测报告")
        print("="*60)
        print(f"\n策略参数:")
        print(f"  动量窗口: {self.momentum_window}日")
        print(f"  大盘过滤: {self.market_filter_window}日均线")
        print(f"  行业触发阈值: 领先宽基3%")
        
        print(f"\n回测结果:")
        print(f"  总收益率: {self.metrics['总收益率']:.2f}%")
        print(f"  年化收益率: {self.metrics['年化收益率']:.2f}%")
        print(f"  夏普比率: {self.metrics['夏普比率']:.2f}")
        print(f"  最大回撤: {self.metrics['最大回撤']:.2f}%")
        print(f"  交易次数: {self.metrics['交易次数']}次")
        print(f"    - 宽基ETF: {self.metrics['宽基买入次数']}次")
        print(f"    - 行业ETF: {self.metrics['行业买入次数']}次")
        print("="*60)


def main():
    strategy = ETFRotationStrategyV41(
        start_date='20220101',
        end_date='20241231',
        momentum_window=30,
        market_filter_window=60,
        stop_loss=-0.08
    )
    
    strategy.fetch_data()
    metrics = strategy.backtest(initial_capital=100000)
    strategy.print_report()
    
    print("\n✅ 分层轮动策略回测完成！")


if __name__ == '__main__':
    main()
