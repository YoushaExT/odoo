/** @odoo-module **/

import { useModels } from '@mail/component_hooks/use_models/use_models';
import { useShouldUpdateBasedOnProps } from '@mail/component_hooks/use_should_update_based_on_props/use_should_update_based_on_props';

import Dialog from 'web.OwlDialog';

const { Component } = owl;
const { useRef } = owl.hooks;

const components = { Dialog };

export class AttachmentDeleteConfirmDialog extends Component {

    /**
     * @override
     */
    constructor(...args) {
        super(...args);
        useShouldUpdateBasedOnProps();
        useModels();
        // to manually trigger the dialog close event
        this._dialogRef = useRef('dialog');
    }

    //--------------------------------------------------------------------------
    // Public
    //--------------------------------------------------------------------------

    /**
     * @returns {mail.attachment}
     */
    get attachment() {
        return this.env.models['mail.attachment'].get(this.props.attachmentLocalId);
    }

    /**
     * @returns {string}
     */
    getBody() {
        return _.str.sprintf(
            this.env._t(`Do you really want to delete "%s"?`),
            owl.utils.escape(this.attachment.displayName)
        );
    }

    /**
     * @returns {string}
     */
    getTitle() {
        return this.env._t("Confirmation");
    }

    //--------------------------------------------------------------------------
    // Handlers
    //--------------------------------------------------------------------------

    /**
     * @private
     */
    _onClickCancel() {
        this._dialogRef.comp._close();
    }

    /**
     * @private
     */
    async _onClickOk() {
        await this.attachment.remove();
        this._dialogRef.comp._close();
        this.trigger('o-attachment-removed', { attachmentLocalId: this.props.attachmentLocalId });
    }

}

Object.assign(AttachmentDeleteConfirmDialog, {
    components,
    props: {
        attachmentLocalId: String,
    },
    template: 'mail.AttachmentDeleteConfirmDialog',
});
