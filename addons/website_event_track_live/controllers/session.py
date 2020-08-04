# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import re

from odoo.addons.website_event_track_session.controllers.session import WebsiteEventSessionController
from odoo.http import request


class WebsiteEventSessionLiveController(WebsiteEventSessionController):

    def _event_track_page_get_values(self, event, track, **options):
        if 'widescreen' not in options:
            options['widescreen'] = bool(track.youtube_video_url)
        values = super(WebsiteEventSessionLiveController, self)._event_track_page_get_values(event, track, **options)
        # Youtube disables the chat embed on all mobile devices
        # This regex is a naive attempt at matching their behavior (should work for most cases)
        values['is_mobile_chat_disabled'] = bool(re.match(
            r'^.*(Android|iPad|iPhone).*',
            request.httprequest.headers.get('User-Agent', request.httprequest.headers.get('user-agent', ''))))
        return values
