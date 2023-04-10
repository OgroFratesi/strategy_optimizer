
import random
import numpy as np
from multiprocessing import Pool
import pandas as pd
import time
import backtrader as bt
import backtrader.analyzers as btanalyzers
import backtrader.strategies as btstrats

CRYPTO = "ETH-USD"
CRYPTO_FROM = "2017-6-25"
CRYPTO_TO = "2023-02-20"
N_PERIODS = 4

parameters_dictionary = {'slow_lenght':[x for x in range(25, 76, 3)], 
                         'fast_lenght':[x for x in range(2, 20, 2)], 
                         'rsi':[x for x in range(10,30, 2)],
                         'boll_period':[x for x in range(14,30,4)], 
                         'boll_devfactor':[1,2,3]}


def strategy_backtrader(list_parameters, DATAFRAME, threshold):


    class firstStrategy(bt.Strategy):

        
        params = (
                ('slow_length', int(list_parameters[0])),
                ('fast_length',  int(list_parameters[1])),
                ('rsi',  int(list_parameters[2])),
                ('boll_period',  int(list_parameters[3])),
                ('boll_devfactor',  int(list_parameters[4]))
            )
        
        def __init__(self):
            # initializing rsi, slow and fast sma
            self.rsi = bt.indicators.RSI(self.data.close, period=self.params.rsi)
            self.boll = bt.indicators.BollingerBands(period=self.params.boll_period, devfactor=self.params.boll_devfactor)
            self.fast_sma = bt.indicators.SMA(self.data.close, period=self.params.fast_length)
            self.slow_sma = bt.indicators.SMA(self.data.close, period=self.params.slow_length)
            self.crossup = bt.ind.CrossUp(self.fast_sma, self.slow_sma)

        def next(self):
            if not self.position:
                if (self.rsi > 30) & (self.fast_sma > self.slow_sma) & (self.data.close < self.boll.lines.top):  # fast_sma cross up slow_sma and it is not over solded (rsi < 30)
                    self.buy()
            elif self.position:
                if (self.fast_sma < self.slow_sma) | (self.data.close > self.boll.lines.top):
                    self.close()

    # Now we will create a loop and get the score for all the periods we selected, then we will average the scores
    # If ONE score is less than our threshold, the total score will be 0
    profits, trades = [], []
    for PERIODS in DATAFRAME:
        # Create a cerebro instance, add our strategy, some starting cash at broker and a 0.1% broker commission
        cerebro = bt.Cerebro()
        cerebro.addstrategy(firstStrategy)
        cerebro.broker.setcash(10000)
        cerebro.broker.setcommission(commission=0.001)


        data = bt.feeds.PandasData(dataname=PERIODS)
        cerebro.adddata(data)
        # Analyzer
        cerebro.addanalyzer(btanalyzers.SharpeRatio, _name='mysharpe')
        cerebro.addanalyzer(btanalyzers.VWR, _name='VWR')
        cerebro.addanalyzer(btanalyzers.Transactions, _name='transactions')
        thestrats = cerebro.run()
        thestrat = thestrats[0]

        # Just because we use argsort function, lets turn the VWR negative (argsort is from min to max)
        VWR = -thestrat.analyzers.VWR.get_analysis()['vwr']
        PROFIT = -1 * round((cerebro.broker.getvalue() - 10000) / 10000 * 100,3)
        count_trade = len(list(thestrat.analyzers.transactions.get_analysis()))/2

        profits.append(PROFIT)
        trades.append(count_trade)

    profits = np.array(profits)
    trades = np.array(trades)

    
    for l in profits:
        # remember that argsort is from min to max, and we did -1 * profit. So 10 would be -10% of profit.
        if l > (-1 * threshold): # <-- the original threshold is negative
            print(l,(-1 * threshold) )
            return (0,trades,0, profits)

    AVERAGE_PROFIT = round(sum(profits) / len(profits),2) + np.std(profits) # We are penalizing strategies with high standard deviation

    std = np.std(profits)

    return  AVERAGE_PROFIT,trades,std, profits