"""
This script loops over the repositories in the lsst-camera-dh org and
requests any repository tags and their creation times, printing the
most recent tag and its time for each repo.

This script works better with an access token (obtained from the GITHUB*
environment variables):

https://help.github.com/articles/creating-an-access-token-for-command-line-use/
"""
import os
import subprocess
import datetime
from github import Github
import json

def tag_timestamp(tag):
    format = '%a, %d %b %Y %H:%M:%S GMT'
    timestamp_string = tag.commit.stats.last_modified
    return datetime.datetime.strptime(timestamp_string, format)

def latest_tag(repo):
    tags = dict([(tag_timestamp(x), x) for x in repo.get_tags()])
    ts_latest = sorted(tags.keys())[-1]
    return tags[ts_latest], ts_latest

try:
    username = os.environ['GITHUB_USERNAME']
    access_token = os.environ['GITHUB_ACCESS_TOKEN']
except KeyError:
    username = None
    access_token = None

org_name = 'lsst-camera-dh'

g = Github(username, access_token)
org = g.get_organization(org_name)
repos = dict([(repo.name, repo) for repo in org.get_repos()])

for name, repo in repos.items():
    try:
        tag, timestamp = latest_tag(repo)
        print name, tag.name, timestamp
    except IndexError:
        print name
