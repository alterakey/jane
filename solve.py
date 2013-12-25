#!/usr/bin/env python
# solve-imports.py: Crude import solver.
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
#
# Usage example 1. from shell:
# $ solve-imports.py --cache-file=~/.solver.cache --classpath=/path/to/li
# bs/android-support-v4.jar:/usr/local/android-sdk/platforms/android-19/a
# ndroid.jar:/path/to/android/library/src/ /path/to/target.java
# import .....
# import .....
# ....
#
# Usage example 2. from elisp:
# (defun solve-imports ()
#   (interactive)
#   (shell-command-on-region
#    (region-beginning) (region-end)
#    (format "python /path/to/solve.py --cache-file=... %s"
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

    for m in re.finditer(r'\b(?P<constant_lookalikes>[A-Z0-9_]+|[a-z0-9_]+)\b\s*?=\s*?|(?:(?P<op>package|new|import|implements|extends|enum|private|public|protected|final|static|class|interface|volatile|synchronized|abstract) )+(?P<class>[A-Za-z0-9_.*]+)|\b(?P<class_in_context>[A-Z][A-Za-z0-9_]*(\.[A-Z][A-Za-z0-9_]*)*)(?:\.(?!>\.)|\b)', self.f.read()):
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
    for sym in (ImportSolver.constant_ref_degraded(s) for s in self.symbols.uses):
      try:
        target = self.packages[sym]
        if ImportSolver.dequalified(target) in (ImportSolver.dequalified(package) for package in resolved):
          target = None
        if target == ('java.lang.%s' % sym):
          target = None
        if target == 'android.R':
          target = '%s.R' % self.packages['*sprinkle:package']
        if target is not None:
          resolved.add(target)
      except KeyError:
        if sym not in self.symbols.defines:
          pass

    resolved -= set(self.symbols.defines)
    return resolved

  @staticmethod
  def dequalified(qualified):
    return qualified.split('.')[-1]

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
            self.packages['.'.join(target)] = root
        else:
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
    package_root = None
    path = os.path.dirname(os.path.realpath(source_path))
    root = namespace is not None and path.replace(namespace.replace('.', os.sep), '') or path
    for root, dirlist, filelist in os.walk(root):
      if root is None or root != path:
        if package_root is None:
          for p in '.', '..':
            try:
              with open(os.path.join(root, p, 'AndroidManifest.xml'), 'rb') as f:
                try:
                  package_root = ET.parse(f).getroot().attrib['package']
                except:
                  print("! cannot parse AndroidManifest.xml: cannot determine package name: %s" % sys.exc_info()[1], file=sys.stderr)
            except IOError, e:
              pass
        for filename in filter(lambda x: x.endswith('.java'), filelist):
          with open(os.path.join(root, filename), 'rb') as f:
            dep = JavaSourceParser(f).parse()
            for scope, define in dep.scoped_defines():
              packages[define] = '%s.%s' % (dep.namespace, scope)

    if package_root is not None:
      packages['*sprinkle:package'] = package_root

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

if __name__ == '__main__':
  import sys
  import getopt

  classpath = None
  cache_file = 'packages.cache.gz'

  def help():
    print('''\
usage: %s --classpath=<jar|source_path>:... <target file>
''' % sys.argv[0])
    sys.exit(2)
  
  try:
    opts, arg = getopt.getopt(sys.argv[1:], 'c:f:', ['classpath=', 'cache-file='])
    for k, v in opts:
      if k in ('c', '--classpath'): classpath = v.split(':')
      if k in ('f', '--cache-file'): cache_file = os.path.expanduser(v)
    target = arg[0]
  except getopt.GetoptError, e:
    print('Cannot parse options: %s' % e, file=sys.stderr)
    help()
  except IndexError, e:
    print('You need target file', file=sys.stderr)
    help()

  if not classpath:
    print('You need classpath', file=sys.stderr)
    help()

  cacher = PackageCacheGenerator(cache_file, classpath)
  if cacher.needs_update():
    cacher.update().generate()

  with open(target, 'r') as f:
    for import_ in sorted(ImportSolver(JavaSourceParser(f).parse(), PackageCacheLoader(cache_file).load(), target).solve()):
      print('import %s;' % import_)
