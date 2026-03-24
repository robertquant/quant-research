#!/usr/bin/env python3
"""
ETF轮动策略 v4.0 - 使用本地数据缓存
策略逻辑：
1. 标的池：沪深300ETF、中证500ETF、创业板ETF、科创50ETF
2. 轮动逻辑：取N日涨幅最大的1只
3. 调仓频率：每日收盘
4. 风控：大盘跌破M日均线时空仓
5. 止损：-8%硬止损

改进：使用本地数据缓存，避免重复请求

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


class ETFRotationStrategyV4:
    """ETF轮动策略 v4.0"""
    
    def __init__(self, start_date='20150101', end_date=None, 
                 momentum_window=20, market_filter_window=60,
                 stop_loss=-0.08, position_size=1.0):
        """
        初始化
        
        Parameters:
        -----------
        start_date : str
            回测开始日期
        end_date : str
            回测结束日期
        momentum_window : int
            动量计算窗口
        market_filter_window : int
            大盘趋势过滤窗口（默认60日）
        stop_loss : float
            止损比例（默认-8%）
        position_size : float
            仓位比例（默认满仓）
        """
        self.start_date = start_date
        self.end_date = end_date or datetime.now().strftime('%Y%m%d')
        self.momentum_window = momentum_window
        self.market_filter_window = market_filter_window
        self.stop_loss = stop_loss
        self.position_size = position_size
        
        # ETF标的池
        self.etfs = {
            'sh510300': '沪深300ETF',
            'sh510500': '中证500ETF',
            'sz159915': '创业板ETF',
            'sh588000': '科创50ETF'
        }
        
        self.market_etf = 'sh510300'
        
        # 数据存储
        self.price_data = {}
        self.trade_log = []
        self.portfolio_value = []
        
    def fetch_data(self):
        """获取数据（使用缓存）"""
        print("📊 正在获取数据（使用本地缓存）...")
        
        codes = list(self.etfs.keys())
        
        # 批量获取数据（自动使用缓存）
        results = batch_get_data(codes, self.start_date, self.end_date)
        
        for code, df in results.items():
            self.price_data[code] = df
            print(f"  ✅ {self.etfs[code]}: {len(df)}条数据")
        
        if not self.price_data:
            raise ValueError("未能获取任何ETF数据")
            
        print(f"\n数据时间范围: {min(df.index.min() for df in self.price_data.values())} ~ "
              f"{max(df.index.max() for df in self.price_data.values())}")
    
    def backtest(self, initial_capital=100000):
        """执行回测"""
        print("\n🚀 开始回测...")
        print(f"初始资金: ¥{initial_capital:,.0f}")
        print(f"动量窗口: {self.momentum_window}日")
        print(f"大盘过滤: {self.market_filter_window}日均线")
        print(f"止损比例: {self.stop_loss*100:.0f}%\n")
        
        # 准备数据
        all_dates = set()
        for df in self.price_data.values():
            all_dates.update(df.index)
        
        min_date = max(df.index.min() for df in self.price_data.values()) + timedelta(days=max(self.momentum_window, self.market_filter_window))
        trade_dates = sorted([d for d in all_dates if d >= min_date])
        
        # 初始化账户
        cash = initial_capital
        position = None
        shares = 0
        entry_price = 0  # 入场价格（用于止损计算）
        
        # 回测循环
        for current_date in trade_dates:
            # 获取当日价格
            prices = {code: df.loc[current_date, 'close'] 
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
            # 1. 止损检查
            if position and position in prices:
                current_price = prices[position]
                if entry_price > 0:
                    loss_pct = (current_price / entry_price - 1)
                    if loss_pct <= self.stop_loss:
                        # 触发止损，卖出
                        cash += shares * current_price
                        self.trade_log.append({
                            'date': current_date,
                            'action': 'sell',
                            'code': position,
                            'price': current_price,
                            'reason': f'stop_loss ({loss_pct*100:.1f}%)'
                        })
                        position = None
                        shares = 0
                        entry_price = 0
                        continue  # 跳过本次交易，空仓等待
            
            # 2. 大盘趋势过滤
            market_df = self.price_data.get(self.market_etf)
            market_above_ma = False
            if market_df is not None and current_date in market_df.index:
                idx = market_df.index.get_loc(current_date)
                if idx >= self.market_filter_window:
                    ma = market_df.iloc[idx - self.market_filter_window + 1:idx + 1]['close'].mean()
                    market_above_ma = market_df.loc[current_date, 'close'] > ma
            
            # 3. 计算动量并选择最强ETF
            momentum_scores = {}
            for code, df in self.price_data.items():
                if current_date in df.index:
                    idx = df.index.get_loc(current_date)
                    if idx >= self.momentum_window:
                        past_price = df.iloc[idx - self.momentum_window]['close']
                        current_price = df.loc[current_date, 'close']
                        momentum_scores[code] = (current_price / past_price - 1) * 100
            
            best_etf = max(momentum_scores.items(), key=lambda x: x[1])[0] if momentum_scores else None
            
            # 4. 执行交易逻辑
            if not market_above_ma:
                # 大盘趋势向下，空仓
                if position and position in prices:
                    sell_price = prices[position]
                    cash += shares * sell_price
                    self.trade_log.append({
                        'date': current_date, 'action': 'sell', 'code': position,
                        'price': sell_price, 'reason': 'market_filter'
                    })
                    position = None
                    shares = 0
                    entry_price = 0
                    
            elif best_etf and best_etf != position:
                # 调仓
                if position and position in prices:
                    sell_price = prices[position]
                    cash += shares * sell_price
                    self.trade_log.append({
                        'date': current_date, 'action': 'sell', 'code': position,
                        'price': sell_price, 'reason': 'rotation'
                    })
                
                buy_price = prices.get(best_etf, 0)
                if buy_price > 0 and cash > 0:
                    position_value = cash * self.position_size
                    shares = position_value / buy_price
                    cash = cash - position_value
                    position = best_etf
                    entry_price = buy_price
                    self.trade_log.append({
                        'date': current_date, 'action': 'buy', 'code': best_etf,
                        'price': buy_price, 'momentum': momentum_scores.get(best_etf),
                        'reason': 'entry'
                    })
        
        print(f"✅ 回测完成！共{len(trade_dates)}个交易日")
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
        stop_loss_trades = [t for t in self.trade_log if t['action'] == 'sell' and 'stop_loss' in t.get('reason', '')]
        
        self.metrics = {
            '初始资金': initial_capital,
            '最终资金': df['value'].iloc[-1],
            '总收益率': total_return,
            '年化收益率': annual_return,
            '年化波动率': volatility,
            '夏普比率': sharpe_ratio,
            '最大回撤': max_drawdown,
            '交易次数': len(buy_trades),
            '止损次数': len(stop_loss_trades),
            '持仓天数': len(df[df['position'].notna()]),
            '空仓天数': len(df[df['position'].isna()])
        }
        
        self.df = df
        return self.metrics
    
    def plot_results(self, save_path=None):
        """绘制回测结果"""
        if not hasattr(self, 'df'):
            print("请先运行回测")
            return
        
        fig, axes = plt.subplots(3, 1, figsize=(14, 12))
        
        ax1 = axes[0]
        ax1.plot(self.df.index, self.df['cum_returns'], label='Strategy', linewidth=1.5, color='#667eea')
        ax1.axhline(y=0, color='gray', linestyle='--', alpha=0.5)
        ax1.set_title('ETF Rotation Strategy v4.0 - Cumulative Returns', fontsize=12)
        ax1.set_ylabel('Returns (%)')
        ax1.legend()
        ax1.grid(True, alpha=0.3)
        
        ax2 = axes[1]
        ax2.fill_between(self.df.index, self.df['drawdown'], 0, color='red', alpha=0.3)
        ax2.plot(self.df.index, self.df['drawdown'], color='red', linewidth=1)
        ax2.axhline(y=self.stop_loss*100, color='darkred', linestyle='--', alpha=0.7, label=f'Stop Loss ({self.stop_loss*100:.0f}%)')
        ax2.set_title('Drawdown Curve', fontsize=12)
        ax2.set_ylabel('Drawdown (%)')
        ax2.legend()
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
        print("📊 ETF轮动策略 v4.0 回测报告")
        print("="*60)
        print(f"\n策略参数:")
        print(f"  标的池: {', '.join(self.etfs.values())}")
        print(f"  动量窗口: {self.momentum_window}日")
        print(f"  大盘过滤: {self.market_filter_window}日均线")
        print(f"  止损比例: {self.stop_loss*100:.0f}%")
        
        print(f"\n回测结果:")
        print(f"  初始资金: ¥{self.metrics['初始资金']:,.0f}")
        print(f"  最终资金: ¥{self.metrics['最终资金']:,.0f}")
        print(f"  总收益率: {self.metrics['总收益率']:.2f}%")
        print(f"  年化收益率: {self.metrics['年化收益率']:.2f}%")
        print(f"  年化波动率: {self.metrics['年化波动率']:.2f}%")
        print(f"  夏普比率: {self.metrics['夏普比率']:.2f}")
        print(f"  最大回撤: {self.metrics['最大回撤']:.2f}%")
        print(f"  交易次数: {self.metrics['交易次数']}次")
        print(f"  止损次数: {self.metrics['止损次数']}次")
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
    # 使用改进的参数
    strategy = ETFRotationStrategyV4(
        start_date='20150101',      # 从2015年开始
        end_date='20241231',
        momentum_window=30,          # 30日动量（比20日更稳健）
        market_filter_window=60,     # 60日均线过滤（比20日更宽松）
        stop_loss=-0.08              # -8%硬止损
    )
    
    strategy.fetch_data()
    metrics = strategy.backtest(initial_capital=100000)
    strategy.print_report()
    strategy.plot_results(save_path='/project/quant-research/backtests/etf_rotation_v4.png')
    strategy.save_trade_log('/project/quant-research/backtests/etf_rotation_v4_trades.csv')
    
    print("\n✅ ETF轮动策略 v4.0 回测完成！")
    print("\n💡 改进点：")
    print("   • 延长回测周期至2015年（10年数据）")
    print("   • 放宽大盘过滤至60日均线")
    print("   • 增加-8%硬止损机制")
    print("   • 使用本地数据缓存，提升效率")


if __name__ == '__main__':
    main()
