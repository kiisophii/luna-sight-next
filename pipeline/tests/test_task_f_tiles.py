import importlib.util
from pathlib import Path
import numpy as np
import pytest
spec=importlib.util.spec_from_file_location('task_f_tiles',Path(__file__).parents[1]/'task_f_tiles.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

def test_encoding_original_heights_within_quantization():
    heights=np.array([[-100.13,-98.74,5.01],[-102.61,23.17,18.01],[27.5,-90.3,0.]])
    raw=m.encode(heights,.25)
    back=m.decode(raw,3,.25)
    assert np.max(np.abs(back-heights))<=.125
    assert np.array_equal(back,np.round(heights/.25)*.25)

def test_missing_heights_are_rejected():
    with pytest.raises(ValueError):m.encode(np.array([[0.,np.nan],[1.,2.]]),.25)

def test_native_grid_alignment():
    assert m.source_offset(-21807.5,9922.5,-559997.5,559997.5,5)==(110015,107638)
    with pytest.raises(ValueError):m.source_offset(-21807.,9922.5,-559997.5,559997.5,5)
