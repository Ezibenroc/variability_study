#! /usr/bin/env python3
import sys
import csv
import random
import functools
import argparse
from subprocess import Popen, PIPE
try:
    from subprocess import DEVNULL
except ImportError:
    DEVNULL = open('/dev/null', 'w')

BLUE_STR = '\033[1m\033[94m'
GREEN_STR = '\033[1m\033[92m'
RED_STR = '\033[1m\033[91m'
END_STR = '\033[0m'

DGEMM_EXEC = './dgemm_test'
DTRSM_EXEC = './dtrsm_test'

def print_color(msg, color):
    print('%s%s%s' % (color, msg, END_STR))

def print_blue(msg):
    print_color(msg, BLUE_STR)

def print_green(msg):
    print_color(msg, GREEN_STR)

def error(msg):
    sys.stderr.write('%sERROR: %s%s\n' % (RED_STR, msg, END_STR))
    sys.exit(1)

def run_command(args):
    print_blue('%s' % ' '.join(args))
    process = Popen(args, stdout=PIPE)
    output = process.communicate()
    if process.wait() != 0:
        error('with command: %s' % ' '.join(args))
    return output[0]

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

def get_sizes(nb, max_size):
    return tuple(random.randint(1, max_size) for _ in range(nb))
    return (size,)*nb

def get_dim(sizes):
    return tuple(max(sizes) for _ in range(len(sizes)))

def run_exp_generic(run_func, nb_sizes, max_size, csv_writer):
    sizes = get_sizes(nb_sizes, max_size)
    leads = get_dim(sizes)
    time = run_func(sizes, leads)
    size_product = functools.reduce(lambda x,y: x*y, sizes, 1)
    lead_product = functools.reduce(lambda x,y: x*y, leads, 1)
    ratio = lead_product/size_product
    args = [time]
    args.extend(sizes)
    args.extend(leads)
    csv_writer.writerow(args)

def run_all_dgemm(csv_file, nb_exp, max_size):
    with open(csv_file, 'w') as f:
        csv_writer = csv.writer(f)
        csv_writer.writerow(('time', 'm', 'n', 'k', 'lead_A', 'lead_B', 'lead_C'))
        for i in range(nb_exp):
            print('Exp %d/%d' % (i+1, nb_exp))
            run_exp_generic(run_dgemm, 3, max_size, csv_writer)

def run_all_dtrsm(csv_file, nb_exp, max_size):
    with open(csv_file, 'w') as f:
        csv_writer = csv.writer(f)
        csv_writer.writerow(('time', 'm', 'n', 'lead_A', 'lead_B'))
        for i in range(nb_exp):
            print('Exp %d/%d' % (i+1, nb_exp))
            run_exp_generic(run_dtrsm, 2, max_size, csv_writer)

def compile_generic(exec_filename, lib):
    c_filename = exec_filename + '.c'
    if lib == 'mkl':
        run_command(['icc', '-DUSE_MKL', c_filename, '-O3', '-o', exec_filename])
    elif lib == 'atlas':
        run_command(['gcc', c_filename, '-lblas', '-latlas', '-O3', '-o', exec_filename])
    else:
        assert False

if __name__ == '__main__':
    parser = argparse.ArgumentParser(
            description='Experiment runner')
    parser.add_argument('-n', '--nb_runs', type=int,
            default=30, help='Number of experiments to perform.')
    parser.add_argument('-s', '--max_size', type=int,
            default=5000, help='Maximal size of the matrices.')
    required_named = parser.add_argument_group('required named arguments')
    required_named.add_argument('--csv_file', type = str,
            required=True, help='Path of the CSV file for the results.')
    required_named.add_argument('--lib', type = str,
            required=True, help='Library to use.',
            choices = ['mkl', 'atlas'])
    args = parser.parse_args()
    compile_generic(DGEMM_EXEC, args.lib)
    compile_generic(DTRSM_EXEC, args.lib)
    base_filename = args.csv_file
    assert base_filename[-4:] == '.csv'
    dgemm_filename = base_filename[:-4] + '_dgemm.csv'
    dtrsm_filename = base_filename[:-4] + '_dtrsm.csv'
    print("### DGEMM ###")
    run_all_dgemm(dgemm_filename, args.nb_runs, args.max_size)
    print("### DTRSM ###")
    run_all_dtrsm(dtrsm_filename, args.nb_runs, args.max_size)
