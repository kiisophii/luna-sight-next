import csv,io,json,hashlib
from shapely import wkt
from original_psr import Reader
from rasterio.windows import Window
csv.field_size_limit(5000000)
from pathlib import Path
import urllib.request
if not Path('psr-prefix.csv').exists():
 with urllib.request.urlopen(urllib.request.Request('https://pgda.gsfc.nasa.gov/data/LOLA_20mpp/LPSR_80S_20MPP_ADJ.CSV',headers={'Range':'bytes=0-1048575'}),timeout=30) as response:
  assert response.status==206
  Path('psr-prefix.csv').write_bytes(response.read())
r=csv.reader(io.StringIO(open('psr-prefix.csv').read()));header=next(r);row=next(r);poly=wkt.loads(row[1]);point=poly.representative_point()
with Reader('https://pgda.gsfc.nasa.gov/data/LOLA_20mpp/LPSR_80S_20MPP_ADJ.TIF') as src:
 i,j=src.index(point.x,point.y);value=float(src.read(1,window=Window(j,i,1,1))[0,0]);assert value==1
json.dump(dict(polygon_gid=row[0],point=[point.x,point.y],raster_code=value,first_record_sha256=hashlib.sha256(row[1].encode()).hexdigest(),class_1_confirmed=True),open('z2-class-proof.json','w'),indent=2)
print(value,point.x,point.y)
