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
import gzip
import json
import os
import re
import subprocess

from jane.parse import JavaSourceParser

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
      from jane.base import ProjectSolver
      packages['*sprinkle:package'] = ProjectSolver(namespace, source_path).package_name()

  def generate(self):
    with gzip.GzipFile(self.cache_file, 'wb') as f:
      json.dump(dict(classpath=self.classpath, packages=self.packages), f, sort_keys=True, indent=2, separators=(',', ': '))

class PackageCacheLoader(object):
  def __init__(self, cache_file):
    self.cache_file = cache_file

  def classpath(self):
    with gzip.GzipFile(self.cache_file, 'rb') as f:
      return json.load(f)['classpath']

  def load(self):
    with gzip.GzipFile(self.cache_file, 'rb') as f:
      return json.load(f)['packages']
