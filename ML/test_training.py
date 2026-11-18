import copy
import json
import random
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

from evaluate import evaluate_classifier
from model_utils import benign_training_records, labels_from_records, reports_to_matrix
from split_dataset import split_records
from synthetic_reports import make_report
from tune_threshold import select_threshold


class TrainingTests(unittest.TestCase):
    def setUp(self):
        rng = random.Random(7)
        self.records = [{'report': make_report(bool(i % 2), rng), 'label': i % 2}
                        for i in range(60)]

    def test_reproducible_stratified_disjoint_splits(self):
        original = copy.deepcopy(self.records)
        parts = split_records(self.records)
        self.assertEqual(parts, split_records(self.records))
        self.assertNotEqual(parts, split_records(self.records, seed=99))
        self.assertEqual(self.records, original)
        ids = []
        for name, size in (('train', 36), ('validation', 12), ('test', 12)):
            self.assertEqual(len(parts[name]), size)
            self.assertEqual(sum(r['label'] for r in parts[name]), size // 2)
            ids.extend(r['report']['job_id'] for r in parts[name])
        self.assertEqual(len(set(ids)), 60)
        self.assertEqual(set(ids), {r['report']['job_id'] for r in self.records})
        self.assertEqual(parts['train_benign'], [r for r in parts['train'] if r['label'] == 0])

    def test_split_rejects_duplicates_small_classes_and_invalid_ratios(self):
        with self.assertRaisesRegex(ValueError, 'Duplicate'):
            split_records(self.records + [copy.deepcopy(self.records[0])])
        changed = copy.deepcopy(self.records[0])
        changed['report']['timeout_seconds'] = 99
        with self.assertRaisesRegex(ValueError, 'Duplicate'):
            split_records(self.records + [changed])
        with self.assertRaisesRegex(ValueError, 'enough reports'):
            split_records(self.records[:4])
        for validation, test in ((0, .2), (.5, .5), (-.1, .2), (float('nan'), .2)):
            with self.assertRaises(ValueError):
                split_records(self.records, validation, test)

    def test_strict_labels_and_benign_only_training(self):
        for value in (True, False, '0', '1', 0.0, 1.5, 2, -1, None):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    labels_from_records([{'label': value}])
        for operation in (labels_from_records, reports_to_matrix, benign_training_records):
            with self.assertRaises(ValueError):
                operation([])
        with self.assertRaisesRegex(ValueError, 'only records labeled 0'):
            benign_training_records(self.records)
        benign = [r for r in self.records if r['label'] == 0]
        self.assertEqual(benign_training_records(benign), benign)
        with self.assertRaises(ValueError):
            benign_training_records([{'report': self.records[0]['report']}])

    def test_threshold_selection_and_evaluation_use_probability_cutoff(self):
        result = select_threshold([0, 0, 1, 1], [.1, .2, .3, .4])
        self.assertEqual(result['threshold'], .3)
        self.assertEqual(result['validation_f1'], 1.0)
        self.assertEqual(select_threshold([0, 1], [.1, .9])['threshold'], .5)
        for labels, probabilities in (([0, 0], [.1, .2]), ([0, 1], [.1, float('nan')]),
                                      ([0, 1], [0.1]), ([0, 1], [.1, 2])):
            with self.assertRaises(ValueError):
                select_threshold(labels, probabilities)

        class Model:
            classes_ = [1, 0]  # Test malicious-column lookup, not a fixed index.
            def predict_proba(self, features):
                return np.array([[.1, .9], [.2, .8], [.3, .7], [.4, .6]])
        records = [{'label': value} for value in (0, 0, 1, 1)]
        metrics = evaluate_classifier(Model(), np.zeros((4, 9)), records, .3)
        self.assertEqual(metrics['f1_score'], 1.0)
        self.assertEqual(metrics['threshold'], .3)

    def test_cli_split_train_tune_and_held_out_evaluation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'records.json'
            source.write_text(json.dumps(self.records))
            def run(script, *args, success=True):
                result = subprocess.run(
                    [sys.executable, '-B', str(Path(__file__).with_name(script)), *map(str, args)],
                    capture_output=True, text=True, timeout=60)
                self.assertEqual(result.returncode == 0, success, result.stderr)
                return result
            splits = root / 'splits'
            run('split_dataset.py', '--data', source, '--out-dir', splits)
            info = json.loads((splits / 'split_info.json').read_text())
            self.assertEqual(info['counts']['test']['total'], 12)
            classifier = root / 'models' / 'classifier.joblib'
            anomaly = root / 'models' / 'anomaly.joblib'
            run('train_classifier.py', '--data', splits / 'train.json', '--model-out', classifier, '--trees', '5')
            run('train_anomaly.py', '--data', splits / 'train.json', '--model-out', anomaly, success=False)
            self.assertFalse(anomaly.exists())
            run('train_anomaly.py', '--data', splits / 'train_benign.json', '--model-out', anomaly)
            threshold_file = root / 'threshold.json'
            run('tune_threshold.py', '--validation-data', splits / 'validation.json',
                '--model', classifier, '--out', threshold_file)
            threshold = json.loads(threshold_file.read_text())['threshold']
            result = run('evaluate.py', '--data', splits / 'test.json', '--model', classifier,
                         '--model-type', 'classifier', '--threshold', threshold)
            self.assertEqual(json.loads(result.stdout)['threshold'], threshold)
            run('evaluate.py', '--data', splits / 'test.json', '--model', anomaly, '--model-type', 'anomaly')
            run('split_dataset.py', '--data', source, '--out-dir', splits, success=False)


if __name__ == '__main__':
    unittest.main()
