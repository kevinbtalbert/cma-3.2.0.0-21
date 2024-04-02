from distutils.core import setup
from setuptools import find_packages

with open("requirements.txt", "r") as f:
    install_requires = [line.strip() for line in f]

setup(
    name='AM2CM Python Utilities',
    version='1.0',
    description='Collection of utilities that can be used by AM2CM-Ansible project for AM2CM migrations',
    packages=find_packages(),
    url='https://cloudera.atlassian.net/wiki/spaces/ENG/pages/1532298174/AM2CM+and+HDP-CDP+Upgrade',
    author='Cloudera - AM2CM Team',
    install_requires=install_requires
)
