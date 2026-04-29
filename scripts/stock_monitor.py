#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
股票監控與交易決策系統 - Phase 5.1
Stock Monitor & Trading Bot for Taiwan Stock Market with Candlestick Charts
"""

import os
import sys
import json
import logging
import requests
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple
import time
import pandas as pd
import tempfile

# K線圖表套件（Phase 5.1 新增）
try:
    import mplfinance as mpf
    import matplotlib
    matplotlib.use('Agg')  # 無需 GUI 環境
    import matplotlib.pyplot as plt
    CHART_ENABLED = True
    logger_temp = logging.getLogger(__name__)
    logger_temp.info("K線圖表功能已啟用")
except ImportError:
    CHART_ENABLED = False
    logger_temp = logging.getLogger(__name__)
    logger_temp.warning("mplfinance 未安裝，K線圖表功能已禁用")

# 設置日誌
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 台灣時區設定
TW_TZ = timezone(timedelta(hours=8))

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
    STOCK_NAMES = {code: code for code in STOCK_CODES}  # 初始化，稍後會自動抓取
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
        self.temp_dir = tempfile.gettempdir()
    
    def get_stock_name(self, stock_code: str) -> str:
        """
        自動抓取股票名稱
        如果 STOCK_NAMES 中沒有，就從 yfinance 取得
        """
        if stock_code in STOCK_NAMES and STOCK_NAMES[stock_code] != stock_code:
            return STOCK_NAMES[stock_code]
        
        try:
            import yfinance as yf
            ticker = yf.Ticker(f"{stock_code}.TW")
            info = ticker.info
            
            # 嘗試取得中文名稱或英文名稱
            name = info.get('longName', '') or info.get('shortName', '') or stock_code
            
            # 如果是英文名稱，嘗試清理
            if name and name != stock_code:
                # 移除 "Co Ltd" 等後綴
                name = name.replace(' Co Ltd', '').replace(' Corp', '').strip()
                STOCK_NAMES[stock_code] = name
                logger.info(f"自動抓取股票名稱：{stock_code} -> {name}")
                return name
        except Exception as e:
            logger.warning(f"無法抓取 {stock_code} 的名稱: {str(e)}")
        
        # 如果都失敗，就返回代碼本身
        STOCK_NAMES[stock_code] = stock_code
        return stock_code
    
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
    
    def generate_candlestick_chart(self, stock_code: str, stock_name: str, 
                                   data: pd.DataFrame, signal: Dict) -> Optional[str]:
        """
        生成K線圖表（Phase 5.1 新功能）
        
        Args:
            stock_code: 股票代碼
            stock_name: 股票名稱
            data: 歷史數據（DataFrame）
            signal: 信號資訊
            
        Returns:
            圖片檔案路徑，失敗時返回 None
        """
        if not CHART_ENABLED:
            logger.warning("K線圖表功能未啟用（mplfinance 未安裝）")
            return None
        
        try:
            # 準備數據（最近30天）
            chart_data = data.tail(30).copy()
            
            if chart_data.empty or len(chart_data) < 2:
                logger.warning(f"{stock_code} 數據不足，無法生成圖表")
                return None
            
            # 計算 MA20 和 MA50
            chart_data['MA20'] = chart_data['Close'].rolling(window=20, min_periods=1).mean()
            chart_data['MA50'] = chart_data['Close'].rolling(window=50, min_periods=1).mean()
            
            # 設定圖表樣式
            mc = mpf.make_marketcolors(
                up='red',      # 上漲為紅色（台股習慣）
                down='green',  # 下跌為綠色
                edge='inherit',
                wick='inherit',
                volume='in',
                alpha=0.9
            )
            
            s = mpf.make_mpf_style(
                marketcolors=mc,
                gridstyle='-',
                y_on_right=False,
                rc={'font.family': 'sans-serif'}
            )
            
            # 準備附加線條（MA20, MA50）
            apds = [
                mpf.make_addplot(chart_data['MA20'], color='orange', width=1.5, label='MA20'),
                mpf.make_addplot(chart_data['MA50'], color='blue', width=1.5, label='MA50')
            ]
            
            # 標註買賣信號
            if signal['signal_type'] in ['BUY', 'SELL']:
                # 在最後一個點標記信號
                signal_marker = chart_data.copy()
                signal_marker['Signal'] = None
                signal_marker.loc[signal_marker.index[-1], 'Signal'] = signal_marker['Close'].iloc[-1]
                
                marker_color = 'red' if signal['signal_type'] == 'BUY' else 'green'
                marker_symbol = '^' if signal['signal_type'] == 'BUY' else 'v'
                
                apds.append(
                    mpf.make_addplot(
                        signal_marker['Signal'],
                        type='scatter',
                        markersize=200,
                        marker=marker_symbol,
                        color=marker_color,
                        label=f'{signal["signal_type"]} Signal'
                    )
                )
            
            # 生成圖表標題
            signal_emoji = "🔴" if signal['confidence'] >= 0.70 else "🟡" if signal['confidence'] >= 0.50 else "⚪"
            title = f"{stock_code} {stock_name}\n{signal['signal_type']} {signal_emoji} 信心度: {signal['confidence']:.1%}"
            
            # 生成圖片檔案路徑
            chart_file = os.path.join(self.temp_dir, f"stock_{stock_code}.png")
            
            # 繪製圖表
            mpf.plot(
                chart_data,
                type='candle',
                style=s,
                title=title,
                ylabel='Price (TWD)',
                volume=True,
                ylabel_lower='Volume',
                addplot=apds,
                figsize=(12, 8),
                tight_layout=True,
                savefig=chart_file
            )
            
            logger.info(f"K線圖表已生成：{chart_file}")
            return chart_file
            
        except Exception as e:
            logger.error(f"生成 {stock_code} K線圖表失敗: {str(e)}")
            return None
    
    def send_telegram_photo(self, photo_path: str, caption: str) -> bool:
        """
        發送圖片到 Telegram（Phase 5.1 新功能）
        
        Args:
            photo_path: 圖片檔案路徑
            caption: 圖片說明文字
            
        Returns:
            成功返回 True，失敗返回 False
        """
        telegram_token = os.getenv('TELEGRAM_BOT_TOKEN')
        telegram_chat_id = os.getenv('TELEGRAM_CHAT_ID')
        
        if not telegram_token or not telegram_chat_id:
            logger.warning("Telegram 未配置，無法發送圖片")
            return False
        
        if not os.path.exists(photo_path):
            logger.error(f"圖片檔案不存在：{photo_path}")
            return False
        
        try:
            url = f'https://api.telegram.org/bot{telegram_token}/sendPhoto'
            
            with open(photo_path, 'rb') as photo:
                files = {'photo': photo}
                data = {
                    'chat_id': telegram_chat_id,
                    'caption': caption,
                    'parse_mode': 'HTML'
                }
                
                response = requests.post(url, files=files, data=data, timeout=30)
                
                if response.status_code == 200:
                    logger.info(f"圖片已發送到 Telegram：{caption[:30]}...")
                    return True
                else:
                    logger.warning(f"Telegram 圖片發送失敗: {response.text}")
                    return False
                    
        except Exception as e:
            logger.error(f"Telegram 圖片發送異常: {str(e)}")
            return False
        finally:
            # 清理臨時檔案
            try:
                if os.path.exists(photo_path):
                    os.remove(photo_path)
                    logger.debug(f"已清理臨時圖片：{photo_path}")
            except:
                pass
    
    def generate_signal(self, stock_code: str, price: float, 
                       ma_20: Optional[float], ma_50: Optional[float], 
                       rsi: Optional[float], data: pd.DataFrame = None) -> Dict:
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
        if data is not None:
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
        else:
            max_score -= 25

        # 指標5：成交量放大 (權重15%)
        max_score += 15
        if data is not None:
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
        else:
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
        # 使用台灣時間
        tw_now = datetime.now(TW_TZ)
        
        logger.info("=" * 60)
        logger.info(f"開始監控週期 - {tw_now.strftime('%Y-%m-%d %H:%M:%S')} (台灣時間)")
        logger.info(f"Phase 5.1: K線圖表功能{'已啟用' if CHART_ENABLED else '未啟用'}")
        logger.info("=" * 60)
        
        all_signals = []
        
        for stock_code in STOCK_CODES:
            # 先取得或自動抓取股票名稱
            stock_name = self.get_stock_name(stock_code)
            
            logger.info(f"\n監控股票: {stock_name} ({stock_code})")
            
            # 抓取歷史數據用於計算指標
            try:
                import yfinance as yf
                ticker = yf.Ticker(f"{stock_code}.TW")
                hist = ticker.history(period="60d")
                hist = hist.dropna()
                
                if hist.empty:
                    logger.error(f"{stock_code} 無歷史數據")
                    continue
                
                # 取得最新數據
                stock_data = self.fetch_stock_data(stock_code)
                if not stock_data:
                    continue
                
                price = stock_data['price']
                logger.info(f"  當前價格: {price:.2f}")
                
                # 計算技術指標
                closes = hist['Close'].values
                ma_20 = self.calculate_ma(closes.tolist(), 20)
                ma_50 = self.calculate_ma(closes.tolist(), 50)
                rsi = self.calculate_rsi(closes.tolist(), 14)
                
                # 生成信號（傳入完整數據用於 MACD 和成交量計算）
                signal = self.generate_signal(
                    stock_code=stock_code,
                    price=price,
                    ma_20=ma_20,
                    ma_50=ma_50,
                    rsi=rsi,
                    data=hist  # 傳入完整歷史數據
                )
                
                all_signals.append(signal)
                
                # 保存交易日誌（使用台灣時間）
                trade_log = {
                    'stock_code': stock_code,
                    'signal_type': signal['signal_type'],
                    'price': price,
                    'decision_logic': signal['decision_logic'],
                    'profit_loss': 0.0,
                    'timestamp': tw_now.isoformat()
                }
                
                self.save_to_supabase('trade_logs', trade_log)
                
                logger.info(f"  信號: {signal['signal_type']} (信心度: {signal['confidence']:.2%})")
                logger.info(f"  邏輯: {signal['decision_logic']}")
                
                # Phase 5.1: 生成並發送 K 線圖表
                if CHART_ENABLED:
                    logger.info(f"  開始生成 K 線圖表...")
                    chart_path = self.generate_candlestick_chart(
                        stock_code=stock_code,
                        stock_name=stock_name,
                        data=hist,
                        signal=signal
                    )
                    
                    if chart_path:
                        # 準備圖片說明
                        caption = f"<b>{stock_code} {stock_name}</b>\n"
                        caption += f"信號: {signal['signal_type']} | 信心度: {signal['confidence']:.1%}\n"
                        caption += f"價格: {price:.2f} TWD"
                        
                        # 發送圖片
                        self.send_telegram_photo(chart_path, caption)
                
            except Exception as e:
                logger.error(f"處理 {stock_code} 時發生錯誤: {str(e)}")
                continue
        
        # 發送摘要通知
        if all_signals:
            summary_message = self.generate_summary_message(all_signals, tw_now)
            self.send_telegram_notification(summary_message)
        
        logger.info("\n" + "=" * 60)
        logger.info("監控週期完成")
        logger.info("=" * 60)
    
    def generate_summary_message(self, signals: List[Dict], tw_time: datetime) -> str:
        """生成摘要消息（使用台灣時間和股票名稱）"""
        message = "📊 <b>股票監控摘要</b>\n"
        message += f"時間: {tw_time.strftime('%Y-%m-%d %H:%M:%S')} (台灣時間)\n"
        if CHART_ENABLED:
            message += "📈 K線圖表已生成\n"
        message += "\n"
        
        for signal in signals:
            stock_code = signal['code']
            stock_name = self.get_stock_name(stock_code)
            
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
            
            message += f"{emoji} <b>{stock_code} {stock_name} [{level}]</b>\n"
            message += f" 信號: {signal['signal_type']}\n"
            message += f" 價格: {signal['price']:.2f}\n"
            message += f" 信心度: {signal['confidence']:.2%}\n"
            
            if signal['signal_type'] == 'BUY':
                stop_loss = round(signal['price'] * 0.95, 2)
                take_profit = round(signal['price'] * 1.15, 2)
                message += f" 🎯 目標價: {take_profit} (+15%)\n"
                message += f" 🛑 止損價: {stop_loss} (-5%)\n"
            
            message += "\n"
        
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
