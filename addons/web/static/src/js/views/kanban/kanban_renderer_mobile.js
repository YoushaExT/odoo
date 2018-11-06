odoo.define('web.KanbanRendererMobile', function (require) {
"use strict";

/**
 * The purpose of this file is to improve the UX of grouped kanban views in
 * mobile. It includes the KanbanRenderer (in mobile only) to only display one
 * column full width, and enables the swipe to browse to the other columns.
 * Moreover, records in columns are lazy-loaded.
 */

var config = require('web.config');
var core = require('web.core');
var KanbanRenderer = require('web.KanbanRenderer');

var _t = core._t;
var qweb = core.qweb;

if (!config.device.isMobile) {
    return;
}

KanbanRenderer.include({
    events: _.extend({}, KanbanRenderer.prototype.events, {
        'click .o_kanban_mobile_tab': '_onMobileTabClicked',
    }),
    ANIMATE: true, // allows to disable animations for the tests
    /**
     * @override
     */
    init: function () {
        this._super.apply(this, arguments);
        this.activeColumnIndex = 0; // index of the currently displayed column
        this._scrollPosition = null;
    },
    /**
     * As this renderer defines its own scrolling area (the column in grouped
     * mode), we override this hook to restore the scroll position like it was
     * when the renderer has been last detached.
     *
     * @override
     */
    on_attach_callback: function () {
        if (this._scrollPosition && this.state.groupedBy.length && this.widgets.length) {
            var $column = this.widgets[this.activeColumnIndex].$el;
            $column.scrollLeft(this._scrollPosition.left);
            $column.scrollTop(this._scrollPosition.top);
        }
        this._super.apply(this, arguments);
    },
    /**
     * As this renderer defines its own scrolling area (the column in grouped
     * mode), we override this hook to store the scroll position, so that we can
     * restore it if the renderer is re-attached to the DOM later.
     *
     * @override
     */
    on_detach_callback: function () {
        if (this.state.groupedBy.length && this.widgets.length) {
            var $column = this.widgets[this.activeColumnIndex].$el;
            this._scrollPosition = {
                left: $column.scrollLeft(),
                top: $column.scrollTop(),
            };
        } else {
            this._scrollPosition = null;
        }
        this._super.apply(this, arguments);
    },

    //--------------------------------------------------------------------------
    // Public
    //--------------------------------------------------------------------------

    /**
     * Displays the quick create record in the active column
     *
     * @returns {Deferred}
     */
    addQuickCreate: function () {
        return this.widgets[this.activeColumnIndex].addQuickCreate();
    },
    /**
     * Overrides to restore the left property and the scrollTop on the updated
     * column, and to enable the swipe handlers
     *
     * @override
     */
    updateColumn: function (localID) {
        var self = this;
        var index = _.findIndex(this.widgets, {db_id: localID});
        var $column = this.widgets[index].$el;
        var left = $column.css('left');
        var scrollTop = $column.scrollTop();
        return this._super.apply(this, arguments).then(function () {
            $column = self.widgets[index].$el;
            $column.css({left: left});
            $column.scrollTop(scrollTop); // required when clicking on 'Load More'
            self._enableSwipe();
        });
    },

    //--------------------------------------------------------------------------
    // Private
    //--------------------------------------------------------------------------

    /**
     * Enables swipe event on the current column
     *
     * @private
     * @param {KanbanColumn} column
     */
    _enableSwipe: function () {
        var self = this;
        this.$el.swipe({
            excludedElements: ".o_kanban_mobile_tabs",
            swipeLeft: function () {
                self._moveToGroup(self.activeColumnIndex + 1, self.ANIMATE);
            },
            swipeRight: function () {
                self._moveToGroup(self.activeColumnIndex - 1, self.ANIMATE);
            }
        });
    },
    /**
     * Moves to the given kanban column
     *
     * @private
     * @param {integer} moveToIndex index of the column to move to
     * @param {boolean} [animate=false] set to true to animate
     * @returns {Deferred} resolved when the new current group has been loaded
     *   and displayed
     */
    _moveToGroup: function (moveToIndex, animate) {
        var self = this;
        if (moveToIndex < 0 || moveToIndex >= this.widgets.length) {
            return $.when();
        }
        var def = $.Deferred();
        this.activeColumnIndex = moveToIndex;
        var column = this.widgets[this.activeColumnIndex];
        this.trigger_up('kanban_load_records', {
            columnID: column.db_id,
            onSuccess: function () {
                // update the columns and tabs positions (optionally with an animation)
                var updateFunc = animate ? 'animate' : 'css';
                self.$('.o_kanban_mobile_tab, .o_kanban_group').removeClass('o_current');
                _.each(self.widgets, function (column, index) {
                    var columnID = column.id || column.db_id;
                    var $column = self.$('.o_kanban_group[data-id="' + columnID + '"]');
                    var $tab = self.$('.o_kanban_mobile_tab[data-id="' + columnID + '"]');
                    if (index === moveToIndex - 1) {
                        $column[updateFunc]({left: '-100%'});
                        $tab[updateFunc]({left: '0%'});
                    } else if (index === moveToIndex + 1) {
                        $column[updateFunc]({left: '100%'});
                        $tab[updateFunc]({left: '100%'});
                    } else if (index === moveToIndex) {
                        $column[updateFunc]({left: '0%'});
                        $tab[updateFunc]({left: '50%'});
                        $tab.add($column).addClass('o_current');
                    } else if (index < moveToIndex) {
                        $column.css({left: '-100%'});
                        $tab[updateFunc]({left: '-100%'});
                    } else if (index > moveToIndex) {
                        $column.css({left: '100%'});
                        $tab[updateFunc]({left: '200%'});
                    }
                });
                def.resolve();
            },
        });
        return def;
    },
    /**
     * @override
     * @private
     */
    _renderGrouped: function (fragment) {
        var result = this._super.apply(this, arguments);
        var data = [];
        _.each(this.state.data, function (group) {
            if (!group.value) {
                group = _.extend({}, group, {value: _t('Undefined')});
                data.unshift(group);
            }
            else {
                data.push(group);
            }
        });

        $(qweb.render('KanbanView.MobileTabs', {
            data: data,
        })).prependTo(fragment);
        return result;
    },
    /**
     * @override
     * @private
     */
    _renderView: function () {
        var self = this;
        return this._super.apply(this, arguments).then(function () {
            if (self.state.groupedBy.length) {
                return self._moveToGroup(self.activeColumnIndex);
            }
        });
    },

    //--------------------------------------------------------------------------
    // Handlers
    //--------------------------------------------------------------------------

    /**
     * @private
     * @param {MouseEvent} event
     */
    _onMobileTabClicked: function (event) {
        this._moveToGroup($(event.currentTarget).index(), true);
    },
});

});
