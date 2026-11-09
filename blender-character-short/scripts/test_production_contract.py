import json,tempfile,unittest,os,zlib,struct,binascii
from pathlib import Path
from production_contract import *
class ProductionContractTests(unittest.TestCase):
    def setUp(self):
        declared=Path(os.environ.get('BLENDER_TEST_OUTPUT',tempfile.gettempdir())).resolve();declared.mkdir(parents=True,exist_ok=True)
        self.root=Path(tempfile.mkdtemp(prefix='render-contract-',dir=declared));self.sig={'width':8,'height':8,'effective_fps':30,'source':{'sha256':'original'},'producer':{'render':'v1'}}
    # Keep tiny fixtures as test evidence; never chmod or recursively clean denied paths.
    def tearDown(self):pass
    def image(self,frame=1,color='red'):
        p=self.root/f'{frame:04}.png';pixel=bytes([255,0,0] if color=='red' else [0,0,255])
        def chunk(kind,data):return struct.pack('>I',len(data))+kind+data+struct.pack('>I',binascii.crc32(kind+data)&0xffffffff)
        p.write_bytes(b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',8,8,8,2,0,0,0))+chunk(b'IDAT',zlib.compress((b'\x00'+pixel*8)*8))+chunk(b'IEND',b''));return p
    def state(self,frames=(1,),complete=False):
        rows=[]
        for f in frames:
            row=png_receipt(self.image(f),8,8);row['frame']=f;rows.append(row)
        write_json(self.root/'progress.json',{'schema':SCHEMA,'signature':self.sig,'signature_sha256':digest(self.sig),'frames':rows,'complete':complete,'inputs_verified':complete});return rows
    def test_saved_fractional_frame_rate(self):self.assertAlmostEqual(fps_value(30,1.001),29.97002997002997)
    def test_bad_rates_fail(self):
        for a,b in [(0,1),(True,1),(30,0),(30,float('nan')),(30,float('inf'))]:
            with self.subTest(a=a,b=b),self.assertRaises(ValueError):fps_value(a,b)
    def test_roundtrip_resume_preserves_prefix(self):self.state();self.assertEqual(list(validate_frames(self.root,self.sig,1,2)),[1])
    def test_same_size_changed_pixels_are_refused(self):
        self.state();self.image(color='blue')
        with self.assertRaises(ValueError):validate_frames(self.root,self.sig,1,2)
    def test_size_only_legacy_cache_is_refused(self):
        self.image()
        with self.assertRaises(ValueError):validate_frames(self.root,self.sig,1,2)
    def test_input_identity_change_is_refused(self):
        self.state();other=json.loads(json.dumps(self.sig));other['source']['sha256']='changed'
        with self.assertRaises(ValueError):validate_frames(self.root,other,1,2)
    def test_producer_change_is_refused(self):
        self.state();other=json.loads(json.dumps(self.sig));other['producer']['render']='v2'
        with self.assertRaises(ValueError):validate_frames(self.root,other,1,2)
    def test_missing_receipted_frame_is_refused(self):
        self.state();(self.root/'0001.png').unlink()
        with self.assertRaises(FileNotFoundError):validate_frames(self.root,self.sig,1,2)
    def test_orphan_png_is_refused(self):
        self.state();self.image(2)
        with self.assertRaises(ValueError):validate_frames(self.root,self.sig,1,2)
    def test_false_complete_is_refused(self):
        self.state(complete=True)
        with self.assertRaises(ValueError):validate_frames(self.root,self.sig,1,2)
    def test_declared_resource_bytes_checked(self):
        p=self.root/'asset.json';p.write_text('{}');entry={'path':p.name,'sha256':sha(p)};declared_file(entry,self.root);p.write_text('{"new":1}')
        with self.assertRaises(ValueError):declared_file(entry,self.root)
    def test_duplicate_frame_receipts_are_refused(self):
        self.state();p=self.root/'progress.json';d=json.loads(p.read_text());d['frames']*=2;write_json(p,d)
        with self.assertRaises(ValueError):validate_frames(self.root,self.sig,1,2)
    def test_frame_path_traversal_is_refused(self):
        self.state();p=self.root/'progress.json';d=json.loads(p.read_text());d['frames'][0]['file']='../0001.png';write_json(p,d)
        with self.assertRaises(ValueError):validate_frames(self.root,self.sig,1,2)
    def test_png_wrong_resolution_is_refused(self):
        p=self.image()
        with self.assertRaises(ValueError):png_receipt(p,16,8)
    def test_atomic_json_rejects_nonfinite_data(self):
        with self.assertRaises(ValueError):write_json(self.root/'test.json',{'value':float('nan')})
    def test_output_writers_are_exclusive(self):
        with output_lock(self.root):
            with self.assertRaises((RuntimeError,OSError)):
                with output_lock(self.root):pass
if __name__=='__main__':unittest.main()
