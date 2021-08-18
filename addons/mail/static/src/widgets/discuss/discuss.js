/** @odoo-module **/

import { getMessagingComponent } from "@mail/utils/messaging_component";

import AbstractAction from 'web.AbstractAction';
import { action_registry } from 'web.core';

const { Component } = owl;

const DiscussWidget = AbstractAction.extend({
    template: 'mail.widgets.Discuss',
    /**
     * @override {web.AbstractAction}
     * @param {web.ActionManager} parent
     * @param {Object} action
     * @param {Object} [action.context]
     * @param {string} [action.context.active_id]
     * @param {Object} [action.params]
     * @param {string} [action.params.default_active_id]
     * @param {Object} [options={}]
     */
    init(parent, action, options={}) {
        this._super(...arguments);

        // control panel attributes
        this.action = action;
        this.actionManager = parent;
        this.discuss = undefined;
        this.options = options;

        this.component = undefined;

        this._lastPushStateActiveThread = null;
        this.env = Component.env;
        Component.env.services.messaging.modelManager.messagingCreatedPromise.then(() => {
            const initActiveId = this.options.active_id ||
                (this.action.context && this.action.context.active_id) ||
                (this.action.params && this.action.params.default_active_id) ||
                'mail.box_inbox';
            this.discuss = this.env.messaging.discuss;
            this.discuss.update({ initActiveId });
        });
    },
    /**
     * @override {web.AbstractAction}
     */
    destroy() {
        if (this.component) {
            this.component.destroy();
            this.component = undefined;
        }
        if (this.$buttons) {
            this.$buttons.off().remove();
        }
        this._super(...arguments);
    },
    /**
     * @override {web.AbstractAction}
     */
    on_attach_callback() {
        this._super(...arguments);
        if (this.component) {
            // prevent twice call to on_attach_callback (FIXME)
            return;
        }
        const DiscussComponent = getMessagingComponent("Discuss");
        this.component = new DiscussComponent();
        this._pushStateActionManagerEventListener = ev => {
            ev.stopPropagation();
            if (this._lastPushStateActiveThread === this.discuss.thread) {
                return;
            }
            this._pushStateActionManager();
            this._lastPushStateActiveThread = this.discuss.thread;
        };
        this._showRainbowManEventListener = ev => {
            ev.stopPropagation();
            this._showRainbowMan();
        };
        this.el.addEventListener(
            'o-push-state-action-manager',
            this._pushStateActionManagerEventListener
        );
        this.el.addEventListener(
            'o-show-rainbow-man',
            this._showRainbowManEventListener
        );
        return this.component.mount(this.el);
    },
    /**
     * @override {web.AbstractAction}
     */
    on_detach_callback() {
        this._super(...arguments);
        if (this.component) {
            this.component.destroy();
        }
        this.component = undefined;
        this.el.removeEventListener(
            'o-push-state-action-manager',
            this._pushStateActionManagerEventListener
        );
        this.el.removeEventListener(
            'o-show-rainbow-man',
            this._showRainbowManEventListener
        );
    },

    //--------------------------------------------------------------------------
    // Private
    //--------------------------------------------------------------------------

    /**
     * @private
     */
    _pushStateActionManager() {
        this.actionManager.do_push_state({
            action: this.action.id,
            active_id: this.discuss.activeId,
        });
    },
    /**
     * @private
     */
    _showRainbowMan() {
        this.trigger_up('show_effect', {
            message: this.env._t("Congratulations, your inbox is empty!"),
            type: 'rainbow_man',
        });
    },
});

action_registry.add('mail.widgets.discuss', DiscussWidget);

export default DiscussWidget;
