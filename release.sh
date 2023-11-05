#!/bin/bash
rm -rf build
rm -rf dist
rm -rf ompr.egg-info
python setup.py sdist bdist_wheel
python -m twine upload -r pypi dist/*