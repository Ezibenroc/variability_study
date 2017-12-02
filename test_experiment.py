#!/usr/bin/env python3

import unittest
import random
from experiment import *
from pandas.util.testing import assert_frame_equal

# From https://stackoverflow.com/a/21000675/4110059
def assertFrameEqual(df1, df2, **kwds ):
    """ Assert that two dataframes are equal, ignoring ordering of columns"""
    return assert_frame_equal(df1.sort_index(axis=1), df2.sort_index(axis=1), check_names=True, **kwds )

class MockProgram(Program):
    header = ['foo', 'bar']

    def __init__(self, idn, suffix_header=False):
        super().__init__()
        self.idn = idn
        if suffix_header: # to have unique header in some test cases
            self.header = ['%s%d' % (h, idn) for h in self.header]

    def __command_line__(self):
        return ['cmd', str(self.idn)]

    def __environment_variables__(self):
        return {'env': str(self.idn)}

    def __fetch_data__(self):
        self.__append_data__({h: self.idn for h in self.header})

class ProgramTest(unittest.TestCase):
    def test_basic(self):
        idn = random.randint(0, 1000)
        mock = MockProgram(idn)
        self.assertEqual(mock.command_line, ['cmd', str(idn)])
        self.assertEqual(mock.environment_variables, {'env': str(idn)})
        assertFrameEqual(mock.data, pandas.DataFrame())
        for i in range(5):
            mock.fetch_data()
            df = pandas.DataFrame({'foo': [mock.idn]*(i+1), 'bar': [mock.idn]*(i+1), 'run_index': list(range(i+1))})
            assertFrameEqual(mock.data, df)

    def test_merge_empty_data(self):
        idn = random.randint(0, 1000)
        mock = MockProgram(idn)
        assertFrameEqual(mock.data, mock.merge_data(pandas.DataFrame()))

    def test_merge_simple_data(self):
        idn = random.randint(0, 1000)
        mock = MockProgram(idn)
        mock.fetch_data()
        mock.fetch_data()
        data_dict = {'x': [1, 2], 'y': ['a', 'b'], 'run_index': [0, 1]}
        other = pandas.DataFrame(data_dict).set_index('run_index')
        data_dict['foo'] = [mock.idn, mock.idn]
        data_dict['bar'] = [mock.idn, mock.idn]
        expected = pandas.DataFrame(data_dict).set_index('run_index')
        result = mock.merge_data(other)
        assertFrameEqual(result, expected)

    def test_merge_missing_data(self):
        idn = random.randint(0, 1000)
        mock = MockProgram(idn)
        max_ind = 5
        for _ in range(max_ind):
            mock.fetch_data()
        data_dict = {'x': [1, 2], 'y': ['a', 'b'], 'run_index': [0, 3]}
        other = pandas.DataFrame(data_dict).set_index('run_index')
        data_dict['foo'] = [mock.idn, mock.idn]
        data_dict['bar'] = [mock.idn, mock.idn]
        nan = float('NaN')
        expected = pandas.DataFrame({
            'x':   [1,   nan, nan, 2,   nan],
            'y':   ['a', nan, nan, 'b', nan],
            'foo': [mock.idn]*max_ind,
            'bar': [mock.idn]*max_ind,
            'run_index': list(range(max_ind))
        }).set_index('run_index')
        result = mock.merge_data(other)
        assertFrameEqual(result, expected)

    def test_merge_missing_data_samekeys(self):
        df1 = pandas.DataFrame({
                'x': list(range(1, 10, 2)),
                'y': list(range(2, 20, 4)),
            })
        df2 = pandas.DataFrame({
                'x': list(range(0, 10, 2)),
                'y': list(range(0, 20, 4)),
            })
        expected = pandas.DataFrame({
                'x': list(range(0, 10)),
                'y': list(range(0, 20, 2)),
            })
        df1 = df1.set_index('x')
        df2 = df2.set_index('x')
        real = MockProgram.__merge_data__(df1, df2).reset_index()
        assertFrameEqual(expected, real)

class ComposeWrapperTest(unittest.TestCase):
    def setUp(self):
        self.programs = [MockProgram(i, suffix_header=True) for i in range(10)]
        self.wrapper = ComposeWrapper(*self.programs)

    def test_command_line(self):
        expected = sum((prog.command_line for prog in self.programs), [])
        self.assertEqual(self.wrapper.command_line, expected)

    def test_environment_variable(self):
        expected = dict()
        for prog in self.programs:
            expected.update(prog.environment_variables)
        self.assertEqual(self.wrapper.environment_variables, expected)

    def test_key(self):
        self.assertEqual(self.wrapper.key, self.programs[0].key) # they all have the same key here

    def test_data(self):
        for _ in range(10):
            self.wrapper.fetch_data()
        expected = pandas.DataFrame()
        for prog in self.programs:
            expected = prog.merge_data(expected)
        expected = expected.reset_index()
        assertFrameEqual(self.wrapper.data, expected)

class DisableWrapperTest(unittest.TestCase):
    def setUp(self):
        self.program = MockProgram(random.randint(1, 1000))
        self.wrapper = DisableWrapper(self.program)

    def test_command_line(self):
        for _ in range(20):
            self.wrapper.enabled = enabled = random.choice([True, False])
            if enabled:
                expected = self.program.command_line
            else:
                expected = []
        self.assertEqual(self.wrapper.command_line, expected)

    def test_environment_variable(self):
        for _ in range(10):
            self.wrapper.enabled = enabled = random.choice([True, False])
            if enabled:
                expected = self.program.environment_variables
            else:
                expected = {}
        self.assertEqual(self.wrapper.environment_variables, expected)

    def test_key(self):
        self.assertEqual(self.wrapper.key, self.program.key)

    def test_data(self):
        enabled_list = []
        for i in range(20):
            self.wrapper.enabled = enabled = random.choice([True, False])
            if enabled:
                enabled_list.append(i)
            self.wrapper.fetch_data()
        expected = pandas.DataFrame({
                'foo': [self.program.idn]*len(enabled_list),
                'bar': [self.program.idn]*len(enabled_list),
                'run_index': enabled_list
            })
        assertFrameEqual(self.wrapper.data, expected)

class OnlyOneWrapperTest(unittest.TestCase):
    def setUp(self):
        self.programs = [MockProgram(i, suffix_header=True) for i in range(10)]
        self.wrapper = OnlyOneWrapper(*self.programs)

    def get_enabled_program(self):
        enabled = [prog for prog in self.wrapper.programs if prog.enabled]
        self.assertEqual(len(enabled), 1)
        prog = enabled[0]
        assert prog is self.wrapper.current_prog
        return prog.program

    def test_enabled(self):
        enabled = {i:0 for i in range(len(self.programs))}
        nb_iter = 1000
        for _ in range(nb_iter):
            self.wrapper.enabled = True
            prog = self.get_enabled_program()
            enabled[prog.idn] += 1
            self.wrapper.fetch_data()
        for val in enabled.values():
            self.assertGreater(val, nb_iter/len(self.programs)*0.7)
            self.assertLess(val, nb_iter/len(self.programs)*1.3)
        data = self.wrapper.data.reset_index()
        self.assertEqual(set(data['run_index']), set(range(nb_iter)))


if __name__ == "__main__":
    unittest.main()
