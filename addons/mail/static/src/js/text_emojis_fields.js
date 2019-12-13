odoo.define('mail.text_emojis_field', function (require) {
"use strict";

var basicFields = require('web.basic_fields');
var core = require('web.core');
var emojis = require('mail.emojis');
var registry = require('web.field_registry');
var MailEmojisMixin = require('mail.emoji_mixin');
var _onEmojiClickMixin = MailEmojisMixin._onEmojiClick;
var QWeb = core.qweb;

/*
 * Common code for FieldTextEmojis and FieldCharEmojis
 */
var FieldEmojiCommon = {
    /**
     * @override
     * @private
     */
    init: function () {
        this._super.apply(this, arguments);
        this._triggerOnchange =_.throttle(this._triggerOnchange, 1000, {leading: false});
        this.emojis = emojis;
    },

    /**
     * This will add an emoji button that shows the emojis selection dropdown.
     *
     * We use 'on_attach_callback' because we need the element to be attached to the form first.
     * That's because the $emojisIcon element needs to be rendered outside of this $el
     * (which is an text element, that can't 'contain' any other elements).
     *
     * @override
     */
    on_attach_callback: function () {
        var self = this;
        if (!this.$emojisIcon) {
            this.$emojisIcon = $(QWeb.render('mail.EmojisDropdown', {widget: this}));
            this.$emojisIcon.find('.o_mail_emoji').on('click', this._onEmojiClick.bind(this));
            this.$el.after(this.$emojisIcon);
        }

        if (this.mode === 'edit') {
            this.$emojisIcon.show();
        } else {
            this.$emojisIcon.hide();
        }
    },

    //--------------------------------------------------------------------------
    // Handlers
    //--------------------------------------------------------------------------

    /**
     * @override
     * @private
     */
    _render: function () {
        this._super.apply(this, arguments);

        if (this.mode !== 'edit') {
            this.$el.html(this._formatText(this.$el.text()));
        }
    },

    /**
     * Overridden because we need to add the Emoji to the input AND trigger
     * the 'change' event to refresh the value.
     *
     * @override
     * @private
     */
    _onEmojiClick: function () {
        _onEmojiClickMixin.apply(this, arguments);
        self._isDirty = true;
        this.$input.trigger('change');
    },

    /**
     *
     * By default, the 'change' event is only triggered when the text element is blurred.
     *
     * We override this method because we want to update the value while
     * the user is typing his message (and not only on blur).
     *
     * @override
     * @private
     */
    _onKeydown: function () {
        this._super.apply(this, arguments);
        if (this.nodeOptions.onchange_on_keydown) {
            this._triggerOnchange();
        }
    },

    //--------------------------------------------------------------------------
    // Private
    //--------------------------------------------------------------------------

    /**
     * Used by MailEmojisMixin, check its document for more info.
     *
     * @private
     */
    _getTargetTextElement() {
        return this.$el;
    },

    /**
     * Triggers the 'change' event to refresh the value.
     * This method is throttled to run at most once every second.
     * (to avoid spamming the server while the user is typing his message)
     *
     * @private
     */
    _triggerOnchange: function () {
        this.$input.trigger('change');
    }
};

/**
 * Extension of the FieldText that will add emojis support
 */
var FieldTextEmojis = basicFields.FieldText.extend(MailEmojisMixin, FieldEmojiCommon);

/**
 * Extension of the FieldChar that will add emojis support
 */
var FieldCharEmojis = basicFields.FieldChar.extend(MailEmojisMixin, FieldEmojiCommon);

registry.add('text_emojis', FieldTextEmojis);
registry.add('char_emojis', FieldCharEmojis);

return {FieldTextEmojis: FieldTextEmojis, FieldCharEmojis: FieldCharEmojis};

});
