"""Restore portable checkpoints and JSON run metadata into a fresh directory."""
import argparse
from pathlib import Path
import shutil
import numpy as np
import torch
p=argparse.ArgumentParser();p.add_argument('source',type=Path);p.add_argument('output',type=Path)
a=p.parse_args();a.output.mkdir(parents=True,exist_ok=False)
for source in a.source.glob('*.json'):shutil.copy2(source,a.output/source.name)
for source in a.source.glob('*.npz'):
    with np.load(source,allow_pickle=False) as arrays:
        state={k:torch.from_numpy(arrays[k].copy()) for k in arrays.files}
    torch.save(state,a.output/(source.stem+'.pt'))
