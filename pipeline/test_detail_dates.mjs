import test from 'node:test';
import assert from 'node:assert/strict';
import {makeStay,makeSlip,decodeSlip,validCached,isoDay,STAYS,SHIFTS} from './build_detail_dates.mjs';

test('binary prefixes and fully lit/dark windows use exact requested length',()=>{
  const one=new Uint8Array(48).fill(1),zero=new Uint8Array(48);
  const lit=makeStay(one,one,24,24,2);
  assert.deepEqual(lit[0],['ok',24,24,24,1,1,1,0,false,false]);
  const dark=makeStay(zero,one,24,24,2);
  assert.deepEqual(dark[1],['ok',0,24,0,0,1,0,24,true,true]);
  assert.throws(()=>makeStay(Uint8Array.from([2]),Uint8Array.from([1]),1));
});
test('last 23:00 cell is included, later windows are not shortened',()=>{
  const sun=Uint8Array.from([1,0,0,1,0,0]),earth=new Uint8Array(6).fill(1);
  const rows=makeStay(sun,earth,3,1,6);
  assert.deepEqual(rows[3],['ok',1,3,1,1/3,1,1/3,2,false,true]);
  assert.deepEqual(rows[4],['out_of_range',...Array(9).fill(null)]);
});
test('censored dark edges distinguish a real transition at the stay boundary',()=>{
  const s=Uint8Array.from([1,0,0,1,0,1]),e=new Uint8Array(6).fill(1);
  const a=makeStay(s,e,2,1,6);
  assert.equal(a[1][8],false);assert.equal(a[1][9],false);
  assert.equal(a[2][8],true);assert.equal(a[2][9],false);
  assert.equal(a[3][9],false);
});
test('29.5 days is 708 cells, leap day is a real landing day',()=>{
  assert.deepEqual(STAYS,[168,336,708]);
  assert.equal(isoDay(789),'2028-02-29');
  assert.equal(isoDay(1825),'2030-12-31');
  const s=new Uint8Array(710).fill(1);s[707]=0;
  const rows=makeStay(s,s,708,24,30);
  assert.equal(rows[0][1],707);assert.equal(rows[0][4],707/708);
  assert.equal(rows[1][0],'out_of_range');
});
test('signed shifts retain exact count differences and flag both invalid cases',()=>{
  const s=Uint8Array.from([1,1,0,0,1,0]),e=new Uint8Array(6).fill(1);
  const r=makeStay(s,e,2,1,6);
  const p=makeSlip(r,1),m=makeSlip(r,-1);
  assert.deepEqual(p[0],['ok',1,-1,0,-1,1]);
  assert.equal(decodeSlip(p[0],2).sun_frac,-.5);
  assert.equal(m[0][0],'target_out_of_range');
  assert.equal(p[4][0],'target_out_of_range');
  assert.equal(m[5][0],'base_out_of_range');
  assert.equal(p[5][0],'both_out_of_range');
  assert.equal(decodeSlip(p[5],2).sun_frac,null);
});
test('all 1826 daily starts retain explicit invalid tails',()=>{
  const s=new Uint8Array(43824).fill(1);
  const counts=STAYS.map(h=>makeStay(s,s,h).filter(r=>r[0]==='ok').length);
  assert.deepEqual(counts,[1820,1813,1797]);
  assert.deepEqual(SHIFTS,[-7,-3,-1,1,3,7]);
});
test('stale and modified cache records are rejected',()=>{
  assert.equal(validCached(null,'a'),false);
  assert.equal(validCached({schema:'detail-dates-z3-v1',inputs:{signature:'old'}},'new'),false);
  assert.equal(validCached({schema:'detail-dates-z3-v1',inputs:{signature:'a'},content_sha256:'0'.repeat(64),stays:[]},'a'),false);
});
