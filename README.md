# STRATEGY OPTIMIZATION

### The scope of this project is to look for a faster way of optimizing a trading strategy. Backtrader packege contains a module where given a range of values for each indicator, the strategy would run each possible combination. In this way, one can obtain the best combinations of parameters. BUT when there are more than few indicators, each with a range of different values, running ALL possible combinations is slow and expensie. This is way the main goal is divided in two parts. 
### The first one is to look for a way of optimizing the way of running each combination, meaning that each run should help the algorithm to search which combination is best to run in the following step. For this we are going to use 2 algorithms. Bayesian optimization and genetic algorithm.
### The second part of the main goal is to look for a way of parallelizing the work, so more combinations could be running at the same time. For this we decided to use RAY, but it will be also implemented in aws batch jobs, in case there is any trouble with ray.

For optimizing a strategy:

Install RAY in a linux envirorment.

#### Check if other version is required here:
pip install -U "ray[default] @ https://s3-us-west-2.amazonaws.com/ray-wheels/latest/ray-3.0.0.dev0-cp37-cp37m-manylinux2014_x86_64.whl"

#### Create a IAM user and set its credential in a .aws directory at the same level of backtester.

#### Once installed, go to the backtester directory and start ray. This will instantiate EC2 in AWS.
 - cd backtester
 - ray up config.yaml --no-config-cache

#### After some minutes of packeges installation, the ray envirorment will be ready. Now is time to replace whether in bayes_strategy.py or in genetic_strategy.py the desired strategy, with the required parameters.

#### Then go back one directory and run:
 - cd ..
#### This is a test script to check if everything is OK
 - ray job submit --working-dir backtester -- python ray_test.py  
#### After this the optimizer can be run. The user can decide to use the genetic algorithm or the bayesian optimization
-  ray job submit --working-dir backtester -- python genetic_ray.py   
