#!/bin/sh
set -eu
# tag + build the sdist/wheel
tag="v$(python -c 'import pulsechat; print(pulsechat.__version__)')"
git tag -a "$tag" -m "release $tag"
python -m pip install --quiet build && python -m build
