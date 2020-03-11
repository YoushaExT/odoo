odoo.define('web_tour.TourStepUtils', function (require) {
'use strict';

const core = require('web.core');
const _t = core._t;

return core.Class.extend({
    _getHelpMessage: (functionName, ...args) => `Generated by function tour utils ${functionName}(${args.join(', ')})`,

    addDebugHelp: helpMessage => step => {
        if (typeof step.debugHelp === 'string') {
            step.debugHelp = step.debugHelp + '\n' + helpMessage;
        } else {
            step.debugHelp = helpMessage;
        }
        return step;
    },

    editionEnterpriseModifier(step) {
        step.edition = 'enterprise';
        return step;
    },

    mobileModifier(step) {
        step.mobile = true;
        return step;
    },

    showAppsMenuItem() {
        return {
            edition: 'community',
            trigger: '.o_menu_apps a',
            auto: true,
            position: 'bottom',
        };
    },

    toggleHomeMenu() {
        return {
            edition: 'enterprise',
            trigger: '.o_main_navbar .o_menu_toggle',
            content: _t('Click on the <i>Home icon</i> to navigate across apps.'),
            position: 'bottom',
        };
    },

    autoExpandMoreButtons(extra_trigger) {
        return {
            trigger: '.oe_button_box',
            extra_trigger: extra_trigger,
            auto: true,
            run: actions => {
                const $more = $('.oe_button_box .o_button_more');
                if ($more.length) {
                    actions.click($more);
                }
            },
        };
    },

    goBackBreadcrumbsMobile(description, ...extraTrigger) {
        return extraTrigger.map(element => ({
            mobile: true,
            trigger: '.breadcrumb-item:not(.d-none):first',
            extra_trigger: element,
            content: description,
            position: 'bottom',
            debugHelp: this._getHelpMessage('goBackBreadcrumbsMobile', description, ...extraTrigger),
        }));
    },

    goToAppSteps(dataMenuXmlid, description) {
        return [
            this.showAppsMenuItem(),
            {
                trigger: `.o_app[data-menu-xmlid="${dataMenuXmlid}"]`,
                content: description,
                position: 'right',
                edition: 'community',
            },
            {
                trigger: `.o_app[data-menu-xmlid="${dataMenuXmlid}"]`,
                content: description,
                position: 'bottom',
                edition: 'enterprise',
            },
        ].map(this.addDebugHelp(this._getHelpMessage('goToApp', dataMenuXmlid, description)));
    },

    openBuggerMenu(extraTrigger) {
        return {
            mobile: true,
            trigger: '.o_mobile_menu_toggle',
            extra_trigger: extraTrigger,
            content: _t('Open bugger menu.'),
            position: 'bottom',
            debugHelp: this._getHelpMessage('openBuggerMenu', extraTrigger),
        };
    },

    statusbarButtonsSteps(innerTextButton, description, extraTrigger) {
        return [
            {
                mobile: true,
                trigger: '.o_statusbar_buttons .btn.dropdown-toggle:contains(Action)',
                extra_trigger: extraTrigger,
                content: _t('Open Action Dropdown Menu.'),
                position: 'bottom',
            }, {
                trigger: `.o_statusbar_buttons button:enabled:contains('${innerTextButton}')`,
                content: description,
                position: 'bottom',
            },
        ].map(this.addDebugHelp(this._getHelpMessage('statusbarButtonsSteps', innerTextButton, description, extraTrigger)));
    },

    simulateEnterKeyboardInSearchModal() {
        return {
            mobile: true,
            trigger: '.o_searchview_input',
            extra_trigger: '.modal:not(.o_inactive_modal) .dropdown-menu.o_searchview_autocomplete',
            position: 'bottom',
            run: action => {
                const keyEventEnter = new KeyboardEvent('keydown', {
                    bubbles: true,
                    cancelable: true,
                    key: 'Enter',
                    code: 'Enter',
                    which: 13,
                    keyCode: 13,
                });
                action.tip_widget.$anchor[0].dispatchEvent(keyEventEnter);
            },
            debugHelp: this._getHelpMessage('simulateEnterKeyboardInSearchModal'),
        };
    },

    mobileKanbanSearchMany2X(modalTitle, valueSearched) {
        return [
            {
                mobile: true,
                trigger: '.o_enable_searchview',
                extra_trigger: `.modal:not(.o_inactive_modal) .modal-title:contains('${modalTitle}')`,
                position: 'bottom',
            }, {
                mobile: true,
                trigger: '.o_searchview_input',
                position: 'bottom',
                run: `text ${valueSearched}`,
            },
            this.simulateEnterKeyboardInSearchModal(),
            {
                mobile: true,
                trigger: `.o_kanban_record .o_kanban_record_title :contains('${valueSearched}')`,
                position: 'bottom',
            },
        ].map(this.addDebugHelp(this._getHelpMessage('mobileKanbanSearchMany2X', modalTitle, valueSearched)));
    },
});
});
