# OBS Setup Guide for DJ Sources

## Tạo Browser Sources trong OBS

Dựa trên `dj_sources_config.json`, bạn cần tạo các Browser Source trong OBS như sau:

### Scene: `Scene-Music-Location1`
Tạo 3 Browser Sources:

1. **Source Name: `dj_01`**
   - Type: Browser
   - URL: `https://s.tradingview.com/widgetembed/?symbol=BINANCE:BTCUSDT`
   - Width: 1920, Height: 1080
   - Visibility: Hidden (sẽ được toggle bởi script)

2. **Source Name: `dj_02`**
   - Type: Browser
   - URL: `https://s.tradingview.com/widgetembed/?symbol=BINANCE:ETHUSDT`
   - Width: 1920, Height: 1080
   - Visibility: Hidden

3. **Source Name: `dj_03`**
   - Type: Browser
   - URL: `https://whale-alert.io/transactions`
   - Width: 1920, Height: 1080
   - Visibility: Hidden

### Scene: `Scene-Music-Location2`
Tạo 2 Browser Sources:

4. **Source Name: `dj_04`**
   - Type: Browser
   - URL: `https://arkhamintelligence.com/explorer`
   - Width: 1920, Height: 1080
   - Visibility: Hidden

5. **Source Name: `dj_05`**
   - Type: Video/Media Source (hoặc placeholder)
   - Visibility: Hidden

## Tóm tắt

| Scene | Source | URL |
|-------|--------|-----|
| Scene-Music-Location1 | dj_01 | TradingView BTC |
| Scene-Music-Location1 | dj_02 | TradingView ETH |
| Scene-Music-Location1 | dj_03 | Whale Alert |
| Scene-Music-Location2 | dj_04 | Arkham Intelligence |
| Scene-Music-Location2 | dj_05 | (Chưa cấu hình) |

## Script tự động (Optional)

Nếu muốn auto-update sources từ `dj_sources_config.json`, tôi có thể tạo Python script để:
- Đọc config file
- Gọi OBS WebSocket API
- Tự động tạo/update Browser Sources
