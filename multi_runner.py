#! /usr/bin/env python3

import argparse
from experiment import *

def add_wrapper(cls, enabled, wrappers, *args):
    if enabled == 'yes':
        wrappers.append(cls(*args))
    elif enabled == 'random':
        wrappers.append(DisableWrapper(cls(*args)))
    else:
        assert enabled == 'no'

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
    parser.add_argument('--likwid', type=str, choices=Likwid.get_available_groups(), nargs='+',
            default=None, help='Measure the given Likwid event. When used, the option --thread_mapping is automatically enabled.')
    parser.add_argument('--thread_mapping', type=str, choices=['yes', 'no', 'random'],
            default='no', help='Map each thread to a specific core.')
    parser.add_argument('--scheduler', type=str, choices=['yes', 'no', 'random'],
            default='no', help='Use a FIFO scheduling policy.')
    required_named = parser.add_argument_group('required named arguments')
    required_named.add_argument('--csv_file', type = str,
            required=True, help='Path of the CSV file for the results.')
    required_named.add_argument('--lib', type = str,
            required=True, help='Library to use.',
            choices = ['mkl', 'mkl2', 'atlas', 'openblas', 'naive'])
    args = parser.parse_args()
    wrappers=[
            CommandLine(),
            Date(),
            Platform(),
            CPU(),
            Time(),
    ]
    if args.likwid is None:
        wrappers.extend([
                Temperature(),
                Perf(),
                Intercoolr(),
            ])
    else:
        wrappers.append(get_likwid_instance(nb_threads=args.nb_threads, groups=args.likwid))
    if args.likwid is None:
        add_wrapper(ThreadMapping, args.thread_mapping, wrappers, args.nb_threads)
    add_wrapper(Scheduler, args.scheduler, wrappers)

    exp = ExpEngine(application=Dgemm(lib=args.lib, size=args.size, nb_calls=args.nb_calls, nb_threads=args.nb_threads, block_size=args.block_size, likwid=args.likwid), wrappers=wrappers)
    exp.run_all(nb_runs=args.nb_runs, csv_filename=args.csv_file, compress=True)
