import pandas as pd
import os
from datetime import datetime
from multiprocessing import Pool
import time
import backtrader as bt
import backtrader.analyzers as btanalyzers
import yfinance as yf
import time
from hyperopt import fmin, tpe, Trials, hp, STATUS_OK
import boto3
from io import StringIO
from utils import divide_space_second
import json
import textwrap
import importlib.util
from strategies.bayes_strategy import parameters_dictionary, strategy_backtrader, number_of_subspaces
import ray
from config import *

@ray.remote
def bayesian_optimizer(list_params_dic):


    trials = Trials()
    best = fmin(strategy_backtrader,  # <- our strategy function
        space=[hp.choice(key, value) for key, value in list_params_dic.items()],  # we create the list using the strategy dictionary
        algo=tpe.suggest, 
        max_evals=100, # <- we  might estimate the best value for this
        trials=trials)

    # Extract the VWR for every combination 
    results = trials.results
    results_dic = {}

    # This way we can save the results of the optimizer so we can then create a dataframe
    for i, r in enumerate(results):
        for key in r['params'].keys():
            results_dic[key] = []
    results_dic['loss'] = []
    for i, r in enumerate(results):
        for key in r['params'].keys():
            results_dic[key].append(r['params'][key])
        results_dic['loss'].append(r['loss'])


    
    df = pd.DataFrame(results_dic)
    print(df.head(1))
    df.sort_values('loss', ascending=False, inplace=True)

    return df


@ray.remote
def optimize_subspaces(parameters_dictionary):

    # In the following step we load the dictionary created in bayes_strategy
    # We create a list with each range of values for each indicator
    # Calculate total number of combinations, then divide the space into similar N size groups (N being total jobs)

    # We only need parameter values, without indicator names
    list_params = [value for key,value in parameters_dictionary.items()]
    list_list_params = divide_space_second(list_params, times=number_of_subspaces)


    final_subspaces_dic = []
    for list_subspaces in list_list_params:
        # recreate the original dictionary using the new subspaces created
        i = 0
        new_subspace_dictionary = {}
        for key, _ in parameters_dictionary.items():
            new_subspace_dictionary[key] = list_subspaces[i]
            i += 1
        # Append the subspace dictionary to the final list
        final_subspaces_dic.append(new_subspace_dictionary)

    results = []

    for list_subspaces in final_subspaces_dic:
        results.append(bayesian_optimizer.remote(list_subspaces))

    results = ray.get(results)

    results_df = pd.concat(results)

    return results_df

if __name__ == "__main__":

    start_time = time.perf_counter()

    final_result = optimize_subspaces.remote(parameters_dictionary)
    df = ray.get(final_result)

    print(df.sort_values('loss').head(10))
    
    
    csv_buffer = StringIO()
    df.to_csv(csv_buffer, index=False)
    csv_content = csv_buffer.getvalue()

    # Upload the CSV file to S3, this will be a partial result. We are optimizing one subspace.
    s3 = boto3.client(
        's3',
        aws_access_key_id=aws_access_key_id,
        aws_secret_access_key=aws_secret_access_key
    )
    file_name = 'bayesian'
    s3.put_object(Body=csv_content, Bucket='backtester-bucket-results', Key=f'final_results/scores_{file_name}.csv')

    finish_time = time.perf_counter()
    print("Program finished in {} seconds - using multiprocessing".format(finish_time-start_time))
    print("---")