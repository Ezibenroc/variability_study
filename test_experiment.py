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
        return {'env %d' % self.index : str(self.index)}

    def __header__(self):
        return ['head %d' % self.index]

    def __data__(self):
        return ['data %d' % self.index]

class MockPurePython(PurePythonProgram):
    def __header__(self):
        return ['head']

    def __data__(self):
        return ['data']

class MockNoData(NoDataProgram):
    def __command_line__(self):
        return ['cmd']

    def __environment_variables__(self):
        return {'env' : '42'}

class MockDisableable(Disableable, MockProgram):
    pass

class MockApplication(MockProgram):
    def __init__(self):
        super().__init__(-1)

    def __header__(self):
        return ['header_app_1', 'header_app_2', 'header_app_3']

    def __data__(self):
        return [['data_1:1', 'data_1:2'], ['data_2:1', 'data_2:2'], ['data_3:1', 'data_3:2']]

class BasicProgramTest(unittest.TestCase):
    def test_basic(self):
        prog = MockProgram(3)
        self.assertTrue(prog.enabled)
        self.assertEqual(prog.command_line, ['cmd 3'])
        self.assertEqual(prog.environment_variables, {'env 3' : '3'})
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

    def test_pure_python(self):
        prog = MockPurePython()
        self.assertEqual(prog.command_line, [])
        self.assertEqual(prog.environment_variables, {})
        self.assertEqual(prog.header, ['head'])
        self.assertEqual(prog.data, ['data'])

    def test_pure_python(self):
        prog = MockNoData()
        self.assertEqual(prog.command_line, ['cmd'])
        self.assertEqual(prog.environment_variables, {'env' : '42'})
        self.assertEqual(prog.header, [])
        self.assertEqual(prog.data, [])

    def test_pure_python(self):
        prog = MockDisableable(42)
        self.assertTrue(prog.enabled)
        self.assertEqual(prog.command_line, ['cmd 42'])
        self.assertEqual(prog.environment_variables, {'env 42' : '42'})
        self.assertEqual(prog.header, ['head 42', 'MockDisableable'])
        self.assertEqual(prog.data, ['data 42', True])
        prog.enabled = False
        self.assertFalse(prog.enabled)
        self.assertEqual(prog.command_line, [])
        self.assertEqual(prog.environment_variables, {})
        self.assertEqual(prog.header, ['head 42', 'MockDisableable'])
        self.assertEqual(prog.data, ['N/A', False])

class ExpEngineTest(unittest.TestCase):
    def setUp(self):
        self.application = MockApplication()
        self.wrappers=[MockDisableable(i) for i in range(50)]
        self.programs = self.wrappers + [self.application]
        self.expengine = ExpEngine(application=self.application, wrappers=self.wrappers)

    def test_basic(self):
        self.assertEqual(self.expengine.header, sum((prog.header for prog in self.programs), []))
        self.assertEqual(self.expengine.command_line, sum((prog.command_line for prog in self.programs), []))
        expected_env = {}
        for prog in self.programs:
            expected_env.update(prog.environment_variables)
        self.assertEqual(self.expengine.environment_variables, expected_env)
        data = self.expengine.data
        for entry_id, entry in enumerate(self.expengine.data):
            for wrap in self.wrappers:
                for i, h in enumerate(wrap.header):
                    index = self.expengine.header.index(h)
                    self.assertEqual(wrap.data[i], entry[index])
            for i, h in enumerate(self.application.header):
                index = self.expengine.header.index(h)
                self.assertEqual(self.application.data[i][entry_id], entry[index])


    def test_enable(self):
        self.expengine.randomly_enable()
        self.assertIn(True,  [prog.enabled for prog in self.wrappers]) # probability 2^-50 to fail
        self.assertIn(False, [prog.enabled for prog in self.wrappers]) # probability 2^-50 to fail
        self.expengine.enable_all()
        self.assertEqual([True]*len(self.wrappers), [wrap.enabled for wrap in self.wrappers])
        self.expengine.disable_all()
        self.assertEqual([False]*len(self.wrappers), [wrap.enabled for wrap in self.wrappers])

    class DummyTime(MockDisableable):
        def __command_line__(self):
            return ['time']

    class DummyPwd(MockApplication):
        def __command_line__(self):
            return ['pwd']

    def test_run(self):
        initial_environ = dict(os.environ)
        application=self.DummyPwd()
        wrappers=[self.DummyTime(i) for i in range(10)]
        exp = ExpEngine(application=application, wrappers=wrappers)

        exp.disable_all()
        exp.run()
        expected = dict(initial_environ)
        expected.update(application.environment_variables)
        self.assertEqual(expected, dict(os.environ))

        exp.enable_all()
        exp.run()
        expected = dict(initial_environ)
        expected.update(application.environment_variables)
        for wrap in wrappers:
            expected.update(wrap.environment_variables)
        self.assertEqual(expected, dict(os.environ))

        exp.disable_all()
        exp.run()
        expected = dict(initial_environ)
        expected.update(application.environment_variables)
        self.assertEqual(expected, dict(os.environ))

        for _ in range(10):
            exp.randomly_enable()
            exp.run()
            expected = dict(initial_environ)
            expected.update(application.environment_variables)
            for wrap in wrappers:
                if wrap.enabled: # being paranoid, useless if statement if everything is coded correctly
                    expected.update(wrap.environment_variables)
            self.assertEqual(expected, dict(os.environ))

if __name__ == "__main__":
    unittest.main()
