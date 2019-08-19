odoo.define('website_slides.quiz.question.form', function (require) {
'use strict';

var publicWidget = require('web.public.widget');
var core = require('web.core');

var QWeb = core.qweb;
var _t = core._t;

/**
 * This Widget is responsible of displaying the question inputs when adding a new question or when updating an
 * existing one. When validating the question it makes an RPC call to the server and trigger an event for
 * displaying the question by the Quiz widget.
 */
var QuestionFormWidget = publicWidget.Widget.extend({
    template: 'slide.quiz.question.input',
    xmlDependencies: ['/website_slides/static/src/xml/slide_quiz_create.xml'],
    events: {
        'click .o_wslides_js_quiz_validate_question': '_validateQuestion',
        'click .o_wslides_js_quiz_cancel_question': '_cancelValidation',
        'click .o_wslides_js_quiz_add_answer': '_addAnswerLine',
        'click .o_wslides_js_quiz_remove_answer': '_removeAnswerLine',
    },

    /**
     * @override
     * @param parent
     * @param options
     */
    init: function (parent, options) {
        this.$editedQuestion = options.editedQuestion;
        this.question = options.question || {};
        this.update = options.update;
        this.sequence = options.sequence;
        this.slideId = options.slideId;
        this._super.apply(this, arguments);
    },

    /**
     * @override
     * @returns {*}
     */
    start: function () {
        var self = this;
        return this._super.apply(this, arguments).then(function () {
            self.$('.o_wslides_quiz_question input').focus();
        });
    },

    //--------------------------------------------------------------------------
    // Handlers
    //--------------------------------------------------------------------------

    /**
     * Adds a new answer line after the element the user clicked on
     * e.g. If there is 3 answer lines and the user click on the add
     *      answer button on the second line, the new answer line will
     *      display between the second and the third line.
     * @param ev
     * @private
     */
    _addAnswerLine: function (ev) {
        $(ev.currentTarget).closest('.o_wslides_js_quiz_answer').after(QWeb.render('slide.quiz.answer.line'));
    },

    /**
     * Removes an answer line. Can't remove the last answer line.
     * @param ev
     * @private
     */
    _removeAnswerLine: function (ev) {
        if (this.$('.o_wslides_js_quiz_answer').length > 1) {
            $(ev.currentTarget).closest('.o_wslides_js_quiz_answer').remove();
        }
    },

    /**
     * Handler when user click on 'Save & New', 'Save & Close'
     * or 'Update' buttons.
     * @param ev
     * @private
     */
    _validateQuestion: function (ev) {
        this._createOrUpdateQuestion({
            save_and_new: $(ev.currentTarget).hasClass('o_wslides_js_quiz_create_next'),
            update: $(ev.currentTarget).hasClass('o_wslides_js_quiz_update'),
        });
    },

    /**
     * Handler when user click on the 'Cancel' button.
     * Calls a method from slides_course_quiz.js widget
     * which will handle the reset of the question display.
     * @private
     */
    _cancelValidation: function () {
        this.trigger_up('reset_display', {
            questionFormWidget: this,
        });
    },

    //--------------------------------------------------------------------------
    // Private
    //--------------------------------------------------------------------------

    /**
     * RPC call to create or update a question.
     * Triggers method from slides_course_quiz.js to
     * correctly display the question.
     * @param options
     * @private
     */
    _createOrUpdateQuestion: function (options) {
        var self = this;
        var $form = this.$('form');
        if (this._isValidForm($form)) {
            var values = this._serializeForm($form);
            this._rpc({
                route: '/slides/slide/quiz/question_add_or_update',
                params: values
            }).then(function (renderedQuestion) {
                if (options.update) {
                    self.trigger_up('display_updated_question', {
                        newQuestionRenderedTemplate: renderedQuestion,
                        $editedQuestion: self.$editedQuestion,
                        questionFormWidget: self,
                    });
                } else {
                    self.trigger_up('display_created_question', {
                        newQuestionRenderedTemplate: renderedQuestion,
                        save_and_new: options.save_and_new,
                        questionFormWidget: self
                    });
                }
            });
        } else {
            this.displayNotification({
                type: 'warning',
                title: _t('Unable to create question'),
                message: _t('Please fill up the question'),
                sticky: true
            });
            this.$('.o_wslides_quiz_question input').focus();
        }
    },

    /**
     * Check if the Question has been filled up
     * @param $form
     * @returns {boolean}
     * @private
     */
    _isValidForm: function($form) {
        return $form.find('.o_wslides_quiz_question input[type=text]').val().trim() !== "";
    },

    /**
     * Serialize the form into a JSON object to send it
     * to the server through a RPC call.
     * @param $form
     * @returns {{id: *, sequence: *, question: *, slide_id: *, answer_ids: Array}}
     * @private
     */
    _serializeForm: function ($form) {
        var answers = [];
        var sequence = 1;
        $form.find('.o_wslides_js_quiz_answer').each(function () {
            var value = $(this).find('input[type=text]').val();
            if (value.trim() !== "") {
                var answer = {
                    'sequence': sequence++,
                    'text_value': value,
                    'is_correct': $(this).find('input[type=radio]').prop('checked') === true
                };
                answers.push(answer);
            }
        });
        return {
            'existing_question_id': this.$el.data('id'),
            'sequence': this.sequence,
            'question': $form.find('.o_wslides_quiz_question input[type=text]').val(),
            'slide_id': this.slideId,
            'answer_ids': answers
        };
    },

});

return QuestionFormWidget;
});
