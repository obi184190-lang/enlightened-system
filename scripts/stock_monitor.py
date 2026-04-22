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
import pandas as pd

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

# 讀取股票清單（支援A+B兩種方式）
stocks_override = os.getenv('STOCKS_OVERRIDE', '').strip()

if stocks_override:
    # 方式B：執行時臨時輸入
    stock_list = [s.strip() for s in stocks_override.split(',')]
    STOCK_CODES = [s for s in stock_list if s]
    STOCK_NAMES = {code: code for code in STOCK_CODES}
    logger.info(f"使用臨時股票清單：{STOCK_CODES}")
else:
    # 方式A：讀取 stocks.txt
    try:
        with open('stocks.txt', 'r', encoding='utf-8') as f:
            lines = [l.strip() for l in f.readlines() if l.strip()]
        STOCK_CODES = [l.split(',')[0].strip() for l in lines]
        STOCK_NAMES = {}
        for l in lines:
            parts = l.split(',')
            code = parts[0].strip()
            name = parts[1].strip() if len(parts) > 1 else code
            STOCK_NAMES[code] = name
        logger.info(f"從stocks.txt讀取：{STOCK_CODES}")
    except:
        # 備用清單
        STOCK_CODES = ['2303', '2637', '4938']
        STOCK_NAMES = {'2303': '聯電', '2637': '慧洋-KY', '4938': '和碩'}
        logger.warning("stocks.txt讀取失敗，使用備用清單")
    

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
            import yfinance as yf
            ticker = yf.Ticker(f"{stock_code}.TW")
            hist = ticker.history(period="5d")
            hist = hist.dropna()  # 移除 NaN 行
            if hist.empty:
                logger.error(f"{stock_code} 無有效數據（休市或數據缺失）")
                return None
            
            latest = hist.iloc[-1]
            stock_info = {
                'code': stock_code,
                'price': float(latest['Close']),
                'volume': int(latest['Volume']),
                'change': float(latest['Close'] - latest['Open']),
                'change_percent': float((latest['Close'] - latest['Open']) / latest['Open'] * 100)
            }
            return stock_info
        except Exception as e:
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
        
       # ==========================================
        # Phase 4 升級版：多指標加權信心度系統
        # ==========================================
        score = 0
        max_score = 0
        logic_parts = []

        # 指標1：MA20突破 (權重20%)
        max_score += 20
        if ma_20 and price > ma_20:
            score += 20
            logic_parts.append("價格>MA20✓")

        # 指標2：MA50趨勢 (權重20%)
        max_score += 20
        if ma_50 and ma_20 and ma_20 > ma_50:
            score += 20
            logic_parts.append("MA20>MA50✓")

        # 指標3：RSI適中區間 (權重20%)
        max_score += 20
        if rsi:
            if 40 <= rsi <= 65:
                score += 20
                logic_parts.append(f"RSI黃金區={rsi:.1f}✓")
            elif 30 <= rsi < 40 or 65 < rsi <= 70:
                score += 10
                logic_parts.append(f"RSI尚可={rsi:.1f}")

        # 指標4：MACD計算 (權重25%)
        max_score += 25
        try:
            closes = data['Close'].values
            if len(closes) >= 26:
                ema12 = pd.Series(closes).ewm(span=12).mean().values
                ema26 = pd.Series(closes).ewm(span=26).mean().values
                macd_line = ema12 - ema26
                signal_line = pd.Series(macd_line).ewm(span=9).mean().values
                if macd_line[-1] > signal_line[-1] and macd_line[-2] <= signal_line[-2]:
                    score += 25
                    logic_parts.append("MACD金叉✓")
                elif macd_line[-1] > signal_line[-1]:
                    score += 15
                    logic_parts.append("MACD多頭")
        except:
            max_score -= 25

        # 指標5：成交量放大 (權重15%)
        max_score += 15
        try:
            volumes = data['Volume'].values
            if len(volumes) >= 20:
                avg_vol = volumes[-20:].mean()
                if volumes[-1] > avg_vol * 1.5:
                    score += 15
                    logic_parts.append("成交量放大✓")
                elif volumes[-1] > avg_vol * 1.2:
                    score += 8
                    logic_parts.append("成交量略增")
        except:
            max_score -= 15

        # 計算最終信心度
        confidence = round(score / max_score, 4) if max_score > 0 else 0
        logic_str = "，".join(logic_parts) if logic_parts else "條件不足"

        # 判斷信號類型
        if ma_20 and ma_50 and price > ma_20 > ma_50 and rsi and rsi < 70:
            if confidence >= 0.70:
                signal['signal_type'] = 'BUY'
                signal['confidence'] = confidence
                signal['decision_logic'] = f"🔴強烈買入 {logic_str}"
            elif confidence >= 0.50:
                signal['signal_type'] = 'BUY'
                signal['confidence'] = confidence
                signal['decision_logic'] = f"🟡建議買入 {logic_str}"
            else:
                signal['signal_type'] = 'BUY'
                signal['confidence'] = confidence
                signal['decision_logic'] = f"⚪觀望 {logic_str}"
        elif ma_20 and price < ma_20:
            signal['signal_type'] = 'SELL'
            signal['confidence'] = 0.75
            signal['decision_logic'] = f"價格跌破MA20，需要止損"
        elif rsi and rsi > 80:
            signal['signal_type'] = 'SELL'
            signal['confidence'] = 0.70
            signal['decision_logic'] = f"RSI過高={rsi:.2f}，需要獲利了結"
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
            if signal['signal_type'] == 'BUY':
    if signal['confidence'] >= 0.70:
        emoji = "🔴"
        level = "強烈買入"
    elif signal['confidence'] >= 0.50:
        emoji = "🟡"
        level = "建議買入"
    else:
        emoji = "⚪"
        level = "觀望"
    elif signal['signal_type'] == 'SELL':
        emoji = "🔵"
        level = "賣出"
    else:
        emoji = "⚫"
        level = "持有"
            message += f"{emoji} <b>{signal['code']} {STOCK_NAMES.get(signal['code'], '')} [{level}]</b>\n"
            message += f" 信號: {signal['signal_type']}\n"
            message += f" 價格: {signal['price']:.2f}\n"
            message += f" 信心度: {signal['confidence']:.2%}\n\n"
            if signal['signal_type'] == 'BUY':
                stop_loss = round(signal['price'] * 0.95, 2)
                take_profit = round(signal['price'] * 1.15, 2)
                message += f" 🎯 目標價: {take_profit} (+15%)\n"
                message += f" 🛑 止損價: {stop_loss} (-5%)\n\n"
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
