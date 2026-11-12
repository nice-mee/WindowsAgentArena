"""Saved-artifact checks for GUI5, not Galaxy completion claims."""
from pathlib import Path
import json
import shutil
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch
from zipfile import ZipFile, ZIP_DEFLATED
from openpyxl import load_workbook

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cases import CASES, unique_names, sort_and_chart, writer_cross_reference, slide_style_match, purchase_order_reconcile
from prepare_assets import HERE
from desktop import open_application
from batch import load_suite
import run


class GuiFive(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.work = Path(self.temp.name) / 'materials'
        self.work.mkdir()

    def verdict(self, case, state):
        return case.verify(self.work, state, {}, [])['status']

    def gold(self, case, name=None):
        shutil.copyfile(HERE / 'references' / case.ID / (name or case.FILENAME), self.work / case.FILENAME)

    def rewrite_zip(self, path, replace):
        with ZipFile(path) as z:
            data = {n: z.read(n) for n in z.namelist()}
        for name in list(data):
            data[name] = replace(name, data[name])
        with ZipFile(path, 'w', ZIP_DEFLATED) as z:
            for name, value in data.items():
                z.writestr(name, value)

    def test_names_order_and_source_preservation(self):
        case = unique_names
        state = case.setup(self.work)
        self.assertEqual(self.verdict(case, state), 'failed')
        self.gold(case, 'Names_Duplicate_Unique_gold.xlsx')
        self.assertEqual(self.verdict(case, state), 'passed')
        book = load_workbook(self.work / case.FILENAME)
        sheet = book.active
        sheet['D2'], sheet['D3'] = sheet['D3'].value, sheet['D2'].value
        book.save(self.work / case.FILENAME)
        book.close()
        self.assertEqual(self.verdict(case, state), 'failed')

    def test_chart_checks_data_binding(self):
        case = sort_and_chart
        state = case.setup(self.work)
        self.assertEqual(self.verdict(case, state), 'failed')
        self.gold(case, '6_BoomerangSales_gt1.xlsx')
        self.assertEqual(self.verdict(case, state), 'passed')
        book = load_workbook(self.work / case.FILENAME)
        book['Sheet1']._charts[0].series[0].val.numRef.f = "'Sheet1'!$F$2:$F$36"
        book.save(self.work / case.FILENAME)
        book.close()
        self.assertEqual(self.verdict(case, state), 'failed')

    def test_writer_requires_real_reference(self):
        case = writer_cross_reference
        state = case.setup(self.work)
        self.assertEqual(self.verdict(case, state), 'failed')
        self.gold(case, 'Essay_Writing_English_for_uni_Gold.docx')
        self.assertEqual(self.verdict(case, state), 'passed')
        # Preserve displayed [14] but break its bookmark target.
        self.rewrite_zip(self.work / case.FILENAME, lambda n, b: b.replace(
            b'REF __RefNumPara__486_3519752401', b'REF nonexistent_bookmark') if n == 'word/document.xml' else b)
        self.assertEqual(self.verdict(case, state), 'failed')

    def test_slides_style_and_preserved_references(self):
        case = slide_style_match
        state = case.setup(self.work)
        self.assertEqual(self.verdict(case, state), 'failed')
        self.gold(case)
        self.assertEqual(self.verdict(case, state), 'passed')
        self.rewrite_zip(self.work / case.FILENAME, lambda n, b: b.replace(
            b'Research findings', b'Changed reference') if n == 'content.xml' else b)
        self.assertEqual(self.verdict(case, state), 'failed')

    def test_purchase_decisions_and_missing_approved_request(self):
        case = purchase_order_reconcile
        state = case.setup(self.work)
        self.assertEqual(self.verdict(case, state), 'failed')
        self.gold(case)
        self.assertEqual(self.verdict(case, state), 'passed')
        # Remove a complete row without invalidating other cached formula values.
        from xml.etree import ElementTree as ET
        def missing_order(name, data):
            if name != 'xl/worksheets/sheet1.xml':
                return data
            root = ET.fromstring(data)
            ns = {'x': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
            rows = root.find('x:sheetData', ns)
            rows.remove(rows.find("x:row[@r='7']", ns))
            return ET.tostring(root)
        self.rewrite_zip(self.work / case.FILENAME, missing_order)
        self.assertEqual(self.verdict(case, state), 'failed')

    def test_suite_difficulties_and_application_profiles(self):
        suite = load_suite(HERE / 'suites/gui5.json')
        self.assertEqual([CASES[c['id']].DIFFICULTY for c in suite['cases']], ['medium'] * 3 + ['hard'] * 2)
        self.assertEqual(len(load_suite(HERE / 'suites/linux15.json')['cases']), 15)
        directory = Path(self.temp.name)
        with patch('desktop.subprocess.Popen', return_value=Mock()) as launch:
            for app in ('chrome', 'calc', 'writer', 'impress'):
                open_application(app, self.work / 'input', directory)
        self.assertEqual(launch.call_count, 4)
        self.assertTrue(all((directory / 'application-profile' / app).is_dir()
                            for app in ('chrome', 'calc', 'writer', 'impress')))

    def test_multi_app_partial_startup_stops_opened_process(self):
        from argparse import Namespace
        app = Mock(pid=1234, poll=Mock(return_value=None))
        args = Namespace(case='purchase_order_reconcile', output=Path(self.temp.name)/'runs',
                         ufo_root=Path(self.temp.name)/'ufo', device='linux_device_1',
                         local_services=True, timeout=1)
        with patch.object(run, 'open_application', side_effect=[app, OSError('Calc unavailable')]), \
                patch.object(run, 'stop_group', return_value=True) as stop, patch.object(run.time, 'sleep'), \
                patch.object(run.subprocess, 'Popen') as worker:
            result = run.run_case(args)
        worker.assert_not_called()
        stop.assert_called_once_with(app)
        self.assertEqual(result['status'], 'initialization_failed')
        self.assertEqual(result['difficulty'], 'hard')
        self.assertEqual(result['cleanup']['status'], 'completed')


if __name__ == '__main__':
    unittest.main()
