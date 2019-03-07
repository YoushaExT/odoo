# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import base64
import itertools
import logging
import werkzeug

from odoo import http, modules, tools, _
from odoo.exceptions import AccessError, UserError
from odoo.http import request
from odoo.osv import expression

from odoo.addons.http_routing.models.ir_http import slug
from odoo.addons.website_profile.controllers.main import WebsiteProfile
from odoo.addons.website.models.ir_http import sitemap_qs2dom

_logger = logging.getLogger(__name__)


class WebsiteSlides(WebsiteProfile):
    SLIDES_PER_PAGE = 12
    SLIDES_PER_ASIDE = 20
    SLIDES_PER_CATEGORY = 4
    _channel_order_by_criterion = {
        'vote': 'total_votes desc',
        'view': 'total_views desc',
        'date': 'create_date desc',
    }

    def sitemap_slide(env, rule, qs):
        Channel = env['slide.channel']
        dom = sitemap_qs2dom(qs=qs, route='/slides/', field=Channel._rec_name)
        dom += env['website'].get_current_website().website_domain()
        for channel in Channel.search(dom):
            loc = '/slides/%s' % slug(channel)
            if not qs or qs.lower() in loc:
                yield {'loc': loc}

    # SLIDE UTILITIES
    # --------------------------------------------------

    def _fetch_slide(self, slide_id):
        slide = request.env['slide.slide'].browse(int(slide_id)).exists()
        if not slide:
            return {'error': 'slide_wrong'}
        try:
            slide.check_access_rights('read')
            slide.check_access_rule('read')
        except:
            return {'error': 'slide_access'}
        return {'slide': slide}

    def _set_viewed_slide(self, slide, quiz_attempts_inc=False):
        if request.env.user._is_public() or not slide.website_published or not slide.channel_id.is_member:
            viewed_slides = request.session.setdefault('viewed_slides', list())
            if slide.id not in viewed_slides:
                slide.sudo().public_views += 1
                viewed_slides.append(slide.id)
                request.session['viewed_slides'] = viewed_slides
        else:
            slide.action_set_viewed(quiz_attempts_inc=quiz_attempts_inc)
        return True

    def _set_completed_slide(self, slide, quiz_attempts_inc=False):
        if slide.website_published and slide.channel_id.is_member:
            slide.action_set_completed(quiz_attempts_inc=quiz_attempts_inc)
        return True

    def _get_slide_detail(self, slide):
        base_domain = request.website.website_domain()
        if slide.channel_id.channel_type == 'documentation':
            base_domain = expression.AND([base_domain, [('website_published', '=', True), ('id', '!=', slide.id)]])
            related_domain = expression.AND([base_domain, [('channel_id', '=', slide.channel_id.id)]])

            most_viewed_slides = request.env['slide.slide'].search(base_domain, limit=self.SLIDES_PER_ASIDE, order='total_views desc')
            related_slides = request.env['slide.slide'].search(related_domain, limit=self.SLIDES_PER_ASIDE)
            uncategorized_slides, channel_slides = request.env['slide.slide'], request.env['slide.slide']
        else:
            if slide.channel_id.can_publish:
                related_domain = expression.AND([base_domain, [('channel_id', '=', slide.channel_id.id)]])
            else:
                related_domain = expression.AND([base_domain, [('channel_id', '=', slide.channel_id.id), ('website_published', '=', True)]])
            channel_slides = request.env['slide.slide'].search(related_domain)
            most_viewed_slides, related_slides = request.env['slide.slide'], request.env['slide.slide']
            # temporarily kept for fullscreen, to remove asap
            uncategorized_domain = expression.AND([base_domain, [('channel_id', '=', slide.channel_id.id), ('category_id', '=', False)]])
            uncategorized_slides = request.env['slide.slide'].search(uncategorized_domain)

        channel_slides_ids = slide.channel_id.slide_ids.ids
        slide_index = channel_slides_ids.index(slide.id)
        previous_slide = slide.channel_id.slide_ids[slide_index-1] if slide_index > 0 else None
        next_slide = slide.channel_id.slide_ids[slide_index+1] if slide_index < len(channel_slides_ids) - 1 else None

        values = {
            # slide
            'slide': slide,
            'most_viewed_slides': most_viewed_slides,
            'related_slides': related_slides,
            'previous_slide': previous_slide,
            'next_slide': next_slide,
            'uncategorized_slides': uncategorized_slides,
            'channel_slides': channel_slides,
            # user
            'user': request.env.user,
            'is_public_user': request.website.is_public_user(),
            # rating and comments
            'comments': slide.website_message_ids or [],
        }

        # allow rating and comments
        if slide.channel_id.allow_comment:
            values.update({
                'message_post_hash': slide._generate_signed_token(request.env.user.partner_id.id),
                'message_post_pid': request.env.user.partner_id.id,
            })

        return values

    def _get_slide_quiz_info(self, slide, quiz_done=False):
        return slide._compute_quiz_info(request.env.user.partner_id, quiz_done=quiz_done)[slide.id]

    # CHANNEL UTILITIES
    # --------------------------------------------------

    def _get_channel_progress(self, channel, include_quiz=False):
        """ Replacement to user_progress. Both may exist in some transient state. """
        slides = request.env['slide.slide'].sudo().search([('channel_id', '=', channel.id)])
        channel_progress = dict((sid, dict()) for sid in slides.ids)
        if not request.env.user._is_public() and channel.is_member:
            slide_partners = request.env['slide.slide.partner'].sudo().search([
                ('channel_id', '=', channel.id),
                ('partner_id', '=', request.env.user.partner_id.id)
            ])
            for slide_partner in slide_partners:
                channel_progress[slide_partner.slide_id.id].update(slide_partner.read()[0])
                if slide_partner.slide_id.question_ids:
                    gains = [slide_partner.slide_id.quiz_first_attempt_reward,
                             slide_partner.slide_id.quiz_second_attempt_reward,
                             slide_partner.slide_id.quiz_third_attempt_reward,
                             slide_partner.slide_id.quiz_fourth_attempt_reward]
                    channel_progress[slide_partner.slide_id.id]['quiz_gain'] = gains[slide_partner.quiz_attempts_count] if slide_partner.quiz_attempts_count < len(gains) else gains[-1]

        if include_quiz:
            quiz_info = slides._compute_quiz_info(request.env.user.partner_id, quiz_done=False)
            for slide_id, slide_info in quiz_info.items():
                channel_progress[slide_id].update(slide_info)

        return channel_progress

    def _extract_channel_tag_search(self, **post):
        tags = request.env['slide.channel.tag']
        for key in (_key for _key in post if _key.startswith('channel_tag_group_id_')):
            group_id, tag_id = False, False
            try:
                group_id = int(key.lstrip('channel_tag_group_id_'))
                tag_id = int(post[key])
            except:
                pass
            else:
                search_tag = request.env['slide.channel.tag'].search([('id', '=', tag_id), ('group_id', '=', group_id)]).exists()
                if search_tag:
                    tags |= search_tag
        return tags

    def _build_channel_domain(self, base_domain, slide_type=None, my=False, **post):
        search_term = post.get('search')
        channel_tag_id = post.get('channel_tag_id')
        tags = self._extract_channel_tag_search(**post)

        domain = base_domain
        if search_term:
            domain = expression.AND([
                domain,
                ['|', ('name', 'ilike', search_term), ('description', 'ilike', search_term)]])
        if channel_tag_id:
            domain = expression.AND([domain, [('tag_ids', 'in', [channel_tag_id])]])
        elif tags:
            domain = expression.AND([domain, [('tag_ids', 'in', tags.ids)]])

        if slide_type and 'nbr_%s' % slide_type in request.env['slide.channel']:
            domain = expression.AND([domain, [('nbr_%s' % slide_type, '>', 0)]])

        if my:
            domain = expression.AND([domain, [('partner_ids', '=', request.env.user.partner_id.id)]])
        return domain

    # --------------------------------------------------
    # SLIDE.CHANNEL MAIN / SEARCH
    # --------------------------------------------------

    @http.route('/slides', type='http', auth="public", website=True)
    def slides_channel_home(self, **post):
        """ Home page for eLearning platform. Is mainly a container page, does not allow search / filter. """
        domain = request.website.website_domain()
        channels_all = request.env['slide.channel'].search(domain)
        if not request.env.user._is_public():
            channels_my = channels_all.filtered(lambda channel: channel.is_member).sorted('completion', reverse=True)[:3]
        else:
            channels_my = request.env['slide.channel']
        channels_popular = channels_all.sorted('total_votes', reverse=True)[:3]
        channels_newest = channels_all.sorted('create_date', reverse=True)[:3]

        # fetch 'latests achievements' for non logged people
        if request.env.user._is_public():
            achievements = request.env['gamification.badge.user'].sudo().search([('badge_id.is_published', '=', True)], limit=5)
            challenges = None
            challenges_done = None
        else:
            achievements = None
            challenges = request.env['gamification.challenge'].sudo().search([
                ('category', '=', 'slides'),
                ('reward_id.is_published', '=', True)
            ], order='id asc', limit=5)
            challenges_done = request.env['gamification.badge.user'].sudo().search([
                ('challenge_id', 'in', challenges.ids),
                ('user_id', '=', request.env.user.id),
                ('badge_id.is_published', '=', True)
            ]).mapped('challenge_id')

        # fetch 'heroes of the week' for non logged people
        if request.env.user._is_public():
            users = request.env['res.users'].sudo().search([
                ('karma', '>', 0),
                ('website_published', '=', True)], limit=5, order='create_date desc')
        else:
            users = None

        return request.render('website_slides.courses_home', {
            'user': request.env.user,
            'is_public_user': request.website.is_public_user(),
            'channels_my': channels_my,
            'channels_popular': channels_popular,
            'channels_newest': channels_newest,
            'achievements': achievements,
            'users': users,
            'challenges': challenges,
            'challenges_done': challenges_done,
        })

    @http.route('/slides/all', type='http', auth="public", website=True)
    def slides_channel_all(self, slide_type=None, my=False, **post):
        """ Home page displaying a list of courses displayed according to some
        criterion and search terms.

          :param string slide_type: if provided, filter the course to contain at
           least one slide of type 'slide_type'. Used notably to display courses
           with certifications;
          :param bool my: if provided, filter the slide.channels for which the
           current user is a member of
          :param dict post: post parameters, including

           * ``search``: filter on course description / name;
           * ``channel_tag_id``: filter on courses containing this tag;
           * ``channel_tag_group_id_<id>``: filter on courses containing this tag
             in the tag group given by <id> (used in navigation based on tag group);
        """
        domain = request.website.website_domain()
        domain = self._build_channel_domain(domain, slide_type=slide_type, my=my, **post)

        order = self._channel_order_by_criterion.get(post.get('sorting', 'date'), 'create_date desc')

        channels = request.env['slide.channel'].search(domain, order=order)
        # channels_layouted = list(itertools.zip_longest(*[iter(channels)] * 4, fillvalue=None))

        tag_groups = request.env['slide.channel.tag.group'].search(['&', ('tag_ids', '!=', False), ('website_published', '=', True)])
        search_tags = self._extract_channel_tag_search(**post)

        return request.render('website_slides.courses_all', {
            'user': request.env.user,
            'is_public_user': request.website.is_public_user(),
            'channels': channels,
            'tag_groups': tag_groups,
            'search_term': post.get('search'),
            'search_slide_type': slide_type,
            'search_my': my,
            'search_tags': search_tags,
            'search_channel_tag_id': post.get('channel_tag_id'),
        })

    def _prepare_additional_channel_values(self, values, **kwargs):
        return values

    @http.route([
        '/slides/<model("slide.channel"):channel>',
        '/slides/<model("slide.channel"):channel>/page/<int:page>',
        '/slides/<model("slide.channel"):channel>/tag/<model("slide.tag"):tag>',
        '/slides/<model("slide.channel"):channel>/tag/<model("slide.tag"):tag>/page/<int:page>',
        '/slides/<model("slide.channel"):channel>/category/<model("slide.category"):category>',
        '/slides/<model("slide.channel"):channel>/category/<model("slide.category"):category>/page/<int:page>'
    ], type='http', auth="public", website=True, sitemap=sitemap_slide)
    def channel(self, channel, category=None, tag=None, page=1, slide_type=None, uncategorized=False, sorting=None, search=None, **kw):
        if not channel.can_access_from_current_website():
            raise werkzeug.exceptions.NotFound()

        domain = [('channel_id', '=', channel.id)]

        pager_url = "/slides/%s" % (channel.id)
        pager_args = {}
        slide_types = dict(request.env['slide.slide']._fields['slide_type']._description_selection(request.env))

        if search:
            domain += [
                '|', '|', '|',
                ('name', 'ilike', search),
                ('description', 'ilike', search),
                ('index_content', 'ilike', search),
                ('html_content', 'ilike', search)]
            pager_args['search'] = search
        else:
            if category:
                domain += [('category_id', '=', category.id)]
                pager_url += "/category/%s" % category.id
            elif tag:
                domain += [('tag_ids.id', '=', tag.id)]
                pager_url += "/tag/%s" % tag.id
            if uncategorized:
                domain += [('category_id', '=', False)]
                pager_url += "?uncategorized=1"
            elif slide_type:
                domain += [('slide_type', '=', slide_type)]
                pager_url += "?slide_type=%s" % slide_type

        # sorting criterion
        if channel.channel_type == 'documentation':
            actual_sorting = sorting if sorting and sorting in request.env['slide.slide']._order_by_strategy else channel.promote_strategy
        else:
            actual_sorting = 'sequence'
        order = request.env['slide.slide']._order_by_strategy[actual_sorting]
        pager_args['sorting'] = actual_sorting

        pager_count = request.env['slide.slide'].sudo().search_count(domain)
        pager = request.website.pager(url=pager_url, total=pager_count, page=page,
                                      step=self.SLIDES_PER_PAGE, scope=self.SLIDES_PER_PAGE,
                                      url_args=pager_args)

        values = {
            'channel': channel,
            # search
            'search_category': category,
            'search_tag': tag,
            'search_slide_type': slide_type,
            'search_uncategorized': uncategorized,
            'slide_types': slide_types,
            'sorting': actual_sorting,
            'search': search,
            # chatter
            'rating_avg': channel.rating_avg,
            'rating_count': channel.rating_count,
            # display data
            'user': request.env.user,
            'pager': pager,
            'is_public_user': request.website.is_public_user(),
            'is_slides_publisher': request.env.user.has_group('website.group_website_publisher'),
        }
        if not request.env.user._is_public():
            last_message_values = request.env['mail.message'].search([
                ('model', '=', channel._name),
                ('res_id', '=', channel.id),
                ('author_id', '=', request.env.user.partner_id.id),
                ('message_type', '=', 'comment'),
                ('website_published', '=', True)
            ], order='write_date DESC', limit=1).read(['body', 'rating_value'])
            last_message_data = last_message_values[0] if last_message_values else {}
            values.update({
                'message_post_hash': channel._sign_token(request.env.user.partner_id.id),
                'message_post_pid': request.env.user.partner_id.id,
                'last_message_id': last_message_data.get('id'),
                'last_message': tools.html2plaintext(last_message_data.get('body', '')),
                'last_rating_value': last_message_data.get('rating_value'),
            })

        # fetch slides and handle uncategorized slides; done as sudo because we want to display all
        # of them but unreachable ones won't be clickable (+ slide controller will crash anyway)
        # documentation mode may display less slides than content by category but overhead of
        # computation is reasonable
        if not category and not uncategorized:
            category_data = []
            all_categories = request.env['slide.category'].search([('channel_id', '=', channel.id)])
            all_slides = request.env['slide.slide'].sudo().search(domain, order=order)

            uncategorized_slides = all_slides.filtered(lambda slide: not slide.category_id)
            displayed_slides = uncategorized_slides
            if channel.channel_type == 'documentation':
                displayed_slides = uncategorized_slides[:self.SLIDES_PER_CATEGORY]
            if channel.channel_type == 'training' or displayed_slides:
                category_data.append({
                    'category': False, 'id': False,
                    'name':  _('Uncategorized'), 'slug_name':  _('Uncategorized'),
                    'total_slides': len(uncategorized_slides),
                    'slides': displayed_slides,
                })
            for category in all_categories:
                category_slides = all_slides.filtered(lambda slide: slide.category_id == category)
                displayed_slides = category_slides
                if channel.channel_type == 'documentation':
                    displayed_slides = category_slides[:self.SLIDES_PER_CATEGORY]
                    if not displayed_slides:
                        continue
                category_data.append({
                    'id': category.id,
                    'name': category.name,
                    'slug_name': slug(category),
                    'total_slides': len(category_slides),
                    'slides': displayed_slides,
                })
        elif uncategorized:
            if channel.channel_type == 'documentation':
                slides_sudo = request.env['slide.slide'].sudo().search(domain, limit=self.SLIDES_PER_PAGE, offset=pager['offset'], order=order)
            else:
                slides_sudo = request.env['slide.slide'].sudo().search(domain, order=order)
            category_data = [{
                'category': False,
                'id': False,
                'name':  _('Uncategorized'),
                'slug_name':  _('Uncategorized'),
                'total_slides': len(slides_sudo),
                'slides': slides_sudo,
            }]
        else:
            if channel.channel_type == 'documentation':
                slides_sudo = request.env['slide.slide'].sudo().search(domain, limit=self.SLIDES_PER_PAGE, offset=pager['offset'], order=order)
            else:
                slides_sudo = request.env['slide.slide'].sudo().search(domain, order=order)
            category_data = [{
                'category': category,
                'id': category.id,
                'name': category.name,
                'slug_name': slug(category),
                'total_slides': len(slides_sudo),
                'slides': slides_sudo,
            }]
        values['slide_promoted'] = request.env['slide.slide'].sudo().search(domain, limit=1, order=order)
        values['category_data'] = category_data
        values['channel_progress'] = self._get_channel_progress(channel)

        values = self._prepare_additional_channel_values(values, **kw)

        return request.render('website_slides.course_main', values)

    # SLIDE.CHANNEL UTILS
    # --------------------------------------------------

    @http.route('/slides/channel/add', type='http', auth='user', methods=['POST'], website=True)
    def slide_channel_create(self, *args, **kw):
        channel = request.env['slide.channel'].create(self._slide_channel_prepare_values(**kw))
        return werkzeug.utils.redirect("/slides/%s" % (slug(channel)))

    def _slide_channel_prepare_values(self, **kw):
        # `tag_ids` is a string representing a list of int with coma. i.e.: '2,5,7'
        # We don't want to allow user to create tags and tag groups on the fly.
        tag_ids = []
        if kw.get('tag_ids'):
            tag_ids = [int(item) for item in kw['tag_ids'].split(',')]

        return {
            'name': kw['name'],
            'description': kw.get('description'),
            'channel_type': kw.get('channel_type', 'documentation'),
            'user_id': request.env.user.id,
            'tag_ids': [(6, 0, tag_ids)],
            'allow_comment': bool(kw.get('allow_comment')),
        }

    @http.route('/slides/channel/enroll', type='http', auth='public', website=True)
    def slide_channel_join_http(self, channel_id):
        # TDE FIXME: why 2 routes ?
        if not request.website.is_public_user():
            channel = request.env['slide.channel'].browse(int(channel_id))
            channel.action_add_member()
        return werkzeug.utils.redirect("/slides/%s" % (slug(channel)))

    @http.route(['/slides/channel/join'], type='json', auth='public', website=True)
    def slide_channel_join(self, channel_id):
        if request.website.is_public_user():
            return {'error': 'public_user'}
        success = request.env['slide.channel'].browse(channel_id).action_add_member()
        if not success:
            return {'error': 'join_done'}
        return success

    @http.route('/slides/channel/resequence', type="json", website=True, auth="user")
    def resequence_slides(self, channel_id, slides_data):
        """" Reorder the slides within the channel by reassigning their 'sequence' field.
        This method also handles slides that are put in a new category (or uncategorized). """
        channel = request.env['slide.channel'].browse(int(channel_id))
        if not channel.can_publish:
            return {'error': 'Only the publishers of the channel can edit it'}

        slides = request.env['slide.slide'].search([
            ('id', 'in', [int(key) for key in slides_data.keys()]),
            ('channel_id', '=', channel.id)
        ])

        for slide in slides:
            slide_key = str(slide.id)
            slide.sequence = slides_data[slide_key]['sequence']
            slide.category_id = slides_data[slide_key]['category_id'] if 'category_id' in slides_data[slide_key] else False

    @http.route(['/slides/channel/tag/search_read'], type='json', auth='user', methods=['POST'], website=True)
    def slide_channel_tag_search_read(self, fields, domain):
        can_create = request.env['slide.channel.tag'].check_access_rights('create', raise_exception=False)
        return {
            'read_results': request.env['slide.channel.tag'].search_read(domain, fields),
            'can_create': can_create,
        }

    # --------------------------------------------------
    # SLIDE.SLIDE MAIN / SEARCH
    # --------------------------------------------------

    @http.route('''/slides/slide/<model("slide.slide", "[('website_id', 'in', (False, current_website_id))]"):slide>''', type='http', auth="public", website=True)
    def slide_view(self, slide, **kwargs):
        if not slide.channel_id.can_access_from_current_website():
            raise werkzeug.exceptions.NotFound()
        self._set_viewed_slide(slide)

        values = self._get_slide_detail(slide)
        # quiz-specific: update with karma and quiz information
        if slide.question_ids:
            values.update(self._get_slide_quiz_info(slide))
        # sidebar: update with user channel progress
        values['channel_progress'] = self._get_channel_progress(slide.channel_id, include_quiz=True)

        if 'fullscreen' in kwargs:
            return request.render("website_slides.slide_fullscreen", values)
        return request.render("website_slides.slide_main", values)

    @http.route('''/slides/slide/<model("slide.slide"):slide>/pdf_content''',
                type='http', auth="public", website=True, sitemap=False)
    def slide_get_pdf_content(self, slide):
        response = werkzeug.wrappers.Response()
        response.data = slide.datas and base64.b64decode(slide.datas) or b''
        response.mimetype = 'application/pdf'
        return response

    @http.route('/slides/slide/<int:slide_id>/get_image', type='http', auth="public", website=True, sitemap=False)
    def slide_get_image(self, slide_id, field='image_medium', width=0, height=0, crop=False, avoid_if_small=False, upper_limit=False):
        # Protect infographics by limiting access to 256px (large) images
        if field not in ('image_small', 'image_medium', 'image_large'):
            return werkzeug.exceptions.Forbidden()

        slide = request.env['slide.slide'].sudo().browse(slide_id).exists()
        if not slide:
            raise werkzeug.exceptions.NotFound()

        status, headers, content = request.env['ir.http'].sudo().binary_content(
            model='slide.slide', id=slide.id, field=field,
            default_mimetype='image/png')
        if status == 301:
            return request.env['ir.http']._response_by_status(status, headers, content)
        if status == 304:
            return werkzeug.wrappers.Response(status=304)

        if not content:
            content = self._get_default_avatar(field, headers, width, height)

        content = tools.limited_image_resize(
            content, width=width, height=height, crop=crop, upper_limit=upper_limit, avoid_if_small=avoid_if_small)

        image_base64 = base64.b64decode(content)
        headers.append(('Content-Length', len(image_base64)))
        response = request.make_response(image_base64, headers)
        response.status_code = status
        return response

    # SLIDE.SLIDE UTILS
    # --------------------------------------------------

    @http.route('/slides/slide/get_html_content', type="json", auth="public", website=True)
    def get_html_content(self, slide_id):
        fetch_res = self._fetch_slide(slide_id)
        if fetch_res.get('error'):
            return fetch_res
        return {
            'html_content': fetch_res['slide'].html_content
        }

    @http.route('/slides/slide/<model("slide.slide"):slide>/set_completed', website=True, type="http", auth="user")
    def slide_set_completed_and_redirect(self, slide, next_slide_id=None):
        self._set_completed_slide(slide)
        next_slide = None
        if next_slide_id:
            next_slide = self._fetch_slide(next_slide_id).get('slide', None)
        return werkzeug.utils.redirect("/slides/slide/%s" % (slug(next_slide) if next_slide else slug(slide)))

    @http.route('/slides/slide/set_completed', website=True, type="json", auth="public")
    def slide_set_completed(self, slide_id):
        if request.website.is_public_user():
            return {'error': 'public_user'}
        fetch_res = self._fetch_slide(slide_id)
        if fetch_res.get('error'):
            return fetch_res
        self._set_completed_slide(fetch_res['slide'])
        return {
            'channel_completion': fetch_res['slide'].channel_id.completion
        }

    @http.route('/slides/slide/like', type='json', auth="public", website=True)
    def slide_like(self, slide_id, upvote):
        if request.website.is_public_user():
            return {'error': 'public_user'}
        slide_partners = request.env['slide.slide.partner'].sudo().search([
            ('slide_id', '=', slide_id),
            ('partner_id', '=', request.env.user.partner_id.id)
        ])
        if (upvote and slide_partners.vote == 1) or (not upvote and slide_partners.vote == -1):
            return {'error': 'vote_done'}
        slide = request.env['slide.slide'].browse(int(slide_id))
        if upvote:
            slide.action_like()
        else:
            slide.action_dislike()
        slide.invalidate_cache()
        return slide.read(['likes', 'dislikes', 'user_vote'])[0]

    @http.route('/slides/slide/archive', type='json', auth='user', website=True)
    def slide_archive(self, slide_id):
        """ This route allows channel publishers to archive slides.
        It has to be done in sudo mode since only website_publishers can write on slides in ACLs """
        slide = request.env['slide.slide'].browse(int(slide_id))
        if slide.channel_id.can_publish:
            slide.sudo().active = False
            return True

        return False

    @http.route(['/slides/slide/send_share_email'], type='json', auth='user', website=True)
    def slide_send_share_email(self, slide_id, email):
        slide = request.env['slide.slide'].browse(int(slide_id))
        result = slide._send_share_email(email)
        return result

    # --------------------------------------------------
    # QUIZZ SECTION
    # --------------------------------------------------

    @http.route('/slides/slide/quiz/get', type="json", auth="public", website=True)
    def slide_quiz_get(self, slide_id):
        fetch_res = self._fetch_slide(slide_id)
        if fetch_res.get('error'):
            return fetch_res
        slide = fetch_res['slide']
        quiz_info = self._get_slide_quiz_info(slide)
        return {
            'questions': [{
                'id': question.id,
                'question': question.question,
                'answers': [{
                    'id': answer.id,
                    'text_value': answer.text_value,
                    'is_correct': answer.is_correct,
                } for answer in question.answer_ids],
            } for question in slide.question_ids],
            'quizAttemptsCount': quiz_info['quiz_attempts_count'],
            'quizKarmaGain': quiz_info['quiz_karma_gain'],
            'quizKarmaWon': quiz_info['quiz_karma_won'],
        }

    @http.route('/slides/slide/quiz/submit', type="json", auth="user", website=True)
    def slide_quiz_submit(self, slide_id, answer_ids):
        fetch_res = self._fetch_slide(slide_id)
        if fetch_res.get('error'):
            return fetch_res
        slide = fetch_res['slide']

        if slide.user_membership_id.completed:
            return {'error': 'slide_quiz_done'}

        all_questions = request.env['slide.question'].sudo().search([('slide_id', '=', slide.id)])

        user_answers = request.env['slide.answer'].sudo().search([('id', 'in', answer_ids)])
        if user_answers.mapped('question_id') != all_questions:
            return {'error': 'slide_quiz_incomplete'}

        user_bad_answers = user_answers.filtered(lambda answer: not answer.is_correct)
        user_good_answers = user_answers - user_bad_answers

        self._set_viewed_slide(slide, quiz_attempts_inc=True)
        quiz_info = self._get_slide_quiz_info(slide, quiz_done=True)

        rank_progress = {}
        if not user_bad_answers:
            slide._action_set_quiz_done()
            lower_bound = request.env.user.rank_id.karma_min
            upper_bound = request.env.user.next_rank_id.karma_min
            rank_progress = {
                'lowerBound': lower_bound,
                'upperBound': upper_bound,
                'currentKarma': request.env.user.karma,
                'motivational': request.env.user.next_rank_id.description_motivational,
                'progress': 100 * ((request.env.user.karma - lower_bound) / (upper_bound - lower_bound))
            }
        return {
            'goodAnswers': user_good_answers.ids,
            'badAnswers': user_bad_answers.ids,
            'completed': not user_bad_answers,
            'quizKarmaWon': quiz_info['quiz_karma_won'],
            'quizKarmaGain': quiz_info['quiz_karma_gain'],
            'quizAttemptsCount': quiz_info['quiz_attempts_count'],
            'rankProgress': rank_progress
        }

    # --------------------------------------------------
    # CATEGORY MANAGEMENT
    # --------------------------------------------------

    @http.route(['/slides/category/search_read'], type='json', auth='user', methods=['POST'], website=True)
    def slide_category_search_read(self, fields, domain):
        can_create = request.env['slide.category'].check_access_rights('create', raise_exception=False)
        return {
            'read_results': request.env['slide.category'].search_read(domain, fields),
            'can_create': can_create,
        }

    @http.route('/slides/category/add', type="http", website=True, auth="user")
    def slide_category_add(self, channel_id, name):
        """ Adds a category to the specified channel. If categories already exist
        within this channel, it will be added at the bottom (sequence+1) """
        channel = request.env['slide.channel'].browse(int(channel_id))

        values = {
            'name': name,
            'channel_id': channel.id
        }

        latest_category = request.env['slide.category'].search_read([
            ('channel_id', '=', channel.id)
        ], ["sequence"], order="sequence desc", limit=1)
        if latest_category:
            values['sequence'] = latest_category[0]['sequence'] + 1

        request.env['slide.category'].create(values)

        return werkzeug.utils.redirect("/slides/%s" % (slug(channel)))

    # --------------------------------------------------
    # SLIDE.UPLOAD
    # --------------------------------------------------

    @http.route(['/slides/prepare_preview'], type='json', auth='user', methods=['POST'], website=True)
    def prepare_preview(self, **data):
        Slide = request.env['slide.slide']
        document_type, document_id = Slide._find_document_data_from_url(data['url'])
        preview = {}
        if not document_id:
            preview['error'] = _('Please enter valid youtube or google doc url')
            return preview
        existing_slide = Slide.search([('channel_id', '=', int(data['channel_id'])), ('document_id', '=', document_id)], limit=1)
        if existing_slide:
            preview['error'] = _('This video already exists in this channel <a target="_blank" href="/slides/slide/%s">click here to view it </a>') % existing_slide.id
            return preview
        values = Slide._parse_document_url(data['url'], only_preview_fields=True)
        if values.get('error'):
            preview['error'] = _('Could not fetch data from url. Document or access right not available.\nHere is the received response: %s') % values['error']
            return preview
        return values

    @http.route(['/slides/add_slide'], type='json', auth='user', methods=['POST'], website=True)
    def create_slide(self, *args, **post):
        # check the size only when we upload a file.
        if post.get('datas'):
            file_size = len(post['datas']) * 3 / 4  # base64
            if (file_size / 1024.0 / 1024.0) > 25:
                return {'error': _('File is too big. File size cannot exceed 25MB')}

        values = dict((fname, post[fname]) for fname in self._get_valid_slide_post_values() if post.get(fname))

        if post.get('category_id'):
            if post['category_id'][0] == 0:
                values['category_id'] = request.env['slide.category'].create({
                    'name': post['category_id'][1]['name'],
                    'channel_id': values.get('channel_id')}).id
            else:
                values['category_id'] = post['category_id'][0]

        # handle exception during creation of slide and sent error notification to the client
        # otherwise client slide create dialog box continue processing even server fail to create a slide
        try:
            channel = request.env['slide.channel'].browse(values['channel_id'])
            can_upload = channel.can_upload
            can_publish = channel.can_publish
        except (UserError, AccessError) as e:
            _logger.error(e)
            return {'error': e.name}
        else:
            if not can_upload:
                return {'error': _('You cannot upload on this channel.')}

        try:
            values['user_id'] = request.env.uid
            values['website_published'] = values.get('website_published', False) and can_publish
            slide = request.env['slide.slide'].sudo().create(values)
        except (UserError, AccessError) as e:
            _logger.error(e)
            return {'error': e.name}
        except Exception as e:
            _logger.error(e)
            return {'error': _('Internal server error, please try again later or contact administrator.\nHere is the error message: %s') % e}

        redirect_url = "/slides/slide/%s" % (slide.id)
        if channel.channel_type == "training" and not slide.slide_type == "webpage":
            redirect_url = "/slides/%s" % (slug(channel))
        if slide.slide_type == 'webpage':
            redirect_url += "?enable_editor=1"
        if slide.slide_type == "quiz":
            action_id = request.env.ref('website_slides.action_slides_slides').id
            redirect_url = '/web#id=%s&action=%s&model=slide.slide&view_type=form' %(slide.id,action_id)
        return {
            'url': redirect_url,
            'channel_type': channel.channel_type,
            'slide_id': slide.id,
            'category_id': slide.category_id
            }

    def _get_valid_slide_post_values(self):
        return ['name', 'url', 'tag_ids', 'slide_type', 'channel_id', 'is_preview',
            'mime_type', 'datas', 'description', 'image', 'index_content', 'website_published']

    @http.route(['/slides/tag/search_read'], type='json', auth='user', methods=['POST'], website=True)
    def slide_tag_search_read(self, fields, domain):
        can_create = request.env['slide.tag'].check_access_rights('create', raise_exception=False)
        return {
            'read_results': request.env['slide.tag'].search_read(domain, fields),
            'can_create': can_create,
        }

    # --------------------------------------------------
    # EMBED IN THIRD PARTY WEBSITES
    # --------------------------------------------------

    @http.route('/slides/embed/<int:slide_id>', type='http', auth='public', website=True, sitemap=False)
    def slides_embed(self, slide_id, page="1", **kw):
        # Note : don't use the 'model' in the route (use 'slide_id'), otherwise if public cannot access the embedded
        # slide, the error will be the website.403 page instead of the one of the website_slides.embed_slide.
        # Do not forget the rendering here will be displayed in the embedded iframe

        # determine if it is embedded from external web page
        referrer_url = request.httprequest.headers.get('Referer', '')
        base_url = request.env['ir.config_parameter'].sudo().get_param('web.base.url')
        is_embedded = referrer_url and not bool(base_url in referrer_url) or False
        # try accessing slide, and display to corresponding template
        try:
            slide = request.env['slide.slide'].browse(slide_id)
            if is_embedded:
                request.env['slide.embed'].sudo()._add_embed_url(slide.id, referrer_url)
            values = self._get_slide_detail(slide)
            values['page'] = page
            values['is_embedded'] = is_embedded
            self._set_viewed_slide(slide)
            return request.render('website_slides.embed_slide', values)
        except AccessError: # TODO : please, make it clean one day, or find another secure way to detect
                            # if the slide can be embedded, and properly display the error message.
            return request.render('website_slides.embed_slide_forbidden', {})

    # --------------------------------------------------
    # PROFILE
    # --------------------------------------------------

    def _prepare_user_values(self, **kwargs):
        values = super(WebsiteSlides, self)._prepare_user_values(**kwargs)
        channel = self._get_channels(**kwargs)
        if channel:
            values['channel'] = channel
        return values

    def _get_channels(self, **kwargs):
        channels = []
        if kwargs.get('channel'):
            channels = kwargs['channel']
        elif kwargs.get('channel_id'):
            channels = request.env['slide.channel'].browse(int(kwargs['channel_id']))
        return channels

    def _prepare_user_slides_profile(self, user):
        courses = request.env['slide.channel.partner'].sudo().search([('partner_id', '=', user.partner_id.id)])
        courses_completed = courses.filtered(lambda c: c.completed)
        courses_ongoing = courses - courses_completed
        values = {
            'uid': request.env.user.id,
            'user': user,
            'main_object': user,
            'courses_completed': courses_completed,
            'courses_ongoing': courses_ongoing,
            'is_profile_page': True,
            'badge_category': 'slides',
        }
        return values

    def _prepare_user_profile_values(self, user, **post):
        values = super(WebsiteSlides, self)._prepare_user_profile_values(user, **post)
        if post.get('channel_id'):
            values.update({'edit_button_url_param': 'channel_id=' + str(post['channel_id'])})
        channels = self._get_channels(**post)
        if not channels:
            channels = request.env['slide.channel'].search([])
        values.update(self._prepare_user_values(channel=channels[0] if len(channels) == 1 else True, **post))
        values.update(self._prepare_user_slides_profile(user))
        return values
