"""Optional FP64 CUDA horizon adapter; metrics still use actual core.js."""
from pathlib import Path
import time
import numpy as np
import cupy as cp
import horizon as hz


class PolarGPU:
    def __init__(self,chain):
        assert 0<len(chain)<=8
        self.chain=chain;self.arrays=[];params=[]
        for s,gate in chain:
            if isinstance(s,hz.PolarStereoSampler):
                a=np.asarray(s.h,dtype=np.float32)
                for start in range(0,a.shape[0],256):
                    if not np.array_equal(a[start:start+256].astype(np.float64),s.h[start:start+256],equal_nan=True):
                        raise ValueError('GPU input cast would change terrain heights')
                p=[0,*a.shape,s.x0,s.dx,s.y0,s.dy,1,gate,s.res_m]
            else:
                a=s.data
                p=[1,*a.shape,s.lpo,s.spo,s.clon,s.ppd,s.km_scale,gate,s.res_m]
            self.arrays.append(cp.asarray(a));params.append(p)
        self.ptr=cp.asarray([a.data.ptr for a in self.arrays],dtype=cp.uint64)
        self.params=cp.asarray(params,dtype=cp.float64)
        self.dist=hz.distances_km(.005,300,8000)
        th=self.dist/(hz.R_M/1000)
        self.d,self.ct,self.st=[cp.asarray(a) for a in [self.dist,np.cos(th),np.sin(th)]]
        self.kernel=cp.RawModule(code=Path(__file__).with_suffix('.cu').read_text(),
            options=('--std=c++11','--fmad=false')).get_function('march_block')
        cp.cuda.Stream.null.synchronize()

    def points(self,points):
        start=time.perf_counter();n=len(points);nd=len(self.chain)
        if not 1<=n<=16:raise ValueError('Display-GPU batch must contain 1..16 nodes')
        lat=cp.asarray([p['lat'] for p in points],dtype=cp.float64)
        lon=cp.asarray([p['lon'] for p in points],dtype=cp.float64)
        best=cp.empty((n,720),dtype=cp.float64);active=cp.empty((n,720),dtype=cp.int32)
        miss=cp.empty((n,720),dtype=cp.int32);used=cp.empty((n,720,nd),dtype=cp.float64)
        counts=cp.empty((n,720),dtype=cp.int32)
        h0=cp.empty(n,dtype=cp.float64)
        for first in range(0,len(self.dist),128):
            self.kernel(((n*720+127)//128,),(128,),
                (np.int32(n),np.int32(nd),lat,lon,self.ptr,self.params,self.d,self.ct,self.st,
                 np.int32(len(self.dist)),np.int32(first),best,active,miss,counts,used,h0))
        masks=cp.asnumpy(best)*180/np.pi;missing=cp.asnumpy(miss).sum(axis=1)
        sources=cp.asnumpy(used).max(axis=1);ground=cp.asnumpy(h0)
        samples=cp.asnumpy(counts).sum(axis=1)
        result=[]
        for i in range(n):
            assert np.isfinite(masks[i]).all() and np.isfinite(ground[i]) and missing[i]==0
            result.append(dict(mask=masks[i],h0_m=float(ground[i]),n_missing=int(missing[i]),n_samples=int(samples[i]),
                dem_sources=[dict(name=s.name,res_m=round(s.res_m,1),to_km=round(float(sources[i,j]),2))
                             for j,(s,_) in enumerate(self.chain) if sources[i,j]>0],
                params=dict(min_km=.005,max_km=300.,n_steps=8000,early_stop=True,hmax_m=10800.,engine_version=hz.ENGINE_VERSION)))
        return result,time.perf_counter()-start

    def close(self):
        self.arrays.clear();self.ptr=self.params=self.d=self.ct=self.st=None
        cp.get_default_memory_pool().free_all_blocks()
