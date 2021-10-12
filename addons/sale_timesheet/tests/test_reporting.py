# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo.osv import expression
from odoo.tools import float_is_zero, float_compare
from odoo.addons.sale_timesheet.tests.common_reporting import TestCommonReporting
from odoo.tests import tagged


@tagged('-at_install', 'post_install')
class TestReporting(TestCommonReporting):

    def test_profitability_report(self):

        # this test suppose everything is in the same currency as the current one
        currency = self.env.company.currency_id
        rounding = currency.rounding

        project_global_stat = self.env['project.profitability.report'].search([('project_id', '=', self.project_global.id)]).read()[0]
        self.assertTrue(float_is_zero(project_global_stat['amount_untaxed_invoiced'], precision_rounding=rounding), "The invoiced amount of the global project should be 0.0")
        self.assertTrue(float_is_zero(project_global_stat['amount_untaxed_to_invoice'], precision_rounding=rounding), "The amount to invoice of the global project should be 0.0")
        self.assertTrue(float_is_zero(project_global_stat['timesheet_unit_amount'], precision_rounding=rounding), "The timesheet unit amount of the global project should be 0.0")
        self.assertTrue(float_is_zero(project_global_stat['timesheet_cost'], precision_rounding=rounding), "The timesheet cost of the global project should be 0.0")
        self.assertTrue(float_is_zero(project_global_stat['expense_amount_untaxed_to_invoice'], precision_rounding=rounding), "The expense cost to reinvoice of the global project should be 0.0")
        self.assertTrue(float_is_zero(project_global_stat['expense_amount_untaxed_invoiced'], precision_rounding=rounding), "The expense invoiced amount of the global project should be 0.0")
        self.assertTrue(float_is_zero(project_global_stat['expense_cost'], precision_rounding=rounding), "The expense cost of the global project should be 0.0")

        # confirm sales orders
        self.sale_order_1.action_confirm()
        self.sale_order_2.action_confirm()
        self.env['project.profitability.report'].flush()

        project_so_1 = self.so_line_deliver_project.project_id
        project_so_2 = self.so_line_order_project.project_id
        task_so_1 = self.so_line_deliver_project.task_id
        task_so_2 = self.so_line_order_project.task_id
        task_in_global_1 = self.so_line_deliver_task.task_id
        task_in_global_2 = self.so_line_order_task.task_id

        # deliver project should not be impacted, as no timesheet are logged yet
        project_so_1_stat = self.env['project.profitability.report'].read_group([('project_id', 'in', project_so_1.ids)], ['project_id', 'amount_untaxed_to_invoice', 'amount_untaxed_invoiced', 'timesheet_unit_amount', 'timesheet_cost', 'expense_cost', 'expense_amount_untaxed_to_invoice', 'expense_amount_untaxed_invoiced'], ['project_id'])[0]
        self.assertTrue(float_is_zero(project_so_1_stat['amount_untaxed_invoiced'], precision_rounding=rounding), "The invoiced amount of the project from SO1 should be 0.0")
        self.assertTrue(float_is_zero(project_so_1_stat['amount_untaxed_to_invoice'], precision_rounding=rounding), "The amount to invoice of the project from SO1 should be 0.0")
        self.assertTrue(float_is_zero(project_so_1_stat['timesheet_unit_amount'], precision_rounding=rounding), "The timesheet unit amount of the project from SO1 should be 0.0")
        self.assertTrue(float_is_zero(project_so_1_stat['timesheet_cost'], precision_rounding=rounding), "The timesheet cost of the global project from SO1 should be 0.0")
        self.assertTrue(float_is_zero(project_so_1_stat['expense_amount_untaxed_to_invoice'], precision_rounding=rounding), "The expense cost to reinvoice of the project from SO1 should be 0.0")
        self.assertTrue(float_is_zero(project_so_1_stat['expense_amount_untaxed_invoiced'], precision_rounding=rounding), "The expense invoiced amount of the global project should be 0.0")
        self.assertTrue(float_is_zero(project_so_1_stat['expense_cost'], precision_rounding=rounding), "The expense cost of the project from SO1 should be 0.0")

        # order project should be to invoice, but nothing has been delivered yet
        project_so_2_stat = self.env['project.profitability.report'].read_group([('project_id', 'in', project_so_2.ids)], ['project_id', 'amount_untaxed_to_invoice', 'amount_untaxed_invoiced', 'timesheet_unit_amount', 'timesheet_cost', 'expense_cost', 'expense_amount_untaxed_to_invoice', 'expense_amount_untaxed_invoiced'], ['project_id'])[0]
        self.assertTrue(float_is_zero(project_so_2_stat['amount_untaxed_invoiced'], precision_rounding=rounding), "The invoiced amount of the project from SO2 should be 0.0")
        self.assertEqual(float_compare(project_so_2_stat['amount_untaxed_to_invoice'], self.so_line_order_project.price_unit * self.so_line_order_project.qty_to_invoice, precision_rounding=rounding), 0, "The amount to invoice should be the one from the SO line, as we are in ordered quantity")
        self.assertTrue(float_is_zero(project_so_2_stat['timesheet_unit_amount'], precision_rounding=rounding), "The timesheet unit amount of the project from SO2 should be 0.0")
        self.assertTrue(float_is_zero(project_so_2_stat['timesheet_cost'], precision_rounding=rounding), "The timesheet cost of the project from SO2 should be 0.0")
        self.assertTrue(float_is_zero(project_so_2_stat['expense_amount_untaxed_to_invoice'], precision_rounding=rounding), "The expense cost to reinvoice of the project from SO2 should be 0.0")
        self.assertTrue(float_is_zero(project_so_2_stat['expense_amount_untaxed_invoiced'], precision_rounding=rounding), "The expense invoiced amount of the global project should be 0.0")
        self.assertTrue(float_is_zero(project_so_2_stat['expense_cost'], precision_rounding=rounding), "The expense cost of the project from SO2 should be 0.0")

        # global project now contain 2 tasks: 'deliver' one which has no effect (no timesheet yet), and the 'order' one which should update the 'to invoice' amount
        project_global_stat = self.env['project.profitability.report'].read_group([('project_id', 'in', self.project_global.ids)], ['project_id', 'amount_untaxed_to_invoice', 'amount_untaxed_invoiced', 'timesheet_unit_amount', 'timesheet_cost', 'expense_cost', 'expense_amount_untaxed_to_invoice', 'expense_amount_untaxed_invoiced'], ['project_id'])[0]
        self.assertTrue(float_is_zero(project_global_stat['amount_untaxed_invoiced'], precision_rounding=rounding), "The invoiced amount of the global project should be 0.0")
        self.assertEqual(float_compare(project_global_stat['amount_untaxed_to_invoice'], self.so_line_order_task.price_unit * self.so_line_order_task.qty_to_invoice, precision_rounding=rounding), 0, "The amount to invoice of global project should take the task in 'oredered qty' into account")
        self.assertTrue(float_is_zero(project_global_stat['timesheet_unit_amount'], precision_rounding=rounding), "The timesheet unit amount of the global project should be 0.0")
        self.assertTrue(float_is_zero(project_global_stat['timesheet_cost'], precision_rounding=rounding), "The timesheet cost of the global project should be 0.0")
        self.assertTrue(float_is_zero(project_global_stat['expense_amount_untaxed_to_invoice'], precision_rounding=rounding), "The expense cost to reinvoice of the global project should be 0.0")
        self.assertTrue(float_is_zero(project_global_stat['expense_amount_untaxed_invoiced'], precision_rounding=rounding), "The expense invoiced amount of the global project should be 0.0")
        self.assertTrue(float_is_zero(project_global_stat['expense_cost'], precision_rounding=rounding), "The expense cost of the global project should be 0.0")

        # logged some timesheets: on project only, then on tasks with different employees
        timesheet1 = self._log_timesheet_user(project_so_1, 2)
        timesheet2 = self._log_timesheet_user(project_so_2, 2)
        timesheet3 = self._log_timesheet_user(project_so_1, 3, task_so_1)
        timesheet4 = self._log_timesheet_user(project_so_2, 3, task_so_2)

        timesheet5 = self._log_timesheet_manager(project_so_1, 1, task_so_1)
        timesheet6 = self._log_timesheet_manager(project_so_2, 1, task_so_2)
        timesheet7 = self._log_timesheet_manager(self.project_global, 3, task_in_global_1)
        timesheet8 = self._log_timesheet_manager(self.project_global, 3, task_in_global_2)
        self.env['project.profitability.report'].flush()

        # deliver project should now have cost and something to invoice
        project_so_1_stat = self.env['project.profitability.report'].read_group([('project_id', 'in', project_so_1.ids)], ['project_id', 'amount_untaxed_to_invoice', 'amount_untaxed_invoiced', 'timesheet_unit_amount', 'timesheet_cost', 'expense_cost', 'expense_amount_untaxed_to_invoice', 'expense_amount_untaxed_invoiced'], ['project_id'])[0]
        project_so_1_timesheet_cost = timesheet1.amount + timesheet3.amount + timesheet5.amount
        project_so_1_timesheet_sold_unit = timesheet1.unit_amount + timesheet3.unit_amount + timesheet5.unit_amount
        self.assertTrue(float_is_zero(project_so_1_stat['amount_untaxed_invoiced'], precision_rounding=rounding), "The invoiced amount of the project from SO1 should be 0.0")
        self.assertEqual(float_compare(project_so_1_stat['amount_untaxed_to_invoice'], self.so_line_deliver_project.price_unit * project_so_1_timesheet_sold_unit, precision_rounding=rounding), 0, "The amount to invoice of the project from SO1 should only include timesheet linked to task")
        self.assertEqual(float_compare(project_so_1_stat['timesheet_unit_amount'], project_so_1_timesheet_sold_unit, precision_rounding=rounding), 0, "The timesheet unit amount of the project from SO1 should include all timesheet in project")
        self.assertEqual(float_compare(project_so_1_stat['timesheet_cost'], project_so_1_timesheet_cost, precision_rounding=rounding), 0, "The timesheet cost of the project from SO1 should include all timesheet")
        self.assertTrue(float_is_zero(project_so_1_stat['expense_amount_untaxed_to_invoice'], precision_rounding=rounding), "The expense cost to reinvoice of the project from SO1 should be 0.0")
        self.assertTrue(float_is_zero(project_so_1_stat['expense_amount_untaxed_invoiced'], precision_rounding=rounding), "The expense invoiced amount of the project from SO1 should be 0.0")
        self.assertTrue(float_is_zero(project_so_1_stat['expense_cost'], precision_rounding=rounding), "The expense cost of the project from SO1 should be 0.0")

        # order project still have something to invoice but has costs now
        project_so_2_stat = self.env['project.profitability.report'].read_group([('project_id', 'in', project_so_2.ids)], ['project_id', 'amount_untaxed_to_invoice', 'amount_untaxed_invoiced', 'timesheet_unit_amount', 'timesheet_cost', 'expense_cost', 'expense_amount_untaxed_to_invoice', 'expense_amount_untaxed_invoiced'], ['project_id'])[0]
        project_so_2_timesheet_cost = timesheet2.amount + timesheet4.amount + timesheet6.amount
        project_so_2_timesheet_sold_unit = timesheet2.unit_amount + timesheet4.unit_amount + timesheet6.unit_amount
        self.assertTrue(float_is_zero(project_so_2_stat['amount_untaxed_invoiced'], precision_rounding=rounding), "The invoiced amount of the project from SO2 should be 0.0")
        self.assertEqual(float_compare(project_so_2_stat['amount_untaxed_to_invoice'], self.so_line_order_project.price_unit * self.so_line_order_project.qty_to_invoice, precision_rounding=rounding), 0, "The amount to invoice should be the one from the SO line, as we are in ordered quantity")
        self.assertEqual(float_compare(project_so_2_stat['timesheet_unit_amount'], project_so_2_timesheet_sold_unit, precision_rounding=rounding), 0, "The timesheet unit amount of the project from SO2 should include all timesheet")
        self.assertEqual(float_compare(project_so_2_stat['timesheet_cost'], project_so_2_timesheet_cost, precision_rounding=rounding), 0, "The timesheet cost of the project from SO2 should include all timesheet")
        self.assertTrue(float_is_zero(project_so_2_stat['expense_amount_untaxed_to_invoice'], precision_rounding=rounding), "The expense cost to reinvoice of the project from SO2 should be 0.0")
        self.assertTrue(float_is_zero(project_so_2_stat['expense_amount_untaxed_invoiced'], precision_rounding=rounding), "The expense invoiced amount of the project from SO1 should be 0.0")
        self.assertTrue(float_is_zero(project_so_2_stat['expense_cost'], precision_rounding=rounding), "The expense cost of the project from SO2 should be 0.0")

        # global project should have more to invoice, and should now have costs
        project_global_stat = self.env['project.profitability.report'].read_group([('project_id', 'in', self.project_global.ids)], ['project_id', 'amount_untaxed_to_invoice', 'amount_untaxed_invoiced', 'timesheet_unit_amount', 'timesheet_cost', 'expense_cost', 'expense_amount_untaxed_to_invoice', 'expense_amount_untaxed_invoiced'], ['project_id'])[0]
        project_global_timesheet_cost = timesheet7.amount + timesheet8.amount
        project_global_timesheet_unit = timesheet7.unit_amount + timesheet8.unit_amount
        project_global_to_invoice = (self.so_line_order_task.price_unit * self.so_line_order_task.product_uom_qty) + (self.so_line_deliver_task.price_unit * timesheet7.unit_amount)
        self.assertTrue(float_is_zero(project_global_stat['amount_untaxed_invoiced'], precision_rounding=rounding), "The invoiced amount of the global project should be 0.0")
        self.assertEqual(float_compare(project_global_stat['amount_untaxed_to_invoice'], project_global_to_invoice, precision_rounding=rounding), 0, "The amount to invoice of global project should take the task in 'oredered qty' and the delivered timesheets into account")
        self.assertEqual(float_compare(project_global_stat['timesheet_unit_amount'], project_global_timesheet_unit, precision_rounding=rounding), 0, "The timesheet unit amount of the global project should include all timesheet")
        self.assertEqual(float_compare(project_global_stat['timesheet_cost'], project_global_timesheet_cost, precision_rounding=rounding), 0, "The timesheet cost of the global project should include all timesheet")
        self.assertTrue(float_is_zero(project_global_stat['expense_amount_untaxed_to_invoice'], precision_rounding=rounding), "The expense cost to reinvoice of the global project should be 0.0")
        self.assertTrue(float_is_zero(project_global_stat['expense_amount_untaxed_invoiced'], precision_rounding=rounding), "The expense invoiced amount of the project from SO1 should be 0.0")
        self.assertTrue(float_is_zero(project_global_stat['expense_cost'], precision_rounding=rounding), "The expense cost of the global project should be 0.0")

        InvoiceWizard = self.env['sale.advance.payment.inv'].with_context(mail_notrack=True)

        # invoice the Sales Order SO1 (based on delivered qty)
        context = {
            "active_model": 'sale.order',
            "active_ids": [self.sale_order_1.id],
            "active_id": self.sale_order_1.id,
            'open_invoices': True,
        }
        payment = InvoiceWizard.create({
            'advance_payment_method': 'delivered',
        })
        action_invoice = payment.with_context(context).create_invoices()
        invoice_id = action_invoice['res_id']
        invoice_1 = self.env['account.move'].browse(invoice_id)
        invoice_1.action_post()
        self.env['project.profitability.report'].flush()

        # deliver project should now have cost and something invoiced
        project_so_1_stat = self.env['project.profitability.report'].read_group([('project_id', 'in', project_so_1.ids)], ['project_id', 'amount_untaxed_to_invoice', 'amount_untaxed_invoiced', 'timesheet_unit_amount', 'timesheet_cost', 'expense_cost', 'expense_amount_untaxed_to_invoice', 'expense_amount_untaxed_invoiced'], ['project_id'])[0]
        project_so_1_timesheet_cost = timesheet1.amount + timesheet3.amount + timesheet5.amount
        project_so_1_timesheet_sold_unit = timesheet1.unit_amount + timesheet3.unit_amount + timesheet5.unit_amount

        self.assertEqual(float_compare(project_so_1_stat['amount_untaxed_invoiced'], self.so_line_deliver_project.price_unit * project_so_1_timesheet_sold_unit, precision_rounding=rounding), 0, "The invoiced amount of the project from SO1 should only include timesheet linked to task")
        self.assertTrue(float_is_zero(project_so_1_stat['amount_untaxed_to_invoice'], precision_rounding=rounding), "The amount to invoice of the project from SO1 should be 0.0")
        self.assertEqual(float_compare(project_so_1_stat['timesheet_unit_amount'], project_so_1_timesheet_sold_unit, precision_rounding=rounding), 0, "The timesheet unit amount of the project from SO1 should include all timesheet in project")
        self.assertEqual(float_compare(project_so_1_stat['timesheet_cost'], project_so_1_timesheet_cost, precision_rounding=rounding), 0, "The timesheet cost of the project from SO1 should include all timesheet")
        self.assertTrue(float_is_zero(project_so_1_stat['expense_amount_untaxed_to_invoice'], precision_rounding=rounding), "The expense cost to reinvoice of the project from SO1 should be 0.0")
        self.assertTrue(float_is_zero(project_so_1_stat['expense_amount_untaxed_invoiced'], precision_rounding=rounding), "The expense invoiced amount of the project from SO1 should be 0.0")
        self.assertTrue(float_is_zero(project_so_1_stat['expense_cost'], precision_rounding=rounding), "The expense cost of the project from SO1 should be 0.0")

        # order project has still nothing invoiced
        project_so_2_stat = self.env['project.profitability.report'].read_group([('project_id', 'in', project_so_2.ids)], ['project_id', 'amount_untaxed_to_invoice', 'amount_untaxed_invoiced', 'timesheet_unit_amount', 'timesheet_cost', 'expense_cost', 'expense_amount_untaxed_to_invoice', 'expense_amount_untaxed_invoiced'], ['project_id'])[0]
        project_so_2_timesheet_cost = timesheet2.amount + timesheet4.amount + timesheet6.amount
        project_so_2_timesheet_sold_unit = timesheet2.unit_amount + timesheet4.unit_amount + timesheet6.unit_amount
        self.assertTrue(float_is_zero(project_so_2_stat['amount_untaxed_invoiced'], precision_rounding=rounding), "The invoiced amount of the project from SO2 should be 0.0")
        self.assertEqual(float_compare(project_so_2_stat['amount_untaxed_to_invoice'], self.so_line_order_project.price_unit * self.so_line_order_project.qty_to_invoice, precision_rounding=rounding), 0, "The amount to invoice should be the one from the SO line, as we are in ordered quantity")
        self.assertEqual(float_compare(project_so_2_stat['timesheet_unit_amount'], project_so_2_timesheet_sold_unit, precision_rounding=rounding), 0, "The timesheet unit amount of the project from SO2 should include all timesheet")
        self.assertEqual(float_compare(project_so_2_stat['timesheet_cost'], project_so_2_timesheet_cost, precision_rounding=rounding), 0, "The timesheet cost of the project from SO2 should include all timesheet")
        self.assertTrue(float_is_zero(project_so_2_stat['expense_amount_untaxed_to_invoice'], precision_rounding=rounding), "The expense cost to reinvoice of the project from SO2 should be 0.0")
        self.assertTrue(float_is_zero(project_so_2_stat['expense_amount_untaxed_invoiced'], precision_rounding=rounding), "The expense invoiced amount of the project from SO1 should be 0.0")
        self.assertTrue(float_is_zero(project_so_2_stat['expense_cost'], precision_rounding=rounding), "The expense cost of the project from SO2 should be 0.0")

        # global project should have more to invoice, and should now have costs
        project_global_stat = self.env['project.profitability.report'].read_group([('project_id', 'in', self.project_global.ids)], ['project_id', 'amount_untaxed_to_invoice', 'amount_untaxed_invoiced', 'timesheet_unit_amount', 'timesheet_cost', 'expense_cost', 'expense_amount_untaxed_to_invoice', 'expense_amount_untaxed_invoiced'], ['project_id'])[0]
        project_global_timesheet_cost = timesheet7.amount + timesheet8.amount
        project_global_timesheet_unit = timesheet7.unit_amount + timesheet8.unit_amount
        project_global_to_invoice = self.so_line_order_task.price_unit * self.so_line_order_task.product_uom_qty
        project_global_invoiced = self.so_line_deliver_task.price_unit * timesheet7.unit_amount
        self.assertEqual(float_compare(project_global_stat['amount_untaxed_invoiced'], project_global_invoiced, precision_rounding=rounding), 0, "The invoiced amount of the global project should be 0.0")
        self.assertEqual(float_compare(project_global_stat['amount_untaxed_to_invoice'], project_global_to_invoice, precision_rounding=rounding), 0, "The amount to invoice of global project should take the task in 'oredered qty' and the delivered timesheets into account")
        self.assertEqual(float_compare(project_global_stat['timesheet_unit_amount'], project_global_timesheet_unit, precision_rounding=rounding), 0, "The timesheet unit amount of the global project should include all timesheet")
        self.assertEqual(float_compare(project_global_stat['timesheet_cost'], project_global_timesheet_cost, precision_rounding=rounding), 0, "The timesheet cost of the global project should include all timesheet")
        self.assertTrue(float_is_zero(project_global_stat['expense_amount_untaxed_to_invoice'], precision_rounding=rounding), "The expense cost to reinvoice of the global project should be 0.0")
        self.assertTrue(float_is_zero(project_global_stat['expense_amount_untaxed_invoiced'], precision_rounding=rounding), "The expense invoiced amount of the project from SO1 should be 0.0")
        self.assertTrue(float_is_zero(project_global_stat['expense_cost'], precision_rounding=rounding), "The expense cost of the global project should be 0.0")

        # invoice the Sales Order SO2
        context = {
            "active_model": 'sale.order',
            "active_ids": [self.sale_order_2.id],
            "active_id": self.sale_order_2.id,
            'open_invoices': True,
        }
        payment = InvoiceWizard.create({
            'advance_payment_method': 'delivered',
        })
        action_invoice = payment.with_context(context).create_invoices()
        invoice_id = action_invoice['res_id']
        invoice_2 = self.env['account.move'].browse(invoice_id)
        invoice_2.action_post()
        self.env['project.profitability.report'].flush()

        # deliver project should not be impacted by the invoice of the other SO
        project_so_1_stat = self.env['project.profitability.report'].read_group([('project_id', 'in', project_so_1.ids)], ['project_id', 'amount_untaxed_to_invoice', 'amount_untaxed_invoiced', 'timesheet_unit_amount', 'timesheet_cost', 'expense_cost', 'expense_amount_untaxed_to_invoice', 'expense_amount_untaxed_invoiced'], ['project_id'])[0]
        project_so_1_timesheet_cost = timesheet1.amount + timesheet3.amount + timesheet5.amount
        project_so_1_timesheet_sold_unit = timesheet1.unit_amount + timesheet3.unit_amount + timesheet5.unit_amount
        self.assertEqual(float_compare(project_so_1_stat['amount_untaxed_invoiced'], self.so_line_deliver_project.price_unit * project_so_1_timesheet_sold_unit, precision_rounding=rounding), 0, "The invoiced amount of the project from SO1 should only include timesheet linked to task")
        self.assertTrue(float_is_zero(project_so_1_stat['amount_untaxed_to_invoice'], precision_rounding=rounding), "The amount to invoice of the project from SO1 should be 0.0")
        self.assertEqual(float_compare(project_so_1_stat['timesheet_unit_amount'], project_so_1_timesheet_sold_unit, precision_rounding=rounding), 0, "The timesheet unit amount of the project from SO1 should include all timesheet in project")
        self.assertEqual(float_compare(project_so_1_stat['timesheet_cost'], project_so_1_timesheet_cost, precision_rounding=rounding), 0, "The timesheet cost of the project from SO1 should include all timesheet")
        self.assertTrue(float_is_zero(project_so_1_stat['expense_amount_untaxed_to_invoice'], precision_rounding=rounding), "The expense cost to reinvoice of the project from SO1 should be 0.0")
        self.assertTrue(float_is_zero(project_so_1_stat['expense_amount_untaxed_invoiced'], precision_rounding=rounding), "The expense invoiced amount of the project from SO1 should be 0.0")
        self.assertTrue(float_is_zero(project_so_1_stat['expense_cost'], precision_rounding=rounding), "The expense cost of the project from SO1 should be 0.0")

        # order project is now totally invoiced, as we are in ordered qty
        project_so_2_stat = self.env['project.profitability.report'].read_group([('project_id', 'in', project_so_2.ids)], ['project_id', 'amount_untaxed_to_invoice', 'amount_untaxed_invoiced', 'timesheet_unit_amount', 'timesheet_cost', 'expense_cost', 'expense_amount_untaxed_to_invoice', 'expense_amount_untaxed_invoiced'], ['project_id'])[0]
        project_so_2_timesheet_cost = timesheet2.amount + timesheet4.amount + timesheet6.amount
        project_so_2_timesheet_sold_unit = timesheet2.unit_amount + timesheet4.unit_amount + timesheet6.unit_amount
        self.assertEqual(float_compare(project_so_2_stat['amount_untaxed_invoiced'], self.so_line_order_project.price_unit * self.so_line_order_project.product_uom_qty, precision_rounding=rounding), 0, "The invoiced amount should be the one from the SO line, as we are in ordered quantity")
        self.assertTrue(float_is_zero(project_so_2_stat['amount_untaxed_to_invoice'], precision_rounding=rounding), "The amount to invoice should be the one 0.0, as all ordered quantity is invoiced")
        self.assertEqual(float_compare(project_so_2_stat['timesheet_unit_amount'], project_so_2_timesheet_sold_unit, precision_rounding=rounding), 0, "The timesheet unit amount of the project from SO2 should include all timesheet")
        self.assertEqual(float_compare(project_so_2_stat['timesheet_cost'], project_so_2_timesheet_cost, precision_rounding=rounding), 0, "The timesheet cost of the project from SO2 should include all timesheet")
        self.assertTrue(float_is_zero(project_so_2_stat['expense_amount_untaxed_to_invoice'], precision_rounding=rounding), "The expense cost to reinvoice of the project from SO2 should be 0.0")
        self.assertTrue(float_is_zero(project_so_2_stat['expense_amount_untaxed_invoiced'], precision_rounding=rounding), "The expense invoiced amount of the project from SO1 should be 0.0")
        self.assertTrue(float_is_zero(project_so_2_stat['expense_cost'], precision_rounding=rounding), "The expense cost of the project from SO2 should be 0.0")

        # global project should be totally invoiced
        project_global_stat = self.env['project.profitability.report'].read_group([('project_id', 'in', self.project_global.ids)], ['project_id', 'amount_untaxed_to_invoice', 'amount_untaxed_invoiced', 'timesheet_unit_amount', 'timesheet_cost', 'expense_cost', 'expense_amount_untaxed_to_invoice', 'expense_amount_untaxed_invoiced'], ['project_id'])[0]
        project_global_timesheet_cost = timesheet7.amount + timesheet8.amount
        project_global_timesheet_unit = timesheet7.unit_amount + timesheet8.unit_amount
        project_global_invoiced = self.so_line_order_task.price_unit * self.so_line_order_task.product_uom_qty + self.so_line_deliver_task.price_unit * timesheet7.unit_amount
        self.assertEqual(float_compare(project_global_stat['amount_untaxed_invoiced'], project_global_invoiced, precision_rounding=rounding), 0, "The invoiced amount of the global project should be 0.0")
        self.assertTrue(float_is_zero(project_global_stat['amount_untaxed_to_invoice'], precision_rounding=rounding), "The amount to invoice of global project should take the task in 'oredered qty' and the delivered timesheets into account")
        self.assertEqual(float_compare(project_global_stat['timesheet_unit_amount'], project_global_timesheet_unit, precision_rounding=rounding), 0, "The timesheet unit amount of the global project should include all timesheet")
        self.assertEqual(float_compare(project_global_stat['timesheet_cost'], project_global_timesheet_cost, precision_rounding=rounding), 0, "The timesheet cost of the global project should include all timesheet")
        self.assertTrue(float_is_zero(project_global_stat['expense_amount_untaxed_to_invoice'], precision_rounding=rounding), "The expense cost to reinvoice of the global project should be 0.0")
        self.assertTrue(float_is_zero(project_global_stat['expense_amount_untaxed_invoiced'], precision_rounding=rounding), "The expense invoiced amount of the project from SO1 should be 0.0")
        self.assertTrue(float_is_zero(project_global_stat['expense_cost'], precision_rounding=rounding), "The expense cost of the global project should be 0.0")

        # simulate the auto creation of the SO line for expense, like we confirm a vendor bill.
        so_line_expense = self.env['sale.order.line'].create({
            'name': self.product_expense.name,
            'product_id': self.product_expense.id,
            'product_uom_qty': 0.0,
            'product_uom': self.product_expense.uom_id.id,
            'price_unit': self.product_expense.list_price,  # reinvoice at sales price
            'order_id': self.sale_order_1.id,
            'is_expense': True,
        })

        # add expense AAL: 20% margin when reinvoicing
        AnalyticLine = self.env['account.analytic.line']
        expense1 = AnalyticLine.create({
            'name': 'expense on project_so_1',
            'account_id': project_so_1.analytic_account_id.id,
            'so_line': so_line_expense.id,
            'employee_id': self.employee_user.id,
            'unit_amount': 4,
            'amount': 4 * self.product_expense.list_price * -1,
            'product_id': self.product_expense.id,
            'product_uom_id': self.product_expense.uom_id.id,
        })
        expense2 = AnalyticLine.create({
            'name': 'expense on global project',
            'account_id': self.project_global.analytic_account_id.id,
            'employee_id': self.employee_user.id,
            'unit_amount': 2,
            'amount': 2 * self.product_expense.list_price * -1,
            'product_id': self.product_expense.id,
            'product_uom_id': self.product_expense.uom_id.id,
        })
        self.env['project.profitability.report'].flush()

        # deliver project should now have expense cost, and expense to reinvoice as there is a still open sales order linked to the AA1
        project_so_1_stat = self.env['project.profitability.report'].read_group([('project_id', 'in', project_so_1.ids)], ['project_id', 'amount_untaxed_to_invoice', 'amount_untaxed_invoiced', 'timesheet_unit_amount', 'timesheet_cost', 'expense_cost', 'expense_amount_untaxed_to_invoice', 'expense_amount_untaxed_invoiced'], ['project_id'])[0]
        project_so_1_timesheet_cost = timesheet1.amount + timesheet3.amount + timesheet5.amount
        project_so_1_timesheet_sold_unit = timesheet1.unit_amount + timesheet3.unit_amount + timesheet5.unit_amount
        self.assertEqual(float_compare(project_so_1_stat['amount_untaxed_invoiced'], self.so_line_deliver_project.price_unit * project_so_1_timesheet_sold_unit, precision_rounding=rounding), 0, "The invoiced amount of the project from SO1 should only include timesheet linked to task")
        self.assertTrue(float_is_zero(project_so_1_stat['amount_untaxed_to_invoice'], precision_rounding=rounding), "The amount to invoice of the project from SO1 should be 0.0")
        self.assertEqual(float_compare(project_so_1_stat['timesheet_unit_amount'], project_so_1_timesheet_sold_unit, precision_rounding=rounding), 0, "The timesheet unit amount of the project from SO1 should include all timesheet in project")
        self.assertEqual(float_compare(project_so_1_stat['timesheet_cost'], project_so_1_timesheet_cost, precision_rounding=rounding), 0, "The timesheet cost of the project from SO1 should include all timesheet")
        self.assertEqual(float_compare(project_so_1_stat['expense_amount_untaxed_to_invoice'], -1 * expense1.amount, precision_rounding=rounding), 0, "The expense cost to reinvoice of the project from SO1 should be 0.0")
        self.assertTrue(float_is_zero(project_so_1_stat['expense_amount_untaxed_invoiced'], precision_rounding=rounding), "The expense invoiced amount of the project from SO1 should be 0.0")
        self.assertEqual(float_compare(project_so_1_stat['expense_cost'], expense1.amount, precision_rounding=rounding), 0, "The expense cost of the project from SO1 should be 0.0")

        # order project is not impacted by the expenses
        project_so_2_stat = self.env['project.profitability.report'].read_group([('project_id', 'in', project_so_2.ids)], ['project_id', 'amount_untaxed_to_invoice', 'amount_untaxed_invoiced', 'timesheet_unit_amount', 'timesheet_cost', 'expense_cost', 'expense_amount_untaxed_to_invoice', 'expense_amount_untaxed_invoiced'], ['project_id'])[0]
        project_so_2_timesheet_cost = timesheet2.amount + timesheet4.amount + timesheet6.amount
        project_so_2_timesheet_sold_unit = timesheet2.unit_amount + timesheet4.unit_amount + timesheet6.unit_amount
        self.assertEqual(float_compare(project_so_2_stat['amount_untaxed_invoiced'], self.so_line_order_project.price_unit * self.so_line_order_project.product_uom_qty, precision_rounding=rounding), 0, "The invoiced amount should be the one from the SO line, as we are in ordered quantity")
        self.assertTrue(float_is_zero(project_so_2_stat['amount_untaxed_to_invoice'], precision_rounding=rounding), "The amount to invoice should be the one 0.0, as all ordered quantity is invoiced")
        self.assertEqual(float_compare(project_so_2_stat['timesheet_unit_amount'], project_so_2_timesheet_sold_unit, precision_rounding=rounding), 0, "The timesheet unit amount of the project from SO2 should include all timesheet")
        self.assertEqual(float_compare(project_so_2_stat['timesheet_cost'], project_so_2_timesheet_cost, precision_rounding=rounding), 0, "The timesheet cost of the project from SO2 should include all timesheet")
        self.assertTrue(float_is_zero(project_so_2_stat['expense_amount_untaxed_to_invoice'], precision_rounding=rounding), "The expense cost to reinvoice of the project from SO2 should be 0.0")
        self.assertTrue(float_is_zero(project_so_2_stat['expense_amount_untaxed_invoiced'], precision_rounding=rounding), "The expense invoiced amount of the project from SO1 should be 0.0")
        self.assertTrue(float_is_zero(project_so_2_stat['expense_cost'], precision_rounding=rounding), "The expense cost of the project from SO2 should be 0.0")

        # global project should have an expense, but not reinvoiceable
        project_global_stat = self.env['project.profitability.report'].read_group([('project_id', 'in', self.project_global.ids)], ['project_id', 'amount_untaxed_to_invoice', 'amount_untaxed_invoiced', 'timesheet_unit_amount', 'timesheet_cost', 'expense_cost', 'expense_amount_untaxed_to_invoice', 'expense_amount_untaxed_invoiced'], ['project_id'])[0]
        project_global_timesheet_cost = timesheet7.amount + timesheet8.amount
        project_global_timesheet_unit = timesheet7.unit_amount + timesheet8.unit_amount
        project_global_invoiced = self.so_line_order_task.price_unit * self.so_line_order_task.product_uom_qty + self.so_line_deliver_task.price_unit * timesheet7.unit_amount
        self.assertEqual(float_compare(project_global_stat['amount_untaxed_invoiced'], project_global_invoiced, precision_rounding=rounding), 0, "The invoiced amount of the global project should be 0.0")
        self.assertTrue(float_is_zero(project_global_stat['amount_untaxed_to_invoice'], precision_rounding=rounding), "The amount to invoice of global project should take the task in 'oredered qty' and the delivered timesheets into account")
        self.assertEqual(float_compare(project_global_stat['timesheet_unit_amount'], project_global_timesheet_unit, precision_rounding=rounding), 0, "The timesheet unit amount of the global project should include all timesheet")
        self.assertEqual(float_compare(project_global_stat['timesheet_cost'], project_global_timesheet_cost, precision_rounding=rounding), 0, "The timesheet cost of the global project should include all timesheet")
        self.assertTrue(float_is_zero(project_global_stat['expense_amount_untaxed_to_invoice'], precision_rounding=rounding), "The expense cost to reinvoice of the global project should be 0.0")
        self.assertTrue(float_is_zero(project_global_stat['expense_amount_untaxed_invoiced'], precision_rounding=rounding), "The expense invoiced amount of the project from SO1 should be 0.0")
        self.assertEqual(float_compare(project_global_stat['expense_cost'], expense2.amount, precision_rounding=rounding), 0, "The expense cost of the global project should be 0.0")

    def test_reversed_downpayment(self):
        # this test suppose everything is in the same currency as the current one
        currency = self.env.company.currency_id
        rounding = currency.rounding

        self.sale_order_2.action_confirm()
        context = {
            'active_model': 'sale.order',
            'active_ids': self.sale_order_2.ids,
            'active_id': self.sale_order_2.id,
            'default_journal_id': self.company_data['default_journal_sale'].id,
            'open_invoices': True,
        }
        # Let's do an invoice for a deposit of 100
        downpayment = self.env['sale.advance.payment.inv'].with_context(context).create({
            'advance_payment_method': 'percentage',
            'amount': 10,
        })
        action_invoice = downpayment.create_invoices()
        invoice_id = action_invoice['res_id']
        invoice_downpayment = self.env['account.move'].browse(invoice_id)
        invoice_downpayment.action_post()
        posted_invoice_res_ids = [invoice_id]
        downpayment2 = self.env['sale.advance.payment.inv'].with_context(context).create({
            'advance_payment_method': 'percentage',
            'amount': 25,
        })
        action_invoice = downpayment2.create_invoices()
        invoice_downpayment2 = self.env['account.move'].search(expression.AND([action_invoice['domain'], [('id', 'not in', posted_invoice_res_ids)]]))
        invoice_downpayment2.action_post()
        posted_invoice_res_ids += invoice_downpayment2.ids
        milestone_to_invoice = self.so_line_order_project.price_unit * self.so_line_order_project.qty_to_invoice
        timesheets_to_invoice = self.so_line_order_task.price_unit * self.so_line_order_task.qty_to_invoice
        total_product_price = milestone_to_invoice + timesheets_to_invoice
        credit_note_wizard = self.env['account.move.reversal'].with_context({
            'active_ids': invoice_downpayment2.ids,
            'active_id': invoice_downpayment2.id,
            'active_model': 'account.move'
        }).create({
            'refund_method': 'refund',
            'reason': 'reason test create',
            'journal_id': invoice_downpayment2.journal_id.id,
        })
        action_moves = credit_note_wizard.reverse_moves()
        credit_id = action_moves['res_id']
        invoice_credit = self.env['account.move'].browse(credit_id)
        invoice_credit.action_post()
        posted_invoice_res_ids += invoice_credit.ids
        project_so_2 = self.so_line_order_project.project_id
        task_so_2 = self.so_line_order_project.task_id
        task_in_global_2 = self.so_line_order_task.task_id

        self.env['project.profitability.report'].flush()
        project_so_2_stat = self.env['project.profitability.report'].read_group(
            [('project_id', 'in', project_so_2.ids)],
            ['project_id', 'amount_untaxed_to_invoice', 'amount_untaxed_invoiced', 'timesheet_unit_amount', 'timesheet_cost', 'expense_cost', 'expense_amount_untaxed_to_invoice', 'expense_amount_untaxed_invoiced', 'other_revenues'],
            ['project_id']
        )[0]
        self.assertEqual(float_compare(project_so_2_stat['amount_untaxed_invoiced'], 0.1 * total_product_price, precision_rounding=rounding), 0,
                         "The invoiced amount is the amount of downpayments not reversed")
        self.assertEqual(float_compare(project_so_2_stat['amount_untaxed_to_invoice'], milestone_to_invoice - 0.1 * total_product_price, precision_rounding=rounding), 0,
                         "The amount to invoice is the milestone product minus the downpayment not reversed")
        self.assertTrue(float_is_zero(project_so_2_stat['timesheet_unit_amount'], precision_rounding=rounding),
                        "The timesheet unit amount of the project from SO2 is 0")
        self.assertTrue(float_is_zero(project_so_2_stat['timesheet_cost'], precision_rounding=rounding),
                        "The timesheet cost of the project from SO2 is 0")
        self.assertTrue(float_is_zero(project_so_2_stat['expense_amount_untaxed_to_invoice'], precision_rounding=rounding),
                        "The expense cost to reinvoice of the project from SO2 should be 0.0")
        self.assertTrue(float_is_zero(project_so_2_stat['expense_amount_untaxed_invoiced'], precision_rounding=rounding),
                        "The expense invoiced amount of the project from SO2 should be 0.0")
        self.assertTrue(float_is_zero(project_so_2_stat['expense_cost'], precision_rounding=rounding),
                        "The expense cost of the project from SO2 should be 0.0")
        self.assertTrue(float_is_zero(project_so_2_stat['other_revenues'], precision_rounding=rounding),
                        "The other revenues of the project from SO2 should be 0.0")

        # logged some timesheets: on project only, then on tasks with different employees
        timesheet2 = self._log_timesheet_user(project_so_2, 2)
        timesheet4 = self._log_timesheet_user(project_so_2, 3, task_so_2)
        timesheet6 = self._log_timesheet_manager(project_so_2, 2, task_so_2)
        timesheet8 = self._log_timesheet_manager(self.project_global, 3, task_in_global_2)

        # simulate the auto creation of the SO line for expense, like we confirm a vendor bill.
        so_line_expense = self.env['sale.order.line'].create({
            'name': self.product_expense.name,
            'product_id': self.product_expense.id,
            'product_uom_qty': 0.0,
            'product_uom': self.product_expense.uom_id.id,
            'price_unit': self.product_expense.list_price,  # reinvoice at sales price
            'order_id': self.sale_order_2.id,
            'is_expense': True,
        })

        expense1 = self.env['account.analytic.line'].create({
            'name': 'expense on project_so_2',
            'account_id': project_so_2.analytic_account_id.id,
            'so_line': so_line_expense.id,
            'employee_id': self.employee_user.id,
            'unit_amount': 4,
            'amount': 4 * self.product_expense.list_price * -1,
            'product_id': self.product_expense.id,
            'product_uom_id': self.product_expense.uom_id.id,
        })

        self.env['project.profitability.report'].flush()

        project_so_2_stat = self.env['project.profitability.report'].read_group(
            [('project_id', 'in', project_so_2.ids)],
            ['project_id', 'amount_untaxed_to_invoice', 'amount_untaxed_invoiced', 'timesheet_unit_amount', 'timesheet_cost', 'expense_cost', 'expense_amount_untaxed_to_invoice', 'expense_amount_untaxed_invoiced', 'other_revenues'],
            ['project_id']
        )[0]
        project_so_2_timesheet_cost = timesheet2.amount + timesheet4.amount + timesheet6.amount
        project_so_2_timesheet_sold_unit = timesheet2.unit_amount + timesheet4.unit_amount + timesheet6.unit_amount
        self.assertEqual(float_compare(project_so_2_stat['amount_untaxed_invoiced'], 0.1 * total_product_price, precision_rounding=rounding), 0,
                         "The invoiced amount of the project from SO2 should only include downpayment not reversed")
        self.assertEqual(float_compare(project_so_2_stat['amount_untaxed_to_invoice'], milestone_to_invoice - 0.1 * total_product_price, precision_rounding=rounding), 0,
                         "The amount to invoice of the project from SO2 should include the milestone to invoice minus the downpayment")
        self.assertEqual(float_compare(project_so_2_stat['timesheet_unit_amount'], project_so_2_timesheet_sold_unit, precision_rounding=rounding), 0,
                         "The timesheet unit amount of the project from SO2 should include all timesheet in project")
        self.assertEqual(float_compare(project_so_2_stat['timesheet_cost'], project_so_2_timesheet_cost, precision_rounding=rounding), 0,
                         "The timesheet cost of the project from SO2 should include all timesheet")
        self.assertEqual(float_compare(project_so_2_stat['expense_amount_untaxed_to_invoice'], -expense1.amount, precision_rounding=rounding), 0,
                         "The expense cost to reinvoice of the project from SO2 should be the expense amount")
        self.assertTrue(float_is_zero(project_so_2_stat['expense_amount_untaxed_invoiced'], precision_rounding=rounding),
                        "The expense invoiced amount of the project from SO2 should be 0.0")
        self.assertEqual(float_compare(project_so_2_stat['expense_cost'], expense1.amount, precision_rounding=rounding), 0,
                         "The expense cost of the project from SO1 should be expense amount")
        self.assertTrue(float_is_zero(project_so_2_stat['other_revenues'], precision_rounding=rounding),
                        "The other revenues of the project from SO2 should be 0.0")

        # invoice the Sales Order SO2
        context = {
            "active_model": 'sale.order',
            "active_ids": self.sale_order_2.ids,
            "active_id": self.sale_order_2.id,
            'open_invoices': True,
            'mail_notrack': True,
        }
        payment = self.env['sale.advance.payment.inv'].with_context(mail_notrack=True).create({
            'advance_payment_method': 'delivered',
        })
        action_invoice = payment.with_context(context).create_invoices()
        invoice_payment = self.env['account.move'].search(expression.AND([action_invoice['domain'], [('id', 'not in', posted_invoice_res_ids)]]))
        invoice_payment.action_post()
        self.env['project.profitability.report'].flush()

        project_so_2_stat = self.env['project.profitability.report'].read_group(
            [('project_id', 'in', project_so_2.ids)],
            ['project_id', 'amount_untaxed_to_invoice', 'amount_untaxed_invoiced', 'timesheet_unit_amount', 'timesheet_cost', 'expense_cost', 'expense_amount_untaxed_to_invoice', 'expense_amount_untaxed_invoiced', 'other_revenues'],
            ['project_id']
        )[0]
        self.assertEqual(float_compare(project_so_2_stat['amount_untaxed_invoiced'], milestone_to_invoice, precision_rounding=rounding), 0,
                         "The invoiced amount of the project from SO2 should only include timesheet linked to task")
        self.assertTrue(float_is_zero(project_so_2_stat['amount_untaxed_to_invoice'], precision_rounding=rounding),
                        "The amount to invoice of the project from SO2 should be 0.0")
        self.assertEqual(float_compare(project_so_2_stat['timesheet_unit_amount'], project_so_2_timesheet_sold_unit, precision_rounding=rounding), 0,
                         "The timesheet unit amount of the project from SO2 should include all timesheet in project")
        self.assertEqual(float_compare(project_so_2_stat['timesheet_cost'], project_so_2_timesheet_cost, precision_rounding=rounding), 0,
                         "The timesheet cost of the project from SO2 should include all timesheet")
        self.assertTrue(float_is_zero(project_so_2_stat['expense_amount_untaxed_to_invoice'], precision_rounding=rounding),
                        "The expense to invoice amount of the project from SO2 should be 0.0")
        self.assertEqual(float_compare(project_so_2_stat['expense_amount_untaxed_invoiced'], -1 * expense1.amount, precision_rounding=rounding), 0,
                         "The expense cost reinvoiced of the project from SO2 should be the expense amount")
        self.assertEqual(float_compare(project_so_2_stat['expense_cost'], expense1.amount, precision_rounding=rounding), 0,
                         "The expense cost of the project from SO2 should be the expense amount")
        self.assertTrue(float_is_zero(project_so_2_stat['other_revenues'], precision_rounding=rounding),
                        "The other revenues of the project from SO2 should be 0.0")

        credit_note_wizard = self.env['account.move.reversal'].with_context({
            'active_ids': invoice_payment.ids,
            'active_id': invoice_payment.id,
            'active_model': 'account.move'
        }).create({
            'refund_method': 'refund',
            'reason': 'reason test create',
            'journal_id': invoice_payment.journal_id.id,
        })
        action_moves = credit_note_wizard.reverse_moves()
        credit_id = action_moves['res_id']
        invoice_credit = self.env['account.move'].browse(credit_id)
        invoice_credit.action_post()
        self.env['project.profitability.report'].flush()

        project_so_2_stat = self.env['project.profitability.report'].read_group(
            [('project_id', 'in', project_so_2.ids)],
            ['project_id', 'amount_untaxed_to_invoice', 'amount_untaxed_invoiced', 'timesheet_unit_amount', 'timesheet_cost', 'expense_cost', 'expense_amount_untaxed_to_invoice', 'expense_amount_untaxed_invoiced', 'other_revenues'],
            ['project_id']
        )[0]
        self.assertEqual(float_compare(project_so_2_stat['amount_untaxed_invoiced'], 0.1 * total_product_price, precision_rounding=rounding), 0,
                         "The invoiced amount of the project from SO2 should only include downpayment not reversed")
        self.assertEqual(float_compare(project_so_2_stat['amount_untaxed_to_invoice'], milestone_to_invoice - 0.1 * total_product_price, precision_rounding=rounding), 0,
                         "The amount to invoice of the project from SO2 should include the milestone to invoice minus the downpayment")
        self.assertEqual(float_compare(project_so_2_stat['timesheet_unit_amount'], project_so_2_timesheet_sold_unit, precision_rounding=rounding), 0,
                         "The timesheet unit amount of the project from SO2 should include all timesheet in project")
        self.assertEqual(float_compare(project_so_2_stat['timesheet_cost'], project_so_2_timesheet_cost, precision_rounding=rounding), 0,
                         "The timesheet cost of the project from SO2 should include all timesheet")
        self.assertEqual(float_compare(project_so_2_stat['expense_amount_untaxed_to_invoice'], -expense1.amount, precision_rounding=rounding), 0,
                         "The expense cost to reinvoice of the project from SO2 should be the expense amount")
        self.assertTrue(float_is_zero(project_so_2_stat['expense_amount_untaxed_invoiced'], precision_rounding=rounding),
                        "The expense invoiced amount of the project from SO2 should be 0.0")
        self.assertEqual(float_compare(project_so_2_stat['expense_cost'], expense1.amount, precision_rounding=rounding), 0,
                         "The expense cost of the project from SO1 should be expense amount")
        self.assertTrue(float_is_zero(project_so_2_stat['other_revenues'], precision_rounding=rounding),
                        "The other revenues of the project from SO2 should be 0.0")
