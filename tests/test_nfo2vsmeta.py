# -*- coding: utf-8 -*-
"""nfo-to-vsmeta 单元测试（unittest，无需第三方依赖）"""

import os
import sys
import subprocess
import tempfile
import unittest
import importlib.util

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)  # 让主脚本能 from version import __version__
_spec = importlib.util.spec_from_file_location(
    "nfo2vsmeta", os.path.join(ROOT, "nfo-to-vsmeta.1.0.py")
)
assert _spec is not None and _spec.loader is not None
n2v = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(n2v)


def make_nfo(
    title="测试电影",
    plot="简介",
    year="2000",
    rating="8.0",
    genre=None,
    actors=None,
    directors=None,
    writers=None,
    studio=None,
    tagline="",
    sorttitle="",
    cdata=False,
    encoding="utf-8",
):
    """构造测试 nfo XML 文本"""
    parts = ['<?xml version="1.0" encoding="UTF-8"?><movie>']
    parts.append(f"<title>{title}</title>")
    if sorttitle:
        parts.append(f"<sorttitle>{sorttitle}</sorttitle>")
    if tagline:
        parts.append(f"<tagline>{tagline}</tagline>")
    if cdata:
        parts.append(f"<plot><![CDATA[{plot}]]></plot>")
    else:
        parts.append(f"<plot>{plot}</plot>")
    parts.append(f"<year>{year}</year>")
    parts.append("<premiered>2000-01-01</premiered>")
    parts.append(f"<rating>{rating}</rating>")
    for g in genre or []:
        parts.append(f"<genre>{g}</genre>")
    for a in actors or []:
        parts.append(f"<actor><name>{a}</name></actor>")
    for d in directors or []:
        parts.append(f"<director>{d}</director>")
    for w in writers or []:
        parts.append(f"<writer>{w}</writer>")
    for s in studio or []:
        parts.append(f"<studio>{s}</studio>")
    parts.append("</movie>")
    xml_text = "".join(parts)
    if encoding == "gb18030":
        return xml_text.encode("gb18030")
    return xml_text.encode("utf-8")


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
        self.assertEqual(bytes(ba), b"\x80\x01")


class SeasonEpisodeTestCase(unittest.TestCase):
    def test_sxxeyy(self):
        self.assertEqual(n2v.parse_season_episode("Show.S01E02.mkv"), (1, 2))
        self.assertEqual(n2v.parse_season_episode("Show.S12E34.mp4"), (12, 34))

    def test_nx_ny(self):
        self.assertEqual(n2v.parse_season_episode("Show.1x2.mkv"), (1, 2))
        self.assertEqual(n2v.parse_season_episode("Show 3x05.avi"), (3, 5))

    def test_trailing_digits(self):
        # 尾数字解析默认关闭（避免 JAV 番号等误判），开启后仅接受两位数字
        self.assertEqual(n2v.parse_season_episode("Show.02.mkv"), (None, None))
        self.assertEqual(n2v.parse_season_episode("Show - 12.ts"), (None, None))
        self.assertEqual(n2v.parse_season_episode("Show.02.mkv", True), (1, 2))
        self.assertEqual(n2v.parse_season_episode("Show - 12.ts", True), (1, 12))

    def test_jav_fanhao_not_misparsed(self):
        # JAV 番号：默认与开启尾数字后均不应误判为剧集（3 位数字被收紧规则排除）
        for name in ["ABP-998.mkv", "STARS-061.mkv", "MIDV-904.mp4"]:
            self.assertEqual(n2v.parse_season_episode(name), (None, None), name)
            self.assertEqual(n2v.parse_season_episode(name, True), (None, None), name)
        # 电影年份/名称不应误判
        self.assertEqual(n2v.parse_season_episode("Movie.2020.mkv", True), (None, None))
        self.assertEqual(n2v.parse_season_episode("The.300.mkv", True), (None, None))

    def test_no_match(self):
        self.assertIsNone(n2v.parse_season_episode("Movie (2020).mkv")[0])
        self.assertIsNone(n2v.parse_season_episode("Movie (2020).mkv")[1])


class NfoParsingTestCase(unittest.TestCase):
    def test_full_fields(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "m.nfo")
            with open(path, "wb") as f:
                f.write(
                    make_nfo(
                        title="黑客帝国",
                        plot="简介内容",
                        genre=["科幻", "动作"],
                        actors=["演员A", "演员B"],
                        directors=["导演X"],
                        writers=["编剧Y"],
                        studio=["华纳"],
                    )
                )
            meta = n2v.parse_nfo(path)
            self.assertEqual(meta["title"], "黑客帝国")
            self.assertEqual(meta["genre"], ["科幻", "动作"])
            self.assertEqual(meta["actors"], ["演员A", "演员B"])
            self.assertEqual(meta["directors"], ["导演X"])
            self.assertEqual(meta["writers"], ["编剧Y"])
            self.assertEqual(meta["studio"], ["华纳"])
            self.assertEqual(meta["year"], "2000")

    def test_cdata_plot(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "m.nfo")
            with open(path, "wb") as f:
                f.write(make_nfo(plot="<b>带标签的简介</b> & 符号", cdata=True))
            meta = n2v.parse_nfo(path)
            self.assertEqual(meta["plot"], "<b>带标签的简介</b> & 符号")

    def test_gb18030_encoding(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "m.nfo")
            with open(path, "wb") as f:
                f.write(make_nfo(title="中文标题", encoding="gb18030"))
            meta = n2v.parse_nfo(path)
            self.assertEqual(meta["title"], "中文标题")

    def test_missing_fields_defaults(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "m.nfo")
            with open(path, "wb") as f:
                f.write(
                    '<?xml version="1.0"?><movie><title>只有标题</title></movie>'.encode("utf-8")
                )
            meta = n2v.parse_nfo(path)
            self.assertEqual(meta["title"], "只有标题")
            self.assertEqual(meta["year"], "1900")
            self.assertEqual(meta["genre"], [])


class VsmetaBuildTestCase(unittest.TestCase):
    CONFIG = {
        "compress_image": False,
        "compress_kb": 200,
        "studio_as_tagline": False,
    }

    def _build(self, meta, season=None, episode=None):
        return n2v.build_vsmeta_content(
            meta, "/nonexist-poster.jpg", "/nonexist-fanart.jpg", self.CONFIG, season, episode
        )

    def test_full_field_structure(self):
        meta = {
            "title": "黑客帝国",
            "sorttitle": "黑客帝国",
            "tagline": "标语",
            "plot": "简介",
            "year": "1999",
            "level": "R",
            "date": "1999-03-31",
            "rate": "8.7",
            "genre": ["科幻", "动作"],
            "actors": ["基努·里维斯"],
            "directors": ["沃卓斯基"],
            "writers": ["沃卓斯基"],
            "studio": [],
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
            "title": "剧集",
            "sorttitle": "",
            "tagline": "",
            "plot": "",
            "year": "2020",
            "level": "G",
            "date": "2020-01-01",
            "rate": "0",
            "genre": [],
            "actors": [],
            "directors": [],
            "writers": [],
            "studio": [],
        }
        data = bytes(self._build(meta, season=3, episode=5))
        fields = n2v.parse_vsmeta_fields(data)
        self.assertIn(n2v.TAG_GROUP2, fields)
        g2 = n2v.parse_group2(fields[n2v.TAG_GROUP2][0])
        self.assertEqual(g2[n2v.TAG2_SEASON], 3)
        self.assertEqual(g2[n2v.TAG2_EPISODE], 5)

    def test_128_byte_plot(self):
        meta = {
            "title": "边界",
            "sorttitle": "",
            "tagline": "",
            "plot": "a" * 128,
            "year": "2000",
            "level": "G",
            "date": "2000-01-01",
            "rate": "7.5",
            "genre": [],
            "actors": [],
            "directors": [],
            "writers": [],
            "studio": [],
        }
        data = bytes(self._build(meta))
        fields = n2v.parse_vsmeta_fields(data)
        # 128 字节 plot 不破坏后续字段
        self.assertEqual(fields[n2v.TAG_YEAR][0], 2000)
        self.assertEqual(fields[n2v.TAG_RATING][0], 75)

    def test_studio_as_tagline(self):
        meta = {
            "title": "电影",
            "sorttitle": "",
            "tagline": "原标语",
            "plot": "",
            "year": "2000",
            "level": "G",
            "date": "2000-01-01",
            "rate": "0",
            "genre": [],
            "actors": [],
            "directors": [],
            "writers": [],
            "studio": ["华纳", "DC"],
        }
        cfg = dict(self.CONFIG, studio_as_tagline=True)
        data = bytes(n2v.build_vsmeta_content(meta, "/nonexist.jpg", "/nonexist.jpg", cfg))
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
                    raw = data[pos : pos + length].decode("utf-8")
                pos += length
        self.assertEqual(raw, "原标语 · 华纳 / DC")


class VerifyTestCase(unittest.TestCase):
    def test_verify_pass(self):
        meta = {
            "title": "电影",
            "sorttitle": "",
            "tagline": "",
            "plot": "简介",
            "year": "2000",
            "level": "G",
            "date": "2000-01-01",
            "rate": "8.0",
            "genre": [],
            "actors": [],
            "directors": [],
            "writers": [],
            "studio": [],
        }
        cfg = {"compress_image": False, "compress_kb": 200, "studio_as_tagline": False}
        data = bytes(n2v.build_vsmeta_content(meta, "/nonexist.jpg", "/nonexist.jpg", cfg))
        ok, issues = n2v.verify_vsmeta(data, meta)
        self.assertTrue(ok, f"自检应通过: {issues}")

    def test_verify_catches_year_mismatch(self):
        meta = {
            "title": "电影",
            "sorttitle": "",
            "tagline": "",
            "plot": "简介",
            "year": "2000",
            "level": "G",
            "date": "2000-01-01",
            "rate": "8.0",
            "genre": [],
            "actors": [],
            "directors": [],
            "writers": [],
            "studio": [],
        }
        cfg = {"compress_image": False, "compress_kb": 200, "studio_as_tagline": False}
        data = bytes(n2v.build_vsmeta_content(meta, "/nonexist.jpg", "/nonexist.jpg", cfg))
        bad_meta = dict(meta, year="1999")
        ok, issues = n2v.verify_vsmeta(data, bad_meta)
        self.assertFalse(ok)
        self.assertTrue(any("年份不符" in i for i in issues))

    def test_verify_non_numeric_year(self):
        # 非数字年份不应抛异常，而是返回明确的 issue
        meta = {
            "title": "电影",
            "sorttitle": "",
            "tagline": "",
            "plot": "简介",
            "year": "2000",
            "level": "G",
            "date": "2000-01-01",
            "rate": "8.0",
            "genre": [],
            "actors": [],
            "directors": [],
            "writers": [],
            "studio": [],
        }
        cfg = {"compress_image": False, "compress_kb": 200, "studio_as_tagline": False}
        data = bytes(n2v.build_vsmeta_content(meta, "/nonexist.jpg", "/nonexist.jpg", cfg))
        ok, issues = n2v.verify_vsmeta(data, dict(meta, year="2020-05-01"))
        self.assertFalse(ok)
        self.assertTrue(any("年份格式异常" in i for i in issues))


class DryRunTestCase(unittest.TestCase):
    def test_dry_run_creates_no_file(self):
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "m.nfo"), "wb") as f:
                f.write(make_nfo())
            open(os.path.join(d, "m.mkv"), "wb").write(b"x")
            cfg = {
                "directory": d,
                "poster_suffix": "-poster.jpg",
                "fanart_suffix": "-fanart.jpg",
                "video_extensions": [".mkv"],
                "ignore_extensions": [],
                "delete_vsmeta": False,
                "max_workers": 1,
                "compress_image": False,
                "compress_kb": 200,
            }
            stats = n2v.process_files(cfg, dry_run=True)
            self.assertEqual(stats["success"], 1)
            self.assertFalse(os.path.exists(os.path.join(d, "m.mkv.vsmeta")))


class EndToEndTestCase(unittest.TestCase):
    def test_full_flow_with_verify(self):
        with tempfile.TemporaryDirectory() as d:
            # 剧集文件
            with open(os.path.join(d, "Show.S02E03.nfo"), "wb") as f:
                f.write(
                    make_nfo(
                        title="某剧",
                        plot="简介",
                        year="2021",
                        rating="9.2",
                        genre=["剧情"],
                        actors=["演员"],
                    )
                )
            open(os.path.join(d, "Show.S02E03.mkv"), "wb").write(b"x")
            cfg = {
                "directory": d,
                "poster_suffix": "-poster.jpg",
                "fanart_suffix": "-fanart.jpg",
                "video_extensions": [".mkv"],
                "ignore_extensions": [],
                "delete_vsmeta": True,
                "max_workers": 1,
                "compress_image": False,
                "compress_kb": 200,
            }
            stats = n2v.process_files(cfg, verify=True)
            self.assertEqual(stats["success"], 1)
            vsmeta = os.path.join(d, "Show.S02E03.mkv.vsmeta")
            self.assertTrue(os.path.exists(vsmeta))
            with open(vsmeta, "rb") as f:
                data = f.read()
            fields = n2v.parse_vsmeta_fields(data)
            self.assertIn(n2v.TAG_GROUP2, fields)
            g2 = n2v.parse_group2(fields[n2v.TAG_GROUP2][0])
            self.assertEqual(g2[n2v.TAG2_SEASON], 2)
            self.assertEqual(g2[n2v.TAG2_EPISODE], 3)
            # verify_vsmeta 应通过（含季/集校验）
            meta = n2v.parse_nfo(os.path.join(d, "Show.S02E03.nfo"))
            ok, issues = n2v.verify_vsmeta(data, meta, season=2, episode=3)
            self.assertTrue(ok, f"verify 应通过: {issues}")


class SeasonEpisodeMultiTestCase(unittest.TestCase):
    def test_sxxeyy_multi_takes_first(self):
        # S01E02E03（合辑）取第一集
        self.assertEqual(n2v.parse_season_episode("Show.S01E02E03.mkv"), (1, 2))

    def test_sxxeyy_multi_triple(self):
        self.assertEqual(n2v.parse_season_episode("Show.S02E05E06E07.mkv"), (2, 5))

    def test_sxxeyy_single_unchanged(self):
        self.assertEqual(n2v.parse_season_episode("Show.S01E02.mkv"), (1, 2))


class ConfigValidationTestCase(unittest.TestCase):
    def test_bad_directory_type(self):
        with self.assertRaises(ValueError):
            n2v.validate_config({"directory": 123})

    def test_empty_directory_list(self):
        with self.assertRaises(ValueError):
            n2v.validate_config({"directory": []})

    def test_bad_max_workers(self):
        with self.assertRaises(ValueError):
            n2v.validate_config({"directory": "./v", "max_workers": 0})

    def test_bad_compress_kb(self):
        with self.assertRaises(ValueError):
            n2v.validate_config({"directory": "./v", "compress_kb": "big"})

    def test_valid_config_passes(self):
        n2v.validate_config(
            {
                "directory": "./v",
                "poster_suffix": "-p.jpg",
                "fanart_suffix": "-f.jpg",
                "video_extensions": [".mkv"],
                "max_workers": 2,
                "compress_kb": 200,
            }
        )  # 不应抛异常


class StaleVsmetaTestCase(unittest.TestCase):
    def _make_env(self, d):
        with open(os.path.join(d, "m.nfo"), "wb") as f:
            f.write(make_nfo(title="电影", year="2020"))
        with open(os.path.join(d, "m.mkv"), "wb") as f:
            f.write(b"x")
        return {
            "directory": d,
            "poster_suffix": "-poster.jpg",
            "fanart_suffix": "-fanart.jpg",
            "video_extensions": [".mkv"],
            "ignore_extensions": [],
            "delete_vsmeta": False,
            "update_stale_vsmeta": True,
            "max_workers": 1,
            "compress_image": False,
            "compress_kb": 200,
        }

    def test_stale_source_reconverts(self):
        with tempfile.TemporaryDirectory() as d:
            cfg = self._make_env(d)
            stats = n2v.process_files(dict(cfg))
            self.assertEqual(stats["success"], 1)
            # nfo 更新（mtime 改为未来）→ 再次运行应重转而不是跳过
            future = os.path.getmtime(os.path.join(d, "m.nfo")) + 100
            os.utime(os.path.join(d, "m.nfo"), (future, future))
            stats = n2v.process_files(dict(cfg))
            self.assertEqual(stats["success"], 1)
            self.assertEqual(stats["skipped"], 0)

    def test_fresh_vsmeta_skips(self):
        with tempfile.TemporaryDirectory() as d:
            cfg = self._make_env(d)
            n2v.process_files(dict(cfg))
            # vsmeta 比源文件新 → 跳过
            stats = n2v.process_files(dict(cfg))
            self.assertEqual(stats["skipped"], 1)

    def test_stale_disabled_skips(self):
        with tempfile.TemporaryDirectory() as d:
            cfg = self._make_env(d)
            n2v.process_files(dict(cfg))
            future = os.path.getmtime(os.path.join(d, "m.nfo")) + 100
            os.utime(os.path.join(d, "m.nfo"), (future, future))
            cfg["update_stale_vsmeta"] = False
            stats = n2v.process_files(dict(cfg))
            self.assertEqual(stats["skipped"], 1)


class AtomicWriteTestCase(unittest.TestCase):
    def test_no_tmp_leftover_after_convert(self):
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "m.nfo"), "wb") as f:
                f.write(make_nfo())
            open(os.path.join(d, "m.mkv"), "wb").write(b"x")
            cfg = {
                "directory": d,
                "poster_suffix": "-poster.jpg",
                "fanart_suffix": "-fanart.jpg",
                "video_extensions": [".mkv"],
                "ignore_extensions": [],
                "delete_vsmeta": False,
                "max_workers": 1,
                "compress_image": False,
                "compress_kb": 200,
            }
            n2v.process_files(dict(cfg))
            vsmeta = os.path.join(d, "m.mkv.vsmeta")
            self.assertTrue(os.path.exists(vsmeta))
            # 不应残留临时文件
            leftovers = [f for f in os.listdir(d) if f.endswith(".tmp")]
            self.assertEqual(leftovers, [])
            # vsmeta 内容可解析
            with open(vsmeta, "rb") as f:
                fields = n2v.parse_vsmeta_fields(f.read())
            self.assertIn(n2v.TAG_SHOW_TITLE, fields)


class VerifyEnhancedTestCase(unittest.TestCase):
    def _meta(self, **overrides):
        meta = {
            "title": "电影",
            "sorttitle": "",
            "tagline": "",
            "plot": "简介",
            "year": "2000",
            "level": "R",
            "date": "2000-01-01",
            "rate": "8.0",
            "genre": ["科幻"],
            "actors": ["演员A", "演员B"],
            "directors": [],
            "writers": [],
            "studio": [],
        }
        meta.update(overrides)
        return meta

    def _build(self, meta):
        cfg = {"compress_image": False, "compress_kb": 200, "studio_as_tagline": False}
        return bytes(n2v.build_vsmeta_content(meta, "/nonexist.jpg", "/nonexist.jpg", cfg))

    def test_verify_checks_date_level_actors_pass(self):
        meta = self._meta()
        ok, issues = n2v.verify_vsmeta(self._build(meta), meta)
        self.assertTrue(ok, f"完整元数据自检应通过: {issues}")

    def test_verify_catches_date_mismatch(self):
        meta = self._meta()
        bad = dict(meta, date="1999-12-31")
        ok, issues = n2v.verify_vsmeta(self._build(meta), bad)
        self.assertFalse(ok)
        self.assertTrue(any("日期不符" in i for i in issues))

    def test_verify_catches_level_mismatch(self):
        meta = self._meta()
        bad = dict(meta, level="PG-13")
        ok, issues = n2v.verify_vsmeta(self._build(meta), bad)
        self.assertFalse(ok)
        self.assertTrue(any("分级不符" in i for i in issues))

    def test_verify_catches_actor_count_mismatch(self):
        meta = self._meta()
        bad = dict(meta, actors=["演员A", "演员B", "演员C"])
        ok, issues = n2v.verify_vsmeta(self._build(meta), bad)
        self.assertFalse(ok)
        self.assertTrue(any("演员数量不符" in i for i in issues))

    def test_verify_skips_actor_check_when_empty(self):
        # nfo 无演员时不校验演员数量（避免误报）
        meta = self._meta(actors=[])
        ok, issues = n2v.verify_vsmeta(self._build(meta), meta)
        self.assertTrue(ok, f"无演员场景应通过: {issues}")


class ExitCodeTestCase(unittest.TestCase):
    def _run(self, d, args):
        return subprocess.run(
            [sys.executable, os.path.join(ROOT, "nfo-to-vsmeta.1.0.py")] + args,
            cwd=d,
            capture_output=True,
            text=True,
            timeout=60,
        )

    def test_success_exit_zero(self):
        with tempfile.TemporaryDirectory() as d:
            r = self._run(d, ["--dry-run", "--directory", "/nonexistent"])
            self.assertEqual(r.returncode, 0, r.stderr[-500:])

    def test_failure_exit_one(self):
        with tempfile.TemporaryDirectory() as d:
            # 坏 nfo（非 XML）→ 处理失败 → 退出码 1
            with open(os.path.join(d, "m.nfo"), "wb") as f:
                f.write(b"<not-xml")
            with open(os.path.join(d, "m.mkv"), "wb") as f:
                f.write(b"x")
            r = self._run(d, ["--directory", d])
            self.assertEqual(r.returncode, 1, r.stderr[-500:])

    def test_version_exit_zero(self):
        with tempfile.TemporaryDirectory() as d:
            r = self._run(d, ["--version"])
            self.assertEqual(r.returncode, 0)
            self.assertIn("nfo-to-vsmeta", r.stdout)


if __name__ == "__main__":
    unittest.main()
