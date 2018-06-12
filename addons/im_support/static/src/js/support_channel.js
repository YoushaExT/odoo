odoo.define('im_support.SupportChannel', function (require) {
"use strict";

var supportSession = require('im_support.SupportSession');

var ThreadWithCache = require('mail.model.ThreadWithCache');

var core = require('web.core');
var session = require('web.session');

var _t = core._t;

/**
 * This mail model represents support channel, which are communication channels
 * between two different databases for support-related reasons. It is like
 * livechat, but both users are in different databases, and both users
 * communicate from their respective 'backend' access.
 *
 * FIXME: it should inherit from mail.model.Channel, not from
 * mail.model.ThreadWithCache
 */
var SupportChannel = ThreadWithCache.extend({
    init: function (parent, data, options) {

        data.type = 'support_channel';
        data.name = _t("Support");

        this._available = data.available;
        this._operator = data.operator;
        this._supportChannelUUID = data.id;
        this._welcomeMessage = data.welcome_message;
        if (!this._available) {
            data.name += _t(" (offline)");
        }

        this._super.apply(this, arguments);

        // force stuff that should probably be in Thread (or at least
        // ThreadWithCache), but that are currently in Channel
        this._detached = data.is_minimized;
        this._folded = data.state === 'folded';
        this._uuid = data.uuid;
    },

    //--------------------------------------------------------------------------
    // Public
    //--------------------------------------------------------------------------

    /**
     * Adds the default message in the Support channel (depending on its
     * availability).
     */
    addDefaultMessage: function () {
        if (!this._available) {
            this._addSupportNotAvailableMessage();
        } else {
            this._addSupportWelcomeMessage();
        }
    },
    /**
     * Overrides to store the state of the Support channel in the localStorage.
     *
     * @override
     */
    close: function () {
        this._super.apply(this, arguments);
        this.call('mail_service', 'updateSupportChannelState', 'closed');
    },
    /**
     * Overrides to store the state of the Support channel in the localStorage.
     *
     * @override
     */
    detach: function () {
        this._super.apply(this, arguments);
        this.call('mail_service', 'updateSupportChannelState', 'open');
    },
    /**
     * Overrides to store the state of the Support channel in the localStorage.
     *
     * @override
     */
    fold: function (folded) {
        this._super.apply(this, arguments);
        var value = folded ? 'folded' : 'open';
        this.call('mail_service', 'updateSupportChannelState', value);
    },
    /**
     * FIXME: this method is necessary just because the support channel is
     * considered as a channel, even though it does not inherit from
     * mail.model.Channel.
     *
     * @returns {boolean}
     */
    hasBeenPreviewed: function () {
        return true;
    },
    /**
     * @returns {boolean} true iff the Support channel is available
     */
    isAvailable: function () {
        return this._available;
    },
    /**
     * FIXME: this override is necessary just because the support channel is
     * considered as a channel, even though it does not inherit from
     * mail.model.Channel.
     *
     * @override
     * @returns {boolean}
     */
    isChannel: function () {
        return true;
    },
    /**
     * Support channels are not considered as chat, so they are not displayed
     * in the 'chat' filter of the systray messaging menu.
     *
     * @override
     * @returns {boolean}
     */
    isChat: function () {
        return false;
    },
    /**
     * FIXME: this override is necessary just because the support channel is
     * considered as a channel, even though it does not inherit from
     * mail.model.Channel.
     *
     * @returns {integer}
     */
    getNeedactionCounter: function () {
        return 0;
    },
    /**
     * @return {string} uuid of this channel
     */
    getUUID: function () {
        return this._uuid;
    },
    /**
     * Posts the message on the Support server.
     *
     * @override
     * @return {$.Promise}
     */
    postMessage: function (data) {
        // ensure that the poll is active before posting the message
        this.call('mail_service', 'startPollingSupport');
        return supportSession.rpc('/odoo_im_support/chat_post', {
            uuid: this._supportChannelUUID,
            message_content: data.content,
        });
    },

    //--------------------------------------------------------------------------
    // Private
    //--------------------------------------------------------------------------

    /**
     * Adds a message in the Support channel indicating that this channel is
     * not available for now.
     *
     * @private
     */
    _addSupportNotAvailableMessage: function () {
        var msg = {
            author_id: this.call('mail_service', 'getOdoobotID'),
            body: _t("None of our operators are available. <a href='https://www.odoo.com/help' " +
                "target='_blank'>Submit a ticket</a> to ask your question now."),
            channel_ids: [this.getID()],
            id: Number.MAX_SAFE_INTEGER, // last message in the channel
        };
        this.call('mail_service', 'addMessage', msg, { silent: true });
    },
    /**
     * Adds the welcome message as first message of the Support channel.
     *
     * @private
     */
    _addSupportWelcomeMessage: function () {
        if (this._welcomeMessage) {
            var msg = {
                author_id: this._operator,
                body: this._welcomeMessage,
                channel_ids: [this.getID()],
                id: -1, // first message of the channel
            };
            this.call('mail_service', 'addMessage', msg, { silent: true });
        }
    },
    /**
     * Fetches the messages from the Support server.
     *
     * @override
     * @private
     */
    _fetchMessages: function (channel, options) {
        var self = this;
        var domain = options && options.domain || [];
        var cache = this._getCache(channel, domain);
        if (options && options.loadMore) {
            var minMessageID = cache.messages[0].id;
            domain = [['id', '<', minMessageID]].concat(domain);
        }

        return supportSession.rpc('/odoo_im_support/fetch_messages', {
                domain: domain,
                channel_uuid: session.support_token,
                limit: self._FETCH_LIMIT,
            }).then(function (msgs) {
                if (!cache.all_history_loaded) {
                    cache.all_history_loaded =  msgs.length < self._FETCH_LIMIT;
                }
                cache.loaded = true;

                _.each(msgs, function (msg) {
                    _.extend(msg, {channel_ids: [self.getID()]});
                    self.call('mail_service', 'addMessage', msg, {
                        channel_id: self.getID(),
                        silent: true,
                        domain: domain,
                    });
                });
                var channelCache = self._getCache(channel, domain);
                return channelCache.messages;
            });
    },
});

return SupportChannel;

});
