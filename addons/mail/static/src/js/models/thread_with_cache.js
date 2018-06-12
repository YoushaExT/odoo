odoo.define('mail.model.ThreadWithCache', function (require) {
"use strict";

var Thread = require('mail.model.Thread');

var session = require('web.session');

/**
 * This is a version of a thread that is handling a cache.
 * Basically, this cache is an object indexed by stringified indexes.
 * These indexes represent the domain of messages that match this domain.
 *
 * Any threads that are instances of this Class can be used with a search view,
 * in order to make searches on messages in a thread.
 */
var ThreadWithCache = Thread.extend({
    /**
     * @override
     * @param {integer} [data.seen_message_id=undefined]
     */
    init: function (parent, data) {
        this._super.apply(this, arguments);

        this._cache = {
            '[]': {
                allHistoryLoaded: false,
                loaded: false,
                messages: [],
            }
        };
        this._lastSeenMessageID = data.seen_message_id;
    },

    //--------------------------------------------------------------------------
    // Public
    //--------------------------------------------------------------------------

    /**
     * Add the message to this thread
     *
     * @override
     * @private
     * @param {mail.model.Message} message
     * @param {Array} domain
     */
    addMessage: function (message, domain) {
        var cache = this._getCache(domain);
        var index = _.sortedIndex(cache.messages, message, function (msg) {
            return msg.getID();
        });
        if (cache.messages[index] !== message) {
            cache.messages.splice(index, 0, message);
        }
    },
    /**
     * Get the last seen message for a given thread
     *
     * @return {integer|null} last seen message ID (if any)
     */
    getLastSeenMessageID: function () {
        return this._lastSeenMessageID || null;
    },
    /**
     * @override
     * @param {Array} [domain]
     * @param {boolean} [loadMore=false]
     */
    getMessages: function (domain, loadMore) {
        if (loadMore) {
            return this._fetchMessages(domain, true);
        }
        var cache = this._getCache(domain);
        if (cache.loaded) {
            return $.when(cache.messages);
        } else {
            return this._fetchMessages(domain);
        }
    },
    /**
     * @private
     * @return {boolean} true if there is at least a message, false otherwise
     */
    hasMessages: function () {
        return !!(_.last(this._cache['[]'].messages));
    },
    /**
     * Invalidate the caches of the thread
     */
    invalidateCaches: function () {
        this._cache = _.pick(this._cache, '[]');
    },
    /**
     * State whether all messages have been loaded or not
     *
     * @param  {Array} domain
     * @return {boolean}
     */
    isAllHistoryLoaded: function (domain) {
        return this._getCache(domain).allHistoryLoaded;
    },
    /**
     * Remove message with ID `messageID` from this thread
     *
     * This is equivalent to removing this message from all the caches
     *
     * @param {integer} messageID
     */
    removeMessage: function (messageID) {
        _.each(this._cache, function (cache) {
            cache.messages = _.reject(cache.messages, function (message) {
                return message.getID() === messageID;
            });
        });
    },
    /**
     * Set 'messageID' as the ID of the last message seen in this thread
     *
     * @param {integer} messageID
     */
    setLastSeenMessageID: function (messageID) {
        this._lastSeenMessageID = messageID;
    },

    //--------------------------------------------------------------------------
    // Private
    //--------------------------------------------------------------------------

    /**
     * Gets messages from thread
     *
     * @override
     * @private
     * @param  {Array} [pDomain] filter on the messages of the channel
     * @param  {boolean} [loadMore] Whether it should load more message
     * @return {$.Promise<mail.model.Message[]>} resolved with list of messages
     */
    _fetchMessages: function (pDomain, loadMore) {
        var self = this;

        var domain = this._getThreadDomain();

        var cache = this._getCache(pDomain);
        if (pDomain) {
            domain = domain.concat(pDomain || []);
        }
        if (loadMore) {
            var minMessageID = cache.messages[0].getID();
            domain = [['id', '<', minMessageID]].concat(domain);
        }
        return this._rpc({
            model: 'mail.message',
            method: 'message_fetch',
            args: [domain],
            kwargs: {
                limit: this._FETCH_LIMIT,
                context: session.user_context
            },
        }).then(function (messages) {
            if (!cache.allHistoryLoaded) {
                cache.allHistoryLoaded = messages.length < self._FETCH_LIMIT;
            }
            cache.loaded = true;
            _.each(messages, function (message) {
                self.call('mail_service', 'addMessage', message, {
                    silent: true,
                    domain: pDomain,
                });
            });
            cache = self._getCache(pDomain || []);
            return cache.messages;
        });
    },
    /**
     * Get thread content from the cache
     * Useful to get cached messages.
     *
     * @private
     * @param  {Array} domain
     * @return {Object|undefined}
     */
    _getCache: function (domain) {
        var stringifiedDomain = JSON.stringify(domain || []);
        if (!this._cache[stringifiedDomain]) {
            this._cache[stringifiedDomain] = {
                allHistoryLoaded: false,
                loaded: false,
                messages: [],
            };
        }
        return this._cache[stringifiedDomain];
    },
    /**
     * Get the domain to fetch all the messages in the current thread
     *
     * @abstract
     * @private
     * @returns {Array}
     */
    _getThreadDomain: function () {},
});

return ThreadWithCache;

});
