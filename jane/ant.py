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

import os.path
from xml.etree import cElementTree as ET

from jane.base import ProjectSolver, BaseProjectSolver

class EclipseProjectSolver(BaseProjectSolver):
  def root_path(self):
    key = 'root'
    if key not in self._cache:
      path = os.path.dirname(os.path.realpath(self.target))
      root = path.replace(self.namespace.replace('.', os.sep), '')
      for p in self.look_parent_to(5):
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
