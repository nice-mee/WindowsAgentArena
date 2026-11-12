"""Small fixture/verifier checks. These are not Galaxy execution results."""
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch, Mock
from zipfile import ZipFile, ZIP_DEFLATED

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cases import (replace_text, collect_jpg, collect_failed_notebooks,
                   normalize_permissions, archive_by_age, zoom_out, monthly_sales,
                   logs, config)
from prepare_assets import HERE
from desktop import open_application
from openpyxl import load_workbook


class Stage3Cases(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.work = Path(self.temp.name) / "materials"
        self.work.mkdir()

    def verdict(self, case, state):
        return case.verify(self.work, state, {}, [])["status"]

    def test_replace_saved_text_and_one_missed_replacement(self):
        state = replace_text.setup(self.work)
        output = self.work / replace_text.FILENAME
        shutil.copyfile(HERE / "references/replace_text/vscode_replace_text_gold.txt", output)
        self.assertEqual(self.verdict(replace_text, state), "passed")
        output.write_text(output.read_text().replace("test", "text", 1))
        self.assertEqual(self.verdict(replace_text, state), "failed")

    def test_collect_jpg_and_one_missing_image(self):
        state = collect_jpg.setup(self.work)
        for source in (self.work / "photos").rglob("*.jpg"):
            shutil.copyfile(source, self.work / "cpjpg" / source.name)
        self.assertEqual(self.verdict(collect_jpg, state), "passed")
        next((self.work / "cpjpg").iterdir()).unlink()
        self.assertEqual(self.verdict(collect_jpg, state), "failed")

    def test_notebook_paths_and_incorrect_flattening(self):
        state = collect_failed_notebooks.setup(self.work)
        for name in state["expected"]:
            output = self.work / "fails" / name
            output.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(self.work / "project" / name, output)
        self.assertEqual(self.verdict(collect_failed_notebooks, state), "passed")
        nested = self.work / "fails/dir2/subdir1/c_failed.ipynb"
        nested.rename(self.work / "fails" / nested.name)
        self.assertEqual(self.verdict(collect_failed_notebooks, state), "failed")

    def test_permissions_and_one_unchanged_file(self):
        state = normalize_permissions.setup(self.work)
        self.assertEqual([oct((self.work / name).stat().st_mode & 0o777) for name in normalize_permissions.INITIAL_MODES],
                         ["0o755", "0o644", "0o777"])
        for name in state["sha256"]:
            (self.work / name).chmod(0o644)
        self.assertEqual(self.verdict(normalize_permissions, state), "passed")
        (self.work / "testDir/file1.txt").chmod(0o755)
        self.assertEqual(self.verdict(normalize_permissions, state), "failed")

    def test_archive_and_missing_old_member(self):
        state = archive_by_age.setup(self.work)
        for name, mtime in state["mtimes"].items():
            self.assertAlmostEqual((self.work / name).stat().st_mtime, mtime, places=4)
        archive_path = self.work / "old_files/history.zip"
        with ZipFile(archive_path, "w", ZIP_DEFLATED) as archive:
            for name in state["old"]:
                archive.write(self.work / "test_files" / name, name)
        for name in state["new"]:
            (self.work / "test_files" / name).rename(self.work / "new_files" / name)
        self.assertEqual(self.verdict(archive_by_age, state), "passed")
        with ZipFile(archive_path, "w", ZIP_DEFLATED) as archive:
            name = next(iter(state["old"]))
            archive.write(self.work / "test_files" / name, name)
        self.assertEqual(self.verdict(archive_by_age, state), "failed")

    def test_zoom_saved_reference_and_unchanged_input(self):
        state = zoom_out.setup(self.work)
        self.assertEqual(self.verdict(zoom_out, state), "failed")
        shutil.copyfile(HERE / "references/zoom_out/Zoom_Out_Oversized_Cells_gold.xlsx", self.work / zoom_out.FILENAME)
        self.assertEqual(self.verdict(zoom_out, state), "passed")

    def test_sales_cached_reference_and_wrong_total(self):
        state = monthly_sales.setup(self.work)
        path = self.work / monthly_sales.FILENAME
        shutil.copyfile(HERE / "references/monthly_sales/3_SalesRep_gt1.xlsx", path)
        self.assertEqual(self.verdict(monthly_sales, state), "passed")
        book = load_workbook(path)
        book["Sheet2"]["B2"] = -1
        book.save(path)
        book.close()
        self.assertEqual(self.verdict(monthly_sales, state), "failed")

    def test_natural_answers_compare_values_without_expected_number_search(self):
        expected = {"error_count": 2, "error_request_ids": ["a", "b"], "error_codes": ["E_A", "E_B"]}
        answer = "共 2 条 ERROR 日志。\n1. request_id=a, code=E_A\n2. request_id=b, code=E_B"
        self.assertEqual(logs.judge_answer(answer, expected)["status"], "passed")
        self.assertEqual(logs.judge_answer(answer.replace("2 条", "3 条"), expected)["status"], "failed")
        expected = {"changes": {"retries": {"before": "1", "after": "5"}}}
        self.assertEqual(config.judge_answer("1. retries: 修改前='1' -> 修改后='5'", expected)["status"], "passed")
        self.assertEqual(config.judge_answer("retries: 1 -> 4", expected)["status"], "failed")

    def test_gui_launch_uses_separate_profile_and_owned_process_group(self):
        for app in ("code", "calc"):
            directory = Path(self.temp.name) / app
            directory.mkdir()
            with patch("desktop.subprocess.Popen", return_value=Mock()) as launch:
                open_application(app, self.work / "input", directory)
            command = launch.call_args.args[0]
            self.assertTrue(launch.call_args.kwargs["start_new_session"])
            self.assertTrue(any(str(directory / "application-profile") in part for part in command))


if __name__ == "__main__":
    unittest.main()
