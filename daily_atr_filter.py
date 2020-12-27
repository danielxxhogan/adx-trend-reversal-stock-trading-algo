import pandas as pd
import alpaca_trade_api as tradeapi
import json
import talib as ta

from config import *

in_file = 'sp-1500-orig.csv'
out_file = 'sp-1500.csv'

api = tradeapi.REST(ALPACA_API_KEY, ALPACA_SECRET_KEY, PAPER_URL, api_version='v2')
tickers = pd.read_csv(in_file)['0'].tolist()

atrs = {}

for ticker in tickers:
    print(ticker)
    try:
        daily = api.get_barset(symbols=ticker, timeframe='day', limit=15)
        ticker_daily = daily[ticker]
        
        ohlc_df = pd.DataFrame(columns = ['high', 'low', 'close', 'volume'])
        high_list = []
        low_list = []
        close_list = []
        volume_list = []
        
        for i in range(len(ticker_daily)):
            high_list.append(ticker_daily[i].h)
            low_list.append(ticker_daily[i].l)
            close_list.append(ticker_daily[i].c)
            volume_list.append(ticker_daily[i].v)
        
        ohlc_df['high'] = high_list
        ohlc_df['low'] = low_list
        ohlc_df['close'] = close_list
        ohlc_df['volume'] = volume_list
        ohlc_df['avg_vol'] = ohlc_df['volume'].rolling(window=14).mean()
        ohlc_df['atr'] = ta.ATR(ohlc_df['high'], ohlc_df['low'], ohlc_df['close'], timeperiod=14)
        ohlc_df['atr_pct'] = ohlc_df['atr'] / ohlc_df['close']
        
        if ohlc_df['atr_pct'].iloc[-1] < .03:
            pass
        
        elif ohlc_df['close'].iloc[-1] < 5.0:
            pass
        
        elif ohlc_df['volume'].iloc[-1] < 1000000:
            pass
        
        else:
            atrs[ticker] = ohlc_df['atr'].iloc[-1]
            
    except:
        pass

ticker_list = []

for key in atrs.keys():
    ticker_list.append(key)

ticker_series = pd.Series(ticker_list)
ticker_series.to_csv(out_file, index=False)
    
with open('daily-atrs.json', 'w') as f:
    json.dump(atrs, f)
    

# ****************************************************************************************************************
# --- get the original sp 1000 list ---
# sp500 = pd.read_html('https://en.wikipedia.org/wiki/List_of_S%26P_500_companies')[0]['Symbol']
# sp500.to_csv('sp-500-orig.csv', index=False)
    
# sp400 = pd.read_html('https://en.wikipedia.org/wiki/List_of_S%26P_400_companies')[0]['Ticker symbol']
# sp400.to_csv('sp-400-orig.csv', index=False)
    
# sp600 = pd.read_html('https://en.wikipedia.org/wiki/List_of_S%26P_600_companies')[4]['Ticker symbol']
# sp600.to_csv('sp-600-orig.csv', index=False)
    
# sp1000 = pd.read_html('https://en.wikipedia.org/wiki/List_of_S%26P_1000_companies')[5]['Ticker symbol']
# sp1000.to_csv('sp-1000-orig.csv', index=False)

# sp1500 = pd.concat([sp500,sp1000]).drop_duplicates(keep=False)
# sp1500.to_csv('sp-1500-orig.csv', index=False)

# sp900 = pd.concat([sp500,sp400]).drop_duplicates(keep=False)
# sp900.to_csv('sp-900-orig.csv', index=False)

# sp1500 = pd.concat([pd.Series(sp500),sp400,sp600]).drop_duplicates()
# sp1500.to_csv('sp-1500-orig.csv', index=False)         
