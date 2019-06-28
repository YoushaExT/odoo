# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import datetime
from dateutil.relativedelta import relativedelta
import pytz
import unittest

from odoo.tools import misc, date_utils
from odoo.tests.common import TransactionCase, tagged


@tagged('standard', 'at_install')
class TestCountingStream(unittest.TestCase):
    def test_empty_stream(self):
        s = misc.CountingStream(iter([]))
        self.assertEqual(s.index, -1)
        self.assertIsNone(next(s, None))
        self.assertEqual(s.index, 0)

    def test_single(self):
        s = misc.CountingStream(range(1))
        self.assertEqual(s.index, -1)
        self.assertEqual(next(s, None), 0)
        self.assertIsNone(next(s, None))
        self.assertEqual(s.index, 1)

    def test_full(self):
        s = misc.CountingStream(range(42))
        for _ in s:
            pass
        self.assertEqual(s.index, 42)

    def test_repeated(self):
        """ Once the CountingStream has stopped iterating, the index should not
        increase anymore (the internal state should not be allowed to change)
        """
        s = misc.CountingStream(iter([]))
        self.assertIsNone(next(s, None))
        self.assertEqual(s.index, 0)
        self.assertIsNone(next(s, None))
        self.assertEqual(s.index, 0)


@tagged('standard', 'at_install')
class TestDateRangeFunction(unittest.TestCase):
    """ Test on date_range generator. """

    def test_date_range_with_naive_datetimes(self):
        """ Check date_range with naive datetimes. """
        start = datetime.datetime(1985, 1, 1)
        end = datetime.datetime(1986, 1, 1)

        expected = [
            datetime.datetime(1985, 1, 1, 0, 0),
            datetime.datetime(1985, 2, 1, 0, 0),
            datetime.datetime(1985, 3, 1, 0, 0),
            datetime.datetime(1985, 4, 1, 0, 0),
            datetime.datetime(1985, 5, 1, 0, 0),
            datetime.datetime(1985, 6, 1, 0, 0),
            datetime.datetime(1985, 7, 1, 0, 0),
            datetime.datetime(1985, 8, 1, 0, 0),
            datetime.datetime(1985, 9, 1, 0, 0),
            datetime.datetime(1985, 10, 1, 0, 0),
            datetime.datetime(1985, 11, 1, 0, 0),
            datetime.datetime(1985, 12, 1, 0, 0),
            datetime.datetime(1986, 1, 1, 0, 0)
        ]

        dates = [date for date in date_utils.date_range(start, end)]

        self.assertEqual(dates, expected)

    def test_date_range_with_timezone_aware_datetimes_other_than_utc(self):
        """ Check date_range with timezone-aware datetimes other than UTC."""
        timezone = pytz.timezone('Europe/Brussels')

        start = datetime.datetime(1985, 1, 1)
        end = datetime.datetime(1986, 1, 1)
        start = timezone.localize(start)
        end = timezone.localize(end)

        expected = [datetime.datetime(1985, 1, 1, 0, 0),
                    datetime.datetime(1985, 2, 1, 0, 0),
                    datetime.datetime(1985, 3, 1, 0, 0),
                    datetime.datetime(1985, 4, 1, 0, 0),
                    datetime.datetime(1985, 5, 1, 0, 0),
                    datetime.datetime(1985, 6, 1, 0, 0),
                    datetime.datetime(1985, 7, 1, 0, 0),
                    datetime.datetime(1985, 8, 1, 0, 0),
                    datetime.datetime(1985, 9, 1, 0, 0),
                    datetime.datetime(1985, 10, 1, 0, 0),
                    datetime.datetime(1985, 11, 1, 0, 0),
                    datetime.datetime(1985, 12, 1, 0, 0),
                    datetime.datetime(1986, 1, 1, 0, 0)]

        expected = [timezone.localize(e) for e in expected]

        dates = [date for date in date_utils.date_range(start, end)]

        self.assertEqual(expected, dates)

    def test_date_range_with_mismatching_zones(self):
        """ Check date_range with mismatching zone should raise an exception."""
        start_timezone = pytz.timezone('Europe/Brussels')
        end_timezone = pytz.timezone('America/Recife')

        start = datetime.datetime(1985, 1, 1)
        end = datetime.datetime(1986, 1, 1)
        start = start_timezone.localize(start)
        end = end_timezone.localize(end)

        with self.assertRaises(ValueError):
            dates = [date for date in date_utils.date_range(start, end)]

    def test_date_range_with_inconsistent_datetimes(self):
        """ Check date_range with a timezone-aware datetime and a naive one."""
        context_timezone = pytz.timezone('Europe/Brussels')

        start = datetime.datetime(1985, 1, 1)
        end = datetime.datetime(1986, 1, 1)
        end = context_timezone.localize(end)

        with self.assertRaises(ValueError):
            dates = [date for date in date_utils.date_range(start, end)]

    def test_date_range_with_hour(self):
        """ Test date range with hour and naive datetime."""
        start = datetime.datetime(2018, 3, 25)
        end = datetime.datetime(2018, 3, 26)
        step = relativedelta(hours=1)

        expected = [
            datetime.datetime(2018, 3, 25, 0, 0),
            datetime.datetime(2018, 3, 25, 1, 0),
            datetime.datetime(2018, 3, 25, 2, 0),
            datetime.datetime(2018, 3, 25, 3, 0),
            datetime.datetime(2018, 3, 25, 4, 0),
            datetime.datetime(2018, 3, 25, 5, 0),
            datetime.datetime(2018, 3, 25, 6, 0),
            datetime.datetime(2018, 3, 25, 7, 0),
            datetime.datetime(2018, 3, 25, 8, 0),
            datetime.datetime(2018, 3, 25, 9, 0),
            datetime.datetime(2018, 3, 25, 10, 0),
            datetime.datetime(2018, 3, 25, 11, 0),
            datetime.datetime(2018, 3, 25, 12, 0),
            datetime.datetime(2018, 3, 25, 13, 0),
            datetime.datetime(2018, 3, 25, 14, 0),
            datetime.datetime(2018, 3, 25, 15, 0),
            datetime.datetime(2018, 3, 25, 16, 0),
            datetime.datetime(2018, 3, 25, 17, 0),
            datetime.datetime(2018, 3, 25, 18, 0),
            datetime.datetime(2018, 3, 25, 19, 0),
            datetime.datetime(2018, 3, 25, 20, 0),
            datetime.datetime(2018, 3, 25, 21, 0),
            datetime.datetime(2018, 3, 25, 22, 0),
            datetime.datetime(2018, 3, 25, 23, 0),
            datetime.datetime(2018, 3, 26, 0, 0)
        ]

        dates = [date for date in date_utils.date_range(start, end, step)]

        self.assertEqual(dates, expected)


class TestFormatLangDate(TransactionCase):
    def test_00_accepted_types(self):
        datetime_str = '2017-01-31 12:00:00'
        date_datetime = datetime.datetime.strptime(datetime_str, "%Y-%m-%d %H:%M:%S")
        date_date = date_datetime.date()
        date_str = '2017-01-31'
        time_part = datetime.time(16, 30, 22)

        self.assertEqual(misc.format_date(self.env, date_datetime), '01/31/2017')
        self.assertEqual(misc.format_date(self.env, date_date), '01/31/2017')
        self.assertEqual(misc.format_date(self.env, date_str), '01/31/2017')
        self.assertEqual(misc.format_date(self.env, ''), '')
        self.assertEqual(misc.format_date(self.env, False), '')
        self.assertEqual(misc.format_date(self.env, None), '')

        self.assertEqual(misc.format_datetime(self.env, date_datetime), 'Jan 31, 2017, 1:00:00 PM')
        self.assertEqual(misc.format_datetime(self.env, datetime_str), 'Jan 31, 2017, 1:00:00 PM')
        self.assertEqual(misc.format_datetime(self.env, ''), '')
        self.assertEqual(misc.format_datetime(self.env, False), '')
        self.assertEqual(misc.format_datetime(self.env, None), '')

        self.assertEqual(misc.format_time(self.env, time_part), '4:30:22 PM')
        self.assertEqual(misc.format_time(self.env, ''), '')
        self.assertEqual(misc.format_time(self.env, False), '')
        self.assertEqual(misc.format_time(self.env, None), '')

    def test_01_code_and_format(self):
        date_str = '2017-01-31'
        lang = self.env['res.lang']

        # Activate French and Simplified Chinese (test with non-ASCII characters)
        lang.search([('active', '=', False), ('code', 'in', ['fr_FR', 'zh_CN'])]).write({'active': True})

        # -- test `date`
        # Change a single parameter
        self.assertEqual(misc.format_date(lang.with_context(lang='fr_FR').env, date_str), '31/01/2017')
        self.assertEqual(misc.format_date(lang.env, date_str, lang_code='fr_FR'), '31/01/2017')
        self.assertEqual(misc.format_date(lang.env, date_str, date_format='MMM d, y'), 'Jan 31, 2017')

        # Change 2 parameters
        self.assertEqual(misc.format_date(lang.with_context(lang='zh_CN').env, date_str, lang_code='fr_FR'), '31/01/2017')
        self.assertEqual(misc.format_date(lang.with_context(lang='zh_CN').env, date_str, date_format='MMM d, y'), u'1\u6708 31, 2017')
        self.assertEqual(misc.format_date(lang.env, date_str, lang_code='fr_FR', date_format='MMM d, y'), 'janv. 31, 2017')

        # Change 3 parameters
        self.assertEqual(misc.format_date(lang.with_context(lang='zh_CN').env, date_str, lang_code='en_US', date_format='MMM d, y'), 'Jan 31, 2017')

        # -- test `datetime`
        datetime_str = '2017-01-31 10:33:00'

        # Change languages and timezones
        self.assertEqual(misc.format_datetime(lang.with_context(lang='fr_FR').env, datetime_str, tz='Europe/Brussels'), '31 janv. 2017 à 11:33:00')
        self.assertEqual(misc.format_datetime(lang.with_context(lang='zh_CN').env, datetime_str, tz='America/New_York'), '2017\u5E741\u670831\u65E5 \u4E0A\u53485:33:00')  # '2017年1月31日 上午5:33:00'

        # Change language, timezone and format
        self.assertEqual(misc.format_datetime(lang.with_context(lang='fr_FR').env, datetime_str, tz='America/New_York', dt_format='short'), '31/01/2017 05:33')
        self.assertEqual(misc.format_datetime(lang.with_context(lang='en_US').env, datetime_str, tz='Europe/Brussels', dt_format='MMM d, y'), 'Jan 31, 2017')

        # Check given `lang_code` overwites context lang
        self.assertEqual(misc.format_datetime(lang.env, datetime_str, tz='Europe/Brussels', dt_format='long', lang_code='fr_FR'), '31 janvier 2017 à 11:33:00 +0100')
        self.assertEqual(misc.format_datetime(lang.with_context(lang='zh_CN').env, datetime_str, tz='Europe/Brussels', dt_format='long', lang_code='en_US'), 'January 31, 2017 at 11:33:00 AM +0100')

        # -- test `time`
        time_part = datetime.time(16, 30, 22)
        time_part_tz = datetime.time(16, 30, 22, tzinfo=pytz.timezone('US/Eastern'))  # 4:30 PM timezoned

        self.assertEqual(misc.format_time(lang.with_context(lang='fr_FR').env, time_part), '16:30:22')
        self.assertEqual(misc.format_time(lang.with_context(lang='zh_CN').env, time_part), '\u4e0b\u53484:30:22')

        # Check format in different languages
        self.assertEqual(misc.format_time(lang.with_context(lang='fr_FR').env, time_part, time_format='short'), '16:30')
        self.assertEqual(misc.format_time(lang.with_context(lang='zh_CN').env, time_part, time_format='short'), '\u4e0b\u53484:30')

        # Check timezoned time part
        self.assertEqual(misc.format_time(lang.with_context(lang='fr_FR').env, time_part_tz, time_format='long'), '16:30:22 -0504')
        self.assertEqual(misc.format_time(lang.with_context(lang='zh_CN').env, time_part_tz, time_format='full'), '\u5317\u7f8e\u4e1c\u90e8\u6807\u51c6\u65f6\u95f4\u0020\u4e0b\u53484:30:22')

        # Check given `lang_code` overwites context lang
        self.assertEqual(misc.format_time(lang.with_context(lang='fr_FR').env, time_part, time_format='short', lang_code='zh_CN'), '\u4e0b\u53484:30')
        self.assertEqual(misc.format_time(lang.with_context(lang='zh_CN').env, time_part, time_format='medium', lang_code='fr_FR'), '16:30:22')
