/** @odoo-module **/

import { create, insert } from 'mail/static/src/model/model_field_command.js';
import {
    afterEach,
    beforeEach,
    start,
} from 'mail/static/src/utils/test_utils.js';

QUnit.module('mail', {}, function () {
QUnit.module('model', {}, function () {
QUnit.module('model_field_command', {}, function () {
QUnit.module('insert_tests.js', {
    beforeEach() {
        beforeEach(this);
        this.start = async params => {
            const { env, widget } = await start(Object.assign({}, params, {
                data: this.data,
            }));
            this.env = env;
            this.widget = widget;
        };
    },
    afterEach() {
        afterEach(this);
    },
});

QUnit.test('insert: should create and link a new record for an empty x2one field', async function (assert) {
    assert.expect(2);
    await this.start();

    const contact = this.env.models['test.contact'].create({ id: 10 });
    contact.update({ address: insert({ id: 10 }) });
    const address = this.env.models['test.address'].findFromIdentifyingData({ id: 10 });
    assert.strictEqual(
        contact.address,
        address,
        'insert: should create and link a record for an empty x2one field'
    );
    assert.strictEqual(
        address.contact,
        contact,
        'the inverse relation should be set as well'
    );
});

QUnit.test('insert: should create and replace a new record for a non-empty x2one field', async function (assert) {
    assert.expect(3);
    await this.start();

    const contact = this.env.models['test.contact'].create({
        id: 10,
        address: create({ id: 10 }),
    });
    const address10 = this.env.models['test.address'].findFromIdentifyingData({ id: 10 });
    contact.update({ address: insert({ id: 20 }) });
    const address20 = this.env.models['test.address'].findFromIdentifyingData({ id: 20 });
    assert.strictEqual(
        contact.address,
        address20,
        'insert: should create and replace a new record for a non-empty x2one field'
    );
    assert.strictEqual(
        address20.contact,
        contact,
        'the inverse relation should be set as well'
    );
    assert.strictEqual(
        address10.contact,
        undefined,
        'the original relation should be dropped'
    );
});

QUnit.test('insert: should update the existing record for an x2one field', async function (assert) {
    assert.expect(2);
    await this.start();

    const contact = this.env.models['test.contact'].create({
        id: 10,
        address: create({
            id: 10,
            addressInfo: 'address 10',
        }),
    });
    const address10 = this.env.models['test.address'].findFromIdentifyingData({ id: 10 });
    contact.update({
        address: insert({
            id: 10,
            addressInfo: 'address 10 updated',
        }),
    });
    assert.strictEqual(
        contact.address,
        address10,
        'insert: should not drop an existing record'
    );
    assert.strictEqual(
        address10.addressInfo,
        'address 10 updated',
        'insert: should update the existing record for a x2one field'
    );
});

QUnit.test('insert: should create and link a new record for an x2many field', async function (assert) {
    assert.expect(3);
    await this.start();

    const contact = this.env.models['test.contact'].create({ id: 10 });
    contact.update({ tasks: insert({ id: 10 }) });
    const task = this.env.models['test.task'].findFromIdentifyingData({ id: 10 });
    assert.strictEqual(
        contact.tasks.length,
        1,
        'should have 1 record'
    );
    assert.strictEqual(
        contact.tasks[0],
        task,
        "should link the new record"
    );
    assert.strictEqual(
        task.responsible,
        contact,
        'the inverse relation should be set as well'
    );
});

QUnit.test('insert: should create and add a new record for an x2many field', async function (assert) {
    assert.expect(4);
    await this.start();

    const contact = this.env.models['test.contact'].create({
        id: 10,
        tasks: create({ id: 10 }),
    });
    const task10 = this.env.models['test.task'].findFromIdentifyingData({ id: 10 });
    contact.update({ tasks: insert({ id: 20 }) });
    const task20 = this.env.models['test.task'].findFromIdentifyingData({ id: 20 });
    assert.strictEqual(
        contact.tasks.length,
        2,
        "should have 2 records"
    );
    assert.strictEqual(
        contact.tasks[0],
        task10,
        "the original record should be kept"
    );
    assert.strictEqual(
        contact.tasks[1],
        task20,
        'new record should be added'
    );
    assert.strictEqual(
        task20.responsible,
        contact,
        'the inverse relation should be set as well'
    );
});

QUnit.test('insert: should update existing records for an x2many field', async function (assert) {
    assert.expect(3);
    await this.start();

    const contact = this.env.models['test.contact'].create({
        id: 10,
        tasks: create({
            id: 10,
            title: 'task 10',
        }),
    });
    const task = this.env.models['test.task'].findFromIdentifyingData({ id: 10 });
    contact.update({
        tasks: insert({
            id: 10,
            title: 'task 10 updated',
        }),
    });
    assert.strictEqual(
        contact.tasks.length,
        1,
        "should have 1 record"
    );
    assert.strictEqual(
        contact.tasks[0],
        task,
        "the original task should be kept"
    );
    assert.strictEqual(
        task.title,
        'task 10 updated',
        'should update the existing record'
    );
});

});
});
});
