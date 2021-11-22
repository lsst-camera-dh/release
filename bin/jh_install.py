#!/usr/bin/env python
import os
import glob
import shutil
import subprocess
import warnings
import configparser

class Parfile(dict):
    def __init__(self, infile, section):
        super(Parfile, self).__init__()
        parser = configparser.ConfigParser()
        parser.optionxform = str
        result = parser.read(infile)
        if not result:
            raise RuntimeError("invalid or empty config file: {f}".format(f=infile))
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


def get_package_name(package):
    pattern = os.path.join(package + '*', 'ups', '*.table')
    return os.path.basename(glob.glob(pattern)[0]).split('.')[0]


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
        self._third_party_pars = None
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
        subprocess.check_call(commands, shell=True, executable=self._executable)

    @staticmethod
    def github_download(package_name, version):
        if not package_name.startswith('REB_'):
            url = '/'.join((Installer._github_org, package_name, 'archive',
                        version + '.tar.gz'))
        else:
            url = '/'.join((Installer._github_elec_org, package_name, 'archive',
                        version + '.tar.gz'))
        commands = ["curl -L -O " + url,
                    "tar xzf %(version)s.tar.gz" % locals()]
        for command in commands:
            subprocess.check_call(command, shell=True,
                                  executable=Installer._executable)

    @staticmethod
    def github_clone(package_name, version):
        if not version:
            version = 'master'
        url = '/'.join((Installer._github_org, package_name + '.git'))
        command = f'git clone {url}; cd {package_name}; git checkout {version}'
        subprocess.check_call(command, shell=True,
                              executable=Installer._executable)

    def lcatr_install(self, package_name):
        version = self.pars[package_name]
        self.github_download(package_name, version)
        inst_dir = self.inst_dir
        python_exec = self.python_exec
        command = "cd %(package_name)s-%(version)s/; %(python_exec)s setup.py install --prefix=%(inst_dir)s" % locals()
        subprocess.check_call(command, shell=True, executable=self._executable)

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
    def third_party_pars(self):
        if self._third_party_pars is None:
            try:
                self._third_party_pars = Parfile(self.version_file,
                                                 'third_party')
            except configparser.NoSectionError:
                self._third_party_pars = dict()
        return self._third_party_pars

    def write_setup(self):
        contents = "export INST_DIR=%s\n" % self.inst_dir
        if self.stack_dir is not None:
            contents += """export STACK_DIR=%s
source ${STACK_DIR}/loadLSST.bash
export EUPS_PATH=${INST_DIR}/eups:${EUPS_PATH}
""" % self.stack_dir

        contents += self._eups_config()
        if 'eo_utilities_dir' in self.third_party_pars:
            eo_utilities_dir = self.third_party_pars['eo_utilities_dir']
            contents += 'setup -r %(eo_utilities_dir)s\n' % locals()
        contents += self._jh_config()
        contents += self._package_env_vars()
        contents += self._schema_paths()
        contents += self._python_configs()
        contents += "export OMP_NUM_THREADS=1\n"
        contents += "export MPLBACKEND=svg\n"
        contents += 'PS1="[jh]$ "\n'

        output = open(os.path.join(self.inst_dir, 'setup.sh'), 'w')
        output.write(contents)
        output.close()

    def _eups_config(self):
        try:
            pars = Parfile(self.version_file, 'eups_packages')
        except configparser.NoSectionError:
            return ''
        return '\n'.join(['setup lsst_distrib'] +
                         ['setup %s' % get_package_name(package)
                          for package in pars]) + '\n'

    def _jh_config(self):
        bin_dirs = [os.path.join('${INST_DIR}', os.path.split(x)[-1], 'bin')
                    for x in self.package_dirs.values()
                    if os.path.isdir(os.path.join(x, 'bin'))]
        bin_path = ":".join(bin_dirs + ['${INST_DIR}/bin', '${PATH}'])
        hj_version = self.pars['harnessed-jobs']
        site = self.site
        modules_dir = self.third_party_pars['modules_dir']
        return """export HARNESSEDJOBSDIR=${INST_DIR}/harnessed-jobs-%(hj_version)s
export VIRTUAL_ENV=${INST_DIR}
source %(modules_dir)s/3.2.10/init/bash
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
        for package_dir, path in self.third_party_pars.items():
            if package_dir in ('modules_dir', 'eo_utilities_dir'):
                continue
            python_dirs.append(path)
        python_dirs.extend(['${HARNESSEDJOBSDIR}/python', self._module_path(),
                            '${PYTHONPATH}'])
        python_configs = "export PYTHONPATH=%s\n" % ":".join(python_dirs)
        return python_configs

    def jh(self):
        os.chdir(self.inst_dir)
        #self.modules_install()
        self.lcatr_install('lcatr-harness')
        self.lcatr_install('lcatr-schema')
        self.lcatr_install('lcatr-modulefiles')
        inst_dir = self.inst_dir
        subprocess.check_call('ln -sf %(inst_dir)s/share/modulefiles %(inst_dir)s/Modules' % locals(), shell=True, executable=self._executable)
        subprocess.check_call('touch `ls -d %(inst_dir)s/lib/python*/site-packages/lcatr`/__init__.py' % locals(), shell=True, executable=self._executable)
        hj_version = self.pars['harnessed-jobs']
        self.github_download('harnessed-jobs', hj_version)
        for folder in self.hj_folders:
            subprocess.check_call('ln -sf %(inst_dir)s/harnessed-jobs-%(hj_version)s/%(folder)s/* %(inst_dir)s/share' % locals(), shell=True, executable=self._executable)
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
            if package == 'obs_lsst':
                scons_command = 'scons lib python shebang examples doc policy python/lsst/obs/lsst/version.py'
            else:
                scons_command = 'scons'
            if version == 'master':
                self.github_clone(package, version)
            else:
                self.github_download(package, version)
            package_name = get_package_name(package)
            commands = """source %(stack_dir)s/loadLSST.bash; export EUPS_PATH=%(inst_dir)s/eups:${EUPS_PATH}; cd %(package)s*; eups declare %(package_name)s %(version)s -r . -c; setup %(package_name)s; %(scons_command)s""" % locals()
            subprocess.check_call(commands, shell=True,
                                  executable=self._executable)

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
                subprocess.check_call(command, executable=self._executable,
                                shell=True)

    def jh_test(self):
        os.chdir(self.inst_dir)
        try:
            pars = Parfile(self.version_file, 'eups_packages')
            pars['eotest']
            hj_version = self.pars['harnessed-jobs']
            command = 'source ./setup.sh; python harnessed-jobs-%(hj_version)s/tests/setup_test.py' % locals()
            subprocess.check_call(command, shell=True, executable=self._executable)
            os.chdir(self.curdir)
        except (configparser.NoSectionError, KeyError):
            pass

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
    parser.add_argument('--dev', action='store_true')

    args = parser.parse_args()

    installer = Installer(args.version_file, inst_dir=args.inst_dir,
                          python_exec=args.python_exec,
                          hj_folders=args.hj_folders.split(), site=args.site)

    if args.inst_dir is not None:
        installer.jh()
