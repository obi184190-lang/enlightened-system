#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
動態目標價/止損價計算 - Phase 5.2.5 Week 2 Day 6-7
基於 ATR（平均真實波幅）和技術面關鍵位
"""

import yfinance as yf
import pandas as pd
from datetime import datetime
from typing import Dict

class DynamicTargetCalculator:
    """動態目標價計算器"""
    
    def __init__(self):
        self.test_stocks = ['2330', '2303', '2637', '2317', '2412', '4938']
    
    def calculate_dynamic_targets(self, stock_code: str, entry_price: float = None, risk_level: str = 'moderate') -> Dict:
        """計算動態目標價和止損價"""
        try:
            ticker_code = f"{stock_code}.TW"
            ticker = yf.Ticker(ticker_code)
            hist = ticker.history(period="100d")
            
            if hist.empty:
                return {'success': False, 'stock_code': stock_code, 'error': f'無法獲取數據'}
            
            atr = self._calculate_atr(hist)
            current_price = hist['Close'].iloc[-1]
            
            if entry_price is None:
                entry_price = current_price
            
            volatility = self._classify_volatility(hist, atr)
            
            if risk_level == 'conservative':
                target_multiplier, stop_loss_multiplier = 1.5, 0.8
            elif risk_level == 'moderate':
                target_multiplier, stop_loss_multiplier = 2.0, 1.0
            else:
                target_multiplier, stop_loss_multiplier = 2.5, 1.2
            
            if volatility == 'high':
                target_multiplier *= 0.9
                stop_loss_multiplier *= 1.1
            elif volatility == 'low':
                target_multiplier *= 1.1
                stop_loss_multiplier *= 0.9
            
            target_price = entry_price + (atr * target_multiplier)
            stop_loss = entry_price - (atr * stop_loss_multiplier)
            
            profit = target_price - entry_price
            loss = entry_price - stop_loss
            risk_reward = profit / loss if loss > 0 else 0
            
            return {
                'success': True,
                'stock_code': stock_code,
                'current_price': round(current_price, 2),
                'entry_price': round(entry_price, 2),
                'target_price': round(target_price, 2),
                'stop_loss': round(stop_loss, 2),
                'profit_amount': round(profit, 2),
                'loss_amount': round(loss, 2),
                'risk_reward_ratio': round(risk_reward, 2),
                'atr_value': round(atr, 2),
                'volatility': volatility,
                'method': 'ATR_based'
            }
        except Exception as e:
            return {'success': False, 'stock_code': stock_code, 'error': str(e)}
    
    def _calculate_atr(self, hist: pd.DataFrame, period: int = 14) -> float:
        """計算 ATR"""
        try:
            high = hist['High']
            low = hist['Low']
            close = hist['Close']
            
            tr1 = high - low
            tr2 = abs(high - close.shift())
            tr3 = abs(low - close.shift())
            
            tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
            atr = tr.rolling(period).mean()
            
            return atr.iloc[-1]
        except:
            return 0
    
    def _classify_volatility(self, hist: pd.DataFrame, atr: float) -> str:
        """分類波動率"""
        try:
            current_price = hist['Close'].iloc[-1]
            atr_percentage = (atr / current_price) * 100
            
            if atr_percentage > 5:
                return 'high'
            elif atr_percentage > 2.5:
                return 'moderate'
            else:
                return 'low'
        except:
            return 'moderate'
    
    def test_all_stocks(self) -> Dict:
        """測試所有 6 支股票"""
        print("\n" + "="*70)
        print("開明體系 Phase 5.2.5 - Week 2 Day 6-7 動態目標價計算")
        print("="*70)
        print(f"檢驗時間：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*70 + "\n")
        
        results = {'test_time': datetime.now().isoformat(), 'total_stocks': len(self.test_stocks), 'stocks_tested': 0, 'detailed_results': []}
        
        for stock_code in self.test_stocks:
            print(f"計算 {stock_code}...", end=' ', flush=True)
            
            result = self.calculate_dynamic_targets(stock_code)
            
            if not result.get('success'):
                print(f"❌ 失敗")
                continue
            
            results['stocks_tested'] += 1
            
            print(f"✓ 完成")
            print(f"  • 當前價：{result['current_price']:.2f}")
            print(f"  • 目標價：{result['target_price']:.2f} (RR: {result['risk_reward_ratio']:.2f}x)")
            print(f"  • 止損價：{result['stop_loss']:.2f}")
            print(f"  • ATR：{result['atr_value']:.2f} | 波動率：{result['volatility']}")
            
            results['detailed_results'].append(result)
        
        print("\n" + "="*70)
        print("📊 計算結果總結")
        print("="*70)
        print(f"✓ 成功計算：{results['stocks_tested']}/{results['total_stocks']}")
        
        if results['stocks_tested'] > 0:
            rr_ratios = [r['risk_reward_ratio'] for r in results['detailed_results']]
            print(f"\n📈 風報比統計：")
            print(f"  • 平均：{sum(rr_ratios)/len(rr_ratios):.2f}x")
            print(f"  • 最高：{max(rr_ratios):.2f}x")
            print(f"  • 最低：{min(rr_ratios):.2f}x")
        
        print("="*70 + "\n")
        
        return results


def main():
    calculator = DynamicTargetCalculator()
    results = calculator.test_all_stocks()
    return results


if __name__ == '__main__':
    main()
