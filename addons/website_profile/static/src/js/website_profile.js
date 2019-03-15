odoo.define('website_profile.website_profile', function (require) {
'use strict';

var sAnimations = require('website.content.snippets.animation');

//TODO DBE : to change into publicWidget = require('web.public.widget'); after forward port in master
sAnimations.registry.websiteProfile = sAnimations.Class.extend({
    selector: '.o_wprofile_email_validation_container',
    read_events: {
        'click .send_validation_email': '_onSendValidationEmailClick',
        'click .validated_email_close': '_onCloseValidatedEmailClick',
    },

    //--------------------------------------------------------------------------
    // Handlers
    //--------------------------------------------------------------------------
    /**
     * @private
     * @param {Event} ev
     */
    _onSendValidationEmailClick: function (ev) {
        ev.preventDefault();
        var self = this;
        var $element = $(ev.currentTarget);
        this._rpc({
            route: '/profile/send_validation_email',
            params: {'redirect_url': $element.data('redirect_url')},
        }).then(function (data) {
            if (data) {
                self.$('button.validation_email_close').click();
            }
        });
    },

    /**
     * @private
     */
    _onCloseValidatedEmailClick: function () {
        this._rpc({
            route: '/profile/validate_email/close',
        });
    },
});

return sAnimations.registry.websiteProfile;

});
