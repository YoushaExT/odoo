odoo.define('pos_restaurant.tour.TipScreenTourMethods', function (require) {
    'use strict';

    const { createTourMethods } = require('point_of_sale.tour.utils');

    class Do {
        clickPercentTip(percent) {
            return [
                {
                    trigger: `.tip-screen .percentage:contains("${percent}")`,
                },
            ];
        }
        setCustomTip(amount) {
            return [
                {
                    trigger: `.tip-screen .custom-amount-form input`,
                    run: `text ${amount}`,
                },
            ];
        }
    }

    class Check {
        isShown() {
            return [
                {
                    trigger: '.pos .tip-screen',
                    run: () => {},
                },
            ];
        }
        totalAmountIs(amount) {
            return [
                {
                    trigger: `.tip-screen .total-amount:contains("${amount}")`,
                    run: () => {},
                },
            ];
        }
        percentAmountIs(percent, amount) {
            return [
                {
                    trigger: `.tip-screen .percentage:contains("${percent}") ~ .amount:contains("${amount}")`,
                    run: () => {},
                },
            ];
        }
        inputAmountIs(amount) {
            return [
                {
                    trigger: `.tip-screen .custom-amount-form input`,
                    run: function() {
                        if (this.$anchor.val().indexOf(amount) === -1) {
                            throw new Error(`".tip-screen .custom-amount-form input" element does not contain ${amount}.`)
                        };
                    },
                }
            ]
        }
    }

    return createTourMethods('TipScreen', Do, Check);
});
