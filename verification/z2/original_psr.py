import math,numpy as np,tifffile
from source_http import RemoteTIFF
from rasterio.crs import CRS
from rasterio.transform import from_origin
class Reader:
 def __init__(self,url):
  self.s=RemoteTIFF(url);self.f=tifffile.TiffFile(self.s);self.p=self.f.pages[0];self.width=self.p.imagewidth;self.height=self.p.imagelength;self.nodata=float(self.p.tags['GDAL_NODATA'].value.rstrip('\x00'));self.transform=from_origin(-304000,304000,20,20);self.crs=CRS.from_wkt(self.p.geotiff_tags['GeogCitationGeoKey']) if False else CRS.from_string('+proj=stere +lat_0=-90 +lat_ts=-90 +lon_0=0 +R=1737400')
  g=self.p.geotiff_tags;assert self.p.dtype==np.dtype('float32') and g['GTRasterTypeGeoKey']==1 and g['ProjStraightVertPoleLongGeoKey']==0 and self.p.tags['ModelTiepointTag'].value==(0.,0.,0.,-304000.,304000.,0.);assert g['GeogSemiMajorAxisGeoKey']==1737400 and g['ProjNatOriginLatGeoKey']==-90 and self.p.tags['ModelPixelScaleTag'].value[:2]==(20.,20.)
  import json;json.dump({'source':url,'geokeys':str(g),'nodata':'NaN','dtype':str(self.p.dtype),'pixel_size':20,'registration':'pixel-area'},open('z2-source-metadata.json','w'),indent=2)
 def __enter__(self):return self
 def __exit__(self,*args):self.f.close()
 def index(self,x,y):return math.floor((304000-y)/20),math.floor((x+304000)/20)
 def read(self,band,window):
  p=self.p;r0=int(window.row_off);c0=int(window.col_off);r1=r0+int(window.height);c1=c0+int(window.width);a=np.full((r1-r0,c1-c0),np.nan,dtype=np.float32);th=p.tilelength;tw=p.tilewidth;nc=math.ceil(p.imagewidth/tw)
  for rr in range(r0//th,(r1-1)//th+1):
   for cc in range(c0//tw,(c1-1)//tw+1):
    k=rr*nc+cc;self.s.seek(p.dataoffsets[k]);v=p.decode(self.s.read(p.databytecounts[k]),k)[0];v=v.reshape(v.shape[1:3]);ya,yb=max(r0,rr*th),min(r1,(rr+1)*th);xa,xb=max(c0,cc*tw),min(c1,(cc+1)*tw);a[ya-r0:yb-r0,xa-c0:xb-c0]=v[ya-rr*th:yb-rr*th,xa-cc*tw:xb-cc*tw]
  return a
