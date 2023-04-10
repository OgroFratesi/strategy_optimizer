import backtrader as bt
import backtrader.analyzers as btanalyzers
import yfinance as yf
from hyperopt import fmin, tpe, Trials, hp, STATUS_OK
import boto3
import pandas as pd
import ray

# First it is needed to set how many subspaces the user want to divide the original space (total combinations)
number_of_subspaces = 10

# As in the darwin algorithm, the parameters_dictionary have every value for each indicator
parameters_dictionary = {'fast_lenght':[x for x in range(2, 20, 2)], 
                         'slow_lenght':[x for x in range(25, 76, 3)], 
                         'rsi':[x for x in range(10,30, 2)],
                         'boll_period':[x for x in range(14,30,4)], 
                         'boll_devfactor':[1,2,3]}

# Load the data, in this case ETH from 2018 to 2022, daily candles.
DATAFRAME = pd.read_csv('data/eth_usd.csv', index_col=0)
DATAFRAME.index =  pd.to_datetime(DATAFRAME.index)

# DATAFRAME = yf.download("ETH-USD", "2018-6-25", "2022-3-25")


# The strategy function to be used by the bayesian optimization algorithm. This is where the user use its own strategy.
# IMPORTANT - don't change the strategy class name. The parameters dictionary should have the same key names. 
# IMPORTANT - parameters_dictionary MUST have the same order as params (in the strategy class)
def strategy_backtrader(list_params):


    # ************************************************************************************************************* # 
    # 


    list_params_dic = {'fast_lenght': list_params[0], 
                       'slow_lenght':list_params[1], 
                       'rsi':list_params[2],
                        'boll_period':list_params[3], 
                        'boll_devfactor':list_params[4]}


    class firstStrategy(bt.Strategy):

        
        params = (
                ('fast_length', list_params[0]),
                ('slow_length', list_params[1]),
                ('rsi', list_params[2]),
                ('boll_period', list_params[3]),
                ('boll_devfactor', list_params[4]) # if more indicators are added to the dictionary, remember to continue the sequence of "list_params[n]"
            )

        def __init__(self, params=None):
            if params != None:
                for name, val in params.items():
                    setattr(self.params, name, val) # This __init__ must be the same.
            # initializing rsi, slow and fast sma
            self.rsi = bt.indicators.RSI(self.data.close, period=21)
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

    # ************************************************************************************************************* # 
                
    # Do not modify the following

    for _ in range(1):
        # Create a cerebro instance, add our strategy, some starting cash at broker and a 0.1% broker commission
        cerebro = bt.Cerebro()
        # Replace "firstStrategy" with the name of the strategy you chose
        cerebro.addstrategy(firstStrategy)
        cerebro.broker.setcash(10000)
        cerebro.broker.setcommission(commission=0.001)
        data = bt.feeds.PandasData(dataname=DATAFRAME)
        cerebro.adddata(data)
        # Analyzer
        cerebro.addanalyzer(btanalyzers.SharpeRatio, _name='mysharpe')
        cerebro.addanalyzer(btanalyzers.VWR, _name='VWR')
        cerebro.addanalyzer(btanalyzers.Transactions, _name='transactions')
        thestrats = cerebro.run()
        thestrat = thestrats[0]

        loss = -thestrat.analyzers.VWR.get_analysis()['vwr']

        trades = len(list(thestrat.analyzers.transactions.get_analysis()))/2

    return {'params': list_params_dic, 'loss': loss,'trades':trades, 'status': STATUS_OK }
