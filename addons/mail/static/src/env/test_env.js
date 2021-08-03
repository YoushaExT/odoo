/** @odoo-module **/

import { makeDeferred } from '@mail/utils/deferred/deferred';
import { nextTick } from '@mail/utils/utils';

const { EventBus } = owl.core;

/**
 * @param {Object} [providedEnv={}]
 * @returns {Object}
 */
function addMessagingToEnv(providedEnv = {}) {
    const env = Object.assign(providedEnv);

    /**
     * Registry of models.
     */
    env.models = {};
    /**
     * Environment keys used in messaging.
     */
    Object.assign(env, {
        autofetchPartnerImStatus: false,
        browser: Object.assign({
            innerHeight: 1080,
            innerWidth: 1920,
            Notification: Object.assign({
                permission: 'denied',
                async requestPermission() {
                    return this.permission;
                },
            }, (env.browser && env.browser.Notification) || {}),
        }, env.browser),
        destroyMessaging() {
            if (env.modelManager) {
                env.modelManager.deleteAll();
                env.messaging = undefined;
            }
        },
        disableAnimation: true,
        isMessagingInitialized() {
            if (!this.messaging) {
                return false;
            }
            return this.messaging.isInitialized;
        },
        /**
         * States whether the environment is in QUnit test or not.
         *
         * Useful to prevent some behaviour in QUnit tests, like applying
         * style of attachment that uses url.
         */
        isQUnitTest: true,
        loadingBaseDelayDuration: providedEnv.loadingBaseDelayDuration || 0,
        messaging: undefined,
        messagingCreatedPromise: makeDeferred(),
        messagingInitializedDeferred: makeDeferred(),
        messagingBus: new EventBus(),
        modelManager: undefined,
    });

    return env;
}

/**
 * @param {Object} [providedEnv={}]
 * @returns {Object}
 */
function addTimeControlToEnv(providedEnv = {}) {

    let env = Object.assign({}, providedEnv);

    if (!env.browser) {
        env.browser = {};
    }
    // list of timeout ids that have timed out.
    let timedOutIds = [];
    // key: timeoutId, value: func + remaining duration
    const timeouts = new Map();
    Object.assign(env.browser, {
        clearTimeout: id => {
            timeouts.delete(id);
            timedOutIds = timedOutIds.filter(i => i !== id);
        },
        setTimeout: (func, duration) => {
            const timeoutId = _.uniqueId('timeout_');
            const timeout = {
                id: timeoutId,
                isTimedOut: false,
                func,
                duration,
            };
            timeouts.set(timeoutId, timeout);
            if (duration === 0) {
                timedOutIds.push(timeoutId);
                timeout.isTimedOut = true;
            }
            return timeoutId;
        },
    });
    if (!env.testUtils) {
        env.testUtils = {};
    }
    Object.assign(env.testUtils, {
        advanceTime: async duration => {
            await nextTick();
            for (const id of timeouts.keys()) {
                const timeout = timeouts.get(id);
                if (timeout.isTimedOut) {
                    continue;
                }
                timeout.duration = Math.max(timeout.duration - duration, 0);
                if (timeout.duration === 0) {
                    timedOutIds.push(id);
                }
            }
            while (timedOutIds.length > 0) {
                const id = timedOutIds.shift();
                const timeout = timeouts.get(id);
                timeouts.delete(id);
                timeout.func();
                await nextTick();
            }
            await nextTick();
        },
    });
    return env;
}

export {
    addMessagingToEnv,
    addTimeControlToEnv,
}
