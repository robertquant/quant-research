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
matplotlib.use('Agg')  # 非交互式后端
import matplotlib.pyplot as plt
import warnings
warnings.filterwarnings('ignore')

# 设置中文字体
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
        
        # ETF标的池配置 (腾讯财经代码格式)
        self.etfs = {
            'sh510300': '沪深300ETF',
            'sh510500': '中证500ETF',
            'sz159915': '创业板ETF',
            'sh588000': '科创50ETF'
        }
        
        # 大盘过滤基准
        self.market_etf = 'sh510300'
        
        # 数据存储
        self.price_data = {}
        self.trade_log = []
        self.portfolio_value = []
        
    def fetch_data(self):
        """从腾讯财经获取ETF历史数据"""
        print("📊 正在获取ETF数据...")
        
        # 转换日期格式
        start = f"{self.start_date[:4]}-{self.start_date[4:6]}-{self.start_date[6:]}"
        end = f"{self.end_date[:4]}-{self.end_date[4:6]}-{self.end_date[6:]}"
        
        for code, name in self.etfs.items():
            try:
                # 腾讯财经接口
                url = f'http://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={code},day,{start},{end},500,qfq'
                r = requests.get(url, timeout=30)
                data = r.json()
                
                # 解析数据
                kline_data = data['data'].get(code, {}).get('qfqday', [])
                
                if not kline_data:
                    print(f"  ⚠️ {name}({code}): 无数据")
                    continue
                
                # 转换为DataFrame
                df_data = []
                for row in kline_data:
                    try:
                        df_data.append({
                            '日期': row[0],
                            '开盘': float(row[1]),
                            '收盘': float(row[2]),
                            '最低': float(row[3]),
                            '最高': float(row[4]),
                            '成交量': float(row[5])  # 成交量可能是浮点数
                        })
                    except Exception as e:
                        print(f"    解析行失败: {row}, 错误: {e}")
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
    
    def calculate_signals(self, current_date):
        """计算当日交易信号"""
        signals = {
            'date': current_date,
            'momentum': {},
            'market_above_ma': False,
            'selected_etf': None,
            'action': 'hold'
        }
        
        # 1. 计算各ETF动量（20日涨幅）
        for code, df in self.price_data.items():
            if current_date in df.index:
                current_price = df.loc[current_date, '收盘']
                
                # 获取N交易日前的价格
                try:
                    idx = df.index.get_loc(current_date)
                    if idx >= self.momentum_window:
                        past_price = df.iloc[idx - self.momentum_window]['收盘']
                        momentum = (current_price / past_price - 1) * 100
                        signals['momentum'][code] = {
                            'name': self.etfs[code],
                            'momentum': momentum,
                            'price': current_price
                        }
                except:
                    signals['momentum'][code] = {
                        'name': self.etfs[code],
                        'momentum': np.nan,
                        'price': current_price
                    }
        
        # 2. 大盘趋势过滤
        market_df = self.price_data.get(self.market_etf)
        if market_df is not None and current_date in market_df.index:
            idx = market_df.index.get_loc(current_date)
            if idx >= self.market_filter_window:
                ma_window = market_df.iloc[idx - self.market_filter_window + 1:idx + 1]['收盘']
                ma20 = ma_window.mean()
                current_price = market_df.loc[current_date, '收盘']
                signals['market_above_ma'] = current_price > ma20
        
        # 3. 选择动量最强的ETF
        valid_momentum = {k: v for k, v in signals['momentum'].items() 
                         if not np.isnan(v['momentum'])}
        
        if valid_momentum:
            best_etf = max(valid_momentum.items(), key=lambda x: x[1]['momentum'])
            signals['selected_etf'] = best_etf[0]
            signals['best_momentum'] = best_etf[1]['momentum']
        
        # 4. 确定操作
        if not signals['market_above_ma']:
            signals['action'] = 'empty'
        elif signals['selected_etf']:
            signals['action'] = 'switch'
        
        return signals
    
    def backtest(self, initial_capital=100000):
        """执行回测"""
        print("\n🚀 开始回测...")
        print(f"初始资金: ¥{initial_capital:,.0f}")
        print(f"动量窗口: {self.momentum_window}日")
        print(f"大盘过滤: 沪深300 {self.market_filter_window}日均线\n")
        
        # 获取所有交易日
        all_dates = set()
        for df in self.price_data.values():
            all_dates.update(df.index)
        
        min_date = max(df.index.min() for df in self.price_data.values()) + timedelta(days=self.momentum_window)
        trade_dates = sorted([d for d in all_dates if d >= min_date])
        
        # 初始化持仓
        cash = initial_capital
        position = None
        position_value = 0
        
        # 回测循环
        for i, current_date in enumerate(trade_dates):
            signals = self.calculate_signals(current_date)
            
            # 获取当日各ETF价格
            prices = {}
            for code, df in self.price_data.items():
                if current_date in df.index:
                    prices[code] = df.loc[current_date, '收盘']
            
            if not prices:
                continue
            
            # 计算当前总资产
            if position and position in prices:
                # 根据当前价格计算持仓市值
                shares = position_value / prices[position] if prices[position] > 0 else 0
                current_position_value = shares * prices[position]
                total_value = cash + current_position_value
            else:
                total_value = cash
            
            # 更新position_value为当前市值
            if position and position in prices:
                position_value = shares * prices[position] if prices[position] > 0 else 0
            
            self.portfolio_value.append({
                'date': current_date,
                'value': total_value,
                'position': position,
                'action': signals['action']
            })
            
            # 执行交易
            if signals['action'] == 'empty':
                if position:
                    sell_price = prices.get(position, 0)
                    cash += position_value
                    self.trade_log.append({
                        'date': current_date,
                        'action': 'sell',
                        'code': position,
                        'price': sell_price,
                        'reason': 'market_filter'
                    })
                    position = None
                    position_value = 0
                    
            elif signals['action'] == 'switch' and signals['selected_etf']:
                selected = signals['selected_etf']
                
                if position != selected:
                    if position:
                        sell_price = prices.get(position, 0)
                        cash += position_value
                        self.trade_log.append({
                            'date': current_date,
                            'action': 'sell',
                            'code': position,
                            'price': sell_price,
                            'reason': 'rotation'
                        })
                    
                    buy_price = prices.get(selected, 0)
                    if buy_price > 0 and cash > 0:
                        position_value = cash
                        cash = 0
                        position = selected
                        self.trade_log.append({
                            'date': current_date,
                            'action': 'buy',
                            'code': selected,
                            'price': buy_price,
                            'momentum': signals['best_momentum']
                        })
            
            # 更新持仓市值
            if position and position in prices:
                position_value = position_value * prices[position] / prices.get(position, position_value)
        
        print(f"✅ 回测完成！共{len(trade_dates)}个交易日，{len([t for t in self.trade_log if t['action']=='buy'])}笔交易")
        return self.calculate_metrics(initial_capital)
    
    def calculate_metrics(self, initial_capital):
        """计算回测指标"""
        if not self.portfolio_value:
            return {}
        
        df = pd.DataFrame(self.portfolio_value)
        df.set_index('date', inplace=True)
        
        # 计算收益率
        df['returns'] = df['value'].pct_change()
        df['cum_returns'] = (df['value'] / initial_capital - 1) * 100
        
        # 关键指标
        total_return = (df['value'].iloc[-1] / initial_capital - 1) * 100
        annual_return = total_return / (len(df) / 252)
        volatility = df['returns'].std() * np.sqrt(252) * 100
        sharpe_ratio = annual_return / volatility if volatility > 0 else 0
        
        # 最大回撤
        df['cummax'] = df['value'].cummax()
        df['drawdown'] = (df['value'] / df['cummax'] - 1) * 100
        max_drawdown = df['drawdown'].min()
        
        # 交易统计
        trades_df = pd.DataFrame(self.trade_log)
        buy_trades = trades_df[trades_df['action'] == 'buy'] if len(trades_df) > 0 else pd.DataFrame()
        
        metrics = {
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
        
        self.metrics = metrics
        self.df = df
        
        return metrics
    
    def plot_results(self, save_path=None):
        """绘制回测结果图表"""
        if not hasattr(self, 'df'):
            print("请先运行回测")
            return
        
        fig, axes = plt.subplots(3, 1, figsize=(14, 10))
        
        # 1. 净值曲线
        ax1 = axes[0]
        ax1.plot(self.df.index, self.df['cum_returns'], label='Strategy', linewidth=1.5, color='#667eea')
        ax1.axhline(y=0, color='gray', linestyle='--', alpha=0.5)
        ax1.set_title('ETF Rotation Strategy - Cumulative Returns', fontsize=12)
        ax1.set_ylabel('Returns (%)')
        ax1.legend()
        ax1.grid(True, alpha=0.3)
        
        # 2. 回撤曲线
        ax2 = axes[1]
        ax2.fill_between(self.df.index, self.df['drawdown'], 0, 
                         color='red', alpha=0.3, label='Drawdown')
        ax2.plot(self.df.index, self.df['drawdown'], color='red', linewidth=1)
        ax2.set_title('Drawdown Curve', fontsize=12)
        ax2.set_ylabel('Drawdown (%)')
        ax2.legend()
        ax2.grid(True, alpha=0.3)
        
        # 3. 持仓状态
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
    # 创建策略实例
    strategy = ETFRotationStrategy(
        start_date='20190101',
        end_date='20241231',
        momentum_window=20,
        market_filter_window=20
    )
    
    # 获取数据
    strategy.fetch_data()
    
    # 运行回测
    metrics = strategy.backtest(initial_capital=100000)
    
    # 打印报告
    strategy.print_report()
    
    # 绘制图表
    strategy.plot_results(save_path='/project/quant-research/backtests/etf_rotation_chart.png')
    
    # 保存交易记录
    strategy.save_trade_log('/project/quant-research/backtests/etf_rotation_trades.csv')
    
    print("\n✅ 策略回测完成！")


if __name__ == '__main__':
    main()
