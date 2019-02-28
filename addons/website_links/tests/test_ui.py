# Part of Odoo. See LICENSE file for full copyright and licensing details.

import odoo.tests
import unittest


@odoo.tests.common.tagged('post_install', '-at_install')
class TestUi(odoo.tests.HttpCase):

    @unittest.skip("Race condition on runbot or on local with Docker. Merging the test skipped for history purpose as the tour has been reviewed.")
    def test_01_test_ui(self):
        self.env['link.tracker'].create({
            'campaign_id': 2,
            'medium_id': 2,
            'source_id': 2,
            'url': self.env["ir.config_parameter"].sudo().get_param("web.base.url") + '/contactus',
        })
        self.phantom_js("/", "odoo.__DEBUG__.services['web_tour.tour'].run('website_links_tour')", "odoo.__DEBUG__.services['web_tour.tour'].tours.website_links_tour.ready", login="admin")
