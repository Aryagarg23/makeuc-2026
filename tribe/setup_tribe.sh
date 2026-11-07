#!/usr/bin/env bash
set -euo pipefail
cd ~
[ -d tribev2 ] || git clone -q https://github.com/facebookresearch/tribev2 ~/tribev2
cd ~/tribev2
git log -1 --format='commit %H %cd'
uv venv --python 3.12 .venv
. .venv/bin/activate
time uv pip install -e ".[plotting]" 2>&1 | tail -15
python -c "import torch,sys;print('python',sys.version.split()[0],'torch',torch.__version__,'cuda',torch.version.cuda,torch.cuda.is_available())"
