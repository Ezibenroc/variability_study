import tempfile
import os
import abc
import re
import itertools
import time
import platform
import psutil
import csv
import cpuinfo # https://github.com/workhorsy/py-cpuinfo
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

    @abc.abstractmethod
    def data(self, output):
        pass

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

    def data(self, _):
        reg = re.compile('# ENERGY=')
        with open(self.tmp_filename) as f:
            for line in f:
                m = reg.match(line)
                if m is not None:
                    return [float(line[m.end():])]

class Date(Program):
    def __init__(self):
        super().__init__()
        self.date = time.strftime("%Y/%m/%d")

    @property
    def command_line(self):
        return []

    @property
    def header(self):
        return ['date']

    def data(self, output):
        return [self.date]

class Platform(Program):
    def __init__(self):
        super().__init__()
        self.hostname = platform.node()
        self.os = platform.platform()

    @property
    def command_line(self):
        return []

    @property
    def header(self):
        return ['hostname', 'os']

    def data(self, output):
        return [self.hostname, self.os]

class CPU(Program):
    @property
    def command_line(self):
        return []

    @property
    def header(self):
        return ['cpu_model',
                'nb_cores',
                'advertised_frequency',
                'current_frequency',
                'cache_size',
            ]

    def data(self, output):
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

class Temperature(Program):
    @property
    def command_line(self):
        return []

    @property
    def header(self):
        return ['average_temperature']

    def data(self, output):
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

    def data(self, output):
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

class Dgemm(Program):
    def __init__(self, lib, size, nb_calls):
        super().__init__()
        self.lib = lib
        self.size = size
        self.nb_calls = nb_calls
        compile_generic('multi_dgemm', lib)

    @property
    def command_line(self):
        return ['./multi_dgemm', str(self.nb_calls), str(self.size)]

    @property
    def header(self):
        return ['call_index', 'size', 'nb_calls', 'time']

    def data(self, output):
        output = output[0].decode('utf8').strip()
        times = output.split('\n')
        return [(call_index, self.size, self.nb_calls, float(t)) for call_index, t in enumerate(times)]

class ExpEngine:
    def __init__(self, csv_filename, application, wrappers):
        self.csv_filename = csv_filename
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
        wrapper_data = [wrap.data(self.output) for wrap in self.wrappers]
        app_data = self.application.data(self.output)
        data = []
        for entry in app_data:
            data.append(list(itertools.chain(*[*wrapper_data, entry])))
        return data

    def run_all(self, nb_runs):
        with open(self.csv_filename, 'w') as f:
            writer = csv.writer(f)
            header = ['run_index'] + self.header
            writer.writerow(header)
            for run_index in range(nb_runs):
                self.run()
                for line in self.data:
                    writer.writerow([run_index] + line)


if __name__ == '__main__':
    example = ExpEngine(csv_filename='/tmp/bla.csv', application=Dgemm(lib='naive', size=300, nb_calls=3),
            wrappers=[
                    Date(),
                    Platform(),
                    CPU(),
                    Temperature(),
                    Perf(),
                    Intercoolr(),
                ])
    example.run_all(3)
