#!/usr/bin/env python
from __future__ import print_function, absolute_import
import os
import subprocess
import ConfigParser

class Parfile(dict):
    def __init__(self, infile, section):
        super(Parfile, self).__init__()
        parser = ConfigParser.ConfigParser()
        parser.optionxform = str
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
    _executable = '/bin/bash'
    _github_org = 'https://github.com/lsst-camera-dh'
    def __init__(self, version_file, inst_dir='.',
                 hj_folders=('BNL_T03',), site='BNL'):
        self.version_file = os.path.abspath(version_file)
        if inst_dir is not None:
            self.inst_dir = os.path.abspath(inst_dir)
        self.hj_folders = hj_folders
        self.site = site
        self._stack_dir = None
        self._datacat_pars = None
        self.curdir = os.path.abspath('.')
        self.package_dirs = {}

    def modules_install(self):
        url = 'http://sourceforge.net/projects/modules/files/Modules/modules-3.2.10/modules-3.2.10.tar.gz'
        inst_dir = self.inst_dir
        commands = ";".join(["curl -L -O %(url)s",
                             "tar xzf modules-3.2.10.tar.gz",
                             "cd modules-3.2.10",
                             "./configure --prefix=%(inst_dir)s",
                             "make",
                             "make install",
                             "cd %(inst_dir)s"]) % locals()
        subprocess.call(commands, shell=True, executable=self._executable)

    @staticmethod
    def github_download(package_name, version):
        url = '/'.join((Installer._github_org, package_name, 'archive',
                        version + '.tar.gz'))
        commands = ["curl -L -O " + url,
                    "tar xzf %(version)s.tar.gz" % locals()]
        for command in commands:
            subprocess.call(command, shell=True,
                            executable=Installer._executable)

    def lcatr_install(self, package_name):
        version = self.pars[package_name]
        self.github_download(package_name, version)
        inst_dir = self.inst_dir
        command = "cd %(package_name)s-%(version)s/; python setup.py install --prefix=%(inst_dir)s" % locals()
        subprocess.call(command, shell=True, executable=self._executable)

    @property
    def stack_dir(self):
        if self._stack_dir is None:
            try:
                pars = Parfile(self.version_file, 'dmstack')
                self._stack_dir = pars['stack_dir']
            except ConfigParser.NoSectionError:
                pass
        return self._stack_dir

    @property
    def datacat_pars(self):
        if self._datacat_pars is None:
            try:
                self._datacat_pars = Parfile(self.version_file, 'datacat')
            except ConfigParser.NoSectionError:
                pass
        return self._datacat_pars

    def write_setup(self):
        contents = "export INST_DIR=%s\n" % self.inst_dir
        if self.stack_dir is not None:
            contents += """export STACK_DIR=%s
source ${STACK_DIR}/loadLSST.bash
export EUPS_PATH=${INST_DIR}/eups:${EUPS_PATH}
""" % self.stack_dir
        try:
            self.pars['eotest']
            contents += """setup eotest
setup mysqlpython
"""
        except KeyError:
            pass

        bin_dirs = [os.path.join('${INST_DIR}', os.path.split(x)[-1], 'bin')
                    for x in self.package_dirs.values()
                    if os.path.isdir(os.path.join(x, 'bin'))]
        bin_path = ":".join(bin_dirs + ['${INST_DIR}/bin', '${PATH}'])
        hj_version = self.pars['harnessed-jobs']
        site = self.site
        contents += """export HARNESSEDJOBSDIR=${INST_DIR}/harnessed-jobs-%(hj_version)s
export LCATR_SCHEMA_PATH=${HARNESSEDJOBSDIR}/schemas:${LCATR_SCHEMA_PATH}
export VIRTUAL_ENV=${INST_DIR}
source ${INST_DIR}/Modules/3.2.10/init/bash
export PATH=%(bin_path)s
export SITENAME=%(site)s
""" % locals()
        contents += self._package_env_vars()
        contents += self._python_configs()
        contents +="""PS1="[jh]$ "
"""
        output = open(os.path.join(self.inst_dir, 'setup.sh'), 'w')
        output.write(contents)
        output.close()

    def _package_env_vars(self):
        contents = ""
        for package, package_dir in self.package_dirs.items():
            subdir = os.path.split(package_dir.rstrip(os.path.sep))[-1]
            env_var = self._env_var(package)
            contents += ("export %s=${INST_DIR}/%s\n" % (env_var, subdir))
        return contents

    @staticmethod
    def _env_var(package_name):
        return package_name.replace('-', '').upper() + 'DIR'

    def _module_path(self):
        module_path = subprocess.check_output('ls -d %s/lib/python*/site-packages' % self.inst_dir, shell=True).strip()
        return os.path.join('${INST_DIR}',
                            module_path[len(self.inst_dir):].lstrip(os.path.sep))

    def _python_configs(self):
        python_dirs = [os.path.join('${'+self._env_var(x)+'}', 'python')
                       for x in self.package_dirs]
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
        self.pars = Parfile(self.version_file, 'jh')
        os.chdir(self.inst_dir)
        self.modules_install()
        self.lcatr_install('lcatr-harness')
        self.lcatr_install('lcatr-schema')
        self.lcatr_install('lcatr-modulefiles')
        inst_dir = self.inst_dir
        subprocess.call('ln -sf %(inst_dir)s/share/modulefiles %(inst_dir)s/Modules' % locals(), shell=True, executable=self._executable)
        subprocess.call('touch `ls -d %(inst_dir)s/lib/python*/site-packages/lcatr`/__init__.py' % locals(), shell=True, executable=self._executable)
        try:
            eotest_version = self.pars['eotest']
            self.github_download('eotest', eotest_version)
            stack_dir = self.stack_dir.rstrip(os.path.sep)
            commands = """source %(stack_dir)s/loadLSST.bash; mkdir -p %(inst_dir)s/eups/ups_db; export EUPS_PATH=%(inst_dir)s/eups:${EUPS_PATH}; cd eotest-%(eotest_version)s/; eups declare eotest %(eotest_version)s -r . -c; setup eotest; setup mysqlpython; scons opt=3""" % locals()
            subprocess.call(commands, shell=True, executable=self._executable)
        except KeyError:
            pass

        hj_version = self.pars['harnessed-jobs']
        self.github_download('harnessed-jobs', hj_version)
        for folder in self.hj_folders:
            subprocess.call('ln -sf %(inst_dir)s/harnessed-jobs-%(hj_version)s/%(folder)s/* %(inst_dir)s/share' % locals(), shell=True, executable=self._executable)
        self.hj_package_installer()
        self.write_setup()
        os.chdir(self.curdir)

    def hj_package_installer(self):
        try:
            pars = Parfile(self.version_file, 'hj_packages')
        except ConfigParser.NoSectionError:
            return
        inst_dir = self.inst_dir
        for package, version in pars.items():
            self.github_download(package, version)
            package_dir = "%(package)s-%(version)s" % locals()
            hj_dir = "%(inst_dir)s/%(package_dir)s/harnessed_jobs" % locals()
            if os.path.isdir(hj_dir):
                command = 'ln -sf %(hj_dir)s/* %(inst_dir)s/share' % locals()
                subprocess.call(command, shell=True, executable=self._executable)
            self.package_dirs[package] = os.path.join(inst_dir, package_dir)

    def jh_test(self):
        os.chdir(self.inst_dir)
        try:
            self.pars['eotest']
            hj_version = self.pars['harnessed-jobs']
            command = 'source ./setup.sh; python harnessed-jobs-%(hj_version)s/tests/setup_test.py' % locals()
            subprocess.call(command, shell=True, executable=self._executable)
            os.chdir(self.curdir)
        except KeyError:
            pass

    def _ccs_download(self, package_name, package_version):

        if not package_name.startswith('org-lsst'):
            self.github_download(package_name,package_version)
            return

        subdir = '-'.join((package_name, package_version))
        isReleasedVersion = 'SNAPSHOT' not in package_version

        if isReleasedVersion and os.path.exists(subdir):
            print("Skipping download of released package {} since it already exists.".format(subdir))
        else:
            # Download the CCS package only when necessary:
            # - if it is a SNAPSHOT version
            # - if it is a released version and it does not exist in the ccs install directory
            base_url = "http://dev.lsstcorp.org:8081/nexus/service/local/artifact/maven/redirect?r=ccs-maven2-public&g=org.lsst"
            command = 'wget "%(base_url)s&a=%(package_name)s&v=%(package_version)s&e=zip&c=dist" -O temp.zip' % locals()
            subprocess.call(command, shell=True, executable=self._executable)
            if os.path.isdir(subdir):
                subprocess.call('rm -r %(subdir)s' % locals(), shell=True, executable=self._executable)
            subprocess.call('unzip -uoqq temp.zip', shell=True, executable=self._executable)
            subprocess.call('rm temp.zip', shell=True, executable=self._executable)

        self._ccs_symlink(package_name, subdir)

    def _ccs_symlink(self, symlinkName, symlinkTarget):
        createSymlink = False
        if not os.path.exists(symlinkName):
            #If the symlink does not exist, create it
            print("Creating symlink {} ---> {}".format(symlinkName,
                                                       symlinkTarget))
            createSymlink = True
        else:
            if os.path.realpath(symlinkName) != os.path.realpath(symlinkTarget):
                #If the symlink exists, but it points to a different version of
                #the package, then remove it and then re-create it.
                print("Updating symlink {} ---> {}".format(symlinkName,
                                                           symlinkTarget))
                createSymlink = True
                subprocess.call('rm %(symlinkName)s' % locals(), shell=True,
                                executable=self._executable)

        if createSymlink:
            subprocess.call('ln -sf %(symlinkTarget)s %(symlinkName)s'
                            % locals(), shell=True, executable=self._executable)

    def ccs(self, args, section='ccs'):

        # The CCS installation directory
        inst_dir = args.ccs_inst_dir
        # CCS Installation directory full path from where the script is being run
        inst_dir_full_path = os.path.realpath(args.ccs_inst_dir)

        # Check if the CCS installation directory exists and create it if it does not exist.
        if not os.path.exists(inst_dir_full_path):
            print("Creating CCS install directory {}.".format(inst_dir_full_path))
            os.makedirs(inst_dir_full_path)

        # Change directory to the installation directory
        os.chdir(inst_dir)

        # These actions are taken only in a development environment:
        # - create a .installArgs file
        # - create a symlink for the update script
        # - create a symlink to the package list file
        if args.dev:
            # Create a list with the arguments required to build the CCS installation directory
            ccs_arguments = []
            ccs_arguments.append("--ccs_inst_dir")
            ccs_arguments.append(inst_dir_full_path)
            ccs_arguments.append("--site")
            ccs_arguments.append(args.site)
            ccs_arguments.append("--dev")
            ccs_arguments.append(self.version_file)

            install_file_name = ".installArgs"
            # If the install file does not exist, create it.
            if not os.path.exists(install_file_name):
                install_file = open(install_file_name, 'w')
                for arg in ccs_arguments:
                    install_file.write(arg+"\n")
            # Create a symbolic link to the package list file used to create this installation directory
            self._ccs_symlink("packageList.txt", self.version_file)
            # Create a symbolic link to the install script used to create this installation directory
            self._ccs_symlink("update.py", os.path.abspath(os.path.join(self.curdir,__file__)))
        try:
            pars = Parfile(self.version_file, section)
        except ConfigParser.NoSectionError:
            return

        # Loop over the content of the [ccs] section to find either
        #  - packages to be downloaded
        #  - executable symlinks in the bin directory
        #  - symlinks to be created
        # Symlinks are created after the packages have been downloaded
        symlink_map = {}
        symlink_token = "symlink."
        executable_map = {}
        executable_token = "executable."
        for x in pars:
            # Executables
            if x.startswith(executable_token):
                executable_map.update({x.replace(executable_token, ''): pars[x]})
            # Symlinks
            elif x.startswith(symlink_token):
                symlink_map.update({x.replace(symlink_token, ''): pars[x]})
            else:
                self._ccs_download(x, pars[x])

        # Now create the executable symlinks in the distribution bin directory
        try:
            os.mkdir('bin')
        except OSError:
            # bin directory already exists(?)
            pass
        os.chdir('bin')

        for executable_name in executable_map:
            self._ccs_symlink(executable_name, "../{}/bin/CCSbootstrap.sh".format(executable_map[executable_name]))

        # Now create the symlinks from the top level of the distribution directory
        os.chdir('..')
        for symlink_name in symlink_map:
            self._ccs_symlink(symlink_name, symlink_map[symlink_name])
        os.chdir(self.curdir)

if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description="Job Harness Installer",
                                     fromfile_prefix_chars="@")
    parser.add_argument("version_file", help='software version file')
    parser.add_argument('--inst_dir', type=str, default=None,
                        help='installation directory')
    parser.add_argument('--site', type=str, default='SLAC',
                        help='Site (SLAC, BNL, etc.)')
    parser.add_argument('--hj_folders', type=str, default="SLAC")
    parser.add_argument('--ccs_inst_dir', type=str, default=None)
    parser.add_argument('--dev', action='store_true')

    installerArguments = None
    # Check if there is a previously written installation arguments file
    # in the script's directory.
    installArgsFileName = ".installArgs"
    installArgsFullPath = os.path.join(os.path.realpath(os.path.dirname(__file__)), installArgsFileName)
    if os.path.exists(installArgsFullPath):
        installerArguments = ["@{}".format(installArgsFullPath)]

    args = parser.parse_args(installerArguments)

    installer = Installer(args.version_file, inst_dir=args.inst_dir,
                          hj_folders=args.hj_folders.split(), site=args.site)

    if args.inst_dir is not None:
        installer.jh()
        installer.jh_test()

    if args.ccs_inst_dir is not None:
        installer.ccs(args)
