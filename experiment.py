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
import random
import collections
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
        self.__enabled__ = True

    def __del__(self):
        self.tmp_dir.cleanup()

    @property
    def enabled(self):
        return True

    @enabled.setter
    def enabled(self, value):
        pass

    @property
    def command_line(self):
        return self.__command_line__()

    @abc.abstractmethod
    def __command_line__(self):
        pass

    @property
    def environment_variables(self):
        return self.__environment_variables__()

    @abc.abstractmethod
    def __environment_variables__(self):
        pass

    @property
    def header(self):
        return self.__header__()

    @abc.abstractmethod
    def __header__(self):
        pass

    @property
    def data(self):
        data = self.__data__()
        assert len(data) == len(self.header)
        return data

    @abc.abstractmethod
    def __data__(self):
        pass

class Disableable(Program):
    @property
    def enabled(self):
        return self.__enabled__

    @enabled.setter
    def enabled(self, value):
        assert value in (True, False)
        self.__enabled__ = value

    @property
    def command_line(self):
        if self.enabled:
            return self.__command_line__()
        else:
            return []

    @property
    def environment_variables(self):
        if self.enabled:
            return self.__environment_variables__()
        else:
            return {}

    @property
    def header(self):
        enabled_name = self.__class__.__name__
        return self.__header__() + [enabled_name]

    @property
    def data(self):
        if self.enabled:
            data = self.__data__()
        else:
            data = ['N/A']*(len(self.header)-1)
        return data + [self.enabled]

class PurePythonProgram(Program):
    def __command_line__(self):
        return []

    def __environment_variables__(self):
        return {}

class NoDataProgram(Program):
    def __header__(self):
        return []

    def __data__(self):
        return []


class Intercoolr(Program):
    def __init__(self):
        super().__init__()
        run_command(['make', '-C', 'intercoolr'])
        self.reg = re.compile('# ENERGY=')

    def __command_line__(self):
        return ['intercoolr/etrace2', '-o', self.tmp_filename]

    def __environment_variables__(self):
        return {}

    def __header__(self):
        return ['energy']

    def __data__(self):
        with open(self.tmp_filename) as f:
            for line in f:
                m = self.reg.match(line)
                if m is not None:
                    return [float(line[m.end():])]

class CommandLine(PurePythonProgram):
    def __init__(self):
        super().__init__()
        self.hash = git.Repo(search_parent_directories=True).head.object.hexsha
        self.cmd = ' '.join(sys.argv)

    def __header__(self):
        return ['git_hash', 'command_line']

    def __data__(self):
        return [self.hash, self.cmd]


class Date(PurePythonProgram):
    def __header__(self):
        return ['date', 'hour']

    def __data__(self):
        date = time.strftime("%Y/%m/%d")
        hour = time.strftime("%H:%M:%S")
        return [date, hour]

class Platform(PurePythonProgram):
    def __init__(self):
        super().__init__()
        self.hostname = platform.node()
        self.os = platform.platform()

    def __header__(self):
        return ['hostname', 'os']

    def __data__(self):
        return [self.hostname, self.os]

class CPU(PurePythonProgram):
    def __header__(self):
        return ['cpu_model',
                'nb_cores',
                'advertised_frequency',
                'current_frequency',
                'cache_size',
            ]

    def __data__(self):
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
    def __header__(self):
        return ['average_temperature']

    def __data__(self):
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

    def __command_line__(self):
        return ['perf', 'stat', '-ddd', '-x,', '-o', self.tmp_filename]

    def __environment_variables__(self):
        return {'LC_TIME' : 'en'} # perf uses locale to display numbers, which is very annoying

    def __header__(self):
        return [m.replace('-', '_') for m in self.metrics]

    def __data__(self):
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

class RemoveOperatingSystemNoise(Disableable):
    def __init__(self, nb_threads):
        super().__init__()
        self.nb_cores = psutil.cpu_count()
        if nb_threads not in (1, self.nb_cores):
            raise ValueError('wrong number of threads, can only handle either one thread or a number equal to the number of cores (%d).' % self.nb_cores)
        self.nb_threads = nb_threads

    def __header__(self):
        return ['cpubind']

    def __data__(self):
        return [self.cpubind]

    def __environment_variables__(self):
        return {'OMP_PROc_BIND' : 'TRUE'}

    def __command_line__(self):
        if self.nb_threads == self.nb_cores:
            self.cpubind = 'all'
        else:
            self.cpubind = str(random.randint(0, self.nb_cores))
        return ['chrt', '--fifo', '99',
                'numactl', '--physcpubind=%s' % self.cpubind, '--localalloc', # we have to choose between localalloc and membind, let's pick localalloc
                # also cannot use --touch option here, not sure to understand why
                ]

class Likwid(Program):
    def __init__(self, group, nb_threads):
        super().__init__()
        self.group = group
        self.nb_cores = psutil.cpu_count()
        if nb_threads not in (1, self.nb_cores):
            raise ValueError('wrong number of threads, can only handle either one thread or a number equal to the number of cores (%d).' % self.nb_cores)
        self.nb_threads = nb_threads

    def __environment_variables__(self):
        # likwid handles the number of threads and the core pinning
        return {'LIKWID_FILENAME': self.tmp_filename}

    def __command_line__(self):
        if self.nb_threads == self.nb_cores:
            self.cpubind = '%d-%d' % (0, self.nb_cores)
        else:
            self.cpubind = str(random.randint(0, self.nb_cores))
        return ['chrt', '--fifo', '99',
                'likwid-perfctr', '-C', self.cpubind, '-g', self.group, '-m'
                ]

class LikwidClock(Likwid):
    def __init__(self, nb_threads):
        super().__init__('CLOCK', nb_threads)

    def __header__(self):
        return ['TODO']

    def __data__(self):
        return ['TODO']

class LikwidEnergy(Likwid):
    def __init__(self, nb_threads):
        super().__init__('ENERGY', nb_threads)

    def __header__(self):
        return ['TODO']

    def __data__(self):
        return ['TODO']

def get_likwid_instance(group, nb_threads):
    likwid_cls = {
        'clock': LikwidClock,
        'energy': LikwidEnergy,
    }
    try:
        return likwid_cls[group](nb_threads)
    except KeyError:
        raise ValueError('This Likwid event group is not supported: %s.\nSupported values: %s.' % (group, list(likwid_cls.keys())))


class Dgemm(Program):
    DgemmData = collections.namedtuple('DgemmData', ['call_index', 'size', 'nb_calls', 'time'])
    def __init__(self, lib, size, nb_calls, nb_threads, block_size, likwid=None):
        super().__init__()
        self.lib = lib
        self.size = size
        self.nb_calls = nb_calls
        self.nb_threads = nb_threads
        self.likwid = likwid
        compile_generic('multi_dgemm', lib, block_size, likwid)

    def __environment_variables__(self):
        return {'OMP_NUM_THREADS' : str(self.nb_threads)}

    def __command_line__(self):
        return ['./multi_dgemm', str(self.nb_calls), str(self.size), self.tmp_filename]

    def __header__(self):
        return ['call_index', 'size', 'nb_calls', 'time']

    def __data__(self):
        with open(self.tmp_filename, 'r') as f:
            times = f.readlines()
        data = self.DgemmData([], [self.size]*len(times), [self.nb_calls]*len(times), [])
        for call_index, t in enumerate(times):
            data.call_index.append(call_index)
            data.time.append(float(t))
        return data

class ExpEngine:
    def __init__(self, application, wrappers):
        self.wrappers = wrappers
        self.application = application
        self.programs = [*self.wrappers, self.application]
        self.base_environment = dict(os.environ)

    def randomly_enable(self):
        for prog in self.programs:
            prog.enabled = random.choice([False, True])

    def enable_all(self):
        for prog in self.programs:
            prog.enabled = True

    def disable_all(self):
        for prog in self.programs:
            prog.enabled = False

    @property
    def command_line(self):
        cmd =[]
        for prog in self.programs:
            cmd.extend(prog.command_line)
        return cmd

    @property
    def environment_variables(self):
        env = {}
        for prog in self.programs:
            env.update(prog.environment_variables)
        return env

    @property
    def header(self):
        return list(itertools.chain(*[prog.header for prog in self.programs]))

    @property
    def data(self):
        wrapper_data = [wrap.data for wrap in self.wrappers]
        app_data = self.application.data
        data = []
        for i in range(len(app_data[0])):
            entry = [*wrapper_data, [d[i] for d in app_data]]
            data.append(list(itertools.chain(*entry)))
        return data

    def run(self):
        os.environ.clear()
        os.environ.update(self.base_environment)
        os.environ.update(self.environment_variables)
        self.output = run_command(self.command_line)

    def run_all(self, csv_filename, nb_runs, compress=False):
        with open(csv_filename, 'w') as f:
            writer = csv.writer(f)
            header = ['run_index'] + self.header
            writer.writerow(header)
            for run_index in range(nb_runs):
                self.randomly_enable()
                self.run()
                for line in self.data:
                    writer.writerow([run_index] + line)
        if compress:
            zip_name = os.path.splitext(csv_filename)[0] + '.zip'
            with zipfile.ZipFile(zip_name, 'w', zipfile.ZIP_DEFLATED) as myzip:
                myzip.write(csv_filename)
            print('Compressed the results: %s' % zip_name)
