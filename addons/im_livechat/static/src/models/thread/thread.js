odoo.define('im_livechat/static/src/models/thread/thread.js', function (require) {
'use strict';

const {
    registerClassPatchModel,
    registerInstancePatchModel,
} = require('mail/static/src/model/model_core.js');

registerClassPatchModel('mail.thread', 'im_livechat/static/src/models/thread/thread.js', {

    //----------------------------------------------------------------------
    // Public
    //----------------------------------------------------------------------

    /**
     * @override
     */
    convertData(data) {
        const data2 = this._super(data);
        if ('last_message_id' in data) {
            if (!data2.messagesAsServerChannel) {
                data2.messagesAsServerChannel = [];
            }
            data2.messagesAsServerChannel.push(['insert', { id: data.last_message_id }]);
        }
        if ('livechat_visitor' in data && data.livechat_visitor) {
            if (!data2.members) {
                data2.members = [];
            }
            // `livechat_visitor` without `id` is the anonymous visitor.
            if (!data.livechat_visitor.id) {
                /**
                 * Create partner derived from public partner and replace the
                 * public partner.
                 *
                 * Indeed the anonymous visitor is registered as a member of the
                 * channel as the public partner in the database to avoid
                 * polluting the contact list with many temporary partners.
                 *
                 * But the issue with public partner is that it is the same
                 * record for every livechat, whereas every correspondent should
                 * actually have its own visitor name, typing status, etc.
                 *
                 * Due to JS being temporary by nature there is no such notion
                 * of polluting the database, it is therefore acceptable and
                 * easier to handle one temporary partner per channel.
                 */
                data2.members.push(['unlink', this.env.messaging.publicPartner]);
                const partner = this.env.models['mail.partner'].create(
                    Object.assign(
                        this.env.models['mail.partner'].convertData(data.livechat_visitor),
                        { id: this.env.models['mail.partner'].getNextPublicId() }
                    )
                );
                data2.members.push(['link', partner]);
            } else {
                const partnerData = this.env.models['mail.partner'].convertData(data.livechat_visitor);
                data2.members.push(['insert', partnerData]);
            }
        }
        return data2;
    },
});

registerInstancePatchModel('mail.thread', 'im_livechat/static/src/models/thread/thread.js', {

    //----------------------------------------------------------------------
    // Private
    //----------------------------------------------------------------------

    /**
     * @override
     */
    _computeDisplayName() {
        if (this.channel_type === 'livechat' && this.correspondent) {
            if (this.correspondent.country) {
                return `${this.correspondent.nameOrDisplayName} (${this.correspondent.country.name})`;
            }
            return this.correspondent.nameOrDisplayName;
        }
        return this._super();
    },
});

});
