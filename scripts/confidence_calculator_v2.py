#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
開明體系 Phase 5.2.3 - 升級版信心度計算
整合 BDI 指數 + 外資籌碼
"""

from typing import Dict, Optional, Tuple, List


class ConfidenceCalculatorV2:
    """
    升級版信心度計算器
    
    Phase 4: 5 個技術指標
    Phase 5.2.3: 
        - 航運股: 7 個指標（技術 5 + BDI 1 + 外資 1）
        - 一般股: 6 個指標（技術 5 + 外資 1）
    """
    
    # 航運股清單
    SHIPPING_STOCKS = ['2603', '2609', '2615', '2637', '2645']
    
    def __init__(self):
        self.shipping_stocks = self.SHIPPING_STOCKS
    
    def is_shipping_stock(self, stock_code: str) -> bool:
        """判斷是否為航運股"""
        return stock_code in self.shipping_stocks
    
    def calculate_confidence(
        self,
        stock_code: str,
        stock_data: Dict,
        bdi_data: Optional[Dict] = None,
        foreign_data: Optional[Dict] = None
    ) -> Tuple[float, List[str]]:
        """
        計算信心度
        
        Args:
            stock_code: 股票代號
            stock_data: 股票技術數據 {
                'price': float,
                'ma_20': float,
                'ma_50': float,
                'rsi': float,
                'macd_signal': str,  # 'golden_cross' or 'dead_cross' or 'neutral'
                'volume_ratio': float  # 當日成交量 / 20日平均量
            }
            bdi_data: BDI 數據（可選）
            foreign_data: 外資數據（可選）
        
        Returns:
            (confidence, logic_parts)
            confidence: 信心度 (0-1)
            logic_parts: 決策邏輯說明列表
        """
        if self.is_shipping_stock(stock_code):
            return self._calculate_shipping_confidence(
                stock_data, bdi_data, foreign_data
            )
        else:
            return self._calculate_normal_confidence(
                stock_data, foreign_data
            )
    
    def _calculate_shipping_confidence(
        self,
        stock_data: Dict,
        bdi_data: Optional[Dict],
        foreign_data: Optional[Dict]
    ) -> Tuple[float, List[str]]:
        """
        航運股信心度計算（7 個指標）
        
        指標權重分配：
        1. MA20 突破: 15%
        2. MA50 趨勢: 15%
        3. RSI 黃金區: 15%
        4. MACD 金叉: 20%
        5. 成交量放大: 10%
        6. BDI 指數: 15%  ⭐ 新增
        7. 外資籌碼: 10%  ⭐ 新增
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
        
        # ===== 技術指標 (75%) =====
        
        # 指標 1: MA20 突破 (15%)
        if ma_20 and price > ma_20:
            score += 15
            logic_parts.append(f"價格>{ma_20:.2f}(MA20)✓")
        else:
            logic_parts.append(f"價格<MA20✗")
        
        # 指標 2: MA50 趨勢 (15%)
        if ma_50 and ma_20 and ma_20 > ma_50:
            score += 15
            logic_parts.append("MA20>MA50✓")
        else:
            logic_parts.append("MA20<MA50✗")
        
        # 指標 3: RSI 黃金區 (15%)
        if rsi:
            if 40 <= rsi <= 65:
                score += 15
                logic_parts.append(f"RSI={rsi:.1f}(黃金區)✓")
            elif 30 <= rsi < 40:
                score += 10
                logic_parts.append(f"RSI={rsi:.1f}(略低)△")
            elif 65 < rsi <= 70:
                score += 10
                logic_parts.append(f"RSI={rsi:.1f}(略高)△")
            else:
                logic_parts.append(f"RSI={rsi:.1f}✗")
        
        # 指標 4: MACD 金叉 (20%)
        if macd_signal == 'golden_cross':
            score += 20
            logic_parts.append("MACD金叉✓")
        elif macd_signal == 'neutral':
            score += 5
            logic_parts.append("MACD中性△")
        else:
            logic_parts.append("MACD死叉✗")
        
        # 指標 5: 成交量放大 (10%)
        if volume_ratio > 1.2:
            score += 10
            logic_parts.append(f"量能放大{volume_ratio:.1f}倍✓")
        elif volume_ratio > 1.0:
            score += 5
            logic_parts.append(f"量能{volume_ratio:.1f}倍△")
        else:
            logic_parts.append(f"量能萎縮{volume_ratio:.1f}倍✗")
        
        # ===== BDI 指數 (15%) ⭐ 新增 =====
        
        if bdi_data:
            bdi_value = bdi_data.get('value', 0)
            bdi_level = bdi_data.get('level', '未知')
            
            if bdi_value > 2000:
                score += 15
                logic_parts.append(f"🚢BDI={bdi_value:.0f}(極強)✓")
            elif bdi_value > 1500:
                score += 10
                logic_parts.append(f"🚢BDI={bdi_value:.0f}(強勢)✓")
            elif bdi_value > 1000:
                score += 5
                logic_parts.append(f"🚢BDI={bdi_value:.0f}(中性)△")
            else:
                logic_parts.append(f"🚢BDI={bdi_value:.0f}(弱勢)✗")
        else:
            logic_parts.append("🚢BDI無數據")
        
        # ===== 外資籌碼 (10%) ⭐ 新增 =====
        
        if foreign_data:
            foreign_net = foreign_data.get('foreign_net', 0)
            
            if foreign_net > 5000:
                score += 10
                logic_parts.append(f"💰外資+{foreign_net:,}張✓")
            elif foreign_net > 1000:
                score += 8
                logic_parts.append(f"💰外資+{foreign_net:,}張✓")
            elif foreign_net > 0:
                score += 5
                logic_parts.append(f"💰外資+{foreign_net:,}張△")
            elif foreign_net > -1000:
                score += 2
                logic_parts.append(f"💰外資{foreign_net:,}張△")
            else:
                logic_parts.append(f"💰外資{foreign_net:,}張✗")
        else:
            logic_parts.append("💰外資無數據")
        
        confidence = score / max_score
        return confidence, logic_parts
    
    def _calculate_normal_confidence(
        self,
        stock_data: Dict,
        foreign_data: Optional[Dict]
    ) -> Tuple[float, List[str]]:
        """
        一般股票信心度計算（6 個指標）
        
        指標權重分配：
        1. MA20 突破: 20%
        2. MA50 趨勢: 20%
        3. RSI 黃金區: 15%
        4. MACD 金叉: 20%
        5. 成交量放大: 10%
        6. 外資籌碼: 15%  ⭐ 新增
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
        
        # ===== 技術指標 (85%) =====
        
        # 指標 1: MA20 突破 (20%)
        if ma_20 and price > ma_20:
            score += 20
            logic_parts.append(f"價格>{ma_20:.2f}(MA20)✓")
        else:
            logic_parts.append(f"價格<MA20✗")
        
        # 指標 2: MA50 趨勢 (20%)
        if ma_50 and ma_20 and ma_20 > ma_50:
            score += 20
            logic_parts.append("MA20>MA50✓")
        else:
            logic_parts.append("MA20<MA50✗")
        
        # 指標 3: RSI 黃金區 (15%)
        if rsi:
            if 40 <= rsi <= 65:
                score += 15
                logic_parts.append(f"RSI={rsi:.1f}(黃金區)✓")
            elif 30 <= rsi < 40:
                score += 10
                logic_parts.append(f"RSI={rsi:.1f}(略低)△")
            elif 65 < rsi <= 70:
                score += 10
                logic_parts.append(f"RSI={rsi:.1f}(略高)△")
            else:
                logic_parts.append(f"RSI={rsi:.1f}✗")
        
        # 指標 4: MACD 金叉 (20%)
        if macd_signal == 'golden_cross':
            score += 20
            logic_parts.append("MACD金叉✓")
        elif macd_signal == 'neutral':
            score += 5
            logic_parts.append("MACD中性△")
        else:
            logic_parts.append("MACD死叉✗")
        
        # 指標 5: 成交量放大 (10%)
        if volume_ratio > 1.2:
            score += 10
            logic_parts.append(f"量能放大{volume_ratio:.1f}倍✓")
        elif volume_ratio > 1.0:
            score += 5
            logic_parts.append(f"量能{volume_ratio:.1f}倍△")
        else:
            logic_parts.append(f"量能萎縮{volume_ratio:.1f}倍✗")
        
        # ===== 外資籌碼 (15%) ⭐ 新增 =====
        
        if foreign_data:
            foreign_net = foreign_data.get('foreign_net', 0)
            
            if foreign_net > 5000:
                score += 15
                logic_parts.append(f"💰外資+{foreign_net:,}張✓")
            elif foreign_net > 1000:
                score += 12
                logic_parts.append(f"💰外資+{foreign_net:,}張✓")
            elif foreign_net > 0:
                score += 8
                logic_parts.append(f"💰外資+{foreign_net:,}張△")
            elif foreign_net > -1000:
                score += 3
                logic_parts.append(f"💰外資{foreign_net:,}張△")
            else:
                logic_parts.append(f"💰外資{foreign_net:,}張✗")
        else:
            logic_parts.append("💰外資無數據")
        
        confidence = score / max_score
        return confidence, logic_parts
    
    def get_signal_level(self, confidence: float) -> Tuple[str, str, str]:
        """
        根據信心度判斷信號等級
        
        Returns:
            (signal_type, level_emoji, level_text)
        """
        if confidence >= 0.70:
            return 'BUY', '🔴', '強烈買入'
        elif confidence >= 0.50:
            return 'BUY', '🟡', '建議買入'
        elif confidence >= 0.30:
            return 'HOLD', '⚪', '觀望'
        else:
            return 'HOLD', '⚫', '暫不考慮'
    
    def format_telegram_message(
        self,
        stock_code: str,
        stock_name: str,
        price: float,
        confidence: float,
        logic_parts: List[str],
        bdi_data: Optional[Dict] = None,
        foreign_data: Optional[Dict] = None
    ) -> str:
        """
        格式化 Telegram 通知訊息（修正版 - 避免 HTML 錯誤）
        
        Args:
            stock_code: 股票代號
            stock_name: 股票名稱
            price: 當前價格
            confidence: 信心度
            logic_parts: 決策邏輯
            bdi_data: BDI 數據（航運股）
            foreign_data: 外資數據
        
        Returns:
            格式化後的訊息
        """
        signal_type, emoji, level_text = self.get_signal_level(confidence)
        
        # 基本訊息 - 簡化 HTML
        message = f"{emoji} {stock_code} {stock_name} [{level_text}]\n"
        message += f"信號: {signal_type}  價格: {price:.2f}  信心度: {confidence:.0%}\n\n"
        
        # 技術面分析
        message += "📊 技術面\n"
        
        # 分離技術指標和其他指標
        tech_parts = [p for p in logic_parts if not p.startswith(('🚢', '💰'))]
        if tech_parts:
            # 每行最多3個指標，避免過長
            for i in range(0, len(tech_parts), 3):
                batch = tech_parts[i:i+3]
                message += " • " + ", ".join(batch) + "\n"
        
        # 航運指標（僅航運股）
        if bdi_data:
            message += f"\n🚢 航運指標\n"
            bdi_value = bdi_data.get('value', 0)
            bdi_change = bdi_data.get('change_percent', 0)
            bdi_level = bdi_data.get('level', '未知')
            
            # 簡化格式，避免複雜符號
            direction = "📈" if bdi_change > 0 else "📉" if bdi_change < 0 else "➡️"
            message += f" • BDI指數: {bdi_value:.0f} ({bdi_change:+.1f}%) {direction}\n"
            message += f" • 運價評級: {bdi_level}\n"
        
        # 籌碼面分析
        if foreign_data:
            message += f"\n💰 籌碼面\n"
            
            foreign_net = foreign_data.get('foreign_net', 0)
            holding_pct = foreign_data.get('foreign_holding_pct', 0)
            strength = foreign_data.get('strength', '未知')
            
            # 簡化格式
            if foreign_net > 0:
                message += f" • 外資買超: +{foreign_net:,}張 🟢\n"
            elif foreign_net < 0:
                message += f" • 外資賣超: {foreign_net:,}張 🔴\n"
            else:
                message += f" • 外資持平: {foreign_net:,}張 ⚪\n"
            
            if holding_pct > 0:
                message += f" • 外資持股: {holding_pct:.1f}%\n"
            
            message += f" • 籌碼評級: {strength}\n"
        
        # 止盈止損
        if signal_type == 'BUY':
            take_profit = price * 1.15
            stop_loss = price * 0.95
            
            message += f"\n🎯 目標價: {take_profit:.2f} (+15%)\n"
            message += f"🛑 止損價: {stop_loss:.2f} (-5%)\n"
        
        return message


# ============================================================================
# 使用範例
# ============================================================================

if __name__ == '__main__':
    print("🚀 開明體系 Phase 5.2.3 - 信心度計算測試\n")
    
    calculator = ConfidenceCalculatorV2()
    
    # 測試案例 1: 航運股（慧洋 2637）
    print("=" * 60)
    print("測試 1: 航運股 - 慧洋 2637")
    print("=" * 60)
    
    stock_data_shipping = {
        'price': 75.80,
        'ma_20': 72.50,
        'ma_50': 70.00,
        'rsi': 52.3,
        'macd_signal': 'golden_cross',
        'volume_ratio': 1.5
    }
    
    bdi_data = {
        'value': 1876,
        'change_percent': 2.3,
        'level': '強勢'
    }
    
    foreign_data_2637 = {
        'foreign_net': 3200,
        'foreign_holding_pct': 28.5,
        'strength': '強勢'
    }
    
    confidence, logic = calculator.calculate_confidence(
        '2637', stock_data_shipping, bdi_data, foreign_data_2637
    )
    
    print(f"信心度: {confidence:.1%}")
    print(f"決策邏輯:")
    for part in logic:
        print(f"  • {part}")
    
    print("\n📱 Telegram 訊息:")
    print("-" * 60)
    message = calculator.format_telegram_message(
        '2637', '慧洋-KY', 75.80, confidence, logic, bdi_data, foreign_data_2637
    )
    print(message)
    
    # 測試案例 2: 一般股票（台積電 2330）
    print("\n" + "=" * 60)
    print("測試 2: 一般股票 - 台積電 2330")
    print("=" * 60)
    
    stock_data_normal = {
        'price': 2050.00,
        'ma_20': 2000.00,
        'ma_50': 1950.00,
        'rsi': 58.1,
        'macd_signal': 'golden_cross',
        'volume_ratio': 1.3
    }
    
    foreign_data_2330 = {
        'foreign_net': 12500,
        'foreign_holding_pct': 78.2,
        'strength': '極度強勢'
    }
    
    confidence, logic = calculator.calculate_confidence(
        '2330', stock_data_normal, None, foreign_data_2330
    )
    
    print(f"信心度: {confidence:.1%}")
    print(f"決策邏輯:")
    for part in logic:
        print(f"  • {part}")
    
    print("\n📱 Telegram 訊息:")
    print("-" * 60)
    message = calculator.format_telegram_message(
        '2330', '台積電', 2050.00, confidence, logic, None, foreign_data_2330
    )
    print(message)
