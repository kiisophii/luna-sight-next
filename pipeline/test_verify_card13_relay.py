"""Analytic checks for the separate card-13 verifier (no production imports)."""
import sys
import json
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import verify_card13_relay as verify


def test_ecef_clearance_and_fresnel_hand_values():
    angle = 10000 / verify.RADIUS
    a = np.array([verify.RADIUS + 2, 0, 0])
    b = (verify.RADIUS + 50) * np.array([np.cos(angle), np.sin(angle), 0])
    t = (verify.RADIUS + 10) * np.array([[np.cos(angle / 2), np.sin(angle / 2), 0]])
    result = verify.profile_geometry(a, b, t, {"S": 2.2e9, "Ka": 26e9})
    assert result["min_clear_m"] == pytest.approx(8.805, abs=.01)
    assert result["fresnel"]["S"] == pytest.approx(.4771, abs=.002)
    assert result["fresnel"]["Ka"] == pytest.approx(1.640, abs=.005)


def test_polar_horizon_of_flat_sphere():
    distances = np.array([100., 1000., 10000.])
    mask = verify.trace_mask(-89., 37., 0., 2., lambda a, b: np.zeros(a.shape), [0., 90., 180.], distances)
    r, ro = verify.RADIUS, verify.RADIUS + 2
    expected = np.degrees(np.max(np.arctan2(r * np.cos(distances / r) - ro,
                                           r * np.sin(distances / r))))
    assert np.allclose(mask, expected, atol=1e-9)


def test_interpolation_does_not_fill_missing_neighbors():
    z = np.array([[1., 2.], [3., np.nan]])
    assert np.isnan(verify.bilinear(z, np.array([.25]), np.array([.75]))[0])


def test_missing_ray_fails_instead_of_assuming_clear():
    with pytest.raises(ValueError, match="missing terrain"):
        verify.trace_mask(0., 0., 0., 2., lambda a, b: np.full(a.shape, np.nan), [0.], np.array([100.]))


def test_hour_selection_covers_window_without_duplicates():
    hours = verify.hour_indices(43824, 30)
    assert len(hours) == len(np.unique(hours)) == 30
    assert hours[0] == 0 and hours[-1] == 43823


@pytest.mark.parametrize('epoch_location', ['inputs', 'top'])
def test_checkpoint_must_match_output_inputs_and_be_complete(tmp_path, epoch_location):
    record = dict(lat=0., lon=1., window={'n': 8}, candidates={'n': 2},
                  params={'heights_m': [15.], 'engine_version': 2}, input_identity={'source': 'new'})
    key = dict(lat=0., lon=1., v=2, inputs={'source': 'old'})
    if epoch_location == 'inputs':
        record['input_identity']['n'] = 8
        key['inputs']['n'] = 8
    else:
        key['n'] = 8
    (tmp_path/'key.json').write_text(json.dumps(key))
    np.save(tmp_path/'vis.npy', np.array([[[255]], [[0]]], dtype=np.uint8))
    np.save(tmp_path/'done.npy', np.array([True, True]))
    with pytest.raises(ValueError, match='identity'):
        verify.load_reference(record, tmp_path, 0, 0)
    key['inputs'] = record['input_identity']
    (tmp_path/'key.json').write_text(json.dumps(key))
    assert verify.load_reference(record, tmp_path, 0, 0).all()
    np.save(tmp_path/'done.npy', np.array([True, False]))
    with pytest.raises(ValueError, match='incomplete'):
        verify.load_reference(record, tmp_path, 0, 0)

