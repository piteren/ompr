from setuptools import setup, find_packages

from pypaq.lipytools.files import get_requirements


setup(
    name=               'ompr',
    version=            'v1.3.2',
    url=                'https://github.com/piteren/ompr.git',
    author=             'Piotr Niewinski',
    author_email=       'pioniewinski@gmail.com',
    description=        'Object based Multi-Processing Runner',
    packages=           find_packages(),
    install_requires=   get_requirements(),
    license=            'MIT')