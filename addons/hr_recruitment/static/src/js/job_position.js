odoo.define('hr_recruitment.hr_recruitment', function(require) {
"use strict";

var KanbanRecord = require('web.KanbanRecord');

KanbanRecord.include({
    on_card_clicked: function() {
        if (this.modelName === 'hr.job') {
            this.$('.oe_applications a').first().click();
        } else {
            this._super.apply(this, arguments);
        }
    },
});

});
