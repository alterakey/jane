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
#
from __future__ import print_function
import re

import os.path
import glob
from xml.etree import cElementTree as ET

from jane.cache import PackageCacheGenerator

class ImportSolver(object):
  def __init__(self, symbols, packages, source_path):
    self.symbols = symbols
    self.packages = packages
    PackageCacheGenerator.sprinkle(self.packages, symbols.namespace, source_path)

  def solve(self):
    resolved = set(self.symbols.imports)
    references = (self.symbols.uses - set(self.symbols.defines))
    for sym in (ImportSolver.constant_ref_degraded(s) for s in references):
      try:
        target = self.packages[sym]
        if ImportSolver.dequalified(target) in (ImportSolver.dequalified(package) for package in resolved):
          target = None
        if target == ('java.lang.%s' % sym):
          target = None
        if target == 'android.R':
          target = '%s.R' % self.packages['*sprinkle:package']
        if target is not None:
          if ImportSolver.namespace(target) != self.symbols.namespace:
            resolved.add(target)
      except KeyError:
        if sym not in self.symbols.defines:
          pass

    return resolved

  @staticmethod
  def dequalified(qualified):
    return qualified.split('.')[-1]

  @staticmethod
  def namespace(qualified):
    return '.'.join(qualified.split('.')[:-1])

  @staticmethod
  def constant_ref_degraded(qualified):
    return re.sub(r'\.(?:[A-Z0-9_]+|[a-z0-9_]+)$', '', qualified)

class ClasspathExpander(object):
  def __init__(self, symbols, target):
    self.project = ProjectSolver(symbols.namespace, target)

  def expand(self, classpath):
    ret = []
    for path in classpath.split(':'):
      if not path.startswith('!'):
        matches = glob.glob(self.normalize(path))
        ret.extend(matches)
      else:
        matches = glob.glob(self.normalize(path[1:]))
        for p in matches:
          try:
            ret.remove(p)
          except KeyError:
            pass
    return ret

  def normalize(self, component):
    expanded = os.path.expanduser(component)
    if not expanded.startswith(os.sep):
      return self.project.relative_path(expanded)
    else:
      return expanded

class ProjectSolver(object):
  def __new__(cls, namespace, target):
    from jane.ant import EclipseProjectSolver
    from jane.gradle import GradleProjectSolver
    for class_ in GradleProjectSolver, EclipseProjectSolver:
      try_ = class_(namespace, target)
      if try_.probe():
        return try_
    else:
      print('! project layout unknown')

class BaseProjectSolver(object):
  def __init__(self, namespace, target):
    self.namespace = namespace
    self.target = target
    self._cache = dict()

  def profile_name(self):
    key = 'profile'
    if key not in self._cache:
      for filename in glob.iglob(os.path.join(self.root_path(), '*.properties')):
        with open(filename, 'rb') as f:
          for line in f:
            m = re.match(r'^jane.profile\s*=\s*([A-Za-z0-9_]+?)$', line)
            if m:
              self._cache[key] = m.group(1)
              return self._cache[key]
      else:
        self._cache[key] = None
    return self._cache[key]

  @staticmethod
  def look_parent_to(level):
    yield '.%s' % os.sep
    for i in xrange(level):
      yield ('..%s' % os.sep) * i

  def probe(self):
    return os.path.exists(self.relative_path('AndroidManifest.xml'))

