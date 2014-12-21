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
import re

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
