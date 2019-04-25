# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging
import re

from email.utils import formataddr

from odoo import api, fields, models, tools, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

emails_split = re.compile(r"[;,\n\r]+")


class SurveyInvite(models.TransientModel):
    _name = 'survey.invite'
    _description = 'Survey Invitation Wizard'

    @api.model
    def _get_default_from(self):
        if self.env.user.email:
            return formataddr((self.env.user.name, self.env.user.email))
        raise UserError(_("Unable to post message, please configure the sender's email address."))

    @api.model
    def _get_default_author(self):
        return self.env.user.partner_id

    # composer content
    subject = fields.Char('Subject')
    body = fields.Html('Contents', default='', sanitize_style=True)
    attachment_ids = fields.Many2many(
        'ir.attachment', 'survey_mail_compose_message_ir_attachments_rel', 'wizard_id', 'attachment_id',
        string='Attachments')
    template_id = fields.Many2one(
        'mail.template', 'Use template', index=True,
        domain="[('model', '=', 'survey.user_input')]")
    # origin
    email_from = fields.Char('From', default=_get_default_from, help="Email address of the sender.")
    author_id = fields.Many2one(
        'res.partner', 'Author', index=True,
        ondelete='set null', default=_get_default_author,
        help="Author of the message.")
    # recipients
    partner_ids = fields.Many2many(
        'res.partner', 'survey_invite_partner_ids', 'invite_id', 'partner_id', string='Recipients')
    existing_partner_ids = fields.Many2many(
        'res.partner', compute='_compute_existing_partner_ids', readonly=True, store=False)
    emails = fields.Text(string='Additional emails', help="This list of emails of recipients will not be converted in contacts.\
        Emails must be separated by commas, semicolons or newline.")
    existing_emails = fields.Text(
        'Existing emails', compute='_compute_existing_emails',
        readonly=True, store=False)
    existing_mode = fields.Selection([
        ('new', 'New invite'), ('resend', 'Resend invite')],
        string='Handle existing', default='resend', required=True)
    existing_text = fields.Text('Resend Comment', compute='_compute_existing_text', readonly=True, store=False)
    # technical info
    mail_server_id = fields.Many2one('ir.mail_server', 'Outgoing mail server')
    # survey
    survey_id = fields.Many2one('survey.survey', string='Survey', required=True)
    survey_url = fields.Char(related="survey_id.public_url", readonly=True)
    survey_access_mode = fields.Selection(related="survey_id.access_mode", readonly=True)
    survey_users_login_required = fields.Boolean(related="survey_id.users_login_required", readonly=True)
    deadline = fields.Datetime(string="Answer deadline")

    @api.depends('partner_ids', 'survey_id')
    def _compute_existing_partner_ids(self):
        existing_answers = self.survey_id.user_input_ids
        self.existing_partner_ids = existing_answers.mapped('partner_id') & self.partner_ids

    @api.depends('emails', 'survey_id')
    def _compute_existing_emails(self):
        emails = list(set(emails_split.split(self.emails or "")))
        existing_emails = self.survey_id.mapped('user_input_ids.email')
        self.existing_emails = '\n'.join(email for email in emails if email in existing_emails)

    @api.depends('existing_partner_ids', 'existing_emails')
    def _compute_existing_text(self):
        existing_text = False
        if self.existing_partner_ids:
            existing_text = '%s: %s.' % (
                _('The following customers have already received an invite'),
                ', '.join(self.mapped('existing_partner_ids.name'))
            )
        if self.existing_emails:
            existing_text = '%s\n' % existing_text if existing_text else ''
            existing_text += '%s: %s.' % (
                _('The following emails have already received an invite'),
                self.existing_emails
            )

        self.existing_text = existing_text

    @api.onchange('emails')
    def _onchange_emails(self):
        if self.emails and (self.survey_users_login_required and not self.survey_id.users_can_signup):
            raise UserError(_('This survey does not allow external people to participate. You should create user accounts or update survey access mode accordingly.'))
        if not self.emails:
            return
        valid, error = [], []
        emails = list(set(emails_split.split(self.emails or "")))
        for email in emails:
            email_check = tools.email_split_and_format(email)
            if not email_check:
                error.append(email)
            else:
                valid.extend(email_check)
        if error:
            raise UserError(_("Some emails you just entered are incorrect: %s") % (', '.join(error)))
        self.emails = '\n'.join(valid)

    @api.onchange('survey_users_login_required')
    def _onchange_survey_users_login_required(self):
        if self.survey_users_login_required and not self.survey_id.users_can_signup:
            return {'domain': {
                    'partner_ids': [('user_ids', '!=', False)]
                    }}
        return {'domain': {
                'partner_ids': []
                }}

    @api.onchange('partner_ids')
    def _onchange_partner_ids(self):
        if self.survey_users_login_required and self.partner_ids:
            if not self.survey_id.users_can_signup:
                invalid_partners = self.env['res.partner'].search([
                    ('user_ids', '=', False),
                    ('id', 'in', self.partner_ids.ids)
                ])
                if invalid_partners:
                    raise UserError(
                        _('The following recipients have no user account: %s. You should create user accounts for them or allow external signup in configuration.' %
                            (','.join(invalid_partners.mapped('name')))))

    @api.onchange('template_id')
    def _onchange_template_id(self):
        """ UPDATE ME """
        if self.template_id:
            self.subject = self.template_id.subject
            self.body = self.template_id.body_html

    @api.model
    def create(self, values):
        if values.get('template_id') and not (values.get('body') or values.get('subject')):
            template = self.env['mail.template'].browse(values['template_id'])
            if not values.get('subject'):
                values['subject'] = template.subject
            if not values.get('body'):
                values['body'] = template.body_html
        return super(SurveyInvite, self).create(values)

    #------------------------------------------------------
    # Wizard validation and send
    #------------------------------------------------------

    def _prepare_answers(self, partners, emails):
        answers = self.env['survey.user_input']
        existing_answers = self.env['survey.user_input'].search([
            '&', ('survey_id', '=', self.survey_id.id),
            '|',
            ('partner_id', 'in', partners.ids),
            ('email', 'in', emails)
        ])
        partners_done = self.env['res.partner']
        emails_done = []
        if existing_answers:
            if self.existing_mode == 'resend':
                partners_done = existing_answers.mapped('partner_id')
                emails_done = existing_answers.mapped('email')

                # only add the last answer for each user of each type (partner_id & email)
                # to have only one mail sent per user
                for partner_done in partners_done:
                    answers |= next(existing_answer for existing_answer in
                        existing_answers.sorted(lambda answer: answer.create_date, reverse=True)
                        if existing_answer.partner_id == partner_done)

                for email_done in emails_done:
                    answers |= next(existing_answer for existing_answer in
                        existing_answers.sorted(lambda answer: answer.create_date, reverse=True)
                        if existing_answer.email == email_done)

        for new_partner in partners - partners_done:
            answers |= self.survey_id._create_answer(partner=new_partner, check_attempts=False, **self._get_answers_values())
        for new_email in [email for email in emails if email not in emails_done]:
            answers |= self.survey_id._create_answer(email=new_email, check_attempts=False, **self._get_answers_values())

        return answers

    def _get_answers_values(self):
        return {
            'input_type': 'link',
            'deadline': self.deadline,
        }

    def _send_mail(self, answer):
        """ Create mail specific for recipient containing notably its access token """
        subject = self.env['mail.template']._render_template(self.subject, 'survey.user_input', answer.id, post_process=True)
        body = self.env['mail.template']._render_template(self.body, 'survey.user_input', answer.id, post_process=True)
        # post the message
        mail_values = {
            'email_from': self.email_from,
            'author_id': self.author_id.id,
            'model': None,
            'res_id': None,
            'subject': subject,
            'body_html': body,
            'attachment_ids': [(4, att.id) for att in self.attachment_ids],
            'auto_delete': True,
        }
        if answer.partner_id:
            mail_values['recipient_ids'] = [(4, answer.partner_id.id)]
        else:
            mail_values['email_to'] = answer.email

        # optional support of notif_layout in context
        notif_layout = self.env.context.get('notif_layout', self.env.context.get('custom_layout'))
        if notif_layout:
            try:
                template = self.env.ref(notif_layout, raise_if_not_found=True)
            except ValueError:
                _logger.warning('QWeb template %s not found when sending survey mails. Sending without layouting.' % (notif_layout))
            else:
                template_ctx = {
                    'message': self.env['mail.message'].sudo().new(dict(body=mail_values['body_html'], record_name=self.survey_id.title)),
                    'model_description': self.env['ir.model']._get('survey.survey').display_name,
                    'company': self.env.company_id,
                }
                body = template.render(template_ctx, engine='ir.qweb', minimal_qcontext=True)
                mail_values['body_html'] = self.env['mail.thread']._replace_local_links(body)

        return self.env['mail.mail'].sudo().create(mail_values)

    @api.multi
    def action_invite(self):
        """ Process the wizard content and proceed with sending the related
            email(s), rendering any template patterns on the fly if needed """
        self.ensure_one()
        Partner = self.env['res.partner']

        # compute partners and emails, try to find partners for given emails
        valid_partners = self.partner_ids
        valid_emails = []
        for email in emails_split.split(self.emails or ''):
            partner = False
            email_normalized = tools.email_normalize(email)
            if email_normalized:
                partner = Partner.search([('email_normalized', '=', email_normalized)])
            if partner:
                valid_partners |= partner
            else:
                email_formatted = tools.email_split_and_format(email)
                if email_formatted:
                    valid_emails.extend(email_formatted)

        if not valid_partners and not valid_emails:
            raise UserError(_("Please enter at least one valid recipient."))

        answers = self._prepare_answers(valid_partners, valid_emails)
        for answer in answers:
            self._send_mail(answer)

        return {'type': 'ir.actions.act_window_close'}
