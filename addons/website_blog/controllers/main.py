# -*- coding: utf-8 -*-

import datetime
import werkzeug

from openerp import tools
from openerp.addons.web import http
from openerp.addons.web.http import request
from openerp.addons.website.models.website import slug
from openerp.osv.orm import browse_record
from openerp.tools.translate import _
from openerp import SUPERUSER_ID
from openerp.tools import html2plaintext


class QueryURL(object):
    def __init__(self, path='', path_args=None, **args):
        self.path = path
        self.args = args
        self.path_args = set(path_args or [])

    def __call__(self, path=None, path_args=None, **kw):
        path = path or self.path
        for k, v in self.args.items():
            kw.setdefault(k, v)
        path_args = set(path_args or []).union(self.path_args)
        paths, fragments = [], []
        for key, value in kw.items():
            if value and key in path_args:
                if isinstance(value, browse_record):
                    paths.append((key, slug(value)))
                else:
                    paths.append((key, value))
            elif value:
                if isinstance(value, list) or isinstance(value, set):
                    fragments.append(werkzeug.url_encode([(key, item) for item in value]))
                else:
                    fragments.append(werkzeug.url_encode([(key, value)]))
        for key, value in paths:
            path += '/' + key + '/%s' % value
        if fragments:
            path += '?' + '&'.join(fragments)
        return path


class WebsiteBlog(http.Controller):
    _blog_post_per_page = 20
    _post_comment_per_page = 10

    def nav_list(self):
        blog_post_obj = request.registry['blog.post']
        groups = blog_post_obj.read_group(
            request.cr, request.uid, [], ['name', 'create_date'],
            groupby="create_date", orderby="create_date desc", context=request.context)
        for group in groups:
            begin_date = datetime.datetime.strptime(group['__domain'][0][2], tools.DEFAULT_SERVER_DATETIME_FORMAT).date()
            end_date = datetime.datetime.strptime(group['__domain'][1][2], tools.DEFAULT_SERVER_DATETIME_FORMAT).date()
            group['date_begin'] = '%s' % datetime.date.strftime(begin_date, tools.DEFAULT_SERVER_DATE_FORMAT)
            group['date_end'] = '%s' % datetime.date.strftime(end_date, tools.DEFAULT_SERVER_DATE_FORMAT)
        return groups

    @http.route([
        '/blog',
        '/blog/page/<int:page>',
    ], type='http', auth="public", website=True)
    def blogs(self, page=1, **post):
        cr, uid, context = request.cr, request.uid, request.context
        blog_obj = request.registry['blog.post']
        total = blog_obj.search(cr, uid, [], count=True, context=context)
        pager = request.website.pager(
            url='/blog',
            total=total,
            page=page,
            step=self._blog_post_per_page,
        )
        post_ids = blog_obj.search(cr, uid, [], offset=(page-1)*self._blog_post_per_page, limit=self._blog_post_per_page, context=context)
        posts = blog_obj.browse(cr, uid, post_ids, context=context)
        blog_url = QueryURL('', ['blog', 'tag'])
        return request.website.render("website_blog.latest_blogs", {
            'posts': posts,
            'pager': pager,
            'blog_url': blog_url,
        })

    @http.route([
        '/blog/<model("blog.blog"):blog>',
        '/blog/<model("blog.blog"):blog>/page/<int:page>',
        '/blog/<model("blog.blog"):blog>/tag/<model("blog.tag"):tag>',
        '/blog/<model("blog.blog"):blog>/tag/<model("blog.tag"):tag>/page/<int:page>',
    ], type='http', auth="public", website=True)
    def blog(self, blog=None, tag=None, page=1, **opt):
        """ Prepare all values to display the blog.

        :return dict values: values for the templates, containing

         - 'blog': current blog
         - 'blogs': all blogs for navigation
         - 'pager': pager of posts
         - 'tag': current tag
         - 'tags': all tags, for navigation
         - 'nav_list': a dict [year][month] for archives navigation
         - 'date': date_begin optional parameter, used in archives navigation
         - 'blog_url': help object to create URLs
        """
        date_begin, date_end = opt.get('date_begin'), opt.get('date_end')

        cr, uid, context = request.cr, request.uid, request.context
        blog_post_obj = request.registry['blog.post']

        blog_obj = request.registry['blog.blog']
        blog_ids = blog_obj.search(cr, uid, [], order="create_date asc", context=context)
        blogs = blog_obj.browse(cr, uid, blog_ids, context=context)

        domain = []
        if blog:
            domain += [('blog_id', '=', blog.id)]
        if tag:
            domain += [('tag_ids', 'in', tag.id)]
        if date_begin and date_end:
            domain += [("create_date", ">=", date_begin), ("create_date", "<=", date_end)]

        blog_url = QueryURL('', ['blog', 'tag'], blog=blog, tag=tag, date_begin=date_begin, date_end=date_end)
        post_url = QueryURL('', ['blogpost'], tag_id=tag and tag.id or None, date_begin=date_begin, date_end=date_end)

        blog_post_ids = blog_post_obj.search(cr, uid, domain, order="create_date desc", context=context)
        blog_posts = blog_post_obj.browse(cr, uid, blog_post_ids, context=context)

        pager = request.website.pager(
            url=blog_url(),
            total=len(blog_posts),
            page=page,
            step=self._blog_post_per_page,
        )
        pager_begin = (page - 1) * self._blog_post_per_page
        pager_end = page * self._blog_post_per_page
        blog_posts = blog_posts[pager_begin:pager_end]

        tags = blog.all_tags()[blog.id]

        values = {
            'blog': blog,
            'blogs': blogs,
            'tags': tags,
            'tag': tag,
            'blog_posts': blog_posts,
            'pager': pager,
            'nav_list': self.nav_list(),
            'blog_url': blog_url,
            'post_url': post_url,
            'date': date_begin,
        }
        response = request.website.render("website_blog.blog_post_short", values)
        return response

    @http.route([
            '''/blog/<model("blog.blog"):blog>/post/<model("blog.post", "[('blog_id','=',blog[0])]"):blog_post>''',
    ], type='http', auth="public", website=True)
    def blog_post(self, blog, blog_post, tag_id=None, page=1, enable_editor=None, **post):
        """ Prepare all values to display the blog.

        :return dict values: values for the templates, containing

         - 'blog_post': browse of the current post
         - 'blog': browse of the current blog
         - 'blogs': list of browse records of blogs
         - 'tag': current tag, if tag_id in parameters
         - 'tags': all tags, for tag-based navigation
         - 'pager': a pager on the comments
         - 'nav_list': a dict [year][month] for archives navigation
         - 'next_post': next blog post, to direct the user towards the next interesting post
        """
        cr, uid, context = request.cr, request.uid, request.context
        tag_obj = request.registry['blog.tag']
        blog_post_obj = request.registry['blog.post']
        date_begin, date_end = post.get('date_begin'), post.get('date_end')

        pager_url = "/blogpost/%s" % blog_post.id

        pager = request.website.pager(
            url=pager_url,
            total=len(blog_post.website_message_ids),
            page=page,
            step=self._post_comment_per_page,
            scope=7
        )
        pager_begin = (page - 1) * self._post_comment_per_page
        pager_end = page * self._post_comment_per_page
        comments = blog_post.website_message_ids[pager_begin:pager_end]

        tag = None
        if tag_id:
            tag = request.registry['blog.tag'].browse(request.cr, request.uid, int(tag_id), context=request.context)
        post_url = QueryURL('', ['blogpost'], blogpost=blog_post, tag_id=tag_id, date_begin=date_begin, date_end=date_end)
        blog_url = QueryURL('', ['blog', 'tag'], blog=blog_post.blog_id, tag=tag, date_begin=date_begin, date_end=date_end)

        if not blog_post.blog_id.id == blog.id:
            return request.redirect("/blog/%s/post/%s" % (slug(blog_post.blog_id), slug(blog_post)))

        tags = tag_obj.browse(cr, uid, tag_obj.search(cr, uid, [], context=context), context=context)

        # Find next Post
        visited_blogs = request.httprequest.cookies.get('visited_blogs') or ''
        visited_ids = filter(None, visited_blogs.split(','))
        visited_ids = map(lambda x: int(x), visited_ids)
        if blog_post.id not in visited_ids:
            visited_ids.append(blog_post.id)
        next_post_id = blog_post_obj.search(cr, uid, [
            ('id', 'not in', visited_ids),
        ], order='ranking desc', limit=1, context=context)
        if not next_post_id:
            next_post_id = blog_post_obj.search(cr, uid, [('id', '!=', blog.id)], order='ranking desc', limit=1, context=context)
        next_post = next_post_id and blog_post_obj.browse(cr, uid, next_post_id[0], context=context) or False

        values = {
            'tags': tags,
            'tag': tag,
            'blog': blog,
            'blog_post': blog_post,
            'main_object': blog_post,
            'nav_list': self.nav_list(),
            'enable_editor': enable_editor,
            'next_post': next_post,
            'date': date_begin,
            'post_url': post_url,
            'blog_url': blog_url,
            'pager': pager,
            'comments': comments,
        }
        response = request.website.render("website_blog.blog_post_complete", values)
        response.set_cookie('visited_blogs', ','.join(map(str, visited_ids)))

        request.session[request.session_id] = request.session.get(request.session_id, [])
        if not (blog_post.id in request.session[request.session_id]):
            request.session[request.session_id].append(blog_post.id)
            # Increase counter
            blog_post_obj.write(cr, SUPERUSER_ID, [blog_post.id], {
                'visits': blog_post.visits+1,
            },context=context)
        return response

    def _blog_post_message(self, user, blog_post_id=0, **post):
        cr, uid, context = request.cr, request.uid, request.context
        blog_post = request.registry['blog.post']
        partner_obj = request.registry['res.partner']

        if uid != request.website.user_id.id:
            partner_ids = [user.partner_id.id]
        else:
            partner_ids = blog_post._find_partner_from_emails(
                cr, SUPERUSER_ID, 0, [post.get('email')], context=context)
            if not partner_ids or not partner_ids[0]:
                partner_ids = [partner_obj.create(cr, SUPERUSER_ID, {'name': post.get('name'), 'email': post.get('email')}, context=context)]

        message_id = blog_post.message_post(
            cr, SUPERUSER_ID, int(blog_post_id),
            body=post.get('comment'),
            type='comment',
            subtype='mt_comment',
            author_id=partner_ids[0],
            path=post.get('path', False),
            context=context)
        return message_id

    @http.route(['/blogpost/comment'], type='http', auth="public", methods=['POST'], website=True)
    def blog_post_comment(self, blog_post_id=0, **post):
        cr, uid, context = request.cr, request.uid, request.context
        if post.get('comment'):
            user = request.registry['res.users'].browse(cr, uid, uid, context=context)
            blog_post = request.registry['blog.post']
            blog_post.check_access_rights(cr, uid, 'read')
            self._blog_post_message(user, blog_post_id, **post)
        return werkzeug.utils.redirect(request.httprequest.referrer + "#comments")

    def _get_discussion_detail(self, ids, publish=False, **post):
        cr, uid, context = request.cr, request.uid, request.context
        values = []
        mail_obj = request.registry.get('mail.message')
        for message in mail_obj.browse(cr, SUPERUSER_ID, ids, context=context):
            values.append({
                "id": message.id,
                "author_name": message.author_id.name,
                "author_image": message.author_id.image and \
                    ("data:image/png;base64,%s" % message.author_id.image) or \
                    '/website_blog/static/src/img/anonymous.png',
                "date": message.date,
                'body': html2plaintext(message.body),
                'website_published' : message.website_published,
                'publish' : publish,
            })
        return values

    @http.route(['/blogpost/post_discussion'], type='json', auth="public", website=True)
    def post_discussion(self, blog_post_id, **post):
        cr, uid, context = request.cr, request.uid, request.context
        publish = request.registry['res.users'].has_group(cr, uid, 'base.group_website_publisher')
        user = request.registry['res.users'].browse(cr, uid, uid, context=context)
        id = self._blog_post_message(user, blog_post_id, **post)
        return self._get_discussion_detail([id], publish, **post)

    @http.route('/blogpost/new', type='http', auth="public", website=True)
    def blog_post_create(self, blog_id, **post):
        cr, uid, context = request.cr, request.uid, request.context
        new_blog_post_id = request.registry['blog.post'].create(cr, uid, {
            'blog_id': blog_id,
            'name': _("Blog Post Title"),
            'subtitle': _("Subtitle"),
            'content': '',
            'website_published': False,
        }, context=context)
        new_blog_post = request.registry['blog.post'].browse(cr, uid, new_blog_post_id, context=context)
        return werkzeug.utils.redirect("/blog/%s/post/%s?enable_editor=1" % (slug(new_blog_post.blog_id), slug(new_blog_post)))

    @http.route('/blogpost/duplicate', type='http', auth="public", website=True)
    def blog_post_copy(self, blog_post_id, **post):
        """ Duplicate a blog.

        :param blog_post_id: id of the blog post currently browsed.

        :return redirect to the new blog created
        """
        cr, uid, context = request.cr, request.uid, request.context
        create_context = dict(context, mail_create_nosubscribe=True)
        nid = request.registry['blog.post'].copy(cr, uid, blog_post_id, {}, context=create_context)
        new_blog_post = request.registry['blog.post'].browse(cr, uid, nid, context=context)
        post = request.registry['blog.post'].browse(cr, uid, nid, context)
        return werkzeug.utils.redirect("/blog/%s/post/%s?enable_editor=1" % (slug(post.blog_id), slug(new_blog_post)))

    @http.route('/blogpost/get_discussion/', type='json', auth="public", website=True)
    def discussion(self, post_id=0, path=None, count=False, **post):
        cr, uid, context = request.cr, request.uid, request.context
        mail_obj = request.registry.get('mail.message')
        domain = [('res_id', '=', int(post_id)), ('model', '=', 'blog.post'), ('path', '=', path)]
        #check current user belongs to website publisher group
        publish = request.registry['res.users'].has_group(cr, uid, 'base.group_website_publisher')
        if not publish:
            domain.append(('website_published', '=', True))
        ids = mail_obj.search(cr, SUPERUSER_ID, domain, count=count)
        if count:
            return ids
        return self._get_discussion_detail(ids, publish, **post)

    @http.route('/blogpost/get_discussions/', type='json', auth="public", website=True)
    def discussions(self, post_id=0, paths=None, count=False, **post):
        ret = []
        for path in paths:
            result = self.discussion(post_id=post_id, path=path, count=count, **post)
            ret.append({"path": path, "val": result})
        return ret

    @http.route('/blogpost/change_background', type='json', auth="public", website=True)
    def change_bg(self, post_id=0, image=None, **post):
        if not post_id:
            return False
        return request.registry['blog.post'].write(request.cr, request.uid, [int(post_id)], {'background_image': image}, request.context)

    @http.route('/blog/get_user/', type='json', auth="public", website=True)
    def get_user(self, **post):
        return [False if request.session.uid else True]
