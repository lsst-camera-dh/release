#!/usr/bin/env python
import os
import sys

jobname = os.environ["LCATR_JOB"]
unittype = os.environ["LCATR_UNIT_TYPE"]
jobdir = "%s/share/%s/%s" % (os.environ["VIRTUAL_ENV"], jobname,
                          os.environ["LCATR_VERSION"])

print "jobname is ", jobname
print "unit type is ", unittype
print "unit id is ", os.environ["LCATR_UNIT_ID"]
print "jobdir is ", jobdir

