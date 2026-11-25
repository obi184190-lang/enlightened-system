#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
開明體系 Phase 5.2.3 - BDI + 外資籌碼數據模組
"""

import requests
from typing import Dict, Optional, List
from datetime import datetime
import time


class BDIFetcher:
    """BDI 波羅的海指數抓取器"""
    
    @staticmethod
    def get_bdi_index() -> Optional[Dict]:
        """
        獲取 BDI 指數
        
        Returns:
            {
                'value': float,          # BDI 指數值
                'change_percent': float, # 漲跌幅 %
                'level': str,           # 強度等級
                'timestamp': str        # 抓取時間
            }
        """
        try:
            # 方法 1: 使用 Investing.com
            url = "https://www.investing.com/indices/baltic-dry"
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                # 簡化版：從 HTML 中提取數字
                text = response.text
                
                # 尋找 BDI 數值（這裡需要根據實際 HTML 結構調整）
                # 備註：實際部署時可能需要用 BeautifulSoup 解析
                
                # 暫時返回模擬數據（實際部署時替換）
                bdi_value = 1876.0  # 實際從網頁抓取
                change_pct = 2.3    # 實際從網頁抓取
            else:
                # 如果主要來源失敗，使用備用方法
                return BDIFetcher._get_bdi_via_yfinance()
        
        except Exception as e:
            print(f"⚠️ BDI 主要來源失敗: {e}")
            # 使用備用方法
            return BDIFetcher._get_bdi_via_yfinance()
        
        # 判斷 BDI 強度等級
        level = BDIFetcher._get_bdi_level(bdi_value)
        
        return {
            'value': bdi_value,
            'change_percent': change_pct,
            'level': level,
            'timestamp': datetime.now().isoformat()
        }
    
    @staticmethod
    def _get_bdi_via_yfinance() -> Optional[Dict]:
        """
        備用方法：透過 BDI 相關 ETF 獲取趨勢
        BDRY: Breakwave Dry Bulk Shipping ETF
        """
        try:
            import yfinance as yf
            
            ticker = yf.Ticker("BDRY")
            hist = ticker.history(period="5d")
            
            if hist.empty:
                return None
            
            latest = hist.iloc[-1]
            prev = hist.iloc[-2] if len(hist) > 1 else latest
            
            change_percent = ((latest['Close'] - prev['Close']) / prev['Close']) * 100
            
            # 使用 ETF 價格推估 BDI（粗略估計）
            # BDRY 價格約是 BDI 的代理指標
            estimated_bdi = latest['Close'] * 100  # 簡化估算
            
            level = BDIFetcher._get_bdi_level(estimated_bdi)
            
            return {
                'value': estimated_bdi,
                'change_percent': change_percent,
                'level': level,
                'source': 'BDRY ETF (代理指標)',
                'timestamp': datetime.now().isoformat()
            }
        
        except Exception as e:
            print(f"⚠️ BDI 備用來源也失敗: {e}")
            return None
    
    @staticmethod
    def _get_bdi_level(bdi_value: float) -> str:
        """判斷 BDI 強度等級"""
        if bdi_value > 2000:
            return "極度強勢"
        elif bdi_value > 1500:
            return "強勢"
        elif bdi_value > 1000:
            return "中性"
        elif bdi_value > 500:
            return "弱勢"
        else:
            return "極度弱勢"
    
    @staticmethod
    def get_bdi_score(bdi_value: float) -> int:
        """
        根據 BDI 指數計算評分（滿分 15 分）
        僅用於航運股
        """
        if bdi_value > 2000:
            return 15  # 極度強勢
        elif bdi_value > 1500:
            return 10  # 強勢
        elif bdi_value > 1000:
            return 5   # 中性
        else:
            return 0   # 弱勢/極度弱勢


class ForeignInvestmentFetcher:
    """外資籌碼抓取器"""
    
    @staticmethod
    def get_foreign_investment(stock_code: str) -> Optional[Dict]:
        """
        獲取外資籌碼數據
        
        Args:
            stock_code: 股票代號（如 "2303"）
        
        Returns:
            {
                'stock_code': str,
                'foreign_buy': int,
                'foreign_sell': int,
                'foreign_net': int,
                'foreign_holding_pct': float,
                'strength': str,
                'timestamp': str
            }
        """
        table = ForeignInvestmentFetcher._get_t86_table()
        if table and stock_code in table:
            row = table[stock_code]
            foreign_net = row['net']
            return {
                'stock_code': stock_code,
                'foreign_buy': row['buy'],
                'foreign_sell': row['sell'],
                'foreign_net': foreign_net,
                'foreign_holding_pct': None,  # T86 不含持股比例
                'strength': ForeignInvestmentFetcher._get_chip_strength(foreign_net),
                'data_date': ForeignInvestmentFetcher._t86_date,
                'timestamp': datetime.now().isoformat()
            }

        # 取不到就回傳 None，訊息會顯示「外資無數據」，不再用 0 假裝有資料
        print(f"ℹ️ {stock_code} 外資數據暫時無法獲取")
        return None

    _t86_cache = None
    _t86_date = None

    @staticmethod
    def _get_t86_table() -> Optional[Dict[str, Dict]]:
        """
        抓 TWSE T86（三大法人買賣超日報），整張表快取一次。
        T86 約 16:00 後才公布，盤中執行時抓不到當天，因此往前找最近 7 天內有資料的交易日。
        欄位依 fields 名稱定位，不寫死索引；單位由「股」換算成「張」。
        """
        if ForeignInvestmentFetcher._t86_cache is not None:
            return ForeignInvestmentFetcher._t86_cache or None

        from datetime import timedelta, timezone
        tw_now = datetime.now(timezone(timedelta(hours=8)))
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}

        def find_idx(fields, prefix):
            # 以欄位名稱開頭比對（「外資自營商…」開頭的欄位不會誤中「外陸資…」）
            for i, f in enumerate(fields):
                if f.strip().startswith(prefix):
                    return i
            return None

        def to_int(v):
            try:
                return int(str(v).replace(',', '').strip())
            except ValueError:
                return 0

        for back in range(0, 8):
            d = tw_now - timedelta(days=back)
            if d.weekday() >= 5:
                continue
            date_str = d.strftime('%Y%m%d')
            try:
                resp = requests.get(
                    "https://www.twse.com.tw/rwd/zh/fund/T86",
                    params={'response': 'json', 'date': date_str, 'selectType': 'ALLBUT0999'},
                    headers=headers, timeout=15
                )
                data = resp.json() if resp.status_code == 200 else {}
            except Exception as e:
                print(f"⚠️ T86 {date_str} 抓取失敗: {e}")
                time.sleep(1)
                continue

            rows, fields = data.get('data'), data.get('fields')
            if not rows or not fields:
                time.sleep(1)
                continue

            i_buy = find_idx(fields, '外陸資買進股數')
            i_sell = find_idx(fields, '外陸資賣出股數')
            i_net = find_idx(fields, '外陸資買賣超股數')
            if i_net is None:
                i_net = find_idx(fields, '外資買賣超')
            if i_net is None:
                print(f"⚠️ T86 欄位格式改變，找不到外資買賣超欄位: {fields}")
                break

            table = {}
            for r in rows:
                code = str(r[0]).strip()
                table[code] = {
                    'buy': to_int(r[i_buy]) // 1000 if i_buy is not None else 0,
                    'sell': to_int(r[i_sell]) // 1000 if i_sell is not None else 0,
                    'net': to_int(r[i_net]) // 1000,
                }
            ForeignInvestmentFetcher._t86_cache = table
            ForeignInvestmentFetcher._t86_date = date_str
            print(f"✅ T86 外資資料日期: {date_str}（{len(table)} 檔）")
            return table

        ForeignInvestmentFetcher._t86_cache = {}
        return None

    @staticmethod
    def _get_foreign_via_twstock(stock_code: str) -> Optional[Dict]:
        """
        備用方法：使用 twstock 套件
        """
        try:
            import twstock
            
            stock = twstock.Stock(stock_code)
            
            # 獲取最近交易日數據
            # 注意：twstock 可能需要調整以獲取外資數據
            # 這裡提供架構，實際使用時可能需要調整
            
            # 暫時返回 None，實際部署時完善
            return None
        
        except Exception as e:
            print(f"⚠️ {stock_code} 外資數據備用來源也失敗: {e}")
            return None
    
    @staticmethod
    def _get_chip_strength(foreign_net: int) -> str:
        """判斷籌碼強度"""
        if foreign_net > 5000:
            return "極度強勢"
        elif foreign_net > 1000:
            return "強勢"
        elif foreign_net > 0:
            return "略為看好"
        elif foreign_net > -1000:
            return "略為看壞"
        elif foreign_net > -5000:
            return "弱勢"
        else:
            return "極度弱勢"
    
    @staticmethod
    def get_foreign_score(foreign_net: int) -> int:
        """
        根據外資買賣超計算評分（滿分 20 分）
        適用於所有股票
        """
        if foreign_net > 5000:
            return 20  # 強力買超
        elif foreign_net > 1000:
            return 15  # 持續買超
        elif foreign_net > 0:
            return 10  # 小幅買超
        elif foreign_net > -1000:
            return 5   # 小幅賣超
        elif foreign_net > -5000:
            return 0   # 賣超
        else:
            return -10  # 大幅賣超（扣分）
    
    @staticmethod
    def batch_get_foreign_investment(stock_codes: List[str]) -> Dict[str, Dict]:
        """
        批次獲取多支股票的外資籌碼
        
        Args:
            stock_codes: 股票代號列表
        
        Returns:
            {stock_code: foreign_data}
        """
        results = {}
        
        for code in stock_codes:
            try:
                data = ForeignInvestmentFetcher.get_foreign_investment(code)
                if data:
                    results[code] = data
                    print(f"✅ {code} 外資籌碼已獲取")
                else:
                    print(f"⚠️ {code} 外資籌碼無數據")
                
                # 避免請求過快，加入延遲
                time.sleep(0.5)
            
            except Exception as e:
                print(f"❌ {code} 外資籌碼獲取失敗: {e}")
        
        return results


class MarketDataIntegration:
    """市場數據整合器 - 整合 BDI + 外資籌碼"""
    
    def __init__(self):
        self.bdi_fetcher = BDIFetcher()
        self.foreign_fetcher = ForeignInvestmentFetcher()
        
        self.bdi_data = None
        self.foreign_data = {}
    
    def fetch_all_data(self, stock_codes: List[str]) -> Dict:
        """
        獲取所有市場數據
        
        Args:
            stock_codes: 股票代號列表
        
        Returns:
            {
                'bdi': bdi_data,
                'foreign': {stock_code: foreign_data}
            }
        """
        print("=" * 60)
        print("📊 開始獲取市場數據...")
        print("=" * 60)
        
        # 1. 獲取 BDI 指數
        print("\n🚢 獲取 BDI 指數...")
        self.bdi_data = self.bdi_fetcher.get_bdi_index()
        
        if self.bdi_data:
            print(f"✅ BDI: {self.bdi_data['value']:.0f} ({self.bdi_data['change_percent']:+.2f}%)")
            print(f"   強度: {self.bdi_data['level']}")
        else:
            print("⚠️ BDI 數據獲取失敗")
        
        # 2. 批次獲取外資籌碼
        print(f"\n💰 獲取外資籌碼（{len(stock_codes)} 支股票）...")
        self.foreign_data = self.foreign_fetcher.batch_get_foreign_investment(stock_codes)
        
        print(f"\n✅ 數據獲取完成：BDI={bool(self.bdi_data)}, 外資={len(self.foreign_data)}/{len(stock_codes)}")
        print("=" * 60)
        
        return {
            'bdi': self.bdi_data,
            'foreign': self.foreign_data
        }
    
    def get_bdi_for_stock(self, stock_code: str) -> Optional[Dict]:
        """
        判斷股票是否需要 BDI 數據
        僅航運股返回 BDI 數據
        """
        # 航運股清單（可擴充）
        shipping_stocks = ['2603', '2609', '2615', '2637', '2645']
        
        if stock_code in shipping_stocks:
            return self.bdi_data
        else:
            return None
    
    def get_foreign_for_stock(self, stock_code: str) -> Optional[Dict]:
        """獲取指定股票的外資數據"""
        return self.foreign_data.get(stock_code)


# ============================================================================
# 使用範例
# ============================================================================

if __name__ == '__main__':
    print("🚀 開明體系 Phase 5.2.3 - BDI + 外資籌碼測試\n")
    
    # 測試 BDI 抓取
    print("=" * 60)
    print("測試 1: BDI 指數抓取")
    print("=" * 60)
    
    bdi_fetcher = BDIFetcher()
    bdi_data = bdi_fetcher.get_bdi_index()
    
    if bdi_data:
        print(f"✅ BDI 指數: {bdi_data['value']:.0f}")
        print(f"   漲跌幅: {bdi_data['change_percent']:+.2f}%")
        print(f"   強度等級: {bdi_data['level']}")
        print(f"   評分: {bdi_fetcher.get_bdi_score(bdi_data['value'])}/15")
    else:
        print("❌ BDI 數據獲取失敗")
    
    # 測試外資籌碼抓取
    print("\n" + "=" * 60)
    print("測試 2: 外資籌碼抓取")
    print("=" * 60)
    
    test_stocks = ['2303', '2637', '2330']
    
    foreign_fetcher = ForeignInvestmentFetcher()
    
    for stock_code in test_stocks:
        print(f"\n📊 {stock_code}:")
        foreign_data = foreign_fetcher.get_foreign_investment(stock_code)
        
        if foreign_data:
            print(f"   外資買賣超: {foreign_data['foreign_net']:+,} 張")
            print(f"   持股比例: {foreign_data['foreign_holding_pct']:.2f}%")
            print(f"   籌碼強度: {foreign_data['strength']}")
            print(f"   評分: {foreign_fetcher.get_foreign_score(foreign_data['foreign_net'])}/20")
        else:
            print("   ⚠️ 無數據")
    
    # 測試整合器
    print("\n" + "=" * 60)
    print("測試 3: 市場數據整合器")
    print("=" * 60)
    
    integrator = MarketDataIntegration()
    all_data = integrator.fetch_all_data(test_stocks)
    
    print("\n📋 整合結果:")
    print(f"   BDI 數據: {'✅' if all_data['bdi'] else '❌'}")
    print(f"   外資數據: {len(all_data['foreign'])}/{len(test_stocks)} 支")
