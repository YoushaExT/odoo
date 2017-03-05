odoo.define('web_tour.DebugManager', function (require) {
"use strict";

var core = require("web.core");
var DebugManager = require('web.DebugManager');
var Dialog = require("web.Dialog");

var tour = require('web_tour.tour');

function get_active_tours () {
    return _.difference(_.keys(tour.tours), tour.consumed_tours);
}

DebugManager.include({
    start: function () {
        this.consume_tours_enabled = get_active_tours().length > 0;
        return this._super.apply(this, arguments);
    },
    consume_tours: function () {
        var active_tours = get_active_tours();
        if (active_tours.length > 0) { // tours might have been consumed meanwhile
            this.rpc('web_tour.tour', 'consume')
                .args([active_tours])
                .exec()
                .then(function () {
                    window.location.reload();
                });
        }
    },
    start_tour: function() {
        var dialog = new Dialog(this, {
            title: 'Tours',
            $content: core.qweb.render('WebClient.DebugManager.ToursDialog', {
                tours: tour.tours
            }),
        }).open();

        dialog.$('.o_start_tour').on('click', function(e) {
            e.preventDefault();
            tour.run($(e.target).data('name'));
        });
    },
});

});
