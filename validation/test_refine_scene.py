"""Scene refinement validation; native cases also run under Blender factory startup."""
import copy
import sys
sys.dont_write_bytecode = True
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'blender-character-short' / 'scripts'))
from refine_scene import validate_config, validate, apply
try:
    import bpy
except ImportError:
    bpy = None

class ConfigTests(unittest.TestCase):
    def test_minimal(self):
        validate_config({'schema':1,'objects':['Stage'],'collection':'Stage only'})
    def test_unknown(self):
        with self.assertRaises(ValueError): validate_config({'schema':1,'objects':['Stage'],'collection':'Stage','exec':'bad'})
    def test_nonfinite(self):
        with self.assertRaises(ValueError): validate_config({'schema':1,'objects':['Stage'],'collection':'Stage','lights':[{'name':'Fill','energy':float('nan')}]})
    def test_duplicate(self):
        with self.assertRaises(ValueError): validate_config({'schema':1,'objects':['Stage','Stage'],'collection':'Stage'})

@unittest.skipIf(bpy is None, 'Blender native test')
class NativeTests(unittest.TestCase):
    def setUp(self):
        bpy.ops.wm.read_factory_settings(use_empty=True)
        self.s=bpy.context.scene
        self.col=bpy.data.collections.new('Stage only'); self.s.collection.children.link(self.col)
        self.mesh=bpy.data.meshes.new('Stage mesh'); self.obj=bpy.data.objects.new('Stage',self.mesh); self.col.objects.link(self.obj)
        self.mat=bpy.data.materials.new('Wall'); self.mat.use_nodes=True; self.mesh.materials.append(self.mat)
        self.tree=self.mat.node_tree; self.bs=self.tree.nodes.get('Principled BSDF')
        self.rgb=self.tree.nodes.new('ShaderNodeRGB'); self.rgb.name='Source'; self.tree.links.new(self.rgb.outputs[0],self.bs.inputs['Base Color'])
        self.cfg={'schema':1,'objects':['Stage'],'collection':'Stage only'}
    def test_quiet(self):
        self.cfg['materials']=[{'name':'Wall','quiet':[{'name':'Quiet','source_node':'Source','source_socket':'Color','target_node':'Principled BSDF','target_socket':'Base Color','factor':.3,'color':[.1,.2,.3,1]}]}]
        count=len(self.tree.nodes)
        self.assertEqual(validate(self.s,self.cfg),{'materials':['Wall'],'lights':[]}); self.assertEqual(len(self.tree.nodes),count)
        out=apply(self.s,self.cfg); self.assertEqual(len(out['changes']),1)
        self.assertEqual(self.bs.inputs['Base Color'].links[0].from_node.name,'Quiet')
        with self.assertRaises(ValueError): apply(self.s,self.cfg)
    def test_contact(self):
        self.cfg['materials']=[{'name':'Wall','contact':[{'name':'Ground','source_node':'Source','source_socket':'Color','target_node':'Principled BSDF','target_socket':'Base Color','distance':.025,'strength':.8,'minimum':.12,'samples':16}]}]
        apply(self.s,self.cfg); self.assertEqual(self.bs.inputs['Base Color'].links[0].from_node.name,'Ground Mix')
    def test_shared_material_rejected(self):
        other=bpy.data.objects.new('Actor',bpy.data.meshes.new('Actor mesh')); self.s.collection.objects.link(other); other.data.materials.append(self.mat)
        self.cfg['materials']=[{'name':'Wall','inputs':[{'node':'Principled BSDF','socket':'Roughness','value':.8}]}]
        with self.assertRaises(ValueError): validate(self.s,self.cfg)
    def test_receiver_contamination(self):
        other=bpy.data.objects.new('Actor',bpy.data.meshes.new('Actor mesh')); self.col.objects.link(other)
        with self.assertRaises(ValueError): validate(self.s,self.cfg)
    def test_new_and_existing_light(self):
        self.cfg['add_lights']=[{'name':'Fill','location':[0,0,2],'target':[0,1,0],'energy':100,'size':2,'color':[.7,.8,.9]}]
        apply(self.s,self.cfg); light=bpy.data.objects['Fill']; self.assertEqual(light.light_linking.receiver_collection,self.col)
        self.cfg.pop('add_lights'); self.cfg['lights']=[{'name':'Fill','energy':120,'size':1}]
        self.assertEqual(validate(self.s,self.cfg)['lights'],['Fill']); apply(self.s,self.cfg); self.assertEqual(light.data.energy,120)
    def test_bad_edge_no_mutation(self):
        self.cfg['materials']=[{'name':'Wall','inputs':[{'node':'Principled BSDF','socket':'Roughness','value':.9}], 'quiet':[{'name':'Quiet','source_node':'Missing','source_socket':'Color','target_node':'Principled BSDF','target_socket':'Base Color','factor':.3,'color':[.1,.2,.3,1]}]}]
        old=self.bs.inputs['Roughness'].default_value
        with self.assertRaises(ValueError): apply(self.s,self.cfg)
        self.assertEqual(self.bs.inputs['Roughness'].default_value,old)

if __name__=='__main__':
    unittest.main(argv=[sys.argv[0]])
