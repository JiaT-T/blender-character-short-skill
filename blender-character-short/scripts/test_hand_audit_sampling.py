import unittest
from hand_audit_sampling import audit_times

class AuditSampling(unittest.TestCase):
    def test_two_bounded_windows_cover_every_integer_and_half_frame(self):
        _,full=audit_times([1,240],2);a,first=audit_times([1,240],2,[1,121]);b,second=audit_times([1,240],2,[121,240])
        self.assertEqual(a,[1,121]);self.assertEqual(b,[121,240]);self.assertEqual(set(full),set(first)|set(second));self.assertEqual(set(first)&set(second),{121.})
        self.assertEqual(len(first),241);self.assertEqual(len(second),239);self.assertLessEqual(max(len(first),len(second))*1191,300000)
    def test_default_preserves_original_interval(self):
        window,times=audit_times([31,33],2);self.assertEqual(window,[31,33]);self.assertEqual(times,[31,31.5,32,32.5,33])
    def test_integer_only_is_not_mislabeled_half_sampling(self):
        _,times=audit_times([1,4],1);self.assertEqual(times,[1,2,3,4])
    def test_invalid_window_refused(self):
        for window in [[0,121],[121,241],[10,10],[130,10],[True,120],[1,120.5],{},[1]]:
            with self.subTest(window=window),self.assertRaises(ValueError):audit_times([1,240],2,window)
    def test_invalid_motion_or_substeps_refused(self):
        for frames,substeps in [([1,1],2),([1,481],2),([True,120],2),([1,240],True),([1,240],3)]:
            with self.subTest(frames=frames,substeps=substeps),self.assertRaises(ValueError):audit_times(frames,substeps)

if __name__=='__main__':unittest.main()
