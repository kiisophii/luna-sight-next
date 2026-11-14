# Independent review and verification record

Read-only review of the working diff from base `64e3bee` by a separate Codex session (GPT-6 Astra, High), under the requesting-code-review skill. The reviewer did not run browsers during timed benchmarks or change the checkout.

## Findings and resolution

- No critical or important production rendering defect found. Reviewer checked row orientation, DataTexture flipY, filters/mipmaps, sRGB, anisotropy, texture-size cap, termination, disposed-result guard and retained pixels for context restore.
- Important benchmark finding: page-only CDP transfer counts omit the worker image. The old diagnostic showed approximately the JPEG size missing from zoom traffic. Resolved with actual server payload records (including worker fetch), explicit one-response/expected-byte assertions, worker-target CDP observation and server-side no-early-request checks. Initial scene transfer remains measured before any worker/image request. No bandwidth reduction is attributed to the worker change.
- Throttle scope: Chrome rejects dedicated-worker CPU throttling. Report explicitly calls the laptop profile **4× main-thread CPU**, with desktop worker/GPU hardware. An isolated worker fetch measured 32 ms native versus 5,349.8 ms under page network emulation for the same 6,574,251-byte asset, proving the network limit is inherited. See check_network.py and network_check.json.
- Standalone verification created no output directory in the first draft. verify.py now creates its output parent so the documented command works without running the benchmark first.

## Additional verification

Browser tests check exact sampled rendered-pixel parity against the legacy image path, full 8K, 2K retention on HTTP/decode error, termination during an unfinished worker job, the no-worker legacy path, a simulated 4K hardware cap, and context restoration. Evidence: verification.json; command: `python docs/texture_stall/verify.py`.

The >100 ms upload acceptance check was run before implementation and failed at 230.8 ms desktop / 683.8 ms limited. A separate texture-cap check failed at 8192 before respecting maxTextureSize and passed at 4096 after the correction. Raw timed acceptance checks are kept separate from these headless correctness tests.

Final evidence: 24 unprofiled runs, two successful six-run worker acceptance checks, six browser correctness cases, JavaScript syntax checks, and full unchanged data contract 0 errors / 0 warnings against Git LF producer/core bytes. The direct Windows CRLF checkout produced 33 provenance errors first; isolated LF verification preserves the byte-exact checker and avoids changing either scientific files or the checkout. Later main 7e7964e changed no measured runtime/terrain paths. One additional profiled 4K run isolates a separate synchronous mesh-build bottleneck; it is excluded from headline timings.

## Review boundaries

Other browser engines, actual low-power laptop GPUs, peak memory pressure and full-image pixel equality were not verified. Worker failure retains the 2K image; worker absence uses the legacy path. These are stated compatibility limits, not a claim that every browser now has identical timing. No production data, scientific algorithm or index.html change is part of this fix.
