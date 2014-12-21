import os
import sys

from setuptools import setup, find_packages

here = os.path.abspath(os.path.dirname(__file__))
README = open(os.path.join(here, 'README.md')).read()
CHANGES = open(os.path.join(here, 'CHANGES.md')).read()

requires = []

setup(name='jane',
      version='0.0.1',
      description='Crude import solver for Android',
      long_description=README + '\n\n' + CHANGES,
      classifiers=[
        "Programming Language :: Python",
        "Programming Language :: Java",
        ],
      author='Takahiro Yoshimura',
      author_email='altakey@gmail.com',
      url='https://github.com/taky/jane',
      keywords='android java import',
      packages=find_packages(),
      include_package_data=True,
      zip_safe=False,
      install_requires = requires,
      entry_points = {'console_scripts':['solve = jane.shell:entry']}
      )

