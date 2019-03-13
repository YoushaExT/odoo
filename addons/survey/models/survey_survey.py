# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import uuid

from collections import Counter, OrderedDict
from itertools import product
from werkzeug import urls
import random

from odoo import api, fields, models, SUPERUSER_ID, _
from odoo.exceptions import UserError
from odoo.osv import expression


class Survey(models.Model):
    """ Settings for a multi-page/multi-question survey. Each survey can have one or more attached pages
    and each page can display one or more questions. """
    _name = 'survey.survey'
    _description = 'Survey'
    _rec_name = 'title'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    def _get_default_stage_id(self):
        return self.env['survey.stage'].search([], limit=1).id

    def _get_default_access_token(self):
        return str(uuid.uuid4())

    # description
    title = fields.Char('Title', required=True, translate=True)
    description = fields.Html("Description", translate=True, help="A long description of the purpose of the survey")
    color = fields.Integer('Color Index', default=0)
    thank_you_message = fields.Html("Thanks Message", translate=True, help="This message will be displayed when survey is completed")
    active = fields.Boolean("Active", default=True)
    question_and_page_ids = fields.One2many('survey.question', 'survey_id', string='Sections and Questions', copy=True)
    page_ids = fields.One2many('survey.question', string='Pages', compute="_compute_page_and_question_ids")
    question_ids = fields.One2many('survey.question', string='Questions', compute="_compute_page_and_question_ids")
    stage_id = fields.Many2one('survey.stage', string="Stage", default=lambda self: self._get_default_stage_id(),
                               ondelete="restrict", copy=False, group_expand='_read_group_stage_ids')
    is_closed = fields.Boolean("Is closed", related='stage_id.closed', readonly=True)
    questions_layout = fields.Selection([
        ('one_page', 'One page with all the questions'),
        ('page_per_section', 'One page per section'),
        ('page_per_question', 'One page per question')],
        string="Layout", required=True, default='one_page')
    questions_selection = fields.Selection([
        ('all', 'All questions'),
        ('random', 'Randomized per section')],
        string="Selection", required=True, default='all',
        help="If randomized is selected, add the number of random questions next to the section.")

    category = fields.Selection([
        ('default', 'Generic Survey')], string='Category',
        default='default', required=True,
        help='Category is used to know in which context the survey is used. Various apps may define their own categories when they use survey like jobs recruitment or employee appraisal surveys.')
    # content
    user_input_ids = fields.One2many('survey.user_input', 'survey_id', string='User responses', readonly=True, groups='survey.group_survey_user')
    # security / access
    access_mode = fields.Selection([
        ('public', 'Anyone with the link'),
        ('token', 'Invited people only')], string='Access Mode',
        default='public', required=True)
    access_token = fields.Char('Access Token', default=lambda self: self._get_default_access_token(), copy=False)
    users_login_required = fields.Boolean('Login required', help="If checked, users have to login before answering even with a valid token.")
    users_can_go_back = fields.Boolean('Users can go back', help="If checked, users can go back to previous pages.")
    users_can_signup = fields.Boolean('Users can signup', compute='_compute_users_can_signup')
    public_url = fields.Char("Public link", compute="_compute_survey_url")
    # statistics
    invite_count = fields.Integer("Invite", compute="_compute_survey_statistic")
    answer_count = fields.Integer("Started", compute="_compute_survey_statistic")
    answer_done_count = fields.Integer("Completed", compute="_compute_survey_statistic")
    certified_count = fields.Integer("Certified", compute="_compute_certified_count")

    # scoring and certification fields
    scoring_type = fields.Selection([
        ('no_scoring', 'No scoring'),
        ('scoring_with_answers', 'Scoring with answers at the end'),
        ('scoring_without_answers', 'Scoring without answers at the end')],
        string="Scoring", required=True, default='no_scoring')
    passing_score = fields.Float('Passing score (%)', required=True, default=80.0)
    is_attempts_limited = fields.Boolean('Limited number of attempts',
        help="Check this option if you want to limit the number of attempts per user")
    attempts_limit = fields.Integer('Number of attempts', default=1)
    is_time_limited = fields.Boolean('The survey is limited in time')
    time_limit = fields.Float("Time limit (minutes)")
    certificate = fields.Boolean('Certificate')
    certification_mail_template_id = fields.Many2one(
        'mail.template', 'Certification Email Template',
        domain="[('model', '=', 'survey.user_input')]",
        help="Automated email sent to the user when he succeeds the certification, containing his certification document.")

    _sql_constraints = [
        ('access_token_unique', 'unique(access_token)', 'Access token should be unique'),
        ('certificate_check', "CHECK( scoring_type!='no_scoring' OR certificate=False )", 'You can only create certifications for surveys that have a scoring mechanism.'),
        ('time_limit_check', "CHECK( (is_time_limited=False) OR (time_limit is not null AND time_limit > 0) )", 'The time limit needs to be a positive number if the survey is time limited.'),
        ('attempts_limit_check', "CHECK( (is_attempts_limited=False) OR (attempts_limit is not null AND attempts_limit > 0) )", 'The attempts limit needs to be a positive number if the survey has a limited number of attempts.')
    ]

    @api.multi
    def _compute_users_can_signup(self):
        signup_allowed = self.env['res.users'].sudo()._get_signup_invitation_scope() == 'b2c'
        for survey in self:
            survey.users_can_signup = signup_allowed

    @api.depends('user_input_ids.state', 'user_input_ids.test_entry')
    def _compute_survey_statistic(self):
        stat = dict((cid, dict(invite_count=0, answer_count=0, answer_done_count=0)) for cid in self.ids)
        UserInput = self.env['survey.user_input']
        base_domain = ['&', ('survey_id', 'in', self.ids), ('test_entry', '!=', True)]

        read_group_res = UserInput.read_group(base_domain, ['input_type', 'state'], ['survey_id', 'input_type', 'state'], lazy=False)
        for item in read_group_res:
            stat[item['survey_id'][0]]['answer_count'] += item['__count']
            if item['state'] == 'done':
                stat[item['survey_id'][0]]['answer_done_count'] += item['__count']
            if item['input_type'] == 'link':
                stat[item['survey_id'][0]]['invite_count'] += item['__count']

        for survey in self:
            survey.update(stat[survey.id])

    @api.depends('certificate', 'user_input_ids.quizz_passed', 'user_input_ids.test_entry')
    def _compute_certified_count(self):
        stat = dict((cid, 0) for cid in self.ids)
        certificate_surveys = self.filtered(lambda survey: survey.certificate)
        if certificate_surveys:
            read_group_res = self.env['survey.user_input'].read_group(
                [('survey_id', 'in', certificate_surveys.ids), ('test_entry', '!=', True), ('quizz_passed', '=', True)],
                [],
                ['survey_id']
            )
            for item in read_group_res:
                stat[item['survey_id'][0]] += item['survey_id_count']

        for survey in self:
            survey.certified_count = stat.get(survey.id, 0)

    def _compute_survey_url(self):
        """ Computes a public URL for the survey """
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        for survey in self:
            survey.public_url = urls.url_join(base_url, "survey/start/%s" % (survey.access_token))

    @api.depends('question_and_page_ids')
    def _compute_page_and_question_ids(self):
        for survey in self:
            survey.page_ids = survey.question_and_page_ids.filtered(lambda question: question.is_page)
            survey.question_ids = survey.question_and_page_ids - survey.page_ids

    @api.onchange('passing_score')
    def _onchange_passing_score(self):
        if self.passing_score < 0 or self.passing_score > 100:
            self.passing_score = 80.0

    @api.onchange('scoring_type')
    def _onchange_scoring_type(self):
        if self.scoring_type != 'no_scoring':
            self.certificate = False

    @api.onchange('users_login_required', 'access_mode')
    def _onchange_access_mode(self):
        if self.access_mode == 'public' and not self.users_login_required:
            self.is_attempts_limited = False

    @api.onchange('attempts_limit')
    def _onchange_attempts_limit(self):
        if self.attempts_limit <= 0:
            self.attempts_limit = 1

    @api.onchange('is_time_limited', 'time_limit')
    def _onchange_time_limit(self):
        if self.is_time_limited and (not self.time_limit or self.time_limit <= 0):
            self.time_limit = 10

    @api.model
    def _read_group_stage_ids(self, stages, domain, order):
        """ Read group customization in order to display all the stages in the
            kanban view, even if they are empty
        """
        stage_ids = stages._search([], order=order, access_rights_uid=SUPERUSER_ID)
        return stages.browse(stage_ids)

    # Public methods #
    def copy_data(self, default=None):
        title = _("%s (copy)") % (self.title)
        default = dict(default or {}, title=title)
        return super(Survey, self).copy_data(default)

    @api.multi
    def _create_answer(self, user=False, partner=False, email=False, test_entry=False, check_attempts=True, **additional_vals):
        """ Main entry point to get a token back or create a new one. This method
        does check for current user access in order to explicitely validate
        security.

          :param user: target user asking for a token; it might be void or a
                       public user in which case an email is welcomed;
          :param email: email of the person asking the token is no user exists;
        """
        self.check_access_rights('read')
        self.check_access_rule('read')

        answers = self.env['survey.user_input']
        for survey in self:
            if partner and not user and partner.user_ids:
                user = partner.user_ids[0]

            invite_token = additional_vals.pop('invite_token', False)
            survey._check_answer_creation(user, partner, email, test_entry=test_entry, check_attempts=check_attempts, invite_token=invite_token)
            answer_vals = {
                'survey_id': survey.id,
                'test_entry': test_entry,
                'question_ids': [(6, 0, survey._prepare_answer_questions().ids)]
            }
            if user and not user._is_public():
                answer_vals['partner_id'] = user.partner_id.id
                answer_vals['email'] = user.email
            elif partner:
                answer_vals['partner_id'] = partner.id
                answer_vals['email'] = partner.email
            else:
                answer_vals['email'] = email

            if invite_token:
                answer_vals['invite_token'] = invite_token
            elif survey.is_attempts_limited and survey.access_mode != 'public':
                # attempts limited: create a new invite_token
                # exception made for 'public' access_mode since the attempts pool is global because answers are
                # created every time the user lands on '/start'
                answer_vals['invite_token'] = self.env['survey.user_input']._generate_invite_token()

            answer_vals.update(additional_vals)
            answers += answers.create(answer_vals)

        return answers

    @api.multi
    def _check_answer_creation(self, user, partner, email, test_entry=False, check_attempts=True, invite_token=False):
        """ Ensure conditions to create new tokens are met. """
        self.ensure_one()
        if test_entry:
            if not user.has_group('survey.group_survey_manager') or not user.has_group('survey.group_survey_user'):
                raise UserError(_('Creating test token is not allowed for you.'))
        else:
            if not self.active:
                raise UserError(_('Creating token for archived surveys is not allowed.'))
            elif self.is_closed:
                raise UserError(_('Creating token for closed surveys is not allowed.'))
            if self.access_mode == 'authentication':
                # signup possible -> should have at least a partner to create an account
                if self.users_can_signup and not user and not partner:
                    raise UserError(_('Creating token for external people is not allowed for surveys requesting authentication.'))
                # no signup possible -> should be a not public user (employee or portal users)
                if not self.users_can_signup and (not user or user._is_public()):
                    raise UserError(_('Creating token for external people is not allowed for surveys requesting authentication.'))
            if self.access_mode == 'internal' and (not user or not user.has_group('base.group_user')):
                raise UserError(_('Creating token for anybody else than employees is not allowed for internal surveys.'))
            if check_attempts and not self._has_attempts_left(partner or (user and user.partner_id), email, invite_token):
                raise UserError(_('No attempts left.'))

    @api.model
    def next_page_or_question(self, user_input, page_or_question_id, go_back=False):
        """ The next page to display to the user, knowing that page_id is the id
            of the last displayed page.

            If page_id == 0, it will always return the first page of the survey.

            If all the pages have been displayed and go_back == False, it will
            return None

            If go_back == True, it will return the *previous* page instead of the
            next page.

            .. note::
                It is assumed here that a careful user will not try to set go_back
                to True if she knows that the page to display is the first one!
                (doing this will probably cause a giant worm to eat her house)
        """
        survey = user_input.survey_id

        if survey.questions_layout == 'page_per_question' and survey.questions_selection == 'random':
            pages_or_questions = list(enumerate(
                user_input.question_ids
            ))
        else:
            pages_or_questions = list(enumerate(
                survey.question_ids if survey.questions_layout == 'page_per_question' else survey.page_ids
            ))

        # First page
        if page_or_question_id == 0:
            return (pages_or_questions[0][1], len(pages_or_questions) == 1)

        current_page_index = pages_or_questions.index(next(p for p in pages_or_questions if p[1].id == page_or_question_id))

        # All the pages have been displayed
        if current_page_index == len(pages_or_questions) - 1 and not go_back:
            return (None, False)
        # Let's get back, baby!
        elif go_back and survey.users_can_go_back:
            return (pages_or_questions[current_page_index - 1][1], False)
        else:
            # This will show the last page
            if current_page_index == len(pages_or_questions) - 2:
                return (pages_or_questions[current_page_index + 1][1], True)
            # This will show a regular page
            else:
                return (pages_or_questions[current_page_index + 1][1], False)

    @api.multi
    def filter_input_ids(self, filters, finished=False):
        """If user applies any filters, then this function returns list of
           filtered user_input_id and label's strings for display data in web.
           :param filters: list of dictionary (having: row_id, ansewr_id)
           :param finished: True for completely filled survey,Falser otherwise.
           :returns list of filtered user_input_ids.
        """
        self.ensure_one()
        if filters:
            domain_filter, choice = [], []
            for current_filter in filters:
                row_id, answer_id = current_filter['row_id'], current_filter['answer_id']
                if row_id == 0:
                    choice.append(answer_id)
                else:
                    domain_filter.extend(['|', ('value_suggested_row.id', '=', row_id), ('value_suggested.id', '=', answer_id)])
            if choice:
                domain_filter.insert(0, ('value_suggested.id', 'in', choice))
            else:
                domain_filter = domain_filter[1:]
            input_lines = self.env['survey.user_input_line'].search(domain_filter)
            filtered_input_ids = [input_line.user_input_id.id for input_line in input_lines]
        else:
            filtered_input_ids = []
        if finished:
            UserInput = self.env['survey.user_input']
            if not filtered_input_ids:
                user_inputs = UserInput.search([('survey_id', '=', self.id)])
            else:
                user_inputs = UserInput.browse(filtered_input_ids)
            return user_inputs.filtered(lambda input_item: input_item.state == 'done').ids
        return filtered_input_ids

    @api.model
    def get_filter_display_data(self, filters):
        """Returns data to display current filters
            :param filters: list of dictionary (having: row_id, answer_id)
            :returns list of dict having data to display filters.
        """
        filter_display_data = []
        if filters:
            Label = self.env['survey.label']
            for current_filter in filters:
                row_id, answer_id = current_filter['row_id'], current_filter['answer_id']
                label = Label.browse(answer_id)
                question = label.question_id
                if row_id == 0:
                    labels = label
                else:
                    labels = Label.browse([row_id, answer_id])
                filter_display_data.append({'question_text': question.question,
                                            'labels': labels.mapped('value')})
        return filter_display_data

    @api.model
    def prepare_result(self, question, current_filters=None):
        """ Compute statistical data for questions by counting number of vote per choice on basis of filter """
        current_filters = current_filters if current_filters else []
        result_summary = {}
        input_lines = question.user_input_line_ids.filtered(lambda line: not line.user_input_id.test_entry)

        # Calculate and return statistics for choice
        if question.question_type in ['simple_choice', 'multiple_choice']:
            comments = []
            answers = OrderedDict((label.id, {'text': label.value, 'count': 0, 'answer_id': label.id, 'answer_score': label.answer_score}) for label in question.labels_ids)
            for input_line in input_lines:
                if input_line.answer_type == 'suggestion' and answers.get(input_line.value_suggested.id) and (not(current_filters) or input_line.user_input_id.id in current_filters):
                    answers[input_line.value_suggested.id]['count'] += 1
                if input_line.answer_type == 'text' and (not(current_filters) or input_line.user_input_id.id in current_filters):
                    comments.append(input_line)
            result_summary = {'answers': list(answers.values()), 'comments': comments}

        # Calculate and return statistics for matrix
        if question.question_type == 'matrix':
            rows = OrderedDict()
            answers = OrderedDict()
            res = dict()
            comments = []
            [rows.update({label.id: label.value}) for label in question.labels_ids_2]
            [answers.update({label.id: label.value}) for label in question.labels_ids]
            for cell in product(rows, answers):
                res[cell] = 0
            for input_line in input_lines:
                if input_line.answer_type == 'suggestion' and (not(current_filters) or input_line.user_input_id.id in current_filters) and input_line.value_suggested_row:
                    res[(input_line.value_suggested_row.id, input_line.value_suggested.id)] += 1
                if input_line.answer_type == 'text' and (not(current_filters) or input_line.user_input_id.id in current_filters):
                    comments.append(input_line)
            result_summary = {'answers': answers, 'rows': rows, 'result': res, 'comments': comments}

        # Calculate and return statistics for free_text, textbox, date
        if question.question_type in ['free_text', 'textbox', 'date', 'datetime']:
            result_summary = []
            for input_line in input_lines:
                if not(current_filters) or input_line.user_input_id.id in current_filters:
                    result_summary.append(input_line)

        # Calculate and return statistics for numerical_box
        if question.question_type == 'numerical_box':
            result_summary = {'input_lines': []}
            all_inputs = []
            for input_line in input_lines:
                if not(current_filters) or input_line.user_input_id.id in current_filters:
                    all_inputs.append(input_line.value_number)
                    result_summary['input_lines'].append(input_line)
            if all_inputs:
                result_summary.update({'average': round(sum(all_inputs) / len(all_inputs), 2),
                                       'max': round(max(all_inputs), 2),
                                       'min': round(min(all_inputs), 2),
                                       'sum': sum(all_inputs),
                                       'most_common': Counter(all_inputs).most_common(5)})
        return result_summary

    @api.model
    def get_input_summary(self, question, current_filters=None):
        """ Returns overall summary of question e.g. answered, skipped, total_inputs on basis of filter """
        current_filters = current_filters if current_filters else []
        result = {}
        search_line_ids = current_filters if current_filters else question.user_input_line_ids.ids

        result['answered'] = len([line for line in question.user_input_line_ids if line.user_input_id.state != 'new' and not line.user_input_id.test_entry and not line.skipped])
        result['skipped'] = len([line for line in question.user_input_line_ids if line.user_input_id.state != 'new' and not line.user_input_id.test_entry and line.skipped])

        return result

    # Actions

    @api.multi
    def action_start_survey(self):
        """ Open the website page with the survey form """
        self.ensure_one()
        token = self.env.context.get('survey_token')
        trail = "?answer_token=%s" % token if token else ""
        return {
            'type': 'ir.actions.act_url',
            'name': "Start Survey",
            'target': 'self',
            'url': self.public_url + trail
        }

    @api.multi
    def action_send_survey(self):
        """ Open a window to compose an email, pre-filled with the survey message """
        # Ensure that this survey has at least one page with at least one question.
        if (not self.page_ids and self.questions_layout != 'page_per_question') or not self.question_ids:
            raise UserError(_('You cannot send an invitation for a survey that has no questions.'))

        if self.stage_id.closed:
            raise UserError(_("You cannot send invitations for closed surveys."))

        template = self.env.ref('survey.mail_template_user_input_invite', raise_if_not_found=False)

        local_context = dict(
            self.env.context,
            default_survey_id=self.id,
            default_use_template=bool(template),
            default_template_id=template and template.id or False,
            notif_layout='mail.mail_notification_light',
        )
        return {
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'survey.invite',
            'target': 'new',
            'context': local_context,
        }

    @api.multi
    def action_print_survey(self):
        """ Open the website page with the survey printable view """
        self.ensure_one()
        token = self.env.context.get('survey_token')
        trail = "?answer_token=%s" % token if token else ""
        return {
            'type': 'ir.actions.act_url',
            'name': "Print Survey",
            'target': 'self',
            'url': '/survey/print/%s%s' % (self.access_token, trail)
        }

    @api.multi
    def action_result_survey(self):
        """ Open the website page with the survey results view """
        self.ensure_one()
        return {
            'type': 'ir.actions.act_url',
            'name': "Results of the Survey",
            'target': 'self',
            'url': '/survey/results/%s' % self.id
        }

    @api.multi
    def action_test_survey(self):
        ''' Open the website page with the survey form into test mode'''
        self.ensure_one()
        return {
            'type': 'ir.actions.act_url',
            'name': "Test Survey",
            'target': 'self',
            'url': '/survey/test/%s' % self.access_token,
        }

    @api.multi
    def action_survey_user_input_completed(self):
        action_rec = self.env.ref('survey.action_survey_user_input_notest')
        action = action_rec.read()[0]
        ctx = dict(self.env.context)
        ctx.update({'search_default_survey_id': self.ids[0],
                    'search_default_completed': 1})
        action['context'] = ctx
        return action

    @api.multi
    def action_survey_user_input_certified(self):
        action_rec = self.env.ref('survey.action_survey_user_input_notest')
        action = action_rec.read()[0]
        ctx = dict(self.env.context)
        ctx.update({'search_default_survey_id': self.ids[0],
                    'search_default_quizz_passed': 1})
        action['context'] = ctx
        return action

    @api.multi
    def action_survey_user_input_invite(self):
        action_rec = self.env.ref('survey.action_survey_user_input_notest')
        action = action_rec.read()[0]
        ctx = dict(self.env.context)
        ctx.update({'search_default_survey_id': self.ids[0],
                    'search_default_invite': 1})
        action['context'] = ctx
        return action

    @api.multi
    def _has_attempts_left(self, partner, email, invite_token):
        self.ensure_one()

        if (self.access_mode != 'public' or self.users_login_required) and self.is_attempts_limited:
            return self._get_number_of_attempts_lefts(partner, email, invite_token) > 0

        return True

    @api.multi
    def _get_number_of_attempts_lefts(self, partner, email, invite_token):
        """ Returns the number of attempts left. """
        self.ensure_one()

        domain = [
            ('survey_id', '=', self.id),
            ('test_entry', '=', False),
            ('state', '=', 'done')
        ]

        if partner:
            domain = expression.AND([domain, [('partner_id', '=', partner.id)]])
        else:
            domain = expression.AND([domain, [('email', '=', email)]])

        if invite_token:
            domain = expression.AND([domain, [('invite_token', '=', invite_token)]])

        return self.attempts_limit - self.env['survey.user_input'].search_count(domain)

    @api.multi
    def _prepare_answer_questions(self):
        """ Will generate the questions for a randomized survey.
        It uses the random_questions_count of every sections of the survey to
        pick a random number of questions and returns the merged recordset """
        self.ensure_one()

        questions = self.env['survey.question']

        for page in self.page_ids:
            if self.questions_selection == 'all':
                questions |= page.question_ids
            else:
                if page.random_questions_count > 0 and len(page.question_ids) > page.random_questions_count:
                    questions = questions.concat(*random.sample(page.question_ids, page.random_questions_count))
                else:
                    questions |= page.question_ids

        if not questions:
            questions = self.question_ids

        return questions
