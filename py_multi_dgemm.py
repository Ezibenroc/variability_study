#! /usr/bin/env python3

import argparse
import numpy as np
import time
import sys

def init_matrix(size):
    return np.zeros((size, size))

def matrix_product(A, B):
    t = time.time()
    np.dot(A, B)
    return time.time() - t

if __name__ == '__main__':
    parser = argparse.ArgumentParser(
            description='Experiment runner')
    parser.add_argument('--nb_calls', type=int,
            default=50, help='Number of calls to dgemm.')
    parser.add_argument('--size', type=int,
            default=1024, help='Size of the matrix.").')
    parser.add_argument('--gflops', action='store_true',
            help='Display Gflops instead of seconds.").')
    args = parser.parse_args()
    A = init_matrix(args.size)
    B = init_matrix(args.size)
    for _ in range(args.nb_calls):
        t = matrix_product(A, B)
        gflops = 2*args.size**3 / t * 1e-9
        if args.gflops:
            print(gflops)
        else:
            print(t)
