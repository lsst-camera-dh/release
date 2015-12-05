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
    def __init__(self, version_file, inst_dir='.',
                 hj_folders=('BNL_T03',), site='BNL'):
        self.version_file = os.path.abspath(version_file)
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
        subprocess.call(commands, shell=True, executable="/bin/bash")

    def github_download(self, package_name):
        version = self.pars[package_name]
        url = '/'.join((self._github_org, package_name, 'archive',
                        version + '.tar.gz'))
        commands = ["curl -L -O " + url,
                    "tar xzf %(version)s.tar.gz" % locals()]
        for command in commands:
            subprocess.call(command, shell=True, executable="/bin/bash")

    def lcatr_install(self, package_name):
        self.github_download(package_name)
        version = self.pars[package_name]
        inst_dir = self.inst_dir
        command = "cd %(package_name)s-%(version)s/; python setup.py install --prefix=%(inst_dir)s" % locals()
        subprocess.call(command, shell=True, executable="/bin/bash")

    @property
    def stack_dir(self):
        if self._stack_dir is None:
            pars = Parfile(self.version_file, self.site)
            self._stack_dir = pars['stack_dir']
        return self._stack_dir

    def write_setup(self):
        stack_dir = self.stack_dir
        inst_dir = self.inst_dir
        #
        # Read in packageLists/Externals_versions.txt assuming it lives 
        # relative to the location of this script in the release pacakge.
        #
        extfile = os.path.join(os.path.dirname(os.path.abspath(__file__)), 
                               '..', 'packageLists', 'Externals_versions.txt')
        datacatpath = os.path.join(Parfile(extfile, 'externals')['datacat'],
                                   'lib')
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
export DATACATPATH=%(datacatpath)s/lib
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

    def jh(self, prod=False, section='jh_dev'):
        os.chdir(self.inst_dir)
        if prod:
            section = 'jh_prod'
            print "Installing production versions of Job Harness software"
        self.pars = Parfile(self.version_file, section)
        self.modules_install()
        self.lcatr_install('lcatr-harness')
        self.lcatr_install('lcatr-schema')
        self.lcatr_install('lcatr-modulefiles')
        inst_dir = self.inst_dir
        subprocess.call('ln -sf %(inst_dir)s/share/modulefiles %(inst_dir)s/Modules' % locals(), shell=True, executable="/bin/bash")
        subprocess.call('touch `ls -d %(inst_dir)s/lib/python*/site-packages/lcatr`/__init__.py' % locals(), shell=True, executable="/bin/bash")
        self.github_download('eotest')
        stack_dir = self.stack_dir
        eotest_version = self.pars['eotest']
        commands = """source %(stack_dir)s/loadLSST.bash; mkdir -p %(inst_dir)s/eups/ups_db; export EUPS_PATH=%(inst_dir)s/eups:${EUPS_PATH}; cd eotest-%(eotest_version)s/; eups declare eotest %(eotest_version)s -r . -c; setup eotest; setup mysqlpython; scons opt=3""" % locals()
        subprocess.call(commands, shell=True, executable="/bin/bash")
        self.github_download('harnessed-jobs')
        hj_version = self.pars['harnessed-jobs']
        for folder in self.hj_folders:
            subprocess.call('ln -sf %(inst_dir)s/harnessed-jobs-%(hj_version)s/%(folder)s/* %(inst_dir)s/share' % locals(), shell=True, executable="/bin/bash")
        self.write_setup()
        os.chdir(self.curdir)

    def jh_test(self):
        os.chdir(self.inst_dir)
        hj_version = self.pars['harnessed-jobs']
        command = 'source ./setup.sh; python harnessed-jobs-%(hj_version)s/tests/setup_test.py' % locals()
        subprocess.call(command, shell=True, executable="/bin/bash")
        os.chdir(self.curdir)

    def _ccs_download(self, package_name, sub_system):
        base_url = "http://dev.lsstcorp.org:8081/nexus/service/local/artifact/maven/redirect?r=ccs-maven2-public&g=org.lsst"
        command = 'wget "%(base_url)s&a=%(package_name)s&v=%(sub_system)s&e=zip&c=dist" -O temp.zip' % locals()
        subprocess.call(command, shell=True, executable="/bin/bash")
        subdir = '-'.join((package_name, sub_system))
        if os.path.isdir(subdir):
            subprocess.call('rm -r %(subdir)s' % locals(), shell=True, executable="/bin/bash")
        subprocess.call('unzip -uo temp.zip', shell=True, executable="/bin/bash")
        subprocess.call('rm temp.zip', shell=True, executable="/bin/bash")
        subprocess.call('ln -sf %(subdir)s %(package_name)s' % locals(), shell=True, executable="/bin/bash")

    def ccs(self, inst_dir, prod=False, section='ccs_dev'):
        os.chdir(inst_dir)
        if prod:
            section = 'ccs_prod'
            print "Installing production versions of CCS software"
        pars = Parfile(self.version_file, section)
        for package in ['org-lsst-ccs-subsystem-' + x for x in 
                        'archon-main archon-gui'.split()]:
            self._ccs_download(package, pars['archon'])
        for package in ['org-lsst-ccs-subsystem-' + x for x in 
                        'teststand-main teststand-gui'.split()]:
            self._ccs_download(package, pars['teststand'])
        self._ccs_download('org-lsst-ccs-localdb-main', pars['localdb'])
        self._ccs_download('org-lsst-ccs-subsystem-console', pars['console'])

        try:
            os.mkdir('bin')
        except OSError:
            # bin directory already exists(?)
            pass
        os.chdir('bin')
        commands = """ln -sf ../org-lsst-ccs-subsystem-teststand-main/bin/CCSbootstrap.sh ts
ln -sf ../org-lsst-ccs-subsystem-teststand-main/bin/CCSbootstrap.sh tsSim
ln -sf ../org-lsst-ccs-subsystem-archon-main/bin/CCSbootstrap.sh archon
ln -sf ../org-lsst-ccs-subsystem-archon-main/bin/CCSbootstrap.sh archonSim
ln -sf ../org-lsst-ccs-subsystem-teststand-gui/bin/CCSbootstrap.sh CCS-Console
ln -sf ../org-lsst-ccs-subsystem-teststand-main/bin/CCSbootstrap.sh JythonConsole
ln -sf ../org-lsst-ccs-subsystem-teststand-main/bin/CCSbootstrap.sh ShellCommandConsole
ln -sf ../org-lsst-ccs-localdb-main/bin/trendingPersister.sh trendingPersister.sh
ln -sf ../org-lsst-ccs-localdb-main/bin/trendingServer.sh trendingServer
ln -sf ../org-lsst-ccs-subsystem-teststand-gui/bin/tsJas.sh tsGui
""".split('\n')
        for command in commands:
            subprocess.call(command, shell=True, executable="/bin/bash")
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
    parser.add_argument('--ccs_inst_dir', type=str, default=None)
    parser.add_argument('--prod', action='store_true', default=False,
                        help='Install production versions')

    args = parser.parse_args()
    
    installer = Installer(args.version_file, inst_dir=args.inst_dir,
                          hj_folders=args.hj_folders.split(), site=args.site)
    installer.jh(prod=args.prod)
    installer.jh_test()

    if args.ccs_inst_dir is not None:
        installer.ccs(args.ccs_inst_dir, prod=args.prod)
