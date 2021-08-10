/** @odoo-module */

import { registry } from "@web/core/registry";

const { Component } = owl;
const { xml } = owl.tags;

class DialogCommand extends Component {}
DialogCommand.template = xml`
    <div class="o_command_default">
        <span t-esc="props.name"/>
        <span t-if="props.email" t-esc="props.email"/>
    </div>
`;

const commandProviderRegistry = registry.category("command_provider");

commandProviderRegistry.add("partner", {
    nameSpace: "@",
    async provide(newEnv, options) {
        const env = Component.env;
        await env.messagingCreatedPromise;
        await env.messaging.initializedPromise;
        const suggestions = [];
        await env.models['mail.partner'].imSearch({
            callback(partners) {
                partners.forEach((partner) => {
                    suggestions.push({
                        Component: DialogCommand,
                        action() {
                            partner.openChat();
                        },
                        name: partner.nameOrDisplayName,
                        props: {
                            email: partner.email,
                        },
                    });
                });
            },
            keyword: options.searchValue,
            limit: 10,
        });
        return suggestions;
    },
});

commandProviderRegistry.add("channel", {
    nameSpace: "#",
    async provide(newEnv, options) {
        const env = Component.env;
        await env.messagingCreatedPromise;
        await env.messaging.initializedPromise;
        const channels = await env.models['mail.thread'].searchChannelsToOpen({
            limit: 10,
            searchTerm: options.searchValue,
        });
        return channels.map((channel) => ({
            async action() {
                await channel.join();
                // Channel must be pinned immediately to be able to open it before
                // the result of join is received on the bus.
                channel.update({ isServerPinned: true });
                channel.open();
            },
            name: channel.displayName,
        }));
    },
});
