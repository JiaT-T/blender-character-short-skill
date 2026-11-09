import unittest
try:import bpy
except ImportError:bpy=None
@unittest.skipIf(bpy is None,'Blender-only saved compositor transfer tests')
class SavedLookTests(unittest.TestCase):
    def setUp(self):
        from saved_look import clone_compositor,graph_identity
        self.clone=clone_compositor;self.identity=graph_identity;self.a=bpy.data.scenes.new('Test look source');self.b=bpy.data.scenes.new('Test look target');self.a.use_nodes=True;self.a.node_tree.nodes.clear();t=self.a.node_tree
        self.math=t.nodes.new('CompositorNodeMath');self.math.operation='MULTIPLY';self.math.inputs[0].default_value=.25;self.math.inputs[1].default_value=.8
        c=t.nodes.new('CompositorNodeComposite');t.links.new(self.math.outputs[0],c.inputs['Image'])
    def tearDown(self):bpy.data.scenes.remove(self.a);bpy.data.scenes.remove(self.b)
    def test_numeric_node_and_viewer_preserved(self):
        n=self.a.node_tree.nodes.new('CompositorNodeViewer');self.a.node_tree.links.new(self.math.outputs[0],n.inputs['Image']);self.clone(self.a,self.b)
        m=self.b.node_tree.nodes[self.math.name];self.assertEqual(m.operation,'MULTIPLY');self.assertAlmostEqual(m.inputs[0].default_value,.25);self.assertAlmostEqual(m.inputs[1].default_value,.8);self.assertEqual(len(self.b.node_tree.nodes),3)
    def test_no_duplicate_post_on_repeat(self):
        self.clone(self.a,self.b);self.clone(self.a,self.b);self.assertEqual(len(self.b.node_tree.nodes),2);self.assertEqual(self.identity(self.a.node_tree,self.a),self.identity(self.b.node_tree,self.b))
    def test_mute_and_color_management_preserved(self):
        self.math.mute=True;self.a.view_settings.view_transform='Standard';self.a.view_settings.exposure=.3;self.clone(self.a,self.b);self.assertTrue(self.b.node_tree.nodes[self.math.name].mute);self.assertEqual(self.b.view_settings.view_transform,'Standard');self.assertAlmostEqual(self.b.view_settings.exposure,.3,places=5)
    def test_unknown_effect_is_not_silently_replaced(self):
        self.a.node_tree.nodes.new('CompositorNodeValToRGB')
        with self.assertRaisesRegex(ValueError,'Unreviewed compositor'):self.clone(self.a,self.b)
    def test_packed_image_dynamic_enums_copy_after_image_assignment(self):
        from test_production_contract import ProductionContractTests
        from pathlib import Path
        import os,tempfile
        fixture=ProductionContractTests('test_roundtrip_resume_preserves_prefix');fixture.root=Path(tempfile.mkdtemp(prefix='packed-look-',dir=os.environ['BLENDER_TEST_OUTPUT']));path=fixture.image();image=bpy.data.images.load(str(path),check_existing=False);image.pack();self.assertIsNotNone(image.packed_file);n=self.a.node_tree.nodes.new('CompositorNodeImage');n.image=image
        try:
            self.clone(self.a,self.b);self.assertIs(self.b.node_tree.nodes[n.name].image,image);self.assertEqual(self.identity(self.a.node_tree,self.a),self.identity(self.b.node_tree,self.b))
        finally:bpy.data.images.remove(image)
if __name__=='__main__':unittest.main()
