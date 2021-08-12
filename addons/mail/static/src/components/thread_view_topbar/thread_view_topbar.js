/** @odoo-module **/

import { registerMessagingComponent } from '@mail/utils/messaging_component';
import { useRefToModel } from '@mail/component_hooks/use_ref_to_model/use_ref_to_model';
import { useUpdateToModel } from '@mail/component_hooks/use_update_to_model/use_update_to_model';

const { Component } = owl;

export class ThreadViewTopbar extends Component {

    /**
     * @override
     */
    setup() {
        super.setup();
        useRefToModel({ fieldName: 'threadNameInputRef', modelName: 'mail.thread_view_topbar', propNameAsRecordLocalId: 'localId', refName: 'threadNameInput' });
        useUpdateToModel({ methodName: 'onComponentUpdate', modelName: 'mail.thread_view_topbar', propNameAsRecordLocalId: 'localId' });
    }

    //--------------------------------------------------------------------------
    // Public
    //--------------------------------------------------------------------------

    /**
     * @returns {mail.thread_view_topbar}
     */
    get threadViewTopBar() {
        return this.env.models['mail.thread_view_topbar'].get(this.props.localId);
    }

}

Object.assign(ThreadViewTopbar, {
    props: {
        localId: String,
    },
    template: 'mail.ThreadViewTopbar',
});

registerMessagingComponent(ThreadViewTopbar);
