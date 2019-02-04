odoo.define('website.translateMenu', function (require) {
'use strict';

var utils = require('web.utils');
var TranslatorMenu = require('website.editor.menu.translate');
var websiteNavbarData = require('website.navbar');

var TranslatePageMenu = websiteNavbarData.WebsiteNavbarActionWidget.extend({
    actions: _.extend({}, websiteNavbarData.WebsiteNavbar.prototype.actions || {}, {
        edit_master: '_goToMasterPage',
        translate: '_startTranslateMode',
    }),

    /**
     * @override
     */
    start: function () {
        var context;
        this.trigger_up('context_get', {
            extra: true,
            callback: function (ctx) {
                context = ctx;
            },
        });
        this._mustEditTranslations = context.edit_translations;
        if (this._mustEditTranslations) {
            this._startTranslateMode();
        }
        return this._super.apply(this, arguments);
    },

    //--------------------------------------------------------------------------
    // Actions
    //--------------------------------------------------------------------------

    /**
     * Redirects the user to the same page but in the original language and in
     * edit mode.
     *
     * @private
     * @returns {Deferred}
     */
    _goToMasterPage: function () {
        var lang = '/' + utils.get_cookie('frontend_lang');

        var current = document.createElement('a');
        current.href = window.location.toString();
        current.search += (current.search ? '&' : '?') + 'enable_editor=1';
        if (current.pathname.indexOf(lang) === 0) {
            current.pathname = current.pathname.replace(lang, '');
        }

        var link = document.createElement('a');
        link.href = '/website/lang/default';
        link.search += (link.search ? '&' : '?') + 'r=' + encodeURIComponent(current.pathname + current.search + current.hash);

        window.location = link.href;
        return $.Deferred();
    },
    /**
     * Redirects the user to the same page in translation mode (or start the
     * translator is translation mode is already enabled).
     *
     * @private
     * @returns {Deferred}
     */
    _startTranslateMode: function () {
        if (!this._mustEditTranslations) {
            window.location.search += '&edit_translations';
            return $.Deferred();
        }
        var translator = new TranslatorMenu(this);
        return translator.prependTo(document.body);
    },
});

websiteNavbarData.websiteNavbarRegistry.add(TranslatePageMenu, '.o_menu_systray:has([data-action="translate"])');
});
