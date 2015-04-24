# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from openerp import tools
from openerp.osv import fields, osv
from ..models import hr_recruitment
from openerp.addons.decimal_precision import decimal_precision as dp


class hr_recruitment_report(osv.Model):
    _name = "hr.recruitment.report"
    _description = "Recruitments Statistics"
    _auto = False
    _rec_name = 'date_create'
    _order = 'date_create desc'

    _columns = {
        'user_id': fields.many2one('res.users', 'User', readonly=True),
        'company_id': fields.many2one('res.company', 'Company', readonly=True),
        'date_create': fields.datetime('Create Date', readonly=True),
        'date_last_stage_update': fields.datetime('Last Stage Update', readonly=True),
        'date_closed': fields.date('Closed', readonly=True),
        'job_id': fields.many2one('hr.job', 'Applied Job',readonly=True),
        'stage_id': fields.many2one ('hr.recruitment.stage', 'Stage'),
        'type_id': fields.many2one('hr.recruitment.degree', 'Degree'),
        'department_id': fields.many2one('hr.department','Department',readonly=True),
        'priority': fields.selection(hr_recruitment.AVAILABLE_PRIORITIES, 'Appreciation'),
        'salary_prop' : fields.float("Salary Proposed", digits=0),
        'salary_prop_avg' : fields.float("Avg. Proposed Salary", group_operator="avg", digits=0),
        'salary_exp' : fields.float("Salary Expected", digits=0),
        'salary_exp_avg' : fields.float("Avg. Expected Salary", group_operator="avg", digits=0),
        'partner_id': fields.many2one('res.partner', 'Partner',readonly=True),
        'delay_close': fields.float('Avg. Delay to Close', digits=(16,2), readonly=True, group_operator="avg",
                                       help="Number of Days to close the project issue"),
        'last_stage_id': fields.many2one ('hr.recruitment.stage', 'Last Stage'),
    }
    
    def init(self, cr):
        tools.drop_view_if_exists(cr, 'hr_recruitment_report')
        cr.execute("""
            create or replace view hr_recruitment_report as (
                 select
                     min(s.id) as id,
                     s.create_date as date_create,
                     date(s.date_closed) as date_closed,
                     s.date_last_stage_update as date_last_stage_update,
                     s.partner_id,
                     s.company_id,
                     s.user_id,
                     s.job_id,
                     s.type_id,
                     s.department_id,
                     s.priority,
                     s.stage_id,
                     s.last_stage_id,
                     sum(salary_proposed) as salary_prop,
                     (sum(salary_proposed)/count(*)) as salary_prop_avg,
                     sum(salary_expected) as salary_exp,
                     (sum(salary_expected)/count(*)) as salary_exp_avg,
                     extract('epoch' from (s.write_date-s.create_date))/(3600*24) as delay_close,
                     count(*) as nbr
                 from hr_applicant s
                 group by
                     s.date_open,
                     s.create_date,
                     s.write_date,
                     s.date_closed,
                     s.date_last_stage_update,
                     s.partner_id,
                     s.company_id,
                     s.user_id,
                     s.stage_id,
                     s.last_stage_id,
                     s.type_id,
                     s.priority,
                     s.job_id,
                     s.department_id
            )
        """)
