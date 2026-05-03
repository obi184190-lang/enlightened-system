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

# Phase 5.2.3 使用升級版計算
if PHASE_5_2_3_ENABLED and calculator:
    # 準備計算器需要的輸入資料
    calc_input = {
        "code": stock_code,
        "sector": stock_data.get("sector", "general"),
        "price": stock_data.get("price"),
        "ma20": stock_data.get("ma20"),
        "ma50": stock_data.get("ma50"),
        "rsi": stock_data.get("rsi"),
        "macd_hist": stock_data.get("macd_hist"),
        "volume_ratio": stock_data.get("volume_ratio", 1.0),
        "bdi_change_pct": bdi_for_stock.get("change_pct", 0) if isinstance(bdi_for_stock, dict) else 0,
        "foreign_strength": foreign_data.get("strength", 0.5) if isinstance(foreign_data, dict) else 0.5,
    }

    confidence, detail = calculator.calculate_confidence(calc_input)
    
    logic_breakdown = detail.get('breakdown', {})
    signal = detail.get('signal', '觀望')
    
    print(f"✅ Phase 5.2.3 信心度計算完成 → {confidence}% ({signal})")
else:
    # 舊版備用（Phase 4）
    confidence = 55
    logic_breakdown = {}
    signal = "觀望"
    print("⚠️ 使用 Phase 4 備用信心度計算")

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
    # 方式 B: 環境變數（手動執行時指定）
    stocks_override = os.getenv('STOCKS_OVERRIDE', '').strip()
    if stocks_override:
        print(f"📝 使用環境變數指定的股票: {stocks_override}")
        codes = [s.strip() for s in stocks_override.split(',') if s.strip()]
        return codes
    
    # 方式 A: 讀取 stocks.txt
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
                        # 快取名稱（如果有提供）
                        if len(parts) >= 2:
                            name = parts[1].strip()
                            if name:
                                STOCK_NAMES[code] = name
            
            if codes:
                print(f"📝 從 stocks.txt 讀取 {len(codes)} 支股票")
                return codes
    except FileNotFoundError:
        print("⚠️ stocks.txt 未找到，使用預設清單")
    
    # 預設清單
    default_stocks = ['2303', '2637', '4938', '2330', '2317', '2412']
    print(f"📝 使用預設股票清單: {', '.join(default_stocks)}")
    return default_stocks


def get_stock_name(stock_code: str) -> str:
    """
    獲取股票名稱
    優先使用快取，否則從 yfinance 抓取
    """
    # 檢查快取
    if stock_code in STOCK_NAMES and STOCK_NAMES[stock_code] != stock_code:
        return STOCK_NAMES[stock_code]
    
    # 從 yfinance 抓取
    try:
        ticker = yf.Ticker(f"{stock_code}.TW")
        info = ticker.info
        
        # 嘗試多種名稱欄位
        name = info.get('longName', '') or info.get('shortName', '') or stock_code
        
        # 清理名稱
        if name and name != stock_code:
            name = name.replace(' Co Ltd', '').replace(' Corp', '').replace(' Inc', '').strip()
            STOCK_NAMES[stock_code] = name
            return name
    except Exception as e:
        print(f"⚠️ 無法抓取 {stock_code} 的名稱: {e}")
    
    return stock_code


def fetch_stock_data(stock_code: str) -> Optional[Dict]:
    """
    獲取股票技術數據
    
    Returns:
        {
            'price': float,
            'ma_20': float,
            'ma_50': float,
            'rsi': float,
            'macd_signal': str,  # 'golden_cross', 'dead_cross', 'neutral'
            'volume_ratio': float
        }
    """
    try:
        ticker = yf.Ticker(f"{stock_code}.TW")
        hist = ticker.history(period="60d")
        
        # 移除 NaN 行
        hist = hist.dropna()
        
        if hist.empty or len(hist) < 50:
            print(f"⚠️ {stock_code}: 數據不足")
            return None
        
        # 基本數據
        latest = hist.iloc[-1]
        price = float(latest['Close'])
        volume = int(latest['Volume'])
        
        # 計算 MA20 和 MA50
        ma_20 = float(hist['Close'].rolling(window=20).mean().iloc[-1])
        ma_50 = float(hist['Close'].rolling(window=50).mean().iloc[-1])
        
        # 計算 RSI
        delta = hist['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        rsi = float(100 - (100 / (1 + rs.iloc[-1])))
        
        # 計算 MACD
        ema_12 = hist['Close'].ewm(span=12, adjust=False).mean()
        ema_26 = hist['Close'].ewm(span=26, adjust=False).mean()
        macd = ema_12 - ema_26
        signal = macd.ewm(span=9, adjust=False).mean()
        
        # 判斷 MACD 信號
        if macd.iloc[-1] > signal.iloc[-1] and macd.iloc[-2] <= signal.iloc[-2]:
            macd_signal = 'golden_cross'
        elif macd.iloc[-1] < signal.iloc[-1] and macd.iloc[-2] >= signal.iloc[-2]:
            macd_signal = 'dead_cross'
        else:
            macd_signal = 'neutral'
        
        # 計算成交量比率
        avg_volume_20 = hist['Volume'].rolling(window=20).mean().iloc[-1]
        volume_ratio = volume / avg_volume_20 if avg_volume_20 > 0 else 1.0
        
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
            'apikey': SUPABASE_ANON_KEY,
            'Authorization': f'Bearer {SUPABASE_ANON_KEY}',
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
            'text': message
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
    """
    Phase 4 信心度計算（備用）
    當 Phase 5.2.3 模組不可用時使用
    """
    score = 0
    max_score = 100
    logic_parts = []
    
    price = stock_data.get('price', 0)
    ma_20 = stock_data.get('ma_20')
    ma_50 = stock_data.get('ma_50')
    rsi = stock_data.get('rsi')
    macd_signal = stock_data.get('macd_signal', 'neutral')
    volume_ratio = stock_data.get('volume_ratio', 1.0)
    
    # MA20 (20%)
    if ma_20 and price > ma_20:
        score += 20
        logic_parts.append(f"價格>{ma_20:.2f}(MA20)✓")
    
    # MA50 (20%)
    if ma_50 and ma_20 and ma_20 > ma_50:
        score += 20
        logic_parts.append("MA20>MA50✓")
    
    # RSI (20%)
    if rsi and 40 <= rsi <= 65:
        score += 20
        logic_parts.append(f"RSI={rsi:.1f}(黃金區)✓")
    
    # MACD (25%)
    if macd_signal == 'golden_cross':
        score += 25
        logic_parts.append("MACD金叉✓")
    
    # 成交量 (15%)
    if volume_ratio > 1.2:
        score += 15
        logic_parts.append(f"量能放大{volume_ratio:.1f}倍✓")
    
    confidence = score / max_score
    return confidence, logic_parts


def format_message_phase4(stock_code: str, stock_name: str, price: float, 
                          confidence: float, logic_parts: List[str]) -> str:
    """Phase 4 訊息格式（備用）"""
    # 判斷等級
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
    global PHASE_5_2_3_ENABLED  # 修復：宣告為全局變數
    # 格式化訊息
if PHASE_5_2_3_ENABLED and calculator and 'detail' in locals():
    message = calculator.format_telegram_message(
        stock_code=stock_code,
        stock_name=stock_name,
        price=price,
        confidence=confidence,
        detail=detail,
        target_price=stock_data.get('target_price'),
        stop_loss=stock_data.get('stop_loss')
    )
else:
    # 舊版格式化方式（備用）
    message = f"🟡 {stock_code} {stock_name} [建議買入]\n"
    message += f"信心度: {confidence}%\n"

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
    
    # 初始化 Telegram 訊息（簡化格式，避免 HTML 錯誤）
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
            
            # 初始化升級版計算器
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
        
        # 獲取股票名稱
        stock_name = get_stock_name(stock_code)
        
        # 獲取技術數據
        stock_data = fetch_stock_data(stock_code)
        
        if not stock_data:
            print(f"❌ {stock_code} 跳過（數據不足）")
            continue
        
        price = stock_data['price']
        
        # Phase 5.2.3 使用升級版計算
if PHASE_5_2_3_ENABLED and calculator:
    # 準備計算器需要的輸入資料
    calc_input = {
        "code": stock_code,
        "sector": stock_data.get("sector", "general"),
        "price": stock_data.get("price"),
        "ma20": stock_data.get("ma20"),
        "ma50": stock_data.get("ma50"),
        "rsi": stock_data.get("rsi"),
        "macd_hist": stock_data.get("macd_hist"),
        "volume_ratio": stock_data.get("volume_ratio", 1.0),
        "bdi_change_pct": bdi_for_stock.get("change_pct", 0) if isinstance(bdi_for_stock, dict) else 0,
        "foreign_strength": foreign_data.get("strength", 0.5) if isinstance(foreign_data, dict) else 0.5,
    }

    confidence, detail = calculator.calculate_confidence(calc_input)
    
    logic_breakdown = detail.get('breakdown', {})
    signal = detail.get('signal', '觀望')
    
    print(f"✅ Phase 5.2.3 信心度計算完成 → {confidence}% ({signal})")
else:
    # 舊版備用（Phase 4）
    confidence = 55
    logic_breakdown = {}
    signal = "觀望"
    print("⚠️ 使用 Phase 4 備用信心度計算")

            message = calculator.format_telegram_message(
                stock_code,
                stock_name,
                price,
                confidence,
                logic_parts,
                bdi_for_stock,
                foreign_data
            )
            
            # 獲取信號類型
            signal_type, _, _ = calculator.get_signal_level(confidence)
            
        else:
            # Phase 4: 使用備用計算
            confidence, logic_parts = calculate_confidence_phase4(stock_data)
            message = format_message_phase4(stock_code, stock_name, price, confidence, logic_parts)
            
            if confidence >= 0.50:
                signal_type = 'BUY'
            else:
                signal_type = 'HOLD'
        
        # 加入 Telegram 訊息
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
        
        # Phase 5.2.3: 新增欄位
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


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️ 使用者中斷執行")
        sys.exit(0)
    except Exception as e:
        print(f"\n\n❌ 執行錯誤: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
