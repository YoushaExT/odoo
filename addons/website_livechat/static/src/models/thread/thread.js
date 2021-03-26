odoo.define('website_livechat/static/src/models/thread/thread.js', function (require) {
'use strict';

const {
    registerClassPatchModel,
    registerFieldPatchModel,
} = require('@mail/model/model_core');
const { many2one } = require('@mail/model/model_field');
const { insert, unlink } = require('@mail/model/model_field_command');

registerClassPatchModel('mail.thread', 'website_livechat/static/src/models/thread/thread.js', {

    //----------------------------------------------------------------------
    // Public
    //----------------------------------------------------------------------

    /**
     * @override
     */
    convertData(data) {
        const data2 = this._super(data);
        if ('visitor' in data) {
            if (data.visitor) {
                data2.visitor = insert(this.env.models['website_livechat.visitor'].convertData(data.visitor));
            } else {
                data2.visitor = unlink();
            }
        }
        return data2;
    },

});

registerFieldPatchModel('mail.thread', 'website_livechat/static/src/models/thread/thread.js', {
    /**
     * Visitor connected to the livechat.
     */
    visitor: many2one('website_livechat.visitor', {
        inverse: 'threads',
    }),
});

});
