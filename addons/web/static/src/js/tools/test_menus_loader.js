odoo.define('web.clickEverywhere', function (require) {
    "use strict";
    var ajax = require('web.ajax');
    function startClickEverywhere(menu_id, appsMenusOnly) {
        ajax.loadJS('web/static/src/js/tools/test_menus.js').then(
            function() {
                clickEverywhere(menu_id, appsMenusOnly);
            }
        );
    }
    return startClickEverywhere;
});
