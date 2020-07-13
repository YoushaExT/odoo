odoo.define("web/static/src/js/model.js", function (require) {
    "use strict";

    const { groupBy, partitionBy } = require("web.utils");
    const Registry = require("web.Registry");

    const { Component, core } = owl;
    const { EventBus, Observer } = core;
    const isNotNull = (val) => val !== null && val !== undefined;

    /**
     * Feature extension of the class Model.
     * @see {Model}
     */
    class ModelExtension {
        /**
         * @param {Object} config
         * @param {Object} config.env
         */
        constructor(config) {
            this.config = config;
            this.env = this.config.env;
            this._shouldLoad = true;
            this.state = {};
        }

        //---------------------------------------------------------------------
        // Public
        //---------------------------------------------------------------------

        /**
         * Used by the parent model to initiate a load action. The actual
         * loading of the extension is determined by the "_shouldLoad" property.
         */
        async callLoad() {
            if (this._shouldLoad) {
                this._shouldLoad = false;
                await this.load();
            }
        }

        /**
         * Exports the current state of the extension.
         * @returns {Object}
         */
        exportState() {
            return this.state;
        }

        /**
         * Meant to return the result of the appropriate getter or do nothing
         * if not concerned by the given property.
         * @abstract
         * @param {string} property
         * @param  {...any} args
         * @returns {null}
         */
        get() {
            return null;
        }

        /**
         * Imports the given state after parsing it. If no state is given the
         * extension will prepare a new state and will need to be loaded.
         * @param {Object} [state]
         */
        importState(state) {
            this._shouldLoad = !state;
            if (this._shouldLoad) {
                this.prepareState();
            } else {
                Object.assign(this.state, state);
            }
        }

        /**
         * Called and awaited on initial model load.
         * @abstract
         * @returns {Promise}
         */
        async load() {
            /* ... */
        }

        /**
         * Called on initialization if no imported state for the extension is
         * found.
         * @abstract
         */
        prepareState() {
            /* ... */
        }

        /**
         * Called and awaited after an action dispatch.
         * @abstract
         * @returns {Promise}
         */
        async reloadAfterDispatch() {
            /* ... */
        }
    }
    /**
     * The layer of an extension indicates with which other extensions this one
     * will be loaded. This property must be overridden in case the model
     * depends on other extensions to be loaded first.
     */
    ModelExtension.layer = 0;

    /**
     * Model
     *
     * The purpose of the class Model and the associated hook useModel
     * is to offer something similar to an owl store but with no automatic
     * notification (and rendering) of components when the 'state' used in the
     * model would change. Instead, one should call the "__notifyComponents"
     * function whenever it is useful to alert registered component.
     * Nevertheless, when calling a method through the 'dispatch' method, a
     * notification does take place automatically, and registered components
     * (via useModel) are rendered.
     *
     * It is highly expected that this class will change in a near future. We
     * don't have the necessary hindsight to be sure its actual form is good.
     *
     * The following snippets show a typical use case of the model system: a
     * search model with a control panel extension feature.
     *
     *-------------------------------------------------------------------------
     * MODEL AND EXTENSIONS DEFINITION
     *-------------------------------------------------------------------------
     *
     * 1. Definition of the main model
     * @see Model
     * ```
     *  class ActionModel extends Model {
     *      // ...
     *  }
     * ```
     *
     * 2. Definition of the model extension
     * @see ModelExtension
     * ```
     *  class ControlPanelModelExtension extends ActionModel.Extension {
     *      // ...
     *  }
     * ```
     *
     * 3. Registration of the extension into the main model
     * @see Registry()
     * ```
     *  ActionModel.registry.add("SearchPanel", ControlPanelModelExtension, 10);
     * ```
     *
     *-------------------------------------------------------------------------
     * ON VIEW/ACTION INIT
     *-------------------------------------------------------------------------
     *
     * 4. Creation of the core model and its extensions
     * @see Model.prototype.constructor()
     * ```
     *  const extensions = {
     *      SearchPanel: {
     *          // ...
     *      }
     *  }
     *  const searchModelConfig = {
     *      // ...
     *  };
     *  const actionModel = new ActionModel(extensions, searchModelConfig);
     * ```
     *
     * 5. Loading of all extensions' asynchronous data
     * @see Model.prototype.load()
     * ```
     *  await actionModel.load();
     * ```
     *
     * 6. Subscribing to the model changes
     * @see useModel()
     * ```
     *  class ControlPanel extends Component {
     *      constructor() {
     *          super(...arguments);
     *          // env must contain the actionModel
     *          this.actionModel = useModel('actionModel');
     *      }
     *  }
     * ```
     *
     *-------------------------------------------------------------------------
     * MODEL USAGE ON RUNTIME
     *-------------------------------------------------------------------------
     *
     * Case: dispatch an action
     * @see Model.prototype.dispatch()
     * ```
     *  actionModel.dispatch("updateProperty", value);
     * ```
     *
     * Case: call a getter
     * @see Model.prototype.get()
     * ```
     *  const result = actionModel.get("property");
     * ```
     *
     * @abstract
     * @extends EventBus
     */
    class Model extends EventBus {
        /**
         * Instantiated extensions are determined by the `extensions` argument:
         * - keys are the extensions names as added in the registry
         * - values are the local configurations given to each extension
         * The extensions are grouped by the sequence number they where
         * registered with in the registry. Extensions being on the same level
         * will be loaded in parallel; this means that all extensions belonging
         * to the same group are awaited before loading the next group.
         * @param {Object<string, any>} [extensions={}]
         * @param {Object} [globalConfig={}] global configuration: can be
         *      accessed by itself and each of the added extensions.
         * @param {Object} [globalConfig.env]
         * @param {string} [globalConfig.importedState]
         */
        constructor(extensions = {}, globalConfig = {}) {
            super();

            this.config = globalConfig;
            this.env = this.config.env;

            this.dispatching = false;
            this.extensions = [];
            this.externalState = {};
            this.mapping = {};
            this.rev = 1;

            const { name, registry } = this.constructor;
            if (!registry || !(registry instanceof Registry)) {
                throw new Error(`Unimplemented registry on model "${name}".`);
            }
            // Order, group and sequencially instantiate all extensions
            const registryExtensions = Object.entries(registry.entries());
            const extensionNameLayers = registryExtensions.map(
                ([name, { layer }]) => ({ name, layer })
            );
            const groupedNameLayers = groupBy(extensionNameLayers, "layer");
            for (const groupNameLayers of Object.values(groupedNameLayers)) {
                for (const { name } of groupNameLayers) {
                    if (name in extensions) {
                        this.addExtension(name, extensions[name]);
                    }
                }
            }
            this.importState(this.config.importedState);
        }

        //---------------------------------------------------------------------
        // Public
        //---------------------------------------------------------------------

        /**
         * Method used internally to instantiate all extensions. Can also be
         * called externally to add extensions after model instantiation.
         * @param {string} extensionName
         * @param {Object} extensionConfig
         */
        addExtension(extensionName, extensionConfig) {
            const { name, registry } = this.constructor;
            const Extension = registry.get(extensionName);
            if (!Extension) {
                throw new Error(`Unknown model extension "${extensionName}" in model "${name}"`);
            }
            // Extension config = this.config ∪ extension.config
            const get = this.__get.bind(this, Extension.name);
            const trigger = this.trigger.bind(this);
            const config = Object.assign({ get, trigger }, this.config, extensionConfig);
            const extension = new Extension(config);
            if (!(Extension.layer in this.extensions)) {
                this.extensions[Extension.layer] = [];
            }
            this.extensions[Extension.layer].push(extension);
        }

        /**
         * Returns the result of the first related method on any instantiated
         * extension. This method must be overridden if multiple extensions
         * return a value with a common method (and dispatchAll does not
         * suffice). After the dispatch of the action, all models are partially
         * reloaded (@see ModelExtension.reloadAfterDispatch()) and components
         * are notified afterwards.
         */
        dispatch(method, ...args) {
            const isInitialDispatch = !this.dispatching;
            this.dispatching = true;
            for (const extension of this.extensions.flat()) {
                if (method in extension) {
                    extension[method](...args);
                }
            }
            if (isInitialDispatch) {
                this.dispatching = false;
                (async () => {
                    // Calls 'after dispatch' hooks
                    // Purpose: fetch updated data from the server. This is
                    // considered a loading action and is thus performed by groups
                    // instead of loading all extensions at once.
                    for (let layer = 0; layer < this.extensions.length; layer++) {
                        const afterDispatchPromises = [];
                        for (const extension of this.extensions[layer]) {
                            afterDispatchPromises.push(extension.reloadAfterDispatch());
                        }
                        await Promise.all(afterDispatchPromises);
                    }
                    // Notifies subscribed components
                    // Purpose: re-render components bound by 'useModel'
                    let rev = this.rev;
                    await Promise.resolve();
                    if (rev === this.rev) {
                        this._notifyComponents();
                    }
                })();
            }
        }

        /**
         * Stringifies and exports an object holding the exported state of each
         * active extension.
         * @returns {string}
         */
        exportState() {
            const exported = {};
            for (const extension of this.extensions.flat()) {
                exported[extension.constructor.name] = extension.exportState();
            }
            const fullState = Object.assign({}, this.externalState, exported);
            return JSON.stringify(fullState);
        }

        /**
         * Returns the result of the first related getter on any instantiated
         * extension. This method must be overridden if multiple extensions
         * share a common getter (and getAll does not make the job).
         * @param {string} property
         * @param  {...any} args
         * @returns {any}
         */
        get(property, ...args) {
            for (const extension of this.extensions.flat()) {
                const result = extension.get(property, ...args);
                if (isNotNull(result)) {
                    return result;
                }
            }
            return null;
        }

        /**
         * Parses the given stringified state object and imports each state
         * part to its related extension.
         * @param {string} [stringifiedState="null"]
         */
        importState(stringifiedState = "null") {
            const state = JSON.parse(stringifiedState) || {};
            Object.assign(this.externalState, state);
            for (const extension of this.extensions.flat()) {
                extension.importState(state[extension.constructor.name]);
            }
        }

        /**
         * Must be called after construction and state preparation/import.
         * Waits for all asynchronous work needed by the model extensions to be
         * ready.
         * /!\ The current model extensions do not require a smarter system at
         * the moment (therefore using layers instead of dependencies). It
         * should be changed if at some point an extension needs another
         * specific extension to be loaded instead of a whole batch (with the
         * current system some promises will be waited needlessly).
         * @returns {Promise}
         */
        async load() {
            for (let layer = 0; layer < this.extensions.length; layer++) {
                const layerPromises = [];
                for (const extension of this.extensions[layer]) {
                    layerPromises.push(extension.callLoad());
                }
                await Promise.all(layerPromises);
            }
        }

        //---------------------------------------------------------------------
        // Private
        //---------------------------------------------------------------------

        /**
         * Returns the list of the results of all extensions providing a getter
         * for the given property returning a non-null value, excluding the
         * extension whose name is equal to "excluded". This method is given to
         * each extension in the "config" object bound to the model scope and
         * having the extension name bound as the first argument.
         * @private
         * @param {string} excluded
         * @param {string} property
         * @param  {...any} args
         * @returns {any[]}
         */
        __get(excluded, property, ...args) {
            const results = [];
            for (const extension of this.extensions.flat()) {
                if (extension.constructor.name !== excluded) {
                    const result = extension.get(property, ...args);
                    if (isNotNull(result)) {
                        results.push(result);
                    }
                }
            }
            return results;
        }

        /**
         * @see Context.__notifyComponents() in owl.js for explanation
         * @private
         */
        async _notifyComponents() {
            const rev = ++this.rev;
            const subscriptions = this.subscriptions.update;
            const groups = partitionBy(subscriptions, (s) =>
                s.owner ? s.owner.__owl__.depth : -1
            );
            for (let group of groups) {
                const proms = group.map((sub) =>
                    sub.callback.call(sub.owner, rev)
                );
                Component.scheduler.flush();
                await Promise.all(proms);
            }
        }
    }

    Model.Extension = ModelExtension;

    /**
     * This is more or less the hook 'useContextWithCB' from owl only slightly
     * simplified.
     *
     * @param {string} modelName
     * @returns {model}
     */
    function useModel(modelName) {
        const component = Component.current;
        const model = component.env[modelName];
        if (!(model instanceof Model)) {
            throw new Error(`No Model found when connecting '${
                component.name
                }'`);
        }

        const mapping = model.mapping;
        const __owl__ = component.__owl__;
        const componentId = __owl__.id;
        if (!__owl__.observer) {
            __owl__.observer = new Observer();
            __owl__.observer.notifyCB = component.render.bind(component);
        }
        const currentCB = __owl__.observer.notifyCB;
        __owl__.observer.notifyCB = function () {
            if (model.rev > mapping[componentId]) {
                return;
            }
            currentCB();
        };
        mapping[componentId] = 0;
        const renderFn = __owl__.renderFn;
        __owl__.renderFn = function (comp, params) {
            mapping[componentId] = model.rev;
            return renderFn(comp, params);
        };

        model.on("update", component, async (modelRev) => {
            if (mapping[componentId] < modelRev) {
                mapping[componentId] = modelRev;
                await component.render();
            }
        });

        const __destroy = component.__destroy;
        component.__destroy = (parent) => {
            model.off("update", component);
            __destroy.call(component, parent);
        };

        return model;
    }

    return {
        Model,
        useModel,
    };
});
