"""Explicit new-copy passive BOX settings, with reviewed documentation identity."""
import math

def digest(value):
    if not isinstance(value,str) or len(value)!=64 or any(c not in '0123456789abcdef' for c in value):raise ValueError('Reviewed lowercase SHA256 required')

def number(value,lo,hi):
    if type(value) not in [int,float] or not math.isfinite(value) or not lo<=value<=hi:raise ValueError('Finite bounded passive-ground geometry required')

def validate(cfg):
    if not isinstance(cfg,dict) or set(cfg)!={'schema','source_sha256','instructions_review_sha256','blender_version','center_xy','size_xy','top_z','thickness'} or type(cfg['schema']) is not int or cfg['schema']!=1:raise ValueError('Explicit passive-ground schema1 required')
    digest(cfg['source_sha256']);digest(cfg['instructions_review_sha256'])
    if not isinstance(cfg['blender_version'],list) or len(cfg['blender_version'])!=3 or any(type(n) is not int or not 0<=n<=1000 for n in cfg['blender_version']):raise ValueError('Exact reviewed Blender version required')
    for key,lo,hi in [('center_xy',-1000,1000),('size_xy',.001,1000)]:
        if not isinstance(cfg[key],list) or len(cfg[key])!=2:raise ValueError('Explicit two-axis ground geometry required')
        for value in cfg[key]:number(value,lo,hi)
    number(cfg['top_z'],-1000,1000);number(cfg['thickness'],.001,1)
    return cfg
