#!/usr/bin/env python
# solve.py: Crude import solver.
# Copyright 2013 Takahiro Yoshimura
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

import gzip
import json
import subprocess
import os.path

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
      'Integer', 'Boolean', 'Char', 'Double', 'Float', 'Long', 'Void', 
      'Exception', 'Runnable'
    ])

    for m in re.finditer(r'(?:(package|new|import|implements|extends|enum|private|public|protected|final|static|class|interface|volatile|synchronized) )+([A-Za-z0-9_.*]+)', self.f.read()):
      class_ = m.group(2)
      op = {
        'package': 'namespace',
        'import': 'imports',
        'class': 'defines',
        'interface': 'defines',
        'enum': 'defines'
      }.get(m.group(1), 'uses')
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
    for sym in self.symbols.uses:
      try:
        target = self.packages[sym]
        print('%s -> %s' % (sym, target), file=sys.stderr)
        resolved.add(target)
      except KeyError:
        if sym not in self.symbols.defines:
          print('?: %s' % sym, file=sys.stderr)
    resolved -= set(self.symbols.defines)
    return resolved

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
      self.packages = PackageCacheGenerator.sprinkle(self.packages, None, [package_path])
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
    for path in source_path:
        path = os.path.dirname(os.path.realpath(path))
        root = namespace is not None and path.replace(namespace.replace('.', os.sep), '') or path
        for root, dirlist, filelist in os.walk(root):
          if root is None or root != path:
            for filename in filter(lambda x: x.endswith('.java'), filelist):
              with open(os.path.join(root, filename), 'rb') as f:
                dep = JavaSourceParser(f).parse()
                for scope, define in dep.scoped_defines():
                  packages[define] = '%s.%s' % (dep.namespace, scope)
                    
    return packages

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
    usage: %s --classpath=<jar|source_path>:... <buffer file name> < (buffer content)
''')
    sys.exit(2)
  
  try:
    opts, arg = getopt.getopt(sys.argv[1:], 'c:f:', ['classpath=', 'cache-file='])
    for k, v in opts:
      if k in ('c', '--classpath'): classpath = v.split(':')
      if k in ('f', '--cache-file'): cache_file = os.path.expanduser(v)
    source_path = arg
  except getopt.GetoptError, e:
    print('cannot parse options: %s' % e, file=sys.stderr)
    help()

  if not classpath:
    print('You need classpath', file=sys.stderr)
    help()

  cacher = PackageCacheGenerator(cache_file, classpath)
  if cacher.needs_update():
    cacher.update().generate()

  for import_ in sorted(ImportSolver(JavaSourceParser(sys.stdin).parse(), PackageCacheLoader(cache_file).load(), source_path).solve()):
    print('import %s;' % import_)
