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
import pandas
import cpuinfo # https://github.com/workhorsy/py-cpuinfo
import git     # https://github.com/gitpython-developers/GitPython
from multiprocessing import cpu_count

from runner import run_command, compile_generic

def mean(l):
    return sum(l)/len(l)

class Program(metaclass=abc.ABCMeta):
    key = ['run_index']
    def __init__(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.tmp_filename = os.path.join(self.tmp_dir.name, 'file')
        self.data = pandas.DataFrame(columns=self.header + ['run_index'])
        self.run_index = 0
        self.enabled = True

    def __del__(self):
        self.tmp_dir.cleanup()

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

    def fetch_data(self):
        self.__fetch_data__()
        self.run_index += 1

    @abc.abstractmethod
    def __fetch_data__(self):
        pass

    def __append_data__(self, data):
        data['run_index'] = self.run_index
        self.data.loc[len(self.data)] = data

    @staticmethod
    def __merge_data__(df1, df2, key):
        return df1.join(df2.set_index(key), on=key)

    def merge_data(self, other_data):
        for i in range(len(self.key), 0, -1):
            key = self.key[0:i]
            try:
                return self.__merge_data__(self.data, other_data, key)
            except KeyError: # the last part of this key (e.g. call_index) is not present yet in the aggregate, let's just add it
                continue
        # Merging without key
        return self.data.join(other_data)

    def post_process(self):
        pass

class ComposeWrapper(Program):
    def __init__(self, *programs):
        self.programs = programs

    def __command_line__(self):
        cmd = []
        for prog in self.programs:
            cmd.extend(prog.command_line)
        return cmd

    def __environment_variables__(self):
        env = dict()
        for prog in self.programs:
            env.update(prog)
        return env

    def __fetch_data__(self):
        for prog in self.programs:
            prog.fetch_data()


class DisableWrapper(Program):
    def __init__(self, program):
        self.program = program

    def __command_line__(self):
        if self.enabled:
            return self.program.command_line
        else:
            return []

    def __environment_variables__(self):
        if self.enabled:
            return self.program.environment_variables
        else:
            return dict()

    def __fetch_data__(self):
        if self.enabled:
            self.program.fetch_data()
        else:
            self.__append_data__({h : 'N/A' for h in self.header})

class PurePythonProgram(Program):
    def __command_line__(self):
        return []

    def __environment_variables__(self):
        return {}

class NoDataProgram(Program):
    def __fetch_data__(self):
        pass

class Time(Program):
    header = ['user_time', 'system_time']
    def __command_line__(self):
        return ['/usr/bin/time', '-o', self.tmp_filename]

    def __environment_variables__(self):
        return {'TIME': '%U %S'}

    def __fetch_data__(self):
        with open(self.tmp_filename) as f:
            output = f.readlines()[0]
        output = output.split()
        user = float(output[0])
        system = float(output[1])
        self.__append_data__({'user_time': user, 'system_time': system})

class Intercoolr(Program):
    header = ['energy']
    def __init__(self):
        super().__init__()
        run_command(['make', '-C', 'intercoolr'])
        self.reg = re.compile('# ENERGY=')

    def __command_line__(self):
        return ['intercoolr/etrace2', '-o', self.tmp_filename]

    def __environment_variables__(self):
        return {}

    def get_energy(self):
        with open(self.tmp_filename) as f:
            for line in f:
                m = self.reg.match(line)
                if m is not None:
                    return float(line[m.end():])

    def __fetch_data__(self):
        energy = self.get_energy()
        self.__append_data__({'energy': energy})

class CommandLine(PurePythonProgram):
    header = ['git_hash', 'command_line']
    def __init__(self):
        super().__init__()
        self.hash = git.Repo(search_parent_directories=True).head.object.hexsha
        self.cmd = ' '.join(sys.argv)

    def __fetch_data__(self):
        self.__append_data__({'git_hash': self.hash, 'command_line': self.cmd})

class Date(PurePythonProgram):
    header = ['date', 'hour']

    def __fetch_data__(self):
        date = time.strftime("%Y/%m/%d")
        hour = time.strftime("%H:%M:%S")
        self.__append_data__({'date': date, 'hour': hour})

class Platform(PurePythonProgram):
    header = ['hostname', 'os']
    def __init__(self):
        super().__init__()
        self.hostname = platform.node()
        self.os = platform.platform()

    def __fetch_data__(self):
        self.__append_data__({'hostname': self.hostname, 'os': self.os})

class CPU(PurePythonProgram):
    header = ['cpu_model',
              'nb_cores',
              'advertised_frequency',
              'current_frequency',
              'cache_size',
            ]

    def __fetch_data__(self):
        self.cpuinfo = cpuinfo.get_cpu_info()
        cache_size = self.cpuinfo['l2_cache_size']
        cache_size = cache_size.split()
        assert len(cache_size) == 2 and cache_size[1] == 'KB'
        self.cpuinfo['l2_cache_size'] = int(cache_size[0])*1000
        self.__append_data__({'cpu_model': self.cpuinfo['brand'],
                            'nb_cores':  self.cpuinfo['count'],
                            'advertised_frequency': self.cpuinfo['hz_advertised_raw'][0],
                            'current_frequency': self.cpuinfo['hz_actual_raw'][0],
                            'cache_size': self.cpuinfo['l2_cache_size'],
                            })


class Temperature(PurePythonProgram):
    header = ['average_temperature']

    def __fetch_data__(self):
        temperatures = [temp.current for temp in psutil.sensors_temperatures()['coretemp'] if temp.label.startswith('Core')]
        assert len(temperatures) == cpu_count() or len(temperatures) == cpu_count()/2 # case of hyperthreading
        return self.__append_data__({'average_temperature': mean(temperatures)})

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
    header = [m.replace('-', '_') for m in metrics]
    metric_to_header = {m:m.replace('-', '_') for m in metrics}

    def __command_line__(self):
        return ['perf', 'stat', '-ddd', '-x,', '-o', self.tmp_filename]

    def __environment_variables__(self):
        return {'LC_TIME' : 'en'} # perf uses locale to display numbers, which is very annoying

    def __fetch_data__(self):
        with open(self.tmp_filename) as f:
            lines = list(csv.reader(f))
        data = dict()
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
                data[self.metric_to_header[line[2]]] = result
                metrics_to_handle.remove(line[2])
        assert len(metrics_to_handle) == 0
        self.__append_data__(data)

class RemoveOperatingSystemNoise(Program):#Disableable):
    header = ['cpubind']
    def __init__(self, nb_threads):
        super().__init__()
        self.nb_cores = psutil.cpu_count()
        if nb_threads not in (1, self.nb_cores):
            raise ValueError('wrong number of threads, can only handle either one thread or a number equal to the number of cores (%d).' % self.nb_cores)
        self.nb_threads = nb_threads

    def __environment_variables__(self):
        return {'OMP_PROc_BIND' : 'TRUE'}

    def __command_line__(self):
        if self.nb_threads == self.nb_cores:
            self.cpubind = 'all'
        else:
            self.cpubind = str(random.randint(0, self.nb_cores-1))
        return ['chrt', '--fifo', '99',                                         # TODO move chrt in a separate class
                'numactl', '--physcpubind=%s' % self.cpubind, '--localalloc',   # we have to choose between localalloc and membind, let's pick localalloc
                # also cannot use --touch option here, not sure to understand why
                ]

    def __fetch_data__(self):
        self.__append_data__({'cpubind': self.cpubind})

class LikwidError(Exception):
    pass

class Likwid(Program):
    keys = ['run_index', 'call_index', 'thread_index']
    header = []
    def __init__(self, group, nb_threads):
        super().__init__()
        self.group = group
        self.nb_cores = psutil.cpu_count()
        if nb_threads not in (1, self.nb_cores):
            raise ValueError('wrong number of threads, can only handle either one thread or a number equal to the number of cores (%d).' % self.nb_cores)
        self.nb_threads = nb_threads
        self.tmp_output = os.path.join(self.tmp_dir.name, 'output.csv')
        self.check_group()

    def check_group(self):
        stdout, stderr = run_command(['likwid-perfctr', '-a'])
        stdout = stdout.decode('ascii')
        lines = stdout.split('\n')[2:]
        lines = [line.strip().split() for line in lines]
        groups = [line[0] for line in lines if len(line) > 0]
        if self.group not in groups:
            raise LikwidError('Group %s not available on this machine.\nAvailable groups: %s.' % (self.group, groups))

    def __environment_variables__(self):
        # likwid handles the number of threads and the core pinning
        return {'LIKWID_FILENAME': self.tmp_filename}

    def __command_line__(self):
        if self.nb_threads == self.nb_cores:
            self.cpubind = '%d-%d' % (0, self.nb_cores-1)
        else:
            self.cpubind = str(random.randint(0, self.nb_cores-1))
        return ['chrt', '--fifo', '99',                                         # TODO move chrt in a separate class
                'likwid-perfctr', '-C', self.cpubind, '-g', self.group, '-o', self.tmp_output, '-m'
                ]
    def get_cpu_clock(self):
        with open(self.tmp_output, 'r') as f:
            reader = csv.reader(f)
            for row in reader:
                if row[0] == 'CPU clock:':
                    try:
                        val, unit = row[1].split()
                        assert unit == 'GHz'
                    except (ValueError, AssertionError):
                        raise LikwidError('Wrong format for the CPU clock (got %s).' % row[1])
                    return float(val) * 1e9
            raise LikwidError('Did not find CPU clock in output.')

    def get_available_events(self):
        with open(self.tmp_output, 'r') as f:
            reader = csv.reader(f)
            in_events = False
            self.events = []
            for row in reader:
                if in_events:
                    if row[0] == 'TABLE' and row[1].startswith('Region'):
                        return
                    else:
                        self.events.append(row[0])
                elif row[0] == 'Event' and row[1] == 'Counter' and row[2].startswith('Core'):
                    in_events = True
        raise LikwidError('Wrong CSV format, could not identify events.')

    def __init_data__(self):
        try:
            self.events
        except AttributeError:
            self.get_available_events()
            self.header = ['cpu_clock', 'call_index', 'likwid_time', 'thread_index', 'core_index'] + self.events
            self.cumulative_values = list(set(self.cumulative_values) & set(self.events)) + ['likwid_time']
            self.data = pandas.DataFrame(columns=self.header + ['run_index'])

    def __fetch_data__(self):
        self.__init_data__()
        clock = self.get_cpu_clock()
        with open(self.tmp_filename) as f:
            reader = csv.reader(f)
            for row in reader:
                assert len(row) == len(self.header)-1
                entry = {'cpu_clock': clock}
                for i in range(1, len(self.header)): # start from 1 because 0 is the cpu_clock
                    h = self.header[i]
                    entry[h] = float(row[i-1])
                self.__append_data__(entry)

    def __decumulate__(self):
        df = self.data.set_index(['run_index', 'call_index', 'thread_index'])[self.cumulative_values]
        df = df.groupby(level=['run_index', 'thread_index']).diff().fillna(df).reset_index()
        self.data.update(df)

    def post_process(self):
        self.__decumulate__()
        # https://github.com/RRZE-HPC/likwid/blob/b8669dba1c5d8bf61cb0d4d4ff2c6fee31bf99ce/groups/ivybridgeEP/UNCORECLOCK.txt#L45
        self.data['likwid_frequency'] = self.data['CPU_CLK_UNHALTED_CORE']/self.data['CPU_CLK_UNHALTED_REF']*self.data['cpu_clock']

class LikwidClock(Likwid):
    cumulative_values = ['likwid_time', 'INSTR_RETIRED_ANY', 'CPU_CLK_UNHALTED_CORE', 'CPU_CLK_UNHALTED_REF', 'PWR_PKG_ENERGY', 'PWR_DRAM_ENERGY']

    def __init__(self, nb_threads):
        super().__init__('CLOCK', nb_threads)

class LikwidEnergy(Likwid):
    cumulative_values = ['likwid_time', 'INSTR_RETIRED_ANY', 'CPU_CLK_UNHALTED_CORE', 'CPU_CLK_UNHALTED_REF', 'PWR_PKG_ENERGY', 'PWR_PP0_ENERGY', 'PWR_DRAM_ENERGY']

    def __init__(self, nb_threads):
        super().__init__('ENERGY', nb_threads)


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
    header = ['call_index', 'size', 'nb_calls', 'time']
    key = ['run_index', 'call_index']

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

    def __fetch_data__(self):
        with open(self.tmp_filename, 'r') as f:
            times = f.readlines()
        for call_index, t in enumerate(times):
            self.__append_data__({'call_index': call_index, 'size': self.size, 'nb_calls': self.nb_calls, 'time': t})

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
            for run_index in range(nb_runs):
                self.randomly_enable()
                self.run()
                for prog in self.programs:
                    prog.fetch_data()
        all_data = pandas.DataFrame()
        for prog in self.programs:
            prog.post_process()
            all_data = prog.merge_data(all_data)
        with open(csv_filename, 'w') as f:
            f.write(all_data.to_csv())
        if compress:
            zip_name = os.path.splitext(csv_filename)[0] + '.zip'
            with zipfile.ZipFile(zip_name, 'w', zipfile.ZIP_DEFLATED) as myzip:
                myzip.write(csv_filename)
            print('Compressed the results: %s' % zip_name)
