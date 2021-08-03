/** @odoo-module **/

import { useModels } from '@mail/component_hooks/use_models/use_models';
import { useShouldUpdateBasedOnProps } from '@mail/component_hooks/use_should_update_based_on_props/use_should_update_based_on_props';

const { Component } = owl;
const { useRef } = owl.hooks;

export class Dialog extends Component {

    /**
     * @param {...any} args
     */
    constructor(...args) {
        super(...args);
        /**
         * Reference to the component used inside this dialog.
         */
        this._componentRef = useRef('component');
        this._onClickGlobal = this._onClickGlobal.bind(this);
        this._onKeydownDocument = this._onKeydownDocument.bind(this);
        useShouldUpdateBasedOnProps();
        useModels();
        this._constructor();
    }

    /**
     * Allows patching constructor.
     */
    _constructor() {}

    mounted() {
        document.addEventListener('click', this._onClickGlobal, true);
        document.addEventListener('keydown', this._onKeydownDocument);
    }

    willUnmount() {
        document.removeEventListener('click', this._onClickGlobal, true);
        document.removeEventListener('keydown', this._onKeydownDocument);
    }

    //--------------------------------------------------------------------------
    // Public
    //--------------------------------------------------------------------------

    /**
     * @returns {mail.dialog}
     */
    get dialog() {
        return this.env.models['mail.dialog'].get(this.props.dialogLocalId);
    }

    //--------------------------------------------------------------------------
    // Handlers
    //--------------------------------------------------------------------------

    /**
     * Called when clicking on this dialog.
     *
     * @private
     * @param {MouseEvent} ev
     */
    _onClick(ev) {
        ev.stopPropagation();
    }

    /**
     * Closes the dialog when clicking outside.
     * Does not work with attachment viewer because it takes the whole space.
     *
     * @private
     * @param {MouseEvent} ev
     */
    _onClickGlobal(ev) {
        if (this._componentRef.el && this._componentRef.el.contains(ev.target)) {
            return;
        }
        // TODO: this should be child logic (will crash if child doesn't have isCloseable!!)
        // task-2092965
        if (
            this._componentRef.comp &&
            this._componentRef.comp.isCloseable &&
            !this._componentRef.comp.isCloseable()
        ) {
            return;
        }
        this.dialog.delete();
    }

    /**
     * @private
     * @param {KeyboardEvent} ev
     */
    _onKeydownDocument(ev) {
        if (ev.key === 'Escape') {
            this.dialog.delete();
        }
    }

}

Object.assign(Dialog, {
    props: {
        dialogLocalId: String,
    },
    template: 'mail.Dialog',
});
