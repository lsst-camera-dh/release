#!/usr/bin/env python
from __future__ import print_function, absolute_import
import os
import glob
import shutil
import subprocess
import warnings
try:
    import ConfigParser as configparser
except ImportError:
    import configparser

class Parfile(dict):
    def __init__(self, infile, section):
        super(Parfile, self).__init__()
        parser = configparser.ConfigParser()
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
    _github_elec_org = 'https://github.com/lsst-camera-electronics'
    def __init__(self, version_file, inst_dir='.', python_exec='python',
                 hj_folders=('BNL_T03',), site='BNL'):
        self.version_file = os.path.abspath(version_file)
        if inst_dir is not None:
            self.inst_dir = os.path.abspath(inst_dir)
            shutil.copy(self.version_file,
                        os.path.join(self.inst_dir, 'installed_versions.txt'))
        self.python_exec = python_exec
        self.hj_folders = hj_folders
        self.site = site
        self._package_dirs = None
        self._stack_dir = None
        self._datacat_pars = None
        self.curdir = os.path.abspath('.')
        try:
            self.pars = Parfile(self.version_file, 'jh')
        except configparser.NoSectionError:
            pass

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
        if  not package_name.startswith('REB_'):
            url = '/'.join((Installer._github_org, package_name, 'archive',
                        version + '.tar.gz'))
        else:
            url = '/'.join((Installer._github_elec_org, package_name, 'archive',
                        version + '.tar.gz'))
        commands = ["curl -L -O " + url,
                    "tar xzf %(version)s.tar.gz" % locals()]
        for command in commands:
            subprocess.call(command, shell=True,
                            executable=Installer._executable)

    @staticmethod
    def github_clone(package_name, version):
        if not version:
            version = 'master'

        dir_name = package_name+'-'+version
        if os.path.exists(dir_name):
            commands = ["cd " + dir_name, "git pull", "cd .."]
        else:
            commands = ['git clone --branch '+version+' '+'/'.join((Installer._github_org, package_name))+' '+dir_name]

        subprocess.call(commands, shell=True,
                            executable=Installer._executable)

        Installer.ccs_symlink(package_name, dir_name)

    def lcatr_install(self, package_name):
        version = self.pars[package_name]
        self.github_download(package_name, version)
        inst_dir = self.inst_dir
        python_exec = self.python_exec
        command = "cd %(package_name)s-%(version)s/; %(python_exec)s setup.py install --prefix=%(inst_dir)s" % locals()
        subprocess.call(command, shell=True, executable=self._executable)

    @property
    def package_dirs(self):
        if self._package_dirs is None:
            self._package_dirs = {}
            try:
                pars = Parfile(self.version_file, 'packages')
                for package, version in pars.items():
                    package_dir = "%(package)s-%(version)s" % locals()
                    self._package_dirs[package] = os.path.join(self.inst_dir,
                                                               package_dir)
            except configparser.NoSectionError:
                pass
        return self._package_dirs

    @property
    def stack_dir(self):
        if self._stack_dir is None:
            try:
                pars = Parfile(self.version_file, 'dmstack')
                self._stack_dir = pars['stack_dir']
            except configparser.NoSectionError:
                pass
        return self._stack_dir

    @property
    def datacat_pars(self):
        if self._datacat_pars is None:
            try:
                self._datacat_pars = Parfile(self.version_file, 'datacat')
            except configparser.NoSectionError:
                pass
        return self._datacat_pars

    def write_setup(self):
        contents = "export INST_DIR=%s\n" % self.inst_dir
        if self.stack_dir is not None:
            contents += """export STACK_DIR=%s
source ${STACK_DIR}/loadLSST.bash
export EUPS_PATH=${INST_DIR}/eups:${EUPS_PATH}
setup obs_lsst
""" % self.stack_dir

        contents += self._eups_config()
        contents += self._jh_config()
        contents += self._package_env_vars()
        contents += self._schema_paths()
        contents += self._python_configs()
        contents += "export OMP_NUM_THREADS=1\n"
        contents += 'PS1="[jh]$ "\n'

        output = open(os.path.join(self.inst_dir, 'setup.sh'), 'w')
        output.write(contents)
        output.close()

    def _eups_config(self):
        try:
            pars = Parfile(self.version_file, 'eups_packages')
        except configparser.NoSectionError:
            return ''
        return '\n'.join(['setup %s' % package for package in pars]) + '\n'

    def _jh_config(self):
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
        paths = []
        for package, package_dir in self.package_dirs.items():
            if not os.path.isdir(os.path.join(package_dir, 'schemas')):
                continue
            paths.append("${%s}/schemas" % self._env_var(package))
        paths.extend(['${HARNESSEDJOBSDIR}/schemas', '${LCATR_SCHEMA_PATH}'])
        return 'export LCATR_SCHEMA_PATH=' + ':'.join(paths) + '\n'

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
        try:
            module_path = glob.glob('%s/lib/python*/site-packages'
                                    % self.inst_dir)[0][len(self.inst_dir):]
            return os.path.join('${INST_DIR}', module_path.lstrip(os.path.sep))
        except IndexError:
            message = "%s/lib/python*/site-packages not found." % self.inst_dir
            warnings.warn(message)
            return ''

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
        os.chdir(self.inst_dir)
        self.modules_install()
        self.lcatr_install('lcatr-harness')
        self.lcatr_install('lcatr-schema')
        self.lcatr_install('lcatr-modulefiles')
        inst_dir = self.inst_dir
        subprocess.call('ln -sf %(inst_dir)s/share/modulefiles %(inst_dir)s/Modules' % locals(), shell=True, executable=self._executable)
        subprocess.call('touch `ls -d %(inst_dir)s/lib/python*/site-packages/lcatr`/__init__.py' % locals(), shell=True, executable=self._executable)
        hj_version = self.pars['harnessed-jobs']
        self.github_download('harnessed-jobs', hj_version)
        for folder in self.hj_folders:
            subprocess.call('ln -sf %(inst_dir)s/harnessed-jobs-%(hj_version)s/%(folder)s/* %(inst_dir)s/share' % locals(), shell=True, executable=self._executable)
        self.eups_package_installer()
        self.package_installer()
        self.write_setup()
        os.chdir(self.curdir)

    def eups_package_installer(self):
        try:
            pars = Parfile(self.version_file, 'eups_packages')
        except configparser.NoSectionError:
            return
        inst_dir = self.inst_dir
        stack_dir = self.stack_dir.rstrip(os.path.sep)
        ups_db_dir = '%(inst_dir)s/eups/ups_db' % locals()
        if not os.path.isdir(ups_db_dir):
            os.makedirs(ups_db_dir)
        for package, version in pars.items():
            self.github_download(package, version)
            commands = """source %(stack_dir)s/loadLSST.bash; export EUPS_PATH=%(inst_dir)s/eups:${EUPS_PATH}; cd %(package)s-%(version)s/; eups declare %(package)s %(version)s -r . -c; setup %(package)s; scons opt=3""" % locals()
            subprocess.call(commands, shell=True, executable=self._executable)

    def package_installer(self):
        try:
            pars = Parfile(self.version_file, 'packages')
        except configparser.NoSectionError:
            return
        inst_dir = self.inst_dir
        for package, version in pars.items():
            self.github_download(package, version)
            package_dir = "%(package)s-%(version)s" % locals()
            hj_dir = "%(inst_dir)s/%(package_dir)s/harnessed_jobs" % locals()
            if os.path.isdir(hj_dir):
                command = 'ln -sf %(hj_dir)s/* %(inst_dir)s/share' % locals()
                subprocess.call(command, executable=self._executable,
                                shell=True)

    def jh_test(self):
        os.chdir(self.inst_dir)
        try:
            pars = Parfile(self.version_file, 'eups_packages')
            pars['eotest']
            hj_version = self.pars['harnessed-jobs']
            command = 'source ./setup.sh; python harnessed-jobs-%(hj_version)s/tests/setup_test.py' % locals()
            subprocess.call(command, shell=True, executable=self._executable)
            os.chdir(self.curdir)
        except (configparser.NoSectionError, KeyError):
            pass

    def _ccs_download(self, package_name, package_version):

        # Determine the protocol to fetch the package by the prefix
        github_clone = package_name.startswith('github.')
        nexus_download = package_name.startswith('nexus.')

        # If no prefix is provided use _old_ mechanism
        if not github_clone and not nexus_download :
           github_clone = not package_name.startswith('org-lsst')

        # If from github, clone the project
        if github_clone:
            package_name = package_name.replace('github.', '')
            self.github_clone(package_name,package_version)
        else :
            package_name = package_name.replace('nexus.', '')
            subdir = '-'.join((package_name, package_version))
            is_released_version = 'SNAPSHOT' not in package_version

            if is_released_version and os.path.exists(subdir):
                print("Skipping download of released package {} since it already exists.".format(subdir))
            else:
                # Download the CCS package only when necessary:
                # - if it is a SNAPSHOT version
                # - if it is a released version and it does not exist in the ccs install directory
                base_url = "http://repo-nexus.lsst.org/nexus/repository/ccs-maven2-public/org/lsst/"
                command = 'wget --progress=dot:mega "%(base_url)s/%(package_name)s/%(package_version)s/%(package_name)s-%(package_version)s-dist.zip" -O temp.zip' % locals()
                subprocess.call(command, shell=True, executable=self._executable)
                if os.path.isdir(subdir):
                    subprocess.call('rm -r %(subdir)s' % locals(), shell=True, executable=self._executable)
                subprocess.call('unzip -uoqq temp.zip', shell=True, executable=self._executable)
                subprocess.call('rm temp.zip', shell=True, executable=self._executable)
                self.ccs_symlink(package_name, subdir)

    @staticmethod
    def ccs_symlink(symlinkName, symlinkTarget):
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
                                executable=Installer._executable)

        if createSymlink:
            subprocess.call('ln -sf %(symlinkTarget)s %(symlinkName)s'
                            % locals(), shell=True, executable=Installer._executable)

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
            self.ccs_symlink("packageList.txt", self.version_file)
            # Create a symbolic link to the install script used to create this installation directory
            self.ccs_symlink("update.py", os.path.abspath(os.path.join(self.curdir,__file__)))
        try:
            pars = Parfile(self.version_file, section)
        except configparser.NoSectionError:
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
                self._ccs_download(x, str(pars[x]))

        # Now create the executable symlinks in the distribution bin directory
        try:
            os.mkdir('bin')
        except OSError:
            # bin directory already exists(?)
            pass
        os.chdir('bin')

        for executable_name in executable_map:
            self.ccs_symlink(executable_name, "../{}/bin/CCSbootstrap.sh".format(executable_map[executable_name]))

        # Now create the symlinks from the top level of the distribution directory
        os.chdir('..')
        for symlink_name in symlink_map:
            self.ccs_symlink(symlink_name, symlink_map[symlink_name])
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
    parser.add_argument('--python_exec', type=str, default='python')
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
                          python_exec=args.python_exec,
                          hj_folders=args.hj_folders.split(), site=args.site)

    if args.inst_dir is not None:
        installer.jh()
        #installer.jh_test()

    if args.ccs_inst_dir is not None:
        installer.ccs(args)
