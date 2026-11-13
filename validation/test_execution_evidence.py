"""Counterexamples for current-render evidence, not artistic acceptance."""
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import validate_distribution as distribution
from validate_distribution import validate_execution_counts, validate_native_stage_exits


class CurrentExecutionCounts(unittest.TestCase):
    def evidence(self, **changes):
        return dict(retained_frames=24, final_frames=278, initial_rehearsal_frames=288,
                    final_size=[1280, 720], fps=24, full_encoded_decode_exit=0, **changes)

    def changed(self, **changes):
        row=self.evidence();row.update(changes);return row

    def test_current_production_counts(self):
        validate_execution_counts(self.evidence())

    def test_old_rehearsal_is_not_resume_upper_bound(self):
        with self.assertRaisesRegex(AssertionError, 'current final render'):
            validate_execution_counts(self.changed(retained_frames=280))

    def test_complete_sequence_is_not_partial_resume(self):
        with self.assertRaises(AssertionError):
            validate_execution_counts(self.changed(retained_frames=278))

    def test_zero_or_negative_counts_fail(self):
        for key in ('retained_frames','final_frames','initial_rehearsal_frames'):
            for value in (0,-1):
                with self.subTest(key=key,value=value),self.assertRaises(AssertionError):
                    validate_execution_counts(self.changed(**{key:value}))

    def test_boolean_or_text_counts_fail(self):
        for key in ('retained_frames','final_frames','initial_rehearsal_frames'):
            for value in (True,'24'):
                with self.subTest(key=key,value=value),self.assertRaises(AssertionError):
                    validate_execution_counts(self.changed(**{key:value}))

    def test_different_render_size_fails(self):
        with self.assertRaises(AssertionError):
            validate_execution_counts(self.changed(final_size=[640,360]))

    def test_different_rate_fails(self):
        with self.assertRaises(AssertionError):
            validate_execution_counts(self.changed(fps=30))

    def test_failed_or_noninteger_decoder_exit_fails(self):
        for value in (1,False,'0'):
            with self.subTest(value=value),self.assertRaises(AssertionError):
                validate_execution_counts(self.changed(full_encoded_decode_exit=value))


class IndependentNativeExits(unittest.TestCase):
    def evidence(self):
        return {'actual_existing_physics':{'cache_baked':True,'bake_process_exitcode':0,'fresh_verify_process_exitcode':0},
                'independent_physics_native_stage_exits':{
                    'physics-bake':{'status':'completed','returncode':0,'job_receipt_sha256':'a'*64},
                    'physics-fresh-verify':{'status':'completed','returncode':0,'job_receipt_sha256':'b'*64}}}

    def test_two_distinct_successful_receipts(self):
        validate_native_stage_exits(self.evidence())

    def test_true_cache_cannot_mask_failed_stage(self):
        for name in ('physics-bake','physics-fresh-verify'):
            row=self.evidence();row['independent_physics_native_stage_exits'][name]['returncode']=37
            with self.subTest(stage=name),self.assertRaises(AssertionError):validate_native_stage_exits(row)

    def test_true_cache_cannot_mask_failed_summary(self):
        for key in ('bake_process_exitcode','fresh_verify_process_exitcode'):
            row=self.evidence();row['actual_existing_physics'][key]=41
            with self.subTest(key=key),self.assertRaises(AssertionError):validate_native_stage_exits(row)

    def test_noninteger_exit_is_rejected(self):
        for value in (False,'0'):
            for section,key in (('actual_existing_physics','bake_process_exitcode'),('independent_physics_native_stage_exits','physics-fresh-verify')):
                row=self.evidence()
                if section=='actual_existing_physics':row[section][key]=value
                else:row[section][key]['returncode']=value
                with self.subTest(value=value,section=section),self.assertRaises(AssertionError):validate_native_stage_exits(row)

    def test_missing_or_uncertain_stage_is_rejected(self):
        row=self.evidence();del row['independent_physics_native_stage_exits']['physics-fresh-verify']
        with self.assertRaises(AssertionError):validate_native_stage_exits(row)
        row=self.evidence();row['independent_physics_native_stage_exits']['physics-bake']['status']='uncertain'
        with self.assertRaises(AssertionError):validate_native_stage_exits(row)

    def test_duplicate_or_invalid_receipt_identity_is_rejected(self):
        for digest in ('a'*64,'invalid',None):
            row=self.evidence();row['independent_physics_native_stage_exits']['physics-fresh-verify']['job_receipt_sha256']=digest
            with self.subTest(digest=digest),self.assertRaises(AssertionError):validate_native_stage_exits(row)


class PublishedInventory(unittest.TestCase):
    def test_execution_metadata_does_not_replace_file_inventory(self):
        root = Path(__file__).resolve().parents[1]
        manifest = json.loads((root / 'release/distribution-manifest.json').read_text('utf-8'))
        # Exercise the complete release branch, but leave actual CLI health checks
        # to the standalone distribution run. This test starts no subprocesses.
        with patch.object(distribution.subprocess, 'run', return_value=SimpleNamespace(returncode=0, stdout='usage: fixture')):
            report = distribution.validate(root)
        self.assertEqual(report['skill_files'], len(manifest['files']))
        self.assertEqual(report['skill_scripts_compiled_without_bytecode'], manifest['script_count'])


if __name__=='__main__':unittest.main()
