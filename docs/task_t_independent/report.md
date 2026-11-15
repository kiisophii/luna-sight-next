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

## Every independently recomputed raw cell

|Row|Column|Latitude|Longitude|Field|Raw float32|Independent|Difference pp|Pass|
|---|---|---|---|---|---|---|---|---|
|1092|1891|-46.5625|56.4375|sun|0.4256524443626404|0.4256524422738062|-2.0888341611957628e-7|true|
|1092|1891|-46.5625|56.4375|earth|0.9901880025863647|0.9901880248265791|0.0000022240214336832764|true|
|1092|1891|-46.5625|56.4375|both|0.4203176200389862|0.42031763417305584|0.0000014134069636906332|true|
|1243|813|-65.4375|-78.3125|sun|0.4525187015533447|0.45251870338116834|1.8278236146862525e-7|true|
|1243|813|-65.4375|-78.3125|earth|0.75346839427948|0.7534684191310698|0.0000024851589786045736|true|
|1243|813|-65.4375|-78.3125|both|0.3389010727405548|0.33890105878057686|-0.0000013959977951394364|true|
|388|468|41.4375|-121.4375|sun|0.435263991355896|0.435263987807654|-3.548241978013067e-7|true|
|388|468|41.4375|-121.4375|earth|0|0|0|true|
|388|468|41.4375|-121.4375|both|0|0|0|true|
|891|710|-21.4375|-91.1875|sun|0.4916813373565674|0.4916813433368156|5.980248241055364e-7|true|
|891|710|-21.4375|-91.1875|earth|0.2829499840736389|0.28294998174516245|-2.3284764671949176e-7|true|
|891|710|-21.4375|-91.1875|both|0.1423877328634262|0.14238773274917854|-1.1424766688250543e-8|true|
|281|109|54.8125|-166.3125|sun|0.4819197356700897|0.48191974839968466|0.0000012729594933702515|true|
|281|109|54.8125|-166.3125|earth|0|0|0|true|
|281|109|54.8125|-166.3125|both|0|0|0|true|
|460|1136|32.4375|-37.9375|sun|0.499508798122406|0.4995088085860149|0.0000010463608868249707|true|
|460|1136|32.4375|-37.9375|earth|1|1|0|true|
|460|1136|32.4375|-37.9375|both|0.49940672516822815|0.49940671778021173|-7.388016420861732e-7|true|
|952|494|-29.0625|-118.1875|sun|0.48022231459617615|0.4802223152532072|6.57031040685041e-8|true|
|952|494|-29.0625|-118.1875|earth|0|0|0|true|
|952|494|-29.0625|-118.1875|both|0|0|0|true|
|658|2151|7.6875|88.9375|sun|0.4618857502937317|0.46188576057047376|0.0000010276742068437983|true|
|658|2151|7.6875|88.9375|earth|0|0|0|true|
|658|2151|7.6875|88.9375|both|0|0|0|true|
|598|697|15.1875|-92.8125|sun|0.45534953474998474|0.45534952857881067|-6.171174071756269e-7|true|
|598|697|15.1875|-92.8125|earth|0.22645126283168793|0.2264512595837897|-3.2478982281425317e-7|true|
|598|697|15.1875|-92.8125|both|0.11140014976263046|0.11140014603870026|-3.723930205867809e-7|true|
|191|623|66.0625|-102.0625|sun|0.4816623628139496|0.48166235892503423|-3.888915356409228e-7|true|
|191|623|66.0625|-102.0625|earth|0.15188024938106537|0.15188024826579044|-1.1152749279652596e-7|true|
|191|623|66.0625|-102.0625|both|0.08114275336265564|0.08114275282949981|-5.33155825044318e-8|true|

## Scope and run evidence

Actions run https://github.com/kiisophii/lunar-landing-site-navigator/actions/runs/43690245077 . Initial base main aa1e1fb5f0d1a6216fe5453642374a70d14357c9. All three PNG layers use the same 1000 seeded output pixels; ten separate seeded raw-grid cells are computed from DEM. No failing cell was omitted. Publication plus requested sample verification closes the raw-unavailable gap; it is not a full 4,147,200-cell science verification.
