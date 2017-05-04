"""
Utility classes and functions for install scripts.
"""
from __future__ import print_function, absolute_import
import os
from collections import OrderedDict
import json
import subprocess
import ConfigParser

__all__ = ['Parfile', 'make_env_var', 'GitHubAccessor', 'GitHubAccessorError',
           'ccs_symlink']

_executable = '/bin/bash'

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


def make_env_var(package_name):
    return package_name.replace('-', '').upper() + 'DIR'

class GitHubAccessorError(RuntimeError):
    def __init__(self, *args, **kwds):
        super(GitHubAccessorError, self).__init__(*args, **kwds)

class GitHubAccessor(object):
    """
    Class to manage access to repos on GitHub.
    """
    def __init__(self, orgs):
        self.repos = self.github_org_repos(orgs)

    @staticmethod
    def github_org_repos(orgs):
        """
        Get the repositories in the specified list of github orgs.

        Parameters
        ----------
        orgs : sequence
            A list or tuple of github org names, e.g.,
            ('lsst-camera-dh', 'lsst-camera-electronics').

        Returns
        -------
        dict : A dictionary of lists of repos keyed by org name.
        """
        repos = OrderedDict()
        for org in orgs:
            repos[org] = []
            page = 1
            while True:
                command =\
                    'curl -s https://api.github.com/orgs/%s/repos?page=%d'\
                    % (org, page)
                repo_list = json.loads(subprocess.check_output(command,
                                                               shell=True))
                if not repo_list:
                    break
                for item in repo_list:
                    repos[org].append(item['name'])
                page += 1
        return repos

    def download(self, package_name, version):
        """
        Download and unpack the specified version of the package from
        among the specified github orgs.
        """
        for org, repos in self.repos.items():
            if package_name in repos:
                url = '/'.join(('https://github.com', org, package_name,
                                'archive', version + '.tar.gz'))
                commands = ["curl -L -O " + url,
                            "tar xzf %(version)s.tar.gz" % locals()]
                for command in commands:
                    subprocess.call(command, shell=True, executable=_executable)
                return
        raise GitHubAccessorError("%s not found in %s"
                                  % (package_name, self.repos.keys()))

    def clone(self, package_name, branch='master'):
        """
        Clone a specific branch of a repo from github.
        """
        dir_name = '_'.join((package_name, branch))
        if os.path.exists(dir_name):
            commands = ["cd " + dir_name, "git pull", "cd .."]
        else:
            for org, repos in self.repos.items():
                if package_name in repos:
                    commands = ['git clone --branch ' + branch + ' '
                                + '/'.join(('https://github.com', org,
                                            package_name))
                                + ' ' + dir_name]
                break
        subprocess.call(commands, shell=True, executable=_executable)
        ccs_symlink(package_name, dir_name)


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
                            executable=_executable)

    if createSymlink:
        subprocess.call('ln -sf %(symlinkTarget)s %(symlinkName)s'
                        % locals(), shell=True, executable=_executable)
