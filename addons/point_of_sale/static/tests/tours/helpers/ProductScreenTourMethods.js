odoo.define('point_of_sale.tour.ProductScreenTourMethods', function (require) {
    'use strict';

    const { createTourMethods } = require('point_of_sale.tour.utils');

    class Do {
        clickDisplayedProduct(name) {
            return [
                {
                    content: `click product '${name}'`,
                    trigger: `.product-list .product-name:contains("${name}")`,
                },
            ];
        }

        clickOrderline(name, quantity) {
            return [
                {
                    content: `selecting orderline with product '${name}' and quantity '${quantity}'`,
                    trigger: `.order .orderline:not(:has(.selected)) .product-name:contains("${name}") ~ .info-list em:contains("${quantity}")`,
                },
                {
                    content: `orderline with product '${name}' and quantity '${quantity}' has been selected`,
                    trigger: `.order .orderline.selected .product-name:contains("${name}") ~ .info-list em:contains("${quantity}")`,
                    run: () => {},
                },
            ];
        }

        clickSubcategory(name) {
            return [
                {
                    content: `selecting '${name}' subcategory`,
                    trigger: `.products-widget > .products-widget-control .category-simple-button:contains("${name}")`,
                },
                {
                    content: `'${name}' subcategory selected`,
                    trigger: `.breadcrumbs .breadcrumb-button:contains("${name}")`,
                    run: () => {},
                },
            ];
        }

        clickHomeCategory() {
            return [
                {
                    content: `click Home subcategory`,
                    trigger: `.breadcrumbs .breadcrumb-home`,
                },
            ];
        }

        /**
         * Press the numpad in sequence based on the given space-separated keys.
         * NOTE: Maximum of 2 characters because NumberBuffer only allows 2 consecutive
         * fast inputs. Fast inputs is the case in tours.
         *
         * @param {String} keys space-separated numpad keys
         */
        pressNumpad(keys) {
            const numberChars = '. 0 1 2 3 4 5 6 7 8 9'.split(' ');
            const modeButtons = 'Qty Price Disc'.split(' ');
            function generateStep(key) {
                let trigger;
                if (numberChars.includes(key)) {
                    trigger = `.numpad .number-char:contains("${key}")`;
                } else if (modeButtons.includes(key)) {
                    trigger = `.numpad .mode-button:contains("${key}")`;
                } else if (key === 'Backspace') {
                    trigger = `.numpad .numpad-backspace`;
                } else if (key === '+/-') {
                    trigger = `.numpad .numpad-minus`;
                }
                return {
                    content: `'${key}' pressed in product screen numpad`,
                    trigger,
                };
            }
            return keys.split(' ').map(generateStep);
        }

        clickPayButton() {
            return [
                { content: 'click pay button', trigger: '.actionpad .button.pay' },
                {
                    content: 'now in payment screen',
                    trigger: '.pos-content .payment-screen',
                    run: () => {},
                },
            ];
        }

        clickCustomerButton() {
            return [
                { content: 'click customer button', trigger: '.actionpad .button.set-customer' },
                {
                    content: 'customer screen is shown',
                    trigger: '.pos-content .clientlist-screen',
                    run: () => {},
                },
            ];
        }

        clickCustomer(name) {
            return [
                {
                    content: `select customer '${name}'`,
                    trigger: `.clientlist-screen .client-line td:contains("${name}")`,
                },
                {
                    content: `client line '${name}' is highlighted`,
                    trigger: `.clientlist-screen .client-line.highlight td:contains("${name}")`,
                    run: () => {},
                },
            ];
        }

        clickSetCustomer() {
            return [
                {
                    content: 'click set customer',
                    trigger: '.clientlist-screen .button.next.highlight',
                },
            ];
        }
    }

    class Check {
        isShown() {
            return [
                {
                    content: 'product screen is shown',
                    trigger: '.product-screen:not(:has(.oe_hidden))',
                    run: () => {},
                },
            ];
        }
        selectedOrderlineHas(name, quantity, price) {
            const res = [
                {
                    // check first if the order widget is there and has orderlines
                    content: 'order widget has orderlines',
                    trigger: '.order .orderlines',
                    run: () => {},
                },
                {
                    content: `'${name}' is selected`,
                    trigger: `.order .orderline.selected .product-name:contains("${name}")`,
                    run: function () {}, // it's a check
                },
            ];
            if (quantity) {
                res.push({
                    content: `selected line has ${quantity} quantity`,
                    trigger: `.order .orderline.selected .product-name:contains("${name}") ~ .info-list em:contains("${quantity}")`,
                    run: function () {}, // it's a check
                });
            }
            if (price) {
                res.push({
                    content: `selected line has total price of ${price}`,
                    trigger: `.order .orderline.selected .product-name:contains("${name}") ~ .price:contains("${price}")`,
                    run: function () {}, // it's a check
                });
            }
            return res;
        }
        orderIsEmpty() {
            return [
                {
                    content: `order is empty`,
                    trigger: `.order .order-empty`,
                    run: () => {},
                },
            ];
        }

        productIsDisplayed(name) {
            return [
                {
                    content: `'${name}' should be displayed`,
                    trigger: `.product-list .product-name:contains("${name}")`,
                    run: () => {},
                },
            ];
        }
        totalAmountIs(amount) {
            return [
                {
                    content: `order total amount is '${amount}'`,
                    trigger: `.order-container .order .summary .value:contains("${amount}")`,
                    run: () => {},
                }
            ]
        }
        modeIsActive(mode) {
            return [
                {
                    content: `'${mode}' is active`,
                    trigger: `.numpad button.selected-mode:contains('${mode}')`,
                    run: function () {},
                },
            ];
        }
    }

    class Execute {
        /**
         * Create an orderline for the given `productName` and `quantity`.
         * - If `unitPrice` is provided, price of the product of the created line
         *   is changed to that value.
         * - If `expectedTotal` is provided, the created orderline (which is the currently
         *   selected orderline) is checked if it contains the correct quantity and total
         *   price.
         *
         * @param {string} productName
         * @param {string} quantity
         * @param {string} unitPrice
         * @param {string} expectedTotal
         */
        addOrderline(productName, quantity, unitPrice = undefined, expectedTotal = undefined) {
            const res = this._do.clickDisplayedProduct(productName);
            if (unitPrice) {
                res.push(...this._do.pressNumpad('Price'));
                res.push(...this._check.modeIsActive('Price'));
                res.push(...this._do.pressNumpad(unitPrice.toString().split('').join(' ')));
                res.push(...this._do.pressNumpad('Qty'));
                res.push(...this._check.modeIsActive('Qty'));
            }
            for (let char of quantity.toString()) {
                if ('.0123456789'.includes(char)) {
                    res.push(...this._do.pressNumpad(char));
                } else if ('-'.includes(char)) {
                    res.push(...this._do.pressNumpad('+/-'));
                }
            }
            if (expectedTotal) {
                res.push(...this._check.selectedOrderlineHas(productName, quantity, expectedTotal));
            } else {
                res.push(...this._check.selectedOrderlineHas(productName, quantity));
            }
            return res;
        }
        addMultiOrderlines(...list) {
            const steps = [];
            for (let [product, qty, price] of list) {
                steps.push(...this.addOrderline(product, qty, price));
            }
            return steps;
        }
    }

    return createTourMethods('ProductScreen', Do, Check, Execute);
});
