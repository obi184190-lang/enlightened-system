#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
數據精準度檢驗模組 - Phase 5.2.5 Day 1
"""

import yfinance as yf
import pandas as pd
from datetime import datetime
from typing import Dict, List

class DataAdjustmentDetector:
    """數據精準度檢驗器"""
    
    def __init__(self):
        self.test_stocks = ['2330', '2303', '2637', '2317', '2412', '4938']
    
    def detect_adjustments(self, stock_code: str, period: str = "6mo") -> Dict:
        """檢測股票是否有除權息或分割"""
        
        try:
            ticker_code = f"{stock_code}.TW"
            ticker = yf.Ticker(ticker_code)
            hist = ticker.history(period=period)
            
            if hist.empty:
                return {'success': False, 'error': f'無法獲取 {ticker_code} 數據'}
            
            # 執行檢測
            adjustments = {
                'price_jumps': self._detect_price_jumps(hist),
                'dividends': self._detect_dividends(ticker),
                'price_consistency': self._check_price_consistency(hist),
            }
            
            # 綜合判斷
            has_adjustment = (
                adjustments['price_jumps']['detected'] or
                adjustments['dividends']['detected']
            )
            
            data_quality = self._assess_data_quality(adjustments)
            recommendations = self._generate_recommendations(adjustments)
            
            return {
                'success': True,
                'stock_code': stock_code,
                'has_adjustment': has_adjustment,
                'data_quality': data_quality,
                'recommendations': recommendations,
                'details': adjustments
            }
        
        except Exception as e:
            return {'success': False, 'stock_code': stock_code, 'error': str(e)}
    
    def _detect_price_jumps(self, hist: pd.DataFrame) -> Dict:
        """檢測異常價格跳變"""
        
        if hist.empty or len(hist) < 2:
            return {'detected': False}
        
        price_changes = hist['Close'].pct_change()
        suspicious_changes = price_changes[abs(price_changes) > 0.30]
        
        if len(suspicious_changes) > 0:
            return {
                'detected': True,
                'dates': len(suspicious_changes),
                'cause': '股票分割或合併'
            }
        return {'detected': False}
    
    def _detect_dividends(self, ticker) -> Dict:
        """檢測股利公告"""
        
        try:
            dividends = ticker.dividends
            if dividends.empty:
                return {'detected': False}
            
            recent_dividend = dividends.iloc[-1]
            recent_date = dividends.index[-1]
            days_ago = (datetime.now() - recent_date).days
            is_recent = days_ago <= 90
            
            return {
                'detected': is_recent,
                'amount': f"{recent_dividend:.2f}",
                'date': recent_date.strftime('%Y-%m-%d'),
                'days_ago': days_ago
            }
        except:
            return {'detected': False}
    
    def _check_price_consistency(self, hist: pd.DataFrame) -> Dict:
        """檢查價格與 MA 的一致性"""
        
        try:
            if len(hist) < 50:
                return {'status': 'insufficient_data'}
            
            close = hist['Close']
            current = close.iloc[-1]
            ma20 = close.rolling(20).mean().iloc[-1]
            
            deviation = abs(current - ma20) / ma20 if ma20 > 0 else 0
            
            if deviation > 0.20:
                return {'status': 'anomaly', 'deviation': f"{deviation*100:.1f}%"}
            return {'status': 'normal'}
        except:
            return {'status': 'error'}
    
    def _assess_data_quality(self, adjustments: Dict) -> str:
        """評估數據品質"""
        
        warnings = 0
        if adjustments['price_jumps'].get('detected'):
            warnings += 2
        if adjustments['dividends'].get('detected'):
            warnings += 1
        if adjustments['price_consistency'].get('status') == 'anomaly':
            warnings += 2
        
        if warnings == 0:
            return '✓ 良好'
        elif warnings <= 2:
            return '⚠️ 注意'
        else:
            return '✗ 需檢查'
    
    def _generate_recommendations(self, adjustments: Dict) -> List[str]:
        """生成建議"""
        
        recommendations = []
        
        if adjustments['price_jumps'].get('detected'):
            recommendations.append('✗ 檢測到股票分割→技術指標需重新計算')
        
        if adjustments['dividends'].get('detected'):
            amount = adjustments['dividends'].get('amount', '?')
            recommendations.append(f'⚠️ 股利公告({amount}元)→確認股價已調整')
        
        if adjustments['price_consistency'].get('status') == 'anomaly':
            dev = adjustments['price_consistency'].get('deviation', '?')
            recommendations.append(f'⚠️ 價格偏離 MA20 {dev}→查證原因')
        
        if not recommendations:
            recommendations.append('✓ 數據品質良好，無需特殊處理')
        
        return recommendations
    
    def test_all_stocks(self) -> Dict:
        """測試所有 6 支股票"""
        
        print("\n" + "="*70)
        print("開明體系 Phase 5.2.5 - Day 1 數據精準度檢驗")
        print("="*70)
        print(f"檢驗時間：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*70 + "\n")
        
        results = {
            'good': 0,
            'warning': 0,
            'poor': 0,
            'stocks': []
        }
        
        for stock_code in self.test_stocks:
            print(f"檢驗 {stock_code}...", end=' ', flush=True)
            
            result = self.detect_adjustments(stock_code)
            
            if not result.get('success'):
                print(f"❌ 失敗")
                continue
            
            quality = result['data_quality']
            print(quality)
            
            # 統計
            if '良好' in quality:
                results['good'] += 1
            elif '注意' in quality:
                results['warning'] += 1
                if result['recommendations']:
                    print(f"  {result['recommendations'][0]}")
            else:
                results['poor'] += 1
                if result['recommendations']:
                    print(f"  {result['recommendations'][0]}")
            
            results['stocks'].append({
                'code': stock_code,
                'quality': quality,
                'has_adjustment': result['has_adjustment']
            })
        
        # 總結
        total = len(results['stocks'])
        print("\n" + "="*70)
        print("📊 檢驗結果總結")
        print("="*70)
        print(f"✓ 良好：{results['good']}/{total}")
        print(f"⚠️  注意：{results['warning']}/{total}")
        print(f"✗ 需檢查：{results['poor']}/{total}")
        
        if results['good'] == total:
            print(f"\n🎉 太棒了！所有 {total} 支股票數據品質都很好！")
        else:
            print(f"\n⚠️  共 {results['warning'] + results['poor']} 支股票需注意")
        
        print("="*70 + "\n")
        
        return results


def main():
    """主程式"""
    detector = DataAdjustmentDetector()
    results = detector.test_all_stocks()
    return results


if __name__ == '__main__':
    main()
