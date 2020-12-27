import oandapyV20
import oandapyV20.endpoints.orders as orders
import oandapyV20.endpoints.positions as positions
import oandapyV20.endpoints.instruments as instruments
import oandapyV20.endpoints.accounts as accounts
import oandapyV20.endpoints.trades as trades

import talib as ta
import pandas as pd
import time
import math
import numpy as np
import statsmodels.api as sm
import json
import logging

from config import *

logging.basicConfig(filename='adx.log', filemode='w', level=logging.ERROR)

nav = 500000
max_trades = 10

api = oandapyV20.API(access_token=OANDA_API_KEY, environment='practice')

pairs = pd.read_csv('currency-pairs.csv')['0'].tolist()
usd_pairs = pd.read_csv('usd-pairs.csv')['0'].tolist()
pairs_usd = ['GBP_USD', 'EUR_USD', 'AUD_USD', 'NZD_USD']

with open('conversion-pairs.json', 'r') as f:
    conversion_pairs = json.load(f)

with open('oanda-daily-atrs.json', 'r') as f:
    atrs = json.load(f)
    
stop_prices = {}
for pair in pairs:
    stop_prices[pair] = 0.0
    

# ****************************************************************************************************************
def get_position_details(open_positions, pair):
    l_s = ''
    entry_price = 0.0
    amt_owned = 0.0
    
    if len(open_positions) > 0:
        for position in open_positions:
            if position['instrument'] == pair and float(position['long']['units']) != 0:
                l_s = 'long'
                entry_price = float(position['long']['averagePrice'])
                amt_owned = float(position['long']['units'])
            elif position['instrument'] == pair and float(position['short']['units']) != 0:
                l_s = 'short'
                entry_price = float(position['short']['averagePrice'])
                amt_owned = float(position['short']['units']) 
                
    return l_s, entry_price, amt_owned


# ****************************************************************************************************************
def slope(series, n):
    series = (series - series.min()) / (series.max() - series.min())
    x = np.array(range(len(series)))
    x = (x - x.min()) / (x.max() - x.min())
    slopes = [i*0 for i in range(n-1)]
    for i in range(n, len(series) + 1):
        y_scaled = series[i - n:i]
        x_scaled = x[i - n:i]
        x_scaled = sm.add_constant(x_scaled)
        model = sm.OLS(y_scaled, x_scaled)
        results = model.fit()
        slopes.append(results.params[-1])
    slope_angle = (np.rad2deg(np.arctan(np.array(slopes))))
    
    return np.array(slope_angle)


# ****************************************************************************************************************
def create_df(pair):
    delay = 2
    max_period = 20
    timeperiod = 14
    slope_period = 30
    
    payload = {'count': 30,
               'granularity': 'M1', 
               }
    r = instruments.InstrumentsCandles(instrument=pair, params=payload)
    ohlc = api.request(r)['candles']
    
    ohlc_df = pd.DataFrame(columns = ['high', 'low', 'close', 'volume'])
    high_list = []
    low_list = []
    close_list = []
    volume_list = []
    
    for i in range(len(ohlc)):
        high_list.append(float(ohlc[i]['mid']['h']))
        low_list.append(float(ohlc[i]['mid']['l']))
        close_list.append(float(ohlc[i]['mid']['c']))
        volume_list.append(float(ohlc[i]['volume']))
    
    ohlc_df['high'] = high_list
    ohlc_df['low'] = low_list
    ohlc_df['close'] = close_list
    ohlc_df['volume'] = volume_list
    ohlc_df['v_shift'] = ohlc_df['volume'].shift(delay)
    ohlc_df['av'] = ohlc_df['volume'].rolling(window=delay).max()
    ohlc_df['max'] = ohlc_df['v_shift'].rolling(window=(period-delay)).max()
    ohlc_df['adx'] = ta.ADX(ohlc_df['high'], ohlc_df['low'], ohlc_df['close'], timeperiod=timeperiod)
    ohlc_df['slope'] = slope(ohlc_df['close'], slope_period)
    
    return ohlc_df


# ****************************************************************************************************************
def calculate_stop(pair, current_price, max_dd, l_s):
    last_stop = stop_prices[pair]
    
    if l_s == 'long':
        new_stop = current_price - max_dd
        if new_stop > last_stop:
            stop_prices[pair] = new_stop
            return new_stop
        
    elif l_s == 'short':
        new_stop = current_price + max_dd
        if new_stop < last_stop or last_stop == 0.0:
            stop_prices[pair] = new_stop
            return new_stop
        
    return last_stop


# ****************************************************************************************************************
def adx_top_detector(df, pair):
    level = 45
    
    for i in range(75,level,-1):
        if (df['adx'].iloc[-1] < i and
            df['adx'].iloc[-3] > i and
            df['adx'].iloc[-7] < i):
            current = df['adx'].iloc[-1]
            print(f'\nfound adx top for {pair} at {i}\ncurrent adx: {current}\n')
            logging.error(f'\nfound adx top for {pair} at {i}\ncurrent adx: {current}\n')
            return True
    return False
    

# ****************************************************************************************************************
def trade_signal(pair, df, l_s, entry_price=0.0):
    signal = ''
    v_multiplier = 1.0
    take_profit_pct = 0.15
    stop_loss_pct = 0.05
    atr = atrs[pair]
    max_dd = stop_loss_pct*atr
    current_price = df['close'].iloc[-1]
    stop_price = calculate_stop(pair, current_price, max_dd, l_s)    

    if l_s != '':
        print(f'atr: {atr}\ncurrent price: {current_price}\nmax drawdown: {max_dd}\nstop price: {stop_price}')
        logging.error(f'atr: {atr}\ncurrent price: {current_price}\nmax drawdown: {max_dd}\nstop price: {stop_price}')
        
    if l_s == '':
        if (adx_top_detector(df, pair) and
            df['slope'].iloc[-1] < -35 and
            df['av'].iloc[-1] >= df['max'].iloc[-1]*v_multiplier):
            current_volume = df['av'].iloc[-1]
            previous_max = df['max'].iloc[-1]
            print(f'current volume: {current_volume}\nprevious max: {previous_max}\n{pair} is currently downtrending')
            logging.error(f'current volume: {current_volume}\nprevious max: {previous_max}\n{pair} is currently downtrending')
            stop_prices[pair] = 0.0
            signal = 'sell'
                
        elif (adx_top_detector(df, pair) and
              df['slope'].iloc[-1] > 35 and
              df['av'].iloc[-1] >= df['max'].iloc[-1]*v_multiplier):
            current_volume = df['av'].iloc[-1]
            previous_max = df['max'].iloc[-1]
            print(f'current volume: {current_volume}\nprevious max: {previous_max}\n{pair} is currently uptrending')
            logging.error(f'current volume: {current_volume}\nprevious max: {previous_max}\n{pair} is currently uptrending')
            stop_prices[pair] = 0.0
            signal = 'buy'
    
    elif l_s == 'long':
        take_profit_price = entry_price + take_profit_pct*atr
        print(f'take profit price: {take_profit_price}')
        logging.error(f'take profit price: {take_profit_price}')
        if current_price >= take_profit_price or current_price <= stop_price:
            signal = 'close'

    elif l_s == 'short':
        take_profit_price = entry_price - take_profit_pct*atr
        print(f'take profit price: {take_profit_price}')
        logging.error(f'take profit price: {take_profit_price}')
        if current_price <= take_profit_price or current_price >= stop_price:
            signal = 'close'
    
    return signal


# ****************************************************************************************************************
def calculate_qty(df, signal, pair):
    position_size = nav/max_trades*20
    print(f'position size: {position_size}')
    logging.error(f'position size: {position_size}')
    print(df.tail())
    price = df['close'].iloc[-1]
    print(f'price: {price}')
    logging.error(f'price: {price}')
    
    if pair in pairs_usd:
        print('pair is in pairs_usd')
        logging.error('pair is in pairs_usd')
        qty = math.floor(position_size/price)
        print(f'qty: {qty}')
        logging.error(f'qty: {qty}')
    elif pair in usd_pairs:
        print('pair is in usd_pairs')
        logging.error('pair is in usd_pairs')
        qty = math.floor(position_size)
        print(f'qty: {qty}')
        logging.error(f'qty: {qty}')
    else:
        print('pair doesn\'t have usd')
        logging.error('pair doesn\'t have usd')
        conversion_pair = conversion_pairs[pair]
        print(f'conversion pair: {conversion_pair}')
        logging.error(f'conversion pair: {conversion_pair}')
        payload = {'count': 1,
                   'granularity': 'M1', 
                   }
        r = instruments.InstrumentsCandles(instrument=conversion_pair, params=payload)
        conversion_price = float(api.request(r)['candles'][-1]['mid']['c'])
        print(f'conversion price: {conversion_price}')
        logging.error(f'conversion price: {conversion_price}')
        
        if conversion_pair in pairs_usd:
            print('conversion pair in pairs_usd')
            logging.error('conversion pair in pairs_usd')
            price_currency_qty = position_size/conversion_price
            print(f'price currency qty: {price_currency_qty}')
            logging.error(f'price currency qty: {price_currency_qty}')
            qty = math.floor(price_currency_qty/price)
            print(f'qty: {qty}')
            logging.error(f'qty: {qty}')
        else:
            print('conversion pair not in pairs_usd')
            logging.error('conversion pair not in pairs_usd')
            price_currency_qty = position_size*conversion_price
            print(f'price currency qty: {price_currency_qty}')
            logging.error(f'price currency qty: {price_currency_qty}')
            qty = math.floor(price_currency_qty/price)
            print(f'qty: {qty}')
            logging.error(f'qty: {qty}')
            
    if signal == 'buy':
        return qty
    elif signal == 'sell':
        return -qty

    
# ****************************************************************************************************************
def calculate_price(df, pair, signal):
    if df['close'].iloc[-1] > 28 or pair == 'TRY/JPY':
        precision = 3
        offset = .00
    else:
        precision = 5
        offset = .0000
        
    payload = {'count': 1,
               'granularity': 'S5',
               'price': 'B'
               }
    r = instruments.InstrumentsCandles(instrument=pair, params=payload)
    last_bid_price = round(float(api.request(r)['candles'][0]['bid']['c']), precision) - offset
    print(f'last bid price: {last_bid_price}')
    logging.error(f'last bid price: {last_bid_price}')
    
    payload = {'count': 1,
               'granularity': 'S5',
               'price': 'M'
               }
    r = instruments.InstrumentsCandles(instrument=pair, params=payload)
    last_mid_price = round(float(api.request(r)['candles'][0]['mid']['c']), precision) - offset
    print(f'last mid price: {last_mid_price}')
    logging.error(f'last mid price: {last_mid_price}')
    
    payload = {'count': 1,
               'granularity': 'S5',
               'price': 'A'
               }
    r = instruments.InstrumentsCandles(instrument=pair, params=payload)
    last_ask_price = round(float(api.request(r)['candles'][0]['ask']['c']), precision) - offset
    spread = (last_ask_price - last_bid_price)*(math.pow(10, precision - 1))
    print(f'last ask price: {last_ask_price}\nspread: {spread}')
    logging.error(f'last ask price: {last_ask_price}\nspread: {spread}')
    
    if spread > 3:
        print('spread too wide. fuck that shit!')
        return None
    else:
        return last_mid_price


# ****************************************************************************************************************
def main():
    r = orders.OrderList(accountID=ACCOUNT_ID)
    open_orders = api.request(r)['orders']
    for order in open_orders:
        r = orders.OrderCancel(accountID=ACCOUNT_ID, orderID=order['id'])
        api.request(r)
        
    r = positions.OpenPositions(accountID=ACCOUNT_ID)
    open_positions = api.request(r)['positions']

    for pair in pairs:
        try:
            l_s, entry_price, amt_owned = get_position_details(open_positions, pair)
            if l_s != '':
                print('\n', pair, l_s)
                logging.error(f'\n--- {pair} {l_s} ---')
            df = create_df(pair)
            if l_s != '':
                print(df.tail())
                logging.error(f'\n{df.tail()}')
            signal = trade_signal(pair, df, l_s, entry_price)
            if l_s != '':
                print(f'signal: {signal}')
                logging.error(f'signal: {signal}')
                
            if (signal == 'buy' or signal == 'sell') and len(open_positions) < max_trades:
                payload = {'order': {'type': 'LIMIT',
                                     'instrument': pair,
                                     'units': calculate_qty(df, signal, pair),
                                     'price': calculate_price(df, pair, signal),
                                     'TimeInForce': 'GTC',
                                     }}
                r = orders.OrderCreate(accountID=ACCOUNT_ID, data=payload)
                api.request(r)
                print(f'\nNew {signal} position initiated for {pair} \n***************************************\n')
                logging.error(f'\nNew {signal} position initiated for {pair} \n***************************************\n')
                
            elif signal == 'close':
                r = trades.OpenTrades(accountID=ACCOUNT_ID)
                open_trades = api.request(r)['trades']
                for trade in open_trades:
                    if trade['instrument'] == pair:
                        r = trades.TradeClose(accountID=ACCOUNT_ID, tradeID=trade['id'])
                        api.request(r)
                print(f'\nAll positions closed for {pair} \n***************************************\n')
                logging.error(f'\nAll positions closed for {pair} \n***************************************\n')
        except:
            print(f'error encountered... skipping {pair}')
            logging.error(f'error encountered... skipping {pair}')            
       
# START
# ********************************************************************************************************************************
starttime=time.time()
timeout = time.time() + 60*60*24.0

daily_take_profit = .04
daily_stop_loss = -.02

def current_pl():
    r = accounts.AccountDetails(accountID=ACCOUNT_ID)
    account = api.request(r)
    return account['account']['pl']

# and current_pl() < daily_take_profit and current_pl() > daily_stop_loss
while time.time() <= timeout:
    try:
        current_time = time.strftime('%Y-%m-%d %H:%M:%S')
        print("\n----- passthrough at ",time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time.time())), '-----')
        logging.error(f'\n######## PASSTHROUGH AT {current_time} ########')
        main()
        time.sleep(60 - ((time.time() - starttime) % 60.0))
        
    except KeyboardInterrupt:
        print('\n\nKeyboard exception received. Exiting.')
        
        r = orders.OrderList(accountID=ACCOUNT_ID)
        open_orders = api.request(r)['orders']
        for order in open_orders:
            r = orders.OrderCancel(accountID=ACCOUNT_ID, orderID=order['id'])
            api.request(r)
        
        r = trades.OpenTrades(accountID=ACCOUNT_ID)
        open_trades = api.request(r)['trades']
        for trade in open_trades:
            r = trades.TradeClose(accountID=ACCOUNT_ID, tradeID=trade['id'])
            api.request(r)
        exit()
        
    except:
        r = orders.OrderList(accountID=ACCOUNT_ID)
        open_orders = api.request(r)['orders']
        for order in open_orders:
            r = orders.OrderCancel(accountID=ACCOUNT_ID, orderID=order['id'])
            api.request(r)
        
        r = trades.OpenTrades(accountID=ACCOUNT_ID)
        open_trades = api.request(r)['trades']
        for trade in open_trades:
            r = trades.TradeClose(accountID=ACCOUNT_ID, tradeID=trade['id'])
            api.request(r)
        exit()
        
r = orders.OrderList(accountID=ACCOUNT_ID)
open_orders = api.request(r)['orders']
for order in open_orders:
    r = orders.OrderCancel(accountID=ACCOUNT_ID, orderID=order['id'])
    api.request(r)

r = trades.OpenTrades(accountID=ACCOUNT_ID)
open_trades = api.request(r)['trades']
for trade in open_trades:
    r = trades.TradeClose(accountID=ACCOUNT_ID, tradeID=trade['id'])
    api.request(r)
print("all positions closed")
