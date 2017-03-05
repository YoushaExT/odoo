(function() {
"use strict";

/**
 * QUnit Config
 *
 * The Odoo javascript test framework is based on QUnit (http://qunitjs.com/).
 * This file is necessary to setup Qunit and to prepare its interactions with
 * Odoo.  It has to be loaded before any tests are defined.
 *
 * Note that it is not an Odoo module, because we want this code to be executed
 * as soon as possible, not whenever the Odoo module system feels like it.
 */


/**
 * This configuration variable is not strictly necessary, but it ensures more
 * safety for asynchronous tests.  With it, each test has to explicitely tell
 * QUnit how many assertion it expects, otherwise the test will fail.
 */
QUnit.config.requireExpects = true;

/**
 * not important in normal mode, but in debug=assets, the files are loaded
 * asynchroneously, which can lead to various issues with QUnit... Notice that
 * this is done outside of odoo modules, otherwise the setting would not take
 * effect on time.
 */
QUnit.config.autostart = false;

/**
 * A test timeout of 1 min, before an async test is considered failed.
 */
QUnit.config.testTimeout = 1 * 60 * 1000;


var sortButtonAppended = false;

/**
 * This is the way the testing framework knows that tests passed or failed. It
 * only look in the phantomJS console and check if there is a ok or an error.
 *
 * Someday, we should devise a safer strategy...
 */
QUnit.done(function(result) {
    if (!result.failed) {
        console.log('ok');
    } else {
        console.log('error');
    }

    if (!sortButtonAppended) {
        _addSortButton();
    }
});

/**
 * This logs various data in the console, which will be available in the log
 * .txt file generated by the runbot.
 */
QUnit.log(function( result) {
    if (!result.result) {
        console.log('"' + result.name + '"',
                    'in section', '"' + result.module + '"',
                    'failed:', result.message);
    }
});

/**
 * This is done mostly for the .txt log file generated by the runbot.
 */
QUnit.moduleDone(function(result) {
    if (!result.failed) {
        console.log('"' + result.name + '"', "passed", result.total, "tests.");
    } else {
        console.log('"' + result.name + '"',
                    "failed:", result.failed,
                    "tests out of", result.total, ".");
    }

});

/**
 * Add a sort button on top of the QUnit result page, so we can see which tests
 * take the most time.
 */
function _addSortButton() {
    sortButtonAppended = true;
    var $sort = $('<label> sort by time (desc)</label>').css({float: 'right'});
    $('h2#qunit-userAgent').append($sort);
    $sort.click(function() {
        var $ol = $('ol#qunit-tests');
        var $results = $ol.children('li').get();
        $results.sort(function (a, b) {
            var timeA = Number($(a).find('span.runtime').first().text().split(" ")[0]);
            var timeB = Number($(b).find('span.runtime').first().text().split(" ")[0]);
            if (timeA < timeB) {
                return 1;
            } else if (timeA > timeB) {
                return -1;
            } else {
                return 0;
            }
        });
        $.each($results, function(idx, $itm) { $ol.append($itm); });

    });
}

})();
