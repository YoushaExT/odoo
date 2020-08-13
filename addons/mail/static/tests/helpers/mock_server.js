odoo.define('mail.MockServer', function (require) {
"use strict";

const MockServer = require('web.MockServer');

MockServer.include({
    /**
     * Param 'data' may have keys for the different magic partners/users.
     *
     * Note: we must delete these keys, so that this is not
     * handled as a model definition.
     *
     * @override
     * @param {Object} [data.currentPartnerId]
     * @param {Object} [data.currentUserId]
     * @param {Object} [data.partnerRootId]
     * @param {Object} [data.publicPartnerId]
     * @param {Widget} [options.widget] mocked widget (use to call services)
     */
    init(data, options) {
        if (data && data.currentPartnerId) {
            this.currentPartnerId = data.currentPartnerId;
            delete data.currentPartnerId;
        }
        if (data && data.currentUserId) {
            this.currentUserId = data.currentUserId;
            delete data.currentUserId;
        }
        if (data && data.partnerRootId) {
            this.partnerRootId = data.partnerRootId;
            delete data.partnerRootId;
        }
        if (data && data.publicPartnerId) {
            this.publicPartnerId = data.publicPartnerId;
            delete data.publicPartnerId;
        }
        this._widget = options.widget;

        this._super(...arguments);
    },

    //--------------------------------------------------------------------------
    // Private
    //--------------------------------------------------------------------------

    /**
     * @override
     */
    async _performFetch(resource, init) {
        if (resource === '/web/binary/upload_attachment') {
            const formData = init.body;
            const model = formData.get('model');
            const id = parseInt(formData.get('id'));
            const ufiles = formData.getAll('ufile');
            const callback = formData.get('callback');

            const attachmentIds = [];
            for (const ufile of ufiles) {
                const attachmentId = this._mockCreate('ir.attachment', {
                    // datas,
                    mimetype: ufile.type,
                    name: ufile.name,
                    res_id: id,
                    res_model: model,
                });
                attachmentIds.push(attachmentId);
            }
            const attachments = this._getRecords('ir.attachment', [['id', 'in', attachmentIds]]);
            const formattedAttachments = attachments.map(attachment => {
                return {
                    'filename': attachment.name,
                    'id': attachment.id,
                    'mimetype': attachment.mimetype,
                    'size': attachment.file_size
                };
            });
            return {
                text() {
                    return `
                        <script language="javascript" type="text/javascript">
                            var win = window.top.window;
                            win.jQuery(win).trigger('${callback}', ${JSON.stringify(formattedAttachments)});
                        </script>
                    `;
                },
            };
        }
        return this._super(...arguments);
    },
    /**
     * @override
     */
    async _performRpc(route, args) {
        // routes
        if (route === '/mail/init_messaging') {
            return this._mockRouteMailInitMessaging();
        }
        if (route === '/mail/read_followers') {
            const follower_ids = args.follower_ids;
            return this._mockRouteMailReadFollowers(follower_ids);
        }
        if (route === '/mail/read_subscription_data') {
            const follower_id = args.follower_id;
            return this._mockRouteMailReadSubscriptionData(follower_id);
        }
        // mail.activity methods
        if (args.model === 'mail.activity' && args.method === 'activity_format') {
            let res = this._mockRead(args.model, args.args, args.kwargs);
            res = res.map(function (record) {
                if (record.mail_template_ids) {
                    record.mail_template_ids = record.mail_template_ids.map(function (template_id) {
                        return { id: template_id, name: "template" + template_id };
                    });
                }
                return record;
            });
            return res;
        }
        if (args.model === 'mail.activity' && args.method === 'get_activity_data') {
            const res_model = args.args[0] || args.kwargs.res_model;
            const domain = args.args[1] || args.kwargs.domain;
            return this._mockMailActivityGetActivityData(res_model, domain);
        }
        // mail.channel methods
        if (args.model === 'mail.channel' && args.method === 'channel_fetched') {
            const ids = args.args[0];
            return this._mockMailChannelChannelFetched(ids);
        }
        if (args.model === 'mail.channel' && args.method === 'channel_fetch_listeners') {
            return [];
        }
        if (args.model === 'mail.channel' && args.method === 'channel_fetch_preview') {
            const ids = args.args[0];
            return this._mockMailChannelChannelFetchPreview(ids);
        }
        if (args.model === 'mail.channel' && args.method === 'channel_fold') {
            const uuid = args.args[0] || args.kwargs.uuid;
            const state = args.args[1] || args.kwargs.state;
            return this._mockMailChannelChannelFold(uuid, state);
        }
        if (args.model === 'mail.channel' && args.method === 'channel_get') {
            const partners_to = args.args[0] || args.kwargs.partners_to;
            const pin = args.args[1] !== undefined
                ? args.args[1]
                : args.kwargs.pin !== undefined
                    ? args.kwargs.pin
                    : undefined;
            return this._mockMailChannelChannelGet(partners_to, pin);
        }
        if (args.model === 'mail.channel' && args.method === 'channel_minimize') {
            return;
        }
        if (args.model === 'mail.channel' && args.method === 'channel_seen') {
            return;
        }
        if (args.model === 'mail.channel' && args.method === 'channel_set_custom_name') {
            const channel_id = args.args[0] || args.kwargs.channel_id;
            const name = args.args[1] || args.kwargs.name;
            return this._mockMailChannelChannelSetCustomName(channel_id, name);
        }
        if (args.model === 'mail.channel' && args.method === 'execute_command') {
            return this._mockMailChannelExecuteCommand(args);
        }
        if (args.model === 'mail.channel' && args.method === 'message_post') {
            const id = args.args[0];
            const kwargs = args.kwargs;
            return this._mockMailChannelMessagePost(id, kwargs);
        }
        if (args.model === 'mail.channel' && args.method === 'notify_typing') {
            return;
        }
        // mail.message methods
        if (args.model === 'mail.message' && args.method === 'mark_all_as_read') {
            const domain = args.args[0] || args.kwargs.domain;
            return this._mockMailMessageMarkAllAsRead(domain);
        }
        if (args.model === 'mail.message' && args.method === 'message_fetch') {
            const domain = args.args[0] || args.kwargs.domain;
            const limit = args.args[1] || args.kwargs.limit;
            const moderated_channel_ids = args.args[2] || args.kwargs.moderated_channel_ids;
            return this._mockMailMessageMessageFetch(domain, limit, moderated_channel_ids);
        }
        if (args.model === 'mail.message' && args.method === 'message_format') {
            const ids = args.args[0];
            return this._mockMailMessageMessageFormat(ids);
        }
        if (args.model === 'mail.message' && args.method === 'moderate') {
            return this._mockMailMessageModerate(args);
        }
        if (args.model === 'mail.message' && args.method === 'set_message_done') {
            return this._mockMailMessageSetMessageDone(args);
        }
        if (args.model === 'mail.message' && args.method === 'toggle_message_starred') {
            const ids = args.args[0];
            return this._mockMailMessageToggleMessageStarred(ids);
        }
        if (args.model === 'mail.message' && args.method === 'unstar_all') {
            return this._mockMailMessageUnstarAll();
        }
        // res.partner methods
        if (args.model === 'res.partner' && args.method === 'get_mention_suggestions') {
            return this._mockResPartnerGetMentionSuggestions(args);
        }
        if (args.model === 'res.partner' && args.method === 'im_search') {
            const name = args.args[0] || args.kwargs.search;
            const limit = args.args[1] || args.kwargs.limit;
            return this._mockResPartnerImSearch(name, limit);
        }
        // mail.thread methods (can work on any model)
        if (args.method === 'message_subscribe') {
            const ids = args.args[0];
            const partner_ids = args.args[1] || args.kwargs.partner_ids;
            const channel_ids = args.args[2] || args.kwargs.channel_ids;
            const subtype_ids = args.args[3] || args.kwargs.subtype_ids;
            return this._mockMailThreadMessageSubscribe(args.model, ids, partner_ids, channel_ids, subtype_ids);
        }
        if (args.method === 'message_unsubscribe') {
            const ids = args.args[0];
            const partner_ids = args.args[1] || args.kwargs.partner_ids;
            const channel_ids = args.args[2] || args.kwargs.channel_ids;
            return this._mockMailThreadMessageUnsubscribe(args.model, ids, partner_ids, channel_ids);
        }
        if (args.method === 'message_post') {
            const id = args.args[0];
            const kwargs = args.kwargs;
            return this._mockMailThreadMessagePost(id, args.model, kwargs);
        }
        return this._super(route, args);
    },

    //--------------------------------------------------------------------------
    // Private Mocked Routes
    //--------------------------------------------------------------------------

    /**
     * Simulates the `/mail/init_messaging` route.
     *
     * @private
     * @return {Object}
     */
    _mockRouteMailInitMessaging() {
        const channels = this._getRecords('mail.channel', [
            ['channel_type', '=', 'channel'],
            ['members', 'in', this.currentPartnerId],
            ['public', 'in', ['public', 'groups']],
        ]);
        const channelInfos = this._mockMailChannelChannelInfo(channels.map(channel => channel.id));

        const directMessages = this._getRecords('mail.channel', [
            ['channel_type', '=', 'chat'],
            ['is_pinned', '=', true],
            ['members', 'in', this.currentPartnerId],
        ]);
        const directMessageInfos = this._mockMailChannelChannelInfo(directMessages.map(channel => channel.id));

        const privateGroups = this._getRecords('mail.channel', [
            ['channel_type', '=', 'channel'],
            ['members', 'in', this.currentPartnerId],
            ['public', '=', 'private'],
        ]);
        const privateGroupInfos = this._mockMailChannelChannelInfo(privateGroups.map(channel => channel.id));

        const moderation_channel_ids = this._getRecords('mail.channel', [['is_moderator', '=', true]]).map(channel => channel.id);
        const moderation_counter = this._getRecords('mail.message', [
            ['model', '=', 'mail.channel'],
            ['res_id', 'in', moderation_channel_ids],
            ['moderation_status', '=', 'pending_moderation'],
        ]).length;

        const partnerRoot = this._getRecords(
            'res.partner',
            [['id', '=', this.partnerRootId]],
            { active_test: false }
        )[0];
        const partnerRootFormat = this._mockResPartnerMailPartnerFormat(partnerRoot.id);

        const publicPartner = this._getRecords(
            'res.partner',
            [['id', '=', this.publicPartnerId]],
            { active_test: false }
        )[0];
        const publicPartnerFormat = this._mockResPartnerMailPartnerFormat(publicPartner.id);

        const currentPartner = this._getRecords('res.partner', [['id', '=', this.currentPartnerId]])[0];
        const currentPartnerFormat = this._mockResPartnerMailPartnerFormat(currentPartner.id);

        const needaction_inbox_counter = this._getRecords('mail.notification', [
            ['res_partner_id', '=', this.currentPartnerId],
            ['is_read', '=', false],
        ]).length;

        const mailFailures = this._mockMailMessageMessageFetchFailed();

        const starredCounter = this._getRecords('mail.message', [
            ['starred_partner_ids', 'in', this.currentPartnerId],
        ]).length;

        return {
            channel_slots: {
                channel_channel: channelInfos,
                channel_direct_message: directMessageInfos,
                channel_private_group: privateGroupInfos,
            },
            commands: [],
            current_partner: currentPartnerFormat,
            curret_user_id: this.currentUserId,
            mail_failures: mailFailures,
            mention_partner_suggestions: [],
            menu_id: false,
            moderation_channel_ids,
            moderation_counter,
            needaction_inbox_counter,
            partner_root: partnerRootFormat,
            public_partner: publicPartnerFormat,
            shortcodes: [],
            starred_counter: starredCounter,
        };
    },
    /**
     * Simulates the `/mail/read_followers` route.
     *
     * @private
     * @param {integer[]} follower_ids
     * @return {Object} one key for list of followers and one for subtypes
     */
    async _mockRouteMailReadFollowers(follower_ids) {
        const ids = follower_ids; // list of followers IDs to read
        const followers = this._getRecords('mail.followers', [['id', 'in', ids]]);
        const currentPartnerFollower = followers.find(follower => follower.id === this.currentPartnerId);
        const subtypes = currentPartnerFollower
            ? this._mockRouteMailReadSubscriptionData(currentPartnerFollower.id)
            : false;
        return { followers, subtypes };
    },
    /**
     * Simulates the `/mail/read_subscription_data` route.
     *
     * @private
     * @param {integer} follower_id
     * @return {Object[]} list of followed subtypes
     */
    async _mockRouteMailReadSubscriptionData(follower_id) {
        const follower = this._getRecords('mail.followers', [['id', '=', follower_id]])[0];
        const subtypes = this._getRecords('mail.message.subtype', [
            '&',
            ['hidden', '=', false],
            '|',
            ['res_model', '=', follower.res_model],
            ['res_model', '=', false],
        ]);
        const subtypes_list = subtypes.map(subtype => {
            const parent = this._getRecords('mail.message.subtype', [
                ['id', '=', subtype.parent_id],
            ])[0];
            return {
                'default': subtype.default,
                'followed': follower.subtype_ids.includes(subtype.id),
                'id': subtype.id,
                'internal': subtype.internal,
                'name': subtype.name,
                'parent_model': parent ? parent.res_model : false,
                'res_model': subtype.res_model,
                'sequence': subtype.sequence,
            };
        });
        // NOTE: server is also doing a sort here, not reproduced for simplicity
        return subtypes_list;
    },

    //--------------------------------------------------------------------------
    // Private Mocked Methods
    //--------------------------------------------------------------------------

    /**
     * Simulates `get_activity_data` on `mail.activity`.
     *
     * @private
     * @param {string} res_model
     * @param {string} domain
     * @return {Object}
     */
    _mockMailActivityGetActivityData(res_model, domain) {
        const self = this;
        const records = this._getRecords(res_model, domain);

        const activityTypes = this._getRecords('mail.activity.type', []);
        const activityIds = _.pluck(records, 'activity_ids').flat();

        const groupedActivities = {};
        const resIdToDeadline = {};
        const groups = self._mockReadGroup('mail.activity', {
            domain: [['id', 'in', activityIds]],
            fields: ['res_id', 'activity_type_id', 'ids:array_agg(id)', 'date_deadline:min(date_deadline)'],
            groupby: ['res_id', 'activity_type_id'],
            lazy: false,
        });
        groups.forEach(function (group) {
            // mockReadGroup doesn't correctly return all asked fields
            const activites = self._getRecords('mail.activity', group.__domain);
            group.activity_type_id = group.activity_type_id[0];
            let minDate;
            activites.forEach(function (activity) {
                if (!minDate || moment(activity.date_deadline) < moment(minDate)) {
                    minDate = activity.date_deadline;
                }
            });
            group.date_deadline = minDate;
            resIdToDeadline[group.res_id] = minDate;
            let state;
            if (group.date_deadline === moment().format("YYYY-MM-DD")) {
                state = 'today';
            } else if (moment(group.date_deadline) > moment()) {
                state = 'planned';
            } else {
                state = 'overdue';
            }
            if (!groupedActivities[group.res_id]) {
                groupedActivities[group.res_id] = {};
            }
            groupedActivities[group.res_id][group.activity_type_id] = {
                count: group.__count,
                state: state,
                o_closest_deadline: group.date_deadline,
                ids: _.pluck(activites, 'id'),
            };
        });

        return {
            activity_types: activityTypes.map(function (type) {
                let mailTemplates = [];
                if (type.mail_template_ids) {
                    mailTemplates = type.mail_template_ids.map(function (id) {
                        const template = _.findWhere(self.data['mail.template'].records, { id: id });
                        return {
                            id: id,
                            name: template.name,
                        };
                    });
                }
                return [type.id, type.display_name, mailTemplates];
            }),
            activity_res_ids: _.sortBy(_.pluck(records, 'id'), function (id) {
                return moment(resIdToDeadline[id]);
            }),
            grouped_activities: groupedActivities,
        };
    },
    /**
     * Simulates `channel_fetched` on `mail.channel`.
     *
     * @private
     * @param {integer[]} ids
     */
    _mockMailChannelChannelFetched(ids) {
        const channels = this._getRecords('mail.channel', [['id', 'in', ids]]);
        for (const channel of channels) {
            const channelMessages = this._getRecords('mail.message', [['channel_ids', 'in', channel.id]]);
            const lastMessage = channelMessages.reduce((lastMessage, message) => {
                if (message.id > lastMessage.id) {
                    return message;
                }
                return lastMessage;
            }, channelMessages[0]);
            if (!lastMessage) {
                continue;
            }
            this._mockWrite('mail.channel', [
                [channel.id],
                { fetched_message_id: lastMessage.id },
            ]);
            const notification = [
                ["dbName", 'mail.channel', channel.id],
                {
                    id: `${channel.id}/${this.currentPartnerId}`, // simulate channel.partner id
                    info: 'channel_fetched',
                    last_message_id: lastMessage.id,
                    partner_id: this.currentPartnerId,
                },
            ];
            this._widget.call('bus_service', 'trigger', 'notification', [notification]);
        }
    },
    /**
     * Simulates `channel_fetch_preview` on `mail.channel`.
     *
     * @private
     * @param {integer[]} ids
     * @return {Object[]} list of channels previews
     */
    _mockMailChannelChannelFetchPreview(ids) {
        const channels = this._getRecords('mail.channel', [['id', 'in', ids]]);
        return channels.map(channel => {
            const channelMessages = this._getRecords('mail.message', [['channel_ids', 'in', channel.id]]);
            const lastMessage = channelMessages.reduce((lastMessage, message) => {
                if (message.id > lastMessage.id) {
                    return message;
                }
                return lastMessage;
            }, channelMessages[0]);
            return {
                id: channel.id,
                last_message: lastMessage ? this._mockMailMessageMessageFormat([lastMessage.id])[0] : false,
            };
        });
    },
    /**
     * Simulates the 'channel_fold' route on `mail.channel`.
     * In particular sends a notification on the bus.
     *
     * @private
     * @param {string} uuid
     * @param {state} [state]
     */
    _mockMailChannelChannelFold(uuid, state) {
        const channel = this._getRecords('mail.channel', [['uuid', '=', uuid]])[0];
        this._mockWrite('mail.channel', [channel.id], {
            is_minimized: state !== 'closed',
            state,
        });
        const notifConfirmFold = [
            ["dbName", 'res.partner', this.currentPartnerId],
            this._mockMailChannelChannelInfo([channel.id])[0]
        ];
        this._widget.call('bus_service', 'trigger', 'notification', [notifConfirmFold]);
    },
    /**
     * Simulates 'channel_get' on 'mail.channel'.
     *
     * @private
     * @param {integer[]} [partners_to=[]]
     * @param {boolean} [pin=true]
     * @returns {Object}
     */
    _mockMailChannelChannelGet(partners_to = [], pin = true) {
        if (partners_to.length === 0) {
            return false;
        }
        if (!partners_to.includes(this.currentPartnerId)) {
            partners_to.push(this.currentPartnerId);
        }
        const partners = this._getRecords('res.partner', [['id', 'in', partners_to]]);

        // NOTE: this mock is not complete, which is done for simplicity.
        // Indeed if a chat already exists for the given partners, the server
        // is supposed to return this existing chat. But the mock is currently
        // always creating a new chat, because no test is relying on receiving
        // an existing chat.

        const id = this._mockCreate('mail.channel', {
            channel_type: 'chat',
            mass_mailing: false,
            is_minimized: true,
            is_pinned: true,
            members: [[6, 0, partners_to]],
            name: partners.map(partner => partner.name).join(", "),
            public: 'private',
            state: 'open',
        });
        return this._mockMailChannelChannelInfo([id])[0];
    },
    /**
     * Simulates `channel_info` on `mail.channel`.
     *
     * @private
     * @param {integer[]} [ids=[]]
     * @returns {Object[]}
     */
    _mockMailChannelChannelInfo(ids = []) {
        const channels = this._getRecords('mail.channel', [['id', 'in', ids]]);
        const all_partners = [...new Set(channels.reduce((all_partners, channel) => {
            return [...all_partners, ...channel.members];
        }, []))];
        const direct_partners = [...new Set(channels.reduce((all_partners, channel) => {
            if (channel.channel_type === 'chat') {
                return [...all_partners, ...channel.members];
            }
            return all_partners;
        }, []))];
        const partnerInfos = this._mockMailChannelPartnerInfo(all_partners, direct_partners);
        return channels.map(channel => {
            const members = channel.members.map(partnerId => partnerInfos[partnerId]);
            const messages = this._getRecords('mail.message', [
                ['res_id', '=', channel.id],
                ['model', '=', 'mail.channel'],
                ['message_type', '!=', 'user_notification'],
            ]);
            const messageNeedactionCounter = this._getRecords('mail.notification', [
                ['res_partner_id', '=', this.currentPartnerId],
                ['is_read', '=', false],
                ['mail_message_id', 'in', messages.map(message => message.id)],
            ]).length;
            return Object.assign({}, channel, {
                members,
                message_needaction_counter: messageNeedactionCounter,
            });
        });
    },
    /**
     * Simulates `channel_set_custom_name` on `mail.channel`.
     *
     * @private
     * @param {integer} channel_id
     * @return {string} [name]
     */
    _mockMailChannelChannelSetCustomName(channel_id, name) {
        this._mockWrite('mail.channel', [
            [channel_id],
            { custom_channel_name: name },
        ]);
    },
    /**
     * Simulates `execute_command` on `mail.channel`.
     * In particular sends a notification on the bus.
     *
     * @private
     */
    _mockMailChannelExecuteCommand(args) {
        const [ids, commandName] = args.args;
        const channels = this._getRecords('mail.channel', [['id', 'in', ids]]);
        if (commandName === 'leave') {
            for (const channel of channels) {
                this._mockWrite('mail.channel', [channel.id], {
                    is_pinned: false,
                });
                const notifConfirmUnpin = [
                    ["dbName", 'res.partner', this.currentPartnerId],
                    Object.assign({}, channel, { info: 'unsubscribe' })
                ];
                this._widget.call('bus_service', 'trigger', 'notification', [notifConfirmUnpin]);
            }
            return;
        }
        throw new Error(`mail/mock_server: the route execute_command doesn't implement the command "${commandName}"`);
    },
    /**
     * Simulates `message_post` on `mail.channel`.
     *
     * For simplicity this mock handles a simple case in regard to moderation:
     * - messages from JS are assumed to be always sent by the current partner,
     * - moderation white list and black list are not checked.
     *
     * @private
     * @param {integer} id
     * @param {Object} kwargs
     * @return {integer|false}
     */
    _mockMailChannelMessagePost(id, kwargs) {
        const message_type = kwargs.message_type || 'notification';
        const channel = this._getRecords('mail.channel', [['id', '=', id]])[0];
        let moderation_status = 'accepted';
        if (channel.moderation && ['email', 'comment'].includes(message_type)) {
            if (!channel.is_moderator) {
                moderation_status = 'pending_moderation';
            }
        }
        const messageId = this._mockMailThreadMessagePost(
            id,
            'mail.channel',
            Object.assign(kwargs, {
                message_type,
                moderation_status,
            })
        );
        return messageId;
    },
    /**
     * Simulates `partner_info` on `mail.channel`.
     *
     * @private
     * @param {integer[]} all_partners
     * @param {integer[]} direct_partners
     * @returns {Object[]}
     */
    _mockMailChannelPartnerInfo(all_partners, direct_partners) {
        const partners = this._getRecords('res.partner', [['id', 'in', all_partners]]);
        const partnerInfos = {};
        for (const partner of partners) {
            const partnerInfo = {
                email: partner.email,
                id: partner.id,
                name: partner.name,
            };
            if (direct_partners.includes(partner.id)) {
                partnerInfo.im_status = partner.im_status;
            }
            partnerInfos[partner.id] = partnerInfo;
        }
        return partnerInfos;
    },
    /**
     * Simulates `mark_all_as_read` on `mail.message`.
     *
     * @private
     * @param {Array[]} [domain]
     * @return {integer[]}
     */
    _mockMailMessageMarkAllAsRead(domain) {
        const notifDomain = [
            ['res_partner_id', '=', this.currentPartnerId],
            ['is_read', '=', false],
        ];
        if (domain) {
            const messages = this._getRecords('mail.message', domain);
            notifDomain.push(
                ['mail_message_id', 'in', messages.map(messages => messages.id)]
            );
        }
        const notifications = this._getRecords('mail.notification', notifDomain);
        this._mockWrite('mail.notification', [
            notifications.map(notification => notification.id),
            { is_read: true },
        ]);
        const messageIds = [];
        for (const notification of notifications) {
            if (!messageIds.includes(notification.mail_message_id)) {
                messageIds.push(notification.mail_message_id);
            }
        }
        const messages = this._getRecords('mail.message', [['id', 'in', messageIds]]);
        // simulate compute that should be done based on notifications
        for (const message of messages) {
            this._mockWrite('mail.message', [
                [message.id],
                {
                    needaction: false,
                    needaction_partner_ids: message.needaction_partner_ids.filter(
                        partnerId => partnerId !== this.currentPartnerId
                    ),
                },
            ]);
        }
        const notificationData = { type: 'mark_as_read', message_ids: messageIds };
        const notification = [[false, 'res.partner', this.currentPartnerId], notificationData];
        this._widget.call('bus_service', 'trigger', 'notification', [notification]);
        return messageIds;
    },
    /**
     * Simulates `message_fetch` on `mail.message`.
     *
     * @private
     * @param {Array[]} domain
     * @param {string} [limit=20]
     * @param {Object} [moderated_channel_ids]
     * @return {Object[]}
     */
    _mockMailMessageMessageFetch(domain, limit = 20, moderated_channel_ids) {
        let messages = this._getRecords('mail.message', domain);
        if (moderated_channel_ids) {
            const mod_messages = this._getRecords('mail.message', [
                ['model', '=', 'mail.channel'],
                ['res_id', 'in', moderated_channel_ids],
                '|',
                ['author_id', '=', this.currentPartnerId],
                ['moderation_status', '=', 'pending_moderation'],
            ]);
            messages = [...new Set([...messages, ...mod_messages])];
        }
        // sorted from highest ID to lowest ID (i.e. from youngest to oldest)
        messages.sort(function (m1, m2) {
            return m1.id < m2.id ? 1 : -1;
        });
        // pick at most 'limit' messages
        messages.length = Math.min(messages.length, limit);
        return this._mockMailMessageMessageFormat(messages.map(message => message.id));
    },
    /**
     * Simulates `message_fetch_failed` on `mail.message`.
     *
     * @private
     * @return {Object[]}
     */
    _mockMailMessageMessageFetchFailed() {
        const messages = this._getRecords('mail.message', [
            ['author_id', '=', this.currentPartnerId],
            ['res_id', '!=', 0],
            ['model', '!=', false],
            ['message_type', '!=', 'user_notification'],
        ]).filter(message => {
            // Purpose is to simulate the following domain on mail.message:
            // ['notification_ids.notification_status', 'in', ['bounce', 'exception']],
            // But it's not supported by _getRecords domain to follow a relation.
            const notifications = this._getRecords('mail.notification', [
                ['mail_message_id', '=', message.id],
                ['notification_status', 'in', ['bounce', 'exception']],
            ]);
            return notifications.length > 0;
        });
        return this._mockMailMessage_MessageNotificationFormat(messages.map(message => message.id));
    },
    /**
     * Simulates `message_format` on `mail.message`.
     *
     * @private
     * @return {integer[]} ids
     * @return {Object[]}
     */
    _mockMailMessageMessageFormat(ids) {
        const messages = this._getRecords('mail.message', [['id', 'in', ids]]);
        // sorted from highest ID to lowest ID (i.e. from most to least recent)
        messages.sort(function (m1, m2) {
            return m1.id < m2.id ? 1 : -1;
        });
        return messages.map(message => {
            const thread = message.model && this._getRecords(message.model, [
                ['id', '=', message.res_id],
            ])[0];
            let formattedAuthor;
            if (message.author_id) {
                const author = this._getRecords('res.partner', [['id', '=', message.author_id]])[0];
                formattedAuthor = [author.id, author.display_name];
            } else {
                formattedAuthor = [0, message.email_from];
            }
            const attachments = this._getRecords('ir.attachment', [
                ['id', 'in', message.attachment_ids],
            ]);
            const formattedAttachments = attachments.map(attachment => {
                return Object.assign({
                    'checksum': attachment.checksum,
                    'id': attachment.id,
                    'filename': attachment.name,
                    'name': attachment.name,
                    'mimetype': attachment.mimetype,
                    'is_main': thread && thread.message_main_attachment_id === attachment.id,
                    'res_id': attachment.res_id,
                    'res_model': attachment.res_model,
                });
            });
            const notifications = this._getRecords('mail.notification', [
                ['mail_message_id', '=', message.id],
            ]);
            const historyPartnerIds = notifications
                .filter(notification => notification.is_read)
                .map(notification => notification.res_partner_id);
            const needactionPartnerIds = notifications
                .filter(notification => !notification.is_read)
                .map(notification => notification.res_partner_id);
            return Object.assign({}, message, {
                attachment_ids: formattedAttachments,
                author_id: formattedAuthor,
                history_partner_ids: historyPartnerIds,
                needaction_partner_ids: needactionPartnerIds,
            });
        });
    },
    /**
     * Simulates `moderate` on `mail.message`.
     *
     * @private
     */
    _mockMailMessageModerate(args) {
        const messageIDs = args.args[0];
        const decision = args.args[1];
        const model = this.data['mail.message'];
        if (decision === 'reject' || decision === 'discard') {
            model.records = _.reject(model.records, function (rec) {
                return _.contains(messageIDs, rec.id);
            });
            // simulate notification back (deletion of rejected/discarded
            // message in channel)
            const dbName = undefined; // useless for tests
            const notifData = {
                message_ids: messageIDs,
                type: "deletion",
            };
            const metaData = [dbName, 'res.partner'];
            const notification = [metaData, notifData];
            this._widget.call('bus_service', 'trigger', 'notification', [notification]);
        } else if (decision === 'accept') {
            // simulate notification back (new accepted message in channel)
            const messages = _.filter(model.records, function (rec) {
                return _.contains(messageIDs, rec.id);
            });

            const notifications = [];
            _.each(messages, function (message) {
                const dbName = undefined; // useless for tests
                const messageData = message;
                message.moderation_status = 'accepted';
                const metaData = [dbName, 'mail.channel', message.res_id];
                const notification = [metaData, messageData];
                notifications.push(notification);
            });
            this._widget.call('bus_service', 'trigger', 'notification', notifications);
        }
    },
    /**
     * Simulates `_message_notification_format` on `mail.message`.
     *
     * @private
     * @return {integer[]} ids
     * @return {Object[]}
     */
    _mockMailMessage_MessageNotificationFormat(ids) {
        const messages = this._getRecords('mail.message', [['id', 'in', ids]]);
        return messages.map(message => {
            let notifications = this._getRecords('mail.notification', [
                ['mail_message_id', '=', message.id],
            ]);
            notifications = this._mockMailNotification_FilteredForWebClient(
                notifications.map(notification => notification.id)
            );
            notifications = this._mockMailNotification_NotificationFormat(
                notifications.map(notification => notification.id)
            );
            return {
                'date': message.date,
                'id': message.id,
                'message_type': message.message_type,
                'model': message.model,
                'notifications': notifications,
                'res_id': message.res_id,
                'res_model_name': message.res_model_name,
            };
        });
    },
    /**
     * Simulates `set_message_done` on `mail.message`, which turns provided
     * needaction message to non-needaction (i.e. they are marked as read from
     * from the Inbox mailbox). Also notify on the longpoll bus that the
     * messages have been marked as read, so that UI is updated.
     *
     * @private
     * @param {Object} args
     */
    _mockMailMessageSetMessageDone(args) {
        const ids = args.args[0];
        const messages = this._getRecords('mail.message', [['id', 'in', ids]]);

        const notifications = this._getRecords('mail.notification', [
            ['res_partner_id', '=', this.currentPartnerId],
            ['is_read', '=', false],
            ['mail_message_id', 'in', messages.map(messages => messages.id)]
        ]);
        this._mockWrite('mail.notification', [
            notifications.map(notification => notification.id),
            { is_read: true },
        ]);
        // simulate compute that should be done based on notifications
        for (const message of messages) {
            this._mockWrite('mail.message', [
                [message.id],
                {
                    needaction: false,
                    needaction_partner_ids: message.needaction_partner_ids.filter(
                        partnerId => partnerId !== this.currentPartnerId
                    ),
                },
            ]);
        }
        // NOTE: server is also sending channel_ids, not done here for simplicity.
        const data = { type: 'mark_as_read', message_ids: ids };
        const busNotifications = [[[false, 'res.partner', this.currentPartnerId], data]];
        this._widget.call('bus_service', 'trigger', 'notification', busNotifications);
    },
    /**
     * Simulates `toggle_message_starred` on `mail.message`.
     *
     * @private
     * @return {integer[]} ids
     */
    _mockMailMessageToggleMessageStarred(ids) {
        const messages = this._getRecords('mail.message', [['id', 'in', ids]]);
        for (const message of messages) {
            const wasStared = message.starred_partner_ids.includes(this.currentPartnerId);
            this._mockWrite('mail.message', [
                [message.id],
                { starred_partner_ids: [[wasStared ? 3 : 4, this.currentPartnerId]] }
            ]);
            const notificationData = {
                message_ids: [message.id],
                starred: !wasStared,
                type: 'toggle_star',
            };
            const notifications = [[[false, 'res.partner', this.currentPartnerId], notificationData]];
            this._widget.call('bus_service', 'trigger', 'notification', notifications);
        }
    },
    /**
     * Simulates `unstar_all` on `mail.message`.
     *
     * @private
     */
    _mockMailMessageUnstarAll() {
        const messages = this._getRecords('mail.message', [
            ['starred_partner_ids', 'in', this.currentPartnerId],
        ]);
        this._mockWrite('mail.message', [
            messages.map(message => message.id),
            { starred_partner_ids: [[3, this.currentPartnerId]] }
        ]);
        const notificationData = {
            message_ids: messages.map(message => message.id),
            starred: false,
            type: 'toggle_star',
        };
        const notification = [[false, 'res.partner', this.currentPartnerId], notificationData];
        this._widget.call('bus_service', 'trigger', 'notification', [notification]);
    },
    /**
     * Simulates `_filtered_for_web_client` on `mail.notification`.
     *
     * @private
     * @return {integer[]} ids
     * @return {Object[]}
     */
    _mockMailNotification_FilteredForWebClient(ids) {
        return this._getRecords('mail.notification', [
            ['id', 'in', ids],
            ['notification_type', '!=', 'inbox'],
            ['notification_status', 'in', ['bounce', 'exception', 'canceled']],
            // or "res_partner_id.partner_share" not done here for simplicity
        ]);
    },
    /**
     * Simulates `_notification_format` on `mail.notification`.
     *
     * @private
     * @return {integer[]} ids
     * @return {Object[]}
     */
    _mockMailNotification_NotificationFormat(ids) {
        const notifications = this._getRecords('mail.notification', [['id', 'in', ids]]);
        return notifications.map(notification => {
            const partner = this._getRecords('res.partner', [['id', '=', notification.res_partner_id]])[0];
            return {
                'id': notification.id,
                'notification_type': notification.notification_type,
                'notification_status': notification.notification_status,
                'failure_type': notification.failure_type,
                'res_partner_id': [partner && partner.id, partner && partner.display_name],
            };
        });
    },
    /**
     * Simulates `message_post` on `mail.thread`.
     *
     * @private
     * @param {integer} id
     * @param {string} model
     * @param {Object} kwargs
     * @return {integer}
     */
    _mockMailThreadMessagePost(id, model, kwargs) {
        if (kwargs.attachment_ids) {
            const attachments = this._getRecords('ir.attachment', [
                ['id', 'in', kwargs.attachment_ids],
                ['res_model', '=', 'mail.compose.message'],
                ['res_id', '=', 0],
            ]);
            const attachmentIds = attachments.map(attachment => attachment.id);
            this._mockWrite('ir.attachment', [
                attachmentIds,
                {
                    res_id: id,
                    res_model: model,
                },
            ]);
            kwargs.attachment_ids = attachmentIds.map(attachmentId => [4, attachmentId]);
        }
        const subtype_xmlid = kwargs.subtype_xmlid || 'mail.mt_note';
        const values = Object.assign({}, kwargs, {
            is_discussion: subtype_xmlid === 'mail.mt_comment',
            is_note: subtype_xmlid === 'mail.mt_note',
            model,
            res_id: id,
        });
        delete values.subtype_xmlid;
        const messageId = this._mockCreate('mail.message', values);
        const message = this._getRecords('mail.message', [['id', '=', messageId]])[0];
        const notificationData = {
            type: 'author',
            message: this._mockMailMessageMessageFormat([messageId])[0],
        };
        const notification = [[false, 'res.partner', message.author_id], notificationData];
        this._widget.call('bus_service', 'trigger', 'notification', [notification]);
        return messageId;
    },
    /**
     * Simulates `message_subscribe` on `mail.thread`.
     *
     * @private
     * @param {string} model not in server method but necessary for thread mock
     * @param {integer[]} ids
     * @param {integer[]} partner_ids
     * @param {integer[]} channel_ids
     * @param {integer[]} subtype_ids
     * @returns {boolean}
     */
    _mockMailThreadMessageSubscribe(model, ids, partner_ids, channel_ids, subtype_ids) {
        // message_subscribe is too complex for a generic mock.
        // mockRPC should be considered for a specific result.
    },
    /**
     * Simulates `message_unsubscribe` on `mail.thread`.
     *
     * @private
     * @param {string} model not in server method but necessary for thread mock
     * @param {integer[]} ids
     * @param {integer[]} partner_ids
     * @param {integer[]} channel_ids
     * @returns {boolean|undefined}
     */
    _mockMailThreadMessageUnsubscribe(model, ids, partner_ids, channel_ids) {
        if (!partner_ids && !channel_ids) {
            return true;
        }
        const followers = this._getRecords('mail.followers', [
            ['res_model', '=', model],
            ['res_id', 'in', ids],
            '|',
            ['partner_id', 'in', partner_ids || []],
            ['channel_id', 'in', channel_ids || []],
        ]);
        this._mockUnlink(model, [followers.map(follower => follower.id)]);
    },
    /**
     * Simulates `get_mention_suggestions` on `res.partner`.
     *
     * @private
     * @returns {Array[]}
     */
    _mockResPartnerGetMentionSuggestions(args) {
        const search = (args.args[0] || args.kwargs.search || '').toLowerCase();
        const limit = args.args[1] || args.kwargs.limit || 8;

        /**
         * Returns the given list of partners after filtering it according to
         * the logic of the Python method `get_mention_suggestions` for the
         * given search term. The result is truncated to the given limit and
         * formatted as expected by the original method.
         *
         * @param {Object[]} partners
         * @param {string} search
         * @param {integer} limit
         * @returns {Object[]}
         */
        const mentionSuggestionsFilter = function (partners, search, limit) {
            const matchingPartners = partners
                .filter(partner => {
                    // no search term is considered as return all
                    if (!search) {
                        return true;
                    }
                    // otherwise name or email must match search term
                    if (partner.name && partner.name.toLowerCase().includes(search)) {
                        return true;
                    }
                    if (partner.email && partner.email.toLowerCase().includes(search)) {
                        return true;
                    }
                    return false;
                }).map(partner => {
                    // expected format
                    return {
                        email: partner.email,
                        id: partner.id,
                        name: partner.name,
                    };
                });
            // reduce results to max limit
            matchingPartners.length = Math.min(matchingPartners.length, limit);
            return matchingPartners;
        };

        // add main suggestions based on users
        const partnersFromUsers = this._getRecords('res.users', [])
            .map(user => this._getRecords('res.partner', [['id', '=', user.partner_id]])[0])
            .filter(partner => partner);
        const mainMatchingPartners = mentionSuggestionsFilter(partnersFromUsers, search, limit);

        let extraMatchingPartners = [];
        // if not enough results add extra suggestions based on partners
        if (mainMatchingPartners.length < limit) {
            const partners = this._getRecords('res.partner', [['id', 'not in', mainMatchingPartners.map(partner => partner.id)]]);
            extraMatchingPartners = mentionSuggestionsFilter(partners, search, limit);
        }
        return [mainMatchingPartners, extraMatchingPartners];
    },
    /**
     * Simulates `im_search` on `res.partner`.
     *
     * @private
     * @param {string} [name='']
     * @param {integer} [limit=20]
     * @returns {Object[]}
     */
    _mockResPartnerImSearch(name = '', limit = 20) {
        name = name.toLowerCase(); // simulates ILIKE
        // simulates domain with relational parts (not supported by mock server)
        const matchingPartners = this._getRecords('res.users', [])
            .filter(user => {
                const partner = this._getRecords('res.partner', [['id', '=', user.partner_id]])[0];
                // user must have a partner
                if (!partner) {
                    return false;
                }
                // not current partner
                if (partner.id === this.currentPartnerId) {
                    return false;
                }
                // no name is considered as return all
                if (!name) {
                    return true;
                }
                if (partner.name && partner.name.toLowerCase().includes(name)) {
                    return true;
                }
                return false;
            }).map(user => {
                const partner = this._getRecords('res.partner', [['id', '=', user.partner_id]])[0];
                return {
                    id: partner.id,
                    im_status: user.im_status || 'offline',
                    name: partner.name,
                    user_id: user.id,
                };
            });
        matchingPartners.length = Math.min(matchingPartners.length, limit);
        return matchingPartners;
    },
    /**
     * Simulates `mail_partner_format` on `res.partner`.
     *
     * @private
     * @return {integer} id
     * @return {Object}
     */
    _mockResPartnerMailPartnerFormat(id) {
        const partner = this._getRecords(
            'res.partner',
            [['id', '=', id]],
            { active_test: false }
        )[0];
        return {
            "id": partner.id,
            "display_name": partner.display_name,
            "active": partner.active,
        };
    },
});

});
