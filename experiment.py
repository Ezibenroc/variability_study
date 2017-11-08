import tempfile
import os
import sys
import abc
import re
import itertools
import time
import platform
import psutil
import csv
import zipfile
import cpuinfo # https://github.com/workhorsy/py-cpuinfo
import git     # https://github.com/gitpython-developers/GitPython
from multiprocessing import cpu_count

from runner import run_command, compile_generic

def mean(l):
    return sum(l)/len(l)

class Program(metaclass=abc.ABCMeta):
    def __init__(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.tmp_filename = os.path.join(self.tmp_dir.name, 'file')

    @property
    @abc.abstractmethod
    def command_line(self):
        pass

    @property
    @abc.abstractmethod
    def header(self):
        pass

    @property
    @abc.abstractmethod
    def data(self, output):
        pass

class PurePythonProgram(Program):
    @property
    def command_line(self):
        return []

class NoDataProgram(Program):
    @property
    def header(self):
        return []

    @property
    def data(self, output):
        return []


class Intercoolr(Program):
    def __init__(self):
        super().__init__()
        run_command(['make', '-C', 'intercoolr'])

    @property
    def command_line(self):
        return ['intercoolr/etrace2', '-o', self.tmp_filename]

    @property
    def header(self):
        return ['energy']

    @property
    def data(self):
        reg = re.compile('# ENERGY=')
        with open(self.tmp_filename) as f:
            for line in f:
                m = reg.match(line)
                if m is not None:
                    return [float(line[m.end():])]

class CommandLine(PurePythonProgram):
    def __init__(self):
        super().__init__()
        self.hash = git.Repo(search_parent_directories=True).head.object.hexsha
        self.cmd = ' '.join(sys.argv)

    @property
    def header(self):
        return ['git_hash', 'command_line']

    @property
    def data(self):
        return [self.hash, self.cmd]


class Date(PurePythonProgram):
    @property
    def header(self):
        return ['date', 'hour']

    @property
    def data(self):
        date = time.strftime("%Y/%m/%d")
        hour = time.strftime("%H:%M:%S")
        return [date, hour]

class Platform(PurePythonProgram):
    def __init__(self):
        super().__init__()
        self.hostname = platform.node()
        self.os = platform.platform()

    @property
    def header(self):
        return ['hostname', 'os']

    @property
    def data(self):
        return [self.hostname, self.os]

class CPU(PurePythonProgram):
    @property
    def header(self):
        return ['cpu_model',
                'nb_cores',
                'advertised_frequency',
                'current_frequency',
                'cache_size',
            ]

    @property
    def data(self):
        self.cpuinfo = cpuinfo.get_cpu_info()
        cache_size = self.cpuinfo['l2_cache_size']
        cache_size = cache_size.split()
        assert len(cache_size) == 2 and cache_size[1] == 'KB'
        self.cpuinfo['l2_cache_size'] = int(cache_size[0])*1000
        return [self.cpuinfo['brand'],
                self.cpuinfo['count'],
                self.cpuinfo['hz_advertised_raw'][0],
                self.cpuinfo['hz_actual_raw'][0],
                self.cpuinfo['l2_cache_size'],
            ]

class Temperature(PurePythonProgram):
    @property
    def header(self):
        return ['average_temperature']

    @property
    def data(self):
        temperatures = [temp.current for temp in psutil.sensors_temperatures()['coretemp'] if temp.label.startswith('Core')]
        assert len(temperatures) == cpu_count() or len(temperatures) == cpu_count()/2 # case of hyperthreading
        return [mean(temperatures)]

class Perf(Program):
    metrics = ['context-switches',
               'cpu-migrations',
               'page-faults',
               'cycles',
               'instructions',
               'branches',
               'branch-misses',
                'L1-dcache-loads',
                'L1-dcache-load-misses',
                'LLC-loads',
                'LLC-load-misses',
                'L1-icache-load-misses',
                'dTLB-loads',
                'dTLB-load-misses',
                'iTLB-loads',
                'iTLB-load-misses',
            ]

    def __init__(self):
        super().__init__()
        os.environ['LC_TIME'] = 'en' # perf uses locale to display numbers, which is very annoying

    @property
    def command_line(self):
        return ['perf', 'stat', '-ddd', '-x,', '-o', self.tmp_filename]

    @property
    def header(self):
        return [m.replace('-', '_') for m in self.metrics]

    @property
    def data(self):
        with open(self.tmp_filename) as f:
            lines = list(csv.reader(f))
        data = []
        metrics_to_handle = set(self.metrics)
        for line in lines[2:]:
            if line[2] in metrics_to_handle:
                result = line[0]
                try:
                    result = int(result)
                except ValueError:
                    try:
                        result = float(result)
                    except ValueError:
                        pass
                data.append(result)
                metrics_to_handle.remove(line[2])
        assert len(metrics_to_handle) == 0
        return data

class RemoveOperatingSystemNoise(NoDataProgram):
    def __init__(self):
        super().__init__()
        os.environ['OMP_PROc_BIND'] = 'TRUE'

    @property
    def command_line(self):
        return ['chrt', '--fifo', '99',
                'numactl', '--physcpubind=all', '--localalloc', # we have to choose between localalloc and membind, let's pick localalloc
                # also cannot use --touch option here, not sure to understand why
                ]

class Dgemm(Program):
    def __init__(self, lib, size, nb_calls, nb_threads, block_size):
        super().__init__()
        os.environ['OMP_NUM_THREADS'] = str(nb_threads)
        self.lib = lib
        self.size = size
        self.nb_calls = nb_calls
        compile_generic('multi_dgemm', lib, block_size)

    @property
    def command_line(self):
        return ['./multi_dgemm', str(self.nb_calls), str(self.size), self.tmp_filename]

    @property
    def header(self):
        return ['call_index', 'size', 'nb_calls', 'time']

    @property
    def data(self):
        with open(self.tmp_filename, 'r') as f:
            times = output = f.readlines()
        return [(call_index, self.size, self.nb_calls, float(t)) for call_index, t in enumerate(times)]

class ExpEngine:
    def __init__(self, application, wrappers):
        self.wrappers = wrappers
        self.application = application
        self.programs = [*self.wrappers, self.application]

    def run(self):
        args = list(itertools.chain(*[prog.command_line for prog in self.programs]))
        self.output = run_command(args)

    @property
    def header(self):
        return list(itertools.chain(*[prog.header for prog in self.programs]))

    @property
    def data(self):
        wrapper_data = [wrap.data for wrap in self.wrappers]
        app_data = self.application.data
        data = []
        for entry in app_data:
            data.append(list(itertools.chain(*[*wrapper_data, entry])))
        return data

    def run_all(self, csv_filename, nb_runs, compress=False):
        with open(csv_filename, 'w') as f:
            writer = csv.writer(f)
            header = ['run_index'] + self.header
            writer.writerow(header)
            for run_index in range(nb_runs):
                self.run()
                for line in self.data:
                    writer.writerow([run_index] + line)
        if compress:
            zip_name = os.path.splitext(csv_filename)[0] + '.zip'
            with zipfile.ZipFile(zip_name, 'w', zipfile.ZIP_DEFLATED) as myzip:
                myzip.write(csv_filename)
            print('Compressed the results: %s' % zip_name)
