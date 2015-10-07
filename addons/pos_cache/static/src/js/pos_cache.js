odoo.define('pos_cache.pos_cache', function (require) {
    "use strict";
    var core = require('web.core');
    var models = require('point_of_sale.models');
    var Model = require('web.DataModel');
    var _t = core._t;

    var posmodel_super = models.PosModel.prototype;
    models.PosModel = models.PosModel.extend({
        load_server_data: function () {
            var self = this;

            var product_index = _.findIndex(this.models, function (model) {
                return model.model === "product.product";
            });

            // Give both the fields and domain to pos_cache in the
            // backend. This way we don't have to hardcode these
            // values in the backend and they automatically stay in
            // sync with whatever is defined (and maybe extended by
            // other modules) in js.
            var product_model = this.models[product_index];
            var product_fields = product_model.fields;
            var product_domain = product_model.domain;

            // We don't want to load product.product the normal
            // uncached way, so get rid of it.
            if (product_index !== -1) {
                this.models.splice(product_index, 1);
            }

            return posmodel_super.load_server_data.apply(this, arguments).then(function () {
                var records = new Model('pos.config').call('get_products_from_cache',
                                                           [self.pos_session.config_id[0], product_fields, product_domain]);

                self.chrome.loading_message(_t('Loading') + ' product.product', 1);
                return records.then(function (product) {
                    self.db.add_products(product);
                });
            });
        },
    });
});
