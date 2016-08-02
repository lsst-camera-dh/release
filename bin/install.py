#!/usr/bin/env python
import os
import subprocess
import ConfigParser
import inspect

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
    _github_org = 'https://github.com/lsst-camera-dh'
    def __init__(self, version_file, inst_dir='.',
                 hj_folders=('BNL_T03',), site='BNL'):
        self.version_file = os.path.abspath(version_file)
        if inst_dir is not None:
            self.inst_dir = os.path.abspath(inst_dir)
        self.hj_folders = hj_folders
        self.site = site
        self._stack_dir = None
        self.curdir = os.path.abspath('.')
        self.package_dirs = []

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
        subprocess.call(commands, shell=True, executable="/bin/bash")

    @staticmethod
    def github_download(package_name, version):
        url = '/'.join((Installer._github_org, package_name, 'archive',
                        version + '.tar.gz'))
        commands = ["curl -L -O " + url,
                    "tar xzf %(version)s.tar.gz" % locals()]
        for command in commands:
            subprocess.call(command, shell=True, executable="/bin/bash")

    def lcatr_install(self, package_name):
        version = self.pars[package_name]
        self.github_download(package_name, version)
        inst_dir = self.inst_dir
        command = "cd %(package_name)s-%(version)s/; python setup.py install --prefix=%(inst_dir)s" % locals()
        subprocess.call(command, shell=True, executable="/bin/bash")

    @property
    def stack_dir(self):
        if self._stack_dir is None:
            try:
                pars = Parfile(self.version_file, 'dmstack')
                self._stack_dir = pars['stack_dir']
            except ConfigParser.NoSectionError:            
                pass
        return self._stack_dir

    def write_setup(self):
        stack_dir = self.stack_dir
        inst_dir = self.inst_dir
        hj_version = self.pars['harnessed-jobs']
        site = self.site
        module_path = subprocess.check_output('ls -d %(inst_dir)s/lib/python*/site-packages' % locals(), shell=True).strip()
        python_dirs = [os.path.join(x, 'python') for x in self.package_dirs]
        python_dirs.extend(['${DATACATDIR}', 
                            '${HARNESSEDJOBSDIR}/python',
                            module_path,
                            '${PYTHONPATH}'])
        python_path = ":".join(python_dirs)
        bin_dirs = [os.path.join(x, 'bin') for x in self.package_dirs]
        bin_dirs.extend(['${INST_DIR}/bin', '${PATH}'])
        bin_path = ":".join(bin_dirs)
        try:
            datacat_pars = Parfile(self.version_file, 'datacat')
            datacatdir = os.path.join(datacat_pars['datacatdir'])
            datacat_config = datacat_pars['datacat_config']
            python_configs = """export DATACATDIR=%(datacatdir)s/lib
export DATACAT_CONFIG=%(datacat_config)s
export PYTHONPATH=%(python_path)s""" % locals()
        except ConfigParser.NoSectionError:
            python_configs = "export PYTHONPATH=%(python_path)s" % locals()
        contents = """export STACK_DIR=%(stack_dir)s
source ${STACK_DIR}/loadLSST.bash
export INST_DIR=%(inst_dir)s
export EUPS_PATH=${INST_DIR}/eups:${EUPS_PATH}
setup eotest
setup mysqlpython
export VIRTUAL_ENV=${INST_DIR}
source ${INST_DIR}/Modules/3.2.10/init/bash
export HARNESSEDJOBSDIR=${INST_DIR}/harnessed-jobs-%(hj_version)s
%(python_configs)s
export PATH=%(bin_path)s
export SITENAME=%(site)s
export LCATR_SCHEMA_PATH=${HARNESSEDJOBSDIR}/schemas:${LCATR_SCHEMA_PATH}
PS1="[jh]$ "
""" % locals()
        output = open(os.path.join(self.inst_dir, 'setup.sh'), 'w')
        output.write(contents)
        output.close()

    def jh(self, section='jh'):
        try:
            self.pars = Parfile(self.version_file, section)
        except ConfigParser.NoSectionError:            
            return
        os.chdir(self.inst_dir)
        self.modules_install()
        self.lcatr_install('lcatr-harness')
        self.lcatr_install('lcatr-schema')
        self.lcatr_install('lcatr-modulefiles')
        inst_dir = self.inst_dir
        subprocess.call('ln -sf %(inst_dir)s/share/modulefiles %(inst_dir)s/Modules' % locals(), shell=True, executable="/bin/bash")
        subprocess.call('touch `ls -d %(inst_dir)s/lib/python*/site-packages/lcatr`/__init__.py' % locals(), shell=True, executable="/bin/bash")
        eotest_version = self.pars['eotest']
        self.github_download('eotest', eotest_version)
        stack_dir = self.stack_dir
        commands = """source %(stack_dir)s/loadLSST.bash; mkdir -p %(inst_dir)s/eups/ups_db; export EUPS_PATH=%(inst_dir)s/eups:${EUPS_PATH}; cd eotest-%(eotest_version)s/; eups declare eotest %(eotest_version)s -r . -c; setup eotest; setup mysqlpython; scons opt=3""" % locals()
        subprocess.call(commands, shell=True, executable="/bin/bash")
        hj_version = self.pars['harnessed-jobs']
        self.github_download('harnessed-jobs', hj_version)
        for folder in self.hj_folders:
            subprocess.call('ln -sf %(inst_dir)s/harnessed-jobs-%(hj_version)s/%(folder)s/* %(inst_dir)s/share' % locals(), shell=True, executable="/bin/bash")
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
                subprocess.call(command, shell=True, executable="/bin/bash")
            self.package_dirs.append(os.path.join(inst_dir, package_dir))

    def jh_test(self):
        os.chdir(self.inst_dir)
        hj_version = self.pars['harnessed-jobs']
        command = 'source ./setup.sh; python harnessed-jobs-%(hj_version)s/tests/setup_test.py' % locals()
        subprocess.call(command, shell=True, executable="/bin/bash")
        os.chdir(self.curdir)

    def _ccs_download(self, package_name, package_version):

        subdir = '-'.join((package_name, package_version))
        isReleasedVersion = 'SNAPSHOT' not in package_version;
        
        if isReleasedVersion and os.path.exists(subdir):
            print("Skipping download of released package {} since it already exists.".format(subdir));
        else:
            #Download the CCS package only when necessary:
            # - if it is a SNAPSHOT version
            # - if it is a released version and it does not exist in the ccs install directory
            base_url = "http://dev.lsstcorp.org:8081/nexus/service/local/artifact/maven/redirect?r=ccs-maven2-public&g=org.lsst"
            command = 'wget "%(base_url)s&a=%(package_name)s&v=%(package_version)s&e=zip&c=dist" -O temp.zip' % locals()
            subprocess.call(command, shell=True, executable="/bin/bash")
            if os.path.isdir(subdir):
                subprocess.call('rm -r %(subdir)s' % locals(), shell=True, executable="/bin/bash")
            subprocess.call('unzip -uoqq temp.zip', shell=True, executable="/bin/bash")
            subprocess.call('rm temp.zip', shell=True, executable="/bin/bash")
            
        self._ccs_symlink(package_name, subdir);

    def _ccs_symlink(self, symlinkName, symlinkTarget):
        createSymlink = False
        if not os.path.exists(symlinkName):
            #If the symlink does not exist, create it
            print("Creating symlink {} ---> {}".format(symlinkName,symlinkTarget))
            createSymlink = True;
        else:
            if os.path.realpath(symlinkName) != os.path.realpath(symlinkTarget):
                #If the symlink exists, but it points to a different version of
                #the package, then remove it and then re-create it.
                print("Updating symlink {} ---> {}".format(symlinkName,symlinkTarget))
                createSymlink = True;
                subprocess.call('rm %(symlinkName)s' % locals(), shell=True, executable="/bin/bash")

        if createSymlink:
            subprocess.call('ln -sf %(symlinkTarget)s %(symlinkName)s' % locals(), shell=True, executable="/bin/bash")
        

    def ccs(self, args, section='ccs'):
        
        #The CCS installation directory
        inst_dir = args.ccs_inst_dir;
        #CCS Installation directory full path from where the script is being run
        inst_dir_full_path = os.path.realpath(args.ccs_inst_dir);
        
        #Check if the CCS installation directory exists and create it if it does not exist.
        if not os.path.exists(inst_dir_full_path):
            print("Creating CCS install directory {}.".format(inst_dir_full_path))
            os.makedirs(inst_dir_full_path);

        #Change directory to the installation directory
        os.chdir(inst_dir)
            

        #These actions are taken only in a development environment:
        # - create a .installArgs file
        # - create a symlink for the update script
        # - create a symlink to the package list file
        if args.dev:
            #Create a list with the arguments required to build the CCS installation directory
            ccsArguments = [];
            ccsArguments.append("--ccs_inst_dir");
            ccsArguments.append(inst_dir_full_path);
            ccsArguments.append("--site");
            ccsArguments.append(args.site);
            ccsArguments.append("--dev");
            ccsArguments.append(self.version_file);
        

            installFileName = ".installArgs";
            #If the install file does not exist, create it.
            if ( not os.path.exists(installFileName) ):
                installFile = open(installFileName, 'w')
                for arg in ccsArguments:
                    installFile.write(arg+"\n");
            #Create a symbolic link to the install script used to create this installation directory
            self._ccs_symlink("update.py",inspect.stack()[0][1]);        
            #Create a symbolic link to the package list file used to create this installation directory
            self._ccs_symlink("packageList.txt",self.version_file);
        
        try:
            pars = Parfile(self.version_file, section)
        except ConfigParser.NoSectionError:            
            return
        
        
        #Loop over the content of the [ccs] section to find either        
        #  - packages to be downloaded
        #  - symlinks to be created
        #Symlinks are created after the packages have been downloaded
        symlinkMap = {};
        symlinkToken = "symlink."
        for x in pars :
            if not x.startswith(symlinkToken):
                self._ccs_download(x, pars[x])
            else:
                symlinkMap.update({x.replace(symlinkToken,''):pars[x]})

        try:
            os.mkdir('bin')
        except OSError:
            # bin directory already exists(?)
            pass
        os.chdir('bin')
        
        
        #Now create the symlinks
        for symlinkName in symlinkMap:
            self._ccs_symlink(symlinkName,"../{}/bin/CCSbootstrap.sh".format(symlinkMap[symlinkName]))
        
        os.chdir(self.curdir)

if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description="Job Harness Installer",fromfile_prefix_chars="@")
    parser.add_argument("version_file", help='software version file')
    parser.add_argument('--inst_dir', type=str, default=None,
                        help='installation directory')
    parser.add_argument('--site', type=str, default='SLAC',
                        help='Site (SLAC, BNL, etc.)')
    parser.add_argument('--hj_folders', type=str, default="SLAC")
    parser.add_argument('--ccs_inst_dir', type=str, default=None)
    parser.add_argument('--dev', action='store_true')
        
    installerArguments = None;
    #Check if there is a previously written installation arguments file
    #in the script's directory.  
    installArgsFileName = ".installArgs";
    installArgsFullPath = os.path.join(os.path.realpath(os.path.dirname(inspect.stack()[0][1])),installArgsFileName)
    if ( os.path.exists(installArgsFullPath) ):
        installerArguments = ["@{}".format(installArgsFullPath)]

    args = parser.parse_args(installerArguments)
    
    installer = Installer(args.version_file, inst_dir=args.inst_dir,
                          hj_folders=args.hj_folders.split(), site=args.site)

    if args.inst_dir is not None:
        installer.jh()
        installer.jh_test()

    if args.ccs_inst_dir is not None:
        installer.ccs(args)
