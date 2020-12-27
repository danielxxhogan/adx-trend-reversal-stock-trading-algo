import oandapyV20
import oandapyV20.endpoints.instruments as instruments
import talib as ta
import pandas as pd
import json

from config import *

api = oandapyV20.API(access_token=OANDA_API_KEY, environment='practice')
pairs = pd.read_csv('currency-pairs.csv')['0'].tolist()
atrs = {}

payload = {'count': 15,
           'granularity': 'D', 
           }

for pair in pairs:
    r = instruments.InstrumentsCandles(instrument=pair, params=payload)
    ohlc = api.request(r)['candles']
    
    ohlc_df = pd.DataFrame(columns = ['High', 'Low', 'Close'])
    high_list = []
    low_list = []
    close_list = []
    
    for i in range(len(ohlc)):
        high_list.append(ohlc[i]['mid']['h'])
        low_list.append(ohlc[i]['mid']['l'])
        close_list.append(ohlc[i]['mid']['c'])
        
    ohlc_df['High'] = high_list
    ohlc_df['Low'] = low_list
    ohlc_df['Close'] = close_list
    
    atrs[pair] = ta.ATR(ohlc_df['High'], ohlc_df['Low'], ohlc_df['Close']).iloc[-1]
    
with open('oanda-daily-atrs.json', 'w') as f:
    json.dump(atrs, f)
