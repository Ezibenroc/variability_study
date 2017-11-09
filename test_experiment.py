#! /usr/bin/env python3

import unittest
from experiment import *


class MockProgram(Program):
    def __init__(self, index):
        super().__init__()
        self.index = index

    def __command_line__(self):
        return ['cmd %d' % self.index]

    def __environment_variables__(self):
        return {'env %d' % self.index : self.index}

    def __header__(self):
        return ['head %d' % self.index]

    def __data__(self):
        return ['data %d' % self.index]

class BasicProgramTest(unittest.TestCase):
    def test_basic(self):
        prog = MockProgram(3)
        self.assertTrue(prog.enabled)
        self.assertEqual(prog.command_line, ['cmd 3'])
        self.assertEqual(prog.environment_variables, {'env 3' : 3})
        self.assertEqual(prog.header, ['head 3'])
        self.assertEqual(prog.data, ['data 3'])
        prog.enabled = False
        self.assertTrue(prog.enabled)
        # Checking that we can write and read in the tmp file
        expected_content = 'hello world!\n'
        with open(prog.tmp_filename, 'w') as f:
            f.write(expected_content)
        with open(prog.tmp_filename, 'r') as f:
            real_content = f.readlines()
        self.assertEqual([expected_content], real_content)
        del prog

    class WrongMockProgram(MockProgram):
        def __init__(self, size):
            super().__init__(27)
            self.size = size

        def __data__(self):
            return ['data'] * self.size

    def test_wrong_data(self):
        '''
        Test that the size of the data strictly matches the size of the header (1 here).
        '''
        for size in [0, 2, 5]:
            prog = self.WrongMockProgram(size)
            with self.assertRaises(AssertionError):
                data = prog.data
            prog = self.WrongMockProgram(1)
            data = prog.data

class SpecialProgramTest(unittest.TestCase):
    class MockPurePython(PurePythonProgram):
        def __header__(self):
            return ['head']

        def __data__(self):
            return ['data']

    def test_pure_python(self):
        prog = self.MockPurePython()
        self.assertEqual(prog.command_line, [])
        self.assertEqual(prog.environment_variables, {})
        self.assertEqual(prog.header, ['head'])
        self.assertEqual(prog.data, ['data'])

    class MockNoData(NoDataProgram):
        def __command_line__(self):
            return ['cmd']

        def __environment_variables__(self):
            return {'env' : 42}

    def test_pure_python(self):
        prog = self.MockNoData()
        self.assertEqual(prog.command_line, ['cmd'])
        self.assertEqual(prog.environment_variables, {'env' : 42})
        self.assertEqual(prog.header, [])
        self.assertEqual(prog.data, [])

    class MockDisableable(Disableable, MockProgram):
        pass

    def test_pure_python(self):
        prog = self.MockDisableable(42)
        self.assertTrue(prog.enabled)
        self.assertEqual(prog.command_line, ['cmd 42'])
        self.assertEqual(prog.environment_variables, {'env 42' : 42})
        self.assertEqual(prog.header, ['head 42', 'MockDisableable'])
        self.assertEqual(prog.data, ['data 42', True])
        prog.enabled = False
        self.assertFalse(prog.enabled)
        self.assertEqual(prog.command_line, [])
        self.assertEqual(prog.environment_variables, {})
        self.assertEqual(prog.header, ['head 42', 'MockDisableable'])
        self.assertEqual(prog.data, ['N/A', False])

if __name__ == "__main__":
    unittest.main()
