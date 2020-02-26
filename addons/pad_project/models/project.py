# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class ProjectTask(models.Model):
    _name = "project.task"
    _inherit = ["project.task", 'pad.common']
    _description = 'Task'

    description_pad = fields.Char('Pad URL', pad_content_field='description', copy=False)
    use_pad = fields.Boolean(related="project_id.use_pads", string="Use collaborative pad", readonly=True)
    pad_availability = fields.Selection(
        related="project_id.pad_availability",
        string="Availability of collaborative pads",
        readonly=True)

    @api.model
    def create(self, vals):
        # When using quick create, the project_id is in the context, not in the vals
        project_id = vals.get('project_id', False) or self.default_get(['project_id']).get('project_id', False)
        if not self.env['project.project'].browse(project_id).use_pads:
            self = self.with_context(pad_no_create=True)
        return super(ProjectTask, self).create(vals)

    def _use_portal_pad(self):
        """
        Indicates if the task configuration requires to provide
        an access to a portal pad.
        """
        self.ensure_one()
        return self.use_pad and self.pad_availability == 'portal'

    def _get_pad_content(self):
        """
        Gets the content of the pad used to edit the task description
        and returns it.
        """
        self.ensure_one()
        return self.pad_get_content(self.description_pad)


class ProjectProject(models.Model):
    _inherit = "project.project"

    use_pads = fields.Boolean("Use collaborative pads", default=True,
        help="Use collaborative pad for the tasks on this project.")

    pad_availability = fields.Selection([
        ('internal', 'Internal Users'),
        ('portal', 'Portal Users')
        ], compute='_compute_pad_availability', store=True, readonly=False,
        string='Availability of collaborative pads', required=True, default='internal')

    @api.depends('use_pads', 'privacy_visibility')
    def _compute_pad_availability(self):
        for project in self:
            if project.privacy_visibility != 'portal' or not project.use_pads:
                project.pad_availability = 'internal'
