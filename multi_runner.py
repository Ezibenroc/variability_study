#! /usr/bin/env python3

import argparse
from experiment import *

if __name__ == '__main__':
    parser = argparse.ArgumentParser(
            description='Experiment runner')
    parser.add_argument('--nb_runs', type=int,
            default=50, help='Number of experiment to run.')
    parser.add_argument('--nb_calls', type=int,
            default=50, help='Number of calls to dgemm for each run.')
    parser.add_argument('--size', type=int,
            default=1024, help='Size of the matrix.").')
    parser.add_argument('--block_size', type=int,
            default=128, help='Block size of the matrix for computations.").')
    parser.add_argument('-np', '--nb_threads', type=int,
            default=1, help='Number of threads used to perform the operation (may not be supported by all BLAS libraries).')
    required_named = parser.add_argument_group('required named arguments')
    required_named.add_argument('--csv_file', type = str,
            required=True, help='Path of the CSV file for the results.')
    required_named.add_argument('--lib', type = str,
            required=True, help='Library to use.',
            choices = ['mkl', 'mkl2', 'atlas', 'openblas', 'naive'])
    args = parser.parse_args()
    exp = ExpEngine(application=Dgemm(lib=args.lib, size=args.size, nb_calls=args.nb_calls, nb_threads=args.nb_threads, block_size=args.block_size),
            wrappers=[
                    Date(),
                    Platform(),
                    CPU(),
                    Temperature(),
                    Perf(),
                    Intercoolr(),
                ])
    exp.run_all(nb_runs=args.nb_runs, csv_filename=args.csv_file, compress=True)
