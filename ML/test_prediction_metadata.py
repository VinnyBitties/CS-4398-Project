import copy
import hashlib
import json
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from urllib.request import Request, urlopen

import joblib
import numpy as np
from sklearn.ensemble import IsolationForest, RandomForestClassifier

from config import FEATURE_COLUMNS, FEATURE_SCHEMA_VERSION
from model_utils import stamp_feature_schema
from predict import create_server, load_model, model_info, predict_report


class PredictionMetadataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = json.loads(Path(__file__).with_name('sandbox_example.json').read_text())
        features = np.array([[i] * len(FEATURE_COLUMNS) for i in range(8)])
        cls.classifier = RandomForestClassifier(n_estimators=3, random_state=42).fit(
            features, [0, 0, 0, 0, 1, 1, 1, 1])
        cls.anomaly = IsolationForest(n_estimators=3, random_state=42).fit(features[:4])
        stamp_feature_schema(cls.classifier)
        stamp_feature_schema(cls.anomaly)

    def test_sources_and_health_for_all_model_combinations(self):
        baseline = predict_report(self.report, threshold=.7)
        for classifier, anomaly in ((None, None), (self.classifier, None),
                                     (None, self.anomaly), (self.classifier, self.anomaly)):
            with self.subTest(classifier=classifier is not None, anomaly=anomaly is not None):
                expected = predict_report(self.report, .7, classifier, anomaly)
                self.assertEqual(expected['prediction_source'], 'trained_model' if classifier is not None else 'heuristic')
                self.assertEqual(expected['anomaly_source'], 'trained_model' if anomaly is not None else None)
                if classifier is None:
                    for key in ('risk_score', 'risk_level', 'malicious'):
                        self.assertEqual(expected[key], baseline[key])
                self.assertEqual('anomaly_score' in expected, anomaly is not None)
                self.assertEqual(expected['models']['classifier']['loaded'], classifier is not None)
                self.assertEqual(expected['models']['anomaly']['loaded'], anomaly is not None)
                server = create_server('127.0.0.1', 0, .7, classifier, anomaly)
                thread = threading.Thread(target=server.serve_forever, daemon=True)
                thread.start()
                try:
                    url = f'http://127.0.0.1:{server.server_port}'
                    with urlopen(url + '/health', timeout=5) as response:
                        health = json.loads(response.read())
                    self.assertEqual(health['status'], 'ok')
                    for key in ('prediction_source', 'anomaly_source', 'models', 'threshold', 'feature_schema_version'):
                        self.assertEqual(health[key], expected[key])
                    request = Request(url + '/analyze', data=json.dumps(self.report).encode(),
                                      headers={'Content-Type': 'application/json'})
                    with urlopen(request, timeout=5) as response:
                        self.assertEqual(json.loads(response.read()), expected)
                finally:
                    server.shutdown()
                    server.server_close()
                    thread.join()

    def test_artifact_version_and_cli_match_loaded_model_predictions(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            classifier_path, anomaly_path = root / 'rf.joblib', root / 'if.joblib'
            joblib.dump(self.classifier, classifier_path)
            joblib.dump(self.anomaly, anomaly_path)
            classifier, anomaly = load_model(classifier_path), load_model(anomaly_path)
            expected_hash = 'sha256:' + hashlib.sha256(classifier_path.read_bytes()).hexdigest()
            self.assertEqual(model_info(classifier)['version'], expected_hash)
            self.assertEqual(model_info(classifier)['feature_schema_version'], FEATURE_SCHEMA_VERSION)
            self.assertTrue(model_info(classifier)['schema_verified'])
            result = subprocess.run(
                [sys.executable, '-B', str(Path(__file__).with_name('predict.py')),
                 '--classifier-model', str(classifier_path), '--anomaly-model', str(anomaly_path),
                 '--threshold', '.7'], input=json.dumps(self.report), text=True,
                capture_output=True, timeout=60)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout), predict_report(self.report, .7, classifier, anomaly))

    def test_legacy_models_are_unverified_and_mismatches_rejected(self):
        legacy = copy.deepcopy(self.classifier)
        del legacy.sentinel_feature_schema_
        self.assertFalse(model_info(legacy)['schema_verified'])
        self.assertIsNone(model_info(legacy)['feature_schema_version'])
        self.assertIsNone(model_info(legacy)['version'])  # No artifact was loaded.
        for schema in ({'version': 'old', 'columns': FEATURE_COLUMNS},
                       {'version': FEATURE_SCHEMA_VERSION, 'columns': list(reversed(FEATURE_COLUMNS))}):
            model = copy.deepcopy(self.classifier)
            model.sentinel_feature_schema_ = schema
            with self.assertRaisesRegex(ValueError, 'schema'):
                create_server('127.0.0.1', 0, classifier=model)
            with tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / 'bad.joblib'
                joblib.dump(model, path)
                with self.assertRaisesRegex(ValueError, 'schema'):
                    load_model(path)
        legacy.n_features_in_ = 2
        with self.assertRaisesRegex(ValueError, 'feature count'):
            model_info(legacy)

    def test_invalid_threshold_rejected_before_server_starts(self):
        for threshold in (-1, 2, float('nan')):
            with self.assertRaises(ValueError):
                create_server('127.0.0.1', 0, threshold)


if __name__ == '__main__':
    unittest.main()
