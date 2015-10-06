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
        self.version_file = version_file
        self.pars = Parfile(version_file, section)
        self.inst_dir = inst_dir
        self.hj_folders = hj_folders
        self.site = site
        self._stack_dir = None

    def github_download(self, package_name):
        version = self.pars[package_name]
        url = '/'.join((self._github_org, package_name, 'archive',
                        version + '.tag.gz'))
        commands = ["curl -L -O " + url,
                    "tar xzf %(version).tar.gz" % locals()]
        for command in commands:
            subprocess_call(command, shell=True)

    def lcatr_install(self, package_name):
        self.github_download(package_name)
        command = "cd %(package_name)s-%(version)s/; python setup.py install --prefix=%(inst_dir)s"
        subprocess.call(command, shell=True)

    @property
    def stack_dir(self):
        if self._stack_dir is None:
            pars = Parfile(self.version_file, self.site)
            self._stack_dir = pars['stack_dir']
        return self._stack_dir

    def write_setup(self):
        stack_dir = self.pars['stack_dir']
        inst_dir = self.inst_dir
        hj_version = self.pars['harnessed-jobs']
        site = self.site
        module_path = subprocess.check_output('ls -d %(inst_dir)s/lib/python*/site-packages', shell=True)
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
        output = open('setup.sh', 'w')
        output.write(contents)
        output.close()
    def run(self):
        self.lcatr_install('lcatr-harness')
        self.lcatr_install('lcatr-schema')
        self.lcatr_install('lcatr-modulefiles')
        inst_dir = self.inst_dir
        subprocess.call('ln -sf %(inst_dir)s/share/modulefiles %(inst_dir)s/Modules' % locals(), shell=True)
        subprocess.call('touch `ls -d %(inst_dir)s/lib/python*/site-packages/lcatr`/__init__.py' % locals(), shell=True)
        self.github_download('eotest')
        eotest_version = self.pars['eotest']
        os.chdir('eotest-' + eotest_version)
        commands = ['eups declare eotest %(eotest_version)s -r . -c' % locals(),
                    'setup eotest', 
                    'setup mysqlpython',
                    'scons opt=3']
        for command in commands:
            subprocess.call(command, shell=True)
        os.chdir(inst_dir)
        self.github_download('harnessed-jobs')
        hj_version = self.pars['harnessed-jobs']
        for folder in self.hj_folders:
            os.command('ln -sf %(inst_dir)s/harnessed-jobs-%(hj_version)s/%(folder)s/* %(inst_dir)s/share' % locals(), shell=True)
        self.write_setup()
    def test(self):
        hj_version = self.pars['harnessed-jobs']
        command = 'source ./setup.sh; python harnessed-jobs-%(hj_version)s/tests/setup_test.py'
        subprocess.call(command, shell=True)

if __name__ == '__main__':
    installer = Installer('../versions.txt')
    installer.run()
    installer.test()
