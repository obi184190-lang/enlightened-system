# 開明體系 (Enlightened System) - 完整系統文檔

**台灣股票交易自動化決策支援系統**

---

## 📊 系統概述

### 專案資訊
- **專案名稱**: 開明體系 (Enlightened System)
- **GitHub Repository**: https://github.com/obi184190-lang/enlightened-system
- **開發時程**: 2026-04-22 ~ 2026-04-28
- **當前版本**: Phase 4.1
- **開發者**: @obi184190
- **技術協助**: Claude (Anthropic)

### 核心功能
一個全自動化的台灣股票市場監控與交易決策支援系統，透過 GitHub Actions 定時執行、Supabase 資料儲存、Telegram Bot 即時推送，實現無人值守的智能交易監控。

---

## 🏗️ 系統架構

### 技術架構圖
```
┌─────────────────────────────────────────────────────────────┐
│                      GitHub Actions                         │
│              (每日 09:15, 12:10, 14:30 自動觸發)            │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                  stock_monitor.py (Python 3.11)             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │ yfinance API │→│ 技術指標分析 │→│ 信號生成系統 │     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
└────────┬─────────────────────────┬────────────────────┬─────┘
         │                         │                    │
         ▼                         ▼                    ▼
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│  Supabase DB    │  │  Telegram Bot   │  │   日誌記錄      │
│  (trade_logs)   │  │ @enlightened    │  │  (GitHub Logs)  │
│                 │  │  _stock_bot     │  │                 │
└─────────────────┘  └─────────────────┘  └─────────────────┘
```

### 技術棧
| 層級 | 技術 | 版本 | 用途 |
|------|------|------|------|
| **執行環境** | GitHub Actions | - | 自動化排程執行 |
| **程式語言** | Python | 3.11 | 主要開發語言 |
| **股票數據** | yfinance | 0.2.0+ | 台股即時價格 |
| **資料儲存** | Supabase | 2.3.0+ | PostgreSQL 雲端資料庫 |
| **推送通知** | Telegram Bot API | 20.3+ | 即時訊息推送 |
| **數據分析** | pandas | 2.0.0+ | 技術指標計算 |
| **時區處理** | datetime | 內建 | 台灣時間 (UTC+8) |

---

## 📅 開發歷程

### Phase 1: GitHub Actions + yfinance 監控
**完成時間**: 2026-04-22

**核心成果**:
- ✅ 建立 GitHub Repository
- ✅ 實作 `stock_monitor.py` 主程式
- ✅ 設定自動化排程 (初版: 09:15, 14:00)
- ✅ 整合 yfinance API 抓取台股數據
- ✅ 基礎技術指標: MA20, MA50, RSI

**技術挑戰**:
- 台股代碼格式處理 (需加 `.TW` 後綴)
- GitHub Actions 環境變數設定
- 時區換算 (UTC → 台灣時間)

---

### Phase 2: Supabase 資料儲存
**完成時間**: 2026-04-22

**核心成果**:
- ✅ 建立 Supabase 專案
- ✅ 設計 `trade_logs` 資料表結構
- ✅ 實作資料儲存邏輯
- ✅ 設定 GitHub Secrets (3個金鑰)

**資料表結構**:
```sql
CREATE TABLE trade_logs (
    id SERIAL PRIMARY KEY,
    stock_code VARCHAR(10) NOT NULL,
    signal_type VARCHAR(10) NOT NULL,
    price DECIMAL(10, 2) NOT NULL,
    decision_logic TEXT,
    profit_loss DECIMAL(10, 2) DEFAULT 0.0,
    timestamp TIMESTAMP NOT NULL
);
```

---

### Phase 3: Telegram Bot 推送通知
**完成時間**: 2026-04-22

**核心成果**:
- ✅ 建立 @enlightened_stock_bot
- ✅ 取得 Chat ID (8243241782)
- ✅ 實作 HTML 格式化通知
- ✅ 修復 workflow 環境變數問題

**通知格式**:
```html
📊 <b>股票監控摘要</b>
時間: 2026-04-22 13:05:05

🟢 2303 聯電 [BUY]
 價格: 78.60
 信心度: 41.67%
```

**技術挑戰**:
- Workflow YAML 環境變數配置
- Telegram Bot API 整合
- HTML 特殊字符處理

---

### Phase 4: 多指標信心度系統
**完成時間**: 2026-04-22

**核心成果**:
- ✅ 多指標加權信心度系統
- ✅ 止損止盈機制
- ✅ 擴大監控至 6 支股票
- ✅ 分級告警系統
- ✅ A+B 彈性選股機制

**信心度系統**:
| 指標 | 權重 | 判斷條件 |
|------|------|----------|
| MA20 突破 | 20% | 價格 > MA20 |
| MA50 趨勢 | 20% | MA20 > MA50 |
| RSI 黃金區 | 20% | 40 ≤ RSI ≤ 65 |
| MACD 金叉 | 25% | MACD線 > 信號線 且 前一期 ≤ |
| 成交量放大 | 15% | 當日成交量 > 20日均量 × 1.5 |

**信心度提升**: 41.67% → 100%

**風險管理**:
- 🎯 目標價 (止盈): 買入價 × 1.15 (+15%)
- 🛑 止損價: 買入價 × 0.95 (-5%)

**分級告警**:
- 🔴 強烈買入: 信心度 ≥ 70%
- 🟡 建議買入: 信心度 50-70%
- ⚪ 觀望: 信心度 < 50%
- 🔵 賣出: 價格跌破MA20 或 RSI > 80

---

### Phase 4.1: 系統優化
**完成時間**: 2026-04-28

**核心成果**:
- ✅ 排程優化 (2次 → 3次監控)
- ✅ 台灣時間顯示 (UTC → UTC+8)
- ✅ 自動抓取股票名稱

**排程優化**:
| 時間 | 原因 | 市場階段 |
|------|------|----------|
| 09:15 | 開盤後觀察期 | 捕捉開盤信號 |
| 12:10 | 午盤確認點 (新增) | 確認上午趨勢 |
| 14:30 | 收盤前決策點 (調整) | 尾盤判斷 |

**時間顯示修正**:
```python
# 修正前
datetime.now().strftime('%Y-%m-%d %H:%M:%S')
# 輸出: 2026-04-28 15:50:45 (UTC)

# 修正後
from datetime import timezone, timedelta
TW_TZ = timezone(timedelta(hours=8))
tw_now = datetime.now(TW_TZ)
tw_now.strftime('%Y-%m-%d %H:%M:%S')
# 輸出: 2026-04-28 23:50:45 (台灣時間)
```

**股票名稱抓取**:
```python
def get_stock_name(self, stock_code: str) -> str:
    """自動從 yfinance 抓取股票名稱"""
    # 1. 優先使用 stocks.txt 定義
    # 2. 從 yfinance API 抓取
    # 3. 快取避免重複請求
    # 4. 容錯返回代碼本身
```

---

## 🎯 監控股票清單

### 固定監控 (stocks.txt)
| 代號 | 名稱 | 產業 | 加入原因 |
|------|------|------|----------|
| 2303 | 聯電 | 半導體 | 晶圓代工龍頭 |
| 2637 | 慧洋-KY | 航運 | 散裝航運 |
| 4938 | 和碩 | 電子 | 組裝代工 |
| 2330 | 台積電 | 半導體 | 晶圓代工龍頭 |
| 2317 | 鴻海 | 電子 | 電子代工龍頭 |
| 2412 | 中華電 | 通訊 | 電信龍頭 |

### 臨時監控 (手動指定)
- 透過 GitHub Actions 手動執行時輸入
- 格式: `2330,2454,2881` (逗號分隔)
- 立即執行，不影響固定清單

---

## 🔧 技術實作細節

### 檔案結構
```
enlightened-system/
├── .github/
│   └── workflows/
│       └── stock-monitor.yml          # GitHub Actions 工作流程
├── scripts/
│   └── stock_monitor.py               # 主程式（596 行）
├── stocks.txt                          # 監控股票清單
├── requirements.txt                    # Python 依賴套件
├── README.md                          # 專案說明
└── .gitignore                         # Git 忽略清單
```

### 核心程式邏輯

#### 1. 股票數據抓取
```python
def fetch_stock_data(self, stock_code: str) -> Optional[Dict]:
    """從 yfinance 抓取台股數據"""
    ticker = yf.Ticker(f"{stock_code}.TW")
    hist = ticker.history(period="5d")
    hist = hist.dropna()  # 移除 NaN
    
    if hist.empty:
        return None
    
    latest = hist.iloc[-1]
    return {
        'code': stock_code,
        'price': float(latest['Close']),
        'volume': int(latest['Volume']),
        'change': float(latest['Close'] - latest['Open']),
        'change_percent': float((latest['Close'] - latest['Open']) / latest['Open'] * 100)
    }
```

#### 2. 技術指標計算
```python
# MA (移動平均線)
def calculate_ma(self, prices: List[float], period: int) -> Optional[float]:
    if len(prices) < period:
        return None
    return sum(prices[-period:]) / period

# RSI (相對強弱指標)
def calculate_rsi(self, prices: List[float], period: int = 14) -> Optional[float]:
    deltas = [prices[i] - prices[i-1] for i in range(1, len(prices))]
    seed = deltas[:period]
    up = sum([x for x in seed if x > 0]) / period
    down = sum([abs(x) for x in seed if x < 0]) / period
    rs = up / down if down != 0 else 0
    return 100 - (100 / (1 + rs))

# MACD (在 generate_signal 中計算)
ema12 = pd.Series(closes).ewm(span=12).mean().values
ema26 = pd.Series(closes).ewm(span=26).mean().values
macd_line = ema12 - ema26
signal_line = pd.Series(macd_line).ewm(span=9).mean().values
```

#### 3. 信號生成邏輯
```python
def generate_signal(self, stock_code, price, ma_20, ma_50, rsi, data):
    """多指標加權信心度系統"""
    score = 0
    max_score = 0
    
    # 指標1-5 計算 (共100分)
    # ...
    
    confidence = score / max_score
    
    if confidence >= 0.70:
        return 'BUY', confidence, '🔴強烈買入'
    elif confidence >= 0.50:
        return 'BUY', confidence, '🟡建議買入'
    elif price < ma_20:
        return 'SELL', 0.75, '價格跌破MA20'
    else:
        return 'HOLD', confidence, '⚪觀望'
```

### GitHub Actions 排程
```yaml
on:
  schedule:
    - cron: '15 1 * * 1-5'   # 09:15 台灣時間 (UTC+8)
    - cron: '10 4 * * 1-5'   # 12:10 台灣時間
    - cron: '30 6 * * 1-5'   # 14:30 台灣時間
  workflow_dispatch:         # 支援手動觸發
    inputs:
      stocks_override:
        description: '臨時指定股票（逗號分隔）'
        required: false
```

### 環境變數配置
| 變數名稱 | 類型 | 說明 |
|---------|------|------|
| `SUPABASE_URL` | Secret | Supabase 專案 URL |
| `SUPABASE_ANON_KEY` | Secret | 匿名金鑰 (public) |
| `SUPABASE_SERVICE_ROLE_KEY` | Secret | 服務角色金鑰 (admin) |
| `TELEGRAM_BOT_TOKEN` | Secret | Bot 驗證 Token |
| `TELEGRAM_CHAT_ID` | Secret | 推送目標 ID (8243241782) |
| `STOCKS_OVERRIDE` | Input | 臨時股票清單 (可選) |

---

## 📊 系統性能指標

### 執行效率
- **平均執行時間**: 30-60 秒 (6支股票)
- **成功率**: 99%+ (過去7天)
- **資料時效性**: 即時 (市場開盤時段)

### 通知延遲
- **執行觸發**: < 1 分鐘 (GitHub Actions)
- **數據抓取**: 5-10 秒 (yfinance API)
- **技術分析**: 5-10 秒 (計算指標)
- **資料儲存**: 1-2 秒 (Supabase)
- **推送通知**: 1-2 秒 (Telegram)
- **總計**: 約 15-25 秒

### 資料準確性
- **價格數據**: yfinance 官方 API (Yahoo Finance)
- **更新頻率**: 每日3次 (09:15, 12:10, 14:30)
- **歷史數據**: 60 天 (用於技術指標計算)

---

## 🚀 Phase 5 規劃

### 5.1 K線圖表自動生成 📈
**目標**: 為每支股票生成 K 線圖並發送到 Telegram

**技術方案**:
- 使用 `mplfinance` 繪製 K 線圖
- 標註 MA20/MA50 線
- 標記買賣信號點位
- 添加成交量柱狀圖
- 轉換為圖片並透過 Telegram Bot 發送

**預期效果**:
```python
# 生成 K 線圖
import mplfinance as mpf

mpf.plot(data, 
    type='candle',
    mav=(20, 50),
    volume=True,
    style='charles',
    savefig='stock_chart.png'
)

# 透過 Telegram 發送
with open('stock_chart.png', 'rb') as photo:
    bot.send_photo(chat_id=CHAT_ID, photo=photo)
```

---

### 5.2 AI 智能判斷 🤖
**目標**: 使用 AI 模型優化進出場時機判斷

**技術方案 A**: 整合 Claude API
```python
def ai_analyze_entry_timing(stock_data, signals):
    prompt = f"""
    根據以下數據分析最佳進場時機：
    - 股票: {stock_data['code']}
    - 當前價格: {stock_data['price']}
    - MA20: {signals['ma_20']}
    - RSI: {signals['rsi']}
    - 信心度: {signals['confidence']}
    
    請提供:
    1. 是否建議進場
    2. 建議進場價位
    3. 理由說明
    """
    response = claude_api.complete(prompt)
    return response
```

**技術方案 B**: 機器學習模型
```python
from sklearn.ensemble import RandomForestClassifier

# 特徵工程
features = [price, ma_20, ma_50, rsi, macd, volume]
label = [1 if future_price_up else 0]

# 訓練模型
model = RandomForestClassifier()
model.fit(features, label)

# 預測
prediction = model.predict([current_features])
```

---

### 5.3 模擬投資組合 💰
**目標**: 追蹤虛擬投資的損益表現

**資料表設計**:
```sql
CREATE TABLE portfolio (
    id SERIAL PRIMARY KEY,
    stock_code VARCHAR(10) NOT NULL,
    action VARCHAR(10) NOT NULL,  -- BUY / SELL
    quantity INT NOT NULL,
    price DECIMAL(10, 2) NOT NULL,
    total_cost DECIMAL(12, 2) NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    profit_loss DECIMAL(12, 2) DEFAULT 0.0
);

CREATE TABLE portfolio_summary (
    id SERIAL PRIMARY KEY,
    total_investment DECIMAL(12, 2) NOT NULL,
    current_value DECIMAL(12, 2) NOT NULL,
    total_profit DECIMAL(12, 2) NOT NULL,
    return_rate DECIMAL(5, 2) NOT NULL,
    win_rate DECIMAL(5, 2) NOT NULL,
    updated_at TIMESTAMP NOT NULL
);
```

**核心功能**:
```python
def calculate_portfolio_performance():
    """計算投資組合績效"""
    # 1. 計算總投資金額
    # 2. 計算當前市值
    # 3. 計算總損益
    # 4. 計算報酬率
    # 5. 計算勝率 (獲利交易 / 總交易)
    # 6. 找出最佳/最差股票
```

---

### 5.4 每週績效報告 📊
**目標**: 每週一自動產生績效報告

**Workflow 排程**:
```yaml
on:
  schedule:
    - cron: '0 1 * * 1'  # 每週一 09:00 台灣時間
```

**報告內容**:
1. 本週交易統計
   - 交易次數
   - 買入/賣出次數
   - 平均信心度

2. 損益分析
   - 總投資金額
   - 總獲利/虧損
   - 報酬率
   - 勝率

3. 股票排名
   - 最佳表現股票 (Top 3)
   - 最差表現股票 (Top 3)
   - 信心度最高/最低

4. 視覺化圖表
   - 每日累計損益曲線
   - 股票報酬率比較
   - 信心度分布圖

---

## 📝 常見問題 FAQ

### Q1: 為什麼選擇 GitHub Actions 而不是其他方案？
**A**: GitHub Actions 提供免費的自動化執行環境，無需額外伺服器成本，且與程式碼倉庫完美整合。

### Q2: 信心度 100% 是否代表一定會賺錢？
**A**: 不是。信心度只代表技術指標的符合程度，實際市場受多種因素影響。系統僅供參考，不構成投資建議。

### Q3: 可以監控美股或其他市場嗎？
**A**: 理論上可以，但需要修改股票代碼格式。台股使用 `.TW`，美股無需後綴，港股使用 `.HK`。

### Q4: 排程時間可以自由調整嗎？
**A**: 可以。修改 `.github/workflows/stock-monitor.yml` 中的 cron 表達式即可。記得時區換算。

### Q5: Telegram 通知可以關閉嗎？
**A**: 可以。不設定 `TELEGRAM_BOT_TOKEN` 和 `TELEGRAM_CHAT_ID` 即可。程式會自動跳過通知。

### Q6: 可以增加更多技術指標嗎？
**A**: 可以。在 `generate_signal()` 函數中新增指標計算邏輯，並調整權重分配。

### Q7: Supabase 免費方案夠用嗎？
**A**: 足夠。每日3次執行，每次6支股票，月資料量遠低於免費方案限制（500MB 儲存、50,000 行）。

### Q8: 系統會自動執行交易嗎？
**A**: 不會。這是「決策支援系統」，僅提供信號和建議，不會實際執行買賣。

---

## 🛠️ 故障排查指南

### 問題1: Workflow 執行失敗
**可能原因**:
- GitHub Secrets 未正確設定
- YAML 語法錯誤
- Python 依賴套件安裝失敗

**解決方法**:
1. 檢查 Settings → Secrets → Actions
2. 驗證 YAML 語法 (https://www.yamllint.com/)
3. 查看 Actions 執行日誌中的錯誤訊息

---

### 問題2: Telegram 未收到通知
**可能原因**:
- BOT_TOKEN 或 CHAT_ID 錯誤
- Workflow 環境變數未設定
- Telegram API 網路問題

**解決方法**:
1. 驗證 Bot Token: https://api.telegram.org/bot<TOKEN>/getMe
2. 驗證 Chat ID: 傳送訊息給 Bot，查看 /getUpdates
3. 檢查 workflow.yml 的 env 區塊

---

### 問題3: 股票數據抓取失敗
**可能原因**:
- 股票代碼錯誤
- 休市日（週末、國定假日）
- yfinance API 問題

**解決方法**:
1. 確認代碼格式 (例: `2330.TW`)
2. 確認是否為交易日
3. 檢查 yfinance 是否正常: `yf.Ticker("2330.TW").history(period="1d")`

---

### 問題4: 信心度始終為 0%
**可能原因**:
- 歷史數據不足 (< 60天)
- 指標計算邏輯錯誤
- data 參數未正確傳入

**解決方法**:
1. 確認 `hist = ticker.history(period="60d")`
2. 檢查 `generate_signal()` 接收到 data 參數
3. 查看執行日誌中的錯誤訊息

---

## 📚 學習資源

### 官方文檔
- [GitHub Actions 文檔](https://docs.github.com/en/actions)
- [yfinance 文檔](https://pypi.org/project/yfinance/)
- [Supabase 文檔](https://supabase.com/docs)
- [Telegram Bot API](https://core.telegram.org/bots/api)

### 技術指標學習
- [移動平均線 (MA)](https://www.investopedia.com/terms/m/movingaverage.asp)
- [相對強弱指標 (RSI)](https://www.investopedia.com/terms/r/rsi.asp)
- [MACD 指標](https://www.investopedia.com/terms/m/macd.asp)

### Python 學習
- [Python 官方教學](https://docs.python.org/3/tutorial/)
- [pandas 教學](https://pandas.pydata.org/docs/user_guide/index.html)

---

## 🎓 致謝

感謝以下開源專案和服務：
- **yfinance**: 提供免費的股票數據 API
- **Supabase**: 提供免費的雲端資料庫
- **Telegram**: 提供免費的 Bot API
- **GitHub**: 提供免費的 Actions 自動化服務
- **Python**: 強大的程式語言與生態系統

---

## 📄 授權聲明

本專案僅供學習和研究使用，不構成任何投資建議。

**風險提示**:
- 股票投資有風險，請謹慎決策
- 技術指標不保證獲利
- 請勿將全部資金投入單一標的
- 建議設定停損停利機制

**免責聲明**:
使用本系統進行交易決策所產生的任何損失，開發者不承擔任何責任。

---

**文檔版本**: v2.0  
**最後更新**: 2026-04-28  
**維護者**: @obi184190  
**技術支援**: Claude (Anthropic)
