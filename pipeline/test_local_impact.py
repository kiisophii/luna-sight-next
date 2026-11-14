import numpy as np
import pytest
import local_impact as impact


def test_radius_statistics_exclude_square_corners_and_use_linear_iqr():
    points=[dict(e_m=e,n_m=n,lat=0,lon=0,sun_frac=v,earth_frac=v,both_frac=v,longest_dark_h=int(v*10))
            for e,n,v in [(0,0,0),(1000,0,.25),(0,1000,.5),(-1000,0,.75),(0,-1000,1),(1000,1000,99)]]
    result=impact.radius_summary(points,1)
    assert result['n']==5
    assert result['sun_frac']==dict(min=0,max=1,q1=.25,q3=.75,iqr=.5)


def test_pair_separation_and_adjacent_only():
    points=[dict(index=i,e_m=i*1000,n_m=0,lat=0,lon=np.degrees(i*1000/1737400),sun_frac=v,ground_resolution_m=5)
            for i,v in enumerate([0,.4,1])]
    pair=impact.striking_pair(points,'sun_frac',adjacent=True)
    assert (pair['a']['index'],pair['b']['index'])==(1,2)
    assert pair['distance_km']==pytest.approx(1,abs=1e-9)
    whole=impact.striking_pair(points,'sun_frac')
    assert whole['distance_km']==pytest.approx(2,abs=1e-9)


def test_one_tower_outage_is_not_network_outage():
    direct=np.array([0,0,0,0],dtype=bool)
    first=np.array([1,1,0,0],dtype=bool)
    second=~first
    result=impact.single_link(direct,first,True)
    assert result['link_frac']==.5 and result['longest_outage_h']==2
    assert impact.single_link(direct,first|second,True)['longest_outage_h']==0
    assert impact.single_link(direct,first,False)['longest_outage_h']==4


def test_relay_checkpoint_uses_most_significant_bit_first():
    assert impact.unpack_visibility(np.array([128,64],dtype=np.uint8),10).tolist()==[True,False,False,False,False,False,False,False,False,True]


def test_thresholds_are_strict_then_inclusive():
    rows=[dict(id='A',direct_frac=.49,heights=[dict(height_m=h,link_frac=.5) for h in [5,15,30,50]]),
          dict(id='B',direct_frac=.5,heights=[dict(height_m=h,link_frac=1) for h in [5,15,30,50]])]
    counts=impact.threshold_counts(rows)
    assert counts['below_50_count']==1
    assert counts['reached_50_by_height']=={'5':1,'15':1,'30':1,'50':1}
