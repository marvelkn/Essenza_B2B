import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from feature_api.native_model import (
    MANIFEST_PATH, NativeModelError, NativePredictor, validate_manifest,
)


class TestNativePackageIntegrity(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = json.loads(MANIFEST_PATH.read_text(encoding='utf-8'))

    def test_preprocessing_label_order_and_threshold_cannot_silently_change(self):
        changes = (
            lambda item: item['feature_spec'].update(radius=3),
            lambda item: item['feature_spec']['descriptors'].reverse(),
            lambda item: item['labels'].reverse(),
            lambda item: item.update(primary_threshold=0.6),
        )
        for change in changes:
            altered = copy.deepcopy(self.manifest)
            change(altered)
            with self.subTest(change=repr(change)), self.assertRaises(NativeModelError):
                validate_manifest(altered)

    def test_missing_model_fails_before_any_deserialization(self):
        with tempfile.TemporaryDirectory() as directory, patch('feature_api.native_model.joblib.load') as load:
            with self.assertRaisesRegex(NativeModelError, 'belum tersedia'):
                NativePredictor(model_dir=directory)
            load.assert_not_called()

    def test_corrupt_model_fails_before_any_deserialization(self):
        with tempfile.TemporaryDirectory() as directory, patch('feature_api.native_model.joblib.load') as load:
            (Path(directory) / self.manifest['models'][0]['filename']).write_bytes(b'changed model')
            with self.assertRaisesRegex(NativeModelError, 'Checksum'):
                NativePredictor(model_dir=directory)
            load.assert_not_called()

    def test_incompatible_runtime_version_fails_before_deserialization(self):
        with patch('feature_api.native_model.verify_package', return_value=self.manifest), \
                patch('feature_api.native_model.version', return_value='0.0.0'), \
                patch('feature_api.native_model.joblib.load') as load:
            with self.assertRaisesRegex(NativeModelError, 'Runtime memerlukan'):
                NativePredictor()
            load.assert_not_called()
