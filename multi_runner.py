#! /usr/bin/env python3

import argparse
import os
import csv
from runner import compile_generic, run_command

MULTI_DGEMM_EXEC = './multi_dgemm'

def run_multi_dgemm(nb_calls, size, wrapper):
    args = [MULTI_DGEMM_EXEC, str(nb_calls), str(size)]
    output, _ = run_command(args, wrapper=wrapper)
    output = output.decode('utf8').strip()
    times = output.split('\n')
    return [float(t) for t in times]

def run_all(nb_runs, nb_calls, size, nb_threads, csv_file, wrapper):
    os.environ['OMP_NUM_THREADS'] = str(nb_threads)
    with open(csv_file, 'w') as f:
        csv_writer = csv.writer(f)
        csv_writer.writerow(['run_index', 'call_index', 'time'])
        for i in range(nb_runs):
            times = run_multi_dgemm(nb_calls, size, wrapper)
            for j, t in enumerate(times):
                csv_writer.writerow([i, j, t])



if __name__ == '__main__':
    parser = argparse.ArgumentParser(
            description='Experiment runner')
    parser.add_argument('--nb_runs', type=int,
            default=50, help='Number of experiment to run.')
    parser.add_argument('--nb_calls', type=int,
            default=50, help='Number of calls to dgemm for each run.')
    parser.add_argument('--size', type=int,
            default=1024, help='Size of the matrix.").')
    parser.add_argument('-np', '--nb_threads', type=int,
            default=1, help='Number of threads used to perform the operation (may not be supported by all BLAS libraries).')
    parser.add_argument('--wrapper', type=str,
            default=None, help='Command line to use as a wrapper. Example: --wrapper="numactl --physcpubind=0,2,4,6").')
    required_named = parser.add_argument_group('required named arguments')
    required_named.add_argument('--csv_file', type = str,
            required=True, help='Path of the CSV file for the results.')
    required_named.add_argument('--lib', type = str,
            required=True, help='Library to use.',
            choices = ['mkl', 'mkl2', 'atlas', 'openblas'])
    args = parser.parse_args()
    compile_generic(MULTI_DGEMM_EXEC, args.lib)
    run_all(args.nb_runs, args.nb_calls, args.size, args.nb_threads, args.csv_file, args.wrapper)
