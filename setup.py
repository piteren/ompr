from setuptools import setup, find_packages

# reads requirements
def get_requirements():
    with open('requirements.txt') as file:
        lines = [l[:-1] if l[-1]=='\n' else l for l in file.readlines()]
        return lines


setup(
    name=               'ompr',
    version=            'v1.2.1',
    url=                'https://github.com/piteren/ompr.git',
    author=             'Piotr Niewinski',
    author_email=       'pioniewinski@gmail.com',
    description=        'Object based Multi-Processing Runner',
    packages=           find_packages(),
    install_requires=   get_requirements(),
    license=            'MIT')