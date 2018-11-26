odoo.define('mail.tour', function (require) {
"use strict";

var core = require('web.core');
var tour = require('web_tour.tour');

var _t = core._t;

tour.register('mail_tour', {
    url: "/web",
}, [tour.STEPS.SHOW_APPS_MENU_ITEM, {
    trigger: '.o_app[data-menu-xmlid="mail.menu_root_discuss"]',
    content: _t('Want to <b>get in touch</b> with your contacts? <i>Discuss with them here.</i>'),
    position: 'right',
    edition: 'community',
}, {
    trigger: '.o_app[data-menu-xmlid="mail.menu_root_discuss"]',
    content: _t('Want to <b>get in touch</b> with your contacts? <i>Discuss with them here.</i>'),
    position: 'bottom',
    edition: 'enterprise',
}, {
    trigger: '.o_mail_discuss .o_mail_discuss_sidebar .o_add[data-type="public"]',
    content: _t("<p>Channels make it easy to organize information across different topics and groups.</p> <p>Try to <b>create your first channel</b> (e.g. sales, marketing, product XYZ, after work party, etc).</p>"),
    position: 'bottom',
}, {
    trigger: '.o_mail_discuss .o_mail_discuss_sidebar .o_mail_add_thread[data-type="public"]',
    content: _t("<p>Create a channel here.</p>"),
    position: 'right',
    run: function (actions) {
        var t = new Date().getTime();
        actions.text("SomeChannel_" + t, this.$anchor.find("input"));
    },
}, {
    trigger: ".ui-menu-item > a",
    auto: true,
    in_modal: false,
}, {
    trigger: '.o_mail_discuss .o_composer_text_field',
    content: _t("<p><b>Write a message</b> to the members of the channel here.</p> <p>You can notify someone with <i>'@'</i> or link another channel with <i>'#'</i>. Start your message with <i>'/'</i> to get the list of possible commands.</p>"),
    position: "top",
    width: 350,
    run: function (actions) {
        var t = new Date().getTime();
        actions.text("SomeText_" + t, this.$anchor);
    },
}, {
    trigger: '.o_mail_discuss .o_thread_composer .o_composer_button_send',
    content: _t("Post your message on the thread"),
    position: "top",
}, {
    trigger: '.o_mail_discuss .o_mail_thread .o_thread_message_star',
    content: _t("Messages can be <b>starred</b> to remind you to check back later."),
    position: "right",
}, {
    trigger: '.o_mail_discuss .o_mail_discuss_item[data-thread-id="mailbox_starred"]',
    content: _t("Once a message has been starred, you can come back and review it at any time here."),
    position: "bottom",
}, {
    trigger: '.o_mail_discuss .o_mail_discuss_sidebar .o_add[data-type="dm_chat"]',
    content: _t("<p><b>Chat with coworkers</b> in real-time using direct messages.</p><p><i>You might need to invite users from the Settings app first.</i></p>"),
    position: 'bottom',
}]);

});
