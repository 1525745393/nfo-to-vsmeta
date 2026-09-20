# -*- coding: utf-8 -*-
"""nfo-to-vsmeta 单元测试（unittest，无需第三方依赖）"""
import io
import os
import sys
import shutil
import tempfile
import unittest
import importlib.util

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_spec = importlib.util.spec_from_file_location('nfo2vsmeta', os.path.join(ROOT, 'nfo-to-vsmeta.1.0.py'))
n2v = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(n2v)


def make_nfo(title='测试电影', plot='简介', year='2000', rating='8.0', genre=None,
             actors=None, directors=None, writers=None, studio=None,
             tagline='', sorttitle='', cdata=False, encoding='utf-8'):
    """构造测试 nfo XML 文本"""
    parts = ['<?xml version="1.0" encoding="UTF-8"?><movie>']
    parts.append(f'<title>{title}</title>')
    if sorttitle:
        parts.append(f'<sorttitle>{sorttitle}</sorttitle>')
    if tagline:
        parts.append(f'<tagline>{tagline}</tagline>')
    if cdata:
        parts.append(f'<plot><![CDATA[{plot}]]></plot>')
    else:
        parts.append(f'<plot>{plot}</plot>')
    parts.append(f'<year>{year}</year>')
    parts.append(f'<premiered>2000-01-01</premiered>')
    parts.append(f'<rating>{rating}</rating>')
    for g in (genre or []):
        parts.append(f'<genre>{g}</genre>')
    for a in (actors or []):
        parts.append(f'<actor><name>{a}</name></actor>')
    for d in (directors or []):
        parts.append(f'<director>{d}</director>')
    for w in (writers or []):
        parts.append(f'<writer>{w}</writer>')
    for s in (studio or []):
        parts.append(f'<studio>{s}</studio>')
    parts.append('</movie>')
    xml_text = ''.join(parts)
    if encoding == 'gb18030':
        return xml_text.encode('gb18030')
    return xml_text.encode('utf-8')


class VarintTestCase(unittest.TestCase):
    def test_boundaries(self):
        cases = [0, 1, 127, 128, 129, 255, 256, 257, 16383, 16384, 300000]
        for n in cases:
            ba = bytearray()
            n2v.write_int(ba, n)
            val, pos = n2v.read_varint(bytes(ba), 0)
            self.assertEqual(val, n, f"编码/解码不一致: {n}")
            self.assertEqual(pos, len(ba), f"消耗字节数不一致: {n}")

    def test_128_not_single_byte(self):
        ba = bytearray()
        n2v.write_int(ba, 128)
        # 128 的 varint 必须是两字节 [0x80, 0x01]
        self.assertEqual(bytes(ba), b'\x80\x01')


class SeasonEpisodeTestCase(unittest.TestCase):
    def test_sxxeyy(self):
        self.assertEqual(n2v.parse_season_episode("Show.S01E02.mkv"), (1, 2))
        self.assertEqual(n2v.parse_season_episode("Show.S12E34.mp4"), (12, 34))

    def test_nx_ny(self):
        self.assertEqual(n2v.parse_season_episode("Show.1x2.mkv"), (1, 2))
        self.assertEqual(n2v.parse_season_episode("Show 3x05.avi"), (3, 5))

    def test_trailing_digits(self):
        self.assertEqual(n2v.parse_season_episode("Show.02.mkv"), (1, 2))
        self.assertEqual(n2v.parse_season_episode("Show - 12.ts"), (1, 12))

    def test_no_match(self):
        self.assertIsNone(n2v.parse_season_episode("Movie (2020).mkv")[0])
        self.assertIsNone(n2v.parse_season_episode("Movie (2020).mkv")[1])


class NfoParsingTestCase(unittest.TestCase):
    def test_full_fields(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, 'm.nfo')
            with open(path, 'wb') as f:
                f.write(make_nfo(title='黑客帝国', plot='简介内容', genre=['科幻', '动作'],
                                 actors=['演员A', '演员B'], directors=['导演X'],
                                 writers=['编剧Y'], studio=['华纳']))
            meta = n2v.parse_nfo(path)
            self.assertEqual(meta['title'], '黑客帝国')
            self.assertEqual(meta['genre'], ['科幻', '动作'])
            self.assertEqual(meta['actors'], ['演员A', '演员B'])
            self.assertEqual(meta['directors'], ['导演X'])
            self.assertEqual(meta['writers'], ['编剧Y'])
            self.assertEqual(meta['studio'], ['华纳'])
            self.assertEqual(meta['year'], '2000')

    def test_cdata_plot(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, 'm.nfo')
            with open(path, 'wb') as f:
                f.write(make_nfo(plot='<b>带标签的简介</b> & 符号', cdata=True))
            meta = n2v.parse_nfo(path)
            self.assertEqual(meta['plot'], '<b>带标签的简介</b> & 符号')

    def test_gb18030_encoding(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, 'm.nfo')
            with open(path, 'wb') as f:
                f.write(make_nfo(title='中文标题', encoding='gb18030'))
            meta = n2v.parse_nfo(path)
            self.assertEqual(meta['title'], '中文标题')

    def test_missing_fields_defaults(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, 'm.nfo')
            with open(path, 'wb') as f:
                f.write('<?xml version="1.0"?><movie><title>只有标题</title></movie>'.encode('utf-8'))
            meta = n2v.parse_nfo(path)
            self.assertEqual(meta['title'], '只有标题')
            self.assertEqual(meta['year'], '1900')
            self.assertEqual(meta['genre'], [])


class VsmetaBuildTestCase(unittest.TestCase):
    CONFIG = {
        'compress_image': False, 'compress_kb': 200, 'studio_as_tagline': False,
    }

    def _build(self, meta, season=None, episode=None):
        return n2v.build_vsmeta_content(meta, '/nonexist-poster.jpg', '/nonexist-fanart.jpg',
                                        self.CONFIG, season, episode)

    def test_full_field_structure(self):
        meta = {
            'title': '黑客帝国', 'sorttitle': '黑客帝国', 'tagline': '标语', 'plot': '简介',
            'year': '1999', 'level': 'R', 'date': '1999-03-31', 'rate': '8.7',
            'genre': ['科幻', '动作'], 'actors': ['基努·里维斯'], 'directors': ['沃卓斯基'],
            'writers': ['沃卓斯基'], 'studio': [],
        }
        data = bytes(self._build(meta))
        fields = n2v.parse_vsmeta_fields(data)
        self.assertIn(n2v.TAG_SHOW_TITLE, fields)
        self.assertEqual(fields[n2v.TAG_YEAR][0], 1999)
        self.assertEqual(fields[n2v.TAG_RATING][0], 87)
        self.assertIn(n2v.TAG_GROUP1, fields)
        # 电影文件不应写入季/集分组
        self.assertNotIn(n2v.TAG_GROUP2, fields)

    def test_season_episode_group(self):
        meta = {
            'title': '剧集', 'sorttitle': '', 'tagline': '', 'plot': '', 'year': '2020',
            'level': 'G', 'date': '2020-01-01', 'rate': '0', 'genre': [], 'actors': [],
            'directors': [], 'writers': [], 'studio': [],
        }
        data = bytes(self._build(meta, season=3, episode=5))
        fields = n2v.parse_vsmeta_fields(data)
        self.assertIn(n2v.TAG_GROUP2, fields)
        g2 = n2v.parse_group2(fields[n2v.TAG_GROUP2][0])
        self.assertEqual(g2[n2v.TAG2_SEASON], 3)
        self.assertEqual(g2[n2v.TAG2_EPISODE], 5)

    def test_128_byte_plot(self):
        meta = {
            'title': '边界', 'sorttitle': '', 'tagline': '', 'plot': 'a' * 128, 'year': '2000',
            'level': 'G', 'date': '2000-01-01', 'rate': '7.5', 'genre': [], 'actors': [],
            'directors': [], 'writers': [], 'studio': [],
        }
        data = bytes(self._build(meta))
        fields = n2v.parse_vsmeta_fields(data)
        # 128 字节 plot 不破坏后续字段
        self.assertEqual(fields[n2v.TAG_YEAR][0], 2000)
        self.assertEqual(fields[n2v.TAG_RATING][0], 75)

    def test_studio_as_tagline(self):
        meta = {
            'title': '电影', 'sorttitle': '', 'tagline': '原标语', 'plot': '', 'year': '2000',
            'level': 'G', 'date': '2000-01-01', 'rate': '0', 'genre': [], 'actors': [],
            'directors': [], 'writers': [], 'studio': ['华纳', 'DC'],
        }
        cfg = dict(self.CONFIG, studio_as_tagline=True)
        data = bytes(n2v.build_vsmeta_content(meta, '/nonexist.jpg', '/nonexist.jpg', cfg))
        fields = n2v.parse_vsmeta_fields(data)
        # 提取 EPISODE_TITLE 文本校验
        raw = None
        pos = 0
        while pos < len(data):
            tag, pos = n2v.read_varint(data, pos)
            if tag in n2v.INT_TAGS:
                _, pos = n2v.read_varint(data, pos)
            elif tag in n2v.GROUP_TAGS:
                length, pos = n2v.read_varint(data, pos)
                pos += length
            else:
                length, pos = n2v.read_varint(data, pos)
                if tag == n2v.TAG_EPISODE_TITLE:
                    raw = data[pos:pos + length].decode('utf-8')
                pos += length
        self.assertEqual(raw, '原标语 · 华纳 / DC')


class VerifyTestCase(unittest.TestCase):
    def test_verify_pass(self):
        meta = {
            'title': '电影', 'sorttitle': '', 'tagline': '', 'plot': '简介', 'year': '2000',
            'level': 'G', 'date': '2000-01-01', 'rate': '8.0', 'genre': [], 'actors': [],
            'directors': [], 'writers': [], 'studio': [],
        }
        cfg = {'compress_image': False, 'compress_kb': 200, 'studio_as_tagline': False}
        data = bytes(n2v.build_vsmeta_content(meta, '/nonexist.jpg', '/nonexist.jpg', cfg))
        ok, issues = n2v.verify_vsmeta(data, meta)
        self.assertTrue(ok, f"自检应通过: {issues}")

    def test_verify_catches_year_mismatch(self):
        meta = {
            'title': '电影', 'sorttitle': '', 'tagline': '', 'plot': '简介', 'year': '2000',
            'level': 'G', 'date': '2000-01-01', 'rate': '8.0', 'genre': [], 'actors': [],
            'directors': [], 'writers': [], 'studio': [],
        }
        cfg = {'compress_image': False, 'compress_kb': 200, 'studio_as_tagline': False}
        data = bytes(n2v.build_vsmeta_content(meta, '/nonexist.jpg', '/nonexist.jpg', cfg))
        bad_meta = dict(meta, year='1999')
        ok, issues = n2v.verify_vsmeta(data, bad_meta)
        self.assertFalse(ok)
        self.assertTrue(any('年份不符' in i for i in issues))


class DryRunTestCase(unittest.TestCase):
    def test_dry_run_creates_no_file(self):
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, 'm.nfo'), 'wb') as f:
                f.write(make_nfo())
            open(os.path.join(d, 'm.mkv'), 'wb').write(b'x')
            cfg = {
                'directory': d, 'poster_suffix': '-poster.jpg', 'fanart_suffix': '-fanart.jpg',
                'video_extensions': ['.mkv'], 'ignore_extensions': [], 'delete_vsmeta': False,
                'max_workers': 1, 'compress_image': False, 'compress_kb': 200,
            }
            stats = n2v.process_files(cfg, dry_run=True)
            self.assertEqual(stats['success'], 1)
            self.assertFalse(os.path.exists(os.path.join(d, 'm.mkv.vsmeta')))


class EndToEndTestCase(unittest.TestCase):
    def test_full_flow_with_verify(self):
        with tempfile.TemporaryDirectory() as d:
            # 剧集文件
            with open(os.path.join(d, 'Show.S02E03.nfo'), 'wb') as f:
                f.write(make_nfo(title='某剧', plot='简介', year='2021', rating='9.2',
                                 genre=['剧情'], actors=['演员']))
            open(os.path.join(d, 'Show.S02E03.mkv'), 'wb').write(b'x')
            cfg = {
                'directory': d, 'poster_suffix': '-poster.jpg', 'fanart_suffix': '-fanart.jpg',
                'video_extensions': ['.mkv'], 'ignore_extensions': [], 'delete_vsmeta': True,
                'max_workers': 1, 'compress_image': False, 'compress_kb': 200,
            }
            stats = n2v.process_files(cfg, verify=True)
            self.assertEqual(stats['success'], 1)
            vsmeta = os.path.join(d, 'Show.S02E03.mkv.vsmeta')
            self.assertTrue(os.path.exists(vsmeta))
            with open(vsmeta, 'rb') as f:
                data = f.read()
            fields = n2v.parse_vsmeta_fields(data)
            self.assertIn(n2v.TAG_GROUP2, fields)
            g2 = n2v.parse_group2(fields[n2v.TAG_GROUP2][0])
            self.assertEqual(g2[n2v.TAG2_SEASON], 2)
            self.assertEqual(g2[n2v.TAG2_EPISODE], 3)
            # verify_vsmeta 应通过（含季/集校验）
            meta = n2v.parse_nfo(os.path.join(d, 'Show.S02E03.nfo'))
            ok, issues = n2v.verify_vsmeta(data, meta, season=2, episode=3)
            self.assertTrue(ok, f"verify 应通过: {issues}")


if __name__ == '__main__':
    unittest.main()
