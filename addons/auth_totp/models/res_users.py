# -*- coding: utf-8 -*-
import base64
import functools
import hmac
import io
import logging
import os
import re
import struct
import time

import werkzeug.urls

from odoo import _, api, fields, models
from odoo.addons.base.models.res_users import check_identity
from odoo.exceptions import AccessDenied, UserError
from odoo.http import request, db_list

_logger = logging.getLogger(__name__)

compress = functools.partial(re.sub, r'\s', '')
class Users(models.Model):
    _inherit = 'res.users'

    totp_secret = fields.Char(copy=False, groups=fields.NO_ACCESS)
    totp_enabled = fields.Boolean(string="TOTP enabled", compute='_compute_totp_enabled')

    def __init__(self, pool, cr):
        init_res = super().__init__(pool, cr)
        type(self).SELF_READABLE_FIELDS = self.SELF_READABLE_FIELDS + ['totp_enabled']
        return init_res

    def _mfa_url(self):
        r = super()._mfa_url()
        if r is not None:
            return r
        if self.totp_enabled:
            return '/web/login/totp'

    @api.depends('totp_secret')
    def _compute_totp_enabled(self):
        for r, v in zip(self, self.sudo()):
            r.totp_enabled = bool(v.totp_secret)

    def _rpc_api_keys_only(self):
        # 2FA enabled means we can't allow password-based RPC
        self.ensure_one()
        return self.totp_enabled or super()._rpc_api_keys_only()

    def _get_session_token_fields(self):
        return super()._get_session_token_fields() | {'totp_secret'}

    def _totp_check(self, code):
        sudo = self.sudo()
        key = base64.b32decode(sudo.totp_secret)
        match = TOTP(key).match(code)
        if match is None:
            _logger.info("2FA check: FAIL for '%s' (#%s)", self.login, self.id)
            raise AccessDenied()
        _logger.info("2FA check: SUCCESS for '%s' (#%s)", self.login, self.id)

    def _totp_try_setting(self, secret, code):
        if self.totp_enabled or self != self.env.user:
            _logger.info("2FA enable: REJECT for '%s' (#%s)", self.login, self.id)
            return False

        secret = compress(secret).upper()
        match = TOTP(base64.b32decode(secret)).match(code)
        if match is None:
            _logger.info("2FA enable: REJECT CODE for '%s' (#%s)", self.login, self.id)
            return False

        self.sudo().totp_secret = secret
        if request:
            self.flush()
            # update session token so the user does not get logged out (cache cleared by change)
            new_token = self.env.user._compute_session_token(request.session.sid)
            request.session.session_token = new_token

        _logger.info("2FA enable: SUCCESS for '%s' (#%s)", self.login, self.id)
        return True

    @check_identity
    def totp_disable(self):
        if not (self == self.env.user or self.env.user._is_admin() or self.env.su):
            _logger.info("2FA disable: REJECT for '%s' (#%s) by uid #%s", self.login, self.id, self.env.user.id)
            return False

        self.sudo().write({'totp_secret': False})
        if request and self == self.env.user:
            self.flush()
            # update session token so the user does not get logged out (cache cleared by change)
            new_token = self.env.user._compute_session_token(request.session.sid)
            request.session.session_token = new_token

        _logger.info("2FA disable: SUCCESS for '%s' (#%s) by uid #%s", self.login, self.id, self.env.user.id)
        return {'type': 'ir.actions.act_window_close'}

    @check_identity
    def totp_enable_wizard(self):
        if self.env.user != self:
            raise UserError(_("Two-factor authentication can only be enabled for yourself"))

        if self.totp_enabled:
            raise UserError(_("Two-factor authentication already enabled"))

        secret_bytes_count = TOTP_SECRET_SIZE // 8
        secret = base64.b32encode(os.urandom(secret_bytes_count)).decode()
        # format secret in groups of 4 characters for readability
        secret = ' '.join(map(''.join, zip(*[iter(secret)]*4)))
        w = self.env['auth_totp.wizard'].create({
            'user_id': self.id,
            'secret': secret,
        })
        return {
            'type': 'ir.actions.act_window',
            'target': 'new',
            'res_model': 'auth_totp.wizard',
            'name': _("Enable Two-Factor Authentication"),
            'res_id': w.id,
            'views': [(False, 'form')],
        }

class TOTPWizard(models.TransientModel):
    _name = 'auth_totp.wizard'
    _description = "Two-Factor Setup Wizard"

    user_id = fields.Many2one('res.users', required=True, readonly=True)
    secret = fields.Char(required=True, readonly=True)
    url = fields.Char(store=True, readonly=True, compute='_compute_qrcode')
    qrcode = fields.Binary(
        attachment=False, store=True, readonly=True,
        compute='_compute_qrcode',
    )
    code = fields.Char(string="Verification Code", size=7)

    @api.depends('user_id.login', 'user_id.company_id.display_name', 'secret')
    def _compute_qrcode(self):
        # TODO: make "issuer" configurable through config parameter?
        global_issuer = request and request.httprequest.host.split(':', 1)[0]
        for w in self:
            issuer = global_issuer or w.user_id.company_id.display_name
            w.url = url = werkzeug.urls.url_unparse((
                'otpauth', 'totp',
                werkzeug.urls.url_quote(f'{issuer}:{w.user_id.login}', safe=':'),
                werkzeug.urls.url_encode({
                    'secret': compress(w.secret),
                    'issuer': issuer,
                    # apparently a lowercase hash name is anathema to google
                    # authenticator (error) and passlib (no token)
                    'algorithm': ALGORITHM.upper(),
                    'digits': DIGITS,
                    'period': TIMESTEP,
                }), ''
            ))

            data = io.BytesIO()
            import qrcode
            qrcode.make(url.encode(), box_size=4).save(data, optimise=True, format='PNG')
            w.qrcode = base64.b64encode(data.getvalue()).decode()

    @check_identity
    def enable(self):
        try:
            c = int(compress(self.code))
        except ValueError:
            raise UserError(_("The verification code should only contain numbers"))
        if self.user_id._totp_try_setting(self.secret, c):
            self.secret = '' # empty it, because why keep it until GC?
            return {'type': 'ir.actions.act_window_close'}
        raise UserError(_('Verification failed, please double-check the 6-digit code'))

# 160 bits, as recommended by HOTP RFC 4226, section 4, R6.
# Google Auth uses 80 bits by default but supports 160.
TOTP_SECRET_SIZE = 160

# The algorithm (and key URI format) allows customising these parameters but
# google authenticator doesn't support it
# https://github.com/google/google-authenticator/wiki/Key-Uri-Format
ALGORITHM = 'sha1'
DIGITS = 6
TIMESTEP = 30

class TOTP:
    def __init__(self, key):
        self._key = key

    def match(self, code, t=None, window=TIMESTEP):
        """
        :param code: authenticator code to check against this key
        :param int t: current timestamp (seconds)
        :param int window: fuzz window to account for slow fingers, network
                           latency, desynchronised clocks, ..., every code
                           valid between t-window an t+window is considered
                           valid
        """
        if t is None:
            t = time.time()

        low = int((t - window) / TIMESTEP)
        high = int((t + window) / TIMESTEP) + 1

        return next((
            counter for counter in range(low, high)
            if hotp(self._key, counter) == code
        ), None)

def hotp(secret, counter):
    # C is the 64b counter encoded in big-endian
    C = struct.pack(">Q", counter)
    mac = hmac.new(secret, msg=C, digestmod=ALGORITHM).digest()
    # the data offset is the last nibble of the hash
    offset = mac[-1] & 0xF
    # code is the 4 bytes at the offset interpreted as a 31b big-endian uint
    # (31b to avoid sign concerns). This effectively limits digits to 9 and
    # hard-limits it to 10: each digit is normally worth 3.32 bits but the
    # 10th is only worth 1.1 (9 digits encode 29.9 bits).
    code = struct.unpack_from('>I', mac, offset)[0] & 0x7FFFFFFF
    r = code % (10 ** DIGITS)
    # NOTE: use text / bytes instead of int?
    return r
