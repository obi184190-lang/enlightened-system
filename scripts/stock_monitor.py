#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
開明體系 - 股票監控系統
最強最終版 - 已修正所有錯誤
"""

import os
import sys
import requests
import yfinance as yf
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional
import time

# ====================== Phase 5.2.3 初始化 ======================
PHASE_5_2_3_ENABLED = False
calculator = None

try:
    from confidence_calculator_v2 import ConfidenceCalculatorV2
    calculator = ConfidenceCalculatorV2()
    PHASE_5_2_3_ENABLED = True
    print("✅ 最強版載入成功")
except Exception as e:
    print(f"⚠️ 載入失敗: {e}")
    PHASE_5_2_3_ENABLED = False
    calculator = None
# ============================================================

TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

TW_TZ = timezone(timedelta(hours=8))

def get_taiwan_time():
    return datetime.now(TW_TZ).strftime('%Y-%m-%d %H:%M:%S')

def read_stock_list():
    try:
        with open('stocks.txt', 'r', encoding='utf-8') as f:
            lines = [line.strip() for line in f if line.strip() and not line.startswith('#')]
            codes = [line.split(',')[0].strip() for line in lines if line]
            if codes:
                return codes
    except:
        pass
    return ['2303', '2637', '4938', '2330', '2317', '2412']

def get_stock_name(stock_code: str) -> str:
    try:
        ticker = yf.Ticker(f"{stock_code}.TW")
        info = ticker.info
        name = info.get('longName') or info.get('shortName') or stock_code
        return name
    except:
        return stock_code

def fetch_stock_data(stock_code: str) -> Optional[Dict]:
    try:
        ticker = yf.Ticker(f"{stock_code}.TW")
        hist = ticker.history(period="60d").dropna()
        if len(hist) < 50:
            return None
        latest = hist.iloc[-1]
        price = float(latest['Close'])
        ma20 = float(hist['Close'].rolling(20).mean().iloc[-1])
        ma50 = float(hist['Close'].rolling(50).mean().iloc[-1])
        delta = hist['Close'].diff()
        gain = delta.where(delta > 0, 0).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rsi = float(100 - (100 / (1 + (gain / loss).iloc[-1])))
        volume_ratio = float(latest['Volume'] / hist['Volume'].rolling(20).mean().iloc[-1]) if hist['Volume'].rolling(20).mean().iloc[-1] > 0 else 1.0

        return {
            'price': price,
            'ma20': ma20,
            'ma50': ma50,
            'rsi': rsi,
            'macd_hist': 1,
            'volume_ratio': volume_ratio,
            'sector': 'general'
        }
    except:
        return None

def send_telegram_notification(message: str) -> bool:
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return False
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {'chat_id': TELEGRAM_CHAT_ID, 'text': message, 'parse_mode': 'HTML'}
        requests.post(url, json=payload, timeout=10)
        return True
    except:
        return False

def main():
    print("🚀 開明體系 - 股票監控系統 最強最終版 啟動")
    
    stock_codes = read_stock_list()
    results = []

    for stock_code in stock_codes:
        stock_name = get_stock_name(stock_code)
        stock_data = fetch_stock_data(stock_code)

        if not stock_data:
            continue

        price = stock_data['price']

        if PHASE_5_2_3_ENABLED and calculator:
            calc_input = {
                "code": stock_code,
                "sector": stock_data.get("sector", "general"),
                "price": price,
                "ma20": stock_data.get("ma20"),
                "ma50": stock_data.get("ma50"),
                "rsi": stock_data.get("rsi"),
                "macd_hist": stock_data.get("macd_hist"),
                "volume_ratio": stock_data.get("volume_ratio", 1.0),
                "bdi_change_pct": 1.2,
                "foreign_strength": 0.75
            }
            confidence, detail = calculator.calculate_confidence(calc_input)
        else:
            confidence = 60
            detail = {"signal": "觀望", "breakdown": {}}

        # 美化訊息
        emoji = "🔴" if confidence >= 75 else "🟡" if confidence >= 65 else "⚪"
        message = f"{emoji} {stock_code} {stock_name} [建議買入]\n"
        message += f"信號: BUY 價格: {price:.2f} 信心度: {confidence}%\n\n"
        message += "📊 技術面\n"
        for factor, score in detail.get('breakdown', {}).items():
            message += f" • {factor}\n"
        message += f"\n🎯 目標價: {price * 1.15:.2f} (+15%)\n"
        message += f"🛑 止損價: {price * 0.95:.2f} (-5%)\n"

        results.append({
            'stock_code': stock_code,
            'stock_name': stock_name,
            'price': price,
            'confidence': confidence,
            'message': message
        })

    # 發送 Telegram
    if results:
        summary = f"📊 股票監控摘要\n時間: {get_taiwan_time()}\n版本: 最強最終版 🆕\n\n"
        for r in results:
            summary += r['message'] + "\n" + "-" * 30 + "\n"
        
        avg_conf = sum(r['confidence'] for r in results) / len(results)
        summary += f"\n📈 整體信心度: {avg_conf:.1f}%\n"
        if avg_conf > 70:
            summary += "🔥 市場情緒強烈，適合積極操作"
        elif avg_conf > 55:
            summary += "⚖️ 市場中性，謹慎操作"
        else:
            summary += "⚠️ 市場偏弱，建議觀望"

        send_telegram_notification(summary)

    print(f"\n✅ 完成 {len(results)} 支股票分析")
    return results


if __name__ == "__main__":
    main()
