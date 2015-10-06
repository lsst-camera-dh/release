#!/usr/bin/env python
import os
import subprocess
import ConfigParser

class Parfile(dict):
    def __init__(self, infile, section):
        super(Parfile, self).__init__()
        parser = ConfigParser.ConfigParser()
        parser.read(infile)
        for key, value in parser.items(section):
            self[key] = self._cast(value)
    def _cast(self, value):
        if value == 'None':
            return None
        try:
            if value.find('.') == -1 and value.find('e') == -1:
                return int(value)
            else:
                return float(value)
        except ValueError:
            # Cannot cast as either int or float so just return the
            # value as-is (presumably a string).
            return value

class Installer(object):
    _github_org = 'https://github.com/lsst-camera-dh'
    def __init__(self, version_file, section='dev', inst_dir='.',
                 hj_folders=('BNL_T03',), site='BNL'):
        self.version_file = os.path.abspath(version_file)
        self.pars = Parfile(self.version_file, section)
        self.inst_dir = os.path.abspath(inst_dir)
        self.hj_folders = hj_folders
        self.site = site
        self._stack_dir = None
        self.curdir = os.path.abspath('.')

    def modules_install(self):
        url = 'http://sourceforge.net/projects/modules/files/Modules/modules-3.2.10/modules-3.2.10.tar.gz'
        inst_dir = self.inst_dir
        commands = ";".join(["curl -L -O %(url)s",
                             "tar xzf modules-3.2.10.tar.gz",
                             "cd modules-3.2.10",
                             "./configure --prefix=%(inst_dir)s --with-tcl-lib=/usr/lib --with-tcl-inc=/usr/include",
                             "make",
                             "make install",
                             "cd %(inst_dir)s"]) % locals()
        subprocess.call(commands, shell=True)

    def github_download(self, package_name):
        version = self.pars[package_name]
        url = '/'.join((self._github_org, package_name, 'archive',
                        version + '.tar.gz'))
        commands = ["curl -L -O " + url,
                    "tar xzf %(version)s.tar.gz" % locals()]
        for command in commands:
            subprocess.call(command, shell=True)

    def lcatr_install(self, package_name):
        self.github_download(package_name)
        version = self.pars[package_name]
        inst_dir = self.inst_dir
        command = "cd %(package_name)s-%(version)s/; python setup.py install --prefix=%(inst_dir)s" % locals()
        subprocess.call(command, shell=True)

    @property
    def stack_dir(self):
        if self._stack_dir is None:
            pars = Parfile(self.version_file, self.site)
            self._stack_dir = pars['stack_dir']
        return self._stack_dir

    def write_setup(self):
        stack_dir = self.stack_dir
        inst_dir = self.inst_dir
        hj_version = self.pars['harnessed-jobs']
        site = self.site
        module_path = subprocess.check_output('ls -d %(inst_dir)s/lib/python*/site-packages' % locals(), shell=True).strip()
        contents = """export STACK_DIR=%(stack_dir)s
source ${STACK_DIR}/loadLSST.bash
export INST_DIR=%(inst_dir)s
export EUPS_PATH=${INST_DIR}/eups:${EUPS_PATH}
setup eotest
setup mysqlpython
export VIRTUAL_ENV=${INST_DIR}
source ${INST_DIR}/Modules/3.2.10/init/bash
export DATACATPATH=/afs/slac/u/gl/srs/datacat/dev/0.3/lib
export HARNESSEDJOBSDIR=${INST_DIR}/harnessed-jobs-%(hj_version)s
export PYTHONPATH=${DATACATPATH}:${HARNESSEDJOBSDIR}/python:%(module_path)s:${PYTHONPATH}
export PATH=${INST_DIR}/bin:${PATH}
export SITENAME=%(site)s
export LCATR_SCHEMA_PATH=${HARNESSEDJOBSDIR}/schemas:${LCATR_SCHEMA_PATH}
PS1="[jh]$ "
""" % locals()
        output = open(os.path.join(self.inst_dir, 'setup.sh'), 'w')
        output.write(contents)
        output.close()
    def run(self):
        os.chdir(self.inst_dir)
        self.modules_install()
        self.lcatr_install('lcatr-harness')
        self.lcatr_install('lcatr-schema')
        self.lcatr_install('lcatr-modulefiles')
        inst_dir = self.inst_dir
        subprocess.call('ln -sf %(inst_dir)s/share/modulefiles %(inst_dir)s/Modules' % locals(), shell=True)
        subprocess.call('touch `ls -d %(inst_dir)s/lib/python*/site-packages/lcatr`/__init__.py' % locals(), shell=True)
        self.github_download('eotest')
        stack_dir = self.stack_dir
        eotest_version = self.pars['eotest']
        commands = """source %(stack_dir)s/loadLSST.bash; mkdir -p %(inst_dir)s/eups/ups_db; export EUPS_PATH=%(inst_dir)s/eups:${EUPS_PATH}; cd eotest-%(eotest_version)s/; eups declare eotest %(eotest_version)s -r . -c; setup eotest; setup mysqlpython; scons opt=3""" % locals()
        subprocess.call(commands, shell=True)
        self.github_download('harnessed-jobs')
        hj_version = self.pars['harnessed-jobs']
        for folder in self.hj_folders:
            subprocess.call('ln -sf %(inst_dir)s/harnessed-jobs-%(hj_version)s/%(folder)s/* %(inst_dir)s/share' % locals(), shell=True)
        self.write_setup()
        os.chdir(self.curdir)
    def test(self):
        os.chdir(self.inst_dir)
        hj_version = self.pars['harnessed-jobs']
        command = 'source ./setup.sh; python harnessed-jobs-%(hj_version)s/tests/setup_test.py' % locals()
        subprocess.call(command, shell=True)
        os.chdir(self.curdir)

if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description="Job Harness Installer")
    parser.add_argument('version_file', help='software version file')
    parser.add_argument('--inst_dir', type=str, default='.',
                        help='installation directory')
    parser.add_argument('--site', type=str, default='BNL',
                        help='Site (BNL, SLAC, etc.)')
    parser.add_argument('--hj_folders', type=str, default="BNL_TO3")

    args = parser.parse_args()

    installer = Installer(args.version_file, inst_dir=args.inst_dir,
                          hj_folders=args.hj_folders.split(), site=args.site)
    installer.run()
    installer.test()
