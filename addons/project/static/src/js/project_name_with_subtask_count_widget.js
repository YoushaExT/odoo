odoo.define('project.name_with_subtask_count', function (require) {
    "use strict";

    const fieldRegistry = require('web.field_registry');
    const FieldChar = require('web.basic_fields').FieldChar;

    const FieldNameWithSubTaskCount = FieldChar.extend({
        /**
         * @override
         */
        init() {
            this._super(...arguments);
            if (this.viewType === 'kanban') {
                // remove click event handler
                const {click, ...events} = this.events;
                this.events = events;
            }
        },

        /**
         * @override
         */
        _render() {
            let result = this._super.apply(this, arguments);
            if (this.recordData.child_text) {
                this.$el.append($('<span>')
                        .addClass("text-muted ml-2")
                        .text(this.recordData.child_text)
                        .css('font-weight', 'normal'));
            }
            return result;
        }
    });

    fieldRegistry.add('name_with_subtask_count', FieldNameWithSubTaskCount);

    return FieldNameWithSubTaskCount;
});
