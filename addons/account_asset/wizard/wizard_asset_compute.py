# -*- coding: utf-8 -*-
from openerp import api, fields, models, _


class AssetDepreciationConfirmationWizard(models.TransientModel):
    _name = "asset.depreciation.confirmation.wizard"
    _description = "asset.depreciation.confirmation.wizard"

    period_id = fields.Many2one('account.period', string='Period', default='_get_period', required=True,
        help="Choose the period for which you want to automatically post the depreciation lines of running assets")

    def _get_period(self):
        periods = self.env['account.period'].find()
        if periods:
            return periods[0]
        else:
            raise UserError(_('You do not have any period. Please configure them.'))

    @api.multi
    def asset_compute(self):
        self.ensure_one()
        context = self._context
        assets = self.env['account.asset.asset'].search([('state', '=', 'open'), ('category_id.type', '=', context.get('asset_type'))])
        created_move_ids = assets._compute_entries(self.period_id.id)
        if context.get('asset_type') == 'purchase':
            title = _('Created Asset Moves')
        else:
            title = _('Created Revenue Moves')
        return {
            'name': title,
            'view_type': 'form',
            'view_mode': 'tree,form',
            'res_model': 'account.move',
            'view_id': False,
            'domain': "[('id','in',["+','.join(map(str, created_move_ids))+"])]",
            'type': 'ir.actions.act_window',
        }
