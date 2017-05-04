"""
Test code for install script utilities.
"""
import os
import sys
import shutil
import unittest
sys.path.insert(0, '../bin')
import utilities

class GitHubAccessorTestCase(unittest.TestCase):
    "TestCase class for the GitHubAccessor class."
    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_repos(self):
        "Unit test for the GitHubAccessor repos attribute."
        gh = utilities.GitHubAccessor(('lsst-camera-dh',
                                       'lsst-camera-electronics',))
        expected_repos = 'REB_v5 REB_v4_daq1 REB_v4 WREB_v2 GREB_v1'.split()
        electronics_repos = gh.repos['lsst-camera-electronics']
        self.assertEqual(set(expected_repos), set(electronics_repos))
        self.assertNotIn('eotest', electronics_repos)
        self.assertEqual(len(gh.repos['lsst-camera-dh']), 44)

    def test_download(self):
        "Test the GitHubAccessor.download function."
        gh = utilities.GitHubAccessor(('lsst-camera-dh',))
        package, version = 'jh-dev-tools', '0.0.1'
        gh.download(package, version)
        os.remove('%s.tar.gz' % version)
        shutil.rmtree('%s-%s' % (package, version))
        self.assertRaises(utilities.GitHubAccessorError, gh.download,
                          'REB_v5', 'REB_v5_top_30325002')

    def test_clone(self):
        "Test the GitHubAccessor.clone function."
        gh = utilities.GitHubAccessor(('lsst-camera-dh',))
        package, branch = 'jh-ccs-utils', 'master'
        gh.clone(package, branch)
        os.remove(package)
        shutil.rmtree('%s_%s' % (package, branch))

if __name__ == '__main__':
    unittest.main()
