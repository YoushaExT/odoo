# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import re

from werkzeug import urls, utils

from odoo import api, models, tools


class MailRenderMixin(models.AbstractModel):
    _inherit = "mail.render.mixin"

    # ------------------------------------------------------------
    # TOOLS
    # ------------------------------------------------------------

    @api.model
    def _shorten_links(self, html, link_tracker_vals, blacklist=None, base_url=None):
        """

        :param link_tracker_vals: values given to the created link.tracker, containing
          for example: campaign_id, medium_id, source_id, and any other relevant fields
          like mass_mailing_id in mass_mailing;

        :return: update
        """
        base_url = base_url or self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        short_schema = base_url + '/r/'
        for match in re.findall(tools.URL_REGEX, html):
            href = match[0]
            long_url = match[1]

            if not blacklist or not [s for s in blacklist if s in long_url] and not long_url.startswith(short_schema):
                create_vals = dict(link_tracker_vals, url=utils.unescape(long_url))
                link = self.env['link.tracker'].create(create_vals)
                if link.short_url:
                    new_href = href.replace(long_url, link.short_url)
                    html = html.replace(href, new_href)

        return html

    @api.model
    def _shorten_links_text(self, html, link_tracker_vals, blacklist=None, base_url=None):
        base_url = base_url or self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        shortened_schema = base_url + '/r/'
        unsubscribe_schema = base_url + '/sms/'
        for original_url in re.findall(tools.TEXT_URL_REGEX, html):
            # don't shorten already-shortened links or links towards unsubscribe page
            if original_url.startswith(shortened_schema) or original_url.startswith(unsubscribe_schema):
                continue
            # support blacklist items in path, like /u/
            parsed = urls.url_parse(original_url, scheme='http')
            if blacklist and any(item in parsed.path for item in blacklist):
                continue

            create_vals = dict(link_tracker_vals, url= utils.unescape(original_url))
            link = self.env['link.tracker'].create(create_vals)
            if link.short_url:
                html = html.replace(original_url, link.short_url, 1)

        return html
