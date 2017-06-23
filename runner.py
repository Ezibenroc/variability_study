#! /usr/bin/env python3
import sys
import csv
import random
import functools
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

BIG_SIZE = 5000

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

def get_sizes(nb=3):
    return tuple(random.randint(1, BIG_SIZE) for _ in range(nb))
    return (size,)*nb

def get_dim(sizes):
    return tuple(max(sizes) for _ in range(len(sizes)))

def run_exp_generic(run_func, nb_sizes, csv_writer):
    sizes = get_sizes(nb_sizes)
    leads = get_dim(sizes)
    time = run_func(sizes, leads)
    size_product = functools.reduce(lambda x,y: x*y, sizes, 1)
    lead_product = functools.reduce(lambda x,y: x*y, leads, 1)
    ratio = lead_product/size_product
    args = [time]
    args.extend(sizes)
    args.extend(leads)
    csv_writer.writerow(args)

def run_all_dgemm(csv_file, nb_exp):
    with open(csv_file, 'w') as f:
        csv_writer = csv.writer(f)
        csv_writer.writerow(('time', 'm', 'n', 'k', 'lead_A', 'lead_B', 'lead_C'))
        for i in range(nb_exp):
            print('Exp %d/%d' % (i+1, nb_exp))
            run_exp_generic(run_dgemm, 3, csv_writer)

def run_all_dtrsm(csv_file, nb_exp):
    with open(csv_file, 'w') as f:
        csv_writer = csv.writer(f)
        csv_writer.writerow(('time', 'm', 'n', 'lead_A', 'lead_B'))
        for i in range(nb_exp):
            print('Exp %d/%d' % (i+1, nb_exp))
            run_exp_generic(run_dtrsm, 2, csv_writer)

def compile_generic(exec_filename):
    c_filename = exec_filename + '.c'
    run_command(['gcc', c_filename, '-lblas', '-latlas', '-O3', '-o', exec_filename])

if __name__ == '__main__':
    if len(sys.argv) != 3:
        error('Syntax: %s <nb_args> <csv_file>' % sys.argv[0])
    try:
        nb_exp = int(sys.argv[1])
        assert nb_exp > 0
    except (ValueError, AssertionError):
        error('Argument nb_args must be a positive integer.')
    compile_generic(DGEMM_EXEC)
    compile_generic(DTRSM_EXEC)
    base_filename = sys.argv[2]
    assert base_filename[-4:] == '.csv'
    dgemm_filename = base_filename[:-4] + '_dgemm.csv'
    dtrsm_filename = base_filename[:-4] + '_dtrsm.csv'
    print("### DGEMM ###")
    run_all_dgemm(dgemm_filename, nb_exp)
    print("### DTRSM ###")
    run_all_dtrsm(dtrsm_filename, nb_exp)
