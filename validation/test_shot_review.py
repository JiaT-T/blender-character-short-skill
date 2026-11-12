import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"blender-character-short/scripts"))
from shot_plan import validate
from planned_video_review import review_frames,review_video


def plan():
    shot={"id":"a","beat":"discover","camera":"wide","framing":"full body","start":1,"end":6,"action_start":"idle","action_end":"idle","spatial_start":{"actor":"left"},"spatial_end":{"actor":"left"},"props_start":{},"props_end":{}}
    second=copy.deepcopy(shot);second.update(id="b",start=7,end=12)
    return {"schema":1,"fps":24,"fps_base":1,"start":1,"end":12,"shots":[shot,second]}


def frame(value):return np.full((8,8),value,dtype=np.float32)


class ShotTests(unittest.TestCase):
    def test_contract(self):
        r=validate(plan());self.assertEqual(r["expected_cut_frames"],[7]);self.assertFalse(r["warnings"])
    def test_gap_overlap_duplicate(self):
        for change in ({"start":8},{"start":6},{"id":"a"}):
            p=plan();p["shots"][1].update(change)
            with self.assertRaises(ValueError):validate(p)
    def test_final_coverage(self):
        p=plan();p["end"]=13
        with self.assertRaises(ValueError):validate(p)
    def test_continuity_and_explicit_exception(self):
        p=plan();p["shots"][1]["props_start"]={"ribbon":"left_hand"}
        self.assertEqual(validate(p)["warnings"][0]["field"],"props")
        p["shots"][1]["continuity_exceptions"]=[{"field":"props","reason":"elapsed time"}]
        self.assertFalse(validate(p)["warnings"])
    def test_bad_root_schema_and_references(self):
        for p in ([], {"schema":True}):
            with self.assertRaises(ValueError):validate(p)
        p=plan();p["assets"]={"hero":"supplied character"};p["shots"][0]["asset_ids"]=["hero"]
        self.assertTrue(validate(p)["valid_contract"])
        for refs in (["other"],["hero","hero"]):
            p["shots"][0]["asset_ids"]=refs
            with self.assertRaises(ValueError):validate(p)
    def test_bad_rate(self):
        for value in (0,float("nan"),True,1e-320):
            p=plan();p["fps_base"]=value
            with self.assertRaises(ValueError):validate(p)
    def test_transition_not_expected_cut(self):
        p=plan();p["shots"][1]["transition"]="dissolve"
        self.assertFalse(validate(p)["expected_cut_frames"])
    def test_cut(self):
        r=review_frames([frame(0)]*6+[frame(1)]*6,plan())
        self.assertFalse(r["findings"]);self.assertFalse(r["visual_acceptance"])
    def test_cut_offset(self):
        r=review_frames([frame(0)]*7+[frame(1)]*5,plan())
        self.assertEqual(r["findings"][0]["offset_frames"],1)
    def test_flash_jump(self):
        frames=[frame(0)]*12;frames[2]=frame(1)
        r=review_frames(frames,plan())
        self.assertIn("flash",[x["kind"] for x in r["findings"]])
        self.assertIn("jump",[x["kind"] for x in r["findings"]])
    def test_freeze_and_intent_exemption(self):
        p=plan();r=review_frames([frame(0)]*12,p)
        self.assertIn("freeze",[x["kind"] for x in r["findings"]])
        p["review_exemptions"]=[{"kind":"freeze","start":1,"end":12,"reason":"deliberate still"}]
        r=review_frames([frame(0)]*12,p)
        self.assertNotIn("freeze",[x["kind"] for x in r["findings"]])
        self.assertEqual(len(r["suppressed_findings"]),1)
    def test_frame_count(self):
        r=review_frames([frame(0)],plan())
        self.assertIn("frame_count",[x["kind"] for x in r["findings"]])
    def test_bad_thresholds_and_frames(self):
        for cfg in ({"jump":float("nan")},{"unknown":1},{"freeze_frames":0}):
            with self.assertRaises(ValueError):review_frames([],plan(),cfg)
        with self.assertRaises(ValueError):review_frames([frame(float("nan"))],plan())
    def test_non_one_start_and_fractional_fps(self):
        p=plan();p["start"]=25;p["end"]=36;p["fps_base"]=1.001
        for shot in p["shots"]:shot["start"]+=24;shot["end"]+=24
        r=review_frames([frame(0)]*7+[frame(1)]*5,p)
        self.assertEqual(r["findings"][0]["start"],31)
        self.assertEqual(r["findings"][0]["observed"],32)
        self.assertAlmostEqual(r["findings"][0]["seconds"],6*1.001/24)
    def test_cut_boundary_not_flash(self):
        p=plan();frames=[frame(0)]*12;frames[6]=frame(1)
        r=review_frames(frames,p)
        self.assertNotIn("flash",[x["kind"] for x in r["findings"]])
    def test_tiny_encoded_video(self):
        import imageio_ffmpeg
        with tempfile.TemporaryDirectory() as directory:
            video=Path(directory)/"synthetic.mp4"
            writer=imageio_ffmpeg.write_frames(str(video),(32,32),fps=24,codec="libx264",output_params=["-threads","1"],ffmpeg_log_level="error")
            writer.send(None)
            for value in ([0]*6+[255]*6):writer.send(np.full((32,32,3),value,dtype=np.uint8))
            writer.close()
            r=review_video(video,plan())
            self.assertEqual(r["decoded_frames"],12)
            self.assertTrue(r["reported_fps_matches"])
            self.assertFalse(r["findings"])
            self.assertEqual(len(r["video_sha256"]),64)

if __name__=="__main__":unittest.main()
