/** @odoo-module **/
'use strict';

import './commands/deleteBackward.js';
import './commands/deleteForward.js';
import './commands/enter.js';
import './commands/shiftEnter.js';
import './commands/shiftTab.js';
import './commands/tab.js';
import './commands/toggleList.js';
import './commands/align.js';

import { sanitize } from './utils/sanitize.js';
import { serializeNode, unserializeNode, serializeSelection } from './utils/serialize.js';
import {
    closestBlock,
    commonParentGet,
    containsUnremovable,
    DIRECTIONS,
    endPos,
    getCursorDirection,
    getListMode,
    getOuid,
    insertText,
    isColorGradient,
    nodeSize,
    preserveCursor,
    setSelection,
    startPos,
    toggleClass,
    closestElement,
    isVisible,
    rgbToHex,
    isFontAwesome,
    getInSelection,
    getDeepRange,
    ancestors,
    firstLeaf,
    nextLeaf,
    isUnremovable,
    fillEmpty,
    isEmptyBlock,
    getUrlsInfosInString,
    URL_REGEX,
    isBold,
    YOUTUBE_URL_GET_VIDEO_ID,
    unwrapContents,
    peek,
} from './utils/utils.js';
import { editorCommands } from './commands/commands.js';
import { Powerbox } from './powerbox/Powerbox.js';
import { TablePicker } from './tablepicker/TablePicker.js';

export * from './utils/utils.js';
import { UNBREAKABLE_ROLLBACK_CODE, UNREMOVABLE_ROLLBACK_CODE } from './utils/constants.js';

const BACKSPACE_ONLY_COMMANDS = ['oDeleteBackward', 'oDeleteForward'];
const BACKSPACE_FIRST_COMMANDS = BACKSPACE_ONLY_COMMANDS.concat(['oEnter', 'oShiftEnter']);

// 60 seconds
const HISTORY_SNAPSHOT_INTERVAL = 1000 * 60;
// 10 seconds
const HISTORY_SNAPSHOT_BUFFER_TIME = 1000 * 10;

const KEYBOARD_TYPES = { VIRTUAL: 'VIRTUAL', PHYSICAL: 'PHYSICAL', UNKNOWN: 'UKNOWN' };

const IS_KEYBOARD_EVENT_UNDO = ev => ev.key === 'z' && (ev.ctrlKey || ev.metaKey);
const IS_KEYBOARD_EVENT_REDO = ev => ev.key === 'y' && (ev.ctrlKey || ev.metaKey);
const IS_KEYBOARD_EVENT_BOLD = ev => ev.key === 'b' && (ev.ctrlKey || ev.metaKey);

const CLIPBOARD_BLACKLISTS = {
    unwrap: ['.Apple-interchange-newline', 'DIV'], // These elements' children will be unwrapped.
    remove: ['META', 'STYLE', 'SCRIPT'], // These elements will be removed along with their children.
};
const CLIPBOARD_WHITELISTS = {
    nodes: [
        // Style
        'P',
        'H1',
        'H2',
        'H3',
        'H4',
        'H5',
        'H6',
        'BLOCKQUOTE',
        'PRE',
        // List
        'UL',
        'OL',
        'LI',
        // Inline style
        'I',
        'B',
        'U',
        'EM',
        'STRONG',
        // Table
        'TABLE',
        'TH',
        'TBODY',
        'TR',
        'TD',
        // Miscellaneous
        'IMG',
        'BR',
        'A',
        '.fa',
    ],
    classes: [
        // Media
        /^float-/,
        'd-block',
        'mx-auto',
        'img-fluid',
        'img-thumbnail',
        'rounded',
        'rounded-circle',
        /^padding-/,
        /^shadow/,
        // Odoo colors
        /^text-o-/,
        /^bg-o-/,
        // Odoo checklists
        'o_checked',
        'o_checklist',
        // Miscellaneous
        /^btn/,
        /^fa/,
    ],
    attributes: ['class', 'href', 'src'],
};

function defaultOptions(defaultObject, object) {
    const newObject = Object.assign({}, defaultObject, object);
    for (const [key, value] of Object.entries(object)) {
        if (typeof value === 'undefined') {
            newObject[key] = defaultObject[key];
        }
    }
    return newObject;
}
export class OdooEditor extends EventTarget {
    constructor(editable, options = {}) {
        super();

        this.options = defaultOptions(
            {
                controlHistoryFromDocument: false,
                getContextFromParentRect: () => {
                    return { top: 0, left: 0 };
                },
                toSanitize: true,
                isRootEditable: true,
                placeholder: false,
                defaultLinkAttributes: {},
                getContentEditableAreas: () => [],
                getPowerboxElement: () => {
                    const selection = document.getSelection();
                    if (selection.isCollapsed && selection.rangeCount) {
                        return closestElement(selection.anchorNode, 'P, DIV');
                    }
                },
                isHintBlacklisted: () => false,
                _t: string => string,
            },
            options,
        );

        // --------------
        // Set properties
        // --------------

        this.document = options.document || document;

        this.isMobile = matchMedia('(max-width: 767px)').matches;

        // Keyboard type detection, happens only at the first keydown event.
        this.keyboardType = KEYBOARD_TYPES.UNKNOWN;

        // Wether we should check for unbreakable the next history step.
        this._checkStepUnbreakable = true;

        // All dom listeners currently active.
        this._domListeners = [];

        // Set of labels that which prevent the automatic step mechanism if
        // it contains at least one element.
        this._observerTimeoutUnactive = new Set();
        // Set of labels that which prevent the observer to be active if
        // it contains at least one element.
        this._observerUnactiveLabels = new Set();

        // The state of the dom.
        this._currentMouseState = 'mouseup';

        this._onKeyupResetContenteditableNodes = [];

        // Track if we need to rollback mutations in case unbreakable or unremovable are being added or removed.
        this._toRollback = false;

        // Map that from an node id to the dom node.
        this._idToNodeMap = new Map();

        // -------------------
        // Alter the editable
        // -------------------

        if (editable.innerHTML.trim() === '') {
            editable.innerHTML = '<p><br></p>';
        }

        // Convention: root node is ID root.
        editable.oid = 'root';
        this._idToNodeMap.set(1, editable);
        this.editable = this.options.toSanitize ? sanitize(editable) : editable;

        // Set contenteditable before clone as FF updates the content at this point.
        this._activateContenteditable();

        this._collabClientId = this.options.collaborationClientId;

        // Colaborator selection and caret display.
        this._collabSelectionInfos = new Map();
        this._collabSelectionColor = `hsl(${(Math.random() * 360).toFixed(0)}, 75%, 50%)`;
        this._collabSelectionsContainer = this.document.createElement('div');
        this._collabSelectionsContainer.classList.add('oe-collaboration-selections-container');
        this.editable.before(this._collabSelectionsContainer);

        this.idSet(editable);
        this._historyStepsActive = true;
        this.historyReset();

        this._createCommandBar();

        this.toolbarTablePicker = new TablePicker({ document: this.document });
        this.toolbarTablePicker.addEventListener('cell-selected', ev => {
            this.execCommand('insertTable', {
                rowNumber: ev.detail.rowNumber,
                colNumber: ev.detail.colNumber,
            });
        });

        // -----------
        // Bind events
        // -----------

        this.observerActive();

        this.addDomListener(this.editable, 'keydown', this._onKeyDown);
        this.addDomListener(this.editable, 'input', this._onInput);
        this.addDomListener(this.editable, 'beforeinput', this._onBeforeInput);
        this.addDomListener(this.editable, 'mousedown', this._onMouseDown);
        this.addDomListener(this.editable, 'mouseup', this._onMouseup);
        this.addDomListener(this.editable, 'paste', this._onPaste);
        this.addDomListener(this.editable, 'drop', this._onDrop);

        this.addDomListener(this.document, 'selectionchange', this._onSelectionChange);
        this.addDomListener(this.document, 'selectionchange', this._handleCommandHint);
        this.addDomListener(this.document, 'keydown', this._onDocumentKeydown);
        this.addDomListener(this.document, 'keyup', this._onDocumentKeyup);
        this.addDomListener(this.document, 'mousedown', this._onDoumentMousedown);
        this.addDomListener(this.document, 'mouseup', this._onDoumentMouseup);

        this.multiselectionRefresh = this.multiselectionRefresh.bind(this);
        this._resizeObserver = new ResizeObserver(this.multiselectionRefresh);
        this._resizeObserver.observe(this.document.body);
        this._resizeObserver.observe(this.editable);
        this.addDomListener(this.editable, 'scroll', this.multiselectionRefresh);

        if (this._collabClientId) {
            this._snapshotInterval = setInterval(() => {
                this._historyMakeSnapshot();
            }, HISTORY_SNAPSHOT_INTERVAL);
        }

        // -------
        // Toolbar
        // -------

        if (this.options.toolbar) {
            this.toolbar = this.options.toolbar;
            this.bindExecCommand(this.toolbar);
            // Ensure anchors in the toolbar don't trigger a hash change.
            const toolbarAnchors = this.toolbar.querySelectorAll('a');
            toolbarAnchors.forEach(a => a.addEventListener('click', e => e.preventDefault()));
            const tablepickerDropdown = this.toolbar.querySelector('.oe-tablepicker-dropdown');
            tablepickerDropdown && tablepickerDropdown.append(this.toolbarTablePicker.el);
            this.toolbarTablePicker.show();
            const tableDropdownButton = this.toolbar.querySelector('#tableDropdownButton');
            tableDropdownButton &&
                tableDropdownButton.addEventListener('click', () => {
                    this.toolbarTablePicker.reset();
                });
            for (const colorLabel of this.toolbar.querySelectorAll('label')) {
                colorLabel.addEventListener('mousedown', ev => {
                    // Hack to prevent loss of focus (done by preventDefault) while still opening
                    // color picker dialog (which is also prevented by preventDefault on chrome,
                    // except when click detail is 2, which happens on a double-click but isn't
                    // triggered by a dblclick event)
                    if (ev.detail < 2) {
                        ev.preventDefault();
                        ev.currentTarget.dispatchEvent(new MouseEvent('click', { detail: 2 }));
                    }
                });
                colorLabel.addEventListener('input', ev => {
                    this.document.execCommand(ev.target.name, false, ev.target.value);
                    this.updateColorpickerLabels();
                });
            }
            if (this.isMobile) {
                this.editable.before(this.toolbar);
            }
        }
        // placeholder hint
        if (editable.textContent === '' && this.options.placeholder) {
            this._makeHint(editable.firstChild, this.options.placeholder, true);
        }
    }
    /**
     * Releases anything that was initialized.
     *
     * TODO: properly implement this.
     */
    destroy() {
        this.observerUnactive();
        this._removeDomListener();
        this.commandBar.destroy();
        this.commandbarTablePicker.el.remove();
        this._collabSelectionsContainer.remove();
        this._resizeObserver.disconnect();
        clearInterval(this._snapshotInterval);
    }

    sanitize() {
        this.observerFlush();

        let commonAncestor, record;
        for (record of this._currentStep.mutations) {
            const node = this.idFind(record.parentId || record.id) || this.editable;
            commonAncestor = commonAncestor
                ? commonParentGet(commonAncestor, node, this.editable)
                : node;
        }
        if (!commonAncestor) {
            return false;
        }

        // sanitize and mark current position as sanitized
        sanitize(commonAncestor);
    }

    addDomListener(element, eventName, callback) {
        const boundCallback = callback.bind(this);
        this._domListeners.push([element, eventName, boundCallback]);
        element.addEventListener(eventName, boundCallback);
    }

    _generateId() {
        // No need for secure random number.
        return Math.floor(Math.random() * Math.pow(2,52)).toString();
    }

    // Assign IDs to src, and dest if defined
    idSet(node, testunbreak = false) {
        if (!node.oid) {
            node.oid = this._generateId();
        }
        // In case the id was created by another collaboration client.
        this._idToNodeMap.set(node.oid, node);
        // Rollback if node.ouid changed. This ensures that nodes never change
        // unbreakable ancestors.
        node.ouid = node.ouid || getOuid(node, true);
        if (testunbreak && !(node.nodeType === Node.TEXT_NODE && !node.length)) {
            const ouid = getOuid(node);
            if (!this._toRollback && ouid && ouid !== node.ouid) {
                this._toRollback = UNBREAKABLE_ROLLBACK_CODE;
            }
        }

        let childNode = node.firstChild;
        while (childNode) {
            this.idSet(childNode, testunbreak);
            childNode = childNode.nextSibling;
        }
    }

    idFind(id) {
        return this._idToNodeMap.get(id);
    }

    serializeNode(node, mutatedNodes) {
        return this._collabClientId ? serializeNode(node, mutatedNodes) : node;
    }

    unserializeNode(node) {
        return this._collabClientId ? unserializeNode(node) : node;
    }

    automaticStepActive(label) {
        this._observerTimeoutUnactive.delete(label);
    }
    automaticStepUnactive(label) {
        this._observerTimeoutUnactive.add(label);
    }
    automaticStepSkipStack() {
        this.automaticStepUnactive('skipStack');
        setTimeout(() => this.automaticStepActive('skipStack'));
    }
    observerUnactive(label) {
        this._observerUnactiveLabels.add(label);
        clearTimeout(this.observerTimeout);
        this.observer.disconnect();
        this.observerFlush();
    }
    observerFlush() {
        this.observerApply(this.observer.takeRecords());
    }
    observerActive(label) {
        this._observerUnactiveLabels.delete(label);
        if (this._observerUnactiveLabels.size !== 0) return;

        if (!this.observer) {
            this.observer = new MutationObserver(records => {
                records = this.filterMutationRecords(records);
                if (!records.length) return;
                clearTimeout(this.observerTimeout);
                if (this._observerTimeoutUnactive.size === 0) {
                    this.observerTimeout = setTimeout(() => {
                        this.historyStep();
                    }, 100);
                }
                this.observerApply(records);
            });
        }
        this.observer.observe(this.editable, {
            childList: true,
            subtree: true,
            attributes: true,
            attributeOldValue: true,
            characterData: true,
            characterDataOldValue: true,
        });
    }

    observerApply(records) {
        // There is a case where node A is added and node B is a descendant of
        // node A where node B was not in the observed tree) then node B is
        // added into another node. In that case, we need to keep track of node
        // B so when serializing node A, we strip node B from the node A tree to
        // avoid the duplication of node A.
        const mutatedNodes = new Set();
        for (const record of records) {
            if (record.type === 'childList') {
                for (const node of record.addedNodes) {
                    this.idSet(node, this._checkStepUnbreakable);
                    mutatedNodes.add(node.oid);
                }
                for (const node of record.removedNodes) {
                    this.idSet(node, this._checkStepUnbreakable);
                    mutatedNodes.delete(node.oid);
                }
            }
        }
        for (const record of records) {
            switch (record.type) {
                case 'characterData': {
                    this._currentStep.mutations.push({
                        'type': 'characterData',
                        'id': record.target.oid,
                        'text': record.target.textContent,
                        'oldValue': record.oldValue,
                    });
                    break;
                }
                case 'attributes': {
                    this._currentStep.mutations.push({
                        'type': 'attributes',
                        'id': record.target.oid,
                        'attributeName': record.attributeName,
                        'value': record.target.getAttribute(record.attributeName),
                        'oldValue': record.oldValue,
                    });
                    break;
                }
                case 'childList': {
                    record.addedNodes.forEach(added => {
                        this._toRollback =
                            this._toRollback ||
                            (containsUnremovable(added) && UNREMOVABLE_ROLLBACK_CODE);
                        const mutation = {
                            'type': 'add',
                        };
                        if (!record.nextSibling && record.target.oid) {
                            mutation.append = record.target.oid;
                        } else if (record.nextSibling && record.nextSibling.oid) {
                            mutation.before = record.nextSibling.oid;
                        } else if (!record.previousSibling && record.target.oid) {
                            mutation.prepend = record.target.oid;
                        } else if (record.previousSibling && record.previousSibling.oid) {
                            mutation.after = record.previousSibling.oid;
                        } else {
                            return false;
                        }
                        mutation.id = added.oid;
                        mutation.node = this.serializeNode(added, mutatedNodes);
                        this._currentStep.mutations.push(mutation);
                    });
                    record.removedNodes.forEach(removed => {
                        if (!this._toRollback && containsUnremovable(removed)) {
                            this._toRollback = UNREMOVABLE_ROLLBACK_CODE;
                        }
                        this._currentStep.mutations.push({
                            'type': 'remove',
                            'id': removed.oid,
                            'parentId': record.target.oid,
                            'node': this.serializeNode(removed),
                            'nextId': record.nextSibling ? record.nextSibling.oid : undefined,
                            'previousId': record.previousSibling
                                ? record.previousSibling.oid
                                : undefined,
                        });
                    });
                    break;
                }
            }
        }
        if (records.length) {
            this.dispatchEvent(new Event('observerApply'));
        }
    }
    filterMutationRecords(records) {
        // Save the first attribute in a cache to compare only the first
        // attribute record of node to its latest state.
        const attributeCache = new Map();
        const filteredRecords = [];

        for (const record of records) {
            if (record.type === 'attributes') {
                // Skip the attributes change on the dom.
                if (record.target === this.editable) continue;

                attributeCache.set(record.target, attributeCache.get(record.target) || {});
                if (
                    typeof attributeCache.get(record.target)[record.attributeName] === 'undefined'
                ) {
                    const oldValue = record.oldValue === undefined ? null : record.oldValue;
                    attributeCache.get(record.target)[record.attributeName] =
                        oldValue !== record.target.getAttribute(record.attributeName);
                }
                if (!attributeCache.get(record.target)[record.attributeName]) {
                    continue;
                }
            }
            filteredRecords.push(record);
        }
        return filteredRecords;
    }

    // History
    // -------------------------------------------------------------------------

    historyReset() {
        this._historyClean();
        const firstStep = this._historyGetSnapshotStep();
        this._firstStepId = firstStep.id;
        this._historySnapshots = [{ step: firstStep }];
        this._historySteps.push(firstStep);
    }
    historyGetSnapshotSteps() {
        // If the current snapshot has no time, it means that there is the no
        // other snapshot that have been made (either it is the one created upon
        // initialization or reseted by historyResetFromSteps).
        if (!this._historySnapshots[0].time) {
            return this._historySteps;
        }
        const steps = [];
        let snapshot;
        if (this._historySnapshots[0].time + HISTORY_SNAPSHOT_BUFFER_TIME < Date.now()) {
            snapshot = this._historySnapshots[0];
        } else {
            // this._historySnapshots[1] has being created at least 1 minute ago
            // (HISTORY_SNAPSHOT_INTERVAL) or it is the first step.
            snapshot = this._historySnapshots[1];
        }
        let index = this._historySteps.length - 1;
        while (this._historySteps[index].id !== snapshot.step.id) {
            steps.push(this._historySteps[index]);
            index--;
        }
        steps.push(snapshot.step);
        steps.reverse();

        return steps;
    }
    historyResetFromSteps(steps) {
        this.observerUnactive();
        for (const node of [...this.editable.childNodes]) {
            node.remove();
        }
        this._historyClean();
        for (const step of steps) {
            this.historyApply(step.mutations);
        }
        this._historySnapshots = [{ step: steps[0] }];
        this._historySteps = steps;

        this._handleCommandHint();
        this.multiselectionRefresh();
        this.observerActive();
    }
    historyGetMissingSteps({fromStepId, toStepId}) {
        const fromIndex = this._historySteps.findIndex(x => x.id === fromStepId);
        const toIndex = this._historySteps.findIndex(x => x.id === toStepId);
        if (fromIndex === -1 || toIndex === -1) {
            return -1;
        }
        return this._historySteps.slice(fromIndex + 1, toIndex);
    }

    // One step completed: apply to vDOM, setup next history step
    historyStep(skipRollback = false) {
        if (!this._historyStepsActive) {
            return;
        }
        this.observerFlush();
        // check that not two unBreakables modified
        if (this._toRollback) {
            if (!skipRollback) this.historyRollback();
            this._toRollback = false;
        }

        // push history
        const currentStep = this._currentStep;
        if (!currentStep.mutations.length) {
            return false;
        }

        currentStep.id = this._generateId();
        const previousStep = peek(this._historySteps);
        currentStep.clientId = this._collabClientId;
        currentStep.previousStepId = previousStep.id;

        this._historySteps.push(currentStep);
        if (this.options.onHistoryStep) {
            this.options.onHistoryStep(currentStep);
        }
        this._currentStep = {
            selection: {},
            mutations: [],
        };
        this._checkStepUnbreakable = true;
        this._recordHistorySelection();
        this.dispatchEvent(new Event('historyStep'));
        this.multiselectionRefresh();
    }
    // apply changes according to some records
    historyApply(records) {
        for (const record of records) {
            if (record.type === 'characterData') {
                const node = this.idFind(record.id);
                if (node) {
                    node.textContent = record.text;
                }
            } else if (record.type === 'attributes') {
                const node = this.idFind(record.id);
                if (node) {
                    this._safeSetAttribute(node, record.attributeName, record.value);
                }
            } else if (record.type === 'remove') {
                const toremove = this.idFind(record.id);
                if (toremove) {
                    toremove.remove();
                }
            } else if (record.type === 'add') {
                let node = this.idFind(record.oid) || this.unserializeNode(record.node);
                const fakeNode = document.createElement('fake-el');
                fakeNode.appendChild(node);
                DOMPurify.sanitize(fakeNode, { IN_PLACE: true });
                node = fakeNode.childNodes[0];
                if (!node) {
                    continue;
                }
                this.idSet(node, true);

                if (record.append && this.idFind(record.append)) {
                    this.idFind(record.append).append(node);
                } else if (record.before && this.idFind(record.before)) {
                    this.idFind(record.before).before(node);
                } else if (record.after && this.idFind(record.after)) {
                    this.idFind(record.after).after(node);
                } else {
                    continue;
                }
            }
        }
    }
    historyRollback(until = 0) {
        const step = this._currentStep;
        this.observerFlush();
        this.historyRevert(step, { until });
        this.observerFlush();
        step.mutations = step.mutations.slice(0, until);
        this._toRollback = false;
    }
    /**
     * Undo a step of the history.
     *
     * this._historyStepsState is a map from it's location (index) in this.history to a state.
     * The state can be on of:
     * undefined: the position has never been undo or redo.
     * "redo": The position is considered as a redo of another.
     * "undo": The position is considered as a undo of another.
     * "consumed": The position has been undone and is considered consumed.
     */
    historyUndo() {
        // The last step is considered an uncommited draft so always revert it.
        const lastStep = this._currentStep;
        this.historyRevert(lastStep);
        // Clean the last step otherwise if no other step is created after, the
        // mutations of the revert itself will be added to the same step and
        // grow exponentially at each undo.
        lastStep.mutations = [];

        const pos = this._getNextUndoIndex();
        if (pos > 0) {
            // Consider the position consumed.
            this._historyStepsStates.set(this._historySteps[pos].id, 'consumed');
            this.historyRevert(this._historySteps[pos]);
            this.historyStep(true);
            // Consider the last position of the history as an undo.
            const undoStep = this._historySteps[this._historySteps.length - 1];
            this._historyStepsStates.set(undoStep.id, 'undo');
            this.dispatchEvent(new Event('historyUndo'));
        }
    }
    /**
     * Redo a step of the history.
     *
     * @see historyUndo
     */
    historyRedo() {
        const pos = this._getNextRedoIndex();
        if (pos > 0) {
            this._historyStepsStates.set(this._historySteps[pos].id, 'consumed');
            this.historyRevert(this._historySteps[pos]);
            this.historySetSelection(this._historySteps[pos]);
            this.historyStep(true);
            const lastStep = this._historySteps[this._historySteps.length - 1];
            this._historyStepsStates.set(lastStep.id, 'redo');
            this.dispatchEvent(new Event('historyRedo'));
        }
    }
    /**
     * Check wether undoing is possible.
     */
    historyCanUndo() {
        return this._getNextUndoIndex() > 0;
    }
    /**
     * Check wether redoing is possible.
     */
    historyCanRedo() {
        return this._getNextRedoIndex() > 0;
    }
    historySize() {
        return this._historySteps.length;
    }

    historyRevert(step, { until = 0, sideEffect = true } = {} ) {
        // apply dom changes by reverting history steps
        for (let i = step.mutations.length - 1; i >= until; i--) {
            const mutation = step.mutations[i];
            if (!mutation) {
                break;
            }
            switch (mutation.type) {
                case 'characterData': {
                    const node = this.idFind(mutation.id);
                    if (node) node.textContent = mutation.oldValue;
                    break;
                }
                case 'attributes': {
                    const node = this.idFind(mutation.id);
                    if (node) {
                        if (mutation.oldValue) {
                            this._safeSetAttribute(node, mutation.attributeName, mutation.oldValue);
                        } else {
                            node.removeAttribute(mutation.attributeName);
                        }
                    }
                    break;
                }
                case 'remove': {
                    let nodeToRemove = this.idFind(mutation.id);
                    if (!nodeToRemove) {
                        nodeToRemove = this.unserializeNode(mutation.node);
                        const fakeNode = document.createElement('fake-el');
                        fakeNode.appendChild(nodeToRemove);
                        DOMPurify.sanitize(fakeNode, { IN_PLACE: true });
                        nodeToRemove = fakeNode.childNodes[0];
                        if (!nodeToRemove) {
                            continue;
                        }
                        this.idSet(nodeToRemove);
                    }
                    if (mutation.nextId && this.idFind(mutation.nextId)) {
                        const node = this.idFind(mutation.nextId);
                        node && node.before(nodeToRemove);
                    } else if (mutation.previousId && this.idFind(mutation.previousId)) {
                        const node = this.idFind(mutation.previousId);
                        node && node.after(nodeToRemove);
                    } else {
                        const node = this.idFind(mutation.parentId);
                        node && node.append(nodeToRemove);
                    }
                    break;
                }
                case 'add': {
                    const node = this.idFind(mutation.id);
                    if (node) {
                        node.remove();
                    }
                }
            }
        }
        if (sideEffect) {
            this._activateContenteditable();
            this.historySetSelection(step);
            this.dispatchEvent(new Event('historyRevert'));
        }
    }
    /**
     * Place the selection on the last known selection position from the history
     * steps.
     *
     * @param {boolean} [limitToEditable=false] When true returns the latest selection that
     *     happened within the editable.
     * @returns {boolean}
     */
    historyResetLatestComputedSelection(limitToEditable) {
        const computedSelection = limitToEditable
            ? this._latestComputedSelectionInEditable
            : this._latestComputedSelection;
        if (computedSelection && computedSelection.anchorNode) {
            const anchorNode = this.idFind(computedSelection.anchorNode.oid);
            const focusNode = this.idFind(computedSelection.focusNode.oid) || anchorNode;
            if (anchorNode) {
                setSelection(
                    anchorNode,
                    computedSelection.anchorOffset,
                    focusNode,
                    computedSelection.focusOffset,
                );
            }
        }
    }
    historySetSelection(step) {
        if (step.selection && step.selection.anchorNodeOid) {
            const anchorNode = this.idFind(step.selection.anchorNodeOid);
            const focusNode = this.idFind(step.selection.focusNodeOid) || anchorNode;
            if (anchorNode) {
                setSelection(
                    anchorNode,
                    step.selection.anchorOffset,
                    focusNode,
                    step.selection.focusOffset !== undefined
                        ? step.selection.focusOffset
                        : step.selection.anchorOffset,
                    false,
                );
            }
        }
    }
    unbreakableStepUnactive() {
        this._toRollback =
            this._toRollback === UNBREAKABLE_ROLLBACK_CODE ? false : this._toRollback;
        this._checkStepUnbreakable = false;
    }
    historyPauseSteps() {
        this._historyStepsActive = false;
    }
    historyUnpauseSteps() {
        this._historyStepsActive = true;
    }
    _historyClean() {
        this._historySteps = [];
        this._currentStep = {
            selection: {
                anchorNodeOid: undefined,
                anchorOffset: undefined,
                focusNodeOid: undefined,
                focusOffset: undefined,
            },
            mutations: [],
            id: undefined,
            clientId: undefined,
        };
        this._historyStepsStates = new Map();
    }
    _historyGetSnapshotStep() {
        return {
            selection: {
                anchorNode: undefined,
                anchorOffset: undefined,
                focusNode: undefined,
                focusOffset: undefined,
            },
            mutations: Array.from(this.editable.childNodes).map(node => ({
                type: 'add',
                append: 1,
                id: node.oid,
                node: this.serializeNode(node),
            })),
            id: this._generateId(),
            clientId: this.clientId,
            previousStepId: undefined,
        };
    }
    _historyMakeSnapshot() {
        if (
            !this._lastSnapshotHistoryLength ||
            this._lastSnapshotHistoryLength < this._historySteps.length
        ) {
            this._lastSnapshotHistoryLength = this._historySteps.length;
            const step = this._historyGetSnapshotStep();
            step.id = this._historySteps[this._historySteps.length - 1].id;
            const snapshot = {
                time: Date.now(),
                step: step,
            };
            this._historySnapshots = [snapshot, this._historySnapshots[0]];
        }
    }
    /**
     * Insert a step from another collaborator.
     */
    _historyAddExternalStep(newStep) {
        let index = this._historySteps.length - 1;
        while (index >= 0 && this._historySteps[index].id !== newStep.previousStepId) {
            // Skip steps that are already in the list.
            if (this._historySteps[index].id === newStep.id) {
                return;
            }
            index--;
        }

        // When the previousStepId is not present in the this._historySteps it
        // could be either:
        // - the previousStepId is before a snapshot of the same history
        // - the previousStepId has not been received because clients were
        //   disconnected at that time
        // - the previousStepId is in another history (in case two totally
        //   differents this._historySteps (but it should not arise)).
        if (index < 0) {
            if (this.options.onHistoryMissingParentSteps) {
                const historySteps = this._historySteps;
                let index = historySteps.length - 1;
                // Get the last known step that we are sure the missing step
                // client has. It could either be a step that has the same
                // clientId or the first step.
                while(index !== 0) {
                    if (historySteps[index].clientId === newStep.clientId) {
                        break;
                    }
                    index--;
                }
                const fromStepId = historySteps[index].id;
                this.options.onHistoryMissingParentSteps({
                    step: newStep,
                    fromStepId: fromStepId,
                });
            }
            return;
        }

        let currentIndex;
        let concurentSteps = [];
        index++;
        while (index < this._historySteps.length) {
            if (this._historySteps[index].previousStepId === newStep.previousStepId) {
                if (this._historySteps[index].id.localeCompare(newStep.id) === 1) {
                    currentIndex = index;
                    break;
                } else {
                    concurentSteps = [this._historySteps[index].id];
                }
            } else {
                if (concurentSteps.includes(this._historySteps[index].previousStepId)) {
                    concurentSteps.push(this._historySteps[index].id);
                } else {
                    currentIndex = index;
                    break;
                }
            }
            index++;
        }
        currentIndex = typeof currentIndex !== 'undefined' ? currentIndex : index;

        const stepsAfterNewStep = this._historySteps.slice(index);

        for (const stepToRevert of stepsAfterNewStep.slice().reverse()) {
            this.historyRevert(stepToRevert, { sideEffect: false });
        }
        this.historyApply(newStep.mutations);
        this._historySteps.splice(index, 0, newStep);
        for (const stepToApply of stepsAfterNewStep) {
            this.historyApply(stepToApply.mutations);
        }
    }

    onExternalHistorySteps(newSteps) {
        this.observerUnactive();
        this._computeHistorySelection();

        for (const newStep of newSteps) {
            this._historyAddExternalStep(newStep);
        }

        this.observerActive();
        this.historyResetLatestComputedSelection();
        this._handleCommandHint();
        this.multiselectionRefresh();
    }

    // Multi selection
    // -------------------------------------------------------------------------

    onExternalMultiselectionUpdate(selection) {
        this._multiselectionDisplayClient(selection);
        const { clientId } = selection;
        if (this._collabSelectionInfos.has(clientId)) {
            this._collabSelectionInfos.get(clientId).selection = selection;
        } else {
            this._collabSelectionInfos.set(clientId, { selection });
        }
    }

    multiselectionRefresh() {
        this._collabSelectionsContainer.innerHTML = '';
        for (const { selection } of this._collabSelectionInfos.values()) {
            this._multiselectionDisplayClient(selection);
        }
    }

    _multiselectionDisplayClient({ selection, color, clientId, clientName = 'Anonyme' }) {
        let clientRects;

        const anchorNode = this.idFind(selection.anchorNodeOid);
        const focusNode = this.idFind(selection.focusNodeOid);
        if (!anchorNode || !focusNode) {
            return;
        }

        const direction = getCursorDirection(
            anchorNode,
            selection.anchorOffset,
            focusNode,
            selection.focusOffset,
        );
        const range = new Range();
        try {
            if (direction === DIRECTIONS.RIGHT) {
                range.setStart(anchorNode, selection.anchorOffset);
                range.setEnd(focusNode, selection.focusOffset);
            } else {
                range.setStart(focusNode, selection.focusOffset);
                range.setEnd(anchorNode, selection.anchorOffset);
            }

            clientRects = Array.from(range.getClientRects());
        } catch (e) {
            // Changes in the dom might prevent the range to be instantiated
            // (because of a removed node for example), in which case we ignore
            // the range.
            clientRects = [];
        }
        if (!clientRects.length) {
            return;
        }

        // Draw rects (in case the selection is not collapsed).
        const containerRect = this._collabSelectionsContainer.getBoundingClientRect();
        const indicators = clientRects.map(({ x, y, width, height }) => {
            const rectElement = this.document.createElement('div');
            rectElement.style = `
                position: absolute;
                top: ${y - containerRect.y}px;
                left: ${x - containerRect.x}px;
                width: ${width}px;
                height: ${height}px;
                background-color: ${color};
                opacity: 0.25;
                pointer-events: none;
            `;
            rectElement.setAttribute('data-selection-client-id', clientId);
            return rectElement;
        });

        // Draw carret.
        const caretElement = this.document.createElement('div');
        caretElement.style = `border-left: 2px solid ${color}; position: absolute;`;
        caretElement.setAttribute('data-selection-client-id', clientId);
        caretElement.className = 'oe-collaboration-caret';

        // Draw carret top square.
        const caretTopSquare = this.document.createElement('div');
        caretTopSquare.className = 'oe-collaboration-caret-top-square';
        caretTopSquare.style['background-color'] = color;
        caretTopSquare.setAttribute('data-client-name', clientName);
        caretElement.append(caretTopSquare);

        if (clientRects.length) {
            if (direction === DIRECTIONS.LEFT) {
                const rect = clientRects[0];
                caretElement.style.height = `${rect.height * 1.2}px`;
                caretElement.style.top = `${rect.y - containerRect.y}px`;
                caretElement.style.left = `${rect.x - containerRect.x}px`;
            } else {
                const rect = peek(clientRects);
                caretElement.style.height = `${rect.height * 1.2}px`;
                caretElement.style.top = `${rect.y - containerRect.y}px`;
                caretElement.style.left = `${rect.right - containerRect.x}px`;
            }
        }
        this._multiselectionRemoveClient(clientId);
        this._collabSelectionsContainer.append(caretElement, ...indicators);
    }

    multiselectionRemove(clientId) {
        this._collabSelectionInfos.delete(clientId);
        this._multiselectionRemoveClient(clientId);
    }

    _multiselectionRemoveClient(clientId) {
        const elements = this._collabSelectionsContainer.querySelectorAll(
            `[data-selection-client-id="${clientId}"]`,
        );
        for (const element of elements) {
            element.remove();
        }
    }

    /**
     * Same as @see _applyCommand, except that also simulates all the
     * contenteditable behaviors we let happen, e.g. the backspace handling
     * we then rollback.
     *
     * TODO this uses document.execCommand (which is deprecated) and relies on
     * the fact that using a command through it leads to the same result as
     * executing that command through a user keyboard on the unaltered editable
     * section with standard contenteditable attribute. This is already a huge
     * assomption.
     *
     * @param {string} method
     * @returns {?}
     */
    execCommand(...args) {
        this._computeHistorySelection();
        return this._applyCommand(...args);
    }

    /**
     * Find all descendants of `element` with a `data-call` attribute and bind
     * them on mousedown to the execution of the command matching that
     * attribute.
     */
    bindExecCommand(element) {
        for (const buttonEl of element.querySelectorAll('[data-call]')) {
            buttonEl.addEventListener('mousedown', ev => {
                const sel = this.document.getSelection();
                if (sel.anchorNode && ancestors(sel.anchorNode).includes(this.editable)) {
                    this.execCommand(buttonEl.dataset.call, buttonEl.dataset.arg1);

                    ev.preventDefault();
                    this._updateToolbar();
                }
            });
        }
    }

    //--------------------------------------------------------------------------
    // Private
    //--------------------------------------------------------------------------

    _removeDomListener() {
        for (const [element, eventName, boundCallback] of this._domListeners) {
            element.removeEventListener(eventName, boundCallback);
        }
        this._domListeners = [];
    }

    // EDITOR COMMANDS
    // ===============

    deleteRange(sel) {
        let range = getDeepRange(this.editable, {
            sel,
            splitText: true,
            select: true,
            correctTripleClick: true,
        });
        if (!range) return;
        let start = range.startContainer;
        let end = range.endContainer;
        // Let the DOM split and delete the range.
        const doJoin = closestBlock(start) !== closestBlock(range.commonAncestorContainer);
        let next = nextLeaf(end, this.editable);
        const splitEndTd = closestElement(end, 'td') && end.nextSibling;
        const contents = range.extractContents();
        setSelection(start, nodeSize(start));
        range = getDeepRange(this.editable, { sel });
        // Restore unremovables removed by extractContents.
        [...contents.querySelectorAll('*')].filter(isUnremovable).forEach(n => {
            closestBlock(range.endContainer).after(n);
            n.textContent = '';
        });
        // Restore table contents removed by extractContents.
        const tds = [...contents.querySelectorAll('td')].filter(n => !closestElement(n, 'table'));
        let currentFragmentTr, currentTr;
        const currentTd = closestElement(range.endContainer, 'td');
        tds.forEach((td, i) => {
            const parentFragmentTr = closestElement(td, 'tr');
            // Skip the first and the last partially selected TD.
            if (i && !(splitEndTd && i === tds.length - 1)) {
                if (parentFragmentTr !== currentFragmentTr) {
                    currentTr = currentTr
                        ? currentTr.nextElementSibling
                        : closestElement(range.endContainer, 'tr').nextElementSibling;
                }
                currentTr ? currentTr.prepend(td) : currentTd.after(td);
            }
            currentFragmentTr = parentFragmentTr;
            td.textContent = '';
        });
        this.observerFlush();
        this._toRollback = false; // Errors caught with observerFlush were already handled.
        // If the end container was fully selected, extractContents may have
        // emptied it without removing it. Ensure it's gone.
        const isRemovableInvisible = (node, noBlocks = true) =>
            !isVisible(node, noBlocks) && !isUnremovable(node) && node.nodeName !== 'A';
        const endIsStart = end === start;
        while (end && isRemovableInvisible(end, false) && !end.contains(range.endContainer)) {
            const parent = end.parentNode;
            end.remove();
            end = parent;
        }
        // Same with the start container
        while (
            start &&
            isRemovableInvisible(start) &&
            !(endIsStart && start.contains(range.startContainer))
        ) {
            const parent = start.parentNode;
            start.remove();
            start = parent;
        }
        // Ensure empty blocks be given a <br> child.
        if (start) {
            fillEmpty(closestBlock(start));
        }
        fillEmpty(closestBlock(range.endContainer));
        // Ensure trailing space remains visible.
        const joinWith = range.endContainer;
        const joinSibling = joinWith && joinWith.nextSibling;
        const oldText = joinWith.textContent;
        const hasSpaceAfter = joinSibling && joinSibling.textContent.startsWith(' ');
        const shouldPreserveSpace = (doJoin || hasSpaceAfter) && joinWith && oldText.endsWith(' ');
        if (shouldPreserveSpace) {
            joinWith.textContent = oldText.replace(/ $/, '\u00A0');
            setSelection(joinWith, nodeSize(joinWith));
        }
        // Rejoin blocks that extractContents may have split in two.
        while (
            doJoin &&
            next &&
            !(next.previousSibling && next.previousSibling === joinWith) &&
            this.editable.contains(next)
        ) {
            const restore = preserveCursor(this.document);
            this.observerFlush();
            const res = this._protect(() => {
                next.oDeleteBackward();
                if (!this.editable.contains(joinWith)) {
                    this._toRollback = UNREMOVABLE_ROLLBACK_CODE; // tried to delete too far -> roll it back.
                } else {
                    next = firstLeaf(next);
                }
            }, this._currentStep.mutations.length);
            if ([UNBREAKABLE_ROLLBACK_CODE, UNREMOVABLE_ROLLBACK_CODE].includes(res)) {
                restore();
                break;
            }
        }
        next = joinWith && joinWith.nextSibling;
        if (
            shouldPreserveSpace &&
            !(next && next.nodeType === Node.TEXT_NODE && next.textContent.startsWith(' '))
        ) {
            // Restore the text we modified in order to preserve trailing space.
            joinWith.textContent = oldText;
            setSelection(joinWith, nodeSize(joinWith));
        }
        if (joinWith) {
            const el = closestElement(joinWith);
            const { zws } = fillEmpty(el);
            if (zws) {
                setSelection(zws, 0, zws, nodeSize(zws));
            }
        }
    }

    /**
     * Displays the text colors (foreground ink and background highlight)
     * based on the current text cursor position. For gradients, displays
     * the average color of the gradient.
     *
     * @param {object} [params]
     * @param {string} [params.foreColor] - forces the 'foreColor' in the
     *     toolbar instead of determining it from the cursor position
     * @param {string} [params.hiliteColor] - forces the 'hiliteColor' in the
     *     toolbar instead of determining it from the cursor position
     */
    updateColorpickerLabels(params = {}) {
        function hexFromColor(color) {
            if (isColorGradient(color)) {
                // For gradients, compute the average color
                color = color.match(/gradient(.*)/)[0];
                let r = 0, g = 0, b = 0, count = 0;
                for (const entry of color.matchAll(/rgba?\((\d+),\s*(\d+),\s*(\d+)(?:,\s*(\d+(?:\.\d+)?))?\)/g)) {
                    count++;
                    r += parseInt(entry[1], 10);
                    g += parseInt(entry[2], 10);
                    b += parseInt(entry[3], 10);
                }
                color = `rgb(${Math.round(r / count)}, ${Math.round(g / count)}, ${Math.round(b / count)})`;
            }
            return rgbToHex(color);
        }
        let foreColor = params.foreColor;
        let hiliteColor = params.hiliteColor;

        // Determine colors at cursor position
        const sel = this.document.getSelection();
        if (sel.rangeCount && (!foreColor || !hiliteColor)) {
            const endContainer = closestElement(sel.getRangeAt(0).endContainer);
            const computedStyle = getComputedStyle(endContainer);
            const backgroundImage = computedStyle.backgroundImage;
            const hasGradient = isColorGradient(backgroundImage);
            const hasTextGradientClass = endContainer.classList.contains('text-gradient');
            if (!foreColor) {
                if (hasGradient && hasTextGradientClass) {
                    foreColor = backgroundImage;
                } else {
                    foreColor = document.queryCommandValue('foreColor');
                }
            }
            if (!hiliteColor) {
                if (hasGradient && !hasTextGradientClass) {
                    hiliteColor = backgroundImage;
                } else {
                    hiliteColor = computedStyle.backgroundColor;
                }
            }
        }

        // display colors in toolbar buttons
        foreColor = hexFromColor(foreColor);
        this.toolbar.style.setProperty('--fore-color', foreColor);
        const foreColorInput = this.toolbar.querySelector('#foreColor input');
        if (foreColorInput) {
            foreColorInput.value = foreColor;
        }

        hiliteColor = hexFromColor(hiliteColor);
        this.toolbar.style.setProperty('--hilite-color', hiliteColor);
        const hiliteColorInput = this.toolbar.querySelector('#hiliteColor input');
        if (hiliteColorInput) {
            hiliteColorInput.value = hiliteColor.length <= 7 ? hiliteColor : hexFromColor(hiliteColor);
        }
    }

    /**
     * Applies the given command to the current selection. This does *NOT*:
     * 1) update the history cursor
     * 2) protect the unbreakables or unremovables
     * 3) sanitize the result
     * 4) create new history entry
     * 5) follow the exact same operations that would be done following events
     *    that would lead to that command
     *
     * For points 1 -> 4, @see _applyCommand
     * For points 1 -> 5, @see execCommand
     *
     * @private
     * @param {string} method
     * @returns {?}
     */
    _applyRawCommand(method, ...args) {
        const sel = this.document.getSelection();
        if (
            !this.editable.contains(sel.anchorNode) ||
            (sel.anchorNode !== sel.focusNode && !this.editable.contains(sel.focusNode))
        ) {
            // Do not apply commands out of the editable area.
            return false;
        }
        if (!sel.isCollapsed && BACKSPACE_FIRST_COMMANDS.includes(method)) {
            this.deleteRange(sel);
            if (BACKSPACE_ONLY_COMMANDS.includes(method)) {
                return true;
            }
        }
        if (editorCommands[method]) {
            return editorCommands[method](this, ...args);
        }
        if (method.startsWith('justify')) {
            const mode = method.split('justify').join('').toLocaleLowerCase();
            return this._align(mode === 'full' ? 'justify' : mode);
        }
        return sel.anchorNode[method](sel.anchorOffset, ...args);
    }

    /**
     * Same as @see _applyRawCommand but adapt history, protects unbreakables
     * and removables and sanitizes the result.
     *
     * @private
     * @param {string} method
     * @returns {?}
     */
    _applyCommand(...args) {
        this._recordHistorySelection(true);
        const result = this._protect(() => this._applyRawCommand(...args));
        this.sanitize();
        this.historyStep();
        return result;
    }
    /**
     * @private
     * @param {function} callback
     * @param {number} [rollbackCounter]
     * @returns {?}
     */
    _protect(callback, rollbackCounter) {
        try {
            const result = callback.call(this);
            this.observerFlush();
            if (this._toRollback) {
                const torollbackCode = this._toRollback;
                this.historyRollback(rollbackCounter);
                return torollbackCode; // UNBREAKABLE_ROLLBACK_CODE || UNREMOVABLE_ROLLBACK_CODE
            } else {
                return result;
            }
        } catch (error) {
            if (error === UNBREAKABLE_ROLLBACK_CODE || error === UNREMOVABLE_ROLLBACK_CODE) {
                this.historyRollback(rollbackCounter);
                return error;
            } else {
                throw error;
            }
        }
    }
    _resetContenteditableLinks() {
        if (this._fixLinkMutatedElements) {
            for (const element of this._fixLinkMutatedElements.wasContenteditableTrue) {
                element.setAttribute('contenteditable', 'true');
            }
            for (const element of this._fixLinkMutatedElements.wasContenteditableFalse) {
                element.setAttribute('contenteditable', 'false');
            }
            for (const element of this._fixLinkMutatedElements.wasContenteditableNull) {
                element.removeAttribute('contenteditable');
            }
        }
    }
    _activateContenteditable() {
        this.editable.setAttribute('contenteditable', this.options.isRootEditable);

        for (const node of this.options.getContentEditableAreas()) {
            if (!node.isContentEditable) {
                node.setAttribute('contenteditable', true);
            }
        }
    }
    _stopContenteditable() {
        if (this.options.isRootEditable) {
            this.editable.setAttribute('contenteditable', !this.options.isRootEditable);
        }
        for (const node of this.options.getContentEditableAreas()) {
            if (node.getAttribute('contenteditable') === 'true') {
                node.setAttribute('contenteditable', false);
            }
        }
    }

    // HISTORY
    // =======

    /**
     * @private
     * @returns {Object}
     */
    _computeHistorySelection() {
        const sel = this.document.getSelection();
        if (!sel.anchorNode) {
            return this._latestComputedSelection;
        }
        this._latestComputedSelection = {
            anchorNode: sel.anchorNode,
            anchorOffset: sel.anchorOffset,
            focusNode: sel.focusNode,
            focusOffset: sel.focusOffset,
        };
        if (this._isSelectionInEditable(sel)) {
            this._latestComputedSelectionInEditable = this._latestComputedSelection;
        }
        return this._latestComputedSelection;
    }
    /**
     * @private
     * @param {boolean} [useCache=false]
     */
    _recordHistorySelection(useCache = false) {
        this._currentStep.selection =
            serializeSelection(
                useCache ? this._latestComputedSelection : this._computeHistorySelection(),
            ) || {};
    }
    /**
     * Get the step index in the history to undo.
     * Return -1 if no undo index can be found.
     */
    _getNextUndoIndex() {
        // Go back to first step that can be undone ("redo" or undefined).
        for (let index = this._historySteps.length - 1; index >= 0; index--) {
            if (
                this._historySteps[index] &&
                this._historySteps[index].clientId === this._collabClientId
            ) {
                const state = this._historyStepsStates.get(this._historySteps[index].id);
                if (state === 'redo' || !state) {
                    return index;
                }
            }
        }
        // There is no steps left to be undone, return an index that does not
        // point to any step
        return -1;
    }
    /**
     * Get the step index in the history to redo.
     * Return -1 if no redo index can be found.
     */
    _getNextRedoIndex() {
        // We cannot redo more than what is consumed.
        // Check if we have no more "consumed" than "redo" until we get to an
        // "undo"
        let totalConsumed = 0;
        for (let index = this._historySteps.length - 1; index >= 0; index--) {
            if (
                this._historySteps[index] &&
                this._historySteps[index].clientId === this._collabClientId
            ) {
                const state = this._historyStepsStates.get(this._historySteps[index].id);
                switch (state) {
                    case 'undo':
                        return totalConsumed <= 0 ? index : -1;
                    case 'redo':
                        totalConsumed -= 1;
                        break;
                    case 'consumed':
                        totalConsumed += 1;
                        break;
                    default:
                        return -1;
                }
            }
        }
        return -1;
    }

    // COMMAND BAR
    // ===========

    _createCommandBar() {
        this.options.noScrollSelector = this.options.noScrollSelector || 'body';

        const revertHistoryBeforeCommandbar = () => {
            const lastStep = this._currentStep;
            this.historyRevert(lastStep);
            let stepIndex = this._historySteps.length - 1;
            while (stepIndex > this._beforeCommandbarStepIndex) {
                const step = this._historySteps[stepIndex];
                const stepState = this._historyStepsStates.get(step.id);
                if (step.clientId === this._collabClientId && stepState !== 'consumed') {
                    this.historyRevert(this._historySteps[stepIndex]);
                    this._historyStepsStates.set(step.id, 'consumed');
                }
                stepIndex--;
            }
            this.historyStep(true);
            setTimeout(() => {
                this.editable.focus();
                getDeepRange(this.editable, { select: true });
            });
        };

        this.commandbarTablePicker = new TablePicker({
            document: this.document,
            floating: true,
        });

        document.body.appendChild(this.commandbarTablePicker.el);

        this.commandbarTablePicker.addEventListener('cell-selected', ev => {
            this.execCommand('insertTable', {
                rowNumber: ev.detail.rowNumber,
                colNumber: ev.detail.colNumber,
            });
        });

        const mainCommands = [
            {
                groupName: 'Basic blocks',
                title: 'Heading 1',
                description: 'Big section heading.',
                fontawesome: 'fa-header',
                callback: () => {
                    this.execCommand('setTag', 'H1');
                },
            },
            {
                groupName: 'Basic blocks',
                title: 'Heading 2',
                description: 'Medium section heading.',
                fontawesome: 'fa-header',
                callback: () => {
                    this.execCommand('setTag', 'H2');
                },
            },
            {
                groupName: 'Basic blocks',
                title: 'Heading 3',
                description: 'Small section heading.',
                fontawesome: 'fa-header',
                callback: () => {
                    this.execCommand('setTag', 'H3');
                },
            },
            {
                groupName: 'Basic blocks',
                title: 'Text',
                description: 'Paragraph block.',
                fontawesome: 'fa-paragraph',
                callback: () => {
                    this.execCommand('setTag', 'P');
                },
            },
            {
                groupName: 'Basic blocks',
                title: 'Bulleted list',
                description: 'Create a simple bulleted list.',
                fontawesome: 'fa-list-ul',
                callback: () => {
                    this.execCommand('toggleList', 'UL');
                },
            },
            {
                groupName: 'Basic blocks',
                title: 'Numbered list',
                description: 'Create a list with numbering.',
                fontawesome: 'fa-list-ol',
                callback: () => {
                    this.execCommand('toggleList', 'OL');
                },
            },
            {
                groupName: 'Basic blocks',
                title: 'Checklist',
                description: 'Track tasks with a checklist.',
                fontawesome: 'fa-check-square-o',
                callback: () => {
                    this.execCommand('toggleList', 'CL');
                },
            },
            {
                groupName: 'Basic blocks',
                title: 'Separator',
                description: 'Insert an horizontal rule separator.',
                fontawesome: 'fa-minus',
                callback: () => {
                    this.execCommand('insertHorizontalRule');
                },
            },
            {
                groupName: 'Basic blocks',
                title: 'Table',
                description: 'Insert a table.',
                fontawesome: 'fa-table',
                callback: () => {
                    this.commandbarTablePicker.show();
                },
            },
        ];
        // Translate the command title and description if a translate function
        // is provided.
        for (const command of mainCommands) {
            command.title = this.options._t(command.title);
            command.description = this.options._t(command.description);
        }
        this.commandBar = new Powerbox({
            editable: this.editable,
            document: this.document,
            getContextFromParentRect: this.options.getContextFromParentRect,
            _t: this.options._t,
            onShow: () => {
                this.commandbarTablePicker.hide();
            },
            shouldActivate: () => !!this.options.getPowerboxElement(),
            onActivate: () => {
                this._beforeCommandbarStepIndex = this._historySteps.length - 1;
                this.observerUnactive();
                for (const element of document.querySelectorAll(this.options.noScrollSelector)) {
                    element.classList.add('oe-noscroll');
                }
                for (const element of this.document.querySelectorAll(
                    this.options.noScrollSelector,
                )) {
                    element.classList.add('oe-noscroll');
                }
                this.observerActive();
            },
            preValidate: () => {
                revertHistoryBeforeCommandbar();
            },
            postValidate: () => {
                this.historyStep(true);
            },
            onStop: () => {
                this.observerUnactive();
                for (const element of document.querySelectorAll('.oe-noscroll')) {
                    element.classList.remove('oe-noscroll');
                }
                for (const element of this.document.querySelectorAll('.oe-noscroll')) {
                    element.classList.remove('oe-noscroll');
                }
                this.observerActive();
            },
            commands: [...mainCommands, ...(this.options.commands || [])],
        });
    }

    // TOOLBAR
    // =======

    /**
     * @private
     * @param {boolean} [show]
     */
    _updateToolbar(show) {
        if (!this.options.toolbar) return;
        if (!this.options.autohideToolbar && this.toolbar.style.visibility !== 'visible') {
            this.toolbar.style.visibility = 'visible';
        }

        const sel = this.document.getSelection();
        if (!sel.anchorNode) {
            show = false;
        }
        if (this.options.autohideToolbar) {
            if (show !== undefined && !this.isMobile) {
                this.toolbar.style.visibility = show ? 'visible' : 'hidden';
            }
            if (show === false) {
                return;
            }
        }
        const paragraphDropdownButton = this.toolbar.querySelector('#paragraphDropdownButton');
        for (const commandState of [
            'italic',
            'underline',
            'strikeThrough',
            'justifyLeft',
            'justifyRight',
            'justifyCenter',
            'justifyFull',
        ]) {
            const isStateTrue = this.document.queryCommandState(commandState);
            const button = this.toolbar.querySelector('#' + commandState);
            if (commandState.startsWith('justify')) {
                if (paragraphDropdownButton) {
                    button.classList.toggle('active', isStateTrue);
                    const direction = commandState.replace('justify', '').toLowerCase();
                    const newClass = `fa-align-${direction === 'full' ? 'justify' : direction}`;
                    paragraphDropdownButton.classList.toggle(newClass, isStateTrue);
                }
            } else if (button) {
                button.classList.toggle('active', isStateTrue);
            }
        }
        if (sel.rangeCount) {
            const closestStartContainer = closestElement(sel.getRangeAt(0).startContainer, '*');
            const selectionStartStyle = getComputedStyle(closestStartContainer);

            // queryCommandState('bold') does not take stylesheets into account
            const button = this.toolbar.querySelector('#bold');
            button.classList.toggle('active', isBold(closestStartContainer));

            const fontSizeValue = this.toolbar.querySelector('#fontSizeCurrentValue');
            if (fontSizeValue) {
                fontSizeValue.textContent = /\d+/.exec(selectionStartStyle.fontSize).pop();
            }
            const table = getInSelection(this.document, 'table');
            const toolbarButton = this.toolbar.querySelector('.toolbar-edit-table');
            if (toolbarButton) {
                this.toolbar.querySelector('.toolbar-edit-table').style.display = table
                    ? 'block'
                    : 'none';
            }
        }
        this.updateColorpickerLabels();

        const block = closestBlock(sel.anchorNode);
        let activeLabel = undefined;
        for (const [style, tag, isList] of [
            ['paragraph', 'P', false],
            ['pre', 'PRE', false],
            ['heading1', 'H1', false],
            ['heading2', 'H2', false],
            ['heading3', 'H3', false],
            ['heading4', 'H4', false],
            ['heading5', 'H5', false],
            ['heading6', 'H6', false],
            ['blockquote', 'BLOCKQUOTE', false],
            ['unordered', 'UL', true],
            ['ordered', 'OL', true],
            ['checklist', 'CL', true],
        ]) {
            const button = this.toolbar.querySelector('#' + style);
            if (button && !block) {
                button.classList.toggle('active', false);
            } else if (button) {
                const isActive = isList
                    ? block.tagName === 'LI' && getListMode(block.parentElement) === tag
                    : block.tagName === tag;
                button.classList.toggle('active', isActive);

                if (!isList && isActive) {
                    activeLabel = button.textContent;
                }
            }
        }
        if (!activeLabel) {
            // If no element from the text style dropdown was marked as active,
            // mark the paragraph one as active and use its label.
            const firstButtonEl = this.toolbar.querySelector('#paragraph');
            firstButtonEl.classList.add('active');
            activeLabel = firstButtonEl.textContent;
        }
        this.toolbar.querySelector('#style button span').textContent = activeLabel;

        const linkNode = getInSelection(this.document, 'a');
        const linkButton = this.toolbar.querySelector('#createLink');
        linkButton && linkButton.classList.toggle('active', linkNode);
        const unlinkButton = this.toolbar.querySelector('#unlink');
        unlinkButton && unlinkButton.classList.toggle('d-none', !linkNode);
        const undoButton = this.toolbar.querySelector('#undo');
        undoButton && undoButton.classList.toggle('disabled', !this.historyCanUndo());
        const redoButton = this.toolbar.querySelector('#redo');
        redoButton && redoButton.classList.toggle('disabled', !this.historyCanRedo());
        if (this.options.autohideToolbar && !this.isMobile) {
            this._positionToolbar();
        }
    }
    updateToolbarPosition() {
        if (
            this.options.autohideToolbar &&
            !this.isMobile &&
            getComputedStyle(this.toolbar).visibility === 'visible'
        ) {
            this._positionToolbar();
        }
    }
    _positionToolbar() {
        const OFFSET = 10;
        let isBottom = false;
        this.toolbar.classList.toggle('toolbar-bottom', false);
        this.toolbar.style.maxWidth = this.editable.offsetWidth - OFFSET * 2 + 'px';
        const sel = this.document.getSelection();
        const range = sel.getRangeAt(0);
        const isSelForward =
            sel.anchorNode === range.startContainer && sel.anchorOffset === range.startOffset;
        const selRect = range.getBoundingClientRect();
        const toolbarWidth = this.toolbar.offsetWidth;
        const toolbarHeight = this.toolbar.offsetHeight;
        const editorRect = this.editable.getBoundingClientRect();
        const parentContextRect = this.options.getContextFromParentRect();
        const editorLeftPos = Math.max(0, editorRect.left);
        const editorTopPos = Math.max(0, editorRect.top);
        const scrollX = this.document.defaultView.scrollX;
        const scrollY = this.document.defaultView.scrollY;

        // Get left position.
        let left = selRect.left + OFFSET;
        // Ensure the toolbar doesn't overflow the editor on the left.
        left = Math.max(editorLeftPos + OFFSET, left);
        // Ensure the toolbar doesn't overflow the editor on the right.
        left = Math.min(editorLeftPos + this.editable.offsetWidth - OFFSET - toolbarWidth, left);
        // Offset left to compensate for parent context position (eg. Iframe).
        left += parentContextRect.left;
        this.toolbar.style.left = scrollX + left + 'px';

        // Get top position.
        let top = selRect.top - toolbarHeight - OFFSET;
        // Ensure the toolbar doesn't overflow the editor on the top.
        if (top < editorTopPos) {
            // Position the toolbar below the selection.
            top = selRect.bottom + OFFSET;
            isBottom = true;
        }
        // Ensure the toolbar doesn't overflow the editor on the bottom.
        top = Math.min(editorTopPos + this.editable.offsetHeight - OFFSET - toolbarHeight, top);
        // Offset top to compensate for parent context position (eg. Iframe).
        top += parentContextRect.top;
        this.toolbar.style.top = scrollY + top + 'px';

        // Position the arrow.
        let arrowLeftPos = (isSelForward ? selRect.right : selRect.left) - left - OFFSET;
        // Ensure the arrow doesn't overflow the toolbar on the left.
        arrowLeftPos = Math.max(OFFSET, arrowLeftPos);
        // Ensure the arrow doesn't overflow the toolbar on the right.
        arrowLeftPos = Math.min(toolbarWidth - OFFSET - 20, arrowLeftPos);
        this.toolbar.style.setProperty('--arrow-left-pos', arrowLeftPos + 'px');
        if (isBottom) {
            this.toolbar.classList.toggle('toolbar-bottom', true);
            this.toolbar.style.setProperty('--arrow-top-pos', -17 + 'px');
        } else {
            this.toolbar.style.setProperty('--arrow-top-pos', toolbarHeight - 3 + 'px');
        }
    }

    // PASTING / DROPPING

    /**
     * Prepare clipboard data (text/html) for safe pasting into the editor.
     *
     * @private
     * @param {string} clipboardData
     * @returns {string}
     */
    _prepareClipboardData(clipboardData) {
        const container = document.createElement('fake-container');
        container.innerHTML = clipboardData;
        for (const child of [...container.childNodes]) {
            this._cleanForPaste(child);
        }
        return container.innerHTML;
    }
    /**
     * Clean a node for safely pasting. Cleaning an element involves unwrapping
     * its contents if it's an illegal (blacklisted or not whitelisted) element,
     * or removing its illegal attributes and classes.
     *
     * @param {Node} node
     */
    _cleanForPaste(node) {
        if (!this._isWhitelisted(node) || this._isBlacklisted(node)) {
            if (!node.matches || node.matches(CLIPBOARD_BLACKLISTS.remove.join(','))) {
                node.remove();
            } else {
                // Unwrap the illegal node's contents.
                for (const unwrappedNode of unwrapContents(node)) {
                    this._cleanForPaste(unwrappedNode);
                }
            }
        } else if (node.nodeType !== Node.TEXT_NODE) {
            // Remove all illegal attributes and classes from the node, then
            // clean its children.
            for (const attribute of [...node.attributes]) {
                if (!this._isWhitelisted(attribute)) {
                    node.removeAttribute(attribute.name);
                }
            }
            for (const klass of [...node.classList]) {
                if (!this._isWhitelisted(klass)) {
                    node.classList.remove(klass);
                }
            }
            for (const child of [...node.childNodes]) {
                this._cleanForPaste(child);
            }
        }
    }
    /**
     * Return true if the given attribute, class or node is whitelisted for
     * pasting, false otherwise.
     *
     * @private
     * @param {Attr | string | Node} item
     * @returns {boolean}
     */
    _isWhitelisted(item) {
        if (item instanceof Attr) {
            return CLIPBOARD_WHITELISTS.attributes.includes(item.name);
        } else if (typeof item === 'string') {
            return CLIPBOARD_WHITELISTS.classes.some(okClass =>
                okClass instanceof RegExp ? okClass.test(item) : okClass === item,
            );
        } else {
            return (
                item.nodeType === Node.TEXT_NODE ||
                (item.matches && item.matches(CLIPBOARD_WHITELISTS.nodes.join(',')))
            );
        }
    }
    /**
     * Return true if the given node is blacklisted for pasting, false
     * otherwise.
     *
     * @private
     * @param {Node} node
     * @returns {boolean}
     */
    _isBlacklisted(node) {
        return (
            node.nodeType !== Node.TEXT_NODE &&
            node.matches([].concat(...Object.values(CLIPBOARD_BLACKLISTS)).join(','))
        );
    }
    _safeSetAttribute(node, attributeName, attributeValue) {
        const parent = node.parentNode;
        const next = node.nextSibling;
        this.observerFlush();
        node.remove();
        this.observer.takeRecords();
        node.setAttribute(attributeName, attributeValue);
        this.observerFlush();
        DOMPurify.sanitize(node, { IN_PLACE: true });
        if (next) {
            next.before(node);
        } else if (parent) {
            parent.append(node);
        }
        this.observer.takeRecords();
    }

    //--------------------------------------------------------------------------
    // Handlers
    //--------------------------------------------------------------------------

    _onBeforeInput(ev) {
        this._lastBeforeInputType = ev.inputType;
    }

    /**
     * If backspace/delete input, rollback the operation and handle the
     * operation ourself. Needed for mobile, used for desktop for consistency.
     *
     * @private
     */
    _onInput(ev) {
        // Record the selection position that was computed on keydown or before
        // contentEditable execCommand (whatever preceded the 'input' event)
        this._recordHistorySelection(true);
        const selection = this._currentStep.selection;
        const { anchorNodeOid, anchorOffset, focusNodeOid, focusOffset } = selection || {};
        const wasCollapsed =
            !selection || (focusNodeOid === anchorNodeOid && focusOffset === anchorOffset);

        // Sometimes google chrome wrongly triggers an input event with `data`
        // being `null` on `deleteContentForward` `insertParagraph`. Luckily,
        // chrome provide the proper signal with the event `beforeinput`.
        const isChromeDeleteforward =
            ev.inputType === 'insertText' &&
            ev.data === null &&
            this._lastBeforeInputType === 'deleteContentForward';
        const isChromeInsertParagraph =
            ev.inputType === 'insertText' &&
            ev.data === null &&
            this._lastBeforeInputType === 'insertParagraph';
        if (this.keyboardType === KEYBOARD_TYPES.PHYSICAL || !wasCollapsed) {
            if (ev.inputType === 'deleteContentBackward') {
                this.historyRollback();
                ev.preventDefault();
                this._applyCommand('oDeleteBackward');
            } else if (ev.inputType === 'deleteContentForward' || isChromeDeleteforward) {
                this.historyRollback();
                ev.preventDefault();
                this._applyCommand('oDeleteForward');
            } else if (ev.inputType === 'insertParagraph' || isChromeInsertParagraph) {
                this.historyRollback();
                ev.preventDefault();
                if (this._applyCommand('oEnter') === UNBREAKABLE_ROLLBACK_CODE) {
                    this._applyCommand('oShiftEnter');
                }
            } else if (['insertText', 'insertCompositionText'].includes(ev.inputType)) {
                // insertCompositionText, courtesy of Samsung keyboard.
                const selection = this.document.getSelection();
                // Detect that text was selected and change behavior only if it is the case,
                // since it is the only text insertion case that may cause problems.
                if (anchorNodeOid !== focusNodeOid || anchorOffset !== focusOffset) {
                    ev.preventDefault();
                    this._applyRawCommand('oDeleteBackward');
                    insertText(selection, ev.data);
                    const range = selection.getRangeAt(0);
                    setSelection(range.endContainer, range.endOffset);
                }
                // Check for url after user insert a space so we won't transform an incomplete url.
                if (
                    ev.data &&
                    ev.data.includes(' ') &&
                    selection &&
                    selection.anchorNode
                    && (!this.commandBar._active ||
                        this.commandBar._currentOpenOptions.closeOnSpace !== true)
                ) {
                    this._convertUrlInElement(closestElement(selection.anchorNode));
                }
                this.sanitize();
                this.historyStep();
            } else if (ev.inputType === 'insertLineBreak') {
                this.historyRollback();
                ev.preventDefault();
                this._applyCommand('oShiftEnter');
            } else {
                this.sanitize();
                this.historyStep();
            }
        }
    }

    /**
     * @private
     */
    _onKeyDown(ev) {
        this.keyboardType =
            ev.key === 'Unidentified' ? KEYBOARD_TYPES.VIRTUAL : KEYBOARD_TYPES.PHYSICAL;
        // If the pressed key has a printed representation, the returned value
        // is a non-empty Unicode character string containing the printable
        // representation of the key. In this case, call `deleteRange` before
        // inserting the printed representation of the character.
        if (/^.$/u.test(ev.key) && !ev.ctrlKey && !ev.metaKey) {
            const selection = this.document.getSelection();
            if (selection && !selection.isCollapsed) {
                this.deleteRange(selection);
            }
        }
        if (ev.key === 'Backspace' && !ev.ctrlKey && !ev.metaKey) {
            // backspace
            // We need to hijack it because firefox doesn't trigger a
            // deleteBackward input event with a collapsed selection in front of
            // a contentEditable="false" (eg: font awesome).
            const selection = this.document.getSelection();
            if (selection.isCollapsed) {
                ev.preventDefault();
                this._applyCommand('oDeleteBackward');
            }
        } else if (ev.key === 'Tab') {
            // Tab
            const sel = this.document.getSelection();
            const closestTag = (closestElement(sel.anchorNode, 'li, table') || {}).tagName;

            if (closestTag === 'LI') {
                this._applyCommand('indentList', ev.shiftKey ? 'outdent' : 'indent');
            } else if (closestTag === 'TABLE') {
                this._onTabulationInTable(ev);
            } else if (!ev.shiftKey) {
                this.execCommand('insertText', '\u00A0 \u00A0\u00A0');
            }
            ev.preventDefault();
            ev.stopPropagation();
        } else if (IS_KEYBOARD_EVENT_UNDO(ev)) {
            // Ctrl-Z
            ev.preventDefault();
            ev.stopPropagation();
            this.historyUndo();
        } else if (IS_KEYBOARD_EVENT_REDO(ev)) {
            // Ctrl-Y
            ev.preventDefault();
            ev.stopPropagation();
            this.historyRedo();
        } else if (IS_KEYBOARD_EVENT_BOLD(ev)) {
            // Ctrl-B
            ev.preventDefault();
            ev.stopPropagation();
            this.execCommand('bold');
        }
    }
    /**
     * @private
     */
    _onSelectionChange() {
        // Compute the current selection on selectionchange but do not record it. Leave
        // that to the command execution or the 'input' event handler.
        this._computeHistorySelection();

        const selection = this.document.getSelection();
        this._updateToolbar(this._isSelectionInEditable(selection));

        if (this._currentMouseState === 'mouseup') {
            this._fixFontAwesomeSelection();
        }
        if (
            selection.rangeCount &&
            selection.getRangeAt(0) &&
            this.options.onCollaborativeSelectionChange
        ) {
            this.options.onCollaborativeSelectionChange(this.getCurrentCollaborativeSelection());
        }
    }

    /**
     * Returns true if the current selection is inside the editable.
     *
     * @private
     * @param {Object} selection
     * @returns {boolean}
     */
    _isSelectionInEditable(selection) {
        return !selection.isCollapsed &&
            this.editable.contains(selection.anchorNode) &&
            this.editable.contains(selection.focusNode);
    }
    getCurrentCollaborativeSelection() {
        const selection = this._latestComputedSelection || this._computeHistorySelection();
        if (!selection) return;
        return Object.assign({
            selection: serializeSelection(selection),
            color: this._collabSelectionColor,
            clientId: this._collabClientId,
        });
    }

    clean() {
        this.observerUnactive();
        for (const hint of document.querySelectorAll('.oe-hint')) {
            hint.classList.remove('oe-hint', 'oe-command-temporary-hint');
            hint.removeAttribute('placeholder');
        }
        this.observerActive();
    }
    /**
     * Handle the hint preview for the commandbar.
     * @private
     */
    _handleCommandHint() {
        const selectors = {
            BLOCKQUOTE: 'Empty quote',
            H1: 'Heading 1',
            H2: 'Heading 2',
            H3: 'Heading 3',
            H4: 'Heading 4',
            H5: 'Heading 5',
            H6: 'Heading 6',
            'UL LI': 'List',
            'OL LI': 'List',
            'CL LI': 'To-do',
        };

        for (const hint of document.querySelectorAll('.oe-hint')) {
            if (hint.classList.contains('oe-command-temporary-hint') || !isEmptyBlock(hint)) {
                this.observerUnactive();
                hint.classList.remove('oe-hint', 'oe-command-temporary-hint');
                hint.removeAttribute('placeholder');
                this.observerActive();
            }
        }

        for (const [selector, text] of Object.entries(selectors)) {
            for (const el of this.editable.querySelectorAll(selector)) {
                if (!this.options.isHintBlacklisted(el)) {
                    this._makeHint(el, text);
                }
            }
        }

        const block = this.options.getPowerboxElement();
        if (block) {
            this._makeHint(block, 'Type "/" for commands', true);
        }

        // placeholder hint
        if (this.editable.textContent === '' && this.options.placeholder) {
            this._makeHint(this.editable.firstChild, this.options.placeholder, true);
        }
    }
    _makeHint(block, text, temporary = false) {
        const content = block && block.innerHTML.trim();
        if (
            block &&
            (content === '' || content === '<br>') &&
            ancestors(block, this.editable).includes(this.editable)
        ) {
            this.observerUnactive();
            block.setAttribute('placeholder', text);
            block.classList.add('oe-hint');
            if (temporary) {
                block.classList.add('oe-command-temporary-hint');
            }
            this.observerActive();
        }
    }

    _fixSelectionOnContenteditableFalse() {
        // When the browser set the selection inside a node that is
        // contenteditable=false, it breaks the edition upon keystroke. Move the
        // selection so that it remain in an editable area. An example of this
        // case happend when the selection goes into a fontawesome node.

        const selection = this.document.getSelection();
        if (!selection.rangeCount) {
            return;
        }
        const range = selection.getRangeAt(0);
        const newRange = range.cloneRange();
        const startContainer = closestElement(range.startContainer);
        const endContainer = closestElement(range.endContainer);

        /**
         * Get last not editable node if the `node` is within `root` and is a
         * non editable node.
         *
         * Otherwise return `undefined`.
         *
         * Example:
         *
         * ```html
         * <div class="root" contenteditable="true">
         *     <div class="A">
         *         <div class="B" contenteditable="false">
         *             <div class="C">
         *             </div>
         *         </div>
         *     </div>
         * </div>
         * ```
         *
         * ```js
         * _getLastNotEditableAncestorOfNotEditable(document.querySelector(".C")) // return "B"
         * ```
         */
        function _getLastNotEditableAncestorOfNotEditable(node, root) {
            let currentNode = node;
            let lastEditable;
            if (!ancestors(node, root).includes(root)) {
                return;
            }
            while (currentNode && currentNode !== root) {
                if (currentNode.isContentEditable) {
                    return lastEditable;
                } else if (currentNode.isContentEditable === false) {
                    // By checking that the node is contentEditable === false,
                    // we ensure at the same time that the currentNode is a
                    // HTMLElement.
                    lastEditable = currentNode;
                }
                currentNode = currentNode.parentElement;
            }
            return lastEditable;
        }

        const startContainerNotEditable = _getLastNotEditableAncestorOfNotEditable(
            startContainer,
            this.editable,
        );
        const endContainerNotEditable = _getLastNotEditableAncestorOfNotEditable(
            endContainer,
            this.editable,
        );
        const bothNotEditable = startContainerNotEditable && endContainerNotEditable;

        if (startContainerNotEditable) {
            if (startContainerNotEditable.previousSibling) {
                newRange.setStart(
                    startContainerNotEditable.previousSibling,
                    startContainerNotEditable.previousSibling.length,
                );
                if (bothNotEditable) {
                    newRange.setEnd(
                        startContainerNotEditable.previousSibling,
                        startContainerNotEditable.previousSibling.length,
                    );
                }
            } else {
                newRange.setStart(startContainerNotEditable.parentElement, 0);
                if (bothNotEditable) {
                    newRange.setEnd(startContainerNotEditable.parentElement, 0);
                }
            }
        }
        if (!bothNotEditable && endContainerNotEditable) {
            if (endContainerNotEditable.nextSibling) {
                newRange.setEnd(endContainerNotEditable.nextSibling, 0);
            } else {
                newRange.setEnd(...endPos(endContainerNotEditable.parentElement));
            }
        }
        if (startContainerNotEditable || endContainerNotEditable) {
            selection.removeAllRanges();
            selection.addRange(newRange);
        }
    }

    _onMouseup(ev) {
        this._currentMouseState = ev.type;

        this._fixFontAwesomeSelection();

        this._fixSelectionOnContenteditableFalse();
    }

    _onMouseDown(ev) {
        this._currentMouseState = ev.type;

        // When selecting all the text within a link then triggering delete or
        // inserting a character, the cursor and insertion is outside the link.
        // To avoid this problem, we make all editable zone become uneditable
        // except the link. Then when cliking outside the link, reset the
        // editable zones.
        const link = closestElement(ev.target, 'a');
        this._resetContenteditableLinks();
        if (
            link &&
            !link.querySelector('div') &&
            !closestElement(ev.target, '.o_not_editable') &&
            link.getAttribute('contenteditable') !== 'false'
        ) {
            const editableChildren = link.querySelectorAll('[contenteditable=true]');
            this._stopContenteditable();

            this._fixLinkMutatedElements = {
                wasContenteditableTrue: [...editableChildren],
                wasContenteditableFalse: [],
                wasContenteditableNull: [],
            };
            const contentEditableAttribute = link.getAttribute('contenteditable');
            if (contentEditableAttribute === 'true') {
                this._fixLinkMutatedElements.wasContenteditableTrue.push(link);
            } else if (contentEditableAttribute === 'false') {
                this._fixLinkMutatedElements.wasContenteditableFalse.push(link);
            } else {
                this._fixLinkMutatedElements.wasContenteditableNull.push(link);
            }

            [...editableChildren, link].forEach(node => node.setAttribute('contenteditable', true));
        } else {
            this._activateContenteditable();
        }
        // Ignore any changes that might have happened before this point.
        this.observer.takeRecords();

        const node = ev.target;
        // handle checkbox lists
        if (node.tagName == 'LI' && getListMode(node.parentElement) == 'CL') {
            if (ev.offsetX < 0) {
                toggleClass(node, 'o_checked');
                ev.preventDefault();
                this.historyStep();
            }
        }
    }

    _onDocumentKeydown(ev) {
        const canUndoRedo = !['INPUT', 'TEXTAREA'].includes(this.document.activeElement.tagName);

        if (this.options.controlHistoryFromDocument && canUndoRedo) {
            if (IS_KEYBOARD_EVENT_UNDO(ev) && canUndoRedo) {
                ev.preventDefault();
                this.historyUndo();
            } else if (IS_KEYBOARD_EVENT_REDO(ev) && canUndoRedo) {
                ev.preventDefault();
                this.historyRedo();
            }
        } else {
            if (IS_KEYBOARD_EVENT_REDO(ev) || IS_KEYBOARD_EVENT_UNDO(ev)) {
                this._onKeyupResetContenteditableNodes.push(
                    ...this.editable.querySelectorAll('[contenteditable=true]'),
                );
                if (this.editable.getAttribute('contenteditable') === 'true') {
                    this._onKeyupResetContenteditableNodes.push(this.editable);
                }

                for (const node of this._onKeyupResetContenteditableNodes) {
                    this.automaticStepSkipStack();
                    node.setAttribute('contenteditable', false);
                }
            }
        }
    }

    _onDocumentKeyup() {
        if (this._onKeyupResetContenteditableNodes.length) {
            for (const node of this._onKeyupResetContenteditableNodes) {
                this.automaticStepSkipStack();
                node.setAttribute('contenteditable', true);
            }
            this._onKeyupResetContenteditableNodes = [];
        }
        this._fixSelectionOnContenteditableFalse();
    }

    _onDoumentMousedown(event) {
        if (this.toolbar && !ancestors(event.target, this.editable).includes(this.toolbar)) {
            this.toolbar.style.pointerEvents = 'none';
        }
    }

    _onDoumentMouseup() {
        if (this.toolbar) {
            this.toolbar.style.pointerEvents = 'auto';
        }
    }

    /**
     * Convert valid url text into links inside the given element.
     *
     * @param {HTMLElement} el
     */
    _convertUrlInElement(el) {
        // We will not replace url inside already existing Link element.
        if (el.tagName === 'A') {
            return;
        }

        for (let child of el.childNodes) {
            if (child.nodeType === Node.TEXT_NODE && child.length > 3) {
                const childStr = child.nodeValue;
                const matches = getUrlsInfosInString(childStr);
                if (matches.length) {
                    // We only to take care of the first match.
                    // The method `_createLinkWithUrlInTextNode` will split the text node,
                    // the other url matches will then be matched again in the nexts loops of el.childnodes.
                    this._createLinkWithUrlInTextNode(
                        child,
                        matches[0].url,
                        matches[0].index,
                        matches[0].length,
                    );
                }
            }
        }
    }

    /**
     * Create a Link in the node text based on the given data
     *
     * @param {Node} textNode
     * @param {String} url
     * @param {int} index
     * @param {int} length
     */
    _createLinkWithUrlInTextNode(textNode, url, index, length) {
        const link = this.document.createElement('a');
        link.setAttribute('href', url);
        for (const [param, value] of Object.entries(this.options.defaultLinkAttributes)) {
            link.setAttribute(param, `${value}`);
        }
        const range = this.document.createRange();
        range.setStart(textNode, index);
        range.setEnd(textNode, index + length);
        link.appendChild(range.extractContents());
        range.insertNode(link);
    }

    /**
     * Handle safe pasting of html or plain text into the editor.
     */
    _onPaste(ev) {
        ev.preventDefault();
        const clipboardData = ev.clipboardData.getData('text/html');
        if (clipboardData) {
            this.execCommand('insertHTML', this._prepareClipboardData(clipboardData));
        } else {
            const text = ev.clipboardData.getData('text/plain');
            const splitAroundUrl = text.split(URL_REGEX);
            const linkAttributes = this.options.defaultLinkAttributes || {};

            for (let i = 0; i < splitAroundUrl.length; i++) {
                // Even indexes will always be plain text, and odd indexes will always be URL.
                if (i % 2) {
                    const url = /^https?:\/\//gi.test(splitAroundUrl[i])
                        ? splitAroundUrl[i]
                        : 'https://' + splitAroundUrl[i];
                    const youtubeUrl = YOUTUBE_URL_GET_VIDEO_ID.exec(url);
                    const urlFileExtention = url.split('.').pop();
                    const baseEmbedCommand = [
                        {
                            groupName: 'paste',
                            title: 'Paste as URL',
                            description: 'Create an URL.',
                            fontawesome: 'fa-link',
                            callback: () => {
                                this.historyUndo();
                                const link = document.createElement('A');
                                link.setAttribute('href', url);
                                for (const attribute in linkAttributes) {
                                    link.setAttribute(attribute, linkAttributes[attribute]);
                                }
                                link.innerText = splitAroundUrl[i];
                                const sel = this.document.getSelection();
                                if (sel.rangeCount) {
                                    sel.getRangeAt(0).insertNode(link);
                                    sel.collapseToEnd();
                                }
                            },
                        },
                        {
                            groupName: 'paste',
                            title: 'Paste as text',
                            description: 'Simple text paste.',
                            fontawesome: 'fa-font',
                            callback: () => {},
                        },
                    ];

                    if (['jpg', 'jpeg', 'png', 'gif'].includes(urlFileExtention)) {
                        this.execCommand('insertText', splitAroundUrl[i]);
                        this.commandBar.open({
                            commands: [
                                {
                                    groupName: 'Embed',
                                    title: 'Embed Image',
                                    description: 'Embed the image in the document.',
                                    fontawesome: 'fa-image',
                                    callback: () => {
                                        this.historyUndo();
                                        const img = document.createElement('IMG');
                                        img.setAttribute('src', url);
                                        const sel = this.document.getSelection();
                                        if (sel.rangeCount) {
                                            sel.getRangeAt(0).insertNode(img);
                                            sel.collapseToEnd();
                                        }
                                    },
                                },
                            ].concat(baseEmbedCommand),
                        });
                    } else if (youtubeUrl) {
                        this.execCommand('insertText', splitAroundUrl[i]);
                        this.commandBar.open({
                            commands: [
                                {
                                    groupName: 'Embed',
                                    title: 'Embed Youtube Video',
                                    description: 'Embed the youtube video in the document.',
                                    fontawesome: 'fa-youtube-play',
                                    callback: () => {
                                        this.historyUndo();
                                        const video = document.createElement('iframe');
                                        video.setAttribute('width', '560');
                                        video.setAttribute('height', '315');
                                        video.setAttribute(
                                            'src',
                                            `https://www.youtube.com/embed/${youtubeUrl[1]}`,
                                        );
                                        video.setAttribute('title', 'YouTube video player');
                                        video.setAttribute('frameborder', '0');
                                        video.setAttribute(
                                            'allow',
                                            'accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture',
                                        );
                                        video.setAttribute('allowfullscreen', '1');
                                        const sel = this.document.getSelection();
                                        if (sel.rangeCount) {
                                            sel.getRangeAt(0).insertNode(video);
                                            sel.collapseToEnd();
                                        }
                                    },
                                },
                            ].concat(baseEmbedCommand),
                        });
                    } else {
                        const link = document.createElement('A');
                        link.setAttribute('href', url);
                        for (const attribute in linkAttributes) {
                            link.setAttribute(attribute, linkAttributes[attribute]);
                        }
                        link.innerText = splitAroundUrl[i];
                        const sel = this.document.getSelection();
                        if (sel.rangeCount) {
                            sel.getRangeAt(0).insertNode(link);
                            sel.collapseToEnd();
                        }
                    }
                } else if (splitAroundUrl[i] !== '') {
                    const textFragments = splitAroundUrl[i].split('\n');
                    let textIndex = 1;
                    for (const textFragment of textFragments) {
                        this.execCommand('insertText', textFragment);
                        if (textIndex < textFragments.length) {
                            this._applyCommand('oShiftEnter');
                        }
                        textIndex++;
                    }
                }
            }
        }
    }
    /**
     * Handle safe dropping of html into the editor.
     */
    _onDrop(ev) {
        ev.preventDefault();
        const sel = this.document.getSelection();
        let isInEditor = false;
        let ancestor = sel.anchorNode;
        while (ancestor && !isInEditor) {
            if (ancestor === this.editable) {
                isInEditor = true;
            }
            ancestor = ancestor.parentNode;
        }
        const transferItem = [...(ev.originalEvent || ev).dataTransfer.items].find(
            item => item.type === 'text/html',
        );
        if (transferItem) {
            transferItem.getAsString(pastedText => {
                if (isInEditor && !sel.isCollapsed) {
                    this.deleteRange(sel);
                }
                if (this.document.caretPositionFromPoint) {
                    const range = this.document.caretPositionFromPoint(ev.clientX, ev.clientY);
                    setSelection(range.offsetNode, range.offset);
                } else if (this.document.caretRangeFromPoint) {
                    const range = this.document.caretRangeFromPoint(ev.clientX, ev.clientY);
                    setSelection(range.startContainer, range.startOffset);
                }
                this.execCommand('insertHTML', this._prepareClipboardData(pastedText));
            });
        }
        this.historyStep();
    }

    _onTabulationInTable(ev) {
        const sel = this.document.getSelection();
        const closestTable = closestElement(sel.anchorNode, 'table');
        if (!closestTable) {
            return;
        }
        const closestTd = closestElement(sel.anchorNode, 'td');
        const tds = [...closestTable.querySelectorAll('td')];
        const direction = ev.shiftKey ? DIRECTIONS.LEFT : DIRECTIONS.RIGHT;
        const cursorDestination =
            tds[tds.findIndex(td => closestTd === td) + (direction === DIRECTIONS.LEFT ? -1 : 1)];
        if (cursorDestination) {
            setSelection(...startPos(cursorDestination), ...endPos(cursorDestination), true);
        } else if (direction === DIRECTIONS.RIGHT) {
            this._addRowBelow();
            this._onTabulationInTable(ev);
        }
    }

    /**
     * Fix the current selection range in case the range start or end inside a fontAwesome node
     */
    _fixFontAwesomeSelection() {
        const selection = this.document.getSelection();
        if (
            selection.isCollapsed ||
            (selection.anchorNode &&
                !ancestors(selection.anchorNode, this.editable).includes(this.editable))
        )
            return;
        let shouldUpdateSelection = false;
        const fixedSelection = {
            anchorNode: selection.anchorNode,
            anchorOffset: selection.anchorOffset,
            focusNode: selection.focusNode,
            focusOffset: selection.focusOffset,
        };
        const selectionDirection = getCursorDirection(
            selection.anchorNode,
            selection.anchorOffset,
            selection.focusNode,
            selection.focusOffset,
        );
        // check and fix anchor node
        const closestAnchorNodeEl = closestElement(selection.anchorNode);
        if (isFontAwesome(closestAnchorNodeEl)) {
            shouldUpdateSelection = true;
            fixedSelection.anchorNode =
                selectionDirection === DIRECTIONS.RIGHT
                    ? closestAnchorNodeEl.previousSibling
                    : closestAnchorNodeEl.nextSibling;
            if (fixedSelection.anchorNode) {
                fixedSelection.anchorOffset =
                    selectionDirection === DIRECTIONS.RIGHT ? fixedSelection.anchorNode.length : 0;
            } else {
                fixedSelection.anchorNode = closestAnchorNodeEl.parentElement;
                fixedSelection.anchorOffset = 0;
            }
        }
        // check and fix focus node
        const closestFocusNodeEl = closestElement(selection.focusNode);
        if (isFontAwesome(closestFocusNodeEl)) {
            shouldUpdateSelection = true;
            fixedSelection.focusNode =
                selectionDirection === DIRECTIONS.RIGHT
                    ? closestFocusNodeEl.nextSibling
                    : closestFocusNodeEl.previousSibling;
            if (fixedSelection.focusNode) {
                fixedSelection.focusOffset =
                    selectionDirection === DIRECTIONS.RIGHT ? 0 : fixedSelection.focusNode.length;
            } else {
                fixedSelection.focusNode = closestFocusNodeEl.parentElement;
                fixedSelection.focusOffset = 0;
            }
        }
        if (shouldUpdateSelection) {
            setSelection(
                fixedSelection.anchorNode,
                fixedSelection.anchorOffset,
                fixedSelection.focusNode,
                fixedSelection.focusOffset,
                false,
            );
        }
    }
}
