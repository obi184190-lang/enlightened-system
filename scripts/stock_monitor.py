#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
股票監控與交易決策系統 - Phase 5.2.1
Stock Monitor & Trading Bot with Advanced AI Decision Making
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
import numpy as np

# K線圖表套件（Phase 5.1）
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

# Phase 5.2.1: Claude API 開關（預留）
CLAUDE_API_ENABLED = os.getenv('CLAUDE_API_ENABLED', 'false').lower() == 'true'
CLAUDE_API_KEY = os.getenv('CLAUDE_API_KEY', '')

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


class AdvancedIndicators:
    """進階技術指標計算器 (Phase 5.2.1)"""
    
    @staticmethod
    def calculate_bollinger_bands(prices: pd.Series, period: int = 20, std_dev: int = 2) -> Dict:
        """
        計算布林通道
        
        Returns:
            {
                'upper': 上軌,
                'middle': 中軌 (MA),
                'lower': 下軌,
                'bandwidth': 通道寬度,
                'position': 價格位置 (0-1)
            }
        """
        if len(prices) < period:
            return None
        
        middle = prices.rolling(window=period).mean()
        std = prices.rolling(window=period).std()
        upper = middle + (std * std_dev)
        lower = middle - (std * std_dev)
        
        bandwidth = ((upper - lower) / middle * 100).iloc[-1]
        
        # 計算當前價格在通道中的位置 (0=下軌, 0.5=中軌, 1=上軌)
        current_price = prices.iloc[-1]
        current_upper = upper.iloc[-1]
        current_lower = lower.iloc[-1]
        
        if current_upper == current_lower:
            position = 0.5
        else:
            position = (current_price - current_lower) / (current_upper - current_lower)
        
        return {
            'upper': upper.iloc[-1],
            'middle': middle.iloc[-1],
            'lower': lower.iloc[-1],
            'bandwidth': bandwidth,
            'position': position
        }
    
    @staticmethod
    def calculate_kd(high: pd.Series, low: pd.Series, close: pd.Series, 
                     n: int = 9, m1: int = 3, m2: int = 3) -> Dict:
        """
        計算 KD 指標 (隨機指標)
        
        Returns:
            {
                'k': K值,
                'd': D值,
                'j': J值 (3K - 2D)
            }
        """
        if len(close) < n:
            return None
        
        # 計算 RSV
        lowest_low = low.rolling(window=n).min()
        highest_high = high.rolling(window=n).max()
        rsv = (close - lowest_low) / (highest_high - lowest_low) * 100
        
        # 計算 K, D
        k = rsv.ewm(span=m1, adjust=False).mean()
        d = k.ewm(span=m2, adjust=False).mean()
        j = 3 * k - 2 * d
        
        return {
            'k': k.iloc[-1],
            'd': d.iloc[-1],
            'j': j.iloc[-1]
        }
    
    @staticmethod
    def calculate_williams_r(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> float:
        """
        計算威廉指標 %R
        
        Returns:
            威廉指標值 (-100 到 0)
        """
        if len(close) < period:
            return None
        
        highest_high = high.rolling(window=period).max()
        lowest_low = low.rolling(window=period).min()
        
        wr = ((highest_high - close) / (highest_high - lowest_low)) * -100
        
        return wr.iloc[-1]
    
    @staticmethod
    def calculate_adx(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> Dict:
        """
        計算 ADX (平均趨向指數)
        
        Returns:
            {
                'adx': ADX值 (0-100),
                'strength': 趨勢強度描述
            }
        """
        if len(close) < period + 1:
            return None
        
        # 計算 +DM, -DM
        high_diff = high.diff()
        low_diff = -low.diff()
        
        plus_dm = pd.Series([max(h, 0) if h > l else 0 for h, l in zip(high_diff, low_diff)], index=high.index)
        minus_dm = pd.Series([max(l, 0) if l > h else 0 for h, l in zip(high_diff, low_diff)], index=low.index)
        
        # 計算 TR (True Range)
        tr1 = high - low
        tr2 = abs(high - close.shift())
        tr3 = abs(low - close.shift())
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        
        # 計算 ATR
        atr = tr.rolling(window=period).mean()
        
        # 計算 +DI, -DI
        plus_di = 100 * (plus_dm.rolling(window=period).mean() / atr)
        minus_di = 100 * (minus_dm.rolling(window=period).mean() / atr)
        
        # 計算 DX, ADX
        dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)
        adx = dx.rolling(window=period).mean()
        
        adx_value = adx.iloc[-1]
        
        # 判斷趨勢強度
        if adx_value > 50:
            strength = "極強趨勢"
        elif adx_value > 25:
            strength = "強趨勢"
        elif adx_value > 15:
            strength = "弱趨勢"
        else:
            strength = "無明確趨勢"
        
        return {
            'adx': adx_value,
            'strength': strength,
            'plus_di': plus_di.iloc[-1],
            'minus_di': minus_di.iloc[-1]
        }


class AIDecisionEngine:
    """AI 智能決策引擎 (Phase 5.2.1)"""
    
    @staticmethod
    def analyze_risk_level(indicators: Dict, signal_type: str, confidence: float) -> Dict:
        """
        風險評級分析
        
        Returns:
            {
                'level': 'Low' | 'Medium' | 'High',
                'score': 風險分數 (0-100),
                'factors': [風險因素列表]
            }
        """
        risk_score = 0
        factors = []
        
        # 因素1: 信心度越低，風險越高
        if confidence < 0.50:
            risk_score += 30
            factors.append("信心度偏低")
        elif confidence < 0.70:
            risk_score += 15
        
        # 因素2: 布林通道位置
        if indicators.get('bollinger'):
            bb_pos = indicators['bollinger']['position']
            if bb_pos > 0.9:  # 接近上軌
                risk_score += 20
                factors.append("價格接近布林上軌（超買）")
            elif bb_pos < 0.1:  # 接近下軌
                risk_score += 10
                factors.append("價格接近布林下軌")
        
        # 因素3: KD 超買超賣
        if indicators.get('kd'):
            k = indicators['kd']['k']
            if k > 80:
                risk_score += 15
                factors.append("KD 超買")
            elif k < 20 and signal_type == 'BUY':
                risk_score -= 10  # 超賣時買入風險較低
        
        # 因素4: ADX 趨勢強度
        if indicators.get('adx'):
            adx = indicators['adx']['adx']
            if adx < 15:
                risk_score += 20
                factors.append("無明確趨勢，方向不明")
        
        # 因素5: 威廉指標
        if indicators.get('williams_r'):
            wr = indicators['williams_r']
            if wr > -20:
                risk_score += 15
                factors.append("威廉指標超買")
        
        # 判斷風險等級
        if risk_score >= 50:
            level = "High"
        elif risk_score >= 25:
            level = "Medium"
        else:
            level = "Low"
        
        return {
            'level': level,
            'score': min(risk_score, 100),
            'factors': factors if factors else ['風險因素較少']
        }
    
    @staticmethod
    def recommend_timing(indicators: Dict, signal_type: str, price: float) -> Dict:
        """
        時機推薦
        
        Returns:
            {
                'action': '立即買入' | '分批買入' | '等待' | '觀望',
                'timing': 建議時機描述,
                'entry_points': [建議進場價位],
                'reason': 理由
            }
        """
        if signal_type != 'BUY':
            return {
                'action': '持有或賣出',
                'timing': '無買入建議',
                'entry_points': [],
                'reason': '當前非買入信號'
            }
        
        reasons = []
        entry_points = []
        
        # 分析布林通道
        bb_pos = indicators.get('bollinger', {}).get('position', 0.5)
        bb_lower = indicators.get('bollinger', {}).get('lower')
        bb_middle = indicators.get('bollinger', {}).get('middle')
        
        # 分析 KD
        kd_k = indicators.get('kd', {}).get('k', 50)
        
        # 分析 ADX
        adx_value = indicators.get('adx', {}).get('adx', 0)
        adx_strength = indicators.get('adx', {}).get('strength', '')
        
        # 決策邏輯
        if bb_pos < 0.3 and kd_k < 30 and adx_value > 20:
            action = '立即買入'
            timing = '現在是較佳進場時機'
            entry_points = [price]
            reasons.append("價格在布林下軌附近，KD超賣，且有明確趨勢")
        
        elif bb_pos < 0.5 and adx_value > 25:
            action = '分批買入'
            timing = '建議分2-3次進場'
            entry_points = [price, price * 0.97, price * 0.95]
            reasons.append("技術面尚可，但建議分散風險")
            if bb_lower:
                reasons.append(f"若跌至布林下軌 {bb_lower:.2f} 可加碼")
        
        elif bb_pos > 0.7:
            action = '等待'
            timing = '等待回調至較低價位'
            entry_points = [bb_middle] if bb_middle else [price * 0.95]
            reasons.append("當前價格偏高，建議等待")
            if bb_middle:
                reasons.append(f"建議回調至 {bb_middle:.2f} 附近再進場")
        
        elif adx_value < 15:
            action = '觀望'
            timing = '趨勢不明確，建議觀望'
            entry_points = []
            reasons.append("無明確趨勢，等待方向確立")
        
        else:
            action = '分批買入'
            timing = '可小量試單'
            entry_points = [price, price * 0.97]
            reasons.append("技術面中性，可小量試單")
        
        return {
            'action': action,
            'timing': timing,
            'entry_points': entry_points,
            'reason': '；'.join(reasons)
        }
    
    @staticmethod
    def generate_ai_suggestion(stock_code: str, stock_name: str, price: float,
                              indicators: Dict, signal_type: str, confidence: float) -> str:
        """
        生成 AI 分析建議（規則引擎版本，修復版）
        
        Returns:
            格式化的建議文字
        """
        # 風險評級
        risk = AIDecisionEngine.analyze_risk_level(indicators, signal_type, confidence)
        
        # 時機推薦
        timing = AIDecisionEngine.recommend_timing(indicators, signal_type, price)
        
        # 組合建議
        suggestion = f"\n🤖 <b>AI 智能分析 - {stock_code} {stock_name}</b>\n"
        suggestion += f"建議動作: {timing['action']}\n"
        suggestion += f"進場時機: {timing['timing']}\n"
        
        if timing['entry_points']:
            prices_str = ', '.join([f"{p:.2f}" for p in timing['entry_points']])
            suggestion += f"建議價位: {prices_str}\n"
        
        suggestion += f"\n風險評級: {risk['level']} (分數: {risk['score']}/100)\n"
        suggestion += f"風險因素: {', '.join(risk['factors'])}\n"
        
        suggestion += f"\n💡 <b>理由分析</b>\n"
        suggestion += f"{timing['reason']}\n"
        
        # 技術面總結（容錯處理）
        suggestion += f"\n📊 <b>技術面總結</b>\n"
        
        has_any_indicator = False
        
        if indicators.get('bollinger'):
            bb = indicators['bollinger']
            bb_status = "超買區" if bb['position'] > 0.8 else "超賣區" if bb['position'] < 0.2 else "中性區"
            suggestion += f"• 布林通道: {bb_status} (位置 {bb['position']:.1%})\n"
            has_any_indicator = True
        
        if indicators.get('kd'):
            kd = indicators['kd']
            kd_signal = "金叉" if kd['k'] > kd['d'] else "死叉"
            suggestion += f"• KD指標: K={kd['k']:.1f}, D={kd['d']:.1f} ({kd_signal})\n"
            has_any_indicator = True
        
        if indicators.get('adx'):
            adx = indicators['adx']
            suggestion += f"• ADX: {adx['adx']:.1f} ({adx['strength']})\n"
            has_any_indicator = True
        
        if indicators.get('williams_r') is not None:
            wr = indicators['williams_r']
            wr_status = "超買" if wr > -20 else "超賣" if wr < -80 else "中性"
            suggestion += f"• 威廉指標: {wr:.1f} ({wr_status})\n"
            has_any_indicator = True
        
        if not has_any_indicator:
            suggestion += "進階指標數據不足，建議謹慎操作\n"
        
        return suggestion
    
    @staticmethod
    async def call_claude_api(stock_data: Dict, indicators: Dict) -> Optional[str]:
        """
        調用 Claude API 進行深度分析（預留功能）
        
        Args:
            stock_data: 股票基本數據
            indicators: 所有技術指標
            
        Returns:
            Claude 的分析建議，失敗時返回 None
        """
        if not CLAUDE_API_ENABLED or not CLAUDE_API_KEY:
            logger.info("Claude API 未啟用")
            return None
        
        try:
            # TODO: 實作 Claude API 調用
            # 這裡預留接口，Phase 5.2.2 時實作
            logger.info("Claude API 功能預留中...")
            return None
        
        except Exception as e:
            logger.error(f"Claude API 調用失敗: {str(e)}")
            return None


class TaiwanStockMonitor:
    """台灣股市監控器 (Phase 5.2.1 升級版)"""
    
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
        self.advanced_indicators = AdvancedIndicators()
        self.ai_engine = AIDecisionEngine()
    
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
        使用 yfinance API
        """
        try:
            import yfinance as yf
            ticker = yf.Ticker(f"{stock_code}.TW")
            hist = ticker.history(period="5d")
            hist = hist.dropna()
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
    
    def calculate_all_indicators(self, data: pd.DataFrame) -> Dict:
        """
        計算所有技術指標（Phase 5.2.1 修復版）
        
        Returns:
            {
                'ma_20': float,
                'ma_50': float,
                'rsi': float,
                'macd': dict,
                'bollinger': dict,
                'kd': dict,
                'williams_r': float,
                'adx': dict
            }
        """
        indicators = {}
        
        try:
            closes = data['Close']
            highs = data['High']
            lows = data['Low']
            
            # 基礎指標（加入容錯）
            try:
                ma_20 = closes.rolling(window=20).mean().iloc[-1]
                if pd.notna(ma_20):
                    indicators['ma_20'] = float(ma_20)
            except:
                pass
            
            try:
                ma_50 = closes.rolling(window=50).mean().iloc[-1]
                if pd.notna(ma_50):
                    indicators['ma_50'] = float(ma_50)
            except:
                pass
            
            try:
                rsi = self.calculate_rsi(closes.tolist(), 14)
                if rsi is not None and pd.notna(rsi):
                    indicators['rsi'] = float(rsi)
            except:
                pass
            
            # MACD（加入容錯）
            try:
                if len(closes) >= 26:
                    ema12 = closes.ewm(span=12).mean().values
                    ema26 = closes.ewm(span=26).mean().values
                    macd_line = ema12 - ema26
                    signal_line = pd.Series(macd_line).ewm(span=9).mean().values
                    if pd.notna(macd_line[-1]) and pd.notna(signal_line[-1]):
                        indicators['macd'] = {
                            'line': float(macd_line[-1]),
                            'signal': float(signal_line[-1]),
                            'histogram': float(macd_line[-1] - signal_line[-1])
                        }
            except:
                pass
            
            # Phase 5.2.1 新增指標（加入容錯）
            try:
                bb = self.advanced_indicators.calculate_bollinger_bands(closes)
                if bb is not None:
                    # 確保所有值都是有效數字
                    if all(pd.notna(v) for v in [bb['upper'], bb['middle'], bb['lower'], bb['bandwidth'], bb['position']]):
                        indicators['bollinger'] = {
                            'upper': float(bb['upper']),
                            'middle': float(bb['middle']),
                            'lower': float(bb['lower']),
                            'bandwidth': float(bb['bandwidth']),
                            'position': float(bb['position'])
                        }
            except Exception as e:
                logger.warning(f"布林通道計算失敗: {str(e)}")
            
            try:
                kd = self.advanced_indicators.calculate_kd(highs, lows, closes)
                if kd is not None:
                    if all(pd.notna(v) for v in [kd['k'], kd['d'], kd['j']]):
                        indicators['kd'] = {
                            'k': float(kd['k']),
                            'd': float(kd['d']),
                            'j': float(kd['j'])
                        }
            except Exception as e:
                logger.warning(f"KD指標計算失敗: {str(e)}")
            
            try:
                wr = self.advanced_indicators.calculate_williams_r(highs, lows, closes)
                if wr is not None and pd.notna(wr):
                    indicators['williams_r'] = float(wr)
            except Exception as e:
                logger.warning(f"威廉指標計算失敗: {str(e)}")
            
            try:
                adx = self.advanced_indicators.calculate_adx(highs, lows, closes)
                if adx is not None:
                    if all(pd.notna(v) for v in [adx['adx'], adx['plus_di'], adx['minus_di']]):
                        indicators['adx'] = {
                            'adx': float(adx['adx']),
                            'strength': adx['strength'],
                            'plus_di': float(adx['plus_di']),
                            'minus_di': float(adx['minus_di'])
                        }
            except Exception as e:
                logger.warning(f"ADX計算失敗: {str(e)}")
            
        except Exception as e:
            logger.error(f"計算指標時發生錯誤: {str(e)}")
        
        return indicators
    
    def generate_candlestick_chart(self, stock_code: str, stock_name: str, 
                                   data: pd.DataFrame, signal: Dict) -> Optional[str]:
        """
        生成K線圖表（Phase 5.1）
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
        發送圖片到 Telegram（Phase 5.1）
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
    
    def generate_signal(self, stock_code: str, price: float, indicators: Dict, data: pd.DataFrame = None) -> Dict:
        """
        生成買賣信號（Phase 5.2.1 強化版）
        """
        ma_20 = indicators.get('ma_20')
        ma_50 = indicators.get('ma_50')
        rsi = indicators.get('rsi')
        
        signal = {
            'code': stock_code,
            'price': price,
            'ma_20': ma_20,
            'ma_50': ma_50,
            'rsi': rsi,
            'signal_type': 'HOLD',
            'confidence': 0.0,
            'decision_logic': '無明確信號',
            'indicators': indicators  # Phase 5.2.1: 保存所有指標
        }
        
        # Phase 5.2.1: 多指標加權信心度系統（優化版）
        score = 0
        max_score = 0
        logic_parts = []

        # 指標1：MA20突破 (權重15%)
        max_score += 15
        if ma_20 and price > ma_20:
            score += 15
            logic_parts.append("價格>MA20✓")

        # 指標2：MA50趨勢 (權重15%)
        max_score += 15
        if ma_50 and ma_20 and ma_20 > ma_50:
            score += 15
            logic_parts.append("MA20>MA50✓")

        # 指標3：RSI適中區間 (權重15%)
        max_score += 15
        if rsi:
            if 40 <= rsi <= 65:
                score += 15
                logic_parts.append(f"RSI黃金區={rsi:.1f}✓")
            elif 30 <= rsi < 40 or 65 < rsi <= 70:
                score += 8
                logic_parts.append(f"RSI尚可={rsi:.1f}")

        # 指標4：MACD (權重20%)
        max_score += 20
        if indicators.get('macd'):
            macd = indicators['macd']
            if macd['histogram'] > 0:
                score += 20
                logic_parts.append("MACD金叉✓")
            elif macd['histogram'] > -0.5:
                score += 10
                logic_parts.append("MACD轉強")

        # 指標5：成交量 (權重10%)
        max_score += 10
        if data is not None:
            try:
                volumes = data['Volume'].values
                if len(volumes) >= 20:
                    avg_vol = volumes[-20:].mean()
                    if volumes[-1] > avg_vol * 1.5:
                        score += 10
                        logic_parts.append("成交量放大✓")
            except:
                max_score -= 10

        # Phase 5.2.1: 新增指標
        
        # 指標6：布林通道 (權重10%)
        max_score += 10
        if indicators.get('bollinger'):
            bb_pos = indicators['bollinger']['position']
            if 0.3 <= bb_pos <= 0.7:
                score += 10
                logic_parts.append("布林中性區✓")
            elif bb_pos < 0.3:
                score += 5
                logic_parts.append("布林下軌")

        # 指標7：KD指標 (權重10%)
        max_score += 10
        if indicators.get('kd'):
            kd = indicators['kd']
            if kd['k'] > kd['d'] and kd['k'] < 80:
                score += 10
                logic_parts.append("KD金叉✓")
            elif kd['k'] < 20:
                score += 5
                logic_parts.append("KD超賣")

        # 指標8：ADX趨勢強度 (權重5%)
        max_score += 5
        if indicators.get('adx'):
            adx_val = indicators['adx']['adx']
            if adx_val > 25:
                score += 5
                logic_parts.append(f"ADX強勢✓")

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
        """執行一個監控週期（Phase 5.2.1 升級版）"""
        # 使用台灣時間
        tw_now = datetime.now(TW_TZ)
        
        logger.info("=" * 60)
        logger.info(f"開始監控週期 - {tw_now.strftime('%Y-%m-%d %H:%M:%S')} (台灣時間)")
        logger.info(f"Phase 5.2.1: AI 智能判斷功能已啟用")
        logger.info(f"K線圖表: {'已啟用' if CHART_ENABLED else '未啟用'}")
        logger.info(f"Claude API: {'已啟用' if CLAUDE_API_ENABLED else '預留'}")
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
                
                # Phase 5.2.1: 計算所有技術指標
                indicators = self.calculate_all_indicators(hist)
                
                # 生成信號
                signal = self.generate_signal(
                    stock_code=stock_code,
                    price=price,
                    indicators=indicators,
                    data=hist
                )
                
                # Phase 5.2.1: 生成 AI 建議
                if signal['signal_type'] in ['BUY', 'SELL']:
                    ai_suggestion = self.ai_engine.generate_ai_suggestion(
                        stock_code=stock_code,
                        stock_name=stock_name,
                        price=price,
                        indicators=indicators,
                        signal_type=signal['signal_type'],
                        confidence=signal['confidence']
                    )
                    signal['ai_suggestion'] = ai_suggestion
                else:
                    signal['ai_suggestion'] = ""
                
                all_signals.append(signal)
                
                # 保存交易日誌
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
                        
                        # Phase 5.2.1: 如果有 AI 建議，延遲後發送（避免限流）
                        if signal.get('ai_suggestion'):
                            time.sleep(1)  # 延遲 1 秒
                            logger.info(f"  發送 AI 智能分析...")
                            success = self.send_telegram_notification(signal['ai_suggestion'])
                            if success:
                                logger.info(f"  AI 分析已發送")
                            else:
                                logger.warning(f"  AI 分析發送失敗")
                
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
        """生成摘要消息（Phase 5.2.1 強化版）"""
        message = "📊 <b>股票監控摘要</b>\n"
        message += f"時間: {tw_time.strftime('%Y-%m-%d %H:%M:%S')} (台灣時間)\n"
        if CHART_ENABLED:
            message += "📈 K線圖表已生成\n"
        message += "🤖 AI 智能判斷已啟用\n"
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
