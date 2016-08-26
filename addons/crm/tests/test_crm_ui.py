# Part of Odoo. See LICENSE file for full copyright and licensing details.

import odoo.tests


@odoo.tests.common.at_install(False)
@odoo.tests.common.post_install(True)
class TestUi(odoo.tests.HttpCase):

    def test_01_crm_tour(self):
        self.phantom_js("/web", "odoo.__DEBUG__.services['web_tour.tour'].run('crm_tour')", "odoo.__DEBUG__.services['web_tour.tour'].tours.crm_tour.ready", login="admin")
