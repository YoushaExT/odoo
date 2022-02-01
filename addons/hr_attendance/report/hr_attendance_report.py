# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models
from datetime import datetime
import pytz


class HRAttendanceReport(models.Model):
    _name = "hr.attendance.report"
    _description = "Attendance Statistics"
    _auto = False

    department_id = fields.Many2one('hr.department', string="Department", readonly=True)
    employee_id = fields.Many2one('hr.employee', string="Employee", readonly=True)
    check_in = fields.Date("Check In", readonly=True)
    worked_hours = fields.Float("Hours Worked Total", readonly=True)
    daily_hours = fields.Float("Hours Worked", readonly=True, group_operator="avg")
    check_in_time = fields.Float("Check In Time", readonly=True, group_operator="avg")
    check_out_time = fields.Float("Check Out Time", readonly=True, group_operator="avg")
    adjusted_check_in_time = fields.Float("Check In Time*", readonly=True, group_operator="avg")
    adjusted_check_out_time = fields.Float("Check Out Time*", readonly=True, group_operator="avg")

    # disabled this in views
    # overtime_hours = fields.Float("Extra Hours", readonly=True)

    def init(self):
        tz = self.env.user.employee_id.tz or 'Asia/Karachi'
        hours = pytz.timezone(tz).localize(datetime.now()).utcoffset().seconds / 3600
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW %s AS (
                (
                    SELECT
                        hra.id,
                        hr_employee.department_id,
                        hra.employee_id,
                        hra.check_in,
                        hra.worked_hours,
                        coalesce(ot.duration, 0) as overtime_hours,
						hra.check_in_time + %i as check_in_time,
						hra.check_out_time + %i as check_out_time,
						hra.daily_hours,
						hra.adjusted_check_in_time + 5 as adjusted_check_in_time,
						hra.adjusted_check_out_time + 5 as adjusted_check_out_time
                    FROM (
                        SELECT
                            id,
                            row_number() over (partition by employee_id, CAST(check_in AS DATE)) as ot_check,
                            employee_id,
                            CAST(check_in as DATE) as check_in,
                            worked_hours,
                            daily_hours,
							extract (epoch from check_in::time)/3600 as check_in_time,
							extract (epoch from check_out::time)/3600 as check_out_time,
							extract (epoch from adjusted_check_in::time)/3600 as adjusted_check_in_time,
							extract (epoch from adjusted_check_out::time)/3600 as adjusted_check_out_time
                        FROM
                            hr_attendance
                        ) as hra
                    LEFT JOIN
                        hr_employee
                            ON hr_employee.id = hra.employee_id
                    LEFT JOIN
                        hr_attendance_overtime ot
                            ON hra.ot_check = 1
                            AND ot.employee_id = hra.employee_id
                            AND ot.date = hra.check_in
                            AND ot.adjustment = FALSE                
                )
            )
        """ % (self._table, hours, hours))
