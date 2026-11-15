# Task T independent comparison

Minchul Kim checks Soyun Jeong PR87 head 0fc89ad0791d7b19c3e7d7bfe03dd188c6f6dca5. Seed 15112026. All seven release-asset SHA256 values match committed manifest. Full original PDS LDEM64/16 downloaded and SHA256 checked. Own NumPy bilinear readers, full 360-azimuth spherical terrain march without early stop, 21912 topocentric ephemeris samples; no production imports. Sun means visible disc fraction, not sunlit hours. PNG 1000 output pixels per layer compared to independently interpolated raw floats, <=0.20001 pp quantization; DEM 10 raw cells <=0.1 pp. Every signed difference: comparisons.csv.

{
  "png": {
    "sun": {
      "max_abs_pp": 0.1999747168912991,
      "median_abs_pp": 0.10089714529895044
    },
    "earth": {
      "max_abs_pp": 0.19861964151123152,
      "median_abs_pp": 0.0
    },
    "both": {
      "max_abs_pp": 0.1997039432389991,
      "median_abs_pp": 0.03072046451707
    }
  },
  "dem": {
    "sun": {
      "max_abs_pp": 1.2729594933702515e-06,
      "median_abs_pp": 4.934581798732296e-07
    },
    "earth": {
      "max_abs_pp": 2.4851589786045736e-06,
      "median_abs_pp": 5.576374639826298e-08
    },
    "both": {
      "max_abs_pp": 1.4134069636906332e-06,
      "median_abs_pp": 3.237017459634117e-08
    }
  }
}

Failures: 0

[]

Reproduce: python verification/task_t/verify.py with pinned target checkout. Source URLs and hashes: target/docs/task_t/MANIFEST.json. Raw inputs ignored. Agreement is same-input algorithm agreement, not physical accuracy certification.
