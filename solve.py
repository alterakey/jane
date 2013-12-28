#!/usr/bin/env python
# solve.py: Crude import solver.
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
# Usage scenarios with config file, written as follows, is at ~/solver.ini:
# [my-project]
# cache-file=~/.solver.myproject.cache
# classpath=/usr/local/android-sdk/extras/android/support/v4/android-supp
# ort-v4.jar:/usr/local/android-sdk/platforms/android-19/android.jar:/pat
# h/to/android/library/src/ /path/to/target.java
#
# 1. From shell:
# $ solve.py --profile ~/solver.ini:my-project /path/to/target.java
# import .....
# import .....
# ....
#
# 2. From elisp:
# (defun solve-imports ()
#   (interactive)
#   (shell-command-on-region
#    (region-beginning) (region-end)
#    (format "python /path/to/solve.py --profile=~/solver.ini:my-project %s"
#            (buffer-file-name))
#    t
#    t))
#
# ... Then, bind this defun to some key, select import block and invoke over it.
#
from __future__ import print_function
import re

import gzip
import json
import subprocess
import os.path
import ConfigParser
import glob
import itertools
from xml.etree import cElementTree as ET

class SymbolMap(object):
  def __init__(self):
    self.namespace = None
    self.imports = set()
    self.defines = list()
    self.uses = set()

  def __str__(self):
    return '<SymbolMap: uses:%r defines:%r imports:%r>' % (self.uses, self.defines, self.imports)

  def scoped_defines(self):
    scope = None
    for define in self.defines:
      if scope is None:
        scope = define
        yield define, define
      else:
        yield scope, '%s.%s' % (scope, define)

class JavaSourceParser(object):
  def __init__(self, f):
    self.f = f

  def parse(self):
    symbols = SymbolMap()
    intrinsic = frozenset([
      'int', 'boolean', 'byte', 'char', 'double', 'float', 'long', 'void', 
      'Integer', 'Boolean', 'Char', 'Double', 'Float', 'Long', 'String', 'Void', 
      'Exception', 'Runnable'
    ])

    for m in re.finditer(r'\b(?P<constant_lookalikes>[A-Z0-9_]+|[a-z0-9_]+)\b\s*?=\s*?|(?:(?P<op>package|new|import|implements|extends|enum|private|public|protected|final|static|class|interface|volatile|synchronized|abstract) )+\b(?P<class>[A-Za-z0-9_.*]+)\b|\b(?P<class_in_context>[A-Z][A-Za-z0-9_]*(\.[A-Z][A-Za-z0-9_]*)*)(?:\.(?!>\.)|\b)', self.f.read()):
      class_ = filter(None, (m.group('class'), m.group('class_in_context'), m.group('constant_lookalikes')))[0]
      op = {
        'package': 'namespace',
        'import': 'imports',
        'class': 'defines',
        'interface': 'defines',
        'enum': 'defines',
      }.get(m.group('op'), m.group('constant_lookalikes') is not None and 'defines' or 'uses')
      if class_ not in intrinsic:
        if op == 'defines':
          symbols.defines.append(class_)
        elif op == 'namespace':
          symbols.namespace = class_
        else:
          getattr(symbols, op).add(class_)
    return symbols

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

class PackageCacheGenerator(object):
  def __init__(self, cache_file, classpath):
    self.packages = dict()
    self.cache_file = cache_file
    self.classpath = classpath

  def update(self):
    for path in self.classpath:
      self.add(path)
    return self

  def add(self, package_path):
    if os.path.isdir(package_path):
      PackageCacheGenerator.sprinkle(self.packages, None, package_path)
    else:
      for m in re.finditer(r'([A-Za-z0-9$/]+)\.class$', subprocess.check_output('jar -tvf %s' % package_path, shell=True), flags=re.MULTILINE):
        qualified = m.group(1).replace(os.sep, '.')
        packagename = qualified.split('.')[-1]
        if '$' in packagename:
          root = re.sub('\$.*$', '', qualified)
          target = []
          for inner in packagename.split('$'):
            target.append(inner)
            decorated = '.'.join(target)
            if decorated not in self.packages:
              self.packages[decorated] = root
        else:
          if packagename not in self.packages:
            self.packages[packagename] = qualified
      
    return self

  def needs_update(self):
    def mtime(x):
      try:
        return os.path.getmtime(x)
      except OSError, e:
        return None

    try:
      cache_at = os.path.getmtime(self.cache_file)
      for path in self.classpath:
        if os.path.isdir(path):
          for root, dirlist, filelist in os.walk(path):
            if filelist and cache_at < max((mtime(x) for x in filelist)):
              return True
        else:
          if cache_at < mtime(path):
            return True
      else:
        try:
          if PackageCacheLoader(self.cache_file).classpath() != self.classpath:
            return True
          else:
            return False
        except KeyError:
          return True
    except OSError, e:
      return True

  @staticmethod
  def sprinkle(packages, namespace, source_path):
    path = os.path.dirname(os.path.realpath(source_path))
    root = namespace is not None and path.replace(namespace.replace('.', os.sep), '') or path
    for root, dirlist, filelist in os.walk(root):
      if root is None or root != path:
        for filename in filter(lambda x: x.endswith('.java'), filelist):
          with open(os.path.join(root, filename), 'rb') as f:
            dep = JavaSourceParser(f).parse()
            for scope, define in dep.scoped_defines():
              packages[define] = '%s.%s' % (dep.namespace, scope)

    if namespace is not None:
      packages['*sprinkle:package'] = ProjectSolver(namespace, source_path).package_name()

  def generate(self):
    with gzip.GzipFile(self.cache_file, 'wb') as f:
      json.dump(dict(classpath=self.classpath, packages=self.packages), f, sort_keys=True, indent=2, separators=(',', ': '))

class PackageCacheLoader(object):
  def __init__(self, cache_file):
    self.cache_file = cache_file

  def classpath(self):
    with gzip.GzipFile(cache_file, 'rb') as f:
      return json.load(f)['classpath']

  def load(self):
    with gzip.GzipFile(cache_file, 'rb') as f:
      return json.load(f)['packages']

class ClasspathExpander(object):
  def __init__(self, symbols, target):
    self.project = ProjectSolver(symbols.namespace, target)

  def expand(self, classpath):
    return [p for p in itertools.chain(*[glob.iglob(self.normalize(component)) for component in classpath.split(':')])]

  def normalize(self, component):
    expanded = os.path.expanduser(component)
    if not expanded.startswith(os.sep):
      return self.project.relative_path(expanded)
    else:
      return expanded

class ProjectSolver(object):
  def __init__(self, namespace, target):
    self.namespace = namespace
    self.target = target
    self._cache = dict()

  def root_path(self):
    key = 'root'
    if key not in self._cache:
      path = os.path.dirname(os.path.realpath(self.target))
      root = path.replace(self.namespace.replace('.', os.sep), '')
      for p in ProjectSolver.look_parent_to(5):
        look = os.path.join(root, p)
        if os.path.exists(os.path.join(look, 'AndroidManifest.xml')):
          self._cache[key] = os.path.realpath(look)
    return self._cache[key]

  def relative_path(self, filename):
    return os.path.join(self.root_path(), filename)

  def package_name(self):
    key = 'package'
    if key not in self._cache:
      with open(ProjectSolver(self.namespace, self.target).relative_path('AndroidManifest.xml'), 'rb') as f:
        try:
          self._cache[key] = ET.parse(f).getroot().attrib['package']
        except:
          print("! cannot parse AndroidManifest.xml: cannot determine package name: %s" % sys.exc_info()[1], file=sys.stderr)
    return self._cache[key]

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

if __name__ == '__main__':
  import sys
  import getopt

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
