# Independent map / custom-polar check

Requested by Jiyong; docs and independent verifier only. Base: PR #53 plus main 6829725. Keep the open performance comparison checkout unchanged.

1. Pin input hashes/settings and deterministic samples. Read the original CPU method, but independently implement DEM interpolation, full ray marching (no early stop), topocentric ephemeris loop and published PNG export interpolation. Do not import producer computation/check scripts.
2. Recompute ten random 3.8 km source cells and the neighboring source cells needed to compare their nearest published overview pixels. The original float32 grid is not locally available; distinguish agreement with the published 0.4 percentage-point quantized PNG from unverified raw-grid equality. Include original CPU engine as an additional comparator only, never as the independent reference.
3. At three south-polar points, run the actual browser Worker; independently march the card-8 PGDA cache chain with 720 azimuths, 8001 distances from 5 m to 300 km, 2 m observer. Compare horizon RMS/max and the app's sunlit-time fraction (disk visibility >= 0.5) over hourly 2026–2030. The global map instead reports mean visible solar-disk fraction; preserve this existing distinction. Also compare the Worker against an independent reader/march on the exact browser tiles to isolate implementation from DEM resolution differences.
4. Save all masks, samples, input hashes, settings and checks in docs evidence. Append dated ledger rows without overwriting PR #53's historical record, append SI usage, open a PR for Sua to merge.

Review focus: pixel centres and overview interpolation; mean solar disk vs sunlit time; metre/km and observer height; chain fallback/coverage; worker 4-decimal quantization vs DEM-product differences. Full-march finite-sample assertions, quantization-aware comparison and separate same-input checks address these cases. No production files or numbers changed.

Completed: independent map and polar computations, four analytic controls, final-source rerun, input hashes, separate AI review, evidence/report and append-only ledger/SI entries. Map published DN matches 30/30; same-tile Worker masks match 2160/2160 after rounding. Different DEM chains yield up to 2.430175 pp Sun difference and are reported as a limitation, not hidden by a pass label.
