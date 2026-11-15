"""Author-side PSR edge, mask and spherical-distance regression tests."""
import math
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import detail_psr as psr


def test_nearest_uses_spherical_distance_and_true_north_not_grid_north():
    a = np.zeros((101, 101), dtype=np.float32)
    a[50, 51] = 1
    # At the south pole, the x-positive pixel has longitude 90.
    r = psr.analyze(a, -1000, 1000, 20, -90, 0, 900)
    assert r['inside_psr'] is False
    assert r['nearest_pixel_center']['distance_m'] == pytest.approx(20, abs=1e-5)
    assert r['nearest_pixel_center']['bearing_deg'] is None
    assert r['nearest_boundary']['distance_m'] == pytest.approx(10, abs=1e-5)
    assert r['search']['complete_within_radius'] is True


def test_inside_uses_cell_footprint_and_boundary_is_union_boundary():
    a = np.zeros((101, 101), dtype=np.float32)
    a[49:52, 49:52] = 1
    r = psr.analyze(a, -1000, 1000, 20, -90, 0, 900)
    assert r['inside_psr'] is True
    assert r['nearest_pixel_center']['distance_m'] == 0
    # Adjacent cell edges are not PSR region boundaries.
    assert r['nearest_boundary']['distance_m'] == pytest.approx(30, abs=1e-5)
    assert r['distance_to_psr_area_m'] == 0


def test_no_psr_reports_lower_bound_only_for_complete_coverage():
    a = np.zeros((101, 101), dtype=np.float32)
    r = psr.analyze(a, -1000, 1000, 20, -90, 0, 900)
    assert r['nearest_pixel_center'] is None
    assert r['distance_lower_bound_m'] == 900
    assert r['status'] == 'none_within_radius'
    a[50, 50] = np.nan
    r = psr.analyze(a, -1000, 1000, 20, -90, 0, 900)
    assert r['inside_psr'] is None
    assert r['distance_lower_bound_m'] is None
    assert r['status'] == 'incomplete_coverage'


def test_unknown_pixel_nearer_than_candidate_blocks_global_nearest_claim():
    a = np.zeros((101, 101), dtype=np.float32)
    a[50, 51] = np.nan
    a[50, 55] = 1
    r = psr.analyze(a, -1000, 1000, 20, -90, 0, 900)
    assert r['nearest_pixel_center']['nearest_guaranteed'] is False
    assert r['search']['complete_within_radius'] is False


def test_window_edge_never_becomes_false_psr_boundary():
    a = np.ones((101, 101), dtype=np.float32)
    r = psr.analyze(a, -1000, 1000, 20, -90, 0, 900)
    assert r['nearest_boundary'] is None
    assert r['inside_psr'] is True
    assert r['distance_to_psr_area_m'] == 0


def test_unexpected_class_rejected_instead_of_becoming_non_psr():
    a = np.zeros((101, 101), dtype=np.float32)
    a[0, 0] = 2
    with pytest.raises(ValueError, match='class'):
        psr.analyze(a, -1000, 1000, 20, -90, 0, 900)


def test_insufficient_window_does_not_claim_radius_search_complete():
    a = np.zeros((11, 11), dtype=np.float32)
    r = psr.analyze(a, -100, 100, 20, -90, 0, 900)
    assert r['search']['complete_within_radius'] is False
    assert r['distance_lower_bound_m'] is None


def test_dateline_bearing_is_finite_and_distance_short():
    az, distance = psr.inverse(-85, 179.99, -85, -179.99)
    assert distance == pytest.approx(52.8564, abs=.01)
    assert az == pytest.approx(90.00996, abs=.0001)


def test_resume_signature_changes_with_coordinates_radius_and_source():
    base = {'site': {'lat': -85, 'lon': 0}, 'radius_m': 10000, 'etag': 'a'}
    changed = dict(base, radius_m=20000)
    assert psr.signature(base) != psr.signature(changed)
    assert psr.signature(base) == psr.signature(dict(reversed(list(base.items()))))


def test_rotated_polar_grid_does_not_report_grid_east_as_true_east():
    # lon=90: increasing polar x points north, not east. Scale is not unity.
    a = np.zeros((101, 101), dtype=np.float32)
    a[50, 51] = 1
    sx = 2*1737400*math.tan(math.radians(5)/2)
    r = psr.analyze(a, sx-1000, 1000, 20, -85, 90, 900)
    assert r['nearest_pixel_center']['bearing_deg'] == pytest.approx(0, abs=1e-8)
    expected = 2*1737400*(math.atan((sx+20)/(2*1737400))-math.radians(2.5))
    assert r['nearest_pixel_center']['distance_m'] == pytest.approx(expected, abs=1e-5)
    assert r['nearest_pixel_center']['distance_m'] < 19.97


def test_nearby_result_can_be_guaranteed_despite_distant_coverage_edge():
    a = np.zeros((11, 11), dtype=np.float32)
    a[5, 6] = 1
    r = psr.analyze(a, -100, 100, 20, -90, 0, 900)
    assert r['search']['complete_within_radius'] is False
    assert r['nearest_pixel_center']['nearest_guaranteed'] is True
    assert r['nearest_boundary']['nearest_guaranteed'] is True
    assert r['status'] == 'found'


def test_nan_interface_is_not_reported_as_known_psr_boundary():
    a = np.ones((101, 101), dtype=np.float32)
    a[50, 51] = np.nan
    r = psr.analyze(a, -1000, 1000, 20, -90, 0, 900)
    assert r['inside_psr'] is True
    assert r['nearest_boundary'] is None


def test_unknown_site_does_not_claim_distance_to_psr_area():
    a = np.zeros((101, 101), dtype=np.float32)
    a[50, 50] = np.nan
    a[50, 55] = 1
    r = psr.analyze(a, -1000, 1000, 20, -90, 0, 900)
    assert r['nearest_boundary'] is not None
    assert r['inside_psr'] is None
    assert r['distance_to_psr_area_m'] is None


def test_resume_rejects_tampered_output_even_with_same_input_signature(tmp_path):
    path = tmp_path/'result.json'
    path.write_text('{"input_signature":"abc","distance":1}', encoding='utf-8')
    checkpoint = {'input_signature': 'abc', 'sha256': psr.file_hash(path)}
    assert psr.resume_matches(path, checkpoint, 'abc')
    path.write_text('{"input_signature":"abc","distance":2}', encoding='utf-8')
    assert not psr.resume_matches(path, checkpoint, 'abc')
    assert not psr.resume_matches(path, checkpoint, 'changed')


def test_psr_boundary_inside_radius_is_found_even_if_pixel_center_is_outside():
    a = np.zeros((101, 101), dtype=np.float32)
    a[50, 51] = 1
    r = psr.analyze(a, -1000, 1000, 20, -90, 0, 15)
    assert r['nearest_pixel_center'] is None
    assert r['nearest_boundary']['distance_m'] == pytest.approx(10, abs=1e-5)
    assert r['status'] == 'found'
    assert r['distance_lower_bound_m'] is None
