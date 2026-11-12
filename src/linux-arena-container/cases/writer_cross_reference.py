"""Verify the saved bibliography entry and its numbered REF field."""
import re
from xml.etree import ElementTree as ET
from zipfile import ZipFile, BadZipFile
from .common import setup_inputs, checked

ID, MODE, VERSION, DIFFICULTY = "writer_cross_reference", "gui", "1", "medium"
APPLICATION, FILENAME, ARTIFACT = "writer", "Essay_Writing_English_for_uni.docx", True
REFERENCE = ('Steinberg, F. M., Bearden, M. M., & Keen, C. L. (2003). Cocoa and chocolate '
             'flavonoids: Implications for cardiovascular health. Journal of the American '
             'Dietetic Association, 103(2), 215-223. doi: 10.1053/jada.2003.50028')
W = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'


def normalize(text):
    return ' '.join(text.split())


def paragraphs(path):
    with ZipFile(path) as archive:
        root = ET.fromstring(archive.read('word/document.xml'))
    result = []
    for para in root.findall(f'.//{W}body/{W}p'):
        text = ''.join(n.text or '' for n in para.iter(W + 't'))
        if not text.strip():
            continue
        bookmarks = [n.get(W + 'name') for n in para.iter(W + 'bookmarkStart')]
        fields, stack = [], []
        for node in para.iter():
            if node.tag == W + 'fldSimple':
                fields.append((node.get(W + 'instr', ''), ''.join(n.text or '' for n in node.iter(W + 't'))))
            elif node.tag == W + 'fldChar':
                kind = node.get(W + 'fldCharType')
                if kind == 'begin':
                    stack.append(['', '', False])
                elif kind == 'separate' and stack:
                    stack[-1][2] = True
                elif kind == 'end' and stack:
                    field = stack.pop()
                    fields.append(tuple(field[:2]))
            elif stack and node.tag == W + 'instrText' and not stack[-1][2]:
                stack[-1][0] += node.text or ''
            elif stack and node.tag == W + 't' and stack[-1][2]:
                stack[-1][1] += node.text or ''
        result.append({'text': normalize(text), 'bookmarks': bookmarks, 'fields': fields})
    return result


def setup(work):
    return setup_inputs(ID, work)


def make_request(work):
    return (f'在 Writer 中编辑 {work / FILENAME}：将以下文献追加到 References 的编号列表，'
            f'并在正文的 <add here> 位置插入指向它的文献编号交叉引用：{REFERENCE}。'
            '保留其余正文和已有文献，并保存。')


def verify(work, state, answers, traces):
    from prepare_assets import HERE
    try:
        original = paragraphs(HERE / 'fixtures' / ID / FILENAME)
        actual = paragraphs(work / FILENAME)
    except (OSError, BadZipFile, ET.ParseError, KeyError):
        return checked({'saved_document': False})
    entries = [p for p in actual if p['text'] == normalize(REFERENCE)]
    target_names = set(entries[0]['bookmarks']) if len(entries) == 1 else set()
    bibliography_start = next(i for i, p in enumerate(original) if p['text'] == 'References')
    reference_number = str(len(original) - bibliography_start)
    pos = next(i for i, p in enumerate(original) if '<add here>' in p['text'])
    field_ok, replacement = False, ''
    if pos < len(actual):
        for instruction, visible in actual[pos]['fields']:
            match = re.search(r'\bREF\s+"?([^"\s]+)', instruction, re.I)
            if (match and match[1] in target_names and re.search(r'\\[rnw]\b', instruction)
                    and visible.strip().strip('[]') == reference_number):
                field_ok, replacement = True, visible
    expected = [p['text'] for p in original]
    expected[pos] = normalize(expected[pos].replace('<add here>', replacement))
    expected.append(normalize(REFERENCE))
    return checked({'bibliography_added_once': len(entries) == 1,
                    'numbered_reference_targets_new_entry': field_ok,
                    'body_and_existing_references_preserved': [p['text'] for p in actual] == expected})
