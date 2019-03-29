odoo.define('event.event_configurator_tour', function (require) {
"use strict";

var tour = require('web_tour.tour');

tour.register('event_configurator_tour', {
    url: "/web",
    test: true,
}, [tour.STEPS.SHOW_APPS_MENU_ITEM, {
    trigger: '.o_app[data-menu-xmlid="sale.sale_menu_root"]',
    edition: 'community'
}, {
    trigger: '.o_app[data-menu-xmlid="sale.sale_menu_root"]',
    edition: 'enterprise'
}, {
    trigger: ".o_list_button_add",
    extra_trigger: ".o_sale_order"
}, {
    trigger: "a:contains('Add a product')"
}, {
    trigger: 'div[name="product_id"] input',
    run: function (){
        var $input = $('div[name="product_id"] input');
        $input.click();
        $input.val('EVENT');
        // fake keydown to trigger search
        var keyDownEvent = jQuery.Event("keydown");
        keyDownEvent.which = 42;
        $input.trigger(keyDownEvent);
    },
    id: 'product_selection_step'
}, {
    trigger: 'ul.ui-autocomplete a:contains("EVENT")',
    run: 'click'
}, {
    trigger: 'div[name="event_id"] input',
    run: 'click'
}, {
    trigger: 'ul.ui-autocomplete a:contains("Design")',
    run: 'click',
    in_modal: false
}, {
    trigger: 'div[name="event_ticket_id"] input',
    run: 'click'
}, {
    trigger: 'ul.ui-autocomplete a:contains("VIP")',
    run: 'click',
    in_modal: false
}, {
    trigger: '.o_event_sale_js_event_configurator_ok'
}, {
    trigger: 'textarea[name="name"]',
    run: function () {
        var $textarea = $('textarea[name="name"]');
        if ($textarea.val().includes('Design Fair Los Angeles') && $textarea.val().includes('VIP')){
            $textarea.addClass('tour_success');
        }
    }
}, {
    trigger: 'textarea[name="name"].tour_success',
    run: function () {} // check
}, {
    trigger: 'ul.nav a:contains("Order Lines")',
    run: 'click'
}, {
    trigger: 'td:contains("EVENT")',
    run: 'click'
}, {
    trigger: '.o_event_sale_js_event_configurator_edit'
}, {
    trigger: 'div[name="event_ticket_id"] input',
    run: 'click'
}, {
    trigger: 'ul.ui-autocomplete a:contains("Standard")',
    run: 'click',
    in_modal: false
}, {
    trigger: '.o_event_sale_js_event_configurator_ok'
}, {
    trigger: 'textarea[name="name"]',
    run: function () {
        var $textarea = $('textarea[name="name"]');
        if ($textarea.val().includes('Standard')){
            $textarea.addClass('tour_success_2');
        }
    }
}, {
    trigger: 'textarea[name="name"].tour_success_2',
    run: function () {} // check
}]);

});
