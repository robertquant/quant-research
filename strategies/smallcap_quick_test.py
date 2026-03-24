#!/usr/bin/env python3
"""
小市值因子策略 - 快速验证版
策略逻辑：
1. 全市场股票按市值排序
2. 选取市值最小的N只股票
3. 定期调仓（月度/季度）
4. 对比基准：沪深300指数

作者：QuantBot（主动探索）
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

class SmallCapStrategy:
    """小市值因子策略"""
    
    def __init__(self, start_date='20200101', end_date=None, 
                 top_n=20, min_price=2.0, exclude_st=True):
        """
        初始化
        
        Parameters:
        -----------
        start_date : str
            回测开始日期
        end_date : str
            回测结束日期
        top_n : int
            选取市值最小的前N只
        min_price : float
            最小股价（剔除仙股）
        exclude_st : bool
            是否剔除ST股票
        """
        self.start_date = start_date
        self.end_date = end_date or datetime.now().strftime('%Y%m%d')
        self.top_n = top_n
        self.min_price = min_price
        self.exclude_st = exclude_st
        
        self.price_data = {}
        self.trade_log = []
        self.portfolio_value = []
        
    def get_stock_list(self):
        """获取股票列表（简化版 - 使用预设ETF替代）"""
        # 使用小盘股ETF作为代理
        # 实际应该用全市场股票，这里先用几只小盘风格ETF做概念验证
        etfs = {
            'sh510500': '中证500ETF',  # 中盘
            'sh512100': '中证1000ETF',  # 小盘
            'sz159915': '创业板ETF',    # 成长风格
            'sh588000': '科创50ETF',    # 科创板
        }
        return etfs
    
    def fetch_data(self):
        """获取ETF数据（用ETF代替个股做概念验证）"""
        print("📊 正在获取数据...")
        
        etfs = self.get_stock_list()
        start = f"{self.start_date[:4]}-{self.start_date[4:6]}-{self.start_date[6:]}"
        end = f"{self.end_date[:4]}-{self.end_date[4:6]}-{self.end_date[6:]}"
        
        for code, name in etfs.items():
            try:
                url = f'http://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={code},day,{start},{end},500,qfq'
                r = requests.get(url, timeout=30)
                data = r.json()
                kline_data = data['data'].get(code, {}).get('qfqday', [])
                
                if not kline_data:
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
                print(f"  ❌ {name}({code}): {e}")
        
        if not self.price_data:
            raise ValueError("未能获取数据")
            
        print(f"\n数据时间范围: {min(df.index.min() for df in self.price_data.values())} ~ "
              f"{max(df.index.max() for df in self.price_data.values())}")
    
    def backtest(self, initial_capital=100000):
        """执行回测（简化版 - 等权轮动）"""
        print("\n🚀 开始回测...")
        print(f"初始资金: ¥{initial_capital:,.0f}")
        print(f"标的池: {list(self.get_stock_list().values())}")
        
        # 获取所有交易日
        all_dates = set()
        for df in self.price_data.values():
            all_dates.update(df.index)
        
        min_date = max(df.index.min() for df in self.price_data.values())
        trade_dates = sorted([d for d in all_dates if d >= min_date])
        
        # 初始化
        cash = initial_capital
        positions = {}  # {code: shares}
        
        # 简化策略：等权买入所有标的，月度再平衡
        rebalance_days = 20  # 约一个月
        last_rebalance = -999
        
        for i, current_date in enumerate(trade_dates):
            # 获取当日价格
            prices = {code: df.loc[current_date, '收盘'] 
                     for code, df in self.price_data.items() 
                     if current_date in df.index}
            
            if not prices:
                continue
            
            # 计算当前总资产
            position_value = sum(positions.get(code, 0) * prices.get(code, 0) 
                                for code in positions)
            total_value = cash + position_value
            
            self.portfolio_value.append({
                'date': current_date,
                'value': total_value,
                'positions': len(positions)
            })
            
            # 调仓逻辑（每月初）
            if i - last_rebalance >= rebalance_days:
                # 卖出所有持仓
                for code in list(positions.keys()):
                    if code in prices:
                        cash += positions[code] * prices[code]
                        positions[code] = 0
                positions = {}
                
                # 等权买入
                n = len(prices)
                if n > 0 and cash > 0:
                    weight = cash / n
                    for code, price in prices.items():
                        if price > 0:
                            positions[code] = weight / price
                    cash = 0
                
                last_rebalance = i
                self.trade_log.append({
                    'date': current_date,
                    'action': 'rebalance',
                    'value': total_value
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
        
        self.metrics = {
            '初始资金': initial_capital,
            '最终资金': df['value'].iloc[-1],
            '总收益率': total_return,
            '年化收益率': annual_return,
            '年化波动率': volatility,
            '夏普比率': sharpe_ratio,
            '最大回撤': max_drawdown,
        }
        
        self.df = df
        return self.metrics
    
    def print_report(self):
        """打印回测报告"""
        print("\n" + "="*60)
        print("📊 小市值因子策略回测报告（ETF代理版）")
        print("="*60)
        
        print(f"\n回测结果:")
        print(f"  初始资金: ¥{self.metrics['初始资金']:,.0f}")
        print(f"  最终资金: ¥{self.metrics['最终资金']:,.0f}")
        print(f"  总收益率: {self.metrics['总收益率']:.2f}%")
        print(f"  年化收益率: {self.metrics['年化收益率']:.2f}%")
        print(f"  年化波动率: {self.metrics['年化波动率']:.2f}%")
        print(f"  夏普比率: {self.metrics['夏普比率']:.2f}")
        print(f"  最大回撤: {self.metrics['最大回撤']:.2f}%")
        print("="*60)
    
    def save_results(self):
        """保存结果"""
        # 保存净值曲线
        self.df.to_csv('/project/quant-research/backtests/smallcap_backtest.csv')
        
        # 绘制图表
        fig, axes = plt.subplots(2, 1, figsize=(12, 8))
        
        ax1 = axes[0]
        ax1.plot(self.df.index, self.df['cum_returns'], label='Strategy', color='#667eea')
        ax1.axhline(y=0, color='gray', linestyle='--', alpha=0.5)
        ax1.set_title('Small Cap Strategy - Cumulative Returns', fontsize=12)
        ax1.set_ylabel('Returns (%)')
        ax1.legend()
        ax1.grid(True, alpha=0.3)
        
        ax2 = axes[1]
        ax2.fill_between(self.df.index, self.df['drawdown'], 0, color='red', alpha=0.3)
        ax2.plot(self.df.index, self.df['drawdown'], color='red', linewidth=1)
        ax2.set_title('Drawdown Curve', fontsize=12)
        ax2.set_ylabel('Drawdown (%)')
        ax2.grid(True, alpha=0.3)
        
        plt.tight_layout()
        plt.savefig('/project/quant-research/backtests/smallcap_chart.png', dpi=150, bbox_inches='tight')
        print("\n📈 图表已保存")


def main():
    """主函数"""
    strategy = SmallCapStrategy(
        start_date='20200101',
        end_date='20241231'
    )
    
    strategy.fetch_data()
    metrics = strategy.backtest(initial_capital=100000)
    strategy.print_report()
    strategy.save_results()
    
    print("\n✅ 小市值策略初版回测完成！")
    print("\n💡 说明：这是用中小盘ETF代替个股的概念验证版本")
    print("   后续需要接入真实的小市值股票数据")


if __name__ == '__main__':
    main()
