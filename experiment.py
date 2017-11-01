import tempfile
import os
import abc
import re
import itertools
import time

from runner import run_command, compile_generic

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
        return ['size', 'nb_calls', 'time']

    def data(self, output):
        output = output[0].decode('utf8').strip()
        times = output.split('\n')
        return [(self.size, self.nb_calls, float(t)) for t in times]

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
        wrapper_data = [wrap.data(self.output) for wrap in self.wrappers]
        app_data = self.application.data(self.output)
        data = []
        for entry in app_data:
            data.append(list(itertools.chain(*[*wrapper_data, entry])))
        return data

if __name__ == '__main__':
    example = ExpEngine(application=Dgemm(lib='naive', size=300, nb_calls=3),
            wrappers=[
                    Date(),
                    Intercoolr(),
                ])
    for i in range(3):
        example.run()
        print(example.header)
        data = example.data
        for row in data:
            print(row)
