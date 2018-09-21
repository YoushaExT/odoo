odoo.define('iap.credit.checker', function (require) {
'use strict';

var widgetRegistry = require('web.widget_registry');
var Widget = require('web.Widget');

var core = require('web.core');
var rpc = require('web.rpc');

var QWeb = core.qweb;

var IAPCreditChecker = Widget.extend({
    className: 'o_field_iap_credit_checker',

    /**
     * @constructor
     * Prepares the basic rendering of edit mode by setting the root to be a
     * div.dropdown.open.
     * @see FieldChar.init
     */
    init: function (parent, data, options) {
        this._super.apply(this, arguments);
        this.service_name = options.attrs.service_name;
    },

    /**
     * @override
     */
    start: function () {
        this.$widget = $(QWeb.render('partner_autocomplete.iap_credit_checker'));
        this.$loading = this.$widget.find('.loading');
        this.$sufficient = this.$widget.find('.sufficient');
        this.$insufficient = this.$widget.find('.insufficient');
        this.$buyLink = this.$widget.find('.oe_link');

        this.$widget.appendTo(this.$el);

        this._getLink();
        this._getCredits();
    },

    //--------------------------------------------------------------------------
    // Private
    //--------------------------------------------------------------------------
    _getCredits: function () {
        var self = this;
        this._showLoading();

        return rpc.query({
            model: 'iap.account',
            method: 'get_credits',
            args: [this.service_name],
        }, {
            shadow: true,
        }).then(function (credit) {
            if (credit) self._showSufficient(credit);
            else self._showInsufficient();
        });
    },

    _getLink: function () {
        var self = this;
        return rpc.query({
            model: 'iap.account',
            method: 'get_credits_url',
            args: [this.service_name],
        }, {
            shadow: true,
        }).then(function (url) {
            self.$buyLink.attr('href', url);
        });
    },

    _showLoading: function () {
        this.$loading.show();
        this.$sufficient.hide();
        this.$insufficient.hide();
    },
    _showSufficient: function (credits) {
        this.$loading.hide();
        this.$sufficient.show().find('.remaining_credits').text(credits);
        this.$insufficient.hide();
    },
    _showInsufficient: function () {
        this.$loading.hide();
        this.$sufficient.hide();
        this.$insufficient.show();
    },
});

widgetRegistry.add('iap_credit_checker', IAPCreditChecker);

return IAPCreditChecker;
});
