# Jane: Crude import solver.
# Copyright 2013 Takahiro Yoshimura <altakey@gmail.com>
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
from __future__ import print_function
import re

import os.path
import ConfigParser
import sys
import getopt

from jane.base import ClasspathExpander, ImportSolver, ProjectSolver
from jane.parse import JavaSourceParser
from jane.cache import PackageCacheGenerator, PackageCacheLoader

def entry():
  classpath = None
  cache_file = None
  config_file = None

  def help():
    print('''\
usage: %s [--profile=<config file>[:<profile name>]] [--classpath=<jar|source_path>:...] [--cache-file=<cache file>] <target file>
''' % sys.argv[0])
    sys.exit(2)

  def expand_cache_file(cache_file):
    return os.path.expanduser(cache_file)

  try:
    opts, arg = getopt.getopt(sys.argv[1:], 'p:c:f:', ['profile=','classpath=', 'cache-file='])
    for k, v in opts:
      if k in ('p', '--profile'):
        try:
          path, profile = v.split(':')
        except ValueError:
          path, profile = v, None
        config_file = dict(path=path, profile=profile)
      if k in ('c', '--classpath'): classpath = v
      if k in ('f', '--cache-file'): cache_file = expand_cache_file(v)
    target = arg[0]
  except getopt.GetoptError, e:
    print('Cannot parse options: %s' % e, file=sys.stderr)
    help()
  except IndexError, e:
    print('You need target file', file=sys.stderr)
    help()

  with open(target, 'r') as f:
    symbols = JavaSourceParser(f).parse()
    if config_file:
      path = config_file['path']
      profile = None

      if config_file['profile'] is not None:
        profile = config_file['profile']
      else:
        profile = ProjectSolver(symbols.namespace, target).profile_name()
        if not profile:
          print('You need to explicitly set a profile', file=sys.stderr)
          help()

      parser = ConfigParser.SafeConfigParser()
      try:
        with open(os.path.expanduser(path), 'r') as f:
          parser.readfp(f)
        if not classpath:
          try:
            classpath = parser.get(profile, 'classpath')
          except ConfigParser.NoOptionError:
            pass
        if not cache_file:
          try:
            cache_file = expand_cache_file(parser.get(profile, 'cache-file'))
          except ConfigParser.NoOptionError:
            pass
      except ConfigParser.NoSectionError:
        print('Cannot find profile: %s' % profile, file=sys.stderr)
        help()

    if not classpath or not cache_file:
      print('You need to set profile or classpath/cache-file', file=sys.stderr)
      help()

    cacher = PackageCacheGenerator(cache_file, ClasspathExpander(symbols, target).expand(classpath))
    if cacher.needs_update():
      cacher.update().generate()

    for import_ in sorted(ImportSolver(symbols, PackageCacheLoader(cache_file).load(), target).solve()):
      print('import %s;' % import_)
