#!/usr/bin/env python
from __future__ import print_function, absolute_import
import os
import subprocess
import ConfigParser
import argparse
import utilities

_executable = '/bin/bash'

class CcsInstaller(object):
    def __init__(self, version_file, site='BNL', orgs=None):
        self.version_file = os.path.abspath(version_file)
        self.site = site
        self.curdir = os.path.abspath('.')
        if orgs is None:
            orgs = ('lsst-camera-dh',)
        self.gh_accessor = utilities.GitHubAccessor(orgs)

    def _ccs_download(self, package_name, package_version):

        # Determine the protocol to fetch the package by the prefix
        github_clone = package_name.startswith('github.')
        nexus_download = package_name.startswith('nexus.')

        # If no prefix is provided use _old_ mechanism
        if not github_clone and not nexus_download:
            github_clone = not package_name.startswith('org-lsst')

        # If from github, clone the project
        if github_clone:
            package_name = package_name.replace('github.', '')
            self.gh_accessor.clone(package_name, package_version)
        else:
            package_name = package_name.replace('nexus.', '')
            subdir = '-'.join((package_name, package_version))
            is_released_version = 'SNAPSHOT' not in package_version

            if is_released_version and os.path.exists(subdir):
                print("Skipping download of released package {} since it already exists.".format(subdir))
            else:
                # Download the CCS package only when necessary:
                # - if it is a SNAPSHOT version
                # - if it is a released version and it does not exist in the ccs install directory
                base_url = "http://dev.lsstcorp.org:8081/nexus/service/local/artifact/maven/redirect?r=ccs-maven2-public&g=org.lsst"
                command = 'wget "%(base_url)s&a=%(package_name)s&v=%(package_version)s&e=zip&c=dist" -O temp.zip' % locals()
                subprocess.call(command, shell=True, executable=_executable)
                if os.path.isdir(subdir):
                    subprocess.call('rm -r %(subdir)s' % locals(), shell=True, executable=_executable)
                subprocess.call('unzip -uoqq temp.zip', shell=True, executable=_executable)
                subprocess.call('rm temp.zip', shell=True, executable=_executable)
                utilities.ccs_symlink(package_name, subdir)


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
            utilities.ccs_symlink("packageList.txt", self.version_file)
            # Create a symbolic link to the install script used to create this installation directory
            utilities.ccs_symlink("update.py", os.path.abspath(os.path.join(self.curdir, __file__)))
        try:
            pars = utilities.Parfile(self.version_file, section)
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
    parser = argparse.ArgumentParser(description="CCS Installer",
                                     fromfile_prefix_chars="@")
    parser.add_argument("version_file", help='software version file')
    parser.add_argument('--site', type=str, default='SLAC',
                        help='Site (SLAC, BNL, etc.)')
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

    installer = CcsInstaller(args.version_file, site=args.site)
    installer.ccs(args)
