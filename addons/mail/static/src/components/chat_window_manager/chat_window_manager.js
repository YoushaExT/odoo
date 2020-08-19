odoo.define('mail/static/src/components/chat_window_manager/chat_window_manager.js', function (require) {
'use strict';

const components = {
    ChatWindow: require('mail/static/src/components/chat_window/chat_window.js'),
    ChatWindowHiddenMenu: require('mail/static/src/components/chat_window_hidden_menu/chat_window_hidden_menu.js'),
};
const useStore = require('mail/static/src/component_hooks/use_store/use_store.js');

const { Component } = owl;

class ChatWindowManager extends Component {

    /**
     * @override
     */
    constructor(...args) {
        super(...args);
        useStore(props => {
            const chatWindowManager = this.env.messaging && this.env.messaging.chatWindowManager;
            const allOrderedVisible = chatWindowManager
                ? chatWindowManager.allOrderedVisible
                : [];
            return {
                allOrderedVisible: allOrderedVisible.map(chatWindow => chatWindow ? chatWindow.__state : undefined),
                chatWindowManager: chatWindowManager ? chatWindowManager.__state : undefined,
                isMessagingInitialized: this.env.isMessagingInitialized(),
            };
        }, {
            compareDepth: {
                allOrderedVisible: 1,
            },
        });
    }

}

Object.assign(ChatWindowManager, {
    components,
    props: {},
    template: 'mail.ChatWindowManager',
});

return ChatWindowManager;

});
