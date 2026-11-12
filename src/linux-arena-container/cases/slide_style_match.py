"""Compare visible text formatting and geometry in this fixed ODP deck."""
import hashlib
import re
from xml.etree import ElementTree as ET
from zipfile import ZipFile, BadZipFile
from .common import setup_inputs, checked
from prepare_assets import HERE

ID, MODE, VERSION, DIFFICULTY = "slide_style_match", "gui", "1", "hard"
APPLICATION, FILENAME, ARTIFACT = "impress", "Project_Update.odp", True
NS = {k: 'urn:oasis:names:tc:opendocument:xmlns:' + v + ':1.0' for k, v in
      [('office', 'office'), ('style', 'style'), ('draw', 'drawing'), ('text', 'text'),
       ('svg', 'svg-compatible'), ('fo', 'xsl-fo-compatible')]}
NS['xlink'] = 'http://www.w3.org/1999/xlink'


def attr(node, key, default=None):
    prefix, local = key.split(':')
    return node.get('{' + NS[prefix] + '}' + local, default)


def length(value):
    match = re.fullmatch(r'(-?[\d.]+)(cm|mm|in|pt|pc)', value)
    if not match:
        raise ValueError(f'Unsupported length: {value}')
    return float(match[1]) * {'cm': 10, 'mm': 1, 'in': 25.4, 'pt': 25.4 / 72, 'pc': 25.4 / 6}[match[2]]


def slides(path):
    with ZipFile(path) as archive:
        roots = [ET.fromstring(archive.read(n)) for n in ('styles.xml', 'content.xml')]
        styles, defaults, fonts = {}, {}, {}
        for root in roots:
            for node in root.findall('.//style:font-face', NS):
                fonts[attr(node, 'style:name')] = attr(node, 'svg:font-family', '').strip("'")
            for node in root.findall('.//style:default-style', NS):
                defaults[attr(node, 'style:family')] = node
            for node in root.findall('.//style:style', NS):
                styles[(attr(node, 'style:family'), attr(node, 'style:name'))] = node

        def properties(family, name, seen=()):
            if name in seen:
                raise ValueError('Cyclic ODP style')
            node = styles.get((family, name))
            if node is None:
                node = defaults.get(family)
            result = {}
            if node is not None:
                parent = attr(node, 'style:parent-style-name')
                if parent:
                    result.update(properties(family, parent, (*seen, name)))
                for child in node:
                    result.update(child.attrib)
            return result

        def visible_style(props):
            def get(key, default):
                prefix, local = key.split(':')
                return props.get('{' + NS[prefix] + '}' + local, default)
            font = get('style:font-name', get('fo:font-family', 'Liberation Sans'))
            return [fonts.get(font, font).strip("'"), round(length(get('fo:font-size', '18pt')), 3),
                    get('fo:color', '#000000').lower(), get('fo:font-weight', 'normal'),
                    get('fo:font-style', 'normal')]

        output = []
        for page in roots[1].findall('.//draw:page', NS):
            frames = []
            for frame in page.findall('draw:frame', NS):
                box = [length(attr(frame, 'svg:' + k, '0mm')) for k in ('x', 'y', 'width', 'height')]
                texts, aligns = [], []
                base = properties('graphic', attr(frame, 'draw:style-name'))

                def append_text(text, props):
                    if not text:
                        return
                    style = visible_style(props)
                    if texts and texts[-1][1] == style:
                        texts[-1][0] += text
                    else:
                        texts.append([text, style])

                def walk(node, props):
                    local = dict(props)
                    if node.tag == '{' + NS['text'] + '}span':
                        local.update(properties('text', attr(node, 'text:style-name')))
                    if node.tag == '{' + NS['text'] + '}s':
                        append_text(' ' * int(attr(node, 'text:c', '1')), local)
                    elif node.tag == '{' + NS['text'] + '}line-break':
                        append_text('\n', local)
                    else:
                        append_text(node.text, local)
                        for child in node:
                            walk(child, local)
                            append_text(child.tail, local)

                paragraphs = frame.findall('.//text:p', NS) + frame.findall('.//text:h', NS)
                for i, para in enumerate(paragraphs):
                    props = {**base, **properties('paragraph', attr(para, 'text:style-name'))}
                    if ''.join(para.itertext()).strip():
                        alignment = props.get('{' + NS['fo'] + '}text-align', 'start')
                        aligns.append({'left': 'start', 'right': 'end'}.get(alignment, alignment))
                    if i:
                        append_text('\n', props)
                    walk(para, props)
                picture = frame.find('draw:image', NS)
                image_hash = None
                if picture is not None:
                    image_hash = hashlib.sha256(archive.read(attr(picture, 'xlink:href').removeprefix('./'))).hexdigest()
                # Saving in Impress can move styles into spans, including a different
                # style on invisible paragraph separators. Compare visible characters.
                characters = [[char, style if not char.isspace() else None]
                              for text, style in texts for char in text]
                frames.append({'box': box, 'text': characters, 'alignment': aligns, 'image': image_hash})
            output.append(frames)
        return output


def equivalent(actual, expected):
    if len(actual) != len(expected):
        return False
    # Match by text/image content so harmless drawing-order changes are accepted.
    remaining = list(actual)
    for target in expected:
        match = next((item for item in remaining if
                      item['text'] == target['text'] and item['alignment'] == target['alignment']
                      and item['image'] == target['image']
                      and all(abs(a - b) <= 1 for a, b in zip(item['box'], target['box']))), None)
        if match is None:
            return False
        remaining.remove(match)
    return True


def setup(work):
    return setup_inputs(ID, work)


def make_request(work):
    return (f'在 Impress 中编辑 {work / FILENAME}。前四页是已定稿的参考页，'
            '后六页刚加入，包含章节页和内容页。请参照前四页中相应类型的页面，'
            '统一后六页的字体、字号、文字颜色、对齐方式和文本框位置及大小。'
            '保留前四页，所有页面的文字、图片和页序均不变，并保存。')


def verify(work, state, answers, traces):
    try:
        actual = slides(work / FILENAME)
        expected = slides(HERE / 'references' / ID / FILENAME)
    except (OSError, BadZipFile, ET.ParseError, KeyError, ValueError):
        return checked({'saved_presentation': False})
    if len(actual) != len(expected):
        return checked({'all_ten_slides_present': False})
    return checked({'reference_slides_preserved': all(equivalent(a, b) for a, b in zip(actual[:4], expected[:4])),
                    'six_slides_match_reference_style_and_content': all(equivalent(a, b) for a, b in zip(actual[4:], expected[4:]))})
