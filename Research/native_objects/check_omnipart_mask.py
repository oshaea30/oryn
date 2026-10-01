"""CPU-only reproduction of a pinned upstream mask operation; not model inference.

Supply the unmodified public inference_utils.py. Only its reviewed NumPy-only
smart_downsample_mask function executes; importing the GPU module is unnecessary.
Synthetic masks test input retention, not generated geometry or semantic quality.
"""
import argparse
import ast
import hashlib
import json
from pathlib import Path

import numpy as np

REVISION = 'ceb1a4ff2d279a57a673d0f65954735c6bf8231c'
SOURCE_SHA256 = '782b8d28cfc6f37fa1ec8f145f7f0d16d920cc472026c66c26211514144a5f7a'
SOURCE_URL = (
    'https://raw.githubusercontent.com/HKU-MMLab/OmniPart/' + REVISION
    + '/modules/inference_utils.py'
)


def load_operation(source):
    raw = source.read_bytes()
    if hashlib.sha256(raw).hexdigest() != SOURCE_SHA256:
        raise ValueError('Source differs from reviewed revision; refusing execution.')
    tree = ast.parse(raw)
    selected = [node for node in tree.body
                if isinstance(node, ast.FunctionDef)
                and node.name == 'smart_downsample_mask']
    if len(selected) != 1:
        raise ValueError('Expected exactly one reviewed function.')
    namespace = {'np': np}
    exec(compile(ast.Module(body=selected, type_ignores=[]), str(source), 'exec'), namespace)
    return namespace['smart_downsample_mask']


def positive_ids(mask):
    return [int(value) for value in np.unique(mask) if value > 0]


def evaluate(source):
    operation = load_operation(source)
    broad = np.zeros((518, 518), dtype=np.int32)
    for index in range(9):
        row, col = divmod(index, 3)
        broad[28 + row * 168:140 + row * 168,
              28 + col * 168:140 + col * 168] = index + 1
    small = broad.copy()
    small[small == 9] = 0
    small[370, 202] = 9  # One visible pixel surrounded by label 8 in a 14x14 bin.
    cases = []
    for name, mask in [('nine_large_regions', broad), ('nine_regions_one_tiny', small)]:
        result = operation(mask, (37, 37))
        before, after = positive_ids(mask), positive_ids(result)
        cases.append({'fixture': name, 'input_shape': list(mask.shape),
                      'output_shape': list(result.shape), 'input_ids': before,
                      'output_ids': after, 'lost_ids': sorted(set(before) - set(after))})
    if cases[0]['lost_ids'] != [] or cases[1]['lost_ids'] != [9]:
        raise RuntimeError('Unexpected reproduction result; inspect before drawing conclusions.')
    return {'id': 'structure-preflight-001-mask', 'source_url': SOURCE_URL,
            'source_sha256': SOURCE_SHA256, 'numpy_version': np.__version__,
            'scope': 'Exact upstream downsampling function only; synthetic masks, no model or GPU.',
            'fixtures': cases, 'observation': 'A visible small label can disappear before inference.',
            'geometry_generated': False, 'model_quality_assessed': False,
            'paid_calls': 0, 'native_generation_goal_passed': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = evaluate(args.source)
    with args.output.open('x') as stream:
        json.dump(result, stream, indent=2)
        stream.write('\n')
    print(json.dumps({'fixtures': result['fixtures'], 'paid_calls': 0}))


if __name__ == '__main__':
    main()
