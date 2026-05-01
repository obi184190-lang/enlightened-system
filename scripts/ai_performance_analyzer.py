#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI 分析表現追蹤系統 - Phase 5.2.2
分析開明體系 AI 建議的實際表現
"""

import os
import requests
from datetime import datetime, timedelta
from typing import Dict, List
import yfinance as yf
from supabase import create_client, Client

# Supabase 配置
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_ANON_KEY')

# Telegram 配置
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

class AIPerformanceAnalyzer:
    """AI 表現分析器"""
    
    def __init__(self):
        """初始化"""
        self.supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    
    def send_telegram_message(self, message: str) -> bool:
        """
        發送訊息到 Telegram
        
        Args:
            message: 要發送的訊息
            
        Returns:
            是否發送成功
        """
        if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
            print("Telegram 未配置，跳過通知")
            return False
        
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {
            'chat_id': TELEGRAM_CHAT_ID,
            'text': message,
            'parse_mode': 'HTML'
        }
        
        try:
            response = requests.post(url, json=payload, timeout=10)
            response.raise_for_status()
            print("Telegram 訊息已發送")
            return True
        except Exception as e:
            print(f"Telegram 發送失敗: {e}")
            return False
    
    
    def get_recent_signals(self, days: int = 5) -> List[Dict]:
        """
        獲取最近 N 天的 AI 信號
        
        Args:
            days: 回溯天數
            
        Returns:
            信號列表
        """
        cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()
        
        response = self.supabase.table('trade_logs')\
            .select('*')\
            .gte('timestamp', cutoff_date)\
            .order('timestamp', desc=True)\
            .execute()
        
        return response.data
    
    def get_current_price(self, stock_code: str) -> float:
        """
        獲取股票當前價格
        
        Args:
            stock_code: 股票代號（如 2303）
            
        Returns:
            當前價格
        """
        try:
            ticker = yf.Ticker(f"{stock_code}.TW")
            hist = ticker.history(period="1d")
            if not hist.empty:
                return hist['Close'].iloc[-1]
        except Exception as e:
            print(f"獲取 {stock_code} 價格失敗: {e}")
        return None
    
    def analyze_signal_performance(self, signal: Dict) -> Dict:
        """
        分析單一信號的表現
        
        Args:
            signal: 信號記錄
            
        Returns:
            表現分析結果
        """
        stock_code = signal.get('stock_code', 'Unknown')
        signal_type = signal.get('signal_type', 'HOLD')
        entry_price = signal.get('price', 0)
        confidence = signal.get('confidence', 0.0)
        signal_time = signal.get('timestamp', '')
        
        # 獲取當前價格
        current_price = self.get_current_price(stock_code)
        
        if not current_price:
            return {
                'stock_code': stock_code,
                'status': 'error',
                'message': '無法獲取當前價格'
            }
        
        # 計算價格變化
        price_change = ((current_price - entry_price) / entry_price) * 100
        
        # 計算目標價與止損價
        target_price = entry_price * 1.15  # +15%
        stop_loss = entry_price * 0.95     # -5%
        
        # 判斷結果
        result = {
            'stock_code': stock_code,
            'signal_type': signal_type,
            'signal_time': signal_time,
            'confidence': confidence,
            'entry_price': entry_price,
            'current_price': current_price,
            'price_change': price_change,
            'target_price': target_price,
            'stop_loss': stop_loss,
        }
        
        # 判斷狀態
        if signal_type == 'BUY':
            if current_price >= target_price:
                result['status'] = '✅ 達標'
                result['performance'] = 'excellent'
            elif current_price <= stop_loss:
                result['status'] = '🛑 止損'
                result['performance'] = 'poor'
            elif price_change > 0:
                result['status'] = '📈 獲利中'
                result['performance'] = 'good'
            else:
                result['status'] = '📉 虧損中'
                result['performance'] = 'fair'
        elif signal_type == 'SELL':
            if price_change < 0:
                result['status'] = '✅ 正確'
                result['performance'] = 'excellent'
            else:
                result['status'] = '❌ 錯誤'
                result['performance'] = 'poor'
        else:  # HOLD
            result['status'] = '⚫ 持有'
            result['performance'] = 'neutral'
        
        return result
    
    def generate_performance_report(self, days: int = 5) -> str:
        """
        生成表現報告
        
        Args:
            days: 回溯天數
            
        Returns:
            報告文字
        """
        signals = self.get_recent_signals(days)
        
        if not signals:
            return "⚠️ 沒有找到最近的信號記錄"
        
        report = f"📊 <b>AI 分析表現報告</b>\n"
        report += f"時間範圍: 最近 {days} 天\n"
        report += f"分析時間: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
        report += "=" * 40 + "\n\n"
        
        # 統計數據
        buy_signals = [s for s in signals if s['signal_type'] == 'BUY']
        sell_signals = [s for s in signals if s['signal_type'] == 'SELL']
        
        report += f"📈 BUY 信號: {len(buy_signals)} 個\n"
        report += f"📉 SELL 信號: {len(sell_signals)} 個\n"
        report += f"總計: {len(signals)} 個信號\n\n"
        
        # 分析每個 BUY 信號
        if buy_signals:
            report += "📊 <b>BUY 信號表現</b>\n"
            report += "-" * 40 + "\n"
            
            excellent = 0
            good = 0
            fair = 0
            poor = 0
            
            for signal in buy_signals:
                analysis = self.analyze_signal_performance(signal)
                
                report += f"\n{analysis['stock_code']} - {analysis['status']}\n"
                report += f"  建議時間: {analysis['signal_time'][:19]}\n"
                report += f"  信心度: {analysis['confidence']:.1%}\n"
                report += f"  建議價: {analysis['entry_price']:.2f}\n"
                report += f"  當前價: {analysis['current_price']:.2f}\n"
                report += f"  漲跌幅: {analysis['price_change']:+.2f}%\n"
                
                # 統計
                if analysis['performance'] == 'excellent':
                    excellent += 1
                elif analysis['performance'] == 'good':
                    good += 1
                elif analysis['performance'] == 'fair':
                    fair += 1
                elif analysis['performance'] == 'poor':
                    poor += 1
            
            # 總結
            report += "\n" + "=" * 40 + "\n"
            report += "<b>📊 表現統計</b>\n"
            report += f"✅ 達標: {excellent} ({excellent/len(buy_signals)*100:.1f}%)\n"
            report += f"📈 獲利中: {good} ({good/len(buy_signals)*100:.1f}%)\n"
            report += f"📉 虧損中: {fair} ({fair/len(buy_signals)*100:.1f}%)\n"
            report += f"🛑 止損: {poor} ({poor/len(buy_signals)*100:.1f}%)\n"
            
            # 準確率
            success_rate = (excellent + good) / len(buy_signals) * 100
            report += f"\n<b>🎯 整體準確率: {success_rate:.1f}%</b>\n"
        
        return report
    
    def analyze_by_confidence_level(self, days: int = 5) -> str:
        """
        按信心度分級分析
        
        Args:
            days: 回溯天數
            
        Returns:
            分析報告
        """
        signals = self.get_recent_signals(days)
        buy_signals = [s for s in signals if s['signal_type'] == 'BUY']
        
        if not buy_signals:
            return "⚠️ 沒有 BUY 信號"
        
        report = "📊 <b>信心度分級表現</b>\n"
        report += "=" * 40 + "\n\n"
        
        # 分級
        high_conf = []  # >= 70%
        medium_conf = []  # 50-70%
        low_conf = []  # < 50%
        
        for signal in buy_signals:
            analysis = self.analyze_signal_performance(signal)
            confidence = signal.get('confidence', 0.0)
            if confidence >= 0.70:
                high_conf.append(analysis)
            elif confidence >= 0.50:
                medium_conf.append(analysis)
            else:
                low_conf.append(analysis)
        
        # 分析高信心度
        if high_conf:
            report += "🔴 <b>高信心度 (≥70%)</b>\n"
            success = sum(1 for a in high_conf if a['performance'] in ['excellent', 'good'])
            report += f"成功率: {success/len(high_conf)*100:.1f}% ({success}/{len(high_conf)})\n"
            avg_change = sum(a['price_change'] for a in high_conf) / len(high_conf)
            report += f"平均漲跌: {avg_change:+.2f}%\n\n"
        
        # 分析中信心度
        if medium_conf:
            report += "🟡 <b>中信心度 (50-70%)</b>\n"
            success = sum(1 for a in medium_conf if a['performance'] in ['excellent', 'good'])
            report += f"成功率: {success/len(medium_conf)*100:.1f}% ({success}/{len(medium_conf)})\n"
            avg_change = sum(a['price_change'] for a in medium_conf) / len(medium_conf)
            report += f"平均漲跌: {avg_change:+.2f}%\n\n"
        
        # 分析低信心度
        if low_conf:
            report += "⚪ <b>低信心度 (<50%)</b>\n"
            success = sum(1 for a in low_conf if a['performance'] in ['excellent', 'good'])
            report += f"成功率: {success/len(low_conf)*100:.1f}% ({success}/{len(low_conf)})\n"
            avg_change = sum(a['price_change'] for a in low_conf) / len(low_conf)
            report += f"平均漲跌: {avg_change:+.2f}%\n"
        
        return report


def main():
    """主函數"""
    analyzer = AIPerformanceAnalyzer()
    
    print("=" * 60)
    print("開明體系 AI 表現分析")
    print("=" * 60)
    
    # 生成報告
    report = analyzer.generate_performance_report(days=5)
    print(report)
    
    print("\n")
    
    # 信心度分析
    conf_report = analyzer.analyze_by_confidence_level(days=5)
    print(conf_report)
    
    # 發送到 Telegram
    full_report = report + "\n\n" + conf_report
    analyzer.send_telegram_message(full_report)


if __name__ == '__main__':
    main()
