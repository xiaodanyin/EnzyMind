"""Runs inside the disposable container. This is an API convenience, not a security boundary."""
import json
import runpy
from pathlib import Path

inputs = json.loads(Path('/work/input.json').read_text())
namespace = runpy.run_path('/work/code.py', init_globals={
    'data': inputs['data'], 'results': inputs['results'],
    'input_files': inputs['files'], 'output_dir': Path('/work/output'),
}, run_name='__main__')
Path('/work/result.json').write_text(json.dumps(namespace.get('result'), ensure_ascii=False, allow_nan=False))
