odoo.define('website.s_blockquote_options', function (require) {
'use strict';

const options = require('web_editor.snippets.options');

options.registry.Blockquote = options.Class.extend({

    //--------------------------------------------------------------------------
    // Options
    //--------------------------------------------------------------------------

    /**
     * Change blockquote design.
     *
     * @see this.selectClass for parameters
     */
    display: function (previewMode, widgetValue, params) {

        // Classic
        this.$target.find('.s_blockquote_avatar').toggleClass('d-none', widgetValue !== 'classic');

        // Cover
        const $blockquote = this.$target.find('.s_blockquote_content');
        if (widgetValue === 'cover') {
            $blockquote.css({"background-image": "url('/web/image/website.s_blockquote_cover_default_image')"});
            $blockquote.css({"background-position": "50% 50%"});
            $blockquote.addClass('oe_img_bg');
        } else {
            $blockquote.css({"background-image": ""});
            $blockquote.css({"background-position": ""});
            $blockquote.removeClass('oe_img_bg');
            $blockquote.find('.s_blockquote_filter').contents().unwrap(); // Compatibility
        }

        // Minimalist
        this.$target.find('.s_blockquote_icon').toggleClass('d-none', widgetValue === 'minimalist');
        this.$target.find('footer').toggleClass('d-none', widgetValue === 'minimalist');
    },
});
});
