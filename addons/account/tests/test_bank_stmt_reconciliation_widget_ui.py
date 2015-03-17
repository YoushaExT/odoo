import openerp.tests

@openerp.tests.common.at_install(False)
@openerp.tests.common.post_install(True)

class TestUi(openerp.tests.HttpCase):
    def test_01_admin_bank_statement_reconciliation(self):
        self.phantom_js("/", "odoo.__DEBUG__.services['web.Tour'].run('bank_statement_reconciliation', 'test')", "odoo.__DEBUG__.services['web.Tour'].tours.bank_statement_reconciliation", login="admin")