import hashlib
import json
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
from fastapi.testclient import TestClient

from feature_api.app import MANIFEST, app


class TestFeatureApi(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client_context = TestClient(app)
        cls.client = cls.client_context.__enter__()

    @classmethod
    def tearDownClass(cls):
        cls.client_context.__exit__(None, None, None)

    def setUp(self):
        self.lookup_enabled = patch('feature_api.app.ALLOW_PUBCHEM', True)
        self.lookup_enabled.start()

    def tearDown(self):
        self.lookup_enabled.stop()

    def test_v7_feature_vector_matches_frozen_rdkit_reference(self):
        response = self.client.post("/fingerprint", json={
            "smiles": "COc1cc(C=O)ccc1O",
            "feature_schema_id": MANIFEST["feature_schema_id"],
        })
        self.assertEqual(response.status_code, 200)
        data = response.json()
        vector = np.asarray(data["fingerprint"], dtype="<f4")
        self.assertEqual(data["model_id"], MANIFEST["model_id"])
        self.assertEqual(data["bundle_id"], MANIFEST["bundle_id"])
        self.assertEqual(data["molecular_formula"], "C8H8O3")
        self.assertEqual(vector.shape, (2056,))
        self.assertEqual(hashlib.sha256(vector.tobytes()).hexdigest(),
            "277a89f2b2e833bb7572bf827d29af362118594717d81d2f30c038b4150ea114"
        )

    def test_invalid_mixture_and_mismatched_schema_are_rejected(self):
        for smiles, expected in [("not-smiles", "INVALID_SMILES"), ("CCO.O", "UNSUPPORTED_MIXTURE")]:
            response = self.client.post("/fingerprint", json={
                "smiles": smiles, "feature_schema_id": MANIFEST["feature_schema_id"],
            })
            self.assertEqual(response.status_code, 422)
            self.assertEqual(response.json()["detail"]["code"], expected)
        mismatch = self.client.post("/fingerprint", json={
            "smiles": "CCO", "feature_schema_id": "wrong",
        })
        self.assertEqual(mismatch.status_code, 409)
        self.assertEqual(mismatch.json()["detail"]["code"], "FEATURE_SCHEMA_MISMATCH")

    def test_curated_name_resolves_to_the_same_v7_features(self):
        named = self.client.post("/fingerprint", json={
            "compound_name": "Vanillin", "feature_schema_id": MANIFEST["feature_schema_id"],
        })
        direct = self.client.post("/fingerprint", json={
            "smiles": "COc1cc(C=O)ccc1O", "feature_schema_id": MANIFEST["feature_schema_id"],
        })
        self.assertEqual(named.status_code, 200)
        self.assertEqual(named.json()["lookup_source"], "catalog")
        self.assertEqual(named.json()["smiles"], direct.json()["smiles"])
        self.assertEqual(named.json()["fingerprint"], direct.json()["fingerprint"])

    def test_catalog_name_features_never_need_pubchem(self):
        with patch("feature_api.app.requests.get") as get:
            get.return_value.status_code = 200
            get.return_value.json.return_value = {
                "PropertyTable": {"Properties": [{
                    "SMILES": "CCOC(=O)C", "IUPACName": "ethyl acetate",
                }]},
            }
            response = self.client.post("/fingerprint", json={
                "compound_name": "ethyl acetate",
                "feature_schema_id": MANIFEST["feature_schema_id"],
            })
        self.assertEqual(response.status_code, 200)
        get.assert_not_called()
        self.assertEqual(response.json()["lookup_source"], "catalog")
        self.assertEqual(response.json()["smiles"], "CCOC(C)=O")

    def test_resolve_common_names_and_ambiguous_formula(self):
        water = self.client.post("/resolve", json={"query": "Air"})
        self.assertEqual(water.status_code, 200)
        self.assertEqual(water.json()["candidates"][0]["smiles"], "O")
        self.assertFalse(water.json()["candidates"][0]["prediction_supported"])
        carbon_dioxide = self.client.post("/resolve", json={"query": "CO2"})
        self.assertEqual(carbon_dioxide.status_code, 200)
        self.assertEqual(carbon_dioxide.json()["candidates"][0]["smiles"], "O=C=O")
        self.assertFalse(carbon_dioxide.json()["candidates"][0]["prediction_supported"])
        formula = self.client.post("/resolve", json={"query": "C2H6O"})
        self.assertEqual(formula.status_code, 200)
        structures = {item["smiles"] for item in formula.json()["candidates"]}
        self.assertEqual(structures, {"CCO", "COC"})

    def test_resolve_catalog_name_without_network(self):
        with patch("feature_api.app.requests.get") as get:
            response = self.client.post("/resolve", json={"query": "Vanillin"})
            local_name = self.client.post("/resolve", json={"query": "vanilin"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["candidates"][0]["source"], "catalog")
        self.assertTrue(response.json()["candidates"][0]["in_catalog"])
        self.assertEqual(local_name.json()["candidates"][0]["smiles"],
                         response.json()["candidates"][0]["smiles"])
        get.assert_not_called()

    def test_resolve_external_name_requires_confirmable_structure(self):
        with patch("feature_api.app.requests.get") as get:
            get.side_effect = [
                type("Response", (), {"status_code": 200,
                    "raise_for_status": lambda self: None,
                    "json": lambda self: {"IdentifierList": {"CID": [123]}}})(),
                type("Response", (), {"status_code": 200,
                    "raise_for_status": lambda self: None,
                    "json": lambda self: {"PropertyTable": {"Properties": [{
                        "CID": 123, "Title": "Example", "SMILES": "CCO",
                        "MolecularFormula": "C2H6O"}]}}})(),
            ]
            response = self.client.post("/resolve", json={"query": "external example"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["candidates"][0]["cid"], "123")
        self.assertIn("name/external%20example/cids/JSON", get.call_args_list[0].args[0])

    def test_unsupported_structures_are_blocked_through_every_input_route(self):
        for key, value in [('smiles', 'O'), ('smiles', 'O=C=O'), ('smiles', 'N'),
                           ('compound_name', 'Air'), ('compound_name', 'CO2')]:
            with self.subTest(key=key, value=value):
                response = self.client.post('/fingerprint', json={
                    key: value, 'feature_schema_id': MANIFEST['feature_schema_id']})
                self.assertEqual(response.status_code, 422)
                self.assertEqual(response.json()['detail']['code'], 'UNSUPPORTED_COMPOUND')

    def test_local_mode_keeps_catalog_formula_and_smiles_without_external_network(self):
        with patch('feature_api.app.ALLOW_PUBCHEM', False), patch('feature_api.app.requests.get') as get:
            health = self.client.get('/health').json()
            self.assertFalse(health['capabilities']['external_lookup'])
            self.assertEqual(health['input_dimensions'], 2056)
            self.assertEqual(health['label_count'], 109)
            self.assertEqual(self.client.post('/resolve', json={'query': 'C2H6O'}).status_code, 200)
            self.assertEqual(self.client.post('/resolve', json={'query': 'vanilin'}).status_code, 200)
            unknown = self.client.post('/resolve', json={'query': 'not-in-local-catalog'})
            self.assertEqual(unknown.status_code, 404)
            self.assertEqual(unknown.json()['detail']['code'], 'COMPOUND_NOT_IN_LOCAL_CATALOG')
            unknown_name = self.client.post('/fingerprint', json={
                'compound_name': 'not-in-local-catalog', 'feature_schema_id': MANIFEST['feature_schema_id']})
            self.assertEqual(unknown_name.status_code, 404)
            direct = self.client.post('/fingerprint', json={
                'smiles': 'CCO', 'feature_schema_id': MANIFEST['feature_schema_id']})
            self.assertEqual(direct.status_code, 200)
            get.assert_not_called()

    def test_ambiguous_formula_cannot_bypass_structure_confirmation(self):
        response = self.client.post('/fingerprint', json={
            'compound_name': 'C2H6O', 'feature_schema_id': MANIFEST['feature_schema_id']})
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()['detail']['code'], 'AMBIGUOUS_COMPOUND')

    def test_native_predictions_match_all_frozen_python_scores_without_external_network(self):
        reference = json.loads((Path(__file__).parent / 'fixtures/v7_reference.json').read_text(encoding='utf-8-sig'))
        self.assertEqual(reference['source_bundle_sha256'], MANIFEST['source_bundle_sha256'])
        with patch('feature_api.app.ALLOW_PUBCHEM', False), patch('feature_api.app.requests.get') as get:
            for molecule in reference['molecules']:
                with self.subTest(name=molecule['name']):
                    response = self.client.post('/predict', json={
                        'smiles': molecule['input_smiles'],
                        'feature_schema_id': MANIFEST['feature_schema_id'],
                        'bundle_id': MANIFEST['bundle_id'],
                    })
                    self.assertEqual(response.status_code, 200)
                    result = response.json()
                    self.assertEqual(result['runtime'], 'lightgbm')
                    self.assertEqual(result['label_count'], 109)
                    self.assertEqual(result['input_dimensions'], 2056)
                    self.assertEqual(result['primary_threshold'], 0.5)
                    self.assertEqual(result['smiles'], molecule['canonical_smiles'])
                    self.assertNotIn('fingerprint', result)
                    self.assertEqual([item['label'] for item in result['scores']], MANIFEST['labels'])
                    np.testing.assert_array_equal(
                        [item['score'] for item in result['scores']],
                        [item['score'] for item in molecule['labels']],
                    )
            get.assert_not_called()

    def test_native_health_requires_loaded_original_models(self):
        health = self.client.get('/health').json()
        self.assertEqual(health['status'], 'ok')
        self.assertEqual(health['runtime'], 'lightgbm')
        self.assertTrue(health['model_ready'])
        self.assertTrue(health['capabilities']['local_prediction'])
        with patch('feature_api.app.PREDICTOR', None):
            not_ready = self.client.get('/health').json()
            self.assertEqual(not_ready['status'], 'not_ready')
            response = self.client.post('/predict', json={
                'smiles': 'CCO', 'feature_schema_id': MANIFEST['feature_schema_id'],
                'bundle_id': MANIFEST['bundle_id'],
            })
            self.assertEqual(response.status_code, 503)
            self.assertEqual(response.json()['detail']['code'], 'MODEL_NOT_READY')

    def test_prediction_rejects_wrong_contract_and_invalid_inputs_before_inference(self):
        valid = {'smiles': 'CCO', 'feature_schema_id': MANIFEST['feature_schema_id'],
                 'bundle_id': MANIFEST['bundle_id']}
        cases = [
            ({'bundle_id': 'old-runtime-bundle'}, 409, 'MODEL_BUNDLE_MISMATCH'),
            ({'feature_schema_id': 'wrong'}, 409, 'FEATURE_SCHEMA_MISMATCH'),
            ({'smiles': 'not-smiles'}, 422, 'INVALID_SMILES'),
            ({'smiles': 'CCO.O'}, 422, 'UNSUPPORTED_MIXTURE'),
            ({'smiles': 'O'}, 422, 'UNSUPPORTED_COMPOUND'),
            ({'smiles': 'O=C=O'}, 422, 'UNSUPPORTED_COMPOUND'),
            ({'smiles': 'N'}, 422, 'UNSUPPORTED_COMPOUND'),
            ({'smiles': None, 'compound_name': 'C2H6O'}, 422, 'AMBIGUOUS_COMPOUND'),
        ]
        with patch('feature_api.app.PREDICTOR.predict') as inference:
            for override, status, code in cases:
                with self.subTest(override=override):
                    response = self.client.post('/predict', json={**valid, **override})
                    self.assertEqual(response.status_code, status)
                    self.assertEqual(response.json()['detail']['code'], code)
            inference.assert_not_called()

    def test_model_failure_does_not_return_partial_or_fabricated_scores(self):
        with patch('feature_api.app.PREDICTOR.predict', side_effect=ValueError('model failed')):
            response = self.client.post('/predict', json={
                'smiles': 'CCO', 'feature_schema_id': MANIFEST['feature_schema_id'],
                'bundle_id': MANIFEST['bundle_id'],
            })
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()['detail']['code'], 'MODEL_ERROR')
        self.assertNotIn('scores', response.json())
