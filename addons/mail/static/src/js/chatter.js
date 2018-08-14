odoo.define('mail.Chatter', function (require) {
"use strict";

var Activity = require('mail.Activity');
var ChatterComposer = require('mail.composer.Chatter');
var Followers = require('mail.Followers');
var ThreadField = require('mail.ThreadField');
var mailUtils = require('mail.utils');

var concurrency = require('web.concurrency');
var config = require('web.config');
var core = require('web.core');
var Widget = require('web.Widget');

var QWeb = core.qweb;

// The purpose of this widget is to display the chatter area below the form view
//
// It instanciates the optional mail_thread, mail_activity and mail_followers widgets.
// It Ensures that those widgets are appended at the right place, and allows them to communicate
// with each other.
// It synchronizes the rendering of those widgets (as they may be asynchronous), to limitate
// the flickering when switching between records
var Chatter = Widget.extend({
    template: 'mail.Chatter',
    custom_events: {
        discard_record_changes: '_onDiscardRecordChanges',
        reload_mail_fields: '_onReloadMailFields',
    },
    events: {
        'click .o_chatter_button_new_message': '_onOpenComposerMessage',
        'click .o_chatter_button_log_note': '_onOpenComposerNote',
        'click .o_chatter_button_schedule_activity': '_onScheduleActivity',
    },
    supportedFieldTypes: ['one2many'],

    /**
     * @override
     * @param {widget} parent
     * @param {Object} record
     * @param {Object} mailFields
     * @param {string} [mailFields.mail_activity]
     * @param {string} [mailFields.mail_followers]
     * @param {string} [mailFields.mail_thread]
     */
    init: function (parent, record, mailFields, options) {
        this._super.apply(this, arguments);
        this._setState(record);

        this._dp = new concurrency.DropPrevious();

        // mention: get the prefetched partners and use them as mention suggestions
        // if there is a follower widget, the followers will be added to the
        // suggestions as well once fetched
        this._mentionPartnerSuggestions = this.call('mail_service', 'getMentionPartnerSuggestions');
        this._mentionSuggestions = this._mentionPartnerSuggestions;

        this.fields = {};
        if (mailFields.mail_activity) {
            this.fields.activity = new Activity(this, mailFields.mail_activity, record, options);
        }
        if (mailFields.mail_followers) {
            this.fields.followers = new Followers(this, mailFields.mail_followers, record, options);
        }
        if (mailFields.mail_thread) {
            this.fields.thread = new ThreadField(this, mailFields.mail_thread, record, options);
            var fieldsInfo = this.record.fieldsInfo[record.viewType];
            var nodeOptions = fieldsInfo[mailFields.mail_thread].options || {};
            this.hasLogButton = options.display_log_button || nodeOptions.display_log_button;
            this.postRefresh = nodeOptions.post_refresh || 'never';
        }
    },
    /**
     * @override
     */
    start: function () {
        this._$topbar = this.$('.o_chatter_topbar');

        // render and append the buttons
        this._$topbar.append(QWeb.render('mail.chatter.Buttons', {
            newMessageButton: !!this.fields.thread,
            logNoteButton: this.hasLogButton,
            scheduleActivityButton: !!this.fields.activity,
            isMobile: config.device.isMobile,
        }));

        // start and append the widgets
        var fieldDefs = _.invoke(this.fields, 'appendTo', $('<div>'));
        var def = this._dp.add($.when.apply($, fieldDefs));
        this._render(def).then(this._updateMentionSuggestions.bind(this));

        return this._super.apply(this, arguments);
    },

    //--------------------------------------------------------------------------
    // Public
    //--------------------------------------------------------------------------

    /**
     * @param {Object} record
     * @param {integer} [record.res_id=undefined]
     * @param {Object[]} [fieldNames=undefined]
     */
    update: function (record, fieldNames) {
        var self = this;

        // close the composer if we switch to another record as it is record dependent
        if (this.record.res_id !== record.res_id) {
            this._closeComposer(true);
        }

        // update the state
        this._setState(record);

        // detach the thread and activity widgets (temporarily force the height to prevent flickering)
        // keep the followers in the DOM as it has a synchronous pre-rendering
        this.$el.height(this.$el.height());
        if (this.fields.activity) {
            this.fields.activity.$el.detach();
        }
        if (this.fields.thread) {
            this.fields.thread.$el.detach();
        }

        // reset and re-append the widgets (and reset 'height: auto' rule)
        // if fieldNames is given, only reset those fields, otherwise reset all fields
        var fieldsToReset;
        if (fieldNames) {
            fieldsToReset = _.filter(this.fields, function (field) {
                return _.contains(fieldNames, field.name);
            });
        } else {
            fieldsToReset = this.fields;
        }
        var fieldDefs = _.invoke(fieldsToReset, 'reset', record);
        var def = this._dp.add($.when.apply($, fieldDefs));
        this._render(def).then(function () {
            self.$el.height('auto');
            self._updateMentionSuggestions();
        });
    },

    //--------------------------------------------------------------------------
    // Private
    //--------------------------------------------------------------------------

    /**
     * @private
     * @param {boolean} force
     */
    _closeComposer: function (force) {
        if (this._composer && (this._composer.isEmpty() || force)) {
            this.$el.removeClass('o_chatter_composer_active');
            this.$('.o_chatter_button_new_message, .o_chatter_button_log_note').removeClass('o_active');
            this._composer.do_hide();
            this._composer.clearComposer();
        }
    },
    /**
     * @private
     */
    _disableChatter: function () {
        this.$('.btn').prop('disabled', true); // disable buttons
    },
    /**
     * Discard changes on the record.
     *
     * @private
     * @returns {$.Deferred} resolved if successfully discarding changes on
     *   the record, rejected otherwise
     */
    _discardChanges: function () {
        var def = $.Deferred();
        this.trigger_up('discard_changes', {
            recordID: this.record.id,
            onSuccess: def.resolve.bind(def),
            onFailure: def.reject.bind(def),
        });
        return def;
    },
    /**
     * Discard changes on the record if the message will reload the record
     * after posting it
     *
     * @private
     * @param {Object} messageData
     * @return {$.Deferred} resolved if no reload or proceed to discard the
     *   changes on the record, rejected otherwise
     */
    _discardOnReload: function (messageData) {
        if (this._reloadAfterPost(messageData)) {
            return this._discardChanges();
        }
        return $.when();
    },
    /**
     * @private
     */
    _enableChatter: function () {
        this.$('.btn').prop('disabled', false); // enable buttons
    },
    /**
     * @private
     * @param {Object} options
     * @param {Object[]} [options.suggested_partners=[]]
     * @param {boolean} [options.isLog]
     */
    _openComposer: function (options) {
        var self = this;
        var oldComposer = this._composer;
        // create the new composer
        this._composer = new ChatterComposer(this, this.record.model, options.suggested_partners || [], {
            commandsEnabled: false,
            context: this.context,
            inputMinHeight: 50,
            isLog: options && options.isLog,
            recordName: this.recordName,
            defaultBody: oldComposer && oldComposer.$input && oldComposer.$input.val(),
            defaultMentionSelections: oldComposer && oldComposer.getMentionListenerSelections(),
        });
        this._composer.on('input_focused', this, function () {
            this._composer.mentionSetPrefetchedPartners(this._mentionSuggestions || []);
        });
        this._composer.insertAfter(this.$('.o_chatter_topbar')).then(function () {
            // destroy existing composer
            if (oldComposer) {
                oldComposer.destroy();
            }
            if (!config.device.isMobile) {
                self._composer.focus();
            }
            self._composer.on('post_message', self, function (messageData) {
                self._discardOnReload(messageData).then(function () {
                    self.fields.thread.postMessage(messageData).then(function () {
                        self._closeComposer(true);
                        if (self._reloadAfterPost(messageData)) {
                            self.trigger_up('reload');
                        }
                    });
                });
            });
            self._composer.on('need_refresh', self, self.trigger_up.bind(self, 'reload'));
            self._composer.on('close_composer', null, self._closeComposer.bind(self, true));

            self.$el.addClass('o_chatter_composer_active');
            self.$('.o_chatter_button_new_message, .o_chatter_button_log_note').removeClass('o_active');
            self.$('.o_chatter_button_new_message').toggleClass('o_active', !self._composer.options.isLog);
            self.$('.o_chatter_button_log_note').toggleClass('o_active', self._composer.options.isLog);
        });
    },
    /**
     * State if the record will be reloaded after posting a message.
     * Useful to warn the user of unsaved changes if the record is dirty.
     *
     * @private
     * @param {Object} messageData
     * @param {Array} [messageData.partner_ids] list of recipients of a message
     * @return {boolean} true if record will be reloaded after posting the
     *   message, false otherwise
     */
    _reloadAfterPost: function (messageData) {
        return this.postRefresh === 'always' ||
                (
                   this.postRefresh === 'recipients' &&
                   messageData.partner_ids &&
                   messageData.partner_ids.length
                );
    },
    /**
     * @private
     * @param {Deferred} def
     * @returns {Deferred}
     */
    _render: function (def) {
        // the rendering of the chatter is aynchronous: relational data of its fields needs to be
        // fetched (in some case, it might be synchronous as they hold an internal cache).
        // this function takes a deferred as argument, which is resolved once all fields have
        // fetched their data
        // this function appends the fields where they should be once the given deferred is resolved
        // and if it takes more than 500ms, displays a spinner to indicate that it is loading
        var self = this;

        var $spinner = $(QWeb.render('Spinner'));
        concurrency.rejectAfter(concurrency.delay(500), def).then(function () {
            $spinner.appendTo(self.$el);
        });

        return def.then(function () {
            if (self.fields.activity) {
                self.fields.activity.$el.appendTo(self.$el);
            }
            if (self.fields.followers) {
                self.fields.followers.$el.appendTo(self._$topbar);
            }
            if (self.fields.thread) {
                self.fields.thread.$el.appendTo(self.$el);
            }
        }).always(function () {
            // disable widgets in create mode, otherwise enable
            self._isCreateMode ? self._disableChatter() : self._enableChatter();
            $spinner.remove();
        });
    },
    /**
     * @private
     * @param {Object} record
     * @param {integer} [record.res_id]
     * @param {string} [record.model]
     * @param {string} record.data.display_name
     */
    _setState: function (record) {

        this._isCreateMode = !record.res_id;

        if (!this.record || this.record.res_id !== record.res_id) {
            this.context = {
                default_res_id: record.res_id || false,
                default_model: record.model || false,
            };
            // reset the suggested_partners_def to ensure a reload of the
            // suggested partners when opening the composer on another record
            this.suggested_partners_def = undefined;
        }
        this.record = record;
        this.recordName = record.data.display_name;
    },
    /**
     * @private
     */
    _updateMentionSuggestions: function () {
        if (!this.fields.followers) {
            return;
        }
        var self = this;

        this._mentionSuggestions = [];

        // add the followers to the mention suggestions
        var followerSuggestions = [];
        var followers = this.fields.followers.getFollowers();
        _.each(followers, function (follower) {
            if (follower.res_model === 'res.partner') {
                followerSuggestions.push({
                    id: follower.res_id,
                    name: follower.name,
                    email: follower.email,
                });
            }
        });
        if (followerSuggestions.length) {
            this._mentionSuggestions.push(followerSuggestions);
        }

        // add the partners (followers filtered out) to the mention suggestions
        _.each(this._mentionPartnerSuggestions, function (partners) {
            self._mentionSuggestions.push(_.filter(partners, function (partner) {
                return !_.findWhere(followerSuggestions, { id: partner.id });
            }));
        });
    },

    //--------------------------------------------------------------------------
    // Handlers
    //--------------------------------------------------------------------------

    /**
     * Discard changes on the record.
     * This is notified by the composer, when opening the full-composer.
     *
     * @private
     * @param {OdooEvent} ev
     * @param {function} ev.data.proceed callback to tell to proceed
     */
    _onDiscardRecordChanges: function (ev) {
        this._discardChanges().then(ev.data.proceed);
    },
    _onOpenComposerMessage: function () {
        var self = this;
        if (!this.suggested_partners_def) {
            this.suggested_partners_def = $.Deferred();
            var method = 'message_get_suggested_recipients';
            var args = [[this.context.default_res_id], this.context];
            this._rpc({model: this.record.model, method: method, args: args})
                .then(function (result) {
                    if (!self.suggested_partners_def) {
                        return; // widget has been reset (e.g. we just switched to another record)
                    }
                    var suggested_partners = [];
                    var thread_recipients = result[self.context.default_res_id];
                    _.each(thread_recipients, function (recipient) {
                        var parsed_email = recipient[1] && mailUtils.parseEmail(recipient[1]);
                        suggested_partners.push({
                            checked: true,
                            partner_id: recipient[0],
                            full_name: recipient[1],
                            name: parsed_email[0],
                            email_address: parsed_email[1],
                            reason: recipient[2],
                        });
                    });
                    self.suggested_partners_def.resolve(suggested_partners);
                });
        }
        this.suggested_partners_def.then(function (suggested_partners) {
            self._openComposer({ isLog: false, suggested_partners: suggested_partners });
        });
    },
    /**
     * @private
     */
    _onOpenComposerNote: function () {
        this._openComposer({ isLog: true });
    },
    /**
     * @private
     * @param {OdooEvent} event
     * @param {string} event.name
     * @param {Object} event.data
     * @param {boolean} [event.data.activity]
     * @param {boolean} [event.data.followers]
     * @param {boolean} [event.data.thread]
     */
    _onReloadMailFields: function (event) {
        var fieldNames = [];
        if (this.fields.activity && event.data.activity) {
            fieldNames.push(this.fields.activity.name);
        }
        if (this.fields.followers && event.data.followers) {
            fieldNames.push(this.fields.followers.name);
        }
        if (this.fields.thread && event.data.thread) {
            fieldNames.push(this.fields.thread.name);
        }
        this.trigger_up('reload', {
            fieldNames: fieldNames,
            keepChanges: true,
        });
    },
    /**
     * @private
     */
    _onScheduleActivity: function () {
        this.fields.activity.scheduleActivity();
    },
});

return Chatter;

});
