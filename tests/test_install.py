import os
import unittest
import subprocess

running_at_slac = \
    subprocess.check_output('hostname -d', shell=True) == 'slac.stanford.edu\n'

@unittest.skipUnless(running_at_slac, "Not running at slac")
class InstallTestCase(unittest.TestCase):
    "TestCase class for jh_install.py execution."

    def setUp(self):
        self.inst_dir = 'tmp'
        subprocess.call('rm -rf %s/' % self.inst_dir, shell=True)
        os.mkdir(self.inst_dir)

    def tearDown(self):
        os.remove('install.log')
        subprocess.call('rm -rf %s/' % self.inst_dir, shell=True)

    def test_install_py(self):
        "Test jh_install.py"
        command = '(../bin/jh_install.py --inst_dir %s test_install_versions.txt) >& install.log' % self.inst_dir
        self.assertEqual(subprocess.check_call(command, shell=True,
                                               executable='/bin/bash'), 0)
        command = 'source %s/setup.sh; python -c "import siteUtils; import metUtils; import vendorFitsTranslators; import eotestUtils; import lsst.eotest.sensor"' % self.inst_dir
        self.assertEqual(subprocess.check_call(command, shell=True,
                                               executable='/bin/bash'), 0)
        args = ('source %s/setup.sh; python -c "import foobar"'
                % self.inst_dir,)
        kwds = dict(shell=True, executable='/bin/bash',
                    stderr=subprocess.STDOUT)
        self.assertRaises(subprocess.CalledProcessError,
                          subprocess.check_output, *args, **kwds)

        self.assertTrue(os.path.isfile(os.path.join(self.inst_dir,
                                                    'installed_versions.txt')))

if __name__ == '__main__':
    unittest.main()
