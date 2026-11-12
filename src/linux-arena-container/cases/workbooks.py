"""Read saved XLSX values and zoom; never calculate or save an agent's workbook."""
from xml.etree.ElementTree import ParseError
from zipfile import BadZipFile


def read_workbook(path):
    from openpyxl import load_workbook
    from openpyxl.utils.exceptions import InvalidFileException

    try:
        book = load_workbook(path, data_only=True)
        try:
            sheets = {}
            for sheet in book:
                rows = [list(row) for row in sheet.values]
                for row in rows:
                    while row and row[-1] is None:
                        row.pop()
                while rows and not rows[-1]:
                    rows.pop()
                sheets[sheet.title] = {"rows": rows, "zoom": sheet.sheet_view.zoomScale or 100}
            return sheets
        finally:
            book.close()
    except (OSError, BadZipFile, InvalidFileException, ParseError, KeyError, ValueError):
        return None
