import test from 'node:test';
import assert from 'node:assert/strict';
import { cumulative, relayMasks, horizonPoints } from '../web/js/tray_series.js';

test('joint visibility counts both bits, not either one', () => {
  assert.equal(cumulative(Uint8Array.from([1,2,3,0]),3).end,.25);
});
test('relay series clips half-open segments to the inclusive selected period', () => {
  const masks=relayMasks([[8,3,1],[11,2,2],[13,4,0]],10,14);
  assert.deepEqual([...masks.total],[1,1,1,0,0]);
  assert.deepEqual([...masks.added],[0,1,1,0,0]);
  assert.equal(cumulative(masks.total,1).end,.6);
  assert.equal(cumulative(masks.added,1).end,.4);
});
test('missing relay coverage is not silently presented as zero visibility', () => {
  assert.equal(relayMasks([[0,2,1]],0,3),null);
});
test('horizon retains negative elevation and closes at north 360 degrees', () => {
  assert.deepEqual(horizonPoints({mask:[-1,2,3,4],az_step_deg:90}),[[0,-1],[90,2],[180,3],[270,4],[360,-1]]);
});
