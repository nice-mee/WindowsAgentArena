"""Grade sorted records and a saved line chart bound to the correct data."""
from collections import Counter
import posixpath
import warnings
from xml.etree import ElementTree as ET
from zipfile import ZipFile
from openpyxl.utils.cell import range_to_tuple
from .common import setup_inputs, checked

ID, MODE, VERSION, DIFFICULTY = "sort_and_chart", "gui", "1", "medium"
APPLICATION, FILENAME, ARTIFACT = "calc", "BoomerangSales.xlsx", True


def setup(work):
    return setup_inputs(ID, work)


def make_request(work):
    return (f"在 Calc 中将 {work / FILENAME} 的 Sheet1 按 Date Time 升序排列，"
            "保持每条记录完整，再创建以 Date Time 为横轴、Quantity 为纵轴的折线图。"
            "保留 Retail Price 表，保存工作簿。")


NS = {'s': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main',
      'c': 'http://schemas.openxmlformats.org/drawingml/2006/chart',
      'r': 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'}


def referenced_values(sheets, formula):
    name, bounds = range_to_tuple(formula.lstrip("="))
    left, top, right, bottom = bounds
    if right != left or bottom - top > 1000:
        return None
    rows = sheets[name]['rows']
    return [rows[i - 1][left - 1] for i in range(top, bottom + 1)]


def chart_sources(path):
    """Read only charts actually attached to Sheet1; ignore renderer-specific caches.

    LibreOffice 24.2 can save chart properties openpyxl 3.1 cannot deserialize.
    The OOXML drawing relationships and range references remain valid.
    """
    with ZipFile(path) as z:
        def xml(part):
            return ET.fromstring(z.read(part))

        def relationships(part):
            folder, name = posixpath.split(part)
            rels = xml(f'{folder}/_rels/{name}.rels')
            return {r.get('Id'): posixpath.normpath(posixpath.join(folder, r.get('Target'))).lstrip('/')
                    for r in rels if r.get('TargetMode') != 'External'}

        def rid(node):
            return node.get('{' + NS['r'] + '}id')

        workbook_rels = relationships('xl/workbook.xml')
        sheet = next(s for s in xml('xl/workbook.xml').findall('s:sheets/s:sheet', NS)
                     if s.get('name') == 'Sheet1')
        part = workbook_rels[rid(sheet)]
        drawings = xml(part).findall('s:drawing', NS)
        if not drawings:
            return
        sheet_rels = relationships(part)
        for drawing in drawings:
            part = sheet_rels[rid(drawing)]
            drawing_rels = relationships(part)
            for chart in xml(part).findall('.//c:chart', NS):
                root = xml(drawing_rels[rid(chart)])
                for line in root.findall('.//c:plotArea/c:lineChart', NS):
                    series = line.findall('c:ser', NS)
                    if len(series) != 1:
                        continue
                    x = series[0].find('c:cat/c:numRef/c:f', NS)
                    if x is None:
                        x = series[0].find('c:cat/c:strRef/c:f', NS)
                    y = series[0].find('c:val/c:numRef/c:f', NS)
                    if x is not None and y is not None:
                        yield x.text, y.text


def verify(work, state, answers, traces):
    from prepare_assets import HERE
    from .workbooks import read_workbook
    with warnings.catch_warnings():
        warnings.filterwarnings('ignore', message='Unable to read chart .*', category=UserWarning)
        source = read_workbook(HERE / "fixtures" / ID / FILENAME)
        actual = read_workbook(work / FILENAME)
    if not actual or set(actual) != set(source):
        return checked({"saved_workbook": False})
    rows = actual["Sheet1"]["rows"]
    original = source["Sheet1"]["rows"]
    sorted_ok = (bool(rows) and rows[0] == original[0]
                 and Counter(map(tuple, rows[1:])) == Counter(map(tuple, original[1:]))
                 and [r[0] for r in rows[1:]] == sorted(r[0] for r in original[1:]))
    chart_ok = False
    try:
        for x, y in chart_sources(work / FILENAME):
            chart_ok |= (referenced_values(actual, x) == [r[0] for r in rows[1:]]
                         and referenced_values(actual, y) == [r[4] for r in rows[1:]])
    except (ValueError, KeyError, TypeError, IndexError, ET.ParseError):
        chart_ok = False
    return checked({"records_sorted_intact": sorted_ok, "date_quantity_line_chart": chart_ok,
                    "price_table_preserved": actual["Retail Price"]["rows"] == source["Retail Price"]["rows"]})
