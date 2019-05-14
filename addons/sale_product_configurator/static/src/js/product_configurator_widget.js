odoo.define('sale_product_configurator.product_configurator', function (require) {
var ProductConfiguratorWidget = require('sale.product_configurator');

/**
 * Extension of the ProductConfiguratorWidget to support product configuration.
 * It opens when a configurable product_template is set.
 * (multiple variants, or custom attributes)
 *
 * The product customization information includes :
 * - is_configurable_product
 * - product_template_attribute_value_ids
 *
 */
ProductConfiguratorWidget.include({
    /**
     * Override of sale.product_configurator Hook
     *
     * @override
    */
    _isConfigurableProduct: function () {
        return this.recordData.is_configurable_product || this._super.apply(this, arguments);
    },

    /**
     * Set restoreProductTemplateId for further backtrack.
     *
     * @override
     * @private
     */
    _onFieldChanged: function (ev) {
        this.restoreProductTemplateId = this.recordData.product_template_id;

        this._super.apply(this, arguments);
    },

    /**
    * This method is overridden to check if the product_template_id
    * needs configuration or not:
    *
    * - The product_template has only one "product.product" and is not dynamic
    *   -> Set the product_id on the SO line
    *   -> If the product has optional products, open the configurator in 'options' mode
    *
    * - The product_template is configurable
    *   -> Open the product configurator wizard and initialize it with
    *      the provided product_template_id and its current attribute values
    *
    * @override
    * @private
    */
    _onTemplateChange: function (productTemplateId, dataPointId) {
        var self = this;

        return this._rpc({
            model: 'product.template',
            method: 'get_single_product_variant',
            args: [
                productTemplateId
            ]
        }).then(function (result) {
            if (result) {
                self.trigger_up('field_changed', {
                    dataPointID: dataPointId,
                    changes: {
                        product_id: {id: result.product_id},
                        product_custom_attribute_value_ids: {
                            operation: 'DELETE_ALL'
                        }
                    },
                    onSuccess: function () {
                        if (result.has_optional_products) {
                            // VFE WARNING optional products and configurable product_id don't go well
                            // together for the moment...
                            self._openOptionsConfigurator(productTemplateId, dataPointId);
                        }
                    }
                });
            } else {
                self._openProductConfigurator({
                        configuratorMode: 'add',
                        default_pricelist_id: self._getPricelistId(),
                        default_product_template_id: productTemplateId
                    },
                    dataPointId
                );
            }
            return Promise.resolve(true);
            // always returns true for the moment because no other configurator exists.
        });
    },

    _openOptionsConfigurator: function (productTemplateId, dataPointId) {
        this._openProductConfigurator({
                configuratorMode: 'options',
                default_pricelist_id: this._getPricelistId(),
                default_product_template_id: productTemplateId
            },
            dataPointId
        );
    },

    /**
     * Opens the product configurator to allow configuring the product template
     * and its various options.
     *
     * The configuratorMode param controls how to open the configurator.
     * - The "add" mode will allow configuring the product template & options.
     * - The "edit" mode will only allow editing the product template's configuration.
     * - The "options" mode is a special case where the product configurator is used as a bridge
     *   between the SO line and the optional products modal. It will hide its window and handle
     *   the communication between those two.
     *
     * When the configuration is canceled (i.e when the product configurator is closed using the
     * "CANCEL" button or the cross on the top right corner of the window),
     * the product_template is reset to its previous value if any.
     *
     * @param {Object} data various "default_" values
     *  {string} data.configuratorMode 'add' or 'edit' or 'options'.
     * @param {string} dataPointId
     *
     * @private
     */
    _openProductConfigurator: function (data, dataPointId) {
        var self = this;
        this.do_action('sale_product_configurator.sale_product_configurator_action', {
            additional_context: data,
            on_close: function (result) {
                if (result && result !== 'special') {
                    // TODO if mode == 'options'
                    // if no options chosen, don't trigger events...
                    self._addProducts(result, dataPointId);
                } else {
                    if (self.restoreProductTemplateId) {
                        self.trigger_up('field_changed', {
                            dataPointID: dataPointId,
                            preventProductIdCheck: true,
                            changes: {
                                product_template_id: self.restoreProductTemplateId.data
                            }
                        });
                    }
                }
            }
        });
    },

    /**
     * Opens the product configurator in "edit" mode.
     * (see '_openProductConfigurator' for more info on the "edit" mode).
     * The requires to retrieve all the needed data from the SO line
     * that are kept in the "recordData" object.
     *
     * @private
     */
    _onEditProductConfiguration: function () {
        if (!this.recordData.is_configurable_product) {
            // if line should be edited by another configurator
            // or simply inline.
            this._super.apply(this, arguments);
            return;
        }
        // If line has been set up through the product_configurator:
        this._openProductConfigurator({
                configuratorMode: 'edit',
                default_product_template_id: this.recordData.product_template_id.data.id,
                default_pricelist_id: this._getPricelistId(),
                default_product_template_attribute_value_ids: this._convertFromMany2Many(
                    this.recordData.product_template_attribute_value_ids
                ),
                default_product_no_variant_attribute_value_ids: this._convertFromMany2Many(
                    this.recordData.product_no_variant_attribute_value_ids
                ),
                default_product_custom_attribute_value_ids: this._convertFromOne2Many(
                    this.recordData.product_custom_attribute_value_ids
                ),
                default_quantity: this.recordData.product_uom_qty
            },
            this.dataPointID
        );
    },

    /**
     * This will first modify the SO line to update all the information coming from
     * the product configurator using the 'field_changed' event.
     *
     * onSuccess from that first method, it will add the optional products to the SO
     * using the 'add_record' event.
     *
     * Doing both at the same time could lead to unordered product_template/options.
     *
     * @param {Object} products the products to add to the SO line.
     *   {Object} products.mainProduct the product_template configured
     *     with various attribute/custom values
     *   {Array} products.options the various selected optional products
     *     with their configuration
     * @param {string} dataPointId
     *
     * @private
     */
    _addProducts: function (result, dataPointId) {
        var self = this;
        this.trigger_up('field_changed', {
            dataPointID: dataPointId,
            preventProductIdCheck: true,
            changes: this._getMainProductChanges(result.mainProduct),
            onSuccess: function () {
                var parentList = self.getParent();
                if (result.options && result.options.length !== 0) {
                    self.trigger_up('add_record', {
                        context: self._productsToRecords(result.options),
                        forceEditable: 'bottom',
                        allowWarning: true,
                        onSuccess: function () {
                            // Leave edit mode of the last line added.
                            parentList.unselectRow();
                        }
                    });

                } else if (!self._isConfigurableLine()) {
                    // Leave edit mode of current line if no other wizard
                    // will be opened by the field_changed event.
                    parentList.unselectRow();
                }
            }
        });
    },

    /**
     * This will convert the result of the product configurator into
     * "changes" that are understood by the basic_model.js
     *
     * For the product_custom_attribute_value_ids, we need to do a DELETE_ALL
     * command to clean the currently selected values and then a CREATE for every
     * custom value specified in the configurator.
     *
     * For the product_no_variant_attribute_value_ids, we also need to do a DELETE_ALL
     * command to clean the currently selected values and issue a single ADD_M2M containing
     * all the ids of the product_attribute_values.
     *
     * @param {Object} mainProduct
     *
     * @private
     */
    _getMainProductChanges: function (mainProduct) {
        var result = {
            product_id: {id: mainProduct.product_id},
            product_template_id: {id: mainProduct.product_template_id},
            product_uom_qty: mainProduct.quantity
        };

        var customAttributeValues = mainProduct.product_custom_attribute_values;
        var customValuesCommands = [{operation: 'DELETE_ALL'}];
        if (customAttributeValues && customAttributeValues.length !== 0) {
            _.each(customAttributeValues, function (customValue) {
                // FIXME awa: This could be optimized by adding a "disableDefaultGet" to avoid
                // having multiple default_get calls that are useless since we already
                // have all the default values locally.
                // However, this would mean a lot of changes in basic_model.js to handle
                // those "default_" values and set them on the various fields (text,o2m,m2m,...).
                // -> This is not considered as worth it right now.
                customValuesCommands.push({
                    operation: 'CREATE',
                    context: [{
                        default_attribute_value_id: customValue.attribute_value_id,
                        default_custom_value: customValue.custom_value
                    }]
                });
            });
        }

        result['product_custom_attribute_value_ids'] = {
            operation: 'MULTI',
            commands: customValuesCommands
        };

        var noVariantAttributeValues = mainProduct.no_variant_attribute_values;
        var noVariantCommands = [{operation: 'DELETE_ALL'}];
        if (noVariantAttributeValues && noVariantAttributeValues.length !== 0) {
            var resIds = _.map(noVariantAttributeValues, function (noVariantValue) {
                return {id: parseInt(noVariantValue.value)};
            });

            noVariantCommands.push({
                operation: 'ADD_M2M',
                ids: resIds
            });
        }

        result['product_no_variant_attribute_value_ids'] = {
            operation: 'MULTI',
            commands: noVariantCommands
        };

        return result;
    },

    /**
     * Returns the pricelist_id set on the sale_order form
     *
     * @private
     * @returns {integer} pricelist_id's id
     */
    _getPricelistId: function () {
        return this.record.evalContext.parent.pricelist_id;
    },

    /**
     * Will map the products to appropriate record objects that are
     * ready for the default_get.
     *
     * @param {Array} products The products to transform into records
     *
     * @private
     */
    _productsToRecords: function (products) {
        var records = [];
        _.each(products, function (product) {
            var record = {
                default_product_id: product.product_id,
                default_product_template_id: product.product_template_id,
                default_product_uom_qty: product.quantity
            };

            if (product.no_variant_attribute_values) {
                var default_product_no_variant_attribute_values = [];
                _.each(product.no_variant_attribute_values, function (attribute_value) {
                        default_product_no_variant_attribute_values.push(
                            [4, parseInt(attribute_value.value)]
                        );
                });
                record['default_product_no_variant_attribute_value_ids']
                    = default_product_no_variant_attribute_values;
            }

            if (product.product_custom_attribute_values) {
                var default_custom_attribute_values = [];
                _.each(product.product_custom_attribute_values, function (attribute_value) {
                    default_custom_attribute_values.push(
                            [0, 0, {
                                attribute_value_id: attribute_value.attribute_value_id,
                                custom_value: attribute_value.custom_value
                            }]
                        );
                });
                record['default_product_custom_attribute_value_ids']
                    = default_custom_attribute_values;
            }

            records.push(record);
        });

        return records;
    }
});

return ProductConfiguratorWidget;

});
