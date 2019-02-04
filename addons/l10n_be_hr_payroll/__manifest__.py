# -*- coding:utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Belgium - Payroll',
    'category': 'Payroll Localization',
    'depends': ['hr_payroll'],
    'description': """
Belgian Payroll Rules.
======================

    * Employee Details
    * Employee Contracts
    * Passport based Contract
    * Allowances/Deductions
    * Allow to configure Basic/Gross/Net Salary
    * Employee Payslip
    * Monthly Payroll Register
    * Integrated with Leaves Management
    * Salary Maj, ONSS, Withholding Tax, Child Allowance, ...
    """,

    'data': [
        'data/report_paperformat.xml',
        'views/report_payslip_template.xml',
        'views/reports.xml',
        'wizard/hr_payroll_employee_departure_notice_views.xml',
        'wizard/hr_payroll_employee_departure_holiday_attest_views.xml',
        'views/l10n_be_hr_payroll_view.xml',
        'views/report_termination_fees.xml',
        'views/report_termination_holidays.xml',
        'data/l10n_be_hr_payroll_data.xml',
        'data/cp200/employee_double_holidays_data.xml',
        'data/cp200/employee_salary_data.xml',
        'data/cp200/employee_thirteen_month_data.xml',
        'data/cp200/employee_termination_fees_data.xml',
        'data/cp200/employee_termination_holidays_N_data.xml',
        'data/cp200/employee_termination_holidays_N1_data.xml',
        'views/res_config_settings_views.xml',
        'wizard/l10n_be_individual_account_wizard_views.xml',
        'report/hr_individual_account_templates.xml',
    ],
    'demo':[
        'data/l10n_be_hr_payroll_demo.xml'
    ],
    'auto_install': False,
}
