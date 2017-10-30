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
from subprocess import Popen, PIPE
try:
    import psutil
except ImportError:
    psutil = None
import time
import re
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

CONSTANT_VALUE = 1024

EXP_HOSTNAME = socket.gethostname()
EXP_DATE = time.strftime("%Y/%m/%d")
INTERCOOLR_FILE = '/tmp/intercooler.log'

def print_color(msg, color):
    print('%s%s%s' % (color, msg, END_STR))

def print_blue(msg):
    print_color(msg, BLUE_STR)

def print_green(msg):
    print_color(msg, GREEN_STR)

def error(msg):
    sys.stderr.write('%sERROR: %s%s\n' % (RED_STR, msg, END_STR))
    sys.exit(1)

def parse_stat_line(line):
    line = re.split('\s', line.strip())
    line = [w for w in line if w != '']
    return line

def get_intercoolr_output():
    reg = re.compile('# ENERGY=')
    with open(INTERCOOLR_FILE) as f:
        for line in f:
            m = reg.match(line)
            if m is not None:
                return float(line[m.end():])
    assert False

def parse_stat(output):
    output = output.decode('utf-8')
    lines = output.split('\n')
    assert parse_stat_line(lines[1]) == ['CPU', 'Avg_MHz', 'Busy%', 'Bzy_MHz', 'TSC_MHz']
    lines = [parse_stat_line(l) for l in lines[3:-1]]
    assert len(lines) == cpu_count()
    return [int(l[3]) for l in lines]

def run_command(args, get_stat=False, wrapper=None):
    if get_stat:
        args = ['intercoolr/etrace2', '-o', INTERCOOLR_FILE, 'turbostat'] + args
    if wrapper is not None:
        wrapper = re.split('\s', wrapper.strip())
        args = wrapper + args
    print_blue('%s' % ' '.join(args))
    process = Popen(args, stdout=PIPE, stderr=PIPE)
    output = process.communicate()
    if process.wait() != 0:
        error('with command: %s' % ' '.join(args))
    if get_stat:
        stat = parse_stat(output[1])
    else:
        stat = None
    return output[0], stat

def run_dgemm(sizes, dimensions, get_stat, wrapper):
    m, n, k = sizes
    lead_A, lead_B, lead_C = dimensions
    result, stat = run_command([DGEMM_EXEC] + [str(n) for n in [
        m, n, k, lead_A, lead_B, lead_C]], get_stat, wrapper)
    return float(result), stat

def run_dtrsm(sizes, dimensions, get_stat, wrapper):
    m, n = sizes
    lead_A, lead_B = dimensions
    result, stat = run_command([DTRSM_EXEC] + [str(n) for n in [
        m, n, lead_A, lead_B]], get_stat, wrapper)
    return float(result), stat

def get_sizes(nb, size_range, big_size_range, hpl):
    if hpl:
        assert size_range == big_size_range
        size = random.randint(size_range.min, size_range.max)
        sizes = [size]*nb
        if nb == 3: # dgemm
            sizes[2] = CONSTANT_VALUE
        else: # dtrsm
            assert nb == 2
            sizes[0] = CONSTANT_VALUE
        return tuple(sizes)
    else:
        sizes = [random.randint(size_range.min, size_range.max) for _ in range(nb)]
        i = random.choice([0, 1])
        sizes[i] = random.randint(big_size_range.min, big_size_range.max)
        return tuple(sizes)

def get_dim(sizes):
    return tuple(max(sizes) for _ in range(len(sizes)))

def mean(l):
    return sum(l)/len(l)

def get_cpu_temp(): # long and not very precise...
    temperatures = [temp.current for temp in psutil.sensors_temperatures()['coretemp'] if temp.label.startswith('Core')]
    assert len(temperatures) == cpu_count() or len(temperatures) == cpu_count()/2 # case of hyperthreading
    return temperatures

def do_run(run_func, sizes, leads, csv_writer, offloading, nb_repeat, get_stat, wrapper):
    os.environ['MKL_MIC_ENABLE'] = str(int(offloading))
    for _ in range(nb_repeat):
        time, stat = run_func(sizes, leads, get_stat, wrapper)
        args = [time]
        args.extend(sizes)
        args.extend(leads)
        args.append(offloading)
        args.append(EXP_HOSTNAME)
        args.append(EXP_DATE)
        if get_stat:
            args.extend([min(stat), max(stat), mean(stat)])
            temperatures = get_cpu_temp()
            args.extend([min(temperatures), max(temperatures), mean(temperatures)])
            args.append(get_intercoolr_output())
        csv_writer.writerow(args)

def csv_base_header(get_stat):
    header = ['automatic_offloading', 'hostname', 'date']
    if get_stat:
        header.extend(['min_freq', 'max_freq', 'mean_freq', 'min_temp', 'max_temp', 'mean_temp', 'energy'])
    return header

def run_exp_generic(run_func, nb_sizes, size_range, big_size_range, csv_writer, offloading_mode, hpl, nb_repeat, nb_threads, get_stat, wrapper):
    os.environ['OMP_NUM_THREADS'] = str(nb_threads)
    sizes = get_sizes(nb_sizes, size_range, big_size_range, hpl)
    leads = get_dim(sizes)
    offloading_values = list(offloading_mode)
    random.shuffle(offloading_values)
    for offloading in offloading_values:
        do_run(run_func, sizes, leads, csv_writer, offloading, nb_repeat, get_stat, wrapper)

def run_all_dgemm(csv_file, nb_exp, size_range, big_size_range, offloading_mode, hpl, nb_repeat, nb_threads, get_stat, wrapper):
    with open(csv_file, 'w') as f:
        csv_writer = csv.writer(f)
        header = ['time', 'm', 'n', 'k', 'lead_A', 'lead_B', 'lead_C'] + csv_base_header(get_stat)
        csv_writer.writerow(header)
        for i in range(nb_exp):
            print('Exp %d/%d' % (i+1, nb_exp))
            run_exp_generic(run_dgemm, 3, size_range, big_size_range, csv_writer, offloading_mode, hpl, nb_repeat, nb_threads, get_stat, wrapper)

def run_all_dtrsm(csv_file, nb_exp, size_range, big_size_range, offloading_mode, hpl, nb_repeat, nb_threads, get_stat, wrapper):
    with open(csv_file, 'w') as f:
        csv_writer = csv.writer(f)
        header = ['time', 'm', 'n', 'lead_A', 'lead_B'] + csv_base_header(get_stat)
        csv_writer.writerow(header)
        for i in range(nb_exp):
            print('Exp %d/%d' % (i+1, nb_exp))
            run_exp_generic(run_dtrsm, 2, size_range, big_size_range, csv_writer, offloading_mode, hpl, nb_repeat, nb_threads, get_stat, wrapper)

class LibraryNotFound(Exception):
    pass

def compile_generic(exec_filename, lib):
    c_filename = exec_filename + '.c'
    lib_to_command = {
        'mkl': ['icc', '-DUSE_MKL', c_filename, 'common_matrix.c', '-mkl', '-O3', '-o', exec_filename],
        'mkl2': ['/opt/intel/bin/icc', '-DUSE_MKL', c_filename, 'common_matrix.c', '-I', '/opt/intel/compilers_and_libraries_2017.0.098/linux/mkl/include',
		'/opt/intel/mkl/lib/intel64/libmkl_rt.so', '-O3', '-o', exec_filename], # an ugly command for a non-standard library location
        'atlas': ['gcc', '-DUSE_ATLAS', c_filename, 'common_matrix.c', '/usr/lib/atlas-base/libcblas.so.3', '-O3', '-o', exec_filename],
        'openblas': ['gcc', '-DUSE_OPENBLAS', c_filename, 'common_matrix.c', '/usr/lib/openblas-base/libblas.so', '-O3', '-o', exec_filename],
        'naive': ['gcc', '-DUSE_NAIVE', c_filename, 'common_matrix.c', '-O3', '-o', exec_filename],
    }
    try:
        run_command(lib_to_command[lib])
    except KeyError:
        raise LibraryNotFound('Library unknown. The possible choices are %s' % list(lib_to_command.keys()))

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
    parser.add_argument('--wrapper', type=str,
            default=None, help='Command line to use as a wrapper. Example: --wrapper="numactl --physcpubind=0,2,4,6").')
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
    parser.add_argument('--stat', action='store_true',
            help='Include some metrics about the system state (CPU frequencies and temperatures).')
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
    if args.stat and psutil is None:
        sys.stderr.write('Error: the module psutil is required to use the --stat option.\n')
        sys.exit(1)
    compile_generic(DGEMM_EXEC, args.lib)
    compile_generic(DTRSM_EXEC, args.lib)
    if args.dgemm:
        print("### DGEMM ###")
        run_all_dgemm(dgemm_filename, args.nb_runs, args.size_range, args.big_size_range, offloading_mode, args.hpl, args.nb_repeat, args.nb_threads, args.stat, args.wrapper)
    if args.dtrsm:
        print("### DTRSM ###")
        run_all_dtrsm(dtrsm_filename, args.nb_runs, args.size_range, args.big_size_range, offloading_mode, args.hpl, args.nb_repeat, args.nb_threads, args.stat, args.wrapper)
