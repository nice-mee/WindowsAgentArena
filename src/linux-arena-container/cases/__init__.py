"""Explicit registry; no discovery, inheritance, or plugin machinery."""
from prepare_assets import HERE
from . import (logs, config, php_line_count, replace_text, collect_jpg,
               collect_failed_notebooks, normalize_permissions, archive_by_age,
               zoom_out, monthly_sales, unique_names, sort_and_chart,
               writer_cross_reference, slide_style_match, purchase_order_reconcile)

CASES = {case.ID: case for case in (logs, config, php_line_count, replace_text,
                                   collect_jpg, collect_failed_notebooks,
                                   normalize_permissions, archive_by_age,
                                   zoom_out, monthly_sales, unique_names, sort_and_chart,
                                   writer_cross_reference, slide_style_match, purchase_order_reconcile)}


def get_case(case_id):
    return CASES[case_id]
