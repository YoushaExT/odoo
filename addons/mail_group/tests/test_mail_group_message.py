# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.addons.mail_group.tests.common import TestMailListCommon
from odoo.addons.mail_group.tests.data import GROUP_TEMPLATE
from odoo.exceptions import AccessError
from odoo.tools import mute_logger


class TestMailGroupMessage(TestMailListCommon):
    @mute_logger('odoo.addons.mail.models.mail_thread', 'odoo.addons.mail_group.models.mail_group_message')
    def test_email_duplicated(self):
        """ Test gateway does not accept two times same incoming email """
        self.test_group.write({'moderation': False})

        with self.mock_mail_gateway():
            self.format_and_process(
                GROUP_TEMPLATE, self.email_from_unknown, self.test_group.alias_id.display_name,
                subject='Test subject', msg_id='<test.message.id@localhost>', target_model='mail.group')

        message = self.env['mail.group.message'].search([('mail_message_id.message_id', '=', '<test.message.id@localhost>')])
        self.assertEqual(message.subject, 'Test subject', 'Should have created a <mail.group.message>')

        with self.mock_mail_gateway():
            self.format_and_process(
                GROUP_TEMPLATE, self.email_from_unknown, self.test_group.alias_id.display_name,
                subject='Another subject', msg_id='<test.message.id@localhost>', target_model='mail.group')

        new_message = self.env['mail.group.message'].search([('mail_message_id.message_id', '=', '<test.message.id@localhost>')])
        self.assertEqual(new_message, message)

    @mute_logger('odoo.addons.mail.models.mail_thread', 'odoo.addons.mail_group.models.mail_group_message')
    def test_email_not_sent_to_author(self):
        """Test that when someone sends an email the group process does not send
        it back to the original author."""
        self.test_group.write({'moderation': False})

        with self.mock_mail_gateway():
            self.format_and_process(
                GROUP_TEMPLATE, self.test_group_member_1.email,
                self.test_group.alias_id.display_name,
                subject='Test subject', target_model='mail.group')

        mails = self.env['mail.mail'].search([('subject', '=', 'Test subject')])
        self.assertEqual(len(mails), len(self.test_group.member_ids) - 1)
        self.assertNotIn(self.test_group_member_1.email, mails.mapped('email_to'), 'Should not have send the email to the original author')

    @mute_logger('odoo.addons.base.models.ir_rule')
    def test_mail_group_message_security_groups(self):
        user_group = self.env.ref('base.group_partner_manager')
        self.test_group.access_group_id = user_group
        self.test_group.access_mode = 'groups'

        # Message pending
        with self.assertRaises(AccessError, msg='Portal should not have access to pending messages'):
            self.test_group_msg_1_pending.with_user(self.user_portal).check_access_rule('read')

        self.user_portal.groups_id |= user_group
        with self.assertRaises(AccessError, msg='Non moderator should have access to only accepted message'):
            self.test_group_msg_1_pending.with_user(self.user_portal).check_access_rule('read')

        self.test_group_msg_1_pending.invalidate_cache()
        self.assertEqual(self.test_group_msg_1_pending.with_user(self.user_employee).moderation_status, 'pending_moderation',
                         msg='Moderators should have access to pending message')

        # Message accepted
        self.test_group_msg_2_accepted.invalidate_cache()
        self.assertEqual(self.test_group_msg_2_accepted.with_user(self.user_portal).moderation_status, 'accepted',
                         msg='Portal should have access to accepted messages')

        self.user_portal.groups_id -= user_group
        with self.assertRaises(AccessError, msg='User not in the group should not have access to accepted message'):
            self.test_group_msg_2_accepted.with_user(self.user_portal).check_access_rule('read')

    @mute_logger('odoo.addons.base.models.ir_rule')
    def test_mail_group_message_security_public(self):
        self.test_group.access_mode = 'public'

        # Message pending
        with self.assertRaises(AccessError, msg='Portal should not have access to pending messages'):
            self.test_group_msg_1_pending.with_user(self.user_portal).check_access_rule('read')

        with self.assertRaises(AccessError, msg='Non moderator should have access to only accepted message'):
            self.test_group_msg_1_pending.with_user(self.user_employee_2).check_access_rule('read')

        self.test_group_msg_1_pending.invalidate_cache()
        self.assertEqual(self.test_group_msg_1_pending.with_user(self.user_employee).moderation_status, 'pending_moderation',
                         msg='Moderators should have access to pending message')

        # Message rejected
        with self.assertRaises(AccessError, msg='Portal should not have access to pending messages'):
            self.test_group_msg_1_pending.with_user(self.user_portal).check_access_rule('read')

        # Message accepted
        self.assertEqual(self.test_group_msg_2_accepted.with_user(self.user_portal).moderation_status, 'accepted',
                         msg='Portal should have access to accepted messages')

        self.test_group_msg_3_rejected.invalidate_cache()
        self.assertEqual(self.test_group_msg_1_pending.with_user(self.user_admin).moderation_status, 'pending_moderation',
                         msg='Mail Group Administrator should have access to all messages')
