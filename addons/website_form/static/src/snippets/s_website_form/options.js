odoo.define('website_form_editor', function (require) {
'use strict';

const core = require('web.core');
const FormEditorRegistry = require('website_form.form_editor_registry');
const options = require('web_editor.snippets.options');

const qweb = core.qweb;
const _t = core._t;

const FormEditor = options.Class.extend({
    xmlDependencies: ['/website_form/static/src/xml/website_form_editor.xml'],

    //----------------------------------------------------------------------
    // Private
    //----------------------------------------------------------------------

    /**
     * Returns a promise which is resolved once the records of the field
     * have been retrieved.
     *
     * @private
     * @param {Object} field
     * @returns {Promise<Object>}
     */
    _fetchFieldRecords: async function (field) {
        // Convert the required boolean to a value directly usable
        // in qweb js to avoid duplicating this in the templates
        field.required = field.required ? 1 : null;

        if (field.records) {
            return field.records;
        }
        // Set selection as records to avoid added conplexity
        if (field.type === 'selection') {
            field.records = field.selection.map(el => ({
                id: el[0],
                display_name: el[1],
            }));
        } else if (field.relation && field.relation !== 'ir.attachment') {
            field.records = await this._rpc({
                model: field.relation,
                method: 'search_read',
                args: [
                    field.domain,
                    ['display_name']
                ],
            });
        }
        return field.records;
    },
    /**
     * Returns a field object
     *
     * @private
     * @param {string} type the type of the field
     * @param {string} name The name of the field used also as label
     * @returns {Object}
     */
    _getCustomField: function (type, name) {
        return {
            name: name,
            string: name,
            custom: true,
            type: type,
            // Default values for x2many fields and selection
            records: [{
                id: _t('Option 1'),
                display_name: _t('Option 1'),
            }, {
                id: _t('Option 2'),
                display_name: _t('Option 2'),
            }, {
                id: _t('Option 3'),
                display_name: _t('Option 3'),
            }],
        };
    },
    /**
     * Returns the default formatInfos of a field.
     *
     * @private
     * @returns {Object}
     */
    _getDefaultFormat: function () {
        return {
            labelWidth: this.$target[0].querySelector('.s_website_form_label').style.width,
            labelPosition: 'left',
            multiPosition: 'horizontal',
            requiredMark: this._isRequiredMark(),
            optionalMark: this._isOptionalMark(),
            mark: this._getMark(),
        };
    },
    /**
     * @private
     * @returns {string}
     */
    _getMark: function () {
        return this.$target[0].dataset.mark;
    },
    /**
     * @private
     * @returns {boolean}
     */
    _isOptionalMark: function () {
        return this.$target[0].classList.contains('o_mark_optional');
    },
    /**
     * @private
     * @returns {boolean}
     */
    _isRequiredMark: function () {
        return this.$target[0].classList.contains('o_mark_required');
    },
    /**
     * @private
     * @param {Object} field
     * @returns {Promise<HTMLElement>}
     */
    _renderField: function (field) {
        field.id = Math.random().toString(36).substring(2, 15); // Big unique ID
        const template = document.createElement('template');
        template.innerHTML = qweb.render("website_form.field_" + field.type, {field: field}).trim();
        return template.content.firstElementChild;
    },
});

const FieldEditor = FormEditor.extend({
    /**
     * @override
     */
    init: function () {
        this._super.apply(this, arguments);
        this.formEl = this.$target[0].closest('form');
    },

    //--------------------------------------------------------------------------
    // Private
    //--------------------------------------------------------------------------

    /**
     * Returns the target as a field Object
     *
     * @private
     * @returns {Object}
     */
    _getActiveField: function () {
        let field;
        const labelText = this.$target.find('.s_website_form_label_content').text();
        if (this._isFieldCustom()) {
            field = this._getCustomField(this.$target[0].dataset.type, labelText);
        } else {
            field = Object.assign({}, this.fields[this._getFieldName()]);
            field.string = labelText;
        }
        field.records = this._getListItems();
        this._setActiveProperties(field);
        return field;
    },
    /**
     * Returns the format object of a field containing
     * the position, labelWidth and bootstrap col class
     *
     * @private
     * @returns {Object}
     */
    _getFieldFormat: function () {
        let requiredMark, optionalMark;
        const mark = this.$target[0].querySelector('.s_website_form_mark');
        if (mark) {
            requiredMark = this._isFieldRequired();
            optionalMark = !requiredMark;
        }
        const multipleInput = this._getMultipleInputs();
        const format = {
            labelPosition: this._getLabelPosition(),
            labelWidth: this.$target[0].querySelector('.s_website_form_label').style.width,
            multiPosition: multipleInput && multipleInput.dataset.display || 'horizontal',
            col: [...this.$target[0].classList].filter(el => el.match(/^col-/g)).join(' '),
            requiredMark: requiredMark,
            optionalMark: optionalMark,
            mark: mark && mark.textContent,
        };
        return format;
    },
    /**
     * Returns the name of the field
     *
     * @private
     * @returns {string}
     */
    _getFieldName: function () {
        const multipleName = this.$target[0].querySelector('.s_website_form_multiple');
        return multipleName ? multipleName.dataset.name : this.$target[0].querySelector('.s_website_form_input').name;
    },
    /**
     * Returns the type of the  field, can be used for both custom and existing fields
     *
     * @private
     * @returns {string}
     */
    _getFieldType: function () {
        return this.$target[0].dataset.type;
    },
    /**
     * @private
     * @returns {string}
     */
    _getLabelPosition: function () {
        const label = this.$target[0].querySelector('.s_website_form_label');
        if (this.$target[0].querySelector('.row:not(.s_website_form_multiple)')) {
            return label.classList.contains('text-right') ? 'right' : 'left';
        } else {
            return label.classList.contains('d-none') ? 'none' : 'top';
        }
    },
    /**
     * Returns the multiple checkbox/radio element if it exist else null
     *
     * @private
     * @returns {HTMLElement}
     */
    _getMultipleInputs: function () {
        return this.$target[0].querySelector('.s_website_form_multiple');
    },
    /**
     * @private
     * @returns {string}
     */
    _getPlaceholder: function () {
        const input = this._getPlaceholderInput();
        return input ? input.placeholder : '';
    },
    /**
     * Returns the field's input if it is placeholder compatible, else null
     *
     * @private
     * @returns {HTMLElement}
     */
    _getPlaceholderInput: function () {
        return this.$target[0].querySelector('input[type="text"], input[type="email"], input[type="number"] , textarea');
    },
    /**
     * Returns true if the field is a custom field, false if it is an existing field
     *
     * @private
     * @returns {boolean}
     */
    _isFieldCustom: function () {
        return !!this.$target[0].classList.contains('s_website_form_custom');
    },
    /**
     * Returns true if the field is required by the model or by the user.
     *
     * @private
     * @returns {boolean}
     */
    _isFieldRequired: function () {
        const classList = this.$target[0].classList;
        return classList.contains('s_website_form_required') || classList.contains('s_website_form_model_required');
    },
    /**
     * Set the active field properties on the field Object
     *
     * @param {Object} field Field to complete with the active field info
     */
    _setActiveProperties(field) {
        const classList = this.$target[0].classList;
        const textarea = this.$target[0].querySelector('textarea');
        field.placeholder = this._getPlaceholder();
        field.rows = textarea && textarea.rows;
        field.required = classList.contains('s_website_form_required');
        field.modelRequired = classList.contains('s_website_form_model_required');
        field.hidden = classList.contains('s_website_form_field_hidden');
        field.formatInfo = this._getFieldFormat();
    },
    /**
     * Set the placeholder on the current field if the input allow it
     *
     * @private
     * @param {string} value
     */
    _setPlaceholder: function (value) {
        const input = this._getPlaceholderInput();
        if (input) {
            input.placeholder = value;
        }
    },
});

options.registry.WebsiteFormEditor = FormEditor.extend({
    events: _.extend({}, options.Class.prototype.events || {}, {
        'click .toggle-edit-message': '_onToggleEndMessageClick',
    }),

    /**
     * @override
     */
    willStart: async function () {
        const _super = this._super.bind(this);

        // Hide change form parameters option for forms
        // e.g. User should not be enable to change existing job application form
        // to opportunity form in 'Apply job' page.
        this.modelCantChange = this.$target.attr('hide-change-model') !== undefined;
        if (this.modelCantChange) {
            return _super(...arguments);
        }

        // Get list of website_form compatible models.
        this.models = await this._rpc({
            model: "ir.model",
            method: "search_read",
            args: [
                [['website_form_access', '=', true]],
                ['id', 'model', 'name', 'website_form_label', 'website_form_key']
            ],
        });

        const targetModelName = this.$target[0].dataset.model_name || 'mail.mail';
        this.activeForm = _.findWhere(this.models, {model: targetModelName});
        // Create the Form Action select
        this.selectActionEl = document.createElement('we-select');
        this.selectActionEl.setAttribute('string', 'Action');
        this.selectActionEl.dataset.noPreview = 'true';
        this.models.forEach(el => {
            const option = document.createElement('we-button');
            option.textContent = el.website_form_label;
            option.dataset.selectAction = el.id;
            this.selectActionEl.append(option);
        });

        return _super(...arguments);
    },
    /**
     * @override
     */
    start: function () {
        const proms = [this._super(...arguments)];
        // Disable text edition
        this.$target.attr('contentEditable', false);
        // Make button editable
        this.$target.find('.s_website_form_send').attr('contentEditable', true);
        // Get potential message
        this.$message = this.$target.parent().find('.s_website_form_end_message');
        this.showEndMessage = false;
        // If the form has no model it means a new snippet has been dropped.
        // Apply the default model selected in willStart on it.
        if (!this.$target[0].dataset.model_name) {
            proms.push(this._applyFormModel());
        }
        return Promise.all(proms);
    },
    /**
     * @override
     */
    cleanForSave: function () {
        const model = this.$target[0].dataset.model_name;
        // because apparently this can be called on the wrong widget and
        // we may not have a model, or fields...
        if (model) {
            // we may be re-whitelisting already whitelisted fields. Doesn't
            // really matter.
            const fields = [...this.$target[0].querySelectorAll('.s_website_form_field:not(.s_website_form_custom) .s_website_form_input')].map(el => el.name);
            if (fields.length) {
                // ideally we'd only do this if saving the form
                // succeeds... but no idea how to do that
                this._rpc({
                    model: 'ir.model.fields',
                    method: 'formbuilder_whitelist',
                    args: [model, _.uniq(fields)],
                });
            }
        }
        if (this.$message.length) {
            this.$target.removeClass('d-none');
            this.$message.addClass("d-none");
        }
    },
    /**
     * @override
     */
    updateUI: async function () {
        // If we want to rerender the xml we need to avoid the updateUI
        // as they are asynchronous and the ui might try to update while
        // we are building the UserValueWidgets.
        if (this.rerender) {
            this.rerender = false;
            await this._rerenderXML();
            return;
        }
        await this._super.apply(this, arguments);
        // End Message UI
        this.updateUIEndMessage();
    },
    /**
     * @see this.updateUI
     */
    updateUIEndMessage: function () {
        this.$target.toggleClass("d-none", this.showEndMessage);
        this.$message.toggleClass("d-none", !this.showEndMessage);
        this.$el.find(".toggle-edit-message").toggleClass('text-primary', this.showEndMessage);
    },
    /**
     * @override
     */
    notify: function (name, data) {
        this._super(...arguments);
        if (name === 'field_mark') {
            this._setLabelsMark();
        } else if (name === 'add_field') {
            const field = this._getCustomField('char', 'Custom Text');
            field.formatInfo = data.formatInfo;
            field.formatInfo.requiredMark = this._isRequiredMark();
            field.formatInfo.optionalMark = this._isOptionalMark();
            field.formatInfo.mark = this._getMark();
            const htmlField = this._renderField(field);
            data.$target.after(htmlField);
            this.trigger_up('activate_snippet', {
                $snippet: $(htmlField),
            });
        }
    },

    //--------------------------------------------------------------------------
    // Options
    //--------------------------------------------------------------------------

    /**
     * Select the value of a field (hidden) that will be used on the model as a preset.
     * ie: The Job you apply for if the form is on that job's page.
     */
    addActionField: function (previewMode, value, params) {
        const fieldName = params.fieldName;
        if (params.isSelect === 'true') {
            value = parseInt(value);
        }
        this._addHiddenField(value, fieldName);
    },
    /**
     * Changes the onSuccess event.
     */
    onSuccess: function (previewMode, value, params) {
        this.$target[0].dataset.successMode = value;
        if (value === 'message') {
            if (!this.$message.length) {
                this.$message = $(qweb.render('website_form.s_website_form_end_message'));
            }
            this.$target.after(this.$message);
        } else {
            this.showEndMessage = false;
            this.$message.remove();
        }
    },
    /**
     * Select the model to create with the form.
     */
    selectAction: async function (previewMode, value, params) {
        if (this.modelCantChange) {
            return;
        }
        await this._applyFormModel(parseInt(value));
        this.rerender = true;
    },
    /**
     * @override
     */
    selectClass: function (previewMode, value, params) {
        this._super(...arguments);
        if (params.name === 'field_mark_select') {
            this._setLabelsMark();
        }
    },
    /**
     * Set the mark string on the form
     */
    setMark: function (previewMode, value, params) {
        this.$target[0].dataset.mark = value.trim();
        this._setLabelsMark();
    },

    //--------------------------------------------------------------------------
    // Private
    //--------------------------------------------------------------------------

    /**
     * @override
     */
    _computeWidgetState: function (methodName, params) {
        switch (methodName) {
            case 'selectAction':
                return this.activeForm.id;
            case 'addActionField': {
                const value = this.$target.find(`.s_website_form_dnone input[name="${params.fieldName}"]`).val();
                if (value) {
                    return value;
                } else {
                    return params.isSelect ? '0' : '';
                }
            }
            case 'onSuccess':
                return this.$target[0].dataset.successMode;
            case 'setMark':
                return this._getMark();
        }
        return this._super(...arguments);
    },
    /**
     * @override
     */
    _renderCustomXML: function (uiFragment) {
        if (this.modelCantChange) {
            return;
        }
        // Add Action select
        const firstOption = uiFragment.querySelector(':first-child');
        uiFragment.insertBefore(this.selectActionEl.cloneNode(true), firstOption);

        // Add Action related options
        const formKey = this.activeForm.website_form_key;
        const formInfo = FormEditorRegistry.get(formKey);
        if (!formInfo || !formInfo.fields) {
            return;
        }
        const proms = formInfo.fields.map(field => this._fetchFieldRecords(field));
        return Promise.all(proms).then(() => {
            formInfo.fields.forEach(field => {
                let option;
                switch (field.type) {
                    case 'many2one':
                        option = this._buildSelect(field);
                        break;
                    case 'char':
                        option = this._buildInput(field);
                        break;
                }
                if (field.required) {
                    // Get default value or for many2one fields the first option.
                    const defaultValue = field.defaultValue || field.records[0].id;
                    this._addHiddenField(defaultValue, field.name);
                }
                uiFragment.insertBefore(option, firstOption);
            });
        });
    },
    /**
     * Add a hidden field to the form
     *
     * @private
     * @param {string} value
     * @param {string} fieldName
     */
    _addHiddenField: function (value, fieldName) {
        this.$target.find(`.s_website_form_dnone:has(input[name="${fieldName}"])`).remove();
        if (value) {
            const hiddenField = qweb.render('website_form.field_hidden', {
                field: {
                    name: fieldName,
                    value: value,
                },
            });
            this.$target.find('.s_website_form_submit').before(hiddenField);
        }
    },
    /**
     * Returns a we-input element from the field
     *
     * @private
     * @param {Object} field
     * @returns {HTMLElement}
     */
    _buildInput: function (field) {
        const inputEl = document.createElement('we-input');
        inputEl.dataset.noPreview = 'true';
        inputEl.dataset.fieldName = field.name;
        inputEl.dataset.addActionField = '';
        inputEl.setAttribute('string', field.string);
        return inputEl;
    },
    /**
     * Returns a we-select element with field's records as it's options
     *
     * @private
     * @param {Object} field
     * @return {HTMLElement}
     */
    _buildSelect: function (field) {
        const selectEl = document.createElement('we-select');
        selectEl.dataset.noPreview = 'true';
        selectEl.dataset.fieldName = field.name;
        selectEl.dataset.isSelect = 'true';
        selectEl.setAttribute('string', field.string);
        if (!field.required) {
            const noneButton = document.createElement('we-button');
            noneButton.textContent = 'None';
            noneButton.dataset.addActionField = 0;
            selectEl.append(noneButton);
        }
        field.records.forEach(el => {
            const button = document.createElement('we-button');
            button.textContent = el.display_name;
            button.dataset.addActionField = el.id;
            selectEl.append(button);
        });
        return selectEl;
    },
    /**
     * Apply the model on the form changing it's fields
     *
     * @private
     * @param {Integer} modelId
     */
    _applyFormModel: async function (modelId) {
        let oldFormInfo;
        if (modelId) {
            const oldFormKey = this.activeForm.website_form_key;
            if (oldFormKey) {
                oldFormInfo = FormEditorRegistry.get(oldFormKey);
            }
            this.$target.find('.s_website_form_field').remove();
            this.activeForm = _.findWhere(this.models, {id: modelId});
        }
        const formKey = this.activeForm.website_form_key;
        const formInfo = FormEditorRegistry.get(formKey);
        // Success page
        if (!this.$target[0].dataset.successMode) {
            this.$target[0].dataset.successMode = 'redirect';
        }
        if (this.$target[0].dataset.successMode === 'redirect') {
            const currentSuccessPage = this.$target[0].dataset.successPage;
            if (formInfo && formInfo.successPage) {
                this.$target[0].dataset.successPage = formInfo.successPage;
            } else if (!oldFormInfo || (oldFormInfo !== formInfo && oldFormInfo.successPage && currentSuccessPage === oldFormInfo.successPage)) {
                this.$target[0].dataset.successPage = '/contactus-thank-you';
            }
        }
        // Model name
        this.$target[0].dataset.model_name = this.activeForm.model;
        // Load template
        if (formInfo) {
            const formatInfo = this._getDefaultFormat();
            await formInfo.formFields.forEach(async field => {
                field.formatInfo = formatInfo;
                await this._fetchFieldRecords(field);
                this.$target.find('.s_website_form_submit').before(this._renderField(field));
            });
        }
    },
    /**
     * Set the correct mark on all fields.
     *
     * @private
     */
    _setLabelsMark: function () {
        this.$target[0].querySelectorAll('.s_website_form_mark').forEach(el => el.remove());
        const mark = this._getMark();
        if (!mark) {
            return;
        }
        let fieldsToMark = [];
        const requiredSelector = '.s_website_form_model_required, .s_website_form_required';
        const fields = Array.from(this.$target[0].querySelectorAll('.s_website_form_field'));
        if (this._isRequiredMark()) {
            fieldsToMark = fields.filter(el => el.matches(requiredSelector));
        } else if (this._isOptionalMark()) {
            fieldsToMark = fields.filter(el => !el.matches(requiredSelector));
        }
        fieldsToMark.forEach(field => {
            let span = document.createElement('span');
            span.classList.add('s_website_form_mark');
            span.textContent = ` ${mark}`;
            field.querySelector('.s_website_form_label').appendChild(span);
        });
    },

    //--------------------------------------------------------------------------
    // Handlers
    //--------------------------------------------------------------------------

    /**
     * @private
     */
    _onToggleEndMessageClick: function () {
        this.showEndMessage = !this.showEndMessage;
        this.updateUIEndMessage();
        this.trigger_up('activate_snippet', {
            $snippet: this.showEndMessage ? this.$message : this.$target,
        });
    },
});

options.registry.WebsiteFieldEditor = FieldEditor.extend({
    events: _.extend({}, FieldEditor.prototype.events, {
        'click we-button.o_we_select_remove_option': '_onRemoveItemClick',
        'click we-button.o_we_list_add_optional': '_onAddCustomItemClick',
        'click we-button.o_we_list_add_existing': '_onAddExistingItemClick',
        'click we-list we-select': '_onAddItemSelectClick',
        'input we-list input': '_onListItemInput',
    }),

    /**
     * @override
     */
    init: function () {
        this._super.apply(this, arguments);
        this.rerender = true;
    },
    /**
     * @override
     */
    willStart: async function () {
        const _super = this._super.bind(this);
        // Get the authorized existing fields for the form model
        this.existingFields = await this._rpc({
            model: "ir.model",
            method: "get_authorized_fields",
            args: [this.formEl.dataset.model_name],
        }).then(fields => {
            this.fields = _.each(fields, function (field, fieldName) {
                field.name = fieldName;
                field.domain = field.domain || [];
            });
            // Create the buttons for the type we-select
            return Object.keys(fields).map(key => {
                const field = fields[key];
                const button = document.createElement('we-button');
                button.textContent = field.string;
                button.dataset.existingField = field.name;
                return button;
            }).sort((a, b) => (a.textContent > b.textContent) ? 1 : (a.textContent < b.textContent) ? -1 : 0);
        });
        return _super(...arguments);
    },
    /**
     * @override
     */
    cleanForSave: function () {
        this.$target[0].querySelectorAll('#editable_select').forEach(el => el.remove());
        const select = this._getSelect();
        if (select && this.listTable) {
            select.style.display = '';
            select.innerHTML = '';
            // Rebuild the select from the we-list
            this.listTable.querySelectorAll('input').forEach(el => {
                const option = document.createElement('option');
                option.textContent = el.value;
                option.value = this._isFieldCustom() ? el.value : el.name;
                select.appendChild(option);
            });
        }
    },
    /**
     * @override
     */
    updateUI: async function () {
        // See Form updateUI
        if (this.rerender) {
            const select = this._getSelect();
            if (select && !this.$target[0].querySelector('#editable_select')) {
                select.style.display = 'none';
                const editableSelect = document.createElement('div');
                editableSelect.id = 'editable_select';
                editableSelect.classList = 'form-control s_website_form_input';
                select.parentElement.appendChild(editableSelect);
            }
            this.rerender = false;
            await this._rerenderXML().then(() => this._renderList());
            return;
        }
        await this._super.apply(this, arguments);
    },
    /**
     * @override
     */
    onFocus: function () {
        // Other fields type might have change to an existing type.
        // We need to reload the existing type list.
        this.rerender = true;
    },

    //----------------------------------------------------------------------
    // Options
    //----------------------------------------------------------------------

    /**
     * Replace the current field with the custom field selected.
     */
    customField: async function (previewMode, value, params) {
        // Both custom Field and existingField are called when selecting an option
        // value is '' for the method that should not be called.
        if (!value) {
            return;
        }
        const name = this.el.querySelector(`[data-custom-field="${value}"]`).textContent;
        const field = this._getCustomField(value, `Custom ${name}`);
        this._setActiveProperties(field);
        await this._replaceField(field);
        this.rerender = true;
    },
    /**
     * Replace the current field with the existing field selected.
     */
    existingField: async function (previewMode, value, params) {
        // see customField
        if (!value) {
            return;
        }
        const field = Object.assign({}, this.fields[value]);
        this._setActiveProperties(field);
        await this._replaceField(field);
        this.rerender = true;
    },
    /**
     * Set the name of the field on the label
     */
    setLabelText: function (previewMode, value, params) {
        this.$target.find('.s_website_form_label_content').text(value);
        if (this._isFieldCustom()) {
            const multiple = this.$target[0].querySelector('.s_website_form_multiple');
            if (multiple) {
                multiple.dataset.name = value;
            }
            this.$target[0].querySelectorAll('.s_website_form_input').forEach(el => el.name = value);
        }
    },
    /*
    * Set the placeholder of the input
    */
    setPlaceholder: function (previewMode, value, params) {
        this._setPlaceholder(value);
    },
    /**
     * Replace the field with the same field having the label in a different position.
     */
    selectLabelPosition: async function (previewMode, value, params) {
        const field = this._getActiveField();
        field.formatInfo.labelPosition = value;
        await this._replaceField(field);
        this.rerender = true;
    },
    /**
     * Select the display of the multicheckbox field (vertical & horizontal)
     */
    multiCheckboxDisplay: function (previewMode, value, params) {
        const target = this._getMultipleInputs();
        target.querySelectorAll('.checkbox, .radio').forEach(el => {
            if (value === 'horizontal') {
                el.classList.add('col-lg-4', 'col-md-6');
            } else {
                el.classList.remove('col-lg-4', 'col-md-6');
            }
        });
        target.dataset.display = value;
    },
    /**
     * Set the field as required or not
     */
    toggleRequired: function (previewMode, value, params) {
        const isRequired = this.$target[0].classList.contains(params.activeValue);
        this.$target[0].classList.toggle(params.activeValue, !isRequired);
        this.$target[0].querySelectorAll('input, select, textarea').forEach(el => el.toggleAttribute('required', !isRequired));
        this.trigger_up('option_update', {
            optionName: 'WebsiteFormEditor',
            name: 'field_mark',
        });
    },

    //----------------------------------------------------------------------
    // Private
    //----------------------------------------------------------------------

    /**
     * @override
     */
    _computeWidgetState: function (methodName, params) {
        switch (methodName) {
            case 'customField':
                return this._isFieldCustom() ? this._getFieldType() : '';
            case 'existingField':
                return this._isFieldCustom() ? '' : this._getFieldName();
            case 'setLabelText':
                return this.$target.find('.s_website_form_label_content').text();
            case 'setPlaceholder':
                return this._getPlaceholder();
            case 'selectLabelPosition':
                return this._getLabelPosition();
            case 'multiCheckboxDisplay': {
                const target = this._getMultipleInputs();
                return target ? target.dataset.display : '';
            }
            case 'toggleRequired':
                return this.$target[0].classList.contains(params.activeValue) ? params.activeValue : 'false';
        }
        return this._super(...arguments);
    },
    /**
     * @override
     */
    _computeWidgetVisibility: function (widgetName, params) {
        switch (widgetName) {
            case 'multi_check_display_opt':
                return !!this._getMultipleInputs();
            case 'placeholder_opt':
                return !!this._getPlaceholderInput();
            case 'required_opt':
            case 'hidden_opt':
            case 'type_opt':
                return !this.$target[0].classList.contains('s_website_form_model_required');
        }
        return this._super(...arguments);
    },
    /**
     * @override
     */
    _renderCustomXML: function (uiFragment) {
        const selectEl = uiFragment.querySelector('we-select[data-name="type_opt"]');
        const currentFieldName = this._getFieldName();
        const fieldsInForm = Array.from(this.formEl.querySelectorAll('.s_website_form_field:not(.s_website_form_custom) .s_website_form_input')).map(el => el.name).filter(el => el !== currentFieldName);
        const availableFields = this.existingFields.filter(el => !fieldsInForm.includes(el.dataset.existingField));
        if (availableFields.length) {
            const title = document.createElement('we-title');
            title.textContent = 'Existing fields';
            availableFields.unshift(title);
            availableFields.forEach(option => selectEl.append(option.cloneNode(true)));
        }
    },
    /**
     * Replace the target content with the field provided
     *
     * @private
     * @param {Object} field
     * @returns {Promise}
     */
    _replaceField: async function (field) {
        await this._fetchFieldRecords(field);
        const htmlField = this._renderField(field);
        [...this.$target[0].childNodes].forEach(node => node.remove());
        [...htmlField.childNodes].forEach(node => this.$target[0].appendChild(node));
        [...htmlField.attributes].forEach(el => this.$target[0].removeAttribute(el.nodeName));
        [...htmlField.attributes].forEach(el => this.$target[0].setAttribute(el.nodeName, el.nodeValue));
    },

    /**
     * To do after rerenderXML to add the list to the options
     *
     * @private
     */
    _renderList: function () {
        let addItemButton, addItemTitle, listTitle;
        const select = this._getSelect();
        const multipleInputs = this._getMultipleInputs();
        this.listTable = document.createElement('table');
        const isCustomField = this._isFieldCustom();

        if (select) {
            listTitle = 'Options List';
            addItemTitle = 'Add new Option';
            select.querySelectorAll('option').forEach(opt => {
                this._addItemToTable(opt.value, opt.textContent.trim());
            });
            this._renderListItems();
        } else if (multipleInputs) {
            listTitle = multipleInputs.querySelector('.radio') ? 'Radio List' : 'Checkbox List';
            addItemTitle = 'Add new Checkbox';
            multipleInputs.querySelectorAll('.checkbox, .radio').forEach(opt => {
                this._addItemToTable(opt.querySelector('input').value, opt.querySelector('.s_website_form_check_label').textContent.trim());
            });
        } else {
            return;
        }

        if (isCustomField) {
            addItemButton = document.createElement('we-button');
            addItemButton.textContent = addItemTitle;
            addItemButton.classList.add('o_we_list_add_optional');
            addItemButton.dataset.noPreview = 'true';
        } else {
            addItemButton = document.createElement('we-select');
            addItemButton.classList.add('o_we_user_value_widget'); // Todo dont use user value widget class
            const togglerEl = document.createElement('we-toggler');
            togglerEl.textContent = addItemTitle;
            addItemButton.appendChild(togglerEl);
            const selectMenuEl = document.createElement('we-select-menu');
            addItemButton.appendChild(selectMenuEl);
            this._loadListDropdown(selectMenuEl);
        }
        const selectInputEl = document.createElement('we-list');
        const title = document.createElement('we-title');
        title.textContent = listTitle;
        selectInputEl.appendChild(title);
        const tableWrapper = document.createElement('div');
        tableWrapper.classList.add('oe_we_table_wraper');
        tableWrapper.appendChild(this.listTable);
        selectInputEl.appendChild(tableWrapper);
        selectInputEl.appendChild(addItemButton);
        this.el.insertBefore(selectInputEl, this.el.querySelector('[data-set-placeholder]'));
        this._makeListItemsSortable();
    },
    /**
     * Load the dropdown of the list with the records missing from the list.
     *
     * @private
     * @param {HTMLElement} selectMenu
     */
    _loadListDropdown: function (selectMenu) {
        selectMenu = selectMenu || this.el.querySelector('we-list we-select-menu');
        if (selectMenu) {
            selectMenu.innerHTML = '';
            const field = Object.assign({}, this.fields[this._getFieldName()]);
            this._fetchFieldRecords(field).then(() => {
                let buttonItems;
                const optionIds = Array.from(this.listTable.querySelectorAll('input')).map(opt => {
                    return field.type === 'selection' ? opt.name : parseInt(opt.name);
                });
                const availableRecords = (field.records || []).filter(el => !optionIds.includes(el.id));
                if (availableRecords.length) {
                    buttonItems = availableRecords.map(el => {
                        const option = document.createElement('we-button');
                        option.classList.add('o_we_list_add_existing');
                        option.dataset.addOption = el.id;
                        option.dataset.noPreview = 'true';
                        option.textContent = el.display_name;
                        return option;
                    });
                } else {
                    const title = document.createElement('we-title');
                    title.textContent = 'No more records';
                    buttonItems = [title];
                }
                buttonItems.forEach(button => selectMenu.appendChild(button));
            });
        }
    },
    /**
     * @private
     */
    _makeListItemsSortable: function () {
        $(this.listTable).sortable({
            axis: 'y',
            handle: '.o_we_drag_handle',
            items: 'tr',
            cursor: 'move',
            opacity: 0.6,
            stop: (event, ui) => {
                this._renderListItems();
            },
        });
    },
    /**
     * @private
     * @param {string} id
     * @param {string} text
     */
    _addItemToTable: function (id, text) {
        const isCustomField = this._isFieldCustom();
        const draggableEl = document.createElement('we-button');
        draggableEl.classList.add('o_we_drag_handle', 'fa', 'fa-fw', 'fa-arrows');
        draggableEl.dataset.noPreview = 'true';
        const inputEl = document.createElement('input');
        inputEl.type = 'text';
        if (text) {
            inputEl.value = text;
        }
        if (!isCustomField && id) {
            inputEl.name = id;
        }
        inputEl.disabled = !isCustomField;
        const trEl = document.createElement('tr');
        const buttonEl = document.createElement('we-button');
        buttonEl.classList.add('o_we_select_remove_option', 'fa', 'fa-fw', 'fa-minus');
        buttonEl.dataset.removeOption = id;
        buttonEl.dataset.noPreview = 'true';
        const draggableTdEl = document.createElement('td');
        const inputTdEl = document.createElement('td');
        const buttonTdEl = document.createElement('td');
        draggableTdEl.appendChild(draggableEl);
        trEl.appendChild(draggableTdEl);
        inputTdEl.appendChild(inputEl);
        trEl.appendChild(inputTdEl);
        buttonTdEl.appendChild(buttonEl);
        trEl.appendChild(buttonTdEl);
        this.listTable.appendChild(trEl);
        if (isCustomField) {
            inputEl.focus();
        }
    },
    /**
     * Apply the we-list on the target and rebuild the input(s)
     *
     * @private
     */
    _renderListItems: function () {
        const multiInputsWrap = this._getMultipleInputs();
        const selectWrap = this.$target[0].querySelector('#editable_select');
        const isRequiredField = this._isFieldRequired();
        const name = this._getFieldName();
        if (multiInputsWrap) {
            const type = multiInputsWrap.querySelector('.radio') ? 'radio' : 'checkbox';
            multiInputsWrap.innerHTML = '';
            const params = {
                field: {
                    name: name,
                    id: Math.random().toString(36).substring(2, 15), // Big unique ID
                    required: isRequiredField,
                    formatInfo: {
                        multiPosition: multiInputsWrap.dataset.display,
                    }
                }
            };
            this._getListItems().forEach((record, idx) => {
                params.record_index = idx;
                params.record = record;
                const template = document.createElement('template');
                template.innerHTML = qweb.render(`website_form.${type}`, params);
                multiInputsWrap.appendChild(template.content.firstElementChild);
            });
        } else if (selectWrap) {
            selectWrap.innerHTML = '';
            this.listTable.querySelectorAll('input').forEach(el => {
                const option = document.createElement('div');
                option.id = (el.name || el.value);
                option.classList.add('s_website_form_select_item');
                option.textContent = el.value;
                selectWrap.appendChild(option);
            });
        }
    },
    /**
     * Returns an array based on the we-list containing the field's records
     *
     * @returns {Array}
     */
    _getListItems: function () {
        if (!this.listTable) {
            return null;
        }
        const isCustomField = this._isFieldCustom();
        const records = [];
        this.listTable.querySelectorAll('input').forEach(el => {
            const id = isCustomField ? el.value : el.name;
            records.push({
                id: id,
                display_name: el.value,
            });
        });
        return records;
    },
    /**
     * Returns the select element if it exist else null
     *
     * @private
     * @returns {HTMLElement}
     */
    _getSelect: function () {
        return this.$target[0].querySelector('select');
    },

    //--------------------------------------------------------------------------
    // Handlers
    //--------------------------------------------------------------------------

    /**
     * @private
     * @param {Event} ev
     */
    _onRemoveItemClick: function (ev) {
        ev.target.closest('tr').remove();
        this._loadListDropdown();
        this._renderListItems();
    },
    /**
     * @private
     * @param {Event} ev
     */
    _onAddCustomItemClick: function (ev) {
        this._addItemToTable();
        this._makeListItemsSortable();
        this._renderListItems();
    },
    /**
     * @private
     * @param {Event} ev
     */
    _onAddExistingItemClick: function (ev) {
        const value = ev.currentTarget.dataset.addOption;
        this._addItemToTable(value, ev.currentTarget.textContent);
        this._makeListItemsSortable();
        this._loadListDropdown();
        this._renderListItems();
    },
    /**
     * @private
     * @param {Event} ev
     */
    _onAddItemSelectClick: function (ev) {
        ev.currentTarget.querySelector('we-toggler').classList.toggle('active');
    },
    /**
     * @private
     */
    _onListItemInput: function () {
        this._renderListItems();
    },
});

options.registry.AddFieldForm = FormEditor.extend({
    isTopOption: true,

    //--------------------------------------------------------------------------
    // Options
    //--------------------------------------------------------------------------

    /**
     * Add a char field at the end of the form.
     * New field is set as active
     */
    addField: async function (previewMode, value, params) {
        const field = this._getCustomField('char', 'Custom Text');
        field.formatInfo = this._getDefaultFormat();
        const htmlField = this._renderField(field);
        this.$target.find('.s_website_form_submit').before(htmlField);
        this.trigger_up('activate_snippet', {
            $snippet: $(htmlField),
        });
    },
});

options.registry.AddField = FieldEditor.extend({
    isTopOption: true,

    //--------------------------------------------------------------------------
    // Options
    //--------------------------------------------------------------------------

    /**
     * Add a char field with active field properties after the active field.
     * New field is set as active
     */
    addField: async function (previewMode, value, params) {
        this.trigger_up('option_update', {
            optionName: 'WebsiteFormEditor',
            name: 'add_field',
            data: {
                formatInfo: this._getFieldFormat(),
                $target: this.$target,
            },
        });
    },
});

// Superclass for options that need to disable a button from the snippet overlay
const DisableOverlayButtonOption = options.Class.extend({
    // Disable a button of the snippet overlay
    disableButton: function (buttonName, message) {
        // TODO refactor in master
        const className = 'oe_snippet_' + buttonName;
        this.$overlay.add(this.$overlay.data('$optionsSection')).on('click', '.' + className, this.preventButton);
        const $button = this.$overlay.add(this.$overlay.data('$optionsSection')).find('.' + className);
        $button.attr('title', message).tooltip({delay: 0});
        $button.removeClass(className); // Disable the functionnality
    },

    preventButton: function (event) {
        // Snippet options bind their functions before the editor, so we
        // can't cleanly unbind the editor onRemove function from here
        event.preventDefault();
        event.stopImmediatePropagation();
    }
});

// Disable duplicate button for model fields
options.registry.WebsiteFormFieldModel = DisableOverlayButtonOption.extend({
    start: function () {
        this.disableButton('clone', _t('You can\'t duplicate a model field.'));
        return this._super.apply(this, arguments);
    }
});

// Disable delete button for model required fields
options.registry.WebsiteFormFieldRequired = DisableOverlayButtonOption.extend({
    start: function () {
        this.disableButton('remove', _t('You can\'t remove a field that is required by the model itself.'));
        return this._super.apply(this, arguments);
    }
});

// Disable delete and duplicate button for submit
options.registry.WebsiteFormSubmitRequired = DisableOverlayButtonOption.extend({
    start: function () {
        this.disableButton('remove', _t('You can\'t remove the submit button of the form'));
        this.disableButton('clone', _t('You can\'t duplicate the submit button of the form.'));
        return this._super.apply(this, arguments);
    }
});
});
