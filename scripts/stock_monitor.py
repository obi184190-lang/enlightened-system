#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
開明體系 - 股票監控系統
最強 Phase 5.2.3: BDI + 外資 + 美化訊息 + 風險控管
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
    print("✅ Phase 5.2.3 信心度計算器載入成功 (YAML 動態權重)")
except Exception as e:
    print(f"⚠️ Phase 5.2.3 載入失敗: {e}")
    PHASE_5_2_3_ENABLED = False
    calculator = None
# ============================================================

# 環境變數
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_ANON_KEY = os.getenv('SUPABASE_ANON_KEY')
SUPABASE_SERVICE_ROLE_KEY = os.getenv('SUPABASE_SERVICE_ROLE_KEY')
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

# 台灣時區
TW_TZ = timezone(timedelta(hours=8))

# 股票名稱快取
STOCK_NAMES = {}


def get_taiwan_time():
    return datetime.now(TW_TZ).strftime('%Y-%m-%d %H:%M:%S')


def read_stock_list():
    stocks_override = os.getenv('STOCKS_OVERRIDE', '').strip()
    if stocks_override:
        return [s.strip() for s in stocks_override.split(',') if s.strip()]

    try:
        with open('stocks.txt', 'r', encoding='utf-8') as f:
            lines = [line.strip() for line in f if line.strip() and not line.startswith('#')]
            codes = [line.split(',')[0].strip() for line in lines if line]
            if codes:
                return codes
    except FileNotFoundError:
        pass

    return ['2303', '2637', '4938', '2330', '2317', '2412']


def get_stock_name(stock_code: str) -> str:
    if stock_code in STOCK_NAMES:
        return STOCK_NAMES[stock_code]
    try:
        ticker = yf.Ticker(f"{stock_code}.TW")
        info = ticker.info
        name = info.get('longName') or info.get('shortName') or stock_code
        STOCK_NAMES[stock_code] = name
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
    except Exception as e:
        print(f"{stock_code} 數據抓取失敗: {e}")
        return None


def send_telegram_notification(message: str) -> bool:
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("⚠️ Telegram 未設定")
        return False
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {'chat_id': TELEGRAM_CHAT_ID, 'text': message, 'parse_mode': 'HTML'}
        response = requests.post(url, json=payload, timeout=10)
        if response.status_code == 200:
            print("✅ Telegram 訊息已發送")
            return True
        else:
            print(f"⚠️ Telegram 發送失敗: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Telegram 錯誤: {e}")
        return False


def main():
    print("🚀 開明體系 - 股票監控系統 Phase 5.2.3 最強版 啟動")
    
    stock_codes = read_stock_list()
    results = []

    for stock_code in stock_codes:
        print(f"\n🔍 分析 {stock_code}...")

        stock_name = get_stock_name(stock_code)
        stock_data = fetch_stock_data(stock_code)

        if not stock_data:
            print(f"❌ {stock_code} 跳過")
            continue

        price = stock_data['price']

        # Phase 5.2.3 信心度計算
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
                "bdi_change_pct": 0.1, # 之後可接真實 BDI
                "foreign_strength": 0.65 # 之後可接真實外資
            }
            confidence, detail = calculator.calculate_confidence(calc_input)
        else:
            confidence = 55
            detail = {"signal": "觀望", "breakdown": {}}

        # 美化訊息
        if PHASE_5_2_3_ENABLED and calculator:
            message = calculator.format_telegram_message(
                stock_code=stock_code,
                stock_name=stock_name,
                price=price,
                confidence=confidence,
                detail=detail,
                target_price=price * 1.15,
                stop_loss=price * 0.95
            )
        else:
            message = f"🟡 {stock_code} {stock_name} [建議買入]\n信心度: {confidence}%"

        results.append({
            'stock_code': stock_code,
            'stock_name': stock_name,
            'price': price,
            'confidence': confidence,
            'message': message
        })

    # 發送 Telegram 摘要
    if results:
        telegram_summary = f"📊 股票監控摘要\n時間: {get_taiwan_time()}\n版本: Phase 5.2.3 最強版 🆕\n\n"
        for r in results:
            telegram_summary += r['message'] + "\n" + "-" * 30 + "\n"
        
        # 整體風險提示
        avg_conf = sum(r['confidence'] for r in results) / len(results)
        telegram_summary += f"\n📈 整體信心度: {avg_conf:.1f}%\n"
        if avg_conf > 70:
            telegram_summary += "🔥 市場情緒偏強，適合積極操作"
        elif avg_conf > 55:
            telegram_summary += "⚖️ 市場中性，謹慎操作"
        else:
            telegram_summary += "⚠️ 市場偏弱，建議觀望"

        send_telegram_notification(telegram_summary)

    print(f"\n✅ 完成 {len(results)} 支股票分析")
    return results


if __name__ == "__main__":
    main()
