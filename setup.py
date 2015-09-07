from setuptools import setup, find_packages
import sys, os

PACKAGE = 'sequencing_facility'
VERSION = __import__(PACKAGE).__version__

setup(name='mytardis-seqfac',
      version=VERSION,
      description="Sequencing Facility Django app for MyTardis",
      long_description="""\
      A MyTardis Django app for managing next generation sequencing data
      """,
      keywords='mytardis ngs bioinformatics',
      author='Andrew Perry',
      author_email='Andrew.Perry@monash.edu',
      url='',
      license='Apache Software License',
      packages=find_packages(exclude=['ez_setup', 'examples', 'tests']),
      include_package_data=True,
      zip_safe=False,
      install_requires=[
          # -*- Extra requirements: -*-
          'numpy',
      ],
      classifiers=[
          "Development Status :: 5 - Production/Stable",
          "Environment :: Web",
          "Intended Audience :: Science/Research",
          "License :: OSI Approved :: Apache Software License",
          "Operating System :: POSIX",
          "Programming Language :: Python",
          "Topic :: Scientific/Engineering :: Bio-Informatics",
      ],
      entry_points="""
      # -*- Entry points: -*-
      """,
      )
