"""Independent CPU fixtures; no Blender or third-party asset in these fixtures."""
from pathlib import Path
import sys,json,struct,copy,math,unittest,subprocess,os,hashlib,uuid
from contextlib import contextmanager
from unittest.mock import patch
import numpy as np
scripts=Path(__file__).resolve().parent;OUTPUT=None
import convert_glb_motion as converter
from source_motion import decode_clip,node_worlds,sample_track

@contextmanager
def test_directory():
 assert OUTPUT is not None
 base=(OUTPUT/'fixtures').resolve();assert base.is_relative_to(OUTPUT.resolve());base.mkdir(exist_ok=True)
 directory=base/uuid.uuid4().hex;directory.mkdir();yield str(directory)
 # Preserve own fixture evidence; do not touch the inaccessible OS temporary area.

def container(document,binary):
 data=json.dumps(document,allow_nan=False,separators=(',',':')).encode();data+=b' '*((-len(data))%4);payload=binary+b'\0'*((-len(binary))%4)
 body=struct.pack('<II',len(data),0x4e4f534a)+data+struct.pack('<II',len(payload),0x004e4942)+payload
 return struct.pack('<4sII',b'glTF',2,12+len(body))+body

def fixture():
 d={'asset':{'version':'2.0'},'nodes':[{'name':'root','children':[1],'mesh':0,'skin':0},{'name':'child','translation':[0,1,0]}],
 'meshes':[{'name':'Excluded mesh'}],'skins':[{'joints':[0,1]}],'images':[{'uri':'https://invalid.example/never-read.png'}],
 'accessors':[],'bufferViews':[],'buffers':[{'byteLength':0}], 'animations':[{'name':'Move and turn','channels':[],'samplers':[]}]};binary=bytearray()
 def accessor(values,kind):
  array=np.asarray(values,dtype='<f4');index=len(d['accessors']);view=len(d['bufferViews']);start=len(binary);binary.extend(array.tobytes());d['bufferViews'].append({'buffer':0,'byteOffset':start,'byteLength':array.nbytes});d['accessors'].append({'componentType':5126,'type':kind,'count':len(array),'bufferView':view});return index
 def track(node,path,times,values):
  a=d['animations'][0];sampler=len(a['samplers']);a['samplers'].append({'input':accessor(times,'SCALAR'),'output':accessor(values,'VEC4' if path=='rotation' else 'VEC3'),'interpolation':'LINEAR'});a['channels'].append({'target':{'node':node,'path':path},'sampler':sampler})
 track(0,'translation',[0,1,2],[[1,0,0],[2,0,0],[3,0,0]])
 track(0,'rotation',[0,2],[[0,0,0,1],[0,0,math.sin(math.pi/4),math.cos(math.pi/4)]])
 track(1,'translation',[.5,1.5],[[0,1,0],[0,3,0]])
 d['buffers'][0]['byteLength']=len(binary);return d,bytes(binary)

def append_array(document,binary,values,kind):
 array=np.asarray(values,dtype='<f4');index=len(document['accessors']);view=len(document['bufferViews']);start=len(binary);binary.extend(array.tobytes());document['bufferViews'].append({'buffer':0,'byteOffset':start,'byteLength':array.nbytes});document['accessors'].append({'componentType':5126,'type':kind,'count':len(array),'bufferView':view});document['buffers'][0]['byteLength']=len(binary);return index

def chain_fixture(depth,reverse=False,scale=None,animated_scale=False):
 d,b=fixture();nodes=[]
 for index in range(depth):
  node={'name':'own-node-'+str(index)};child=index-1 if reverse else index+1
  if 0<=child<depth:node['children']=[child]
  if scale is not None:node['scale']=[scale]*3
  nodes.append(node)
 d['nodes']=nodes;a=d['animations'][0];a['channels']=a['channels'][:1];a['channels'][0]['target']['node']=depth-1 if reverse else 0
 if animated_scale:
  data=bytearray(b);i=append_array(d,data,[0,1],'SCALAR');o=append_array(d,data,[[1,1,1],[1e6,1e6,1e6]],'VEC3');a['samplers']=[{'input':i,'output':o}];a['channels']=[{'sampler':0,'target':{'node':n,'path':'scale'}} for n in range(depth)];b=bytes(data)
 return container(d,b)

def product_fixture(channels):
 d,b=fixture();data=bytearray(b);d['nodes']=[{} for _ in range(channels)];a=d['animations'][0];a['channels']=[];a['samplers']=[]
 for index in range(channels):
  i=append_array(d,data,[2*index,2*index+1],'SCALAR');o=append_array(d,data,[[0,0,0],[1,1,1]],'VEC3');a['samplers'].append({'input':i,'output':o});a['channels'].append({'sampler':index,'target':{'node':index,'path':'translation'}})
 return container(d,bytes(data))

def isolated_scale_peak_fixture(peak=1e6):
 d,b=fixture();d['nodes']=[{'children':[index+1]} if index<59 else {} for index in range(60)];data=bytearray(b);i=append_array(d,data,np.arange(200,dtype=np.float32),'SCALAR');values=np.ones((200,3),np.float32);values[1]=peak;o=append_array(d,data,values,'VEC3');d['animations'][0]['samplers']=[{'input':i,'output':o}];d['animations'][0]['channels']=[{'sampler':0,'target':{'node':index,'path':'scale'}} for index in range(60)];return container(d,bytes(data))

def cli_case(raw,extra_rights=None,rights_raw=None):
 with test_directory() as folder:
  folder=Path(folder);source=folder/'own.glb';source.write_bytes(raw);record={'source':'self-authored numeric fixture','credit':'project test','license':'self-authored test data','modifications':'CPU regression only','source_sha256':hashlib.sha256(raw).hexdigest()};record.update(extra_rights or {});rights=folder/'rights.json';rights.write_bytes(rights_raw if rights_raw is not None else json.dumps(record).encode());output=folder/'converted';env=dict(os.environ);env['PYTHONPATH']=os.pathsep.join(str(p) for p in sys.path if p)
  result=subprocess.run([sys.executable,'-B',str(scripts/'convert_glb_motion.py'),'--source',str(source),'--provenance',str(rights),'--output',str(output)],env=env,capture_output=True,text=True,timeout=45)
  (folder/'stdout.log').write_text(result.stdout,'utf-8');(folder/'stderr.log').write_text(result.stderr,'utf-8');assert source.read_bytes()==raw
  return result,folder,output

class ConversionTests(unittest.TestCase):
 def convert(self,change=None):
  d,b=fixture()
  if change:change(d)
  return converter.convert(container(d,b))
 def reject(self,change):
  with self.assertRaises(ValueError):self.convert(change)
 def test_independent_timelines_known_world(self):
  sk,clip,report=self.convert();self.assertEqual(clip['packing']['times'],[0,.5,1,1.5,2]);self.assertEqual(report['channels'],3)
  world=node_worlds(sk,decode_clip(clip),1)
  np.testing.assert_allclose(world[1,:3,3],[2-math.sqrt(2),math.sqrt(2),0],atol=1e-6)
  np.testing.assert_allclose(world[0,:3,:3],[[math.sqrt(.5),-math.sqrt(.5),0],[math.sqrt(.5),math.sqrt(.5),0],[0,0,1]],atol=1e-6)
 def test_timeline_end_clamps(self):
  sk,clip,_=self.convert();t=next(t for t in decode_clip(clip) if t['node']==1)
  np.testing.assert_allclose(sample_track(t,0),[0,1,0]);np.testing.assert_allclose(sample_track(t,2),[0,3,0])
 def test_original_indices_and_only_transform_fields(self):
  sk,_,_=self.convert();self.assertEqual(len(sk['nodes']),2);self.assertEqual(sk['nodes'][0],{'name':'root','children':[1]});self.assertNotIn('images',sk)
 def test_antipodal_quaternion_shortest_path(self):
  d,b=fixture();data=bytearray(b);a=d['accessors'][3];v=d['bufferViews'][a['bufferView']];values=np.frombuffer(data,dtype='<f4',count=8,offset=v['byteOffset']).reshape(2,4);values[1]*=-1
  sk,clip,_=converter.convert(container(d,bytes(data)));w=node_worlds(sk,decode_clip(clip),1);self.assertAlmostEqual(w[0,0,0],math.sqrt(.5),places=6)
 def test_multiple_animations_need_selection(self):
  d,b=fixture();d['animations'].append(copy.deepcopy(d['animations'][0]));d['animations'][1]['name']='Explicit second'
  with self.assertRaises(ValueError):converter.convert(container(d,b))
  self.assertEqual(converter.convert(container(d,b),1)[2]['animation_name'],'Explicit second')
 def test_step_not_silently_linearized(self):self.reject(lambda d:d['animations'][0]['samplers'][0].update(interpolation='STEP'))
 def test_cubic_not_silently_linearized(self):self.reject(lambda d:d['animations'][0]['samplers'][0].update(interpolation='CUBICSPLINE'))
 def test_weights_not_silently_discarded(self):self.reject(lambda d:d['animations'][0]['channels'][0]['target'].update(path='weights'))
 def test_duplicate_target(self):self.reject(lambda d:d['animations'][0]['channels'].append(copy.deepcopy(d['animations'][0]['channels'][0])))
 def test_animated_matrix_rejected(self):self.reject(lambda d:d['nodes'][0].update(matrix=np.eye(4).T.reshape(-1).tolist()))
 def test_hierarchy_cycle(self):self.reject(lambda d:d['nodes'][1].update(children=[0]))
 def test_duplicate_child(self):self.reject(lambda d:d['nodes'][0].update(children=[1,1]))
 def test_boolean_node_index(self):self.reject(lambda d:d['animations'][0]['channels'][0]['target'].update(node=True))
 def test_negative_animation_index(self):
  d,b=fixture()
  with self.assertRaises(ValueError):converter.convert(container(d,b),-1)
 def test_external_buffer_not_read(self):self.reject(lambda d:d['buffers'][0].update(uri='https://invalid.example/buffer.bin'))
 def test_required_extension(self):self.reject(lambda d:d.update(extensionsRequired=['KHR_draco_mesh_compression']))
 def test_node_extension(self):self.reject(lambda d:d['nodes'][0].update(extensions={'unknown':{}}))
 def test_outside_buffer_view(self):self.reject(lambda d:d['accessors'][0].update(count=99))
 def test_wrong_accessor_width(self):self.reject(lambda d:d['accessors'][0].update(type='VEC3'))
 def test_sparse_accessor(self):self.reject(lambda d:d['accessors'][0].update(sparse={}))
 def test_normalized_accessor(self):self.reject(lambda d:d['accessors'][0].update(normalized=True))
 def test_animation_stride(self):self.reject(lambda d:d['bufferViews'][0].update(byteStride=4))
 def test_accessor_misalignment(self):self.reject(lambda d:d['accessors'][0].update(byteOffset=1))
 def test_chunk_length_mismatch(self):
  d,b=fixture();raw=bytearray(container(d,b));struct.pack_into('<I',raw,8,len(raw)-4)
  with self.assertRaises(ValueError):converter.convert(bytes(raw))
 def test_invalid_times_and_nonfinite_values(self):
  for value in [-1,float('nan'),float('inf')]:
   d,b=fixture();data=bytearray(b);struct.pack_into('<f',data,0,value)
   with self.subTest(value=value),self.assertRaises(ValueError):converter.convert(container(d,bytes(data)))
  d,b=fixture();data=bytearray(b);struct.pack_into('<f',data,4,0)
  with self.assertRaises(ValueError):converter.convert(container(d,bytes(data)))
 def test_nonunit_quaternion(self):
  d,b=fixture();data=bytearray(b);view=d['bufferViews'][d['accessors'][3]['bufferView']];struct.pack_into('<4f',data,view['byteOffset'],0,0,0,.5)
  with self.assertRaises(ValueError):converter.convert(container(d,bytes(data)))
 def test_quantization_overflow(self):
  d,b=fixture();data=bytearray(b);view=d['bufferViews'][d['accessors'][1]['bufferView']];struct.pack_into('<f',data,view['byteOffset'],1e20)
  with self.assertRaises(ValueError):converter.convert(container(d,bytes(data)))
 def test_provenance_identity(self):
  with test_directory() as folder:
   p=Path(folder)/'rights.json';p.write_text(json.dumps({'source':'own fixture','credit':'own','license':'own test','modifications':'test','source_sha256':'a'*64}),'utf-8')
   with self.assertRaises(ValueError):converter.provenance_record(p,'b'*64)
   self.assertEqual(converter.provenance_record(p,'a'*64)['source'],'own fixture')
 def test_cli_new_directory_and_no_input_mutation(self):
  with test_directory() as folder:
   folder=Path(folder);source=folder/'own.glb';d,b=fixture();source.write_bytes(container(d,b));before=hashlib.sha256(source.read_bytes()).hexdigest();rights=folder/'rights.json';rights.write_text(json.dumps({'source':'self-authored numeric fixture','credit':'project test','license':'self-authored test data','modifications':'CPU conversion only','source_sha256':before}),'utf-8');output=folder/'converted';env=dict(os.environ);env['PYTHONPATH']=os.pathsep.join(str(p) for p in sys.path if p);cmd=[sys.executable,'-X','utf8',str(scripts/'convert_glb_motion.py'),'--source',str(source),'--provenance',str(rights),'--output',str(output)]
   a=subprocess.run(cmd,env=env,capture_output=True,text=True);self.assertEqual(a.returncode,0,a.stderr);self.assertEqual(set(p.name for p in output.iterdir()),{'motion-skeleton.json','motion-packed-v1.json','conversion-report.json'});snapshot={p.name:p.read_bytes() for p in output.iterdir()}
   b=subprocess.run(cmd,env=env,capture_output=True,text=True);self.assertNotEqual(b.returncode,0);self.assertEqual(snapshot,{p.name:p.read_bytes() for p in output.iterdir()});self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(),before)
 def test_cli_wrong_review_hash_creates_no_output(self):
  with test_directory() as folder:
   folder=Path(folder);source=folder/'own.glb';d,b=fixture();source.write_bytes(container(d,b));rights=folder/'rights.json';rights.write_text(json.dumps({'source':'own','credit':'test','license':'own','modifications':'test','source_sha256':'0'*64}),'utf-8');output=folder/'must-not-exist';env=dict(os.environ);env['PYTHONPATH']=os.pathsep.join(str(p) for p in sys.path if p);r=subprocess.run([sys.executable,str(scripts/'convert_glb_motion.py'),'--source',str(source),'--provenance',str(rights),'--output',str(output)],env=env,capture_output=True,text=True);self.assertNotEqual(r.returncode,0);self.assertFalse(output.exists())
 def test_rest_world_overflow_api_and_cli(self):
  raw=chain_fixture(12,scale=1e30)
  with self.assertRaisesRegex(ValueError,'World hierarchy'):converter.convert(raw)
  r,_,out=cli_case(raw);self.assertNotEqual(r.returncode,0);self.assertIn('World hierarchy',r.stderr);self.assertFalse(out.exists());self.assertNotIn('numerically-verified',r.stdout)
 def test_animated_world_overflow_api_and_cli(self):
  raw=chain_fixture(60,animated_scale=True)
  with self.assertRaisesRegex(ValueError,'World hierarchy'):converter.convert(raw)
  r,_,out=cli_case(raw);self.assertNotEqual(r.returncode,0);self.assertIn('World hierarchy',r.stderr);self.assertFalse(out.exists())
 def test_reverse_depth_boundary_accepted(self):
  for reverse in [False,True]:
   with self.subTest(reverse=reverse):
    raw=chain_fixture(converter.LIMITS['hierarchy_depth'],reverse=reverse);sk,clip,_=converter.convert(raw);self.assertTrue(np.isfinite(node_worlds(sk,decode_clip(clip),1)).all())
 def test_forward_and_reverse_depth_refused_cli(self):
  for reverse in [False,True]:
   raw=chain_fixture(converter.LIMITS['hierarchy_depth']+1,reverse=reverse);r,_,out=cli_case(raw)
   with self.subTest(reverse=reverse):self.assertNotEqual(r.returncode,0);self.assertIn('hierarchy_depth budget',r.stderr);self.assertNotIn('RecursionError',r.stderr);self.assertFalse(out.exists())
 def test_1200_reverse_nodes_refused_before_recursion(self):
  r,_,out=cli_case(chain_fixture(1200,reverse=True));self.assertNotEqual(r.returncode,0);self.assertIn('hierarchy_depth budget',r.stderr);self.assertNotIn('RecursionError',r.stderr);self.assertFalse(out.exists())
 def test_full_key_world_work_below_budget(self):
  sk,clip,report=converter.convert(product_fixture(227));self.assertEqual(report['resource_usage']['resampled_channel_samples'],103058);self.assertEqual(len(sk['nodes']),227);self.assertEqual(len(clip['tracks']),227);self.assertEqual(report['verification']['world_matrix_original_key_count'],454);self.assertTrue(report['verification']['all_original_key_worlds_checked']);self.assertLessEqual(report['resource_usage']['validation_graph_samples'],converter.LIMITS['validation_graph_samples'])
 def test_resample_product_above_boundary_cli(self):
  r,_,out=cli_case(product_fixture(354));self.assertNotEqual(r.returncode,0);self.assertIn('resampled_channel_samples budget',r.stderr);self.assertFalse(out.exists())
 def test_resampling_fits_but_full_key_world_work_refused(self):
  raw=product_fixture(353)
  with patch.object(converter,'pack_tracks') as packed,self.assertRaisesRegex(ValueError,'validation_graph_samples budget'):converter.convert(raw)
  packed.assert_not_called();r,_,out=cli_case(raw);self.assertNotEqual(r.returncode,0);self.assertIn('validation_graph_samples budget',r.stderr);self.assertFalse(out.exists())
 def test_original_key_peak_world_overflow_refused_api_cli(self):
  raw=isolated_scale_peak_fixture()
  with self.assertRaisesRegex(ValueError,'World hierarchy'):converter.convert(raw)
  r,_,out=cli_case(raw);self.assertNotEqual(r.returncode,0);self.assertIn('World hierarchy',r.stderr);self.assertFalse(out.exists());self.assertNotIn('numerically-verified',r.stdout)
 def test_finite_original_key_peak_is_really_evaluated(self):
  _,_,report=converter.convert(isolated_scale_peak_fixture(10));v=report['verification'];self.assertEqual(v['world_matrix_original_key_count'],200);self.assertTrue(v['all_original_key_worlds_checked']);self.assertGreater(v['world_matrix_reference_scale'],1e59);self.assertFalse(v['continuous_interval_verified'])
 def test_validation_plan_cannot_omit_original_keys(self):
  raw=isolated_scale_peak_fixture(10);document,binary=converter.read_glb(raw);sk=converter.skeleton_only(document);tracks,_,_=converter.original_tracks(document,binary,sk,None);times,_,_=converter.sampling_plan(tracks,len(sk['nodes']));clip=converter.pack_tracks(tracks,times)
  with self.assertRaisesRegex(ValueError,'omits original key times'):converter.validate_conversion(sk,tracks,clip,np.array([0.,199.]))
 def test_source_and_chunk_byte_budgets(self):
  d,b=fixture();raw=container(d,b)
  for key in ['source_bytes','json_bytes','binary_bytes']:
   with self.subTest(key=key),patch.dict(converter.LIMITS,{key:1}),self.assertRaisesRegex(ValueError,key+' budget'):converter.convert(raw)
 def test_file_budget_checked_before_open(self):
  from types import SimpleNamespace
  with patch.object(Path,'stat',return_value=SimpleNamespace(st_size=converter.LIMITS['source_bytes']+1)),patch.object(Path,'open') as opened:
   with self.assertRaisesRegex(ValueError,'source_bytes budget'):converter.read_bounded(Path('own-not-opened-fixture'),'source_bytes')
   opened.assert_not_called()
 def test_node_channel_accessor_and_decoded_budgets(self):
  for key in ['nodes','channels','accessor_samples','decoded_components']:
   with self.subTest(key=key),patch.dict(converter.LIMITS,{key:1}),self.assertRaisesRegex(ValueError,key+' budget'):self.convert()
 def test_validation_graph_budget(self):
  with patch.dict(converter.LIMITS,{'validation_graph_samples':1}),self.assertRaisesRegex(ValueError,'validation_graph_samples budget'):self.convert()
 def test_actual_node_budget_cli(self):
  d,b=fixture();d['nodes'].extend({} for _ in range(converter.LIMITS['nodes']-1));r,_,out=cli_case(container(d,b));self.assertNotEqual(r.returncode,0);self.assertIn('nodes budget',r.stderr);self.assertFalse(out.exists())
 def test_actual_accessor_budget_cli(self):
  d,b=fixture();d['accessors'][0]['count']=converter.LIMITS['accessor_samples']+1;r,_,out=cli_case(container(d,b));self.assertNotEqual(r.returncode,0);self.assertIn('accessor_samples budget',r.stderr);self.assertFalse(out.exists())
 def test_actual_decoded_component_budget_cli(self):
  d,b=fixture();data=bytearray(b);i=append_array(d,data,np.arange(100000,dtype=np.float32),'SCALAR');o=append_array(d,data,np.zeros((100000,3),np.float32),'VEC3');d['nodes']=[{},{},{}];d['animations'][0]['samplers']=[{'input':i,'output':o}];d['animations'][0]['channels']=[{'sampler':0,'target':{'node':n,'path':'translation'}} for n in range(3)];r,_,out=cli_case(container(d,bytes(data)));self.assertNotEqual(r.returncode,0);self.assertIn('decoded_components budget',r.stderr);self.assertFalse(out.exists())
 def test_actual_validation_graph_budget_cli(self):
  d,b=fixture();d['nodes'].extend({} for _ in range(converter.LIMITS['nodes']-2));data=bytearray(b);i=append_array(d,data,np.linspace(0,2,100,dtype=np.float32),'SCALAR');o=append_array(d,data,np.zeros((100,3),np.float32),'VEC3');d['animations'][0]['samplers'][0]={'input':i,'output':o};r,_,out=cli_case(container(d,bytes(data)));self.assertNotEqual(r.returncode,0);self.assertIn('validation_graph_samples budget',r.stderr);self.assertFalse(out.exists())
 def test_duplicate_glb_json_key_refused(self):
  d,b=fixture();data=json.dumps(d,separators=(',',':')).replace('"version":"2.0"','"version":"1.0","version":"2.0"',1).encode();data+=b' '*((-len(data))%4);binary=b+b'\0'*((-len(b))%4);body=struct.pack('<II',len(data),0x4e4f534a)+data+struct.pack('<II',len(binary),0x004e4942)+binary;raw=struct.pack('<4sII',b'glTF',2,12+len(body))+body
  with self.assertRaisesRegex(ValueError,'duplicate JSON key'):converter.convert(raw)
 def test_duplicate_rights_key_refused_cli(self):
  d,b=fixture();raw=container(d,b);digest=hashlib.sha256(raw).hexdigest();rights=('{"source":"own","credit":"test","license":"restricted","license":"permissive","modifications":"test","source_sha256":"'+digest+'"}').encode();r,_,out=cli_case(raw,rights_raw=rights);self.assertNotEqual(r.returncode,0);self.assertIn('duplicate JSON key',r.stderr);self.assertFalse(out.exists())
 def test_unknown_rights_conditions_refused_cli(self):
  d,b=fixture();r,_,out=cli_case(container(d,b),extra_rights={'conditions':{'redistribution':False}});self.assertNotEqual(r.returncode,0);self.assertIn('Unsupported provenance fields',r.stderr);self.assertFalse(out.exists())
 def test_restrictions_and_raw_rights_hash_retained(self):
  d,b=fixture();r,folder,out=cli_case(container(d,b),extra_rights={'restrictions':'No redistribution; preserve this exact item condition.'});self.assertEqual(r.returncode,0,r.stderr);report=json.loads((out/'conversion-report.json').read_text('utf-8'));self.assertEqual(report['provenance']['restrictions'],'No redistribution; preserve this exact item condition.');self.assertEqual(report['provenance_sha256'],hashlib.sha256((folder/'rights.json').read_bytes()).hexdigest())
 def test_optional_rights_types_and_size(self):
  d={'source':'own','credit':'own','license':'own','modifications':'test','source_sha256':'a'*64}
  for key in ['license_url','restrictions']:
   with self.subTest(key=key),self.assertRaises(ValueError):converter.parse_provenance(json.dumps({**d,key:False}).encode(),'a'*64)
  with patch.dict(converter.LIMITS,{'provenance_bytes':1}),self.assertRaisesRegex(ValueError,'provenance_bytes budget'):converter.parse_provenance(json.dumps(d).encode(),'a'*64)
 def test_static_matrix_parent_known_world(self):
  def change(d):
   matrix=np.eye(4);matrix[0,3]=10;d['nodes'].append({'children':[0],'matrix':matrix.T.reshape(-1).tolist()})
  sk,clip,_=self.convert(change);world=node_worlds(sk,decode_clip(clip),1);np.testing.assert_allclose(world[1,:3,3],[12-math.sqrt(2),math.sqrt(2),0],atol=1e-6)
 def test_single_key_and_nonstring_animation_name(self):
  d,b=fixture();data=bytearray(b);a=d['animations'][0];i=append_array(d,data,[.5],'SCALAR');o=append_array(d,data,[[1,2,3]],'VEC3');a['samplers']=[{'input':i,'output':o}];a['channels']=[{'sampler':0,'target':{'node':0,'path':'translation'}}];sk,clip,report=converter.convert(container(d,bytes(data)));self.assertEqual(report['samples'],1);np.testing.assert_allclose(node_worlds(sk,decode_clip(clip),0)[0,:3,3],[1,2,3])
  a['name']=12
  with self.assertRaisesRegex(ValueError,'Animation name'):converter.convert(container(d,bytes(data)))

def main():
 import argparse,datetime
 global OUTPUT
 parser=argparse.ArgumentParser(description='CPU-only generated-GLB numerical and CLI tests; no Blender/network/external assets.')
 parser.add_argument('--output',required=True,type=Path)
 args=parser.parse_args();OUTPUT=args.output.resolve();OUTPUT.mkdir(parents=True,exist_ok=False)
 suite=unittest.defaultTestLoader.loadTestsFromTestCase(ConversionTests)
 with (OUTPUT/'tests.log').open('w',encoding='utf-8') as stream:result=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
 report={'status':'pass' if result.wasSuccessful() else 'failed','at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'tests_run':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),'skipped':len(result.skipped),'source':'Self-authored numeric fixtures generated at runtime; no external motion/model/texture included.','scope':'CPU conversion/analytic transforms/input rejection/new-output and source-identity behavior only. No Blender/skin/contact/retargeting/naturalness/continuous-view acceptance.'}
 (OUTPUT/'result.json').write_text(json.dumps(report,indent=2)+'\n','utf-8');print(json.dumps(report));raise SystemExit(0 if result.wasSuccessful() else 1)

if __name__=='__main__':main()
