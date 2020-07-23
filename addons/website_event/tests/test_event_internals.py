# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import datetime, timedelta

from odoo import fields
from odoo.addons.website_event.tests.common import TestWebsiteEventCommon
from odoo.tests.common import users


class TestEventWebsite(TestWebsiteEventCommon):

    @users('user_eventmanager')
    def test_menu_create(self):
        event = self.env['event.event'].create({
            'name': 'TestEvent',
            'date_begin': fields.Datetime.to_string(datetime.today() + timedelta(days=1)),
            'date_end': fields.Datetime.to_string(datetime.today() + timedelta(days=15)),
            'website_menu': True,
        })
        self._assert_website_menus(event)

    @users('user_eventmanager')
    def test_menu_update(self):
        event = self.env['event.event'].browse(self.event_0.id)
        self.assertFalse(event.menu_id)
        event.website_menu = True
        self._assert_website_menus(event)
