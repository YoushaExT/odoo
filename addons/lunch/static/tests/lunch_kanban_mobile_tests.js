odoo.define('lunch.lunchKanbanMobileTests', function (require) {
"use strict";

const LunchKanbanView = require('lunch.LunchKanbanView');

const testUtils = require('web.test_utils');
const {createLunchKanbanView, mockLunchRPC} = require('lunch.test_utils');

QUnit.module('Views');

QUnit.module('LunchKanbanView Mobile', {
    beforeEach() {
        const PORTAL_GROUP_ID = 1234;

        this.data = {
            'product': {
                fields: {
                    is_available_at: {string: 'Product Availability', type: 'many2one', relation: 'lunch.location'},
                    category_id: {string: 'Product Category', type: 'many2one', relation: 'lunch.product.category'},
                    supplier_id: {string: 'Vendor', type: 'many2one', relation: 'lunch.supplier'},
                },
                records: [
                    {id: 1, name: 'Tuna sandwich', is_available_at: 1},
                ],
            },
            'lunch.order': {
                fields: {},
                update_quantity() {
                    return $.when();
                },
            },
            'ir.model.data': {
                fields: {},
                xmlid_to_res_id() {
                    return $.when(PORTAL_GROUP_ID);
                },
            },
            'lunch.location': {
                fields: {
                    name: {string: 'Name', type: 'char'},
                },
                records: [
                    {id: 1, name: "Office 1"},
                    {id: 2, name: "Office 2"},
                ],
            },
        };
        this.regularInfos = {
            user_location: [2, "Office 2"],
        };
    },
}, function () {
    QUnit.test('basic rendering', function (assert) {
        assert.expect(9);

        const kanban = createLunchKanbanView({
            View: LunchKanbanView,
            model: 'product',
            data: this.data,
            arch: `
                <kanban>
                    <templates>
                        <t t-name="kanban-box">
                            <div><field name="name"/></div>
                        </t>
                    </templates>
                </kanban>
            `,
            mockRPC: mockLunchRPC({
                infos: this.regularInfos,
                userLocation: this.data['lunch.location'].records[0].id,
            }),
        });

        assert.containsOnce(kanban, '.o_kanban_view .o_kanban_record:not(.o_kanban_ghost)',
            "should have 1 records in the renderer");

        // check view layout
        assert.containsOnce(kanban, '.o_content > div',
            "should have 1 column");
        assert.containsNone(kanban, '.o_content > div.o_search_panel',
            "shouldn't have a 'lunch filters' column");
        assert.containsOnce(kanban, '.o_content > .o_lunch_kanban',
            "should have a 'kanban lunch wrapper' column");
        assert.containsOnce(kanban, '.o_lunch_kanban > .o_kanban_view',
            "should have a 'classical kanban view' column");
        assert.hasClass(kanban.$('.o_kanban_view'), 'o_lunch_kanban_view',
            "should have classname 'o_lunch_kanban_view'");
        assert.containsOnce($('.o_lunch_kanban'), '> details',
            "should have a 'lunch kanban' details/summary discolure panel");
        assert.hasClass($('.o_lunch_kanban > details'), 'fixed-bottom',
            "should have classname 'fixed-bottom'");
        assert.isNotVisible($('.o_lunch_kanban > details .o_lunch_kanban_banner'),
            "shouldn't have a visible 'lunch kanban' banner");

        kanban.destroy();
    });

    QUnit.module('LunchKanbanWidget', function () {
        QUnit.test('toggle', function (assert) {
            assert.expect(6);

            const kanban = createLunchKanbanView({
                View: LunchKanbanView,
                model: 'product',
                data: this.data,
                arch: `
                    <kanban>
                        <templates>
                            <t t-name="kanban-box">
                                <div><field name="name"/></div>
                            </t>
                        </templates>
                    </kanban>
                `,
                mockRPC: mockLunchRPC({
                    infos: Object.assign({}, this.regularInfos, {
                        total: "3.00",
                    }),
                    userLocation: this.data['lunch.location'].records[0].id,
                }),
            });

            const $details = $('.o_lunch_kanban > details');
            assert.isNotVisible($details.find('.o_lunch_kanban_banner'),
                "shouldn't have a visible 'lunch kanban' banner");
            assert.isVisible($details.find('> summary'),
                "should hava a visible cart toggle button");
            assert.containsOnce($details, '> summary:contains(Your cart)',
                "should have 'Your cart' in the button text");
            assert.containsOnce($details, '> summary:contains(3.00)',
                "should have '3.00' in the button text");

            testUtils.dom.click($details.find('> summary'));
            assert.isVisible($details.find('.o_lunch_kanban_banner'),
                "should have a visible 'lunch kanban' banner");

            testUtils.dom.click($details.find('> summary'));
            assert.isNotVisible($details.find('.o_lunch_kanban_banner'),
                "shouldn't have a visible 'lunch kanban' banner");

            kanban.destroy();
        });

        QUnit.test('keep open when adding quantities', function (assert) {
            assert.expect(6);

            const kanban = createLunchKanbanView({
                View: LunchKanbanView,
                model: 'product',
                data: this.data,
                arch: `
                    <kanban>
                        <templates>
                            <t t-name="kanban-box">
                                <div><field name="name"/></div>
                            </t>
                        </templates>
                    </kanban>
                `,
                mockRPC: mockLunchRPC({
                    infos: Object.assign({}, this.regularInfos, {
                        lines: [
                            {
                                id: 6,
                                product: [1, "Tuna sandwich", "3.00"],
                                toppings: [],
                                quantity: 1.0,
                            },
                        ],
                    }),
                    userLocation: this.data['lunch.location'].records[0].id,
                }),
            });

            const $details = $('.o_lunch_kanban > details');
            assert.isNotVisible($details.find('.o_lunch_kanban_banner'),
                "shouldn't have a visible 'lunch kanban' banner");
            assert.isVisible($details.find('> summary'),
                "should hava a visible cart toggle button");

            testUtils.dom.click($details.find('> summary'));
            assert.isVisible($details.find('.o_lunch_kanban_banner'),
                "should have a visible 'lunch kanban' banner");

            const $widgetSecondColumn = kanban.$('.o_lunch_widget .o_lunch_widget_info:eq(1)');

            assert.containsOnce($widgetSecondColumn, '.o_lunch_widget_lines > li',
                "should have 1 order line");

            let $firstLine = $widgetSecondColumn.find('.o_lunch_widget_lines > li:first');

            testUtils.dom.click($firstLine.find('button.o_add_product'));
            assert.isVisible($('.o_lunch_kanban > details .o_lunch_kanban_banner'),
                "add quantity should keep 'lunch kanban' banner open");

            $firstLine = kanban.$('.o_lunch_widget .o_lunch_widget_info:eq(1) .o_lunch_widget_lines > li:first');

            testUtils.dom.click($firstLine.find('button.o_remove_product'));
            assert.isVisible($('.o_lunch_kanban > details .o_lunch_kanban_banner'),
                "remove quantity should keep 'lunch kanban' banner open");

            kanban.destroy();
        });
    });
});

});
