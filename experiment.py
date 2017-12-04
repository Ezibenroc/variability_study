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
        self.run_index = 0
        self.enabled = True

    def __str__(self):
        return self.__class__.__name__

    @property
    def enabled(self):
        return self.__enabled__

    @enabled.setter
    def enabled(self, value):
        assert value in (True, False)
        self.__enabled__ = value

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
        try:
            self.__data__.loc[len(self.__data__)] = data
        except AttributeError:
            self.__data__ = pandas.DataFrame({h:[v] for h, v in data.items()})

    @staticmethod
    def __merge_data__(df1, df2):
        if len(df2) == 0:
            return df1
        if len(df1) == 0:
            return df2
        # See https://github.com/pandas-dev/pandas/blob/d270bbb1448ecaccbb567721c991350bac715059/pandas/core/indexes/base.py#L3230-L3232
        # Cannot do a join on the indexes when using different multi-level indexes.
        # Typical example: joining Likwid's dataframe (which has ['run_index', 'call_index', 'thread_index'] as index)
        # with Dgemm's dataframe (which has ['run_index', 'call_index'].
        # To reproduce:
        # > a = pandas.DataFrame({'x': [1], 'y':['a'], 'z':[10], 'zz': [30]}).set_index(['x', 'y', 'z'])
        # > b = pandas.DataFrame({'x': [1], 'y':['a'], 'foo':[42]}).set_index(['x', 'y'])
        # > a.join(b) # raises NotImplementedError
        # So instead, let's make sure everyone has the same index...
        if df2.index.nlevels > df1.index.nlevels:
            df1, df2 = df2, df1
        if df1.index.nlevels > df2.index.nlevels:
            index_1 = df1.index.names
            index_2 = df2.index.names
            if not set(index_1) > set(index_2):
                raise ValueError('Indexes do not match, got %s and %s.' % (index_1, index_2))
            missing = set(index_1) - set(index_2)
            df2 = df2.reset_index()
            for idx in missing:
                df2[idx] = 0 # warning: will not work if 0 is not a value for df1[idx] (but this is not the case currently)
            df2 = df2.set_index(index_1) # we have added the missing columns, so now we can reindex on the larger index
            return df1.join(df2, how='outer')
        try:
            return df1.join(df2, how='outer')
        except ValueError: # overlap of columns
            result = df1.combine_first(df2)
            if len(df1) + len(df2) != len(result):
                raise ValueError('The two dataframes have overlapping columns and share common values in their index.')
            dtypes = df1.dtypes.combine_first(df2.dtypes)
            for k, v in dtypes.iteritems():
                try:
                    result[k] = result[k].astype(v)
                except valueError:
                    pass # When there is missing data, it is represented as NaN, which is a float, even if the original data was int
            return result

    def merge_data(self, other_data):
        try:
            df = self.data.set_index(self.key)
        except KeyError:
            if len(self.data) == 0:
                return other_data
            else:
                raise ValueError('%s: Could not set index on key %s.' % (self.__class__.__name__, self.key))
        return self.__merge_data__(df, other_data)

    def post_process(self):
        pass

    @property
    def data(self):
        try:
            return self.__data__
        except AttributeError:
            return pandas.DataFrame()

class ComposeWrapper(Program):
    def __init__(self, *programs):
        self.programs = programs
        super().__init__()

    def __str__(self):
        return '%s(%s)' % (self.__class__.__name__, ', '.join([str(prog) for prog in self.programs]))

    def __command_line__(self):
        cmd = []
        for prog in self.programs:
            cmd.extend(prog.command_line)
        return cmd

    def __environment_variables__(self):
        env = dict()
        for prog in self.programs:
            env.update(prog.environment_variables)
        return env

    def __fetch_data__(self):
        for prog in self.programs:
            prog.fetch_data()

    @property
    def header(self):
        header = []
        for prog in self.programs:
            header.extend(prog.header)
        return header

    @property
    def key(self):
        key = set()
        for prog in self.programs:
            key |= set(prog.key)
        return list(key)

    @property
    def data(self):
        all_data = pandas.DataFrame()
        for prog in self.programs:
            all_data = prog.merge_data(all_data)
        return all_data.reset_index()

    def post_process(self):
        for prog in self.programs:
            prog.post_process()

class DisableWrapper(Program):
    def __init__(self, program):
        self.program = program
        super().__init__()

    def __str__(self):
        return '%s(%s)' % (self.__class__.__name__, str(self.program))

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
            self.program.run_index += 1

    @property
    def header(self):
        return self.program.header

    @property
    def key(self):
        return self.program.key

    @property
    def data(self):
        return self.program.data

    @data.setter
    def data(self, df):
        pass # a workaroud, necessary to implemnet the getter...

    def post_process(self):
        self.program.post_process()

class OnlyOneWrapper(ComposeWrapper):
    def __init__(self, *programs):
        programs = [DisableWrapper(prog) for prog in programs]
        super().__init__(*programs)

    @property
    def enabled(self):
        return any(prog.enabled for prog in self.programs)

    @enabled.setter
    def enabled(self, value):
        assert value in (True, False)
        for prog in self.programs:
            prog.enabled = False
        self.current_prog = random.choice(self.programs)
        self.current_prog.enabled = True

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
    key = ['run_index', 'call_index', 'thread_index']
    header = []
    available_groups = None
    def __init__(self, group, nb_threads):
        super().__init__()
        self.group = group
        self.nb_cores = psutil.cpu_count()
        if nb_threads not in (1, self.nb_cores):
            raise ValueError('wrong number of threads, can only handle either one thread or a number equal to the number of cores (%d).' % self.nb_cores)
        self.nb_threads = nb_threads
        self.tmp_output = os.path.join(self.tmp_dir.name, 'output.csv')
        self.check_group()

    @classmethod
    def get_available_groups(cls):
        if cls.available_groups is None:
            stdout, stderr = run_command(['likwid-perfctr', '-a'])
            stdout = stdout.decode('ascii')
            lines = stdout.split('\n')[2:]
            lines = [line.strip().split() for line in lines]
            cls.available_groups = set([line[0] for line in lines if len(line) > 0])
        return cls.available_groups

    def check_group(self):
        groups = self.get_available_groups()
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
                'likwid-perfctr', '-f', '-C', self.cpubind, '-g', self.group, '-o', self.tmp_output, '-m'
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

    def disambiguate_multiple_events(self):
        nb_occurences = collections.Counter(self.events)
        counter = collections.Counter()
        for i, evt in enumerate(self.events):
            if nb_occurences[evt] > 1:
                self.events[i] = '%s_%d' % (evt, counter[evt])
                counter[evt] += 1

    def __init_header__(self):
        try:
            self.events
        except AttributeError:
            self.get_available_events()
            self.disambiguate_multiple_events()
            self.header = ['cpu_clock', 'call_index', 'likwid_time', 'thread_index', 'core_index'] + self.events

    def __fetch_data__(self):
        self.__init_header__()
        clock = self.get_cpu_clock()
        with open(self.tmp_filename) as f:
            reader = csv.reader(f)
            for row in reader:
                assert len(row) == len(self.header)-1
                entry = {'likwid_group': self.group, 'cpu_clock': clock}
                for i in range(1, len(self.header)): # start from 1 because 0 is the cpu_clock
                    h = self.header[i]
                    entry[h] = float(row[i-1])
                self.__append_data__(entry)

    def __decumulate__(self):
        df = self.data.set_index(self.key)[['likwid_time']]
        df = df.groupby(level=['run_index', 'thread_index']).diff().fillna(df).reset_index()
        self.data.update(df)

    def post_process(self):
        if len(self.data) == 0: # can happen when used with a DisableWrapper
            return
        self.__decumulate__()
        # https://github.com/RRZE-HPC/likwid/blob/b8669dba1c5d8bf61cb0d4d4ff2c6fee31bf99ce/groups/ivybridgeEP/UNCORECLOCK.txt#L45
        self.data['likwid_frequency'] = self.data['CPU_CLK_UNHALTED_CORE']/self.data['CPU_CLK_UNHALTED_REF']*self.data['cpu_clock']

def get_likwid_instance(nb_threads, groups):
    assert len(groups) > 0
    if len(groups) == 1:
        return Likwid(group=groups[0], nb_threads=nb_threads)
    else:
        return OnlyOneWrapper(*[Likwid(group=group, nb_threads=nb_threads) for group in groups])

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
            times = [float(t) for t in f.readlines()]
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
        all_data = all_data.reset_index()
        with open(csv_filename, 'w') as f:
            f.write(all_data.to_csv())
        if compress:
            zip_name = os.path.splitext(csv_filename)[0] + '.zip'
            with zipfile.ZipFile(zip_name, 'w', zipfile.ZIP_DEFLATED) as myzip:
                myzip.write(csv_filename)
            print('Compressed the results: %s' % zip_name)
