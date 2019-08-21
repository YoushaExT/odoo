odoo.define('portal.rating.composer', function (require) {
'use strict';

var publicWidget = require('web.public.widget');
var session = require('web.session');
var portalChatter = require('portal.chatter');

var PortalComposer = portalChatter.PortalComposer;

var STAR_RATING_RATIO = 2;  // conversion factor from the star (1-5) to the db rating range (1-10)

/**
 * RatingPopupComposer
 *
 * Display the rating average with a static star widget, and open
 * a popup with the portal composer when clicking on it.
 **/
var RatingPopupComposer = publicWidget.Widget.extend({
    template: 'website_rating.PopupComposer',
    xmlDependencies: [
        '/portal/static/src/xml/portal_chatter.xml',
        '/website_rating/static/src/xml/portal_tools.xml',
        '/website_rating/static/src/xml/portal_rating_composer.xml',
    ],

    init: function (parent, options) {
        this._super.apply(this, arguments);
        this.rating_avg = Math.round(options['ratingAvg'] / STAR_RATING_RATIO * 100) / 100 || 0.0;
        this.rating_total = options['ratingTotal'] || 0.0;

        this.options = _.defaults({}, options, {
            'token': false,
            'res_model': false,
            'res_id': false,
            'pid': 0,
            'display_composer': options['disable_composer'] ? false : !session.is_website_user,
            'display_rating': true,
            'csrf_token': odoo.csrf_token,
            'user_id': session.user_id,
        });
    },
    /**
     * @override
     */
    start: function () {
        var defs = [];
        defs.push(this._super.apply(this, arguments));

        // instanciate and insert composer widget
        this._composer = new PortalComposer(this, this.options);
        defs.push(this._composer.replace(this.$('.o_portal_chatter_composer')));

        return Promise.all(defs);
    },
});

publicWidget.registry.RatingPopupComposer = publicWidget.Widget.extend({
    selector: '.o_rating_popup_composer',

    /**
     * @override
     */
    start: function () {
        var ratingPopup = new RatingPopupComposer(this, this.$el.data());
        return Promise.all([
            this._super.apply(this, arguments),
            ratingPopup.appendTo(this.$el)
        ]);
    },
});
});
