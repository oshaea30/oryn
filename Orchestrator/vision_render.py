"""Local generated SVG -> PNG conversion. No external image inputs accepted."""
import base64
import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import xml.etree.ElementTree as ET

from investigation_episodes import MAX_VISION_TARGETS

RENDERER_VERSION='oryn-svg-chromium-png-v1'


def validate_png(data):
    if not isinstance(data,bytes) or not 33<=len(data)<=3*1024*1024 or data[:8]!=b'\x89PNG\r\n\x1a\n':
        raise ValueError('Invalid object raster.')
    if data[12:16]!=b'IHDR' or struct.unpack('>II',data[16:24])!=(1000,540):
        raise ValueError('Object raster dimensions changed.')


def rasterize(store, package):
    views=package['views']
    if not 1<=len(views)<=MAX_VISION_TARGETS:raise ValueError('Raster target budget exceeded.')
    full=store.get(package['id'])
    svgs=[]
    for view in views:
        ordinal=next((i for i,v in enumerate(full['views']) if v['geometry_id']==view['geometry_id'] and v['view_id']==view['view_id']),None)
        if ordinal is None:raise ValueError('View not bound to prepared object.')
        svg=store.view(package['id'],ordinal)
        root=ET.fromstring(svg)
        allowed={'svg','rect','text','polygon'}
        attrs={'xmlns','viewBox','role','aria-label','width','height','fill','x','y','font-size','points','stroke','stroke-width'}
        if any(node.tag.split('}')[-1] not in allowed or not set(node.attrib)<=attrs for node in root.iter()):
            raise ValueError('Only generated static geometry SVGs may be rasterized.')
        svgs.append(svg)
    node=os.environ.get('ORYN_NODE_BINARY') or shutil.which('node')
    if not node:raise ValueError('Local Node/Playwright renderer unavailable.')
    # Do not pass Meshy/OpenAI keys or unrelated environment to Chromium.
    env={k:os.environ[k] for k in ('PATH','HOME','TMPDIR','NODE_PATH','ORYN_CHROMIUM') if k in os.environ}
    result=subprocess.run([node,str(Path(__file__).with_name('rasterize_evidence.cjs'))],
        input=json.dumps({'views':svgs}).encode(),capture_output=True,timeout=45,env=env)
    if result.returncode or len(result.stdout)>13*1024*1024:raise ValueError('Local object rasterization failed.')
    values=json.loads(result.stdout)
    if set(values)!={'images'} or not isinstance(values['images'],list) or len(values['images'])!=len(views):
        raise ValueError('Invalid local raster output.')
    images=[]
    for view,value in zip(views,values['images']):
        png=base64.b64decode(value,validate=True);validate_png(png)
        images.append({'geometry_id':view['geometry_id'],'view_id':view['view_id'],
                       'png_sha256':hashlib.sha256(png).hexdigest(),'png':png,
                       'renderer':RENDERER_VERSION,'width':1000,'height':540})
    return images
