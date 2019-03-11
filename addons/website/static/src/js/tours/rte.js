odoo.define('website.tour.rte', function (require) {
'use strict';

var ajax = require('web.ajax');
var session = require('web.session');
var tour = require('web_tour.tour');
var Wysiwyg = require('web_editor.wysiwyg.root');

var domReady = $.Deferred();
$(domReady.resolve.bind(domReady));
var ready = $.when(domReady, session.is_bound, ajax.loadXML());

tour.register('rte_translator', {
    test: true,
    wait_for: ready,
}, [{
    content: "click on Add a language",
    trigger: '.js_language_selector a:has(i.fa)',
}, {
    content: "select french",
    trigger: 'select[name="lang"]',
    run: 'text "fr_BE"',
}, {
    content: "load french",
    trigger: '.modal-footer button:first',
    extra_trigger: '.modal select[name="lang"]:propValueContains(fr_BE)',
}, {
    content : "click language dropdown",
    trigger : '.js_language_selector .dropdown-toggle',
    timeout: 60000,
}, {
    content: "go to english version",
    trigger: '.js_language_selector a[data-lang="en_US"]',
    extra_trigger: 'html[lang*="fr"]',
}, {
    content: "Open new page menu",
    trigger: '#new-content-menu > a',
    extra_trigger: 'a[data-action="edit"]',
}, {
    content: "click on new page",
    trigger: 'a[data-action="new_page"]',
}, {
    content: "insert page name",
    trigger: '#editor_new_page input[type="text"]',
    run: 'text rte_translator',
}, {
    content: "create page",
    trigger: 'button.btn-continue',
    extra_trigger: 'input[type="text"]:propValue(rte_translator)',
}, {
    content: "drop a snippet",
    trigger: "#snippet_structure .oe_snippet:eq(1) .oe_snippet_thumbnail",
    run: 'drag_and_drop #wrap',
}, {
    content: "change content",
    trigger: '.oe_overlay_options .oe_options:visible',
    run: function () {
        $("#wrap p:first").replaceWith('<p>Write one or <font style="background-color: yellow;">two paragraphs <b>describing</b></font> your product or\
                <font style="color: rgb(255, 0, 0);">services</font>. To be successful your content needs to be\
                useful to your <a href="/999">readers</a>.</p> <input placeholder="test translate placeholder"/>\
                <p>&lt;b&gt;&lt;/b&gt; is an HTML&nbsp;tag &amp; is empty</p>');
        $("#wrap img").attr("title", "test translate image title");
    }
}, {
    content: "save",
    trigger: 'button[data-action=save]',
    extra_trigger: '#wrap p:first b',
}, {
    content : "click language dropdown",
    trigger : '.js_language_selector .dropdown-toggle',
    extra_trigger: 'body:not(.o_wait_reload):not(:has(.note-editor))',
}, {
    content: "click on french version",
    trigger: '.js_language_selector a[data-lang="fr_BE"]',
    extra_trigger: 'html[lang*="en"]:not(:has(button[data-action=save]))',
}, {
    content: "translate",
    trigger: 'html:not(:has(#wrap p span)) .o_menu_systray a[data-action="translate"]',
}, {
    content: "close modal",
    trigger: '.modal-footer .btn-secondary',
}, {
    content: "check if translation is activate",
    trigger: '[data-oe-translation-id]',
}, {
    content: "translate text",
    trigger: '#wrap p font:first',
    run: function (action_helper) {
        action_helper.text('translated french text');
        Wysiwyg.setRange(this.$anchor.contents()[0], 22);
        this.$anchor.trigger($.Event( "keyup", {key: '_', keyCode: 95}));
    },
}, {
    content: "translate text with special char",
    trigger: '#wrap input + p span:first',
    run: function (action_helper) {
        action_helper.click();
        this.$anchor.prepend('&lt;{translated}&gt;');
        Wysiwyg.setRange(this.$anchor.contents()[0], 0);
        this.$anchor.trigger($.Event( "keyup", {key: '_', keyCode: 95}));
    },
}, {
    content: "click on input",
    trigger: '#wrap input:first',
    extra_trigger: '#wrap .o_dirty font:first:contains(translated french text)',
    run: 'click',
}, {
    content: "translate placeholder",
    trigger: 'input:first',
    run: 'text test french placeholder',
}, {
    content: "close modal",
    trigger: '.modal-footer .btn-primary',
    extra_trigger: '.modal input:propValue(test french placeholder)',
}, {
    content: "save translation",
    trigger: 'button[data-action=save]',
}, {
    content: "check: content is translated",
    trigger: '#wrap p font:first:contains(translated french text)',
    run: function () {}, // it's a check
}, {
    content: "check: content with special char is translated",
    trigger: "#wrap input + p:contains(<{translated}><b></b> is an HTML\xa0tag & )",
    run: function () {}, // it's a check

}, {
    content: "check: placeholder translation",
    trigger: 'input[placeholder="test french placeholder"]',
    run: function () {}, // it's a check

}, {
    content : "click language dropdown",
    trigger : '.js_language_selector .dropdown-toggle',

}, {
    content: "open language selector",
    trigger: '.js_language_selector button:first',
    extra_trigger: 'html[lang*="fr"]:not(:has(#wrap p span))',
}, {
    content: "return to english version",
    trigger: '.js_language_selector a[data-lang="en_US"]',
}, {
    content: "edit english version",
    trigger: 'a[data-action=edit]',
    extra_trigger: 'body:not(:has(#wrap p font:first:containsExact(paragraphs <b>describing</b>)))',
}, {
    content: "select text",
    extra_trigger: 'button[data-action=save]',
    trigger: '#wrap p',
    run: function (action_helper) {
        action_helper.click();
        var el = this.$anchor[0];
        this.$anchor.trigger('mousedown');
        Wysiwyg.setRange(el.childNodes[2], 6, el.childNodes[2], 13);
        this.$anchor.trigger('mouseup');
    },
}, {
    content: "underline",
    trigger: 'button.note-btn-underline',
}, {
    content: "save new change",
    trigger: 'button[data-action=save]',
    extra_trigger: '#wrap.o_dirty p u',

    }, {
    content : "click language dropdown",
    trigger : '.js_language_selector .dropdown-toggle',
    extra_trigger: '#wrap p u',
}, {
    content: "return in french",
    trigger : 'html[lang="en-US"] .js_language_selector .js_change_lang[data-lang="fr_BE"]',
}, {
    content: "check bis: content is translated",
    trigger: '#wrap p font:first:contains(translated french text)',
    extra_trigger: 'body:not(:has(button[data-action=save]))',
}, {
    content: "check bis: placeholder translation",
    trigger: 'input[placeholder="test french placeholder"]',
}, {
    content: "Open customize menu",
    trigger: "#customize-menu > .dropdown-toggle",
}, {
    content: "Open HTML editor",
    trigger: "[data-action='ace']",
}, {
    content: "Check that the editor is not showing translated content (1)",
    trigger: '.ace_text-layer .ace_line:contains("an HTML")',
    run: function (actions) {
        var lineEscapedText = $(this.$anchor.text()).text();
        if (lineEscapedText !== "&lt;b&gt;&lt;/b&gt; is an HTML&nbsp;tag &amp; is empty") {
            console.error('The HTML editor should display the correct untranslated content');
            $('body').addClass('rte_translator_error');
        }
    },
}, {
    content: "Check that the editor is not showing translated content (2)",
    trigger: 'body:not(.rte_translator_error)',
    run: function () {},
}]);
});
