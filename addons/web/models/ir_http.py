# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
import hashlib
import json

from odoo import models
from odoo.http import request
from odoo.tools import ustr

from odoo.addons.web.controllers.main import concat_xml, manifest_glob, module_boot

import odoo


class Http(models.AbstractModel):
    _inherit = 'ir.http'

    def webclient_rendering_context(self):
        return {
            'menu_data': request.env['ir.ui.menu'].load_menus(request.debug),
            'session_info': json.dumps(self.session_info()),
        }

    def session_info(self):
        user = request.env.user
        version_info = odoo.service.common.exp_version()

        user_context = request.session.get_context() if request.session.uid else {}

        mods = module_boot()
        files = [f[0] for f in manifest_glob('qweb', addons=','.join(mods))]
        _, qweb_checksum = concat_xml(files)

        lang = user_context.get("lang")
        translations_per_module, _ = request.env['ir.translation'].get_translations_for_webclient(mods, lang)

        menu_json_utf8 = json.dumps(request.env['ir.ui.menu'].load_menus(request.debug), default=ustr, sort_keys=True).encode()
        translations_json_utf8 = json.dumps(translations_per_module,  sort_keys=True).encode()

        return {
            "uid": request.session.uid,
            "is_system": user._is_system() if request.session.uid else False,
            "is_admin": user._is_admin() if request.session.uid else False,
            "user_context": request.session.get_context() if request.session.uid else {},
            "db": request.session.db,
            "server_version": version_info.get('server_version'),
            "server_version_info": version_info.get('server_version_info'),
            "name": user.name,
            "username": user.login,
            "partner_display_name": user.partner_id.display_name,
            "company_id": user.company_id.id if request.session.uid else None,  # YTI TODO: Remove this from the user context
            "partner_id": user.partner_id.id if request.session.uid and user.partner_id else None,
            # current_company should be default_company
            "user_companies": {'current_company': (user.company_id.id, user.company_id.name), 'allowed_companies': [(comp.id, comp.name) for comp in user.company_ids]},
            "currencies": self.get_currencies() if request.session.uid else {},
            "web.base.url": self.env['ir.config_parameter'].sudo().get_param('web.base.url', default=''),
            "show_effect": True,
            "display_switch_company_menu": user.has_group('base.group_multi_company') and len(user.company_ids) > 1,
            "toggle_company": user.has_group('base.group_toggle_company'),
            "cache_hashes": {
                "load_menus": hashlib.sha1(menu_json_utf8).hexdigest(),
                "qweb": qweb_checksum,
                "translations": hashlib.sha1(translations_json_utf8).hexdigest(),
            },
        }

    def get_currencies(self):
        Currency = request.env['res.currency']
        currencies = Currency.search([]).read(['symbol', 'position', 'decimal_places'])
        return {c['id']: {'symbol': c['symbol'], 'position': c['position'], 'digits': [69,c['decimal_places']]} for c in currencies}
