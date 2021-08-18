/** @odoo-module **/

import { getMessagingComponent } from "@mail/utils/messaging_component";

import AbstractService from 'web.AbstractService';
import { bus, serviceRegistry } from 'web.core';

const ChatWindowService = AbstractService.extend({
    /**
     * @override {web.AbstractService}
     */
    start() {
        this._super(...arguments);
        this._listenHomeMenu();
    },
    /**
     * @private
     */
    destroy() {
        if (this.component) {
            this.component.destroy();
            this.component = undefined;
        }
    },

    //--------------------------------------------------------------------------
    // Private
    //--------------------------------------------------------------------------

    /**
     * @private
     * @returns {Node}
     */
    _getParentNode() {
        return document.querySelector('body');
    },
    /**
     * @private
     */
    _listenHomeMenu() {
        bus.on('web_client_ready', this, this._onWebClientReady.bind(this));
    },
    /**
     * @private
     */
    async _mount() {
        if (this.component) {
            this.component.destroy();
            this.component = undefined;
        }
        const ChatWindowManagerComponent = getMessagingComponent("ChatWindowManager");
        this.component = new ChatWindowManagerComponent(null);
        const parentNode = this._getParentNode();
        await this.component.mount(parentNode);
    },

    //--------------------------------------------------------------------------
    // Handlers
    //--------------------------------------------------------------------------

    /**
     * @private
     */
    async _onWebClientReady() {
        await this._mount();
    },
});

serviceRegistry.add('chat_window', ChatWindowService);

export default ChatWindowService;
