#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
股票監控與交易決策系統
Stock Monitor & Trading Bot for Taiwan Stock Market (2303, 2637, 4938)
"""

import os
import sys
import json
import logging
import requests
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import time

# 設置日誌
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 環境變量
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_ANON_KEY = os.getenv('SUPABASE_ANON_KEY')
SUPABASE_SERVICE_ROLE_KEY = os.getenv('SUPABASE_SERVICE_ROLE_KEY')

# 監控的股票代碼（台灣股市）
STOCK_CODES = ['2303', '2637', '4938']
STOCK_NAMES = {
    '2303': '聯電',
    '2637': '慧洋-KY',
    '4938': '和碩'
}

class TaiwanStockMonitor:
    """台灣股市監控器"""
    
    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'
        }
        self.supabase_headers = {
            'apikey': SUPABASE_ANON_KEY,
            'Authorization': f'Bearer {SUPABASE_ANON_KEY}',
            'Content-Type': 'application/json'
        }
    
    def fetch_stock_data(self, stock_code: str) -> Optional[Dict]:
        """
        從台灣股市 API 抓取股票數據
        使用 TwStock API (免費，無需認證)
        """
        try:
            # 使用台灣股市公開 API
            url = f'https://tw-stock-api.herokuapp.com/api/tse/{stock_code}'
            
            response = requests.get(url, headers=self.headers, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            
            if 'data' in data and data['data']:
                stock_info = {
                    'code': stock_code,
                    'name': STOCK_NAMES.get(stock_code, stock_code),
                    'price': float(data['data'][-1]['close']), # 最新收盤價
                    'timestamp': datetime.now().isoformat(),
                    'high': float(data['data'][-1]['high']),
                    'low': float(data['data'][-1]['low']),
                    'volume': int(data['data'][-1]['volume'])
                }
                return stock_info
            
            logger.warning(f"Stock {stock_code} 無可用數據")
            return None
            
        except requests.exceptions.RequestException as e:
            logger.error(f"抓取 {stock_code} 數據失敗: {str(e)}")
            return None
    
    def calculate_ma(self, prices: List[float], period: int) -> Optional[float]:
        """計算移動平均線 (MA)"""
        if len(prices) < period:
            return None
        return sum(prices[-period:]) / period
    
    def calculate_rsi(self, prices: List[float], period: int = 14) -> Optional[float]:
        """計算相對強度指數 (RSI)"""
        if len(prices) < period + 1:
            return None
        
        deltas = [prices[i] - prices[i-1] for i in range(1, len(prices))]
        seed = deltas[:period]
        
        up = sum([x for x in seed if x > 0]) / period
        down = sum([abs(x) for x in seed if x < 0]) / period
        
        rs = up / down if down != 0 else 0
        rsi = 100 - (100 / (1 + rs)) if rs >= 0 else 0
        
        return rsi
    
    def generate_signal(self, stock_code: str, price: float, 
                       ma_20: Optional[float], ma_50: Optional[float], 
                       rsi: Optional[float]) -> Dict:
        """
        生成買賣信號
        策略：
        - BUY: 價格 > MA20 > MA50，且 RSI < 70
        - SELL: 價格 < MA20，或 RSI > 80
        """
        signal = {
            'code': stock_code,
            'price': price,
            'ma_20': ma_20,
            'ma_50': ma_50,
            'rsi': rsi,
            'signal_type': 'HOLD',
            'confidence': 0.0,
            'decision_logic': '無明確信號'
        }
        
        # 判斷買入信號
        if ma_20 and ma_50 and price > ma_20 > ma_50:
            if rsi and rsi < 70:
                signal['signal_type'] = 'BUY'
                signal['confidence'] = min(1.0, (price - ma_50) / (ma_50 * 0.1))
                signal['decision_logic'] = f'價格突破MA20/MA50，RSI={rsi:.2f}'
        
        # 判斷賣出信號
        elif ma_20 and price < ma_20:
            signal['signal_type'] = 'SELL'
            signal['confidence'] = 0.7
            signal['decision_logic'] = f'價格跌破MA20，需要止損'
        
        elif rsi and rsi > 80:
            signal['signal_type'] = 'SELL'
            signal['confidence'] = 0.6
            signal['decision_logic'] = f'RSI過高={rsi:.2f}，需要獲利了結'
        
        return signal
    
    def save_to_supabase(self, table: str, data: Dict) -> bool:
        """保存數據到 Supabase"""
        try:
            url = f'{SUPABASE_URL}/rest/v1/{table}'
            
            response = requests.post(
                url,
                headers=self.supabase_headers,
                json=data,
                timeout=10
            )
            
            if response.status_code in [200, 201]:
                logger.info(f"數據已保存到 {table}: {data.get('code', 'unknown')}")
                return True
            else:
                logger.error(f"保存失敗: {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"Supabase 保存失敗: {str(e)}")
            return False
    
    def send_telegram_notification(self, message: str) -> bool:
        """發送 Telegram 通知（如果已配置）"""
        telegram_token = os.getenv('TELEGRAM_BOT_TOKEN')
        telegram_chat_id = os.getenv('TELEGRAM_CHAT_ID')
        
        if not telegram_token or not telegram_chat_id:
            logger.info("Telegram 未配置，跳過通知")
            return False
        
        try:
            url = f'https://api.telegram.org/bot{telegram_token}/sendMessage'
            payload = {
                'chat_id': telegram_chat_id,
                'text': message,
                'parse_mode': 'HTML'
            }
            
            response = requests.post(url, json=payload, timeout=10)
            
            if response.status_code == 200:
                logger.info("Telegram 通知已發送")
                return True
            else:
                logger.warning(f"Telegram 發送失敗: {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"Telegram 通知異常: {str(e)}")
            return False
    
    def run_monitoring_cycle(self):
        """執行一個監控週期"""
        logger.info("=" * 60)
        logger.info(f"開始監控週期 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info("=" * 60)
        
        all_signals = []
        
        for stock_code in STOCK_CODES:
            logger.info(f"\n監控股票: {STOCK_NAMES[stock_code]} ({stock_code})")
            
            # 抓取最新數據
            stock_data = self.fetch_stock_data(stock_code)
            if not stock_data:
                continue
            
            price = stock_data['price']
            logger.info(f" 當前價格: {price:.2f}")
            
            # 這裡簡化處理：用當前價格作為示例
            # 在實際應用中，應該從歷史數據計算
            ma_20 = price * 0.98 # 簡化示例
            ma_50 = price * 0.96 # 簡化示例
            rsi = 55.0 # 簡化示例
            
            # 生成信號
            signal = self.generate_signal(
                stock_code=stock_code,
                price=price,
                ma_20=ma_20,
                ma_50=ma_50,
                rsi=rsi
            )
            
            all_signals.append(signal)
            
            # 保存交易日誌
            trade_log = {
                'stock_code': stock_code,
                'signal_type': signal['signal_type'],
                'price': price,
                'decision_logic': signal['decision_logic'],
                'profit_loss': 0.0,
                'timestamp': datetime.now().isoformat()
            }
            
            self.save_to_supabase('trade_logs', trade_log)
            
            logger.info(f" 信號: {signal['signal_type']} (信心度: {signal['confidence']:.2%})")
            logger.info(f" 邏輯: {signal['decision_logic']}")
        
        # 發送摘要通知
        if all_signals:
            summary_message = self.generate_summary_message(all_signals)
            self.send_telegram_notification(summary_message)
        
        logger.info("\n" + "=" * 60)
        logger.info("監控週期完成")
        logger.info("=" * 60)
    
    def generate_summary_message(self, signals: List[Dict]) -> str:
        """生成摘要消息"""
        message = "📊 <b>股票監控摘要</b>\n"
        message += f"時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        
        for signal in signals:
            emoji = "🟢" if signal['signal_type'] == 'BUY' else "🔴" if signal['signal_type'] == 'SELL' else "⚪"
            message += f"{emoji} <b>{signal['code']}</b>\n"
            message += f" 信號: {signal['signal_type']}\n"
            message += f" 價格: {signal['price']:.2f}\n"
            message += f" 信心度: {signal['confidence']:.2%}\n\n"
        
        return message

def main():
    """主函數"""
    # 驗證環境變量
    if not all([SUPABASE_URL, SUPABASE_ANON_KEY]):
        logger.error("缺少必要的環境變量: SUPABASE_URL, SUPABASE_ANON_KEY")
        sys.exit(1)
    
    # 建立監控器
    monitor = TaiwanStockMonitor()
    
    # 執行監控
    try:
        monitor.run_monitoring_cycle()
        logger.info("監控成功完成")
    except Exception as e:
        logger.error(f"監控失敗: {str(e)}", exc_info=True)
        sys.exit(1)

if __name__ == '__main__':
    main()
