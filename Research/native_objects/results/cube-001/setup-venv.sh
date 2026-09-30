#!/bin/bash
set -euo pipefail
python -m venv --system-site-packages /workspace/venv
source /workspace/venv/bin/activate
python -m pip install --disable-pip-version-check 'torch==2.8.0' 'torchvision==0.23.0' 'diffusers==0.35.2' 'transformers==4.57.3' 'huggingface-hub<1.0' accelerate safetensors omegaconf numpy scikit-image trimesh pillow tqdm einops warp-lang jaxtyping typeguard fpsample
python -m pip freeze > /workspace/dependencies.txt
python /workspace/oryn-cube-inputs/cube_worker.py --manifest /workspace/oryn-cube-inputs/cube_protocol_001.json --repo /workspace/cube --weights /workspace/weights --output /workspace/cube-results --download
python /workspace/oryn-cube-inputs/cube_worker.py --manifest /workspace/oryn-cube-inputs/cube_protocol_001.json --repo /workspace/cube --weights /workspace/weights --output /workspace/cube-results
cp /workspace/dependencies.txt /workspace/cube-results/dependencies.txt
printf 'finished\n' > /workspace/finished
