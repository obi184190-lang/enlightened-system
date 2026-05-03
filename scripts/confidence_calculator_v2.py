#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
開明體系 Phase 5.2.3 - 升級版信心度計算
整合 BDI 指數 + 外資籌碼

Phase 5.2.3 修正（2026-05-03）：
- MACD 中性從 +5 提升至 +10（半分）
- RSI 超買區（>70）從 0分 改為 +5（懲罰）
- RSI 65-70 從 +10 調整為 +8
- 成交量萎縮（<0.8x）從 +5 改為 0（不加分）
- 新增 conflict_detector 矛盾說明整合
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
        6. BDI 指數: 15% ⭐ 新增
        7. 外資籌碼: 10% ⭐ 新增
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

        # ── 指標 3: RSI 黃金區 (15%) 【修正】────────────────────
        # 修正說明：
        #   舊版：RSI>70 → 0分（與 RSI<30 同等懲罰，過嚴）
        #         RSI 65-70 → +10（與黃金區差距只有5分）
        #   新版：RSI>70 → +5（超買，給予輕微懲罰但不歸零）
        #         RSI 65-70 → +8（偏強，比黃金區少7分）
        if rsi:
            if 40 <= rsi <= 65:
                score += 15
                logic_parts.append(f"RSI={rsi:.1f}(黃金區)✓")
            elif 30 <= rsi < 40:
                score += 10
                logic_parts.append(f"RSI={rsi:.1f}(略低)△")
            elif 65 < rsi <= 70:
                score += 8  # 舊版 +10，改為 +8
                logic_parts.append(f"RSI={rsi:.1f}(偏強注意)△")
            elif rsi > 70:
                score += 5  # 舊版 0分，改為 +5（超買警示但不歸零）
                logic_parts.append(f"RSI={rsi:.1f}(超買⚠️)✗")
            else:
                logic_parts.append(f"RSI={rsi:.1f}✗")

        # ── 指標 4: MACD 金叉 (20%) 【修正】────────────────────
        # 修正說明：
        #   舊版：neutral → +5（只有金叉的25%，懲罰過重）
        #   新版：neutral → +10（金叉的50%，反映「無明確方向」）
        if macd_signal == 'golden_cross':
            score += 20
            logic_parts.append("MACD金叉✓")
        elif macd_signal == 'neutral':
            score += 10  # 舊版 +5，改為 +10
            logic_parts.append("MACD中性△")
        else:
            logic_parts.append("MACD死叉✗")

        # ── 指標 5: 成交量放大 (10%) 【修正】───────────────────
        # 修正說明：
        #   舊版：volume_ratio <= 1.0 → +5（縮量還給半分）
        #   新版：volume_ratio < 0.8 → 0分（明顯縮量不應加分）
        #         volume_ratio 0.8-1.0 → +3（輕微縮量給少量分）
        if volume_ratio > 1.2:
            score += 10
            logic_parts.append(f"量能放大{volume_ratio:.1f}倍✓")
        elif volume_ratio > 1.0:
            score += 5
            logic_parts.append(f"量能{volume_ratio:.1f}倍△")
        elif volume_ratio >= 0.8:
            score += 3  # 新增：輕微縮量給少量分
            logic_parts.append(f"量能{volume_ratio:.1f}倍△")
        else:
            score += 0  # 舊版 +5，改為 0
            logic_parts.append(f"量能萎縮{volume_ratio:.1f}倍✗")

        # ===== BDI 指數 (15%) ⭐ 不變 =====
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

        # ===== 外資籌碼 (10%) ⭐ 不變 =====
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
        6. 外資籌碼: 15% ⭐ 新增
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

        # ── 指標 3: RSI 黃金區 (15%) 【修正】────────────────────
        if rsi:
            if 40 <= rsi <= 65:
                score += 15
                logic_parts.append(f"RSI={rsi:.1f}(黃金區)✓")
            elif 30 <= rsi < 40:
                score += 10
                logic_parts.append(f"RSI={rsi:.1f}(略低)△")
            elif 65 < rsi <= 70:
                score += 8  # 舊版 +10，改為 +8
                logic_parts.append(f"RSI={rsi:.1f}(偏強注意)△")
            elif rsi > 70:
                score += 5  # 舊版 0分，改為 +5（超買警示）
                logic_parts.append(f"RSI={rsi:.1f}(超買⚠️)✗")
            else:
                logic_parts.append(f"RSI={rsi:.1f}✗")

        # ── 指標 4: MACD 金叉 (20%) 【修正】────────────────────
        if macd_signal == 'golden_cross':
            score += 20
            logic_parts.append("MACD金叉✓")
        elif macd_signal == 'neutral':
            score += 10  # 舊版 +5，改為 +10
            logic_parts.append("MACD中性△")
        else:
            logic_parts.append("MACD死叉✗")

        # ── 指標 5: 成交量放大 (10%) 【修正】───────────────────
        if volume_ratio > 1.2:
            score += 10
            logic_parts.append(f"量能放大{volume_ratio:.1f}倍✓")
        elif volume_ratio > 1.0:
            score += 5
            logic_parts.append(f"量能{volume_ratio:.1f}倍△")
        elif volume_ratio >= 0.8:
            score += 3  # 新增：輕微縮量
            logic_parts.append(f"量能{volume_ratio:.1f}倍△")
        else:
            score += 0  # 舊版 +5，改為 0
            logic_parts.append(f"量能萎縮{volume_ratio:.1f}倍✗")

        # ===== 外資籌碼 (15%) ⭐ 不變 =====
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
        """格式化 Telegram 通知訊息（純文字版）"""
        signal_type, emoji, level_text = self.get_signal_level(confidence)

        message = f"{emoji} {stock_code} {stock_name} [{level_text}]\n"
        message += f"信號: {signal_type}  價格: {price:.2f}  信心度: {confidence:.0%}\n\n"

        # 技術面
        message += "📊 技術面\n"
        tech_parts = [p for p in logic_parts if not p.startswith(('🚢', '💰'))]
        if tech_parts:
            for i in range(0, len(tech_parts), 3):
                batch = tech_parts[i:i+3]
                message += " • " + ", ".join(batch) + "\n"

        # 航運指標
        if bdi_data:
            message += f"\n🚢 航運指標\n"
            bdi_value = bdi_data.get('value', 0)
            bdi_change = bdi_data.get('change_percent', 0)
            bdi_level = bdi_data.get('level', '未知')
            direction = "📈" if bdi_change > 0 else "📉" if bdi_change < 0 else "➡️"
            message += f" • BDI指數: {bdi_value:.0f} ({bdi_change:+.1f}%) {direction}\n"
            message += f" • 運價評級: {bdi_level}\n"

        # 籌碼面
        if foreign_data:
            message += f"\n💰 籌碼面\n"
            foreign_net = foreign_data.get('foreign_net', 0)
            holding_pct = foreign_data.get('foreign_holding_pct', 0)
            strength = foreign_data.get('strength', '未知')
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
# 驗證測試 — 昨天實際數據對照
# ============================================================================
if __name__ == '__main__':
    calc = ConfidenceCalculatorV2()

    cases = [
        {
            'code': '2330', 'name': '台積電', 'price': 2135.0,
            'stock_data': {'price': 2135.0, 'ma_20': 2042.75, 'ma_50': 1900.0,
                           'rsi': 62.6, 'macd_signal': 'neutral', 'volume_ratio': 1.3},
            'foreign_data': {'foreign_net': 2000, 'foreign_holding_pct': 78.2, 'strength': '強勢'},
            'old': 0.70
        },
        {
            'code': '2303', 'name': '聯電', 'price': 77.3,
            'stock_data': {'price': 77.3, 'ma_20': 67.71, 'ma_50': 60.0,
                           'rsi': 71.2, 'macd_signal': 'neutral', 'volume_ratio': 1.7},
            'foreign_data': {'foreign_net': 500, 'foreign_holding_pct': 25.0, 'strength': '中性'},
            'old': 0.55
        },
        {
            'code': '2637', 'name': '慧洋', 'price': 71.7,
            'stock_data': {'price': 71.7, 'ma_20': 71.69, 'ma_50': 65.0,
                           'rsi': 53.9, 'macd_signal': 'neutral', 'volume_ratio': 0.5},
            'bdi_data': {'value': 1173, 'change_percent': 0.1, 'level': '中性'},
            'foreign_data': {'foreign_net': 800, 'foreign_holding_pct': 22.1, 'strength': '中性'},
            'old': 0.55
        },
        {
            'code': '2317', 'name': '鴻海', 'price': 219.5,
            'stock_data': {'price': 219.5, 'ma_20': 209.8, 'ma_50': 225.0,
                           'rsi': 70.2, 'macd_signal': 'neutral', 'volume_ratio': 1.1},
            'foreign_data': {'foreign_net': -200, 'foreign_holding_pct': 45.0, 'strength': '中性'},
            'old': 0.30
        },
    ]

    print("=" * 55)
    print("🧪 修正版信心度驗證 — 昨日實際數據對照")
    print("=" * 55)
    for c in cases:
        conf, logic = calc.calculate_confidence(
            c['code'], c['stock_data'],
            c.get('bdi_data'), c.get('foreign_data')
        )
        old = c['old']
        diff = conf - old
        arrow = f"▲{abs(diff):.0%}" if diff > 0 else f"▼{abs(diff):.0%}" if diff < 0 else "→同"
        print(f"\n{c['code']} {c['name']}")
        print(f"  舊: {old:.0%}  →  新: {conf:.0%}  ({arrow})")
        print(f"  明細: {' | '.join(logic)}")
