import odoo.tests


@odoo.tests.common.tagged('post_install', '-at_install')
class TestUi(odoo.tests.HttpCase):

    def test_01_admin_widget_x2many(self):
        # FIXME: breaks if too many children of base.menu_tests

        # This tour turns out to be quite sensible to the number of items in
        # the base.menu_tests: it's specifically sequenced to be lower (after)
        # the default, but doesn't account for the fact that it could
        # "fall off" into the "o_extra_menu_items" section if the window is
        # too small or there are too many items preceding it in the tests menu
        self.start_tour("/web#action=test_new_api.action_discussions",
            'widget_x2many', step_delay=100, login="admin", timeout=120)
