# -*- coding: utf-8 -*-

from openerp.osv import osv, fields


class res_partner(osv.Model):
    _inherit = 'res.partner'

    _columns = {
        'tag_ids': fields.many2many('res.partner.tag', id1='partner_id', id2='tag_id', string='Tags'),
    }


class res_partner_tags(osv.Model):
    _description = 'Partner Tags - These tags can be used on website to find customers by sector, or ... '
    _name = 'res.partner.tag'

    def get_selection_class(self, cr, uid, context=None):
        classname = ['default', 'primary', 'success', 'warning', 'danger']
        return [(x, str.title(x)) for x in classname]

    _columns = {
        'name': fields.char('Category Name', required=True, translate=True),
        'partner_ids': fields.many2many('res.partner', 'res_partner_res_partner_tag_rel', id1='tag_id', id2='partner_id', string='Partners'),
        'classname': fields.selection(get_selection_class, 'Class', help="Bootstrap class to customize the color of the tag", required=True),
        'website_published': fields.boolean('Publish', help="The publish field allows you to show the tag on website."),
        'active': fields.boolean('Active'),
    }
    _defaults = {
        'active': True,
        'website_published': True,
        'classname': 'default',
    }
