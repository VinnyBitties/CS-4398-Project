import csv
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from build_dataset import build_feature_rows, build_records, read_manifest, write_records_json
from config import FEATURE_COLUMNS
from model_utils import labels_from_records, load_records, reports_to_matrix
from synthetic_reports import generate_dataset, write_manifest


class DatasetExportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.manifest = generate_dataset(20, self.root / 'reports', seed=42)
        self.manifest_path = self.root / 'manifest.csv'
        write_manifest(self.manifest, self.manifest_path)

    def run_script(self, script, *args, success=True):
        result = subprocess.run(
            [sys.executable, '-B', str(Path(__file__).with_name(script)), *map(str, args)],
            cwd=self.root, capture_output=True, text=True, timeout=60,
        )
        if success:
            self.assertEqual(result.returncode, 0, result.stderr)
        else:
            self.assertNotEqual(result.returncode, 0)
        return result

    def test_json_round_trip_preserves_reports_labels_and_features(self):
        records = build_records(read_manifest(self.manifest_path))
        out = self.root / 'nested' / 'records.json'
        write_records_json(records, out)
        loaded = load_records(out)
        for record, (path, label) in zip(loaded, self.manifest):
            self.assertEqual(record, {'report': json.loads(path.read_text()), 'label': label})
        rows = build_feature_rows(self.manifest)
        self.assertEqual(reports_to_matrix(loaded).tolist(),
                         [[row[column] for column in FEATURE_COLUMNS] for row in rows])
        self.assertEqual(labels_from_records(loaded).tolist(), [row['label'] for row in rows])

    def test_cli_formats_and_defaults(self):
        for args, output in (
            ([], self.root / 'data' / 'features.csv'),
            (['--format', 'json'], self.root / 'data' / 'records.json'),
            (['--out', 'inferred.json'], self.root / 'inferred.json'),
            (['--format', 'json', '--out', 'explicit.data'], self.root / 'explicit.data'),
        ):
            with self.subTest(args=args):
                self.run_script('build_dataset.py', '--manifest', self.manifest_path, *args)
                if output.suffix == '.csv':
                    with output.open(newline='') as stream:
                        rows = list(csv.DictReader(stream))
                    self.assertEqual(len(rows), 20)
                    self.assertEqual(list(rows[0]), [*FEATURE_COLUMNS, 'label'])
                else:
                    self.assertEqual(len(load_records(output)), 20)

    def test_invalid_input_does_not_replace_output(self):
        output = self.root / 'records.json'
        output.write_text('existing output')
        path = self.manifest[0][0]
        for contents in ('not json', '{}', '[]'):
            path.write_text(contents)
            result = self.run_script('build_dataset.py', '--manifest', self.manifest_path,
                                     '--out', output, success=False)
            self.assertIn(str(path), result.stderr)
            self.assertEqual(output.read_text(), 'existing output')
        path.unlink()
        with self.assertRaisesRegex(ValueError, 'Invalid report'):
            build_records(self.manifest)

    def test_empty_manifest_and_invalid_labels(self):
        with self.assertRaisesRegex(ValueError, 'at least one'):
            build_records([])
        for label in ('2', '-1', 'true', '0.5', ''):
            self.manifest_path.write_text('report_path,label\nreport.json,' + label + '\n')
            with self.assertRaisesRegex(ValueError, 'row 2'):
                read_manifest(self.manifest_path)
        with self.assertRaisesRegex(ValueError, 'label'):
            build_records([(self.manifest[0][0], True)])

    def test_exports_work_with_existing_trainers_and_evaluator(self):
        records_path = self.root / 'training.json'
        self.run_script('build_dataset.py', '--manifest', self.manifest_path, '--out', records_path)
        classifier = self.root / 'classifier.joblib'
        self.run_script('train_classifier.py', '--data', records_path,
                        '--model-out', classifier, '--trees', '5')
        # Anomaly training currently relies on callers to supply benign data.
        benign_manifest = self.root / 'benign.csv'
        write_manifest([(p, label) for p, label in self.manifest if label == 0], benign_manifest)
        benign_records = self.root / 'benign.json'
        self.run_script('build_dataset.py', '--manifest', benign_manifest, '--out', benign_records)
        anomaly = self.root / 'anomaly.joblib'
        self.run_script('train_anomaly.py', '--data', benign_records, '--model-out', anomaly)
        self.assertTrue(classifier.is_file())
        self.assertTrue(anomaly.is_file())
        test_manifest = generate_dataset(10, self.root / 'test_reports', seed=123)
        test_records = self.root / 'test.json'
        write_records_json(build_records(test_manifest), test_records)
        for model, kind in ((classifier, 'classifier'), (anomaly, 'anomaly')):
            result = self.run_script('evaluate.py', '--data', test_records,
                                     '--model', model, '--model-type', kind)
            self.assertIsInstance(json.loads(result.stdout), dict)


if __name__ == '__main__':
    unittest.main()
