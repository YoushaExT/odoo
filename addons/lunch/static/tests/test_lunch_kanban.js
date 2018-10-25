odoo.define('lunch.lunchKanbanTests', function (require) {
"use strict";

var LunchKanbanView = require('lunch.LunchKanbanView');
var testUtils = require('web.test_utils');

var createView = testUtils.createView;

QUnit.module('Views', {
    beforeEach: function () {
        this.data = {
            product: {
                fields: {
                    id: {string: 'ID', type: 'integer'},
                    is_available_at: {string: 'available_location_ids', type: 'integer'},
                },
                records: [
                    {id: 1, name: 'Tuna sandwich', price: 3.0, is_available_at: 1},
                ]
            },
        };
    },
}, function () {
    QUnit.module('LunchKanbanView');

    QUnit.test('Simple rendering of LunchKanbanView', function (assert) {
        assert.expect(7);

        var lunchKanban = createView({
            View: LunchKanbanView,
            model: 'product',
            data: this.data,
            arch: '<kanban><templates><t t-name="kanban-box">' +
                    '<div>' +
                    '</div>' +
                '</t></templates></kanban>',
            mockRPC: function(route, args) {
                if (route === '/lunch/infos') {
                    return $.when({
                        order: 1,
                        wallet: 20,
                        username: 'Marc Demo',
                        userimage: '',
                        is_manager: false,
                        users: [
                            {id: 1, name: 'Mitchell Admin'},
                            {id: 2, name: 'Marc Demo'},
                        ],
                        total: 7.4,
                        state: 'new',
                        lines: [
                            {id: 1, product: ['Pizza Italiana', 7.4], toppings: [], quantity: 1.0, price: 7.4}
                        ],
                        alerts: [],
                        locations: ['hello', 'hallo'],
                        user_location: [1, 'hello'],
                    });
                } else if (route === '/lunch/user_location_get') {
                    return $.when(1);
                } else if (route === '/web/dataset/call_kw/ir.model.data/xmlid_to_res_id') {
                    return $.when();
                } else if (route.startsWith('data:image/png;base64,')) {
                    return $.when();
                }
                return this._super(route, args);
            },
        });

        var $section = $(lunchKanban.$('.o_lunch_widget_info')[0]);
        // username
        assert.strictEqual($section.find('div:eq(1) div:eq(0)').text().trim(), 'Marc Demo', 'Username should have been Marc Demo');
        // your order section
        $section = $(lunchKanban.$('.o_lunch_widget_info')[1]);
        // only one line
        assert.strictEqual($section.find('div:eq(2) div.d-flex').length, 1, 'There should be only one line');
        // quantity = 1
        assert.strictEqual($section.find('div:eq(2) div:eq(0) span:eq(0)').text().trim(), '1', 'The line should contain only one product');
        // buttons to remove and to add product
        assert.strictEqual($section.find('.o_remove_product').length, 1, 'There should be a remove product button');
        assert.strictEqual($section.find('.o_add_product').length, 1, 'There should be a add product button');

        $section = $(lunchKanban.$('.o_lunch_widget_info')[2]);
        // total
        assert.strictEqual($section.find('div:eq(0) div:eq(1)').text().trim(), '7.40', 'total should be of 7.40');
        // order now button
        assert.strictEqual($section.find('button').length, 1, 'order now button should be available');

        lunchKanban.destroy();
    });

    QUnit.test('User interactions', function (assert) {
        assert.expect(9);

        var state = 'new';

        var lunchKanban = createView({
            View: LunchKanbanView,
            model: 'product',
            data: this.data,
            arch: '<kanban><templates><t t-name="kanban-box">' +
                    '<div>' +
                    '</div>' +
                '</t></templates></kanban>',
            mockRPC: function(route, args) {
                if (route === '/lunch/infos') {
                    return $.when({
                        order: 1,
                        wallet: 20,
                        username: 'Marc Demo',
                        userimage: '',
                        is_manager: false,
                        users: [
                            {id: 1, name: 'Mitchell Admin'},
                            {id: 2, name: 'Marc Demo'},
                        ],
                        total: 7.4,
                        raw_state: state,
                        state: 'New',
                        lines: [
                            {id: 1, product: ['Pizza Italiana', 7.4], toppings: [], quantity: 1.0, price: 7.4}
                        ],
                        alerts: [],
                        locations: ['hello', 'hallo'],
                        user_location: [1, 'hello'],
                    });
                } else if (route === '/lunch/payment_message') {
                    return $.when({message: 'Hello'});
                } else if (route === '/lunch/pay') {
                    return $.when(true);
                } else if (route === '/lunch/user_location_get') {
                    return $.when(1);
                } else if (args.method === 'update_quantity') {
                    assert.step(args.args);
                    return $.when();
                } else if (route === '/web/dataset/call_kw/ir.model.data/xmlid_to_res_id') {
                    return $.when();
                } else if (route.startsWith('data:image/png;base64,')) {
                    return $.when();
                }
                return this._super(route, args);
            },
        });

        lunchKanban.$('.o_add_product').click();
        lunchKanban.$('.o_remove_product').click();

        state = 'ordered';
        lunchKanban.$('.o_lunch_widget_order_button').click();
        // state is shown
        assert.strictEqual(lunchKanban.$('.o_lunch_ordered').length, 1, 'state should be shown as ordered');
        // buttons
        assert.strictEqual(lunchKanban.$('.o_remove_product').length, 1, 'button to remove product should be shown');
        assert.strictEqual(lunchKanban.$('.o_add_product').length, 1, 'button to add product should be shown');
        state = 'confirmed';
        lunchKanban.reload();
        // state is updated
        assert.strictEqual(lunchKanban.$('.o_lunch_confirmed').length, 1, 'state should be shown as confirmed');
        // Buttons not shown anymore
        assert.strictEqual(lunchKanban.$('.o_remove_product').length, 0, 'button to remove product should not be shown');
        assert.strictEqual(lunchKanban.$('.o_add_product').length, 0, 'button to add product should not be shown');


        assert.verifySteps([
            [[1], 1],
            [[1], -1],
        ]);

        lunchKanban.destroy();
    });

    QUnit.test('Manager interactions', function (assert) {
        assert.expect(1);

        var lunchKanban = createView({
            View: LunchKanbanView,
            model: 'product',
            data: this.data,
            arch: '<kanban><templates><t t-name="kanban-box">' +
                    '<div>' +
                    '</div>' +
                '</t></templates></kanban>',
            mockRPC: function(route, args) {
                if (route === '/lunch/infos') {
                    return $.when({
                        order: 1,
                        wallet: 20,
                        username: 'Marc Demo',
                        userimage: '',
                        is_manager: true,
                        users: [
                            {id: 1, name: 'Mitchell Admin'},
                            {id: 2, name: 'Marc Demo'},
                        ],
                        total: 7.4,
                        raw_state: 'new',
                        state: 'New',
                        lines: [
                            {id: 1, product: ['Pizza Italiana', 7.4], toppings: [], quantity: 1.0, price: 7.4}
                        ],
                        alerts: [],
                        locations: ['hello', 'hallo'],
                        user_location: [1, 'hello'],
                    });
                } else if (route === '/lunch/user_location_get') {
                    return $.when(1);
                } else if (route === '/web/dataset/call_kw/ir.model.data/xmlid_to_res_id') {
                    return $.when();
                } else if (route.startsWith('data:image/png;base64,')) {
                    return $.when();
                }
                return this._super(route, args);
            },
        });

        var select = lunchKanban.$('div.o_lunch_user_field div.o_field_widget.o_field_many2one');

        assert.strictEqual(select.length, 1, 'There should be a user selection field');

        lunchKanban.destroy();
    });
});

});
