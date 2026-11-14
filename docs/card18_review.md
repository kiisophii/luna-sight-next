# Card 18 final review and decisions

Fresh GPT-6 Astra High review of `50aa52e..fca5662`: ready for integration; no Critical, Important or Minor findings. Review was read-only and separate from both implementation and the independent five-point geometry check.

The reviewer matched all six maps against report/plot/validation hashes and current production input fingerprints; independently recomputed all radial statistics and adjacent/extreme pairs; checked all 33 relay source hashes and all seven low-direct sites' four single-tower timelines against visibility checkpoints. All agreed exactly. The chart was visually inspected. Full tests were run by the implementer: 137 passed; contract checker: zero errors and warnings. Pytest reported 18 upstream NumPy/pyproj deprecation warnings.

## Decisions and scope boundaries

1. Expanded stored source windows by 16 km while retaining original observer-relative range gates. This avoids artificial cache-edge changes; original source coverage still varies. If the spatial margin were insufficient, missing fine terrain could distort local contrasts, so coverage and independent ray checks are retained.
2. Used actual core.js in persistent Node processes instead of duplicating production metric formulas. This preserves the requested definitions; core changes invalidate old points and can require a full recomputation.
3. Absolute DEM accuracy and Shackleton's precise datum alignment remain external validation work. Current evidence supports implementation consistency on the cited terrain; interpreting it as absolute accuracy could give false confidence in candidate-site rankings.
4. RF performance, power storage, structural feasibility and landing safety remain outside geometric visibility analysis. Ignoring this boundary could mistake a higher visibility fraction for a feasible continuous communications service.
5. Five uniformly sampled checks satisfy the requested numerical comparison, not a statistical error bound for all 2,646 nodes. An untested local defect could remain; complete source provenance and resumable computation support further checks.
6. The local-map contract is proposed and the browser UI integration remains with Sua. This branch delivers data, reports and the static comparison figure; a new interactive local-map panel is not added by this branch.

Deferred minor findings: none. No review-driven code changes were needed.

## Evidence and reproduction

- [Location distributions and measured pairs](location_sensitivity.md)
- [Single-tower effects and remaining outages](relay_impact.md)
- [Independent five-point comparison](card18_validation.json)
- [Reproduction commands](card18_reproduce.md)
- [Recorded compute, resume and verification timings](card18_runtime.json)
