odoo.define('website.s_countdown_options', function (require) {
'use strict';

const core = require('web.core');
const options = require('web_editor.snippets.options');

const qweb = core.qweb;

options.registry.countdown = options.Class.extend({
    events: _.extend({}, options.Class.prototype.events || {}, {
        'click .toggle-edit-message': '_onToggleEndMessageClick',
    }),

    //--------------------------------------------------------------------------
    // Options
    //--------------------------------------------------------------------------

    /**
     * Changes the countdown action at zero.
     *
     * @see this.selectClass for parameters
     */
    endAction: function (previewMode, widgetValue, params) {
        this.$target[0].dataset.endAction = widgetValue;
        if (widgetValue === 'message') {
            if (!this.$target.find('.s_countdown_end_message').length) {
                const message = this.endMessage || qweb.render('website.s_countdown.end_message');
                this.$target.find('.container').append(message);
            }
        } else {
            const $message = this.$target.find('.s_countdown_end_message').detach();
            if ($message.length) {
                this.endMessage = $message[0].outerHTML;
            }
        }
    },
    /**
    * Changes the countdown style.
    *
    * @see this.selectClass for parameters
    */
    layout: function (previewMode, widgetValue, params) {
        switch (widgetValue) {
            case 'circle':
                this.$target[0].dataset.progressBarStyle = 'disappear';
                this.$target[0].dataset.progressBarWeight = 'thin';
                this.$target[0].dataset.layoutBackground = 'none';
                break;
            case 'boxes':
                this.$target[0].dataset.progressBarStyle = 'none';
                this.$target[0].dataset.layoutBackground = 'plain';
                break;
            case 'clean':
                this.$target[0].dataset.progressBarStyle = 'none';
                this.$target[0].dataset.layoutBackground = 'none';
                break;
            case 'text':
                this.$target[0].dataset.progressBarStyle = 'none';
                this.$target[0].dataset.layoutBackground = 'none';
                break;
        }
        this.$target[0].dataset.layout = widgetValue;
    },

    //--------------------------------------------------------------------------
    // Public
    //--------------------------------------------------------------------------

    /**
     * @override
     */
    updateUIVisibility: async function () {
        await this._super(...arguments);
        const dataset = this.$target[0].dataset;

        // End Action UI
        this.$el.find('.toggle-edit-message')
            .toggleClass('d-none', dataset.endAction !== 'message');

        // End Message UI
        this.updateUIEndMessage();
    },
    /**
     * @see this.updateUI
     */
    updateUIEndMessage: function () {
        this.$target.find('.s_countdown_canvas_wrapper')
            .toggleClass("d-none", this.showEndMessage === true && this.$target.hasClass("hide-countdown"));
        this.$target.find('.s_countdown_end_message')
            .toggleClass("d-none", !this.showEndMessage);
    },

    //--------------------------------------------------------------------------
    // Private
    //--------------------------------------------------------------------------

    /**
     * @override
     */
    _computeWidgetState: function (methodName, params) {
        switch (methodName) {
            case 'endAction':
            case 'layout':
                return this.$target[0].dataset[methodName];
        }
        return this._super(...arguments);
    },

    //--------------------------------------------------------------------------
    // Handlers
    //--------------------------------------------------------------------------

    /**
     * @private
     */
    _onToggleEndMessageClick: function () {
        this.showEndMessage = !this.showEndMessage;
        this.$el.find(".toggle-edit-message")
            .toggleClass('text-primary', this.showEndMessage);
        this.updateUIEndMessage();
        this.trigger_up('cover_update');
    },
});
});
