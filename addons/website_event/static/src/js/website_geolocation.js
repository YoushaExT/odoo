odoo.define('website_event.geolocation', function (require) {
"use strict";

var animation = require('web_editor.snippets.animation');

animation.registry.visitor = animation.Class.extend({
    selector: ".oe_country_events",
    start: function () {
        $.post( "/event/get_country_event_list", function( data ) {
            if(data){
                $( ".country_events_list" ).replaceWith( data );
            }
        });
    }
});

});