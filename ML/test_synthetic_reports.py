import csv
import json
import random
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from build_dataset import build_feature_rows, read_manifest
from report_parser import analyze_report, extract_features
from synthetic_reports import COUNT_FIELDS, generate_dataset, make_report, write_manifest


class SyntheticReportTests(unittest.TestCase):
    def test_reports_match_contract_and_include_overlapping_behavior(self):
        for malicious in (False, True):
            rng = random.Random(42)
            features = []
            commands = []
            for _ in range(150):
                report = make_report(malicious, rng)
                self.assertEqual(report['signatures'], [])
                self.assertTrue(report['metadata']['synthetic'])
                self.assertNotIn('label', report)
                self.assertEqual(report['original_filename'], 'sample.exe')
                for count, events in COUNT_FIELDS.items():
                    self.assertEqual(report['summary'][count], len(report[events]))
                self.assertTrue(all('target_object' in e for e in report['registry']))
                self.assertTrue(all('command_line' in e for e in report['processes']))
                features.append(extract_features(report))
                self.assertEqual(analyze_report(report).features, features[-1])
                commands.extend(e['command_line'] for e in report['processes'])
            self.assertTrue(any(f['num_network_connections'] > 0 and
                                f['num_registry_keys_set'] > 0 for f in features))
            self.assertTrue(any(f['num_processes_created'] <= 2 and
                                f['num_network_connections'] <= 1 and
                                f['num_files_written'] <= 1 for f in features))
            self.assertEqual({f['has_persistence_signature'] for f in features}, {0, 1})
            self.assertTrue(any('/Create' in c for c in commands))
            if not malicious:
                self.assertTrue(any('/Query' in c for c in commands))

    def test_seed_reproduces_reports_and_labels_without_global_rng_changes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            state = random.getstate()
            first = generate_dataset(20, root / 'first', 0.5, 12)
            second = generate_dataset(20, root / 'second', 0.5, 12)
            third = generate_dataset(20, root / 'third', 0.5, 13)
            self.assertEqual(random.getstate(), state)
            self.assertEqual([label for _, label in first], [label for _, label in second])
            self.assertEqual(sum(label for _, label in first), 10)
            self.assertEqual([p.read_bytes() for p, _ in first],
                             [p.read_bytes() for p, _ in second])
            self.assertNotEqual(first[0][0].read_bytes(), third[0][0].read_bytes())

    def test_invalid_arguments_and_existing_reports_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for count, ratio in ((0, .5), (-1, .5), (True, .5), (2, -0.1),
                                 (2, 1.1), (2, float('nan'))):
                with self.subTest(count=count, ratio=ratio):
                    with self.assertRaises(ValueError):
                        generate_dataset(count, root / 'invalid', ratio)
            self.assertFalse((root / 'invalid').exists())
            manifest = generate_dataset(1, root / 'valid', 0)
            original = manifest[0][0].read_bytes()
            with self.assertRaisesRegex(ValueError, 'already exist'):
                generate_dataset(1, root / 'valid', 1)
            self.assertEqual(manifest[0][0].read_bytes(), original)
            destination = root / 'manifest.csv'
            write_manifest(manifest, destination)
            with self.assertRaises(FileExistsError):
                write_manifest(manifest, destination)

    def test_cli_manifest_and_dataset_builder(self):
        with tempfile.TemporaryDirectory(prefix='synthetic,reports ') as directory:
            root = Path(directory)
            manifest_path = root / 'manifest.csv'
            script = Path(__file__).with_name('synthetic_reports.py')
            result = subprocess.run(
                [sys.executable, '-B', str(script), '--count', '300', '--seed', '42',
                 '--out-dir', str(root / 'reports'), '--manifest', str(manifest_path)],
                capture_output=True, text=True, timeout=30,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('SYNTHETIC', result.stdout)
            manifest = read_manifest(manifest_path)
            rows = build_feature_rows(manifest)
            self.assertEqual(len(rows), 300)
            self.assertEqual(sum(row['label'] for row in rows), 150)
            self.assertTrue(all(path.is_absolute() for path, _ in manifest))
            # Exercise the existing CSV export as well as its Python helpers.
            output = root / 'features.csv'
            result = subprocess.run(
                [sys.executable, '-B', str(script.with_name('build_dataset.py')),
                 '--manifest', str(manifest_path), '--out', str(output)],
                capture_output=True, text=True, timeout=30,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            with output.open(newline='', encoding='utf-8') as stream:
                self.assertEqual(len(list(csv.DictReader(stream))), 300)


if __name__ == '__main__':
    unittest.main()
