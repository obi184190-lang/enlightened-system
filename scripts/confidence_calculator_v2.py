# confidence_calculator_v2.py
import yaml
import json
from pathlib import Path
from typing import Dict, Tuple

class ConfidenceCalculatorV2:
    """
    Phase 5.2.3 信心度計算器 V2
    預設從專案根目錄讀取 weights_config.yaml
    """
    
    def __init__(self, config_path: str = "weights_config.yaml"):
        self.config_path = config_path
        self.config = self._load_config(config_path)
        self.global_settings = self.config.get('global_settings', {})
        self.factors = self.config.get('factors', {})
        self.sectors = self.config.get('sectors', {})
        self.adjustments = self.config.get('adjustments', {})
        self.signals = self.config.get('signals', {})

    def _load_config(self, config_path: str) -> Dict:
        """載入 YAML 設定檔"""
        path = Path(config_path)
        if not path.exists():
            print(f"⚠️ 警告：找不到 {config_path}，使用內建預設權重")
            return self._get_default_config()

        try:
            with open(path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f)
        except Exception as e:
            print(f"❌ 讀取 weights_config.yaml 失敗: {e}")
            return self._get_default_config()

    def _get_default_config(self) -> Dict:
        """內建預設設定"""
        return {
            "global_settings": {"min_confidence": 30, "max_confidence": 100, "default_sector": "general"},
            "factors": {},
            "sectors": {},
            "adjustments": {},
            "signals": {}
        }

    def calculate_confidence(self, stock_data: Dict) -> Tuple[int, Dict]:
        """計算信心度主函式"""
        sector = stock_data.get('sector') or stock_data.get('industry', 'general')
        sector_weights = self.sectors.get(sector, self.sectors.get('general', {}))

        score = 0.0
        breakdown = {}

        # 技術面
        tech_score = self._calc_technical(stock_data)
        score += tech_score * sector_weights.get('technical', 0.45)
        breakdown['技術面'] = round(tech_score * sector_weights.get('technical', 0.45) * 100, 1)

        # 量能
        vol_score = self._calc_volume(stock_data)
        score += vol_score * sector_weights.get('volume', 0.15)
        breakdown['量能'] = round(vol_score * sector_weights.get('volume', 0.15) * 100, 1)

        # 動能
        mom_score = self._calc_momentum(stock_data)
        score += mom_score * sector_weights.get('momentum', 0.10)
        breakdown['動能'] = round(mom_score * sector_weights.get('momentum', 0.10) * 100, 1)

        # BDI
        bdi_score = self._calc_bdi(stock_data)
        score += bdi_score * sector_weights.get('bdi', 0.12)
        breakdown['BDI'] = round(bdi_score * sector_weights.get('bdi', 0.12) * 100, 1)

        # 外資
        foreign_score = self._calc_foreign(stock_data)
        score += foreign_score * sector_weights.get('foreign', 0.18)
        breakdown['外資'] = round(foreign_score * sector_weights.get('foreign', 0.18) * 100, 1)

        # 罰則調整
        penalty = self._apply_adjustments(stock_data)
        final_score = max(
            self.global_settings.get('min_confidence', 30),
            min(100, round(score * (1 + penalty)))
        )

        return final_score, {
            'total': final_score,
            'sector': sector,
            'breakdown': breakdown,
            'penalty': round(penalty * 100, 1),
            'signal': self._get_signal(final_score)
        }

    # ====================== 各項計算函式 ======================
    def _calc_technical(self, data: Dict) -> float:
        score = 0.0
        if data.get('price', 0) > data.get('ma20', 0): score += 0.4
        if data.get('ma20', 0) > data.get('ma50', 0): score += 0.35
        rsi = data.get('rsi', 50)
        low = self.adjustments.get('rsi', {}).get('golden_zone_low', 40)
        high = self.adjustments.get('rsi', {}).get('golden_zone_high', 65)
        if low <= rsi <= high:
            score += 0.25
        elif 30 <= rsi < 70:
            score += 0.15
        return min(1.0, score)

    def _calc_volume(self, data: Dict) -> float:
        ratio = data.get('volume_ratio', 1.0)
        if ratio >= 1.5: return 1.0
        elif ratio >= 1.1: return 0.75
        elif ratio >= 0.7: return 0.5
        return 0.3

    def _calc_momentum(self, data: Dict) -> float:
        return 1.0 if data.get('macd_hist', 0) > 0 else 0.4

    def _calc_bdi(self, data: Dict) -> float:
        change = data.get('bdi_change_pct', 0)
        if change > 2.0: return 1.0
        elif change > 0: return 0.75
        elif change > -3: return 0.5
        return 0.3

    def _calc_foreign(self, data: Dict) -> float:
        return min(1.0, max(0.0, data.get('foreign_strength', 0.5)))

    def _apply_adjustments(self, data: Dict) -> float:
        rsi = data.get('rsi', 50)
        rsi_config = self.adjustments.get('rsi', {})
        if rsi > 72:
            return rsi_config.get('overbought_72', -0.18)
        elif rsi > 68:
            return rsi_config.get('overbought_68', -0.12)
        elif rsi < 30:
            return rsi_config.get('oversold_30', -0.15)
        return 0.0

    def _get_signal(self, score: int) -> str:
        thresholds = self.adjustments.get('score_thresholds', {})
        if score >= thresholds.get('strong_buy', 75):
            return self.signals.get('strong_buy', '強烈買入')
        elif score >= thresholds.get('buy', 65):
            return self.signals.get('buy', '建議買入')
        elif score >= thresholds.get('hold', 50):
            return self.signals.get('hold', '觀望')
        return self.signals.get('neutral', '暫不進場')
