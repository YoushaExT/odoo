# -*- coding: utf-8 -*-
import cStringIO
import datetime
from itertools import islice
import json
import xml.etree.ElementTree as ET

import logging
import re

import werkzeug.utils
import urllib2
import werkzeug.wrappers
from PIL import Image

import openerp
from openerp.addons.web.controllers.main import WebClient
from openerp.addons.web import http
from openerp.http import request, STATIC_CACHE
from openerp.tools import image_save_for_web

logger = logging.getLogger(__name__)

# Completely arbitrary limits
MAX_IMAGE_WIDTH, MAX_IMAGE_HEIGHT = IMAGE_LIMITS = (1024, 768)
LOC_PER_SITEMAP = 45000
SITEMAP_CACHE_TIME = datetime.timedelta(hours=12)

class Website(openerp.addons.web.controllers.main.Home):
    #------------------------------------------------------
    # View
    #------------------------------------------------------
    @http.route('/', type='http', auth="public", website=True)
    def index(self, **kw):
        page = 'homepage'
        try:
            main_menu = request.registry['ir.model.data'].get_object(request.cr, request.uid, 'website', 'main_menu')
        except Exception:
            pass
        else:
            first_menu = main_menu.child_id and main_menu.child_id[0]
            if first_menu:
                if not (first_menu.url.startswith(('/page/', '/?', '/#')) or (first_menu.url=='/')):
                    return request.redirect(first_menu.url)
                if first_menu.url.startswith('/page/'):
                    return request.registry['ir.http'].reroute(first_menu.url)
        return self.page(page)

    #------------------------------------------------------
    # Login - overwrite of the web login so that regular users are redirected to the backend 
    # while portal users are redirected to the frontend by default
    #------------------------------------------------------
    @http.route(website=True, auth="public")
    def web_login(self, redirect=None, *args, **kw):
        r = super(Website, self).web_login(redirect=redirect, *args, **kw)
        if request.params['login_success'] and not redirect:
            if request.registry['res.users'].has_group(request.cr, request.uid, 'base.group_user'):
                redirect = '/web?' + request.httprequest.query_string
            else:
                redirect = '/'
            return http.redirect_with_hash(redirect)
        return r

    @http.route('/page/<page:page>', type='http', auth="public", website=True)
    def page(self, page, **opt):
        values = {
            'path': page,
            'deletable': True, # used to add 'delete this page' in content menu
        }
        # /page/website.XXX --> /page/XXX
        if page.startswith('website.'):
            return request.redirect('/page/' + page[8:], code=301)
        elif '.' not in page:
            page = 'website.%s' % page

        try:
            request.website.get_template(page)
        except ValueError, e:
            # page not found
            if request.website.is_publisher():
                values.pop('deletable')
                page = 'website.page_404'
            else:
                return request.registry['ir.http']._handle_exception(e, 404)

        return request.render(page, values)

    @http.route(['/robots.txt'], type='http', auth="public")
    def robots(self):
        return request.render('website.robots', {'url_root': request.httprequest.url_root}, mimetype='text/plain')

    @http.route('/sitemap.xml', type='http', auth="public", website=True)
    def sitemap_xml_index(self):
        cr, uid, context = request.cr, openerp.SUPERUSER_ID, request.context
        ira = request.registry['ir.attachment']
        iuv = request.registry['ir.ui.view']
        mimetype ='application/xml;charset=utf-8'
        content = None

        def create_sitemap(url, content):
            ira.create(cr, uid, dict(
                datas=content.encode('base64'),
                mimetype=mimetype,
                type='binary',
                name=url,
                url=url,
            ), context=context)

        sitemap = ira.search_read(cr, uid, [('url', '=' , '/sitemap.xml'), ('type', '=', 'binary')], ('datas', 'create_date'), context=context)
        if sitemap:
            # Check if stored version is still valid
            server_format = openerp.tools.misc.DEFAULT_SERVER_DATETIME_FORMAT
            create_date = datetime.datetime.strptime(sitemap[0]['create_date'], server_format)
            delta = datetime.datetime.now() - create_date
            if delta < SITEMAP_CACHE_TIME:
                content = sitemap[0]['datas'].decode('base64')

        if not content:
            # Remove all sitemaps in ir.attachments as we're going to regenerated them
            sitemap_ids = ira.search(cr, uid, [('url', '=like' , '/sitemap%.xml'), ('type', '=', 'binary')], context=context)
            if sitemap_ids:
                ira.unlink(cr, uid, sitemap_ids, context=context)

            pages = 0
            first_page = None
            locs = request.website.enumerate_pages()
            while True:
                start = pages * LOC_PER_SITEMAP
                values = {
                    'locs': islice(locs, start, start + LOC_PER_SITEMAP),
                    'url_root': request.httprequest.url_root[:-1],
                }
                urls = iuv.render(cr, uid, 'website.sitemap_locs', values, context=context)
                if urls.strip():
                    page = iuv.render(cr, uid, 'website.sitemap_xml', dict(content=urls), context=context)
                    if not first_page:
                        first_page = page
                    pages += 1
                    create_sitemap('/sitemap-%d.xml' % pages, page)
                else:
                    break
            if not pages:
                return request.not_found()
            elif pages == 1:
                content = first_page
            else:
                # Sitemaps must be split in several smaller files with a sitemap index
                content = iuv.render(cr, uid, 'website.sitemap_index_xml', dict(
                    pages=range(1, pages + 1),
                    url_root=request.httprequest.url_root,
                ), context=context)
            create_sitemap('/sitemap.xml', content)

        return request.make_response(content, [('Content-Type', mimetype)])

    @http.route('/website/info', type='http', auth="public", website=True)
    def website_info(self):
        try:
            request.website.get_template('website.info').name
        except Exception, e:
            return request.registry['ir.http']._handle_exception(e, 404)
        irm = request.env()['ir.module.module'].sudo()
        apps = irm.search([('state','=','installed'),('application','=',True)])
        modules = irm.search([('state','=','installed'),('application','=',False)])
        values = {
            'apps': apps,
            'modules': modules,
            'version': openerp.service.common.exp_version()
        }
        return request.render('website.info', values)

    #------------------------------------------------------
    # Edit
    #------------------------------------------------------
    @http.route('/website/add/<path:path>', type='http', auth="user", website=True)
    def pagenew(self, path, noredirect=False, add_menu=None):
        xml_id = request.registry['website'].new_page(request.cr, request.uid, path, context=request.context)
        if add_menu:
            request.registry['website.menu'].create(
                request.cr, request.uid, {
                    'name': path,
                    'url': "/page/" + xml_id,
                    'parent_id': request.website.menu_id.id,
                    'website_id': request.website.id,
                }, context=request.context)
        # Reverse action in order to allow shortcut for /page/<website_xml_id>
        url = "/page/" + re.sub(r"^website\.", '', xml_id)

        if noredirect:
            return werkzeug.wrappers.Response(url, mimetype='text/plain')
        return werkzeug.utils.redirect(url + "?enable_editor=1")

    @http.route(['/website/snippets'], type='json', auth="public", website=True)
    def snippets(self):
        return request.website._render('website.snippets')

    @http.route('/website/reset_templates', type='http', auth='user', methods=['POST'], website=True)
    def reset_template(self, templates, redirect='/'):
        templates = request.httprequest.form.getlist('templates')
        modules_to_update = []
        for temp_id in templates:
            view = request.registry['ir.ui.view'].browse(request.cr, request.uid, int(temp_id), context=request.context)
            if view.page:
                continue
            view.model_data_id.write({
                'noupdate': False
            })
            if view.model_data_id.module not in modules_to_update:
                modules_to_update.append(view.model_data_id.module)

        if modules_to_update:
            module_obj = request.registry['ir.module.module']
            module_ids = module_obj.search(request.cr, request.uid, [('name', 'in', modules_to_update)], context=request.context)
            if module_ids:
                module_obj.button_immediate_upgrade(request.cr, request.uid, module_ids, context=request.context)
        return request.redirect(redirect)

    @http.route('/website/customize_template_get', type='json', auth='user', website=True)
    def customize_template_get(self, key, full=False, bundles=False):
        """ Get inherit view's informations of the template ``key``. By default, only
        returns ``customize_show`` templates (which can be active or not), if
        ``full=True`` returns inherit view's informations of the template ``key``.
        ``bundles=True`` returns also the asset bundles
        """
        return request.registry["ir.ui.view"].customize_template_get(
            request.cr, request.uid, key, full=full, bundles=bundles,
            context=request.context)

    @http.route('/website/get_view_translations', type='json', auth='public', website=True)
    def get_view_translations(self, xml_id, lang=None):
        lang = lang or request.context.get('lang')
        return request.registry["ir.ui.view"].get_view_translations(
            request.cr, request.uid, xml_id, lang=lang, context=request.context)

    @http.route('/website/set_translations', type='json', auth='public', website=True)
    def set_translations(self, data, lang):
        irt = request.registry.get('ir.translation')
        for view_id, trans in data.items():
            view_id = int(view_id)
            for t in trans:
                initial_content = t['initial_content'].strip()
                new_content = t['new_content'].strip()
                tid = t['translation_id']
                if not tid:
                    old_trans = irt.search_read(
                        request.cr, request.uid,
                        [
                            ('type', '=', 'view'),
                            ('res_id', '=', view_id),
                            ('lang', '=', lang),
                            ('src', '=', initial_content),
                        ])
                    if old_trans:
                        tid = old_trans[0]['id']
                if tid:
                    vals = {'value': new_content}
                    irt.write(request.cr, request.uid, [tid], vals)
                else:
                    new_trans = {
                        'name': 'website',
                        'res_id': view_id,
                        'lang': lang,
                        'type': 'view',
                        'source': initial_content,
                        'value': new_content,
                    }
                    if t.get('gengo_translation'):
                        new_trans['gengo_translation'] = t.get('gengo_translation')
                        new_trans['gengo_comment'] = t.get('gengo_comment')
                    irt.create(request.cr, request.uid, new_trans)
        return True

    @http.route('/website/translations', type='json', auth="public", website=True)
    def get_website_translations(self, lang):
        module_obj = request.registry['ir.module.module']
        module_ids = module_obj.search(request.cr, request.uid, [('name', 'ilike', 'website'), ('state', '=', 'installed')], context=request.context)
        modules = [x['name'] for x in module_obj.read(request.cr, request.uid, module_ids, ['name'], context=request.context)]
        return WebClient().translations(mods=modules, lang=lang)

    @http.route('/website/attach', type='http', auth='user', methods=['POST'], website=True)
    def attach(self, func, upload=None, url=None, disable_optimization=None):
        # the upload argument doesn't allow us to access the files if more than
        # one file is uploaded, as upload references the first file
        # therefore we have to recover the files from the request object
        Attachments = request.registry['ir.attachment']  # registry for the attachment table

        uploads = []
        message = None
        if not upload: # no image provided, storing the link and the image name
            uploads.append({'website_url': url})
            name = url.split("/").pop()                       # recover filename
            attachment_id = Attachments.create(request.cr, request.uid, {
                'name':name,
                'type': 'url',
                'url': url,
                'res_model': 'ir.ui.view',
            }, request.context)
        else:                                                  # images provided
            try:
                attachment_ids = []
                for c_file in request.httprequest.files.getlist('upload'):
                    image_data = c_file.read()
                    image = Image.open(cStringIO.StringIO(image_data))
                    w, h = image.size
                    if w*h > 42e6: # Nokia Lumia 1020 photo resolution
                        raise ValueError(
                            u"Image size excessive, uploaded images must be smaller "
                            u"than 42 million pixel")

                    if not disable_optimization and image.format in ('PNG', 'JPEG'):
                        image_data = image_save_for_web(image)

                    attachment_id = Attachments.create(request.cr, request.uid, {
                        'name': c_file.filename,
                        'datas': image_data.encode('base64'),
                        'datas_fname': c_file.filename,
                        'res_model': 'ir.ui.view',
                    }, request.context)
                    attachment_ids.append(attachment_id)

                uploads = Attachments.read(
                    request.cr, request.uid, attachment_ids, ['website_url'],
                    context=request.context)
            except Exception, e:
                logger.exception("Failed to upload image to attachment")
                message = unicode(e)

        return """<script type='text/javascript'>
            window.parent['%s'](%s, %s);
        </script>""" % (func, json.dumps(uploads), json.dumps(message))

    @http.route(['/website/publish'], type='json', auth="public", website=True)
    def publish(self, id, object):
        _id = int(id)
        _object = request.registry[object]
        obj = _object.browse(request.cr, request.uid, _id)

        values = {}
        if 'website_published' in _object._fields:
            values['website_published'] = not obj.website_published
        _object.write(request.cr, request.uid, [_id],
                      values, context=request.context)

        obj = _object.browse(request.cr, request.uid, _id)
        return bool(obj.website_published)

    @http.route(['/website/seo_suggest/<keywords>'], type='http', auth="public", website=True)
    def seo_suggest(self, keywords):
        url = "http://google.com/complete/search"
        try:
            req = urllib2.Request("%s?%s" % (url, werkzeug.url_encode({
                'ie': 'utf8', 'oe': 'utf8', 'output': 'toolbar', 'q': keywords})))
            request = urllib2.urlopen(req)
        except (urllib2.HTTPError, urllib2.URLError):
            return []
        xmlroot = ET.fromstring(request.read())
        return json.dumps([sugg[0].attrib['data'] for sugg in xmlroot if len(sugg) and sugg[0].attrib['data']])

    #------------------------------------------------------
    # Themes
    #------------------------------------------------------

    def get_view_ids(self, xml_ids):
        ids = []
        imd = request.registry['ir.model.data']
        for xml_id in xml_ids:
            if "." in xml_id:
                xml = xml_id.split(".")
                view_model, id = imd.get_object_reference(request.cr, request.uid, xml[0], xml[1])
            else:
                id = int(xml_id)
            ids.append(id)
        return ids

    @http.route(['/website/theme_customize_get'], type='json', auth="public", website=True)
    def theme_customize_get(self, xml_ids):
        view = request.registry["ir.ui.view"]
        enable = []
        disable = []
        ids = self.get_view_ids(xml_ids)
        context = dict(request.context or {}, active_test=True)
        for v in view.browse(request.cr, request.uid, ids, context=context):
            if v.active:
                enable.append(v.xml_id)
            else:
                disable.append(v.xml_id)
        return [enable, disable]

    @http.route(['/website/theme_customize'], type='json', auth="public", website=True)
    def theme_customize(self, enable, disable):
        """ enable or Disable lists of ``xml_id`` of the inherit templates
        """
        cr, uid, context, pool = request.cr, request.uid, request.context, request.registry
        view = pool["ir.ui.view"]
        context = dict(request.context or {}, active_test=True)

        def set_active(ids, active):
            if ids:
                view.write(cr, uid, self.get_view_ids(ids), {'active': active}, context=context)

        set_active(disable, False)
        set_active(enable, True)

        return True

    @http.route(['/website/theme_customize_reload'], type='http', auth="public", website=True)
    def theme_customize_reload(self, href, enable, disable):
        self.theme_customize(enable and enable.split(",") or [],disable and disable.split(",") or [])
        return request.redirect(href + ("&theme=true" if "#" in href else "#theme=true"))

    @http.route(['/website/multi_render'], type='json', auth="public", website=True)
    def multi_render(self, ids_or_xml_ids, values=None):
        res = {}
        for id_or_xml_id in ids_or_xml_ids:
            res[id_or_xml_id] = request.registry["ir.ui.view"].render(request.cr, request.uid, id_or_xml_id, values=values, engine='ir.qweb', context=request.context)
        return res

    #------------------------------------------------------
    # Helpers
    #------------------------------------------------------
    @http.route(['/website/kanban'], type='http', auth="public", methods=['POST'], website=True)
    def kanban(self, **post):
        return request.website.kanban_col(**post)

    def placeholder(self, response):
        return request.registry['website']._image_placeholder(response)

    @http.route([
        '/website/image',
        '/website/image/<xmlid>',
        '/website/image/<xmlid>/<field>',
        '/website/image/<model>/<id>/<field>',
        '/website/image/<model>/<id>/<field>/<int:max_width>x<int:max_height>'
        ], auth="public", website=True)
    def website_image(self, model=None, id=None, field=None, xmlid=None, max_width=None, max_height=None):
        """ Fetches the requested field and ensures it does not go above
        (max_width, max_height), resizing it if necessary.

        If the record is not found or does not have the requested field,
        returns a placeholder image via :meth:`~.placeholder`.

        Sets and checks conditional response parameters:
        * :mailheader:`ETag` is always set (and checked)
        * :mailheader:`Last-Modified is set iif the record has a concurrency
          field (``__last_update``)

        The requested field is assumed to be base64-encoded image data in
        all cases.

        xmlid can be used to load the image. But the field image must by base64-encoded
        """
        if xmlid and "." in xmlid:
            try:
                record = request.env.ref(xmlid)
                model, id = record._name, record.id
            except:
                raise werkzeug.exceptions.NotFound()
            if model == 'ir.attachment' and not field:
                if record.sudo().type == "url":
                    field = "url"
                else:
                    field = "datas"

        if not model or not id or not field:
            raise werkzeug.exceptions.NotFound()

        try:
            idsha = str(id).split('_')
            id = idsha[0]
            response = werkzeug.wrappers.Response()
            return request.registry['website']._image(
                request.cr, request.uid, model, id, field, response, max_width, max_height,
                cache=STATIC_CACHE if len(idsha) > 1 else None)
        except Exception:
            logger.exception("Cannot render image field %r of record %s[%s] at size(%s,%s)",
                             field, model, id, max_width, max_height)
            response = werkzeug.wrappers.Response()
            return self.placeholder(response)

    #------------------------------------------------------
    # Server actions
    #------------------------------------------------------
    @http.route([
        '/website/action/<path_or_xml_id_or_id>',
        '/website/action/<path_or_xml_id_or_id>/<path:path>',
        ], type='http', auth="public", website=True)
    def actions_server(self, path_or_xml_id_or_id, **post):
        cr, uid, context = request.cr, request.uid, request.context
        res, action_id, action = None, None, None
        ServerActions = request.registry['ir.actions.server']

        # find the action_id: either an xml_id, the path, or an ID
        if isinstance(path_or_xml_id_or_id, basestring) and '.' in path_or_xml_id_or_id:
            action_id = request.registry['ir.model.data'].xmlid_to_res_id(request.cr, request.uid, path_or_xml_id_or_id, raise_if_not_found=False)
        if not action_id:
            action_ids = ServerActions.search(cr, uid, [('website_path', '=', path_or_xml_id_or_id), ('website_published', '=', True)], context=context)
            action_id = action_ids and action_ids[0] or None
        if not action_id:
            try:
                action_id = int(path_or_xml_id_or_id)
            except ValueError:
                pass

        # check it effectively exists
        if action_id:
            action_ids = ServerActions.exists(cr, uid, [action_id], context=context)
            action_id = action_ids and action_ids[0] or None
        # run it, return only if we got a Response object
        if action_id:
            action = ServerActions.browse(cr, uid, action_id, context=context)
            if action.state == 'code' and action.website_published:
                action_res = ServerActions.run(cr, uid, [action_id], context=context)
                if isinstance(action_res, werkzeug.wrappers.Response):
                    res = action_res
        if res:
            return res
        return request.redirect('/')

    #------------------------------------------------------
    # Backend html field
    #------------------------------------------------------
    @http.route('/website/field/html', type='http', auth="public", website=True)
    def FieldTextHtml(self, model=None, res_id=None, field=None, callback=None, **kwargs):
        record = None
        if model and res_id:
            res_id = int(res_id)
            record = request.registry[model].browse(request.cr, request.uid, res_id, request.context)

        datarecord = json.loads(kwargs['datarecord'])
        kwargs.update({
            'content': record and getattr(record, field) or "",
            'model': model,
            'res_id': res_id,
            'field': field,
            'datarecord': datarecord
        })
        return request.website.render(kwargs.get("template") or "website.FieldTextHtml", kwargs)
