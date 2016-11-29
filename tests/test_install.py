import os
import unittest
import subprocess

running_at_slac = \
    subprocess.check_output('hostname -d', shell=True) == 'slac.stanford.edu\n'

@unittest.skipUnless(running_at_slac, "Not runnining at slac")
class InstallTestCase(unittest.TestCase):
    "TestCase class for install.py execution."

    def setUp(self):
        subprocess.call('rm -rf tmp/', shell=True)
        os.mkdir('tmp')

    def tearDown(self):
        os.remove('install.log')
        subprocess.call('rm -rf tmp/', shell=True)

    def test_install_py(self):
        "Test install.py"
        command = '(../bin/install.py --inst_dir tmp test_install_versions.txt) >& install.log'
        self.assertEqual(subprocess.check_call(command, shell=True), 0)
        command = 'source tmp/setup.sh; python -c "import siteUtils; import metUtils; import vendorFitsTranslators; import eotestUtils; import lsst.eotest.sensor"'
        self.assertEqual(subprocess.check_call(command, shell=True), 0)

if __name__ == '__main__':
    unittest.main()
