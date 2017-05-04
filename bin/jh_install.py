#!/usr/bin/env python
"Installtion script for Job Harness-related code."
from __future__ import print_function, absolute_import
import os
import glob
import shutil
import subprocess
import warnings
import ConfigParser
import argparse
import utilities

_executable = '/bin/bash'

class JhInstaller(object):
    "Class to install Job Harness-related packages."
    def __init__(self, version_file, inst_dir='.',
                 hj_folders=('BNL_T03',), site='BNL', orgs=None):
        self.version_file = os.path.abspath(version_file)
        if inst_dir is not None:
            self.inst_dir = os.path.abspath(inst_dir)
            shutil.copy(self.version_file,
                        os.path.join(self.inst_dir, 'installed_versions.txt'))
        self.hj_folders = hj_folders
        self.site = site
        if orgs is None:
            orgs = ('lsst-camera-dh', 'lsst-camera-electronics')
        self._gh_accessor = utilities.GitHubAccessor(orgs)
        self._package_dirs = None
        self._stack_dir = None
        self._datacat_pars = None
        self.curdir = os.path.abspath('.')
        try:
            self.pars = utilities.Parfile(self.version_file, 'jh')
        except ConfigParser.NoSectionError:
            pass

    def modules_install(self):
        "Function to install the modules package"
        url = 'http://sourceforge.net/projects/modules/files/Modules/modules-3.2.10/modules-3.2.10.tar.gz'
        inst_dir = self.inst_dir
        commands = ";".join(["curl -L -O %(url)s",
                             "tar xzf modules-3.2.10.tar.gz",
                             "cd modules-3.2.10",
                             "./configure --prefix=%(inst_dir)s",
                             "make",
                             "make install",
                             "cd %(inst_dir)s"]) % locals()
        subprocess.call(commands, shell=True, executable=_executable)

    def lcatr_install(self, package_name):
        "Function to install an lcatr package."
        version = self.pars[package_name]
        self._gh_accessor.download(package_name, version)
        inst_dir = self.inst_dir
        command = "cd %(package_name)s-%(version)s/; python setup.py install --prefix=%(inst_dir)s" % locals()
        subprocess.call(command, shell=True, executable=_executable)

    @property
    def package_dirs(self):
        "Directories of the the installed packages."
        if self._package_dirs is None:
            self._package_dirs = {}
            try:
                pars = utilities.Parfile(self.version_file, 'packages')
                for package, version in pars.items():
                    package_dir = "%(package)s-%(version)s" % locals()
                    self._package_dirs[package] = os.path.join(self.inst_dir,
                                                               package_dir)
            except ConfigParser.NoSectionError:
                pass
        return self._package_dirs

    @property
    def stack_dir(self):
        "Directory where the LSST Stack has been installed."
        if self._stack_dir is None:
            try:
                pars = utilities.Parfile(self.version_file, 'dmstack')
                self._stack_dir = pars['stack_dir']
            except ConfigParser.NoSectionError:
                pass
        return self._stack_dir

    @property
    def datacat_pars(self):
        "The datacat module parameters: install path and config file"
        if self._datacat_pars is None:
            try:
                self._datacat_pars =\
                    utilities.Parfile(self.version_file, 'datacat')
            except ConfigParser.NoSectionError:
                pass
        return self._datacat_pars

    def write_setup(self):
        "Write the bash setup file for running harnessed jobs."
        contents = "export INST_DIR=%s\n" % self.inst_dir
        if self.stack_dir is not None:
            contents += """export STACK_DIR=%s
source ${STACK_DIR}/loadLSST.bash
export EUPS_PATH=${INST_DIR}/eups:${EUPS_PATH}
""" % self.stack_dir

        contents += self._eups_config()
        contents += self._jh_config()
        contents += self._package_env_vars()
        contents += self._schema_paths()
        contents += self._python_configs()
        contents += 'PS1="[jh]$ "\n'

        output = open(os.path.join(self.inst_dir, 'setup.sh'), 'w')
        output.write(contents)
        output.close()

    def _eups_config(self):
        "Setup commands for EUPS-installed packages."
        try:
            pars = utilities.Parfile(self.version_file, 'eups_packages')
        except ConfigParser.NoSectionError:
            return ''
        return '\n'.join(['setup %s' % package for package in pars]) + '\n'

    def _jh_config(self):
        "Setup commands for harnessed-jobs package."
        bin_dirs = [os.path.join('${INST_DIR}', os.path.split(x)[-1], 'bin')
                    for x in self.package_dirs.values()
                    if os.path.isdir(os.path.join(x, 'bin'))]
        bin_path = ":".join(bin_dirs + ['${INST_DIR}/bin', '${PATH}'])
        hj_version = self.pars['harnessed-jobs']
        site = self.site
        return """export HARNESSEDJOBSDIR=${INST_DIR}/harnessed-jobs-%(hj_version)s
export VIRTUAL_ENV=${INST_DIR}
source ${INST_DIR}/Modules/3.2.10/init/bash
export PATH=%(bin_path)s
export SITENAME=%(site)s
""" % locals()

    def _schema_paths(self):
        "Setup command for the LCATR_SCHEMA_PATH environment variable."
        paths = []
        for package, package_dir in self.package_dirs.items():
            if not os.path.isdir(os.path.join(package_dir, 'schemas')):
                continue
            paths.append("${%s}/schemas" % utilities.make_env_var(package))
        paths.extend(['${HARNESSEDJOBSDIR}/schemas', '${LCATR_SCHEMA_PATH}'])
        return 'export LCATR_SCHEMA_PATH=' + ':'.join(paths) + '\n'

    def _package_env_vars(self):
        "Setup commands for the package directory environment variables."
        contents = ""
        for package, package_dir in self.package_dirs.items():
            subdir = os.path.split(package_dir.rstrip(os.path.sep))[-1]
            env_var = utilities.make_env_var(package)
            contents += ("export %s=${INST_DIR}/%s\n" % (env_var, subdir))
        return contents

    def _module_path(self):
        "Path to site-packages-installed modules."
        try:
            module_path = glob.glob('%s/lib/python*/site-packages'
                                    % self.inst_dir)[0][len(self.inst_dir):]
            return os.path.join('${INST_DIR}', module_path.lstrip(os.path.sep))
        except IndexError:
            message = "%s/lib/python*/site-packages not found." % self.inst_dir
            warnings.warn(message)
            return ''

    def _python_configs(self):
        "Setup commands for PYTHONPATH, etc.."
        python_dirs = [os.path.join('${'+utilities.make_env_var(x)+'}',
                                    'python') for x in self.package_dirs]
        datacat_pars = self.datacat_pars
        if datacat_pars is not None:
            python_dirs.append('${DATACATDIR}')
        python_dirs.extend(['${HARNESSEDJOBSDIR}/python', self._module_path(),
                            '${PYTHONPATH}'])
        python_configs = ''
        if datacat_pars is not None:
            python_configs += """export DATACATDIR=%s/lib
export DATACAT_CONFIG=%s
""" % (os.path.join(datacat_pars['datacatdir']), datacat_pars['datacat_config'])
        python_configs += "export PYTHONPATH=%s\n" % ":".join(python_dirs)
        return python_configs

    def jh(self):
        "Install the Job Harness (lcatr-related) code."
        os.chdir(self.inst_dir)
        self.modules_install()
        self.lcatr_install('lcatr-harness')
        self.lcatr_install('lcatr-schema')
        self.lcatr_install('lcatr-modulefiles')
        inst_dir = self.inst_dir
        subprocess.call('ln -sf %(inst_dir)s/share/modulefiles %(inst_dir)s/Modules' % locals(), shell=True, executable=_executable)
        subprocess.call('touch `ls -d %(inst_dir)s/lib/python*/site-packages/lcatr`/__init__.py' % locals(), shell=True, executable=_executable)
        hj_version = self.pars['harnessed-jobs']
        self._gh_accessor.download('harnessed-jobs', hj_version)
        for folder in self.hj_folders:
            subprocess.call('ln -sf %(inst_dir)s/harnessed-jobs-%(hj_version)s/%(folder)s/* %(inst_dir)s/share' % locals(), shell=True, executable=_executable)
        self.eups_package_installer()
        self.package_installer()
        self.write_setup()
        os.chdir(self.curdir)

    def eups_package_installer(self):
        "Install an eups-supported package."
        try:
            pars = utilities.Parfile(self.version_file, 'eups_packages')
        except ConfigParser.NoSectionError:
            return
        inst_dir = self.inst_dir
        stack_dir = self.stack_dir.rstrip(os.path.sep)
        ups_db_dir = '%(inst_dir)s/eups/ups_db' % locals()
        if not os.path.isdir(ups_db_dir):
            os.makedirs(ups_db_dir)
        for package, version in pars.items():
            self._gh_accessor.download(package, version)
            commands = """source %(stack_dir)s/loadLSST.bash; export EUPS_PATH=%(inst_dir)s/eups:${EUPS_PATH}; cd %(package)s-%(version)s/; eups declare %(package)s %(version)s -r . -c; setup %(package)s; scons opt=3""" % locals()
            subprocess.call(commands, shell=True, executable=_executable)

    def package_installer(self):
        "Install a generic package that may contain harnessed jobs."
        try:
            pars = utilities.Parfile(self.version_file, 'packages')
        except ConfigParser.NoSectionError:
            return
        inst_dir = self.inst_dir
        for package, version in pars.items():
            self._gh_accessor.download(package, version)
            package_dir = "%(package)s-%(version)s" % locals()
            hj_dir = "%(inst_dir)s/%(package_dir)s/harnessed_jobs" % locals()
            if os.path.isdir(hj_dir):
                command = 'ln -sf %(hj_dir)s/* %(inst_dir)s/share' % locals()
                subprocess.call(command, executable=_executable,
                                shell=True)

    def jh_test(self):
        "Sanity check for package list installations that include eotest"
        os.chdir(self.inst_dir)
        try:
            pars = utilities.Parfile(self.version_file, 'eups_packages')
            pars['eotest']
            hj_version = self.pars['harnessed-jobs']
            command = 'source ./setup.sh; python harnessed-jobs-%(hj_version)s/tests/setup_test.py' % locals()
            subprocess.call(command, shell=True, executable=_executable)
            os.chdir(self.curdir)
        except (ConfigParser.NoSectionError, KeyError):
            pass

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Job Harness Installer")
    parser.add_argument("version_file", help='software version file')
    parser.add_argument('--inst_dir', type=str, default=None,
                        help='installation directory')
    parser.add_argument('--site', type=str, default='SLAC',
                        help='Site (SLAC, BNL, etc.)')
    parser.add_argument('--hj_folders', type=str, default="SLAC")

    args = parser.parse_args()
    installer = JhInstaller(args.version_file, inst_dir=args.inst_dir,
                            hj_folders=args.hj_folders.split(), site=args.site)

    installer.jh()
    installer.jh_test()
