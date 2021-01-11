# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
import odoo
from odoo.tests import HttpCase, tagged
from odoo.tests.common import HOST
from odoo.tools import mute_logger
from odoo.addons.http_routing.models.ir_http import slug

from unittest.mock import patch


@tagged('-at_install', 'post_install')
class TestRedirect(HttpCase):

    def setUp(self):
        super(TestRedirect, self).setUp()

        self.user_portal = self.env['res.users'].with_context({'no_reset_password': True}).create({
            'name': 'Test Website Portal User',
            'login': 'portal_user',
            'password': 'portal_user',
            'email': 'portal_user@mail.com',
            'groups_id': [(6, 0, [self.env.ref('base.group_portal').id])]
        })

        self.base_url = "http://%s:%s" % (HOST, odoo.tools.config['http_port'])

    def test_01_redirect_308_model_converter(self):

        self.env['website.rewrite'].create({
            'name': 'Test Website Redirect',
            'redirect_type': '308',
            'url_from': '/test_website/country/<model("res.country"):country>',
            'url_to': '/redirected/country/<model("res.country"):country>',
        })
        country_ad = self.env.ref('base.ad')

        """ Ensure 308 redirect with model converter works fine, including:
                - Correct & working redirect as public user
                - Correct & working redirect as logged in user
                - Correct replace of url_for() URLs in DOM
        """
        url = '/test_website/country/' + slug(country_ad)
        redirect_url = url.replace('test_website', 'redirected')

        # [Public User] Open the original url and check redirect OK
        r = self.url_open(url)
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.url.endswith(redirect_url), "Ensure URL got redirected")
        self.assertTrue(country_ad.name in r.text, "Ensure the controller returned the expected value")
        self.assertTrue(redirect_url in r.text, "Ensure the url_for has replaced the href URL in the DOM")

        # [Logged In User] Open the original url and check redirect OK
        self.authenticate("portal_user", "portal_user")
        r = self.url_open(url)
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.url.endswith(redirect_url), "Ensure URL got redirected (2)")
        self.assertTrue('Logged In' in r.text, "Ensure logged in")
        self.assertTrue(country_ad.name in r.text, "Ensure the controller returned the expected value (2)")
        self.assertTrue(redirect_url in r.text, "Ensure the url_for has replaced the href URL in the DOM")

    @mute_logger('odoo.addons.http_routing.models.ir_http')  # mute 403 warning
    def test_02_redirect_308_RequestUID(self):
        self.env['website.rewrite'].create({
            'name': 'Test Website Redirect',
            'redirect_type': '308',
            'url_from': '/test_website/200/<model("test.model"):rec>',
            'url_to': '/test_website/308/<model("test.model"):rec>',
        })

        rec_published = self.env['test.model'].create({'name': 'name', 'website_published': True})
        rec_unpublished = self.env['test.model'].create({'name': 'name', 'website_published': False})

        WebsiteHttp = odoo.addons.website.models.ir_http.Http

        def _get_error_html(env, code, value):
            return str(code).split('_')[-1], "CUSTOM %s" % code

        with patch.object(WebsiteHttp, '_get_error_html', _get_error_html):
            # Patch will avoid to display real 404 page and regenerate assets each time and unlink old one.
            # And it allow to be sur that exception id handled by handle_exception and return a "managed error" page.

            # published
            resp = self.url_open("/test_website/200/name-%s" % rec_published.id, allow_redirects=False)
            self.assertEqual(resp.status_code, 308)
            self.assertEqual(resp.headers.get('Location'), self.base_url + "/test_website/308/name-%s" % rec_published.id)

            resp = self.url_open("/test_website/308/name-%s" % rec_published.id, allow_redirects=False)
            self.assertEqual(resp.status_code, 200)

            resp = self.url_open("/test_website/200/xx-%s" % rec_published.id, allow_redirects=False)
            self.assertEqual(resp.status_code, 308)
            self.assertEqual(resp.headers.get('Location'), self.base_url + "/test_website/308/xx-%s" % rec_published.id)

            resp = self.url_open("/test_website/308/xx-%s" % rec_published.id, allow_redirects=False)
            self.assertEqual(resp.status_code, 301)
            self.assertEqual(resp.headers.get('Location'), self.base_url + "/test_website/308/name-%s" % rec_published.id)

            resp = self.url_open("/test_website/200/xx-%s" % rec_published.id, allow_redirects=True)
            self.assertEqual(resp.status_code, 200)
            self.assertEqual(resp.url, self.base_url + "/test_website/308/name-%s" % rec_published.id)

            # unexisting
            resp = self.url_open("/test_website/200/name-100", allow_redirects=False)
            self.assertEqual(resp.status_code, 308)
            self.assertEqual(resp.headers.get('Location'), self.base_url + "/test_website/308/name-100")

            resp = self.url_open("/test_website/308/name-100", allow_redirects=False)
            self.assertEqual(resp.status_code, 404)
            self.assertEqual(resp.text, "CUSTOM 404")

            resp = self.url_open("/test_website/200/xx-100", allow_redirects=False)
            self.assertEqual(resp.status_code, 308)
            self.assertEqual(resp.headers.get('Location'), self.base_url + "/test_website/308/xx-100")

            resp = self.url_open("/test_website/308/xx-100", allow_redirects=False)
            self.assertEqual(resp.status_code, 404)
            self.assertEqual(resp.text, "CUSTOM 404")

            # unpublish
            resp = self.url_open("/test_website/200/name-%s" % rec_unpublished.id, allow_redirects=False)
            self.assertEqual(resp.status_code, 308)
            self.assertEqual(resp.headers.get('Location'), self.base_url + "/test_website/308/name-%s" % rec_unpublished.id)

            resp = self.url_open("/test_website/308/name-%s" % rec_unpublished.id, allow_redirects=False)
            self.assertEqual(resp.status_code, 403)
            self.assertEqual(resp.text, "CUSTOM 403")

            resp = self.url_open("/test_website/200/xx-%s" % rec_unpublished.id, allow_redirects=False)
            self.assertEqual(resp.status_code, 308)
            self.assertEqual(resp.headers.get('Location'), self.base_url + "/test_website/308/xx-%s" % rec_unpublished.id)

            resp = self.url_open("/test_website/308/xx-%s" % rec_unpublished.id, allow_redirects=False)
            self.assertEqual(resp.status_code, 403)
            self.assertEqual(resp.text, "CUSTOM 403")

            # with seo_name as slug
            rec_published.seo_name = "seo_name"
            rec_unpublished.seo_name = "seo_name"

            resp = self.url_open("/test_website/200/seo-name-%s" % rec_published.id, allow_redirects=False)
            self.assertEqual(resp.status_code, 308)
            self.assertEqual(resp.headers.get('Location'), self.base_url + "/test_website/308/seo-name-%s" % rec_published.id)

            resp = self.url_open("/test_website/308/seo-name-%s" % rec_published.id, allow_redirects=False)
            self.assertEqual(resp.status_code, 200)

            resp = self.url_open("/test_website/200/xx-%s" % rec_unpublished.id, allow_redirects=False)
            self.assertEqual(resp.status_code, 308)
            self.assertEqual(resp.headers.get('Location'), self.base_url + "/test_website/308/xx-%s" % rec_unpublished.id)

            resp = self.url_open("/test_website/308/xx-%s" % rec_unpublished.id, allow_redirects=False)
            self.assertEqual(resp.status_code, 403)
            self.assertEqual(resp.text, "CUSTOM 403")

            resp = self.url_open("/test_website/200/xx-100", allow_redirects=False)
            self.assertEqual(resp.status_code, 308)
            self.assertEqual(resp.headers.get('Location'), self.base_url + "/test_website/308/xx-100")

            resp = self.url_open("/test_website/308/xx-100", allow_redirects=False)
            self.assertEqual(resp.status_code, 404)
            self.assertEqual(resp.text, "CUSTOM 404")
