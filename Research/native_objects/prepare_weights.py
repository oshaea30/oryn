"""Explicit downloads for a research GPU worker, not an inference operation."""
import argparse
import hashlib
import json
from pathlib import Path

REVISIONS={'wgsxm/PartCrafter':'69a0ffc1dad5e48e7e5ed91c0609f2b1276eb31f'}

def main():
    p=argparse.ArgumentParser();p.add_argument('--repo',required=True,type=Path);p.add_argument('--download',action='store_true');a=p.parse_args()
    if not a.download:print(json.dumps({'revisions':REVISIONS,'downloads_started':False},indent=2));return
    from huggingface_hub import snapshot_download
    root=a.repo.resolve();weights=root/'pretrained_weights';weights.mkdir(exist_ok=True)
    manifest=weights/'oryn-weights.json'
    if manifest.exists():p.error('Weights already recorded; verify or use a new checkout')
    for repo,revision in REVISIONS.items():
        snapshot_download(repo_id=repo,revision=revision,local_dir=weights/repo.split('/')[1])
    files={}
    for path in sorted(weights.rglob('*')):
        if path.is_file() and '.cache' not in path.parts:
            h=hashlib.sha256()
            with path.open('rb') as f:
                for data in iter(lambda:f.read(1024*1024),b''):h.update(data)
            files[path.relative_to(root).as_posix()]=h.hexdigest()
    manifest.write_text(json.dumps({'revisions':REVISIONS,'files':files},indent=2))
    print('Pinned weights recorded:',manifest)

if __name__=='__main__':main()
