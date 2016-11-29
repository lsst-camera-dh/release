#!/usr/bin/env python
import unittest

loader = unittest.TestLoader()
testsuite = loader.discover('.', pattern='test_*.py')

runner = unittest.TextTestRunner()
runner.run(testsuite)
