"""Optional Pillow preview of the six computed node maps; no new calculations."""
from pathlib import Path
import json
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from local_maps import ROOT, IDS, METRICS, sha_file, validate_map


def font(size):
    for path in ['C:/Windows/Fonts/arial.ttf','/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf']:
        if Path(path).exists():return ImageFont.truetype(path,size)
    return ImageFont.load_default()


def main():
    records=[json.loads((ROOT/'web/data/local'/f'{sid}.json').read_text(encoding='utf-8')) for sid in IDS]
    for record in records:validate_map(record)
    dark_max=max(p['longest_dark_h'] for r in records for p in r['points'])
    image=Image.new('RGB',(1390,2025),'#f8fafc');draw=ImageDraw.Draw(image)
    draw.text((30,22),'Local terrain changes the Sun and Earth view',font=font(31),fill='#172338')
    draw.text((30,69),'2026–2030 | 2 m observer | 21 x 21 sampled nodes per region | North up, east right',font=font(20),fill='#475569')
    labels=['Sunlit fraction','Earth visible','Both simultaneously','Longest darkness']
    colours=[(234,179,8),(37,99,235),(22,163,74),(124,58,237)]
    for col,(label,colour) in enumerate(zip(labels,colours)):
        x=240+col*280
        draw.text((x,111),label,font=font(19),fill='#172338')
        draw.text((x,138),'0 → 100%' if col<3 else f'0 → {dark_max:,} h',font=font(16),fill=colour)
    hashes={}
    for row,r in enumerate(records):
        y=175+row*290
        title=r['id'].removeprefix('ARTEMIS_').replace('_',' ').title()
        words=title.split();lines=[];line=''
        for word in words:
            if len(line+' '+word)>18:lines.append(line);line=word
            else:line=(line+' '+word).strip()
        lines.append(line)
        for k,label in enumerate(lines):draw.text((24,y+90+k*25),label,font=font(20),fill='#172338')
        draw.text((24,y+170),'Offsets: -10 to +10 km',font=font(16),fill='#475569')
        for col,(metric,colour) in enumerate(zip(METRICS,colours)):
            values=np.array([p[metric] for p in r['points']]).reshape(21,21)
            maximum=dark_max if col==3 else 1
            weight=np.flipud(values/max(1,maximum))[:,:,None]
            rgb=np.rint((1-weight)*np.array([248,250,252])+weight*np.array(colour)).astype('uint8')
            panel=Image.fromarray(rgb).resize((252,252),Image.Resampling.NEAREST)
            x=240+col*280;image.paste(panel,(x,y))
            draw.rectangle((x,y,x+252,y+252),outline='#94a3b8')
            cx,cy=x+126,y+126;draw.line((cx-4,cy,cx+4,cy),fill='#0f172a',width=2);draw.line((cx,cy-4,cx,cy+4),fill='#0f172a',width=2)
            lo,hi=values.min(),values.max()
            text=f'{lo*100:.1f}–{hi*100:.1f}%' if col<3 else f'{lo:,.0f}–{hi:,.0f} h'
            draw.text((x,y+260),'Range: '+text,font=font(16),fill='#475569')
        hashes[r['id']]=sha_file(ROOT/'web/data/local'/f"{r['id']}.json")
    draw.text((30,1930),'Cross = catalogue centre. Colours represent node samples, not pixel-area averages or landing safety.',font=font(18),fill='#475569')
    draw.text((30,1960),'Source: PGDA/LOLA terrain + production ephemeris/core.js. 5 m source coverage can vary; see the report.',font=font(18),fill='#475569')
    draw.text((30,1990),'AI-generated chart from calculated data | Jiyong / Card 18 / 2026-11-14',font=font(17),fill='#475569')
    image.save(ROOT/'docs/location_sensitivity.png')
    (ROOT/'docs/location_sensitivity_plot.json').write_text(json.dumps(dict(local_sha256=hashes,darkness_scale_max_h=dark_max),indent=2)+'\n',encoding='utf-8')


if __name__=='__main__':main()
