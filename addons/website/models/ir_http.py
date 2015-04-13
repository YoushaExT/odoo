# -*- coding: utf-8 -*-
import logging
import os
import re
import traceback

import werkzeug
import werkzeug.routing
import werkzeug.utils

import openerp
from openerp.addons.base import ir
from openerp.addons.base.ir import ir_qweb
from openerp.addons.website.models.website import slug, url_for, _UNSLUG_RE
from openerp.http import request
from openerp.tools import config
from openerp.osv import orm

logger = logging.getLogger(__name__)

class RequestUID(object):
    def __init__(self, **kw):
        self.__dict__.update(kw)

class ir_http(orm.AbstractModel):
    _inherit = 'ir.http'

    rerouting_limit = 10
    geo_ip_resolver = None

    def _get_converters(self):
        return dict(
            super(ir_http, self)._get_converters(),
            model=ModelConverter,
            page=PageConverter,
        )

    def _auth_method_public(self):
        if not request.session.uid:
            website = self.pool['website'].get_current_website(request.cr, openerp.SUPERUSER_ID, context=request.context)
            if website:
                request.uid = website.user_id.id
            else:
                request.uid = self.pool['ir.model.data'].xmlid_to_res_id(request.cr, openerp.SUPERUSER_ID, 'base', 'public_user')
        else:
            request.uid = request.session.uid

    bots = "bot|crawl|slurp|spider|curl|wget".split("|")
    def is_a_bot(self):
        # We don't use regexp and ustr voluntarily
        # timeit has been done to check the optimum method
        ua = request.httprequest.environ.get('HTTP_USER_AGENT', '').lower()
        try:
            return any(bot in ua for bot in self.bots)
        except UnicodeDecodeError:
            return any(bot in ua.encode('ascii', 'ignore') for bot in self.bots)

    def _dispatch(self):
        first_pass = not hasattr(request, 'website')
        request.website = None
        func = None
        try:
            func, arguments = self._find_handler()
            request.website_enabled = func.routing.get('website', False)
        except werkzeug.exceptions.NotFound:
            # either we have a language prefixed route, either a real 404
            # in all cases, website processes them
            request.website_enabled = True

        request.website_multilang = (
            request.website_enabled and
            func and func.routing.get('multilang', func.routing['type'] == 'http')
        )

        if 'geoip' not in request.session:
            record = {}
            if self.geo_ip_resolver is None:
                try:
                    import GeoIP
                    # updated database can be downloaded on MaxMind website
                    # http://dev.maxmind.com/geoip/legacy/install/city/
                    geofile = config.get('geoip_database')
                    if os.path.exists(geofile):
                        self.geo_ip_resolver = GeoIP.open(geofile, GeoIP.GEOIP_STANDARD)
                    else:
                        self.geo_ip_resolver = False
                        logger.warning('GeoIP database file %r does not exists', geofile)
                except ImportError:
                    self.geo_ip_resolver = False
            if self.geo_ip_resolver and request.httprequest.remote_addr:
                record = self.geo_ip_resolver.record_by_addr(request.httprequest.remote_addr) or {}
            request.session['geoip'] = record

        cook_lang = request.httprequest.cookies.get('website_lang')
        if request.website_enabled:
            try:
                if func:
                    self._authenticate(func.routing['auth'])
                elif request.uid is None:
                    self._auth_method_public()
            except Exception as e:
                return self._handle_exception(e)

            request.redirect = lambda url, code=302: werkzeug.utils.redirect(url_for(url), code)
            request.website = request.registry['website'].get_current_website(request.cr, request.uid, context=request.context)
            request.context['website_id'] = request.website.id
            langs = [lg[0] for lg in request.website.get_languages()]
            path = request.httprequest.path.split('/')

            if first_pass:
                if request.website_multilang:
                    is_a_bot = self.is_a_bot()
                    # If the url doesn't contains the lang and that it's the first connection, we to retreive the user preference if it exists.
                    if not path[1] in langs and not is_a_bot:
                        request.lang = cook_lang or request.lang
                        if request.lang not in langs:
                            # Try to find a similar lang. Eg: fr_BE and fr_FR
                            short = request.lang.split('_')[0]
                            langs_withshort = [lg[0] for lg in request.website.get_languages() if lg[0].startswith(short)]
                            if len(langs_withshort):
                                request.lang = langs_withshort[0]
                            else:
                                request.lang = request.website.default_lang_code
                    else:
                        request.lang = request.website.default_lang_code

                    if request.lang != request.website.default_lang_code:
                        path.insert(1, request.lang)
                        path = '/'.join(path) or '/'
                        redirect = request.redirect(path + '?' + request.httprequest.query_string)
                        redirect.set_cookie('website_lang', request.lang)
                        return redirect

            request.context['lang'] = request.lang
            if not request.context.get('tz'):
                request.context['tz'] = request.session['geoip'].get('time_zone')
            if not func:
                if path[1] in langs:
                    request.lang = request.context['lang'] = path.pop(1)
                    path = '/'.join(path) or '/'
                    if request.lang == request.website.default_lang_code:
                        # If language is in the url and it is the default language, redirect
                        # to url without language so google doesn't see duplicate content
                        resp = request.redirect(path + '?' + request.httprequest.query_string, code=301)
                        if cook_lang != request.lang:  # If default lang setted in url directly
                            resp.set_cookie('website_lang', request.lang)
                        return resp
                    return self.reroute(path)
            # bind modified context
            request.website = request.website.with_context(request.context)
        resp = super(ir_http, self)._dispatch()
        if not cook_lang:
            resp.set_cookie('website_lang', request.lang)
        return resp

    def reroute(self, path):
        if not hasattr(request, 'rerouting'):
            request.rerouting = [request.httprequest.path]
        if path in request.rerouting:
            raise Exception("Rerouting loop is forbidden")
        request.rerouting.append(path)
        if len(request.rerouting) > self.rerouting_limit:
            raise Exception("Rerouting limit exceeded")
        request.httprequest.environ['PATH_INFO'] = path
        # void werkzeug cached_property. TODO: find a proper way to do this
        for key in ('path', 'full_path', 'url', 'base_url'):
            request.httprequest.__dict__.pop(key, None)

        return self._dispatch()

    def _postprocess_args(self, arguments, rule):
        super(ir_http, self)._postprocess_args(arguments, rule)

        for key, val in arguments.items():
            # Replace uid placeholder by the current request.uid
            if isinstance(val, orm.BaseModel) and isinstance(val._uid, RequestUID):
                arguments[key] = val.sudo(request.uid)

        try:
            _, path = rule.build(arguments)
            assert path is not None
        except Exception, e:
            return self._handle_exception(e, code=404)

        if getattr(request, 'website_multilang', False) and request.httprequest.method in ('GET', 'HEAD'):
            generated_path = werkzeug.url_unquote_plus(path)
            current_path = werkzeug.url_unquote_plus(request.httprequest.path)
            if generated_path != current_path:
                if request.lang != request.website.default_lang_code:
                    path = '/' + request.lang + path
                if request.httprequest.query_string:
                    path += '?' + request.httprequest.query_string
                return werkzeug.utils.redirect(path, code=301)

    def _handle_exception(self, exception, code=500):
        is_website_request = bool(getattr(request, 'website_enabled', False) and request.website)
        if not is_website_request:
            # Don't touch non website requests exception handling
            return super(ir_http, self)._handle_exception(exception)
        else:
            try:
                response = super(ir_http, self)._handle_exception(exception)
                if isinstance(response, Exception):
                    exception = response
                else:
                    # if parent excplicitely returns a plain response, then we don't touch it
                    return response
            except Exception, e:
                if openerp.tools.config['dev_mode'] and (not isinstance(exception, ir_qweb.QWebException) or not exception.qweb.get('cause')):
                    raise
                exception = e

            values = dict(
                exception=exception,
                traceback=traceback.format_exc(exception),
            )

            if isinstance(exception, werkzeug.exceptions.HTTPException):
                if exception.code is None:
                    # Hand-crafted HTTPException likely coming from abort(),
                    # usually for a redirect response -> return it directly
                    return exception
                else:
                    code = exception.code

            if isinstance(exception, openerp.exceptions.AccessError):
                code = 403

            if isinstance(exception, ir_qweb.QWebException):
                values.update(qweb_exception=exception)
                if isinstance(exception.qweb.get('cause'), openerp.exceptions.AccessError):
                    code = 403

            if code == 500:
                logger.error("500 Internal Server Error:\n\n%s", values['traceback'])
                if 'qweb_exception' in values:
                    view = request.registry.get("ir.ui.view")
                    views = view._views_get(request.cr, request.uid, exception.qweb['template'], request.context)
                    to_reset = [v for v in views if v.model_data_id.noupdate is True and not v.page]
                    values['views'] = to_reset
            elif code == 403:
                logger.warn("403 Forbidden:\n\n%s", values['traceback'])

            values.update(
                status_message=werkzeug.http.HTTP_STATUS_CODES[code],
                status_code=code,
            )

            if not request.uid:
                self._auth_method_public()

            try:
                html = request.website._render('website.%s' % code, values)
            except Exception:
                html = request.website._render('website.http_error', values)
            return werkzeug.wrappers.Response(html, status=code, content_type='text/html;charset=utf-8')

class ModelConverter(ir.ir_http.ModelConverter):
    def __init__(self, url_map, model=False, domain='[]'):
        super(ModelConverter, self).__init__(url_map, model)
        self.domain = domain
        self.regex = _UNSLUG_RE.pattern

    def to_url(self, value):
        return slug(value)

    def to_python(self, value):
        m = re.match(self.regex, value)
        _uid = RequestUID(value=value, match=m, converter=self)
        record_id = int(m.group(2))
        if record_id < 0:
            # limited support for negative IDs due to our slug pattern, assume abs() if not found
            if not request.registry[self.model].exists(request.cr, _uid, [record_id]):
                record_id = abs(record_id)
        return request.registry[self.model].browse(
            request.cr, _uid, record_id, context=request.context)

    def generate(self, cr, uid, query=None, args=None, context=None):
        obj = request.registry[self.model]
        domain = eval( self.domain, (args or {}).copy())
        if query:
            domain.append((obj._rec_name, 'ilike', '%'+query+'%'))
        for record in obj.search_read(cr, uid, domain=domain, fields=['write_date',obj._rec_name], context=context):
            if record.get(obj._rec_name, False):
                yield {'loc': (record['id'], record[obj._rec_name])}

class PageConverter(werkzeug.routing.PathConverter):
    """ Only point of this converter is to bundle pages enumeration logic """
    def generate(self, cr, uid, query=None, args={}, context=None):
        View = request.registry['ir.ui.view']
        domain = [('page', '=', True)]
        query = query and query.startswith('website.') and query[8:] or query
        if query:
            domain += [('key', 'like', query)]

        views = View.search_read(cr, uid, domain, fields=['key', 'priority', 'write_date'], order='name', context=context)
        for view in views:
            xid = view['key'].startswith('website.') and view['key'][8:] or view['key']
            # the 'page/homepage' url is indexed as '/', avoid aving the same page referenced twice
            # when we will have an url mapping mechanism, replace this by a rule: page/homepage --> /
            if xid=='homepage': continue
            record = {'loc': xid}
            if view['priority'] <> 16:
                record['__priority'] = min(round(view['priority'] / 32.0,1), 1)
            if view['write_date']:
                record['__lastmod'] = view['write_date'][:10]
            yield record
