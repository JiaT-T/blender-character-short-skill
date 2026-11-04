"""External, frame-exact elbow-pole plans. No character names or assets."""
import json,math
from pathlib import Path

def load_json(path):
    path=Path(path)
    if path.stat().st_size>4*1024*1024:raise ValueError('JSON input exceeds 4 MiB')
    def pairs(items):
        result={}
        for key,value in items:
            if key in result:raise ValueError('Duplicate JSON key: '+key)
            result[key]=value
        return result
    def constant(value):raise ValueError('Nonfinite JSON constant: '+value)
    return json.loads(path.read_text('utf-8'),object_pairs_hook=pairs,parse_constant=constant)

def finite(value,label,positive=False):
    if type(value) not in (int,float) or not math.isfinite(value) or positive and value<=0:
        raise ValueError(label+' must be a finite '+('positive ' if positive else '')+'number')
    return float(value)

def validate_plan(value,first,last,height,ground):
    if not isinstance(value,dict):raise ValueError('Elbow pole plan must be an object')
    schema=value.get('schema')
    if type(schema) is not int or schema not in (1,2):raise ValueError('Unsupported elbow pole schema')
    fields={'schema','side','start','blend_end','end','pole'}
    if schema==2:fields.add('release_start')
    if set(value)!=fields:raise ValueError('Elbow pole plan requires exactly '+', '.join(sorted(fields)))
    if value['side'] not in ('left','right'):raise ValueError('Side must be left or right')
    for key in ('start','blend_end','end'):
        if type(value[key]) is not int:raise ValueError(key+' must be an integer frame')
    if not first<=value['start']<=value['blend_end']<=value['end']<=last:raise ValueError('Elbow pole frames must fit the actual scene and be ordered')
    if schema==2 and (type(value['release_start']) is not int or not value['blend_end']<=value['release_start']<value['end']):raise ValueError('Schema2 needs blend_end<=release_start<end for a smooth return')
    pole=value['pole']
    if not isinstance(pole,list) or len(pole)!=3:raise ValueError('Pole requires three normalized world coordinates')
    pole=[finite(v,'Pole coordinate') for v in pole]
    if max(map(abs,pole))>1000:raise ValueError('Pole coordinates exceed 1000 character heights')
    height=finite(height,'Character height',True);ground=finite(ground,'Ground')
    world=[pole[0]*height,pole[1]*height,ground+pole[2]*height]
    if not all(math.isfinite(v) and abs(v)<=1e12 for v in world):raise ValueError('Pole world position exceeds supported finite range')
    return {**value,'pole':pole,'pole_world':world}
