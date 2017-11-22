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
    parser.add_argument('--remove_os_noise', action='store_true',
            help='Remove the operating system noise (e.g. by using a FIFO scheduling policy and binding threads and memory).')
    parser.add_argument('--likwid', type=str, choices=['clock', 'energy'],
            default=None, help='Measure the given Likwid event. When used, the option --remove_os_noise is automatically enabled.')
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
    ]
    if args.likwid is None:
        wrappers.extend([
                Temperature(),
                Perf(),
                Intercoolr(),
            ])
    else:
        wrappers.append(get_likwid_instance(group=args.likwid, nb_threads=args.nb_threads))
    if args.remove_os_noise and args.likwid is None:
        wrappers.append(RemoveOperatingSystemNoise(args.nb_threads))
    exp = ExpEngine(application=Dgemm(lib=args.lib, size=args.size, nb_calls=args.nb_calls, nb_threads=args.nb_threads, block_size=args.block_size, likwid=args.likwid), wrappers=wrappers)
    exp.run_all(nb_runs=args.nb_runs, csv_filename=args.csv_file, compress=True)
