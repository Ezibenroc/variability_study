#! /usr/bin/env python3
import sys
import csv
import random
import functools
import argparse
import os
import socket
from multiprocessing import cpu_count
from collections import namedtuple
try:
    import psutil
except ImportError:
    psutil = None
import time
import re
from utils import run_command, compile_generic

DGEMM_EXEC = './dgemm_test'
DTRSM_EXEC = './dtrsm_test'

CONSTANT_VALUE = 1024

EXP_HOSTNAME = socket.gethostname()
EXP_DATE = time.strftime("%Y/%m/%d")

def run_dgemm(sizes, dimensions):
    m, n, k = sizes
    lead_A, lead_B, lead_C = dimensions
    result = run_command([DGEMM_EXEC] + [str(n) for n in [
        m, n, k, lead_A, lead_B, lead_C]])
    return float(result)

def run_dtrsm(sizes, dimensions):
    m, n = sizes
    lead_A, lead_B = dimensions
    result = run_command([DTRSM_EXEC] + [str(n) for n in [
        m, n, lead_A, lead_B]])
    return float(result)

def get_sizes(nb, size_range, big_size_range, hpl):
    size = random.randint(size_range.min, size_range.max)
    return (size,)*nb
#    if hpl:
#        assert size_range == big_size_range
#        size = random.randint(size_range.min, size_range.max)
#        sizes = [size]*nb
#        if nb == 3: # dgemm
#            sizes[2] = CONSTANT_VALUE
#        else: # dtrsm
#            assert nb == 2
#            sizes[0] = CONSTANT_VALUE
#        return tuple(sizes)
#    else:
#        sizes = [random.randint(size_range.min, size_range.max) for _ in range(nb)]
#        i = random.choice([0, 1])
#        sizes[i] = random.randint(big_size_range.min, big_size_range.max)
#        return tuple(sizes)

def get_dim(sizes):
    return tuple(max(sizes) for _ in range(len(sizes)))

def do_run(run_func, sizes, leads, csv_writer, offloading, nb_repeat):
    os.environ['MKL_MIC_ENABLE'] = str(int(offloading))
    for _ in range(nb_repeat):
        time = run_func(sizes, leads)
        args = [time]
        args.extend(sizes)
        args.extend(leads)
        args.append(offloading)
        args.append(EXP_HOSTNAME)
        args.append(EXP_DATE)
        csv_writer.writerow(args)

csv_base_header = ['automatic_offloading', 'hostname', 'date']

def run_exp_generic(run_func, nb_sizes, size_range, big_size_range, csv_writer, offloading_mode, hpl, nb_repeat, nb_threads):
    os.environ['OMP_NUM_THREADS'] = str(nb_threads)
    sizes = get_sizes(nb_sizes, size_range, big_size_range, hpl)
    leads = get_dim(sizes)
    offloading_values = list(offloading_mode)
    random.shuffle(offloading_values)
    for offloading in offloading_values:
        do_run(run_func, sizes, leads, csv_writer, offloading, nb_repeat)

def run_all_dgemm(csv_file, nb_exp, size_range, big_size_range, offloading_mode, hpl, nb_repeat, nb_threads):
    with open(csv_file, 'w') as f:
        csv_writer = csv.writer(f)
        header = ['time', 'm', 'n', 'k', 'lead_A', 'lead_B', 'lead_C'] + csv_base_header
        csv_writer.writerow(header)
        for i in range(nb_exp):
            print('Exp %d/%d' % (i+1, nb_exp))
            run_exp_generic(run_dgemm, 3, size_range, big_size_range, csv_writer, offloading_mode, hpl, nb_repeat, nb_threads)

def run_all_dtrsm(csv_file, nb_exp, size_range, big_size_range, offloading_mode, hpl, nb_repeat, nb_threads):
    with open(csv_file, 'w') as f:
        csv_writer = csv.writer(f)
        header = ['time', 'm', 'n', 'lead_A', 'lead_B'] + csv_base_header
        csv_writer.writerow(header)
        for i in range(nb_exp):
            print('Exp %d/%d' % (i+1, nb_exp))
            run_exp_generic(run_dtrsm, 2, size_range, big_size_range, csv_writer, offloading_mode, hpl, nb_repeat, nb_threads)

def size_parser(string):
    min_v, max_v = (int(n) for n in string.split(','))
    return namedtuple('size_range', ['min', 'max'])(min_v, max_v)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(
            description='Experiment runner')
    parser.add_argument('-n', '--nb_runs', type=int,
            default=30, help='Number of experiments to perform.')
    parser.add_argument('-r', '--nb_repeat', type=int,
            default=3, help='Number of repetition of each experiment.')
    parser.add_argument('-s', '--size_range', type=size_parser,
            default=(1, 5000), help='Minimal and maximal values of the sizes of the matrices (example: "1,5000").')
    parser.add_argument('-b', '--big_size_range', type=size_parser,
            default=None, help='Minimal and maximal values of *one* of the sizes of the matrices (example: "1,5000").\
            The other sizes will remain in the "normal" size range.')
    parser.add_argument('--hpl', action='store_true',
            help='Sample the sizes in the same way than in HPL.')
    parser.add_argument('--test_offloading', action='store_true',
            help='Do tests with the automatic offloading to the Xeon Phi (note: require MKL library).')
    parser.add_argument('--test_no_offloading', action='store_true',
            help='Do tests without the automatic offloading to the Xeon Phi (note: require MKL library).')
    parser.add_argument('--dgemm', action='store_true',
            help='Test the dgemm function.')
    parser.add_argument('--dtrsm', action='store_true',
            help='Test the dtrsm function.')
    parser.add_argument('-np', '--nb_threads', type=int,
            default=1, help='Number of threads used to perform the operation (may not be supported by all BLAS libraries).')
    required_named = parser.add_argument_group('required named arguments')
    required_named.add_argument('--csv_file', type = str,
            required=True, help='Path of the CSV file for the results.')
    required_named.add_argument('--lib', type = str,
            required=True, help='Library to use.',
            choices = ['mkl', 'mkl2', 'atlas', 'openblas'])
    args = parser.parse_args()
    if (args.test_offloading or args.test_no_offloading) and args.lib != 'mkl':
        sys.stderr.write('Error: option --test_[no_]ofloading requires to use the option --lib=mkl.\n')
        sys.exit(1)
    if args.lib == 'mkl' and not (args.test_offloading or args.test_no_offloading):
        sys.stderr.write('Error: please provide at least one offloading mode to test (example: "--test_offloading").\n')
        sys.exit(1)
    offloading_mode = []
    if args.test_offloading:
        offloading_mode.append(True)
    if args.test_no_offloading:
        offloading_mode.append(False)
    if args.lib != 'mkl':
        offloading_mode = [False]
    if not (args.dgemm or args.dtrsm):
        sys.stderr.write('Error: please provide at least one function to test (example: "--dgemm").\n')
        sys.exit(1)
    if args.big_size_range is None:
        args.big_size_range = args.size_range
    base_filename = args.csv_file
    assert base_filename[-4:] == '.csv'
    dgemm_filename = base_filename[:-4] + '_dgemm.csv'
    dtrsm_filename = base_filename[:-4] + '_dtrsm.csv'
    compile_generic(DGEMM_EXEC, args.lib)
    compile_generic(DTRSM_EXEC, args.lib)
    if args.dgemm:
        print("### DGEMM ###")
        run_all_dgemm(dgemm_filename, args.nb_runs, args.size_range, args.big_size_range, offloading_mode, args.hpl, args.nb_repeat, args.nb_threads)
    if args.dtrsm:
        print("### DTRSM ###")
        run_all_dtrsm(dtrsm_filename, args.nb_runs, args.size_range, args.big_size_range, offloading_mode, args.hpl, args.nb_repeat, args.nb_threads)
