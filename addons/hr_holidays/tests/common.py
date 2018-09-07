# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.tests import common


class TestHrHolidaysBase(common.TransactionCase):

    def setUp(self):
        super(TestHrHolidaysBase, self).setUp()

        Users = self.env['res.users'].with_context(no_reset_password=True)

        # Find Employee group
        group_employee_id = self.ref('base.group_user')

        # Test users to use through the various tests
        self.user_hruser = Users.create({
            'name': 'Armande HrUser',
            'login': 'Armande',
            'email': 'armande.hruser@example.com',
            'groups_id': [(6, 0, [group_employee_id, self.ref('hr_holidays.group_hr_holidays_user')])]
        })
        self.user_hruser_id = self.user_hruser.id
        self.user_hrmanager = Users.create({
            'name': 'Bastien HrManager',
            'login': 'bastien',
            'email': 'bastien.hrmanager@example.com',
            'groups_id': [(6, 0, [group_employee_id, self.ref('hr_holidays.group_hr_holidays_manager')])]
        }).id
        self.user_hrmanager_id = self.user_hrmanager
        self.user_employee = Users.create({
            'name': 'David Employee',
            'login': 'david',
            'email': 'david.employee@example.com',
            'groups_id': [(6, 0, [group_employee_id])]
        })
        self.user_employee_id = self.user_employee.id
        self.user_hrmanager_2_id = Users.create({
            'name': 'Florence HrManager',
            'login': 'florence',
            'email': 'florence.hrmanager@example.com',
            'groups_id': [(6, 0, [group_employee_id, self.ref('hr_holidays.group_hr_holidays_manager')])]
        }).id

        # Hr Data
        Department = self.env['hr.department'].with_context(tracking_disable=True)

        self.hr_dept = Department.create({
            'name': 'Human Resources',
        })
        self.rd_dept = Department.create({
            'name': 'Research and devlopment',
        })

        self.employee_emp = self.env['hr.employee'].create({
            'name': 'David Employee',
            'user_id': self.user_employee_id,
            'department_id': self.rd_dept.id,
        })
        self.employee_emp_id = self.employee_emp.id

        self.employee_hruser = self.env['hr.employee'].create({
            'name': 'Armande HrUser',
            'user_id': self.user_hruser_id,
            'department_id': self.rd_dept.id,
        })
        self.employee_hruser_id = self.employee_hruser.id

        self.employee_hrmanager = self.env['hr.employee'].create({
            'name': 'Bastien HrManager',
            'user_id': self.user_hrmanager_id,
            'department_id': self.hr_dept.id,
        })
        self.employee_hrmanager_id = self.employee_hrmanager.id

        self.employee_hrmanager_2_id = self.env['hr.employee'].create({
            'name': 'Florence HrManager',
            'user_id': self.user_hrmanager_2_id,
            'parent_id': self.employee_hrmanager_id,
        }).id

        self.rd_dept.write({'manager_id': self.employee_hruser_id})
