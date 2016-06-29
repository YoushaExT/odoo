# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class RecruitmentSettings(models.TransientModel):
    _name = 'hr.recruitment.config.settings'
    _inherit = ['res.config.settings']

    module_document = fields.Selection(selection=[
        (0, "Do not manage CVs and motivation letter"),
        (1, 'Allow the automatic indexation of resumes')
        ], string='Resumes')

    module_hr_recruitment_survey = fields.Selection(selection=[
        (0, "Do not use interview forms"),
        (1, "Use interview forms during the recruitment process")
        ], string='Interview Form')
