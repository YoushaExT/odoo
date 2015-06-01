# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from openerp.report import report_sxw
from openerp.osv import osv


class account_analytic_profit(report_sxw.rml_parse):
    def __init__(self, cr, uid, name, context):
        super(account_analytic_profit, self).__init__(cr, uid, name, context=context)
        self.localcontext.update({
            'lines': self._lines,
            'user_ids': self._user_ids,
            'journal_ids': self._journal_ids,
            'line': self._line,
        })

    def _user_ids(self, lines):
        user_obj = self.pool['res.users']
        ids=list(set([b.user_id.id for b in lines]))
        return user_obj.browse(self.cr, self.uid, ids)

    def _journal_ids(self, form, user_id):
        if isinstance(user_id, (int, long)):
            user_id = [user_id]
        line_obj = self.pool['account.analytic.line']
        journal_obj = self.pool['account.analytic.journal']
        line_ids=line_obj.search(self.cr, self.uid, [
            ('date', '>=', form['date_from']),
            ('date', '<=', form['date_to']),
            ('journal_id', 'in', form['journal_ids'][0][2]),
            ('user_id', 'in', user_id),
            ])
        ids=list(set([b.journal_id.id for b in line_obj.browse(self.cr, self.uid, line_ids)]))
        return journal_obj.browse(self.cr, self.uid, ids)

    def _line(self, form, journal_ids, user_ids):
        line_obj = self.pool['account.analytic.line']
        product_obj = self.pool['product.product']
        price_obj = self.pool['product.pricelist']
        ids=line_obj.search(self.cr, self.uid, [
                ('date', '>=', form['date_from']),
                ('date', '<=', form['date_to']),
                ('journal_id', 'in', journal_ids),
                ('user_id', 'in', user_ids),
                ])
        res={}
        for line in line_obj.browse(self.cr, self.uid, ids):
            if line.account_id.pricelist_id:
                if line.account_id.to_invoice:
                    if line.to_invoice:
                        id=line.to_invoice.id
                        name=line.to_invoice.name
                        discount=line.to_invoice.factor
                    else:
                        name="/"
                        discount=1.0
                        id = -1
                else:
                    name="Fixed"
                    discount=0.0
                    id=0
                pl=line.account_id.pricelist_id.id
                price=price_obj.price_get(self.cr, self.uid, [pl], line.product_id.id, line.unit_amount or 1.0, line.account_id.partner_id.id)[pl]
            else:
                name="/"
                discount=1.0
                id = -1
                price=0.0
            if id not in res:
                res[id]={'name': name, 'amount': 0, 'cost':0, 'unit_amount':0,'amount_th':0}
            xxx = round(price * line.unit_amount * (1-(discount or 0.0)), 2)
            res[id]['amount_th']+=xxx
            if line.invoice_id:
                self.cr.execute('select id from account_analytic_line where invoice_id=%s', (line.invoice_id.id,))
                tot = 0
                for lid in self.cr.fetchall():
                    lid2 = line_obj.browse(self.cr, self.uid, lid[0])
                    pl=lid2.account_id.pricelist_id.id
                    price=price_obj.price_get(self.cr, self.uid, [pl], lid2.product_id.id, lid2.unit_amount or 1.0, lid2.account_id.partner_id.id)[pl]
                    tot += price * lid2.unit_amount * (1-(discount or 0.0))
                if tot:
                    percent = line.invoice_id.amount_untaxed / tot
                    res[id]['amount'] +=  xxx * percent
                else:
                    res[id]['amount'] += xxx
            else:
                res[id]['amount'] += xxx
            res[id]['cost']+=line.amount
            res[id]['unit_amount']+=line.unit_amount
        for id in res:
            res[id]['profit']=res[id]['amount']+res[id]['cost']
            res[id]['eff']=res[id]['cost'] and '%d' % (-res[id]['amount'] / res[id]['cost'] * 100,) or 0.0
        return res.values()

    def _lines(self, form):
        line_obj = self.pool['account.analytic.line']
        ids=line_obj.search(self.cr, self.uid, [
            ('date', '>=', form['date_from']),
            ('date', '<=', form['date_to']),
            ('journal_id', 'in', form['journal_ids'][0][2]),
            ('user_id', 'in', form['employee_ids'][0][2]),
            ])
        return line_obj.browse(self.cr, self.uid, ids)


class report_account_analytic_profit(osv.AbstractModel):
    _name = 'report.hr_timesheet_invoice.report_analyticprofit'
    _inherit = 'report.abstract_report'
    _template = 'hr_timesheet_invoice.report_analyticprofit'
    _wrapped_report_class = account_analytic_profit
