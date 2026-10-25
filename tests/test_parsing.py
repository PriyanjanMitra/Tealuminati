import unittest
from datetime import datetime

from tealuminati.services.nations_api import parse_nations, parse_wa_nations
from tealuminati.services.rmb_api import parse_posts


class ParseNationsTests(unittest.TestCase):
    def test_comma_separated(self):
        xml = b"<REGION><NATIONS>a,b , c</NATIONS></REGION>"
        self.assertEqual(parse_nations(xml), {"a", "b", "c"})

    def test_colon_legacy(self):
        xml = b"<REGION><NATIONS>a:b</NATIONS></REGION>"
        self.assertEqual(parse_nations(xml), {"a", "b"})

    def test_single(self):
        xml = b"<REGION><NATIONS>solo</NATIONS></REGION>"
        self.assertEqual(parse_nations(xml), {"solo"})

    def test_empty(self):
        self.assertEqual(parse_nations(b"<REGION><NATIONS></NATIONS></REGION>"), set())
        self.assertEqual(parse_nations(b"<REGION></REGION>"), set())


class ParseWaNationsTests(unittest.TestCase):
    def test_wa_comma_separated(self):
        xml = b"<REGION><WANATIONS>wa1, wa2 , wa3</WANATIONS></REGION>"
        self.assertEqual(parse_wa_nations(xml), {"wa1", "wa2", "wa3"})

    def test_wa_empty(self):
        self.assertEqual(parse_wa_nations(b"<REGION><WANATIONS></WANATIONS></REGION>"), set())
        self.assertEqual(parse_wa_nations(b"<REGION></REGION>"), set())


class ParsePostsTests(unittest.TestCase):
    XML = (
        b"<REGION><MESSAGES>"
        b'<POST id="10"><NATION>nsnation</NATION><TIMESTAMP>1700000000</TIMESTAMP>'
        b"<MESSAGE>hello world</MESSAGE><LIKES>4</LIKES></POST>"
        b'<POST id="11"><NATION>n2</NATION><TIMESTAMP>1700000100</TIMESTAMP></POST>'
        b"</MESSAGES></REGION>"
    )

    def test_parse(self):
        posts = parse_posts(self.XML)
        self.assertEqual(len(posts), 2)
        first = posts[0]
        self.assertEqual(first.post_id, 10)
        self.assertEqual(first.nation, "nsnation")
        self.assertEqual(first.message, "hello world")
        self.assertEqual(first.likes, 4)
        self.assertIsInstance(first.timestamp, datetime)
        second = posts[1]
        self.assertEqual(second.post_id, 11)
        self.assertEqual(second.message, "")
        self.assertEqual(second.likes, 0)

    def test_no_messages(self):
        self.assertEqual(parse_posts(b"<REGION></REGION>"), [])


if __name__ == "__main__":
    unittest.main()
