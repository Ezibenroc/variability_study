#! /usr/bin/env python3

import unittest
from experiment import *


class MockProgram(Program):
    def __command_line__(self):
        return ['cmd']

    def __environment_variables__(self):
        return ['env']

    def __header__(self):
        return ['head']

    def __data__(self):
        return ['data']

class BasicProgramTest(unittest.TestCase):

    def test_basic(self):
        prog = MockProgram()
        self.assertEqual(prog.command_line, ['cmd'])
        self.assertEqual(prog.environment_variables, ['env'])
        self.assertEqual(prog.header, ['head'])
        self.assertEqual(prog.data, ['data'])
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
            super().__init__()
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

if __name__ == "__main__":
    unittest.main()
