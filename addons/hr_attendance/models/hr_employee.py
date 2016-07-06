# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from random import choice
from string import digits

from odoo import models, fields, api, exceptions, _, SUPERUSER_ID


class HrEmployee(models.Model):
    _inherit = "hr.employee"
    _description = "Employee"

    def _default_random_pin(self):
        return ("".join(choice(digits) for i in range(4)))

    def _default_random_barcode(self):
        barcode = None
        while not barcode or self.env['hr.employee'].search([('barcode', '=', barcode)]):
            barcode = "".join(choice(digits) for i in range(8))
        return barcode

    barcode = fields.Char(string="Badge ID", help="ID used for employee identification.", default=_default_random_barcode, copy=False, groups='base.group_hr_user')
    pin = fields.Char(string="PIN", default=_default_random_pin, help="PIN used for Check In/Out in Attendance.", copy=False, groups='base.group_hr_user')

    attendance_ids = fields.One2many('hr.attendance', 'employee_id', help='list of attendances for the employee')
    last_attendance_id = fields.Many2one('hr.attendance', compute='_compute_last_attendance_id')
    attendance_state = fields.Selection(string="Attendance", compute='_compute_attendance_state', selection=[('checked_out', "Checked out"), ('checked_in', "Checked in")])
    manual_attendance = fields.Boolean(string='Manual Attendance', compute='_compute_manual_attendance', inverse='_inverse_manual_attendance',
                                       help='The employee will have access to the "My Attendances" menu to perform his check in and out from his session', default=False)

    _sql_constraints = [('barcode_uniq', 'unique (barcode)', "The Badge ID must be unique, this one is already assigned to another employee.")]

    @api.multi
    def _compute_manual_attendance(self):
        for employee in self:
            employee.manual_attendance = employee.user_id.has_group('base.group_hr_attendance') if employee.user_id else False

    @api.multi
    def _inverse_manual_attendance(self):
        manual_attendance_group = self.env['res.groups'].search([('name', '=', 'Manual Attendances')])
        for employee in self:
            if employee.user_id:
                if employee.manual_attendance:
                    manual_attendance_group.users = [(4, employee.user_id.id, 0)]
                else:
                    manual_attendance_group.users = [(3, employee.user_id.id, 0)]

    @api.depends('attendance_ids')
    def _compute_last_attendance_id(self):
        for employee in self:
            employee.last_attendance_id = employee.attendance_ids and employee.attendance_ids[0] or False

    @api.depends('last_attendance_id.check_in', 'last_attendance_id.check_out', 'last_attendance_id')
    def _compute_attendance_state(self):
        """compute employee state, last check in and last check out
        """
        for employee in self:
            employee.attendance_state = employee.last_attendance_id and not employee.last_attendance_id.check_out and 'checked_in' or 'checked_out'

    @api.constrains('pin')
    def _verify_pin(self):
        for employee in self:
            if employee.pin and not employee.pin.isdigit():
                raise exceptions.ValidationError(_("The PIN must be a sequence of digits."))

    @api.model
    def attendance_scan(self, barcode):
        """ Receive a barcode scanned from the main menu and change the attendances of corresponding employee.
            Returns either an action or a warning.
        """
        employee = self.search([('barcode', '=', barcode)], limit=1)
        return employee and employee.attendance_action('hr_attendance.hr_attendance_action_main_menu') or \
            {'warning': _('No employee corresponding to barcode %(barcode)s') % {'barcode': barcode}}

    @api.multi
    def attendance_manual(self, next_action, entered_pin=None):
        self.ensure_one()
        if self.env['res.users'].browse(SUPERUSER_ID).has_group('base.group_hr_attendance_use_pin') and (self.user_id and self.user_id.id != self._uid or not self.user_id):
            if entered_pin != self.pin:
                return {'warning': _('Wrong PIN')}
        return self.attendance_action(next_action)

    @api.multi
    def attendance_action(self, next_action):
        """ Changes the attendance of the employee.
            Returns an action to the check in/out message,
            next_action defines which menu the check in/out message should return to.
        """
        self.ensure_one()
        action_message = self.env.ref('hr_attendance.hr_attendance_action_message').read()[0]
        action_message['previous_attendance_change_date'] = self.last_attendance_id and (self.last_attendance_id.check_out or self.last_attendance_id.check_in) or False
        if action_message['previous_attendance_change_date']:
            action_message['previous_attendance_change_date'] = \
                fields.Datetime.to_string(fields.Datetime.context_timestamp(self, fields.Datetime.from_string(action_message['previous_attendance_change_date'])))
        action_message['employee_name'] = self.name
        action_message['next_action'] = next_action

        if self.user_id:
            modified_attendance = self.sudo(self.user_id.id).attendance_action_change()
        else:
            modified_attendance = self.sudo().attendance_action_change()
        action_message['attendance'] = modified_attendance.read()[0]
        return {'action': action_message}

    @api.multi
    def attendance_action_change(self):
        """ Check In/Check Out action
            Check In: create a new attendance record
            Check Out: modify check_out field of appropriate attendance record
        """
        if len(self) > 1:
            raise exceptions.UserError(_('Cannot perform check in or check out on multiple employees.'))
        action_date = fields.Datetime.now()

        action = 'check_in'
        if self.attendance_state == 'checked_in':
            action = 'check_out'

        if action == 'check_in':
            vals = {
                'employee_id': self.id,
                'check_in': action_date,
            }
            return self.env['hr.attendance'].create(vals)
        else:
            attendance = self.env['hr.attendance'].search([('employee_id', '=', self.id), ('check_out', '=', False)], limit=1)
            if attendance:
                attendance.check_out = action_date
            else:
                raise exceptions.UserError(_('Cannot perform check out on %(empl_name)s, could not find corresponding check in. \
                    Your attendances have probably been modified manually by human resources.') % {'empl_name': self.name, })
            return attendance

    def _init_column(self, cr, column_name, context=None):
        """ Initialize the value of the given column for existing rows.
            Overridden here because we need to have different default values
            for barcode and pin for every employee.
        """
        if column_name not in ["barcode", "pin"]:
            super(HrEmployee, self)._init_column(cr, column_name, context=context)
        else:
            default_compute = self._defaults.get(column_name)

            query = 'SELECT id FROM "%s" WHERE "%s" is NULL' % (
                self._table, column_name)
            cr.execute(query)
            employee_ids = cr.fetchall()

            for employee_id in employee_ids:
                default_value = default_compute(self, cr, SUPERUSER_ID, context)

                query = 'UPDATE "%s" SET "%s"=%%s WHERE id = %s' % (
                    self._table, column_name, employee_id[0])
                cr.execute(query, (default_value,))
