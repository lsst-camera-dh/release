import sys
import warnings
import unittest
sys.path.insert(0, '../bin')
from install import Parfile, Installer

class InstallerTestCase(unittest.TestCase):
    "TestCase class for Installer class."

    def setUp(self):
        self.versions_txt = 'test_install_versions.txt'
        self.site = 'SLAC'

    def tearDown(self):
        pass

    def test_Parfile(self):
        "Test Parfile class."
        pars = Parfile(self.versions_txt, 'jh')
        self.assertEqual(pars._cast('None'), None)
        self.assertEqual(pars._cast('3'), 3)
        self.assertAlmostEqual(pars._cast('0.13152'), 0.13152)
        eups_pars = Parfile(self.versions_txt, 'eups_packages')
        self.assertEqual(eups_pars['eotest'], '0.0.18')

    def test_Installer_methods(self):
        "Test various methods of the Installer class."
        installer = Installer(self.versions_txt, site=self.site)

        self.assertEqual(installer.stack_dir, '/nfs/farm/g/lsst/u1/software/redhat6-x86_64-64bit-gcc44/DMstack/v12_0')

        package_name = 'metrology-data-analysis'
        self.assertEqual(installer._env_var(package_name),
                         'METROLOGYDATAANALYSISDIR')

        self.assertEqual(installer._eups_config(), 'setup eotest\n')

        self.assertEqual(installer._schema_paths(), 'export LCATR_SCHEMA_PATH=${HARNESSEDJOBSDIR}/schemas:${LCATR_SCHEMA_PATH}\n')

        self.assertEqual(installer._jh_config(),
                         '''export HARNESSEDJOBSDIR=${INST_DIR}/harnessed-jobs-0.3.49-slac
export VIRTUAL_ENV=${INST_DIR}
source ${INST_DIR}/Modules/3.2.10/init/bash
export PATH=${INST_DIR}/bin:${PATH}
export SITENAME=%s
''' % self.site)

        with warnings.catch_warnings():
            warnings.filterwarnings('ignore')
            self.assertEqual(installer._python_configs(),
                             '''export DATACATDIR=/afs/slac/u/gl/srs/datacat/dev/0.4/lib
export DATACAT_CONFIG=/nfs/farm/g/lsst/u1/software/datacat/config.cfg
export PYTHONPATH=${OFFLINEJOBSDIR}/python:${METROLOGYDATAANALYSISDIR}/python:${DATACATDIR}:${HARNESSEDJOBSDIR}/python::${PYTHONPATH}
''')

        self.assertEqual(installer._package_env_vars(),
                         '''export OFFLINEJOBSDIR=${INST_DIR}/offline-jobs-0.0.16
export METROLOGYDATAANALYSISDIR=${INST_DIR}/metrology-data-analysis-0.0.10
''')

        self.assertEqual(set(installer.package_dirs.keys()),
                         set(('metrology-data-analysis', 'offline-jobs')))

if __name__ == '__main__':
    unittest.main()
