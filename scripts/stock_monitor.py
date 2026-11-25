#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
開明體系 - 股票監控系統
Phase 5.2.3: 整合 BDI + 外資籌碼
"""

import os
import sys
import requests
import yfinance as yf
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional
import time
import json
from pathlib import Path

# 導入新模組 ⭐ Phase 5.2.3 新增
try:
    from market_data_fetcher import MarketDataIntegration
    from confidence_calculator_v2 import ConfidenceCalculatorV2
    PHASE_5_2_3_ENABLED = True
except ImportError as e:
    print(f"⚠️ Phase 5.2.3 模組未找到: {e}")
    print("⚠️ 系統將以 Phase 4 模式運行")
    PHASE_5_2_3_ENABLED = False

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
    """獲取台灣時間字串"""
    return datetime.now(TW_TZ).strftime('%Y-%m-%d %H:%M:%S')


def read_stock_list():
    """
    讀取股票清單
    優先順序: 1. 環境變數 2. stocks.txt 3. 預設清單
    """
    stocks_override = os.getenv('STOCKS_OVERRIDE', '').strip()
    if stocks_override:
        print(f"📝 使用環境變數指定的股票: {stocks_override}")
        codes = [s.strip() for s in stocks_override.split(',') if s.strip()]
        return codes

    try:
        with open('stocks.txt', 'r', encoding='utf-8') as f:
            lines = [line.strip() for line in f if line.strip() and not line.startswith('#')]
            codes = []
            for line in lines:
                parts = line.split(',')
                if len(parts) >= 1:
                    code = parts[0].strip()
                    if code:
                        codes.append(code)
                        if len(parts) >= 2:
                            name = parts[1].strip()
                            if name:
                                STOCK_NAMES[code] = name
            if codes:
                print(f"📝 從 stocks.txt 讀取 {len(codes)} 支股票")
                return codes
    except FileNotFoundError:
        print("⚠️ stocks.txt 未找到，使用預設清單")

    default_stocks = ['2303', '2637', '4938', '2330', '2317', '2412']
    print(f"📝 使用預設股票清單: {', '.join(default_stocks)}")
    return default_stocks


def get_stock_name(stock_code: str) -> str:
    """獲取股票名稱"""
    if stock_code in STOCK_NAMES and STOCK_NAMES[stock_code] != stock_code:
        return STOCK_NAMES[stock_code]

    try:
        ticker = yf.Ticker(f"{stock_code}.TW")
        info = ticker.info
        name = info.get('longName', '') or info.get('shortName', '') or stock_code
        if name and name != stock_code:
            name = name.replace(' Co Ltd', '').replace(' Corp', '').replace(' Inc', '').strip()
            STOCK_NAMES[stock_code] = name
            return name
    except Exception as e:
        print(f"⚠️ 無法抓取 {stock_code} 的名稱: {e}")

    return stock_code


def fetch_stock_data(stock_code: str) -> Optional[Dict]:
    """獲取股票技術數據"""
    try:
        ticker = yf.Ticker(f"{stock_code}.TW")
        # 6 個月資料：確保 MA50、MACD、Wilder RSI 都有足夠暖機期
        hist = ticker.history(period="6mo")
        hist = hist.dropna()

        if hist.empty or len(hist) < 60:
            print(f"⚠️ {stock_code}: 數據不足")
            return None

        latest = hist.iloc[-1]
        price = float(latest['Close'])
        volume = int(latest['Volume'])

        ma_20 = float(hist['Close'].rolling(window=20).mean().iloc[-1])
        ma_50 = float(hist['Close'].rolling(window=50).mean().iloc[-1])

        # RSI(14)：Wilder 平滑（與看盤軟體一致）
        delta = hist['Close'].diff()
        gain = delta.clip(lower=0).ewm(alpha=1/14, adjust=False, min_periods=14).mean()
        loss = (-delta.clip(upper=0)).ewm(alpha=1/14, adjust=False, min_periods=14).mean()
        last_loss = float(loss.iloc[-1])
        if last_loss == 0:
            rsi = 100.0
        else:
            rsi = float(100 - (100 / (1 + float(gain.iloc[-1]) / last_loss)))

        ema_12 = hist['Close'].ewm(span=12, adjust=False).mean()
        ema_26 = hist['Close'].ewm(span=26, adjust=False).mean()
        macd = ema_12 - ema_26
        signal = macd.ewm(span=9, adjust=False).mean()
        diff = macd - signal

        # MACD 狀態：近 3 日內交叉算金叉/死叉，其餘依 DIF 與訊號線相對位置判斷多方/空方
        macd_signal = 'bullish' if diff.iloc[-1] > 0 else 'bearish'
        for i in range(1, 4):
            if diff.iloc[-i] > 0 and diff.iloc[-i - 1] <= 0:
                macd_signal = 'golden_cross'
                break
            if diff.iloc[-i] < 0 and diff.iloc[-i - 1] >= 0:
                macd_signal = 'dead_cross'
                break

        # 量比：與「前 20 日」均量比較；盤中依已交易時間比例換算，避免盤中量被低估
        avg_volume_20 = float(hist['Volume'].iloc[-21:-1].mean())
        now_tw = datetime.now(TW_TZ)
        expected_fraction = 1.0
        if hist.index[-1].date() == now_tw.date():
            open_t = now_tw.replace(hour=9, minute=0, second=0, microsecond=0)
            minutes = (now_tw - open_t).total_seconds() / 60
            if 0 < minutes < 270:
                expected_fraction = max(minutes / 270, 0.1)
        expected_volume = avg_volume_20 * expected_fraction
        volume_ratio = volume / expected_volume if expected_volume > 0 else 1.0

        return {
            'price': price,
            'ma_20': ma_20,
            'ma_50': ma_50,
            'rsi': rsi,
            'macd_signal': macd_signal,
            'volume_ratio': volume_ratio
        }

    except Exception as e:
        print(f"❌ {stock_code} 數據抓取失敗: {e}")
        return None


def save_to_supabase(data: Dict) -> bool:
    """儲存到 Supabase"""
    if not SUPABASE_URL or not SUPABASE_ANON_KEY:
        print("⚠️ Supabase 未配置")
        return False

    try:
        url = f'{SUPABASE_URL}/rest/v1/trade_logs'
        headers = {
            'apikey': SUPABASE_SERVICE_ROLE_KEY or SUPABASE_ANON_KEY,
            'Authorization': f'Bearer {SUPABASE_SERVICE_ROLE_KEY or SUPABASE_ANON_KEY}',
            'Content-Type': 'application/json',
            'Prefer': 'return=minimal'
        }
        response = requests.post(url, headers=headers, json=data, timeout=10)
        if response.status_code in [200, 201]:
            return True
        else:
            print(f"⚠️ Supabase 寫入失敗: {response.status_code}")
            return False

    except Exception as e:
        print(f"❌ Supabase 錯誤: {e}")
        return False


def send_telegram_notification(message: str) -> bool:
    """發送 Telegram 通知"""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("⚠️ Telegram 未配置，跳過通知")
        return False

    try:
        url = f'https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage'
        payload = {
            'chat_id': TELEGRAM_CHAT_ID,
            'text': message,
            
        }
        response = requests.post(url, json=payload, timeout=10)
        if response.status_code == 200:
            print("✅ Telegram 通知已發送")
            return True
        else:
            print(f"⚠️ Telegram 發送失敗: {response.status_code}")
            return False

    except Exception as e:
        print(f"❌ Telegram 錯誤: {e}")
        return False


def calculate_confidence_phase4(stock_data: Dict) -> tuple:
    """Phase 4 信心度計算（備用）"""
    score = 0
    max_score = 100
    logic_parts = []

    price = stock_data.get('price', 0)
    ma_20 = stock_data.get('ma_20')
    ma_50 = stock_data.get('ma_50')
    rsi = stock_data.get('rsi')
    macd_signal = stock_data.get('macd_signal', 'neutral')
    volume_ratio = stock_data.get('volume_ratio', 1.0)

    if ma_20 and price > ma_20:
        score += 20
        logic_parts.append(f"價格>{ma_20:.2f}(MA20)✓")

    if ma_50 and ma_20 and ma_20 > ma_50:
        score += 20
        logic_parts.append("MA20>MA50✓")

    if rsi and 40 <= rsi <= 65:
        score += 20
        logic_parts.append(f"RSI={rsi:.1f}(黃金區)✓")

    if macd_signal == 'golden_cross':
        score += 25
        logic_parts.append("MACD金叉✓")

    if volume_ratio > 1.2:
        score += 15
        logic_parts.append(f"量能放大{volume_ratio:.1f}倍✓")

    confidence = score / max_score
    return confidence, logic_parts


def format_message_phase4(stock_code: str, stock_name: str, price: float,
                          confidence: float, logic_parts: List[str]) -> str:
    """Phase 4 訊息格式（備用）"""
    if confidence >= 0.70:
        emoji, level = '🔴', '強烈買入'
        signal_type = 'BUY'
    elif confidence >= 0.50:
        emoji, level = '🟡', '建議買入'
        signal_type = 'BUY'
    else:
        emoji, level = '⚪', '觀望'
        signal_type = 'HOLD'

    message = f"{emoji} <b>{stock_code} {stock_name}</b> [{level}]\n"
    message += f" 信號: {signal_type}　價格: {price:.2f}　信心度: {confidence:.1%}\n\n"
    message += "📊 <b>技術面</b>\n"
    message += " • " + ", ".join(logic_parts) + "\n"

    if signal_type == 'BUY':
        take_profit = price * 1.15
        stop_loss = price * 0.95
        message += f"\n🎯 目標價: {take_profit:.2f} (+15%)\n"
        message += f"🛑 止損價: {stop_loss:.2f} (-5%)\n"

    return message


def main():
    """主函數"""
    global PHASE_5_2_3_ENABLED

    print("=" * 60)
    print("🚀 開明體系 - 股票監控系統")
    if PHASE_5_2_3_ENABLED:
        print("📊 Phase 5.2.3: BDI + 外資籌碼整合版")
    else:
        print("📊 Phase 4 模式")
    print("=" * 60)
    print(f"執行時間: {get_taiwan_time()} (台灣時間)")
    print("=" * 60)

    # 讀取股票清單
    stock_codes = read_stock_list()
    print(f"\n監控股票: {', '.join(stock_codes)}")
    print("=" * 60)

    # 初始化 Telegram 訊息
    telegram_message = "📊 股票監控摘要\n"
    telegram_message += f"時間: {get_taiwan_time()} (台灣時間)\n"

    if PHASE_5_2_3_ENABLED:
        telegram_message += "版本: Phase 5.2.3 🆕\n\n"
    else:
        telegram_message += "版本: Phase 4\n\n"

    # Phase 5.2.3: 獲取市場數據
    market_data = None
    bdi_data = None
    foreign_data_all = {}
    calculator = None

    if PHASE_5_2_3_ENABLED:
        print("\n🌐 Phase 5.2.3: 獲取市場數據...")
        try:
            market_data = MarketDataIntegration()
            all_market_data = market_data.fetch_all_data(stock_codes)

            bdi_data = all_market_data.get('bdi')
            foreign_data_all = all_market_data.get('foreign', {})

            calculator = ConfidenceCalculatorV2()

            print("✅ Phase 5.2.3 市場數據獲取完成")
        except Exception as e:
            print(f"⚠️ Phase 5.2.3 數據獲取失敗: {e}")
            print("⚠️ 降級為 Phase 4 模式")
            PHASE_5_2_3_ENABLED = False

    print("\n" + "=" * 60)
    print("📈 開始分析股票...")
    print("=" * 60)

    # 處理每支股票
    results = []

    for stock_code in stock_codes:
        print(f"\n🔍 分析 {stock_code}...")

        stock_name = get_stock_name(stock_code)
        stock_data = fetch_stock_data(stock_code)

        if not stock_data:
            print(f"❌ {stock_code} 跳過（數據不足）")
            continue

        price = stock_data['price']

        # 計算信心度
        if PHASE_5_2_3_ENABLED and calculator:
            foreign_data = foreign_data_all.get(stock_code)
            bdi_for_stock = market_data.get_bdi_for_stock(stock_code) if market_data else None

            confidence, logic_parts = calculator.calculate_confidence(
                stock_code, stock_data, bdi_for_stock, foreign_data
            )
            message = calculator.format_telegram_message(
                stock_code, stock_name, price, confidence, logic_parts,
                bdi_for_stock, foreign_data
            )
            signal_type, _, _ = calculator.get_signal_level(confidence)

        else:
            confidence, logic_parts = calculate_confidence_phase4(stock_data)
            message = format_message_phase4(stock_code, stock_name, price, confidence, logic_parts)
            signal_type = 'BUY' if confidence >= 0.50 else 'HOLD'

        telegram_message += message + "\n"

        # 儲存到 Supabase
        db_data = {
            'stock_code': stock_code,
            'stock_name': stock_name,
            'price': price,
            'signal_type': signal_type,
            'confidence': confidence,
            'logic': ', '.join(logic_parts),
            'timestamp': datetime.now(TW_TZ).isoformat()
        }

        if PHASE_5_2_3_ENABLED:
            bdi_for_stock = market_data.get_bdi_for_stock(stock_code) if market_data else None
            foreign_data = foreign_data_all.get(stock_code)
            db_data['bdi_index'] = bdi_for_stock['value'] if bdi_for_stock else None
            db_data['bdi_change_pct'] = bdi_for_stock['change_percent'] if bdi_for_stock else None
            db_data['foreign_net_buy'] = foreign_data['foreign_net'] if foreign_data else None
            db_data['foreign_holding_pct'] = foreign_data['foreign_holding_pct'] if foreign_data else None
            db_data['chip_strength'] = foreign_data['strength'] if foreign_data else None

        save_to_supabase(db_data)

        results.append({
            'code': stock_code,
            'name': stock_name,
            'signal': signal_type,
            'confidence': confidence
        })

        print(f"✅ {stock_code} {stock_name}: {signal_type} ({confidence:.1%})")

    # 發送 Telegram 通知
    print("\n" + "=" * 60)
    print("📱 發送 Telegram 通知...")
    send_telegram_notification(telegram_message)

    # 摘要
    print("\n" + "=" * 60)
    print("📊 執行摘要")
    print("=" * 60)
    print(f"分析股票: {len(results)}/{len(stock_codes)}")

    buy_signals = [r for r in results if r['signal'] == 'BUY']
    if buy_signals:
        print(f"\n🟢 BUY 信號: {len(buy_signals)} 支")
        for r in buy_signals:
            print(f"  • {r['code']} {r['name']}: {r['confidence']:.1%}")

    print("\n✅ 執行完成")
    print("=" * 60)

    return results


if __name__ == '__main__':
    results = []
    try:
        results = main()
    except KeyboardInterrupt:
        print("\n\n⚠️ 使用者中斷執行")
        sys.exit(0)
    except Exception as e:
        print(f"\n\n❌ 執行錯誤: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    # 完全沒有取得任何股價數據 → 讓 workflow 失敗，觸發 Telegram 失敗告警
    # （舊版把計數存在 /tmp，每次 Actions 都是新機器，計數永遠歸零，告警不會觸發）
    if not results:
        print("❌ 本次沒有任何股票取得數據，標記為失敗")
        sys.exit(1)
