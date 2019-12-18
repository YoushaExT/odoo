odoo.define('website.s_table_of_content_options', function (require) {
'use strict';

const options = require('web_editor.snippets.options');

options.registry.TableOfContent = options.Class.extend({
    /**
     * @override
     */
    start: function () {
        this.targetedElements = 'h1, h2';
        const $headings = this.$target.find(this.targetedElements);
        if ($headings.length > 0) {
            this.isAnimateScrolling = this.$target.find(this.targetedElements)[0].dataset.anchor === 'true' ? true : false;
            this._generateNav();
        }
        // Generate the navbar if the content changes
        const targetNode = this.$target.find('.s_table_of_content_main')[0];
        const config = {attributes: false, childList: true, subtree: true, characterData: true};
        this.observer = new MutationObserver(() => this._generateNav());
        this.observer.observe(targetNode, config);
        return this._super(...arguments);
    },
    /**
     * @override
     */
    onClone: function () {
        this._generateNav();
    },

    //--------------------------------------------------------------------------
    // Options
    //--------------------------------------------------------------------------

    /**
     * Animate (or not) scrolling.
     *
     * @see this.selectClass for parameters
     */
    animateScrolling: function (previewMode, widgetValue, params) {
        const $headings = this.$target.find(this.targetedElements);
        const anchorValue = widgetValue ? 'true' : '0';
        _.each($headings, el => el.dataset.anchor = anchorValue);
        this.isAnimateScrolling = !!widgetValue;
    },
    /**
     * Change the navbar position.
     *
     * @see this.selectClass for parameters
     */
    navbarPosition: function (previewMode, widgetValue, params) {
        const $navbar = this.$target.find('.s_table_of_content_navbar_wrap');
        const $mainContent = this.$target.find('.s_table_of_content_main');
        if (widgetValue === 'top' || widgetValue === 'left') {
            $navbar.prev().before($navbar);
        }
        if (widgetValue === 'left' || widgetValue === 'right') {
            $navbar.removeClass('s_table_of_content_horizontal_navbar col-lg-12').addClass('s_table_of_content_vertical_navbar col-lg-3');
            $mainContent.removeClass('col-lg-12').addClass('col-lg-9');
            $navbar.find('.s_table_of_content_navbar').removeClass('list-group-horizontal-md');
        }
        if (widgetValue === 'right') {
            $navbar.next().after($navbar);
        }
        if (widgetValue === 'top') {
            $navbar.removeClass('s_table_of_content_vertical_navbar col-lg-3').addClass('s_table_of_content_horizontal_navbar col-lg-12');
            $navbar.find('.s_table_of_content_navbar').addClass('list-group-horizontal-md');
            $mainContent.removeClass('col-lg-9').addClass('col-lg-12');
        }
    },

    //--------------------------------------------------------------------------
    // Private
    //--------------------------------------------------------------------------

    /**
     * @private
     */
    _generateNav: function (ev) {
        const $nav = this.$target.find('.s_table_of_content_navbar');
        const $headings = this.$target.find(this.targetedElements);
        $nav.empty();
        _.each($headings, el => {
            const $el = $(el);
            const id = 'table_of_content_heading_' + _.now() + '_' + _.uniqueId();
            $('<a>').attr('href', "#" + id)
                    .addClass('table_of_content_link list-group-item list-group-item-action py-2 border-0 rounded-0')
                    .text($el.text())
                    .appendTo($nav);
            $el.attr('id', id);
            $el[0].dataset.anchor = this.isAnimateScrolling === true ? 'true' : '0';
        });
        $nav.find('a:first').addClass('active');
    },
    /**
     * @override
     */
    _computeWidgetState: function (methodName, params) {
        switch (methodName) {
            case 'animateScrolling': {
                const $headings = this.$target.find(this.targetedElements);
                if ($headings.length > 0) {
                    return $headings[0].dataset.anchor === 'true' ? 'true' : '0';
                } else {
                    return 'true';
                }
            }
            case 'navbarPosition': {
                const $navbar = this.$target.find('.s_table_of_content_navbar_wrap');
                if ($navbar.hasClass('s_table_of_content_horizontal_navbar')) {
                    return 'top';
                } else {
                    const $mainContent = this.$target.find('.s_table_of_content_main');
                    return $navbar.prev().is($mainContent) === true ? 'right' : 'left';
                }
            }
        }
        return this._super(...arguments);
    },
});

options.registry.TableOfContentMainColumns = options.Class.extend({
    /**
     * @override
     */
    start: function () {
        const leftPanelEl = this.$overlay.data('$optionsSection')[0];
        leftPanelEl.querySelector('.oe_snippet_remove').classList.add('d-none'); // TODO improve the way to do that
        leftPanelEl.querySelector('.oe_snippet_clone').classList.add('d-none'); // TODO improve the way to do that
        return this._super.apply(this, arguments);
    },
});
});
