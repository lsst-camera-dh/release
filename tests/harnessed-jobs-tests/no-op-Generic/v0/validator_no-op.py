#!/usr/bin/env python
import glob
import lcatr.schema
import os

results = []


tsstat = 0
results.append(lcatr.schema.valid(lcatr.schema.get('no-op'),stat=tsstat))

lcatr.schema.write_file(results)
lcatr.schema.validate_file()
