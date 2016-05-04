# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.tests.common import TransactionCase


class TestIrValues(TransactionCase):

    def test_00(self):
        # Create some default value for some (non-existing) model, for all users.

        ir_values = self.env['ir.values']
        # use the old API
        ir_values.set('default', False, 'my_test_field', ['unexisting_model'],
                      'global value')
        # use the new API
        ir_values.set_default('other_unexisting_model', 'my_other_test_field',
                              'conditional value', condition='foo=bar')
        
        # Retrieve them.

        # d is a list of triplets (id, name, value)
        # Old API
        d = ir_values.get('default', False, ['unexisting_model'])
        self.assertEqual(len(d), 1, "Only one single value should be retrieved for this model")
        self.assertEqual(d[0][1], 'my_test_field', "Can't retrieve the created default value. (1)")
        self.assertEqual(d[0][2], 'global value', "Can't retrieve the created default value. (2)")

        # New API, Conditional version
        d = ir_values.get_defaults('other_unexisting_model')
        self.assertEqual(len(d), 0, "No value should be retrieved, the condition is not met")
        d = ir_values.get_defaults('other_unexisting_model', condition="foo=eggs")
        self.assertEqual(len(d), 0, 'Condition is not met either, no defaults should be returned')
        d = ir_values.get_defaults('other_unexisting_model', condition="foo=bar")
        self.assertEqual(len(d), 1, "Only one single value should be retrieved")
        self.assertEqual(d[0][1], 'my_other_test_field', "Can't retrieve the created default value. (5)")
        self.assertEqual(d[0][2], 'conditional value', "Can't retrieve the created default value. (6)")

        # Do it again but for a specific user.

        ir_values.set('default', False, 'my_test_field',['unexisting_model'],
                      'specific value', preserve_user=True)

        # Retrieve it and check it is the one for the current user.

        d = ir_values.get('default', False, ['unexisting_model'])
        self.assertEqual(len(d), 1, "Only one default must be returned per field")
        self.assertEqual(d[0][1], 'my_test_field', "Can't retrieve the created default value.")
        self.assertEqual(d[0][2], 'specific value', "Can't retrieve the created default value.")

        # Create some action bindings for a non-existing model.

        act_id_1 = self.ref('base.act_values_form_action')
        act_id_2 = self.ref('base.act_values_form_defaults')
        act_id_3 = self.ref('base.action_res_company_form')
        ir_values.set('action', 'tree_but_open', 'OnDblClick Action', ['unexisting_model'],
                      'ir.actions.act_window,%d' % act_id_1, isobject=True)
        ir_values.set('action', 'tree_but_open', 'OnDblClick Action 2', ['unexisting_model'],
                      'ir.actions.act_window,%d' % act_id_2, isobject=True)
        ir_values.set('action', 'client_action_multi', 'Side Wizard', ['unexisting_model'],
                      'ir.actions.act_window,%d' % act_id_3, isobject=True)
        reports = self.env['ir.actions.report.xml'].search([])
        report_id = next(report.id for report in reports if not report.groups_id)
        ir_values.set('action', 'client_print_multi', 'Nice Report', ['unexisting_model'],
                      'ir.actions.report.xml,%d' % report_id, isobject=True)

        # Replace one action binding to set a new name.

        ir_values.set('action', 'tree_but_open', 'OnDblClick Action New', ['unexisting_model'],
                      'ir.actions.act_window,%d' % act_id_1, isobject=True)

        # Retrieve the action bindings and check they're correct

        actions = ir_values.get('action', 'tree_but_open', ['unexisting_model'])
        self.assertEqual(len(actions), 2, "Mismatching number of bound actions")
        #first action
        self.assertEqual(len(actions[0]), 3, "Malformed action definition")
        self.assertEqual(actions[0][1], 'OnDblClick Action 2', 'Bound action does not match definition')
        self.assertTrue(isinstance(actions[0][2], dict) and actions[0][2]['id'] == act_id_2,
                        'Bound action does not match definition')
        #second action - this ones comes last because it was re-created with a different name
        self.assertEqual(len(actions[1]), 3, "Malformed action definition")
        self.assertEqual(actions[1][1], 'OnDblClick Action New', 'Re-Registering an action should replace it')
        self.assertTrue(isinstance(actions[1][2], dict) and actions[1][2]['id'] == act_id_1,
                        'Bound action does not match definition')

        actions = ir_values.get('action', 'client_action_multi', ['unexisting_model'])
        self.assertEqual(len(actions), 1, "Mismatching number of bound actions")
        self.assertEqual(len(actions[0]), 3, "Malformed action definition")
        self.assertEqual(actions[0][1], 'Side Wizard', 'Bound action does not match definition')
        self.assertTrue(isinstance(actions[0][2], dict) and actions[0][2]['id'] == act_id_3,
                        'Bound action does not match definition')

        actions = ir_values.get('action', 'client_print_multi', ['unexisting_model'])
        self.assertEqual(len(actions), 1, "Mismatching number of bound actions")
        self.assertEqual(len(actions[0]), 3, "Malformed action definition")
        self.assertEqual(actions[0][1], 'Nice Report', 'Bound action does not match definition')
        self.assertTrue(isinstance(actions[0][2], dict) and actions[0][2]['id'] == report_id,
                        'Bound action does not match definition')
