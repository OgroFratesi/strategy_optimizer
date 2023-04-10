import pandas as pd
import time
import boto3
from config import *

def divide_space_first(list_params):


    # For each list inside our list, take the longest list index
    max_len_p = 0
    for i, p in enumerate(list_params):
        if len(p) > max_len_p:
            max_len_p = len(p)
            param_to_devide = i
    # halve the selected list
    list_to_divide_into = int(len(list_params[param_to_devide])/2)

    # Now there are two lists
    new_params = list_params[param_to_devide][:list_to_divide_into], list_params[param_to_devide][list_to_divide_into:]

    # This is tricky
    # original list -> [[indicator_1_range_values],[indicator_2_range_values],[indicator_3_range_values]]
    # if indicator 3 is the longest list, the results will be two list:
    # list a) [[indicator_1_range_values],[indicator_2_range_values],[ 1st HALF indicator_3_range_values]]
    # list b) [[indicator_1_range_values],[indicator_2_range_values],[ 2st HALF indicator_3_range_values]]

    list_list_params = []
    for i_new_version in range(2):
        new_list = []
        for i, p in enumerate(list_params):
            if i == param_to_devide:
                new_list.append(new_params[i_new_version])
            else:
                new_list.append(p)
        list_list_params.append(new_list)

    return list_list_params

def count_combinations(list_params):

    combinations = 1
    for p in list_params:
        combinations *= len(p)
    return combinations

def divide_space_second(list_params, times=2):

    # call the divide space as many times we want to divide our total space
    times_divided=1
    while times_divided < times:
        max_mult = 0
        if times_divided == 1:
            list_params = divide_space_first(list_params)
            times_divided += 1
        else:
            # after dividing the original list into 2 subspaces
            for i,p in enumerate(list_params):
                mult = 1
                for e in p:
                    mult *= len(e)
                # The following space we want to halve will be the one with more combinations
                if mult > max_mult:
                    max_mult = mult
                    list_to_divide = i
            # list_params_new is the result of dividing the space (already a subspace), again into other two sub_subspaces.
            list_params_new = divide_space_first(list_params[list_to_divide])
            # Dont need anymore the subspace, we have two sub_subspaces of it now.
            list_params.pop(list_to_divide)
            # Add the two sub_subspaces to the original list
            list_params += list_params_new
            
            times_divided += 1
            

    return list_params



## ******************************************************************************************************* ##

# We create the functions for submitting the batch job, wait for it, and then collect the results from s3

# Collect results function that we will use after the job is done

def collect_results(file_name):

    s3 = boto3.client(
        's3',
        aws_access_key_id=aws_access_key_id,
        aws_secret_access_key=aws_secret_access_key
    )

    # Define S3 bucket and prefix where CSV files are stored
    bucket_name = 'backtester-bucket-results'
    prefix = 'partial_results/'

    # Get list of CSV files in the bucket with the specified prefix
    objects = s3.list_objects_v2(Bucket=bucket_name, Prefix=prefix)
    csv_files = [obj['Key'] for obj in objects['Contents'] if file_name in obj['Key']]

    # Load CSV files into a list of dataframes
    dfs = []
    for file in csv_files:
        obj = s3.get_object(Bucket=bucket_name, Key=file)
        dfs.append(pd.read_csv(obj['Body']))

    # Concatenate dataframes into a single dataframe
    df = pd.concat(dfs, ignore_index=True)

    # Display the resulting dataframe
    return df

