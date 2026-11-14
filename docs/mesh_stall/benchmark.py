"""Reuse the audited harness, comparing against PR52's colour-only fix.

python docs/mesh_stall/benchmark.py --variant baseline --runs 3
python docs/mesh_stall/benchmark.py --variant fixed --runs 3 --check
"""
import importlib.util,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('texture_benchmark',ROOT/'docs/texture_stall/benchmark.py')
bench=importlib.util.module_from_spec(spec);spec.loader.exec_module(bench)
bench.BASE='d5e2dd7'
if '--out' not in sys.argv:sys.argv+=['--out',str(ROOT/'data/processed/mesh_stall')]
if '--cpu-profile' not in sys.argv:sys.argv+=['--zoom-cycles']
bench.main()
