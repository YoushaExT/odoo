odoo.define('web.util_tests', function (require) {
"use strict";

var utils = require('web.utils');

QUnit.module('core', {}, function () {

    QUnit.module('utils');


    QUnit.test('intersperse', function (assert) {
        assert.expect(27);

        var intersperse = utils.intersperse;

        assert.strictEqual(intersperse("", []), "");
        assert.strictEqual(intersperse("0", []), "0");
        assert.strictEqual(intersperse("012", []), "012");
        assert.strictEqual(intersperse("1", []), "1");
        assert.strictEqual(intersperse("12", []), "12");
        assert.strictEqual(intersperse("123", []), "123");
        assert.strictEqual(intersperse("1234", []), "1234");
        assert.strictEqual(intersperse("123456789", []), "123456789");
        assert.strictEqual(intersperse("&ab%#@1", []), "&ab%#@1");

        assert.strictEqual(intersperse("0", []), "0");
        assert.strictEqual(intersperse("0", [1]), "0");
        assert.strictEqual(intersperse("0", [2]), "0");
        assert.strictEqual(intersperse("0", [200]), "0");

        assert.strictEqual(intersperse("12345678", [0], '.'), '12345678');
        assert.strictEqual(intersperse("", [1], '.'), '');
        assert.strictEqual(intersperse("12345678", [1], '.'), '1234567.8');
        assert.strictEqual(intersperse("12345678", [1], '.'), '1234567.8');
        assert.strictEqual(intersperse("12345678", [2], '.'), '123456.78');
        assert.strictEqual(intersperse("12345678", [2, 1], '.'), '12345.6.78');
        assert.strictEqual(intersperse("12345678", [2, 0], '.'), '12.34.56.78');
        assert.strictEqual(intersperse("12345678", [-1, 2], '.'), '12345678');
        assert.strictEqual(intersperse("12345678", [2, -1], '.'), '123456.78');
        assert.strictEqual(intersperse("12345678", [2, 0, 1], '.'), '12.34.56.78');
        assert.strictEqual(intersperse("12345678", [2, 0, 0], '.'), '12.34.56.78');
        assert.strictEqual(intersperse("12345678", [2, 0, -1], '.'), '12.34.56.78');
        assert.strictEqual(intersperse("12345678", [3,3,3,3], '.'), '12.345.678');
        assert.strictEqual(intersperse("12345678", [3,0], '.'), '12.345.678');
    });

    QUnit.test('is_bin_size', function (assert) {
        assert.expect(3);

        var is_bin_size = utils.is_bin_size;

        assert.strictEqual(is_bin_size('Cg=='), false);
        assert.strictEqual(is_bin_size('2.5 Mb'), true);
        // should also work for non-latin languages (e.g. russian)
        assert.strictEqual(is_bin_size('64.2 Кб'), true);
    });

    QUnit.test('unaccent', function (assert) {
        assert.expect(3);

        var singleCharacters = utils.unaccent("ⱮɀꝾƶⱵȥ");
        var doubledCharacters = utils.unaccent("ǱǄꝎꜩꝡƕ");
        var caseSensetiveCharacters = utils.unaccent("ⱮɀꝾƶⱵȥ", true);

        assert.strictEqual("mzgzhz", singleCharacters);
        assert.strictEqual("dzdzootzvyhv", doubledCharacters);
        assert.strictEqual("MzGzHz", caseSensetiveCharacters);
    });

    QUnit.test('human_number', function (assert) {
        assert.expect(26);

        var human_number = utils.human_number;

        assert.strictEqual(human_number(1020, 2, 1), '1.02k');
        assert.strictEqual(human_number(1020000, 2, 2), '1020k');
        assert.strictEqual(human_number(10200000, 2, 2), '10.2M');
        assert.strictEqual(human_number(1020, 2, 1), '1.02k');
        assert.strictEqual(human_number(1002, 2, 1), '1k');
        assert.strictEqual(human_number(101, 2, 1), '101');
        assert.strictEqual(human_number(64.2, 2, 1), '64');
        assert.strictEqual(human_number(1e+18), '1E');
        assert.strictEqual(human_number(1e+21, 2, 1), '1e+21');
        assert.strictEqual(human_number(1.0045e+22, 2, 1), '1e+22');
        assert.strictEqual(human_number(1.0045e+22, 3, 1), '1.005e+22');
        assert.strictEqual(human_number(1.012e+43, 2, 1), '1.01e+43');
        assert.strictEqual(human_number(1.012e+43, 2, 2), '1.01e+43');

        assert.strictEqual(human_number(-1020, 2, 1), '-1.02k');
        assert.strictEqual(human_number(-1020000, 2, 2), '-1020k');
        assert.strictEqual(human_number(-10200000, 2, 2), '-10.2M');
        assert.strictEqual(human_number(-1020, 2, 1), '-1.02k');
        assert.strictEqual(human_number(-1002, 2, 1), '-1k');
        assert.strictEqual(human_number(-101, 2, 1), '-101');
        assert.strictEqual(human_number(-64.2, 2, 1), '-64');
        assert.strictEqual(human_number(-1e+18), '-1E');
        assert.strictEqual(human_number(-1e+21, 2, 1), '-1e+21');
        assert.strictEqual(human_number(-1.0045e+22, 2, 1), '-1e+22');
        assert.strictEqual(human_number(-1.0045e+22, 3, 1), '-1.004e+22');
        assert.strictEqual(human_number(-1.012e+43, 2, 1), '-1.01e+43');
        assert.strictEqual(human_number(-1.012e+43, 2, 2), '-1.01e+43');
    });

    QUnit.test('patch a class with getter', function (assert) {
        assert.expect(13);

        const { patch } = utils;

        class TestClass {
            get val() {
                return 'aaa';
            }
        }

        const testInstance = new TestClass();
        assert.strictEqual(testInstance.val, 'aaa');

        // Extend `val`

        const removePatch1 = patch(TestClass, 'patch1', {
            get val() {
                return this._super + 'bbb';
            },
        });
        assert.strictEqual(testInstance.val, 'aaabbb');

        const removePatch2 = patch(TestClass, 'patch2', {
            get val() {
                return this._super + 'ccc';
            },
        });
        assert.strictEqual(testInstance.val, 'aaabbbccc');

        removePatch1();
        assert.strictEqual(testInstance.val, 'aaaccc');

        removePatch2();
        assert.strictEqual(testInstance.val, 'aaa');

        // Add getters

        const removeMorePatch1 = patch(TestClass, 'more-patch-1', {
            get realVal() {
                return `${this.wrapper.start}${this.val}${this.wrapper.end}`
            },
            get wrapper() {
                return {
                    start: '(',
                    end: ')',
                }
            }
        })
        assert.strictEqual(testInstance.realVal, '(aaa)');

        const removeMorePatch2 = patch(TestClass, 'more-patch-2', {
            get wrapper() {
                return {
                    start: `[${this._super.start}`,
                    end: `${this._super.end}]`,
                }
            }
        })
        assert.strictEqual(testInstance.realVal, '[(aaa)]');

        const removeMorePatch3 = patch(TestClass, 'more-patch-3', {
            get realVal() {
                return `${this._super} - augmented`;
            }
        })
        assert.strictEqual(testInstance.realVal, '[(aaa)] - augmented');

        removeMorePatch2();
        assert.strictEqual(testInstance.realVal, '(aaa) - augmented');

        removeMorePatch3();
        assert.strictEqual(testInstance.realVal, '(aaa)');

        removeMorePatch1();
        assert.strictEqual(testInstance.realVal, undefined);
        assert.strictEqual(testInstance.wrapper, undefined);
        assert.strictEqual(testInstance.val, 'aaa');
    });

});

});
