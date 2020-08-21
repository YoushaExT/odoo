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

/**
 * Hide passed tests by default in the QUnit page
 */
QUnit.config.hidepassed = (window.location.href.match(/[?&]testId=/) === null);

var sortButtonAppended = false;

/**
 * If we want to log several errors, we have to log all of them at once, as
 * browser_js is closed as soon as an error is logged.
 */
const errorMessages = [];
/**
 * List of elements tolerated in the body after a test. The property "keep"
 * prevents the element from being removed (typically: qunit suite elements).
 */
const validElements = [
    // always in the body:
    { tagName: 'DIV', attr: 'id', value: 'qunit', keep: true },
    { tagName: 'DIV', attr: 'id', value: 'qunit-fixture', keep: true },
    // shouldn't be in the body after a test but are tolerated:
    { tagName: 'SCRIPT', attr: 'id', value: '' },
    { tagName: 'DIV', attr: 'className', value: 'o_notification_manager' },
    { tagName: 'DIV', attr: 'className', value: 'tooltip fade bs-tooltip-auto' },
    { tagName: 'DIV', attr: 'className', value: 'tooltip fade bs-tooltip-auto show' },
    { tagName: 'SPAN', attr: 'className', value: 'select2-hidden-accessible' },
    // Due to a Document Kanban bug (already present in 12.0)
    { tagName: 'DIV', attr: 'className', value: 'ui-helper-hidden-accessible' },
    { tagName: 'UL', attr: 'className', value: 'ui-menu ui-widget ui-widget-content ui-autocomplete ui-front' },
];

/**
 * Waits for the module system to end processing the JS modules, so that we can
 * make the suite fail if some modules couldn't be loaded (e.g. because of a
 * missing dependency).
 *
 * @returns {Promise<boolean>}
 */
async function checkModules() {
    // do not mark the suite as successful already, as we still need to ensure
    // that all modules have been correctly loaded
    $('#qunit-banner').removeClass('qunit-pass');
    const $modulesAlert = $('<div>')
        .addClass('alert alert-info')
        .text('Waiting for modules check...');
    $modulesAlert.appendTo('#qunit');

    // wait for the module system to end processing the JS modules
    await odoo.__DEBUG__.didLogInfo;

    const info = odoo.__DEBUG__.jsModules;
    if (info.missing.length || info.failed.length) {
        $('#qunit-banner').addClass('qunit-fail');
        $modulesAlert.toggleClass('alert-info alert-danger');
        const failingModules = info.missing.concat(info.failed);
        const error = `Some modules couldn't be started: ${failingModules.join(', ')}.`;
        $modulesAlert.text(error);
        errorMessages.unshift(error);
        return false;
    } else {
        $modulesAlert.toggleClass('alert-info alert-success');
        $modulesAlert.text('All modules have been correctly loaded.');
        $('#qunit-banner').addClass('qunit-pass');
        return true;
    }
}

/**
 * This is the way the testing framework knows that tests passed or failed. It
 * only look in the phantomJS console and check if there is a ok or an error.
 *
 * Someday, we should devise a safer strategy...
 */
QUnit.done(async function (result) {
    const allModulesLoaded = await checkModules();
    if (result.failed) {
        errorMessages.push(`${result.failed} / ${result.total} tests failed.`);
    }
    if (!result.failed && allModulesLoaded) {
        console.log('test successful');
    } else {
        console.error(errorMessages.join('\n'));
    }

    if (!sortButtonAppended) {
        _addSortButton();
    }
});

/**
 * This logs various data in the console, which will be available in the log
 * .txt file generated by the runbot.
 */
QUnit.log(function (result) {
    if (!result.result) {
        var info = '"QUnit test failed: "' + result.module + ' > ' + result.name + '"';
        info += ' [message: "' + result.message + '"';
        if (result.actual !== null) {
            info += ', actual: "' + result.actual + '"';
        }
        if (result.expected !== null) {
            info += ', expected: "' + result.expected + '"';
        }
        info += ']';
        errorMessages.push(info);
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
                    "failed", result.failed,
                    "tests out of", result.total, ".");
    }

});

/**
 * After each test, we check that there is no leftover in the DOM.
 *
 * Note: this event is not QUnit standard, we added it for this specific use case.
 */
QUnit.on('OdooAfterTestHook', function () {
    const toRemove = [];
    // check for leftover elements in the body
    for (const bodyChild of document.body.children) {
        const tolerated = validElements.find((e) =>
            e.tagName === bodyChild.tagName && bodyChild[e.attr] === e.value
        );
        if (!tolerated) {
            console.error('Body still contains undesirable elements:' +
                '\nInvalid element:\n' + bodyChild.outerHTML +
                '\nBody HTML: \n' + $('body').html());
            QUnit.pushFailure(`Body still contains undesirable elements`);
        }
        if (!tolerated || !tolerated.keep) {
            toRemove.push(bodyChild);
        }
    }

    // check for leftovers in #qunit-fixture
    const qunitFixture = document.getElementById('qunit-fixture');
    if (qunitFixture.children.length) {
        // console.error('#qunit-fixture still contains elements:' +
        //     '\n#qunit-fixture HTML:\n' + qunitFixture.outerHTML);
        // QUnit.pushFailure(`#qunit-fixture still contains elements`);
        toRemove.push(...qunitFixture.children);
    }

    // remove unwanted elements if not in debug
    if (!document.body.classList.contains('debug')) {
        for (const el of toRemove) {
            el.remove();
        }
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

/**
 * We add here a 'fail fast' feature: we often want to stop the test suite after
 * the first failed test.  This is also useful for the runbot test suites.
 */

QUnit.config.urlConfig.push({
  id: "failfast",
  label: "Fail Fast",
  tooltip: "Stop the test suite immediately after the first failed test."
});

QUnit.begin(function() {
    if (QUnit.config.failfast) {
        QUnit.testDone(function(details) {
            if (details.failed > 0) {
                QUnit.config.queue.length = 0;
            }
        });
    }
});

})();
