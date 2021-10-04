/** @odoo-module **/

import { registerNewModel } from '@mail/model/model_core';
import { attr, many2many, many2one, one2one } from '@mail/model/model_field';

function factory(dependencies) {

    class AttachmentViewer extends dependencies['mail.model'] {

        //----------------------------------------------------------------------
        // Public
        //----------------------------------------------------------------------

        /**
         * Close the attachment viewer by closing its linked dialog.
         */
        close() {
            const dialog = this.messaging.models['mail.dialog'].find(dialog => dialog.record === this);
            if (dialog) {
                dialog.delete();
            }
        }
    }

    AttachmentViewer.fields = {
        /**
         * Angle of the image. Changes when the user rotates it.
         */
        angle: attr({
            default: 0,
        }),
        attachment: many2one('mail.attachment'),
        attachmentList: many2one('mail.attachment_list', {
            inverse: 'attachmentViewer',
            readonly: true,
            required: true,
        }),
        attachments: many2many('mail.attachment', {
            inverse: 'attachmentViewer',
            related: 'attachmentList.viewableAttachments',
        }),
        /**
         * Determines the dialog displaying this attachment viewer.
         */
        dialog: one2one('mail.dialog', {
            inverse: 'attachmentViewer',
            isCausal: true,
            readonly: true,
        }),
        /**
         * Determine whether the image is loading or not. Useful to diplay
         * a spinner when loading image initially.
         */
        isImageLoading: attr({
            default: false,
        }),
        /**
         * Scale size of the image. Changes when user zooms in/out.
         */
        scale: attr({
            default: 1,
        }),
    };
    AttachmentViewer.identifyingFields = ['attachmentList'];
    AttachmentViewer.modelName = 'mail.attachment_viewer';

    return AttachmentViewer;
}

registerNewModel('mail.attachment_viewer', factory);
