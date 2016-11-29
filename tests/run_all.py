#!/usr/bin/env python
import sys
import unittest

loader = unittest.TestLoader()
testsuite = loader.discover('.', pattern='test_*.py')

runner = unittest.TextTestRunner()
result = runner.run(testsuite)

sys.exit(len(result.failures) + len(result.errors))
