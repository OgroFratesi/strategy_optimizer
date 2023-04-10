
import random
import numpy as np
from multiprocessing import Pool
import pandas as pd
import time
import backtrader as bt
import backtrader.analyzers as btanalyzers
import backtrader.strategies as btstrats
import yfinance as yf
import ray
from strategies.genetic_strategy import parameters_dictionary, strategy_backtrader, N_PERIODS, CRYPTO, CRYPTO_FROM, CRYPTO_TO
import socket
from collections import Counter
from config import *


# We create the function we want to paralalize inside our architecture

@ray.remote
def individual_score_backtrader(list_parameters, DATAFRAMES, threshold):
    '''We feed a list containig the parameters for the strategy, they should be in the same order'''

    average_profit,trades,std, profits = strategy_backtrader(list_parameters, DATAFRAMES, threshold)

    sock = socket.gethostbyname(socket.gethostname())
    print(sock)
    

    return (average_profit,trades,std, profits, sock) 

@ray.remote
def calculate_individual_scores(SECTOR, DATAFRAME, threshold):
        '''Here we pass a sector of the poblation and their scores will be calculated simultaneously'''
        list_list_parameters = [parameters for parameters in SECTOR]

        results = []

        for i in range(len(list_list_parameters)):
            results.append(individual_score_backtrader.remote(list_list_parameters[i], DATAFRAME, threshold))

        
        results = ray.get(results)
        
        result = np.array(results,dtype=object)
        scores = result[:,0]
        trades = result[:,1]
        stds = result[:,2]
        list_scores = result[:,3]

    
        return (scores, trades, stds, list_scores)
    


@ray.remote
class CharlesDarwin():

    def __init__(self, POBLATION, dic_params, DATAFRAME, NUM_MULTI, EVOLUTIONS, periods=3, threshold=0):

        self.POBLATION = POBLATION  # <- how many combinations we are going to score in each evolution iteration 
        self.NUM_MULTI = NUM_MULTI # <- how many combinations AT THE SAME time are we going to score?
        self.dic_params = dic_params # <- dictionary of indicators and their parameter space
        self.EVOLUTIONS = EVOLUTIONS # <- how many complete iterations?
        self.ACTUAL_POBLATION = 0
        self.best_combinations = {}
        self.DATAFRAME = []
        # self.DATAFRAME = DATAFRAME
        self.periods = periods
        self.threshold = threshold
        self.replace_worst = 0.2
        self.sockets = []

        # Divide data into similar periods
        self.divide = int(DATAFRAME.shape[0] / self.periods)
        # We will have a list with all the periods dataframes
        i = 1
        for e in range(self.periods):
            period_df = DATAFRAME.iloc[self.divide*e:self.divide*(e+1),:]
            print(f'{i} period from {str(period_df.index[0])[:10]} to {str(period_df.index[-1])[:10]}')
            self.DATAFRAME.append(period_df)
            i += 1

    def generate_initial_poblation(self, POBLATION):
        '''We create our first N number of combinations randomly'''

        params = [values for key,values in self.dic_params.items()]

        columns = []
        for par in params:
            columns.append(np.random.choice(par, size=(POBLATION,1)))

        mtx = np.concatenate(tuple(columns), axis=1)

        return mtx


    def create_vector_scores(self):
        ''' We calculate a vector score with all combinations scores '''
        VECTOR_SCORE = np.zeros((self.ACTUAL_POBLATION.shape[0]))
        VECTOR_STDS = np.zeros((self.ACTUAL_POBLATION.shape[0]))
        LIST_SCORES = []
        VECTOR_TRADES = []

        ray_results = calculate_individual_scores.remote(self.ACTUAL_POBLATION,self.DATAFRAME, self.threshold)
        scores,trades,stds, list_score = ray.get(ray_results)
        VECTOR_SCORE[e:e+self.NUM_MULTI] = scores
        VECTOR_TRADES += list(trades)
        VECTOR_STDS[e:e+self.NUM_MULTI] = stds
        LIST_SCORES += list(list_score)

        
        return VECTOR_SCORE, VECTOR_TRADES, VECTOR_STDS, LIST_SCORES

    def poblation_crossover(self):

        # For each set of indicators, we are going to randomly change one parameter indicator with it nears neighbor

        # This could be then change to both neighbors
        for e in range(self.ACTUAL_POBLATION.shape[0]-1):
            random_crossover = np.random.randint(self.ACTUAL_POBLATION.shape[1])
            self.ACTUAL_POBLATION[e][random_crossover] = self.ACTUAL_POBLATION[e+1][random_crossover]
            random_crossover = np.random.randint(self.ACTUAL_POBLATION.shape[1])
            self.ACTUAL_POBLATION[e][random_crossover] = self.ACTUAL_POBLATION[e+1][random_crossover]

        return self.ACTUAL_POBLATION


    def poblation_mutation(self, prob=0.2):
        '''For each combination, with a probability of p, the combination will have a random parameters changed'''
        params = [values for key,values in self.dic_params.items()]

        # with a probability of 10% (could be changed) one individual could have a mutation

        for e in range(self.ACTUAL_POBLATION.shape[0]-1):

            prob_mutation = np.random.uniform(0,1)
            if prob_mutation < prob:
                random_crossover = np.random.randint(self.ACTUAL_POBLATION.shape[1])
                actual_value = self.ACTUAL_POBLATION[e][random_crossover]
                set_values = params[random_crossover]
                new_value_true = False
                # Lets be sure that we are changing to a new parameter
                while not new_value_true:
                    new_value = np.random.choice(set_values)
                    if new_value != actual_value:
                        new_value_true = True
                self.ACTUAL_POBLATION[e][random_crossover] = new_value

        return self.ACTUAL_POBLATION

    def poblation_replacement(self, worst=0.2):
        '''We are simply removing the worst %20 combinations to new random combinations'''
        n_replacement = int(self.ACTUAL_POBLATION.shape[0] * worst)
        replace_with = self.generate_initial_poblation(POBLATION=n_replacement)
        self.ACTUAL_POBLATION[-n_replacement:] = replace_with

        return self.ACTUAL_POBLATION

    def take_sockets(self):
        return self.sockets


    def run_evolution(self):
        '''We initiate a random poblation and then we start the evolution!'''
        self.ACTUAL_POBLATION = self.generate_initial_poblation(POBLATION=self.POBLATION)

        for n in range(self.EVOLUTIONS):

            FITNESS_VECTOR, TRADES_VECTOR, STD_VECTOR, LIST_SCORES = self.create_vector_scores()  # Create score for each combination

            TRADES_VECTOR = np.array(TRADES_VECTOR)
            LIST_SCORES = np.array(LIST_SCORES)
            print(f'Fitness score {n} ready. Vector mean: {-1*np.mean(FITNESS_VECTOR[np.argsort(FITNESS_VECTOR)][:10])}') # <-- print the mean of the top 10 values

            self.ACTUAL_POBLATION = self.ACTUAL_POBLATION[np.argsort(FITNESS_VECTOR)] # Sort the poblation by best score
            
            TRADES_VECTOR = TRADES_VECTOR[np.argsort(FITNESS_VECTOR)]
            STD_VECTOR = STD_VECTOR[np.argsort(FITNESS_VECTOR)]
            LIST_SCORES = -1*LIST_SCORES[np.argsort(FITNESS_VECTOR)]
            print(f'best of {n+1} poblation -> {self.ACTUAL_POBLATION[0]}')
            print(f'score: {-1* np.min(FITNESS_VECTOR)}')
            print(f'list_scores: {LIST_SCORES[0]}') 
            print(f'Num Trades: {TRADES_VECTOR[0]} / {np.round((TRADES_VECTOR[0]/self.divide)*30,3)} per month')
            
            # We create and update the dictionary with our results
            if f'{self.ACTUAL_POBLATION[0]}' not in self.best_combinations.keys():
                self.best_combinations[f'{self.ACTUAL_POBLATION[0]}'] = {'mean_score':[-1*np.min(FITNESS_VECTOR)],'scores':[LIST_SCORES[0]],'std_scores':[STD_VECTOR[0]], 'num_trades':[TRADES_VECTOR[0]]} # -> save best combination of the actual poblation

            # Start the crossover, the mutation and replacement
            self.ACTUAL_POBLATION = self.poblation_crossover()
            self.ACTUAL_POBLATION = self.poblation_mutation()
            self.ACTUAL_POBLATION = self.poblation_replacement(worst=self.replace_worst)

            if n == 3:
                print('----------------------')
                print('Poblation reduced.')
                print('----------------------')
                self.ACTUAL_POBLATION = self.ACTUAL_POBLATION[:30,:]
                self.replace_worst = 0.1

            print('- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - ')
        print(self.best_combinations)
        return self.best_combinations

if __name__ == "__main__":

    start_time = time.perf_counter()

    NUM_MULTI = 100
    DIC_PARAMS = parameters_dictionary
    POBLATION = 100

    EVOLUTIONS = 8

    DATAFRAME = yf.download(CRYPTO, CRYPTO_FROM, CRYPTO_TO)


    Charles = CharlesDarwin.remote(POBLATION=POBLATION, 
                            dic_params=DIC_PARAMS, 
                            DATAFRAME=DATAFRAME, 
                            NUM_MULTI= NUM_MULTI, 
                            EVOLUTIONS=EVOLUTIONS,
                            periods=N_PERIODS,
                            threshold=-10)

    best_combinations = Charles.run_evolution.remote()
    print(best_combinations)
    best_combinations = ray.get(best_combinations)

    df_best_combinations = pd.DataFrame(best_combinations)

    print_socket = ray.get(Charles.take_sockets.remote())
    print_socket = ray.get(print_socket)
    print('Tasks executed')
    print(print_socket)
    for ip_address, num_tasks in Counter(print_socket).items():
        print('    {} tasks on {}'.format(num_tasks, ip_address))

    # print(Charles.best_combinations)

    # s3 = s3fs.S3FileSystem(anon=False)

    # # Use 'w' for py3, 'wb' for py2
    # with s3.open('tryingray12345/toy.csv','w') as f:
    #     df_best_combinations.to_csv(f)

    finish_time = time.perf_counter()

    print("Program finished in {} seconds - using multiprocessing".format(finish_time-start_time))
    print("---")
