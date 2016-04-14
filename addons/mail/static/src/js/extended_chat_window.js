odoo.define('mail.ExtendedChatWindow', function (require) {
"use strict";

var chat_manager = require('mail.chat_manager');
var ChatWindow = require('mail.ChatWindow');
var composer = require('mail.composer');

return ChatWindow.extend({
    template: "mail.ExtendedChatWindow",

    start: function () {
        var self = this;
        var def;
        if (self.options.thread_less) {
            this.$el.addClass('o_thread_less');
            this.$('.o_chat_search_input input')
                .autocomplete({
                    source: function(request, response) {
                        chat_manager.search_partner(request.term, 10).done(response);
                    },
                    select: function(event, ui) {
                        self.trigger('open_dm_session', ui.item.id);
                    },
                })
                .focus();
        } else if (!self.options.input_less) {
            var basic_composer = new composer.BasicComposer(self, {mention_partners_restricted: true});
            basic_composer.on('post_message', self, function (message) {
                this.trigger('post_message', message, this.channel_id);
            });
            basic_composer.once('input_focused', self, function () {
                var channel = chat_manager.get_channel(this.channel_id);
                var suggestions = chat_manager.get_mention_partner_suggestions(channel);
                basic_composer.mention_set_prefetched_partners(suggestions);
            });
            def = basic_composer.replace(self.$('.o_chat_composer'));
        }
        return $.when(this._super(), def);
    },
    // Override on_keydown to only prevent jquery's blockUI to cancel event, but without sending
    // the message on ENTER keydown as this is handled by the BasicComposer
    on_keydown: function (event) {
        event.stopPropagation();
    },
});

});
