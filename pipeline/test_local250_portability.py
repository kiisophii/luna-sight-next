"""Only coordinate round-off is tolerated; integer grid identity remains exact."""
from check_local250 import same_grid_node

def test_roundoff_only():
    want=dict(index=1,e_m=250,n_m=0,lat=-89.123456789,lon=12.345678901)
    point=dict(want,lat=want['lat']+1e-12,lon=want['lon']-1e-12)
    assert same_grid_node(point,want)
    assert not all(point[k]==v for k,v in want.items())
def test_real_coordinate_change_rejected():
    want=dict(index=1,e_m=250,n_m=0,lat=-89.,lon=12.)
    assert not same_grid_node(dict(want,lat=-88.999999),want)
    assert not same_grid_node(dict(want,lon=12.000001),want)
def test_grid_order_and_offsets_remain_exact():
    want=dict(index=1,e_m=250,n_m=0,lat=-89.,lon=12.)
    for key in ['index','e_m','n_m']:
        assert not same_grid_node(dict(want,**{key:want[key]+1}),want)
def test_nonfinite_coordinates_rejected():
    want=dict(index=1,e_m=250,n_m=0,lat=-89.,lon=12.)
    for bad in [float('nan'),float('inf')]:
        assert not same_grid_node(dict(want,lat=bad),want)
