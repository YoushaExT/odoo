odoo.define('mail.ActivityController', function (require) {
"use strict";

var BasicController = require('web.BasicController');
var core = require('web.core');
var field_registry = require('web.field_registry');
var ViewDialogs = require('web.view_dialogs');

var KanbanActivity = field_registry.get('kanban_activity');
var _t = core._t;

var ActivityController = BasicController.extend({
    custom_events: _.extend({}, BasicController.prototype.custom_events, {
        empty_cell_clicked: '_onEmptyCell',
        send_mail_template: '_onSendMailTemplate',
        schedule_activity: '_onScheduleActivity',
    }),

    //--------------------------------------------------------------------------
    // Public
    //--------------------------------------------------------------------------

    /**
     * Overridden to remove the pager as it makes no sense in this view.
     *
     * @override
     */
    renderPager: function () {
        return Promise.resolve();
    },

    //--------------------------------------------------------------------------
    // Handlers
    //--------------------------------------------------------------------------

    /**
     * @private
     */
    _onScheduleActivity: function () {
        var self = this;

        var state = this.model.get(this.handle);
        new ViewDialogs.SelectCreateDialog(this, {
            res_model: state.model,
            domain: this.model.originalDomain,
            title: _.str.sprintf(_t("Search: %s"), this.renderer.arch.attrs.string),
            disable_multiple_selection: true,
            on_selected: function (record) {
                var fakeRecord = self.renderer.getKanbanActivityData({}, record[0]);
                var widget = new KanbanActivity(self, 'activity_ids', fakeRecord, {});
                widget.scheduleActivity();
            },
        }).open();
    },
    /**
     * @private
     * @param {OdooEvent} ev
     */
    _onEmptyCell: function (ev) {
        var state = this.model.get(this.handle);
        this.do_action({
            type: 'ir.actions.act_window',
            res_model: 'mail.activity',
            view_mode: 'form',
            view_type: 'form',
            views: [[false, 'form']],
            target: 'new',
            context: {
                default_res_id: ev.data.resId,
                default_res_model: state.model,
                default_activity_type_id: ev.data.activityTypeId,
            },
            res_id: false,
        }, {
            on_close: this.reload.bind(this),
        });
    },
    /**
     * @private
     * @param {OdooEvent} ev
     */
    _onSendMailTemplate: function (ev) {
        var templateID = ev.data.templateID;
        var activityTypeID = ev.data.activityTypeID;
        var state = this.model.get(this.handle);
        var groupedActivities = state.grouped_activities;
        var resIDS = [];
        Object.keys(groupedActivities).forEach(function (resID) {
            var activityByType = groupedActivities[resID];
            var activity = activityByType[activityTypeID];
            if (activity) {
                resIDS.push(parseInt(resID));
            }
        });
        this._rpc({
            model: this.model.modelName,
            method: 'activity_send_mail',
            args: [resIDS, templateID],
        });
    },
});

return ActivityController;

});
