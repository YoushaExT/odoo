odoo.define('mail.discuss_test', function (require) {
"use strict";

var Discuss = require('mail.Discuss');
var mailTestUtils = require('mail.testUtils');

var concurrency = require('web.concurrency');
var SearchView = require('web.SearchView');
var testUtils = require('web.test_utils');

var createDiscuss = mailTestUtils.createDiscuss;

QUnit.module('mail', {}, function () {
QUnit.module('Discuss', {
    beforeEach: function () {
        // patch _.debounce and _.throttle to be fast and synchronous
        this.underscoreDebounce = _.debounce;
        this.underscoreThrottle = _.throttle;
        _.debounce = _.identity;
        _.throttle = _.identity;

        this.data = {
            'mail.message': {
                fields: {
                    body: {
                        string: "Contents",
                        type: 'html',
                    },
                    author_id: {
                        string: "Author",
                        relation: 'res.partner',
                    },
                    channel_ids: {
                        string: "Channels",
                        type: 'many2many',
                        relation: 'mail.channel',
                    },
                    starred: {
                        string: "Starred",
                        type: 'boolean',
                    },
                    needaction: {
                        string: "Need Action",
                        type: 'boolean',
                    },
                    needaction_partner_ids: {
                        string: "Partners with Need Action",
                        type: 'many2many',
                        relation: 'res.partner',
                    },
                    starred_partner_ids: {
                        string: "Favorited By",
                        type: 'many2many',
                        relation: 'res.partner',
                    },
                    model: {
                        string: "Related Document model",
                        type: 'char',
                    },
                    res_id: {
                        string: "Related Document ID",
                        type: 'integer',
                    },
                },
            },
        };
        this.services = mailTestUtils.getMailServices();
    },
    afterEach: function () {
        // unpatch _.debounce and _.throttle
        _.debounce = this.underscoreDebounce;
        _.throttle = this.underscoreThrottle;
    }
});

QUnit.test('basic rendering', function (assert) {
    assert.expect(5);
    var done = assert.async();

    createDiscuss({
        id: 1,
        context: {},
        params: {},
        data: this.data,
        services: this.services,
    })
    .then(function (discuss) {
        // test basic rendering
        var $sidebar = discuss.$('.o_mail_discuss_sidebar');
        assert.strictEqual($sidebar.length, 1,
            "should have rendered a sidebar");

        assert.containsOnce(discuss, '.o_mail_discuss_content',
            "should have rendered the content");
        assert.containsOnce(discuss, '.o_mail_no_content',
            "should display no content message");

        var $inbox = $sidebar.find('.o_mail_discuss_item[data-thread-id=mailbox_inbox]');
        assert.strictEqual($inbox.length, 1,
            "should have the channel item 'mailbox_inbox' in the sidebar");

        var $starred = $sidebar.find('.o_mail_discuss_item[data-thread-id=mailbox_starred]');
        assert.strictEqual($starred.length, 1,
            "should have the channel item 'mailbox_starred' in the sidebar");
        discuss.destroy();
        done();
    });
});

QUnit.test('searchview options visibility', function (assert) {
    assert.expect(4);
    var done = assert.async();

    createDiscuss({
        id: 1,
        context: {},
        params: {},
        data: this.data,
        services: this.services,
    })
    .then(function (discuss) {
        var $searchviewOptions = $('.o_search_options > div');
        var $searchviewOptionsToggler = $('.o_searchview_more.fa.fa-search-minus');
        assert.strictEqual($searchviewOptions.length, 1,
            "should have search options");
        assert.strictEqual($searchviewOptionsToggler.length, 1,
            "should have a button to toggle search options");
        assert.strictEqual($searchviewOptions.css('display'), 'block',
            "search options should be visible by default");

        testUtils.dom.click($searchviewOptionsToggler);
        assert.strictEqual($searchviewOptions.css('display'), 'none',
            "search options should be hidden after clicking on search option toggler");

        discuss.destroy();
        done();
    });
});

QUnit.test('searchview filter messages', function (assert) {
    assert.expect(10);
    var done = assert.async();

    this.data['mail.message'].records = [{
        author_id: [5, 'Demo User'],
        body: '<p>abc</p>',
        id: 1,
        needaction: true,
        needaction_partner_ids: [3],
    }, {
        author_id: [6, 'Test User'],
        body: '<p>def</p>',
        id: 2,
        needaction: true,
        needaction_partner_ids: [3],
    }];

    createDiscuss({
        id: 1,
        context: {},
        params: {},
        data: this.data,
        services: this.services,
        session: {
            partner_id: 3
        },
        archs: {
            'mail.message,false,search':
                '<search>' +
                    '<field name="body"/>' +
                '</search>',
        },
    })
    .then(function (discuss) {
        assert.containsN(discuss, '.o_thread_message', 2,
            "there should be two messages in the inbox mailbox");
        assert.strictEqual($('.o_searchview_input').length, 1,
            "there should be a searchview on discuss");
        assert.strictEqual($('.o_searchview_input').val(), '',
            "the searchview should be empty initially");

        // interact with searchview so that there is only once message
        $('.o_searchview_input').val("ab").trigger('keyup');
        $('.o_searchview').trigger($.Event('keydown', { which: $.ui.keyCode.ENTER }));

        assert.strictEqual($('.o_searchview_facet').length, 1,
            "the searchview should have a facet");
        assert.strictEqual($('.o_facet_values').text().trim(), 'ab',
            "the facet should be a search on 'ab'");
        assert.containsOnce(discuss, '.o_thread_message',
            "there should be a single message after filter");

        // interact with search view so that there are no matching messages
        testUtils.dom.click($('.o_facet_remove'));
        $('.o_searchview_input').val("abcd").trigger('keyup');
        $('.o_searchview').trigger($.Event('keydown', { which: $.ui.keyCode.ENTER }));

        assert.strictEqual($('.o_searchview_facet').length, 1,
            "the searchview should have a facet");
        assert.strictEqual($('.o_facet_values').text().trim(), 'abcd',
            "the facet should be a search on 'abcd'");
        assert.containsNone(discuss, '.o_thread_message',
            "there should be no message after 2nd filter");
        assert.strictEqual(discuss.$('.o_thread_title').text().trim(),
            "No matches found",
            "should display that there are no matching messages");

        discuss.destroy();
        done();
    });
});

QUnit.test('unescape channel name in the sidebar', function (assert) {
    // When the user creates a channel, the channel's name is escaped, this in
    // order to prevent XSS attacks. However, the user should see visually the
    // unescaped name of the channel. For instance, when the user creates a
    // channel named  "R&D", he should see "R&D" and not "R&amp;D".
    assert.expect(2);
    var done = assert.async();

    this.data.initMessaging = {
        channel_slots: {
            channel_channel: [{
                id: 1,
                channel_type: "channel",
                name: "R&amp;D",
            }],
        },
    };

    createDiscuss({
        id: 1,
        context: {},
        params: {},
        data: this.data,
        services: this.services,
    })
    .then(function (discuss) {
        var $sidebar = discuss.$('.o_mail_discuss_sidebar');

        var $channel = $sidebar.find('.o_mail_discuss_item[data-thread-id=1]');
        assert.strictEqual($channel.length, 1,
            "should have the channel item for channel 1 in the sidebar");
        assert.strictEqual($channel.find('.o_thread_name').text().replace(/\s/g, ''),
            "#R&D",
            "should have unescaped channel name in the sidebar");

        discuss.destroy();
        done();
    });
});

QUnit.test('@ mention in channel', function (assert) {
    assert.expect(34);
    var done = assert.async();

    var fetchListenersDef = $.Deferred();
    var receiveMessageDef = $.Deferred();

    this.data.initMessaging = {
        channel_slots: {
            channel_channel: [{
                id: 1,
                channel_type: "channel",
                name: "general",
            }],
        },
    };

    var objectDiscuss;
    createDiscuss({
        id: 1,
        context: {},
        params: {},
        data: this.data,
        services: this.services,
        mockRPC: function (route, args) {
            if (args.method === 'channel_fetch_listeners') {
                fetchListenersDef.resolve();
                return $.when([
                    {id: 1, name: 'Admin'},
                    {id: 2, name: 'TestUser'},
                    {id: 3, name: 'DemoUser'}
                ]);
            }
            if (args.method === 'message_post') {
                var data = {
                    author_id: ["42", "Me"],
                    body: args.kwargs.body,
                    channel_ids: [1],
                };
                var notification = [[false, 'mail.channel', 1], data];
                objectDiscuss.call('bus_service', 'trigger', 'notification', [notification]);
                receiveMessageDef.resolve();
                return $.when(42);
            }
            return this._super.apply(this, arguments);
        },
    })
    .then(function (discuss) {
        objectDiscuss = discuss;

        var $general = discuss.$('.o_mail_discuss_sidebar')
                        .find('.o_mail_discuss_item[data-thread-id=1]');
        assert.strictEqual($general.length, 1,
            "should have the channel item with id 1");
        assert.hasAttrValue($general, 'title', 'general',
            "should have the title 'general'");

        // click on general
        testUtils.dom.click($general);
        var $input = discuss.$('textarea.o_composer_text_field').first();
        assert.ok($input.length, "should display a composer input");

        // Note: focus is needed in order to trigger rpc 'channel_fetch_listeners'
        $input.focus();
        $input.val("@");
        $input.trigger('keyup');

        fetchListenersDef
            .then(concurrency.delay.bind(concurrency, 0))
            .then(function () {
                assert.containsOnce(discuss, '.dropup.o_composer_mention_dropdown.show',
                "dropup menu for partner mentions should be open");

                var $mentionPropositions = discuss.$('.o_mention_proposition');
                assert.strictEqual($mentionPropositions.length, 3,
                    "should display 3 partner mention propositions");

                var $mention1 = $mentionPropositions.first();
                var $mention2 = $mentionPropositions.first().next();
                var $mention3 = $mentionPropositions.first().next().next();

                // correct 1st mention proposition
                assert.hasClass($mention1,'active',
                    "first partner mention should be active");
                assert.strictEqual($mention1.data('id'), 1,
                    "first partner mention should link to the correct partner id");
                assert.strictEqual($mention1.find('.o_mention_name').text(), "Admin",
                    "first partner mention should display the correct partner name");
                // correct 2nd mention proposition
                assert.doesNotHaveClass($mention2, 'active',
                    "second partner mention should not be active");
                assert.strictEqual($mention2.data('id'), 2,
                    "second partner mention should link to the correct partner id");
                assert.strictEqual($mention2.find('.o_mention_name').text(), "TestUser",
                    "second partner mention should display the correct partner name");
                // correct 3rd mention proposition
                assert.doesNotHaveClass($mention3, 'active',
                    "third partner mention should not be active");
                assert.strictEqual($mention3.data('id'), 3,
                    "third partner mention should link to the correct partner id");
                assert.strictEqual($mention3.find('.o_mention_name').text(), "DemoUser",
                    "third partner mention should display the correct partner name");

                // check DOWN event
                $input.trigger($.Event('keyup', {which: $.ui.keyCode.DOWN}));
                assert.doesNotHaveClass($mention1, 'active',
                    "first partner mention should not be active");
                assert.hasClass($mention2,'active',
                    "second partner mention should be active");
                assert.doesNotHaveClass($mention3, 'active',
                    "third partner mention should not be active");

                // check UP event
                $input.trigger($.Event('keyup', {which: $.ui.keyCode.UP}));
                assert.hasClass($mention1,'active',
                    "first partner mention should be active");
                assert.doesNotHaveClass($mention2, 'active',
                    "second partner mention should not be active");
                assert.doesNotHaveClass($mention3, 'active',
                    "third partner mention should not be active");

                // check TAB event (full cycle, hence 3 TABs)
                $input.trigger($.Event('keyup', {which: $.ui.keyCode.TAB}));
                assert.doesNotHaveClass($mention1, 'active',
                    "first partner mention should not be active");
                assert.hasClass($mention2,'active',
                    "second partner mention should be active");
                assert.doesNotHaveClass($mention3, 'active',
                    "third partner mention should not be active");

                $input.trigger($.Event('keyup', {which: $.ui.keyCode.TAB}));
                assert.doesNotHaveClass($mention1, 'active',
                    "first partner mention should not be active");
                assert.doesNotHaveClass($mention2, 'active',
                    "second partner mention should not be active");
                assert.hasClass($mention3,'active',
                    "third partner mention should be active");

                $input.trigger($.Event('keyup', {which: $.ui.keyCode.TAB}));
                assert.hasClass($mention1,'active',
                    "first partner mention should be active");
                assert.doesNotHaveClass($mention2, 'active',
                    "second partner mention should not be active");
                assert.doesNotHaveClass($mention3, 'active',
                    "third partner mention should not be active");

//                testUtils.dom.click( equivalent to $mentionPropositions.find('active'));
                $input.trigger($.Event('keyup', {which: $.ui.keyCode.ENTER}));
                assert.containsNone(discuss, '.o_mention_proposition',
                    "should not have any partner mention proposition after ENTER");
                assert.strictEqual($input.val().trim() , "@Admin",
                    "should have the correct mention link in the composer input");

                // send message
                $input.trigger($.Event('keydown', {which: $.ui.keyCode.ENTER}));

                receiveMessageDef
                    .then(concurrency.delay.bind(concurrency, 0))
                    .then(function () {
                        assert.containsOnce(discuss, '.o_thread_message_content',
                            "should display one message with some content");
                        assert.containsOnce(discuss, '.o_thread_message_content a',
                            "should contain a link in the message content");
                        assert.strictEqual(discuss.$('.o_thread_message_content a').text(),
                            "@Admin", "should have correct mention link in the message content");

                        discuss.destroy();
                        done();
                });
        });
    });
});

QUnit.test('@ mention with special chars', function (assert) {
    assert.expect(9);
    var done = assert.async();
    var fetchListenersDef = $.Deferred();
    var receiveMessageDef = $.Deferred();
    this.data.initMessaging = {
        channel_slots: {
            channel_channel: [{
                id: 1,
                channel_type: "channel",
                name: "general",
            }],
        },
    };
    var objectDiscuss;
    createDiscuss({
        id: 1,
        context: {},
        params: {},
        data: this.data,
        services: this.services,
        mockRPC: function (route, args) {
            if (args.method === 'channel_fetch_listeners') {
                fetchListenersDef.resolve();
                return $.when([
                    {id: 1, name: '\u0405pëciãlUser<&>"`\' \u30C4'},
                ]);
            }
            if (args.method === 'message_post') {
                var data = {
                    author_id: ["42", "Me"],
                    body: args.kwargs.body,
                    channel_ids: [1],
                };
                var notification = [[false, 'mail.channel', 1], data];
                objectDiscuss.call('bus_service', 'trigger', 'notification', [notification]);
                receiveMessageDef.resolve();
                return $.when(42);
            }
            return this._super.apply(this, arguments);
        },
    })
    .then(function (discuss) {
        objectDiscuss = discuss;
        var $general = discuss.$('.o_mail_discuss_sidebar')
                        .find('.o_mail_discuss_item[data-thread-id=1]');
        // click on general
        $general.click();
        var $input = discuss.$('textarea.o_composer_text_field').first();
        assert.ok($input.length, "should display a composer input");
        // Note: focus is needed in order to trigger rpc 'channel_fetch_listeners'
        $input.focus();
        $input.val("@");
        $input.trigger('keyup');
        fetchListenersDef
            .then(concurrency.delay.bind(concurrency, 0))
            .then(function () {
                var $mention = discuss.$('.o_mention_proposition');
                // correct mention proposition
                assert.ok($mention.hasClass('active'),
                    "first partner mention should be active");
                assert.strictEqual($mention.data('id'), 1,
                    "first partner mention should link to the correct partner id");
                assert.strictEqual($mention.find('.o_mention_name').text(), '\u0405pëciãlUser<&>"`\' \u30C4',
                    "first partner mention should display the correct partner name");
                // equivalent to $mentionPropositions.find('active').click();
                $input.trigger($.Event('keyup', {which: $.ui.keyCode.ENTER}));
                assert.strictEqual(discuss.$('.o_mention_proposition').length, 0,
                    "should not have any partner mention proposition after ENTER");
                assert.strictEqual($input.val().trim() , "@\u0405pëciãlUser<&>\"`'\u00A0\u30C4",
                    "should have the correct mention link in the composer input");
                // send message
                $input.trigger($.Event('keydown', {which: $.ui.keyCode.ENTER}));
                receiveMessageDef
                    .then(concurrency.delay.bind(concurrency, 0))
                    .then(function () {
                        assert.strictEqual(discuss.$('.o_thread_message_content').length, 1,
                            "should display one message with some content");
                        assert.strictEqual(discuss.$('.o_thread_message_content a').length, 1,
                            "should contain a link in the message content");
                        assert.strictEqual(discuss.$('.o_thread_message_content a').text(),
                            "@\u0405pëciãlUser<&>\"`' \u30C4",
                            "should have correct mention link in the message content");
                        discuss.destroy();
                        done();
                });
        });
    });
});

QUnit.test('no crash focusout emoji button', function (assert) {
    assert.expect(3);
    var done = assert.async();

    this.data.initMessaging = {
        channel_slots: {
            channel_channel: [{
                id: 1,
                channel_type: "channel",
                name: "general",
            }],
        },
    };

    createDiscuss({
        id: 1,
        context: {},
        params: {},
        data: this.data,
        services: this.services,
    })
    .then(function (discuss) {
        var $general = discuss.$('.o_mail_discuss_sidebar')
            .find('.o_mail_discuss_item[data-thread-id=1]');
        assert.strictEqual($general.length, 1,
            "should have the channel item with id 1");
        assert.hasAttrValue($general, 'title', 'general',
            "should have the title 'general'");

        // click on general
        testUtils.dom.click($general);
        discuss.$('.o_composer_button_emoji').focus();
        try {
            discuss.$('.o_composer_button_emoji').focusout();
            assert.ok(true, "should not crash on focusout of emoji button");
        } finally {
            discuss.destroy();
            done();
        }
    });
});

QUnit.test('older messages are loaded on scroll', function (assert) {
    assert.expect(10);
    var done = assert.async();

    var fetchCount = 0;
    var loadMoreDef = $.Deferred();
    var messageData = [];
    for (var i = 0; i < 35; i++) {
        messageData.push({
            author_id: ['1', 'Me'],
            body: '<p>test ' + i + '</p>',
            channel_ids: [1],
            id: i,
        });
    }

    this.data.initMessaging = {
        channel_slots: {
            channel_channel: [{
                id: 1,
                channel_type: "channel",
                name: "general",
                static: true,
            }],
        },
    };
    this.data['mail.message'].records = messageData;

    createDiscuss({
        context: {},
        data: this.data,
        params: {},
        services: this.services,
        mockRPC: function (route, args) {
            if (args.method === 'message_fetch') {
                assert.step(args.method);
                fetchCount++;
                // 1st fetch: inbox initial fetch
                // 2nd fetch: general initial fetch
                // 3rd fetch: general load more
                if (fetchCount === 1) {
                    assert.strictEqual(args.kwargs.limit, 30,
                        "should ask to fetch 30 messages at most");
                }
                if (fetchCount === 3) {
                    loadMoreDef.resolve();
                }
            }
            return this._super.apply(this, arguments);
        },
    }).then(function (discuss) {

        assert.verifySteps(['message_fetch'],
            "should fetch messages once for needaction messages (Inbox)");

        var $general = discuss.$('.o_mail_discuss_item[data-thread-id=1]');
        assert.strictEqual($general.length, 1,
            "should have a channel item with id 1");

        // switch to 'general'
        testUtils.dom.click($general);

        assert.verifySteps(['message_fetch', 'message_fetch'],
            "should fetch a second time for general channel messages (30 last messages)");

        assert.containsN(discuss, '.o_thread_message', 30,
            "should display the 30 messages");

        // simulate a scroll to top to load more messages
        discuss.$('.o_mail_thread').scrollTop(0);

        loadMoreDef
            .then(concurrency.delay.bind(concurrency, 0))
            .then(function () {
                assert.verifySteps(['message_fetch', 'message_fetch', 'message_fetch'],
                    "should fetch a third time for general channel messages (5 remaining messages)");
                assert.containsN(discuss, '.o_thread_message', 35,
                    "all messages should now be loaded");

                discuss.destroy();
                done();
            });
    });
});

QUnit.test('"Unstar all" button should reset the starred counter', function (assert) {
    assert.expect(2);
    var done = assert.async();

    var messageData = [];
    _.each(_.range(1, 41), function (num) {
        messageData.push({
                id: num,
                body: "<p>test" + num + "</p>",
                author_id: ["1", "Me"],
                channel_ids: [1],
                starred: true,
                starred_partner_ids: [1],
            }
        );
    });

    this.data.initMessaging = {
            channel_slots: {
                channel_channel: [{
                    id: 1,
                    channel_type: "channel",
                    name: "general",
                }],
            },
            starred_counter: messageData.length,
    };
    this.data['mail.message'].records = messageData;

    var objectDiscuss;
    createDiscuss({
        id: 1,
        context: {},
        params: {},
        data: this.data,
        services: this.services,
        mockRPC: function (route, args) {
            if (args.method === 'unstar_all') {
                var data = {
                    message_ids: _.range(1, 41),
                    starred: false,
                    type: 'toggle_star',
                };
                var notification = [[false, 'res.partner'], data];
                objectDiscuss.call('bus_service', 'trigger', 'notification', [notification]);
                return $.when(42);
            }
            return this._super.apply(this, arguments);
        },
        session: {partner_id: 1},
    })
    .then(function (discuss) {
        objectDiscuss = discuss;

        var $starred = discuss.$('.o_mail_discuss_sidebar').find('.o_mail_mailbox_title_starred');
        var $starredCounter = $('.o_mail_mailbox_title_starred > .o_mail_sidebar_needaction');

        // Go to Starred channel
        testUtils.dom.click($starred);
        // Test Initial Value
        assert.strictEqual($starredCounter.text().trim(), "40", "40 messages should be starred");

        // Unstar all and wait 'update_starred'
        testUtils.dom.click($('.o_control_panel .o_mail_discuss_button_unstar_all'));
        $starredCounter = $('.o_mail_mailbox_title_starred > .o_mail_sidebar_needaction');
        assert.strictEqual($starredCounter.text().trim(), "0",
            "All messages should be unstarred");

        discuss.destroy();
        done();
    });
});

QUnit.test('do not crash when destroyed before start is completed', function (assert) {
    assert.expect(3);
    var discuss;

    testUtils.mock.patch(Discuss, {
        init: function () {
            discuss = this;
            this._super.apply(this, arguments);
        },
    });

    createDiscuss({
        id: 1,
        context: {},
        params: {},
        data: this.data,
        services: this.services,
        mockRPC: function (route, args) {
            if (args.method) {
                assert.step(args.method);
            }
            var result = this._super.apply(this, arguments);
            if (args.method === 'message_fetch') {
                discuss.destroy();
            }
            return result;
        },
    });

    assert.verifySteps([
        "load_views",
        "message_fetch"
    ]);

    testUtils.mock.unpatch(Discuss);
});

QUnit.test('do not crash when destroyed between start en end of _renderSearchView', function (assert) {
    assert.expect(2);
    var discuss;

    testUtils.mock.patch(Discuss, {
        init: function () {
            discuss = this;
            this._super.apply(this, arguments);
        },
    });

    var def = $.Deferred();

    testUtils.mock.patch(SearchView, {
        willStart: function () {
            var result = this._super.apply(this, arguments);
            return def.then($.when(result));
        },
    });

    createDiscuss({
        id: 1,
        context: {},
        params: {},
        data: this.data,
        services: this.services,
        mockRPC: function (route, args) {
            if (args.method) {
                assert.step(args.method);
            }
            return this._super.apply(this, arguments);
        },
    });

    discuss.destroy();
    def.resolve();
    assert.verifySteps([
        "load_views",
    ]);

    testUtils.mock.unpatch(Discuss);
    testUtils.mock.unpatch(SearchView);
});

QUnit.test('confirm dialog when administrator leave (not chat) channel', function (assert) {
    assert.expect(2);
    var done = assert.async();

    this.data.initMessaging = {
        channel_slots: {
            channel_channel: [{
                id: 1,
                channel_type: "channel",
                name: "MyChannel",
                create_uid: 3,
            }],
        },
    };

    createDiscuss({
        id: 1,
        context: {},
        params: {},
        data: this.data,
        services: this.services,
        session: {
            uid: 3,
        },
    })
    .then(function (discuss) {
        // Unsubscribe on MyChannel as administrator
        testUtils.dom.click(discuss.$('.o_mail_partner_unpin'));

        assert.strictEqual($('.modal-dialog').length, 1,
            "should display a dialog");
        assert.strictEqual($('.modal-body').text(),
            "You are the administrator of this channel. Are you sure you want to unsubscribe?",
            "Warn user that he will be unsubscribed from channel as admin.");
        discuss.destroy();
        done();
    });
});

QUnit.test('convert emoji sources to unicodes on message_post', function (assert) {
    assert.expect(2);
    var done = assert.async();

    var receiveMessageDef = $.Deferred();

    this.data.initMessaging = {
        channel_slots: {
            channel_channel: [{
                id: 1,
                channel_type: "channel",
                name: "general",
            }],
        },
    };

    var objectDiscuss;
    createDiscuss({
        id: 1,
        context: {},
        params: {},
        data: this.data,
        services: this.services,
        mockRPC: function (route, args) {
            if (args.method === 'message_post') {
                assert.strictEqual(args.kwargs.body, "😊 😂",
                    "message_post data should have all emojis in their unicode representation");

                var data = {
                    author_id: ["42", "Me"],
                    body: args.kwargs.body,
                    channel_ids: [1],
                };
                var notification = [[false, 'mail.channel', 1], data];
                objectDiscuss.call('bus_service', 'trigger', 'notification', [notification]);
                receiveMessageDef.resolve();
                return $.when(42);
            }
            return this._super.apply(this, arguments);
        },
    })
    .then(function (discuss) {
        objectDiscuss= discuss;

        var $general = discuss.$('.o_mail_discuss_sidebar')
                        .find('.o_mail_discuss_item[data-thread-id=1]');

        // click on general
        testUtils.dom.click($general);
        var $input = discuss.$('textarea.o_composer_text_field').first();

        $input.focus();
        $input.val(":) x'D");
        $input.trigger($.Event('keydown', {which: $.ui.keyCode.ENTER}));

        receiveMessageDef
            .then(concurrency.delay.bind(concurrency, 0))
            .then(function () {

                assert.strictEqual(discuss.$('.o_thread_message_content').text().replace(/\s/g, ""),
                    "😊😂",
                    "New posted message should contain all emojis in their unicode representation");
                discuss.destroy();
                done();
        });
    });
});

QUnit.test('mark all messages as read from Inbox', function (assert) {
    var done = assert.async();
    assert.expect(9);

    this.data['mail.message'].records = [{
        author_id: [5, 'Demo User'],
        body: '<p>test 1</p>',
        id: 1,
        needaction: true,
        needaction_partner_ids: [3],
    }, {
        author_id: [6, 'Test User'],
        body: '<p>test 2</p>',
        id: 2,
        needaction: true,
        needaction_partner_ids: [3],
    }];

    this.data.initMessaging = {
        needaction_inbox_counter: 2,
    };

    var markAllReadDef = $.Deferred();
    var objectDiscuss;

    createDiscuss({
        id: 1,
        context: {},
        params: {},
        data: this.data,
        services: this.services,
        session: { partner_id: 3 },
        mockRPC: function (route, args) {
            if (args.method === 'mark_all_as_read') {
                _.each(this.data['mail.message'].records, function (message) {
                    message.needaction = false;
                });
                var notificationData = {
                    type: 'mark_as_read',
                    message_ids: [1, 2],
                };
                var notification = [[false, 'res.partner', 3], notificationData];
                objectDiscuss.call('bus_service', 'trigger', 'notification', [notification]);
                markAllReadDef.resolve();
                return $.when();
            }
            return this._super.apply(this, arguments);
        },
    })
    .then(function (discuss) {
        objectDiscuss = discuss;

        var $inbox = discuss.$('.o_mail_discuss_item[data-thread-id="mailbox_inbox"]');
        assert.strictEqual($inbox.length, 1,
            "there should be an 'Inbox' item in Discuss sidebar");
        assert.strictEqual($inbox.find('.o_mail_sidebar_needaction').text().trim(), "2",
            "the mailbox counter of 'Inbox' should be 2");
        assert.hasClass($inbox,'o_active',
            "'Inbox' should be the currently active thread");
        assert.containsN(discuss, '.o_thread_message', 2,
            "there should be 2 messages in inbox");

        var $markAllReadButton = $('.o_mail_discuss_button_mark_all_read');
        assert.strictEqual($markAllReadButton.length, 1,
            "there should be a 'Mark All As Read' button");
        assert.hasAttrValue($markAllReadButton, 'style',
            'display: inline-block;',
            "the 'Mark All As Read' button should be visible");
        assert.notOk($markAllReadButton.prop('disabled'),
            "the 'Mark All As Read' button should not be disabled");

        testUtils.dom.click($markAllReadButton);

        markAllReadDef.then(function () {
            // immediately jump to end of the fadeout animation on messages
            $inbox = discuss.$('.o_mail_discuss_item[data-thread-id="mailbox_inbox"]');
            discuss.$('.o_thread_message').stop(false, true);
            assert.strictEqual($inbox.find('.o_mail_sidebar_needaction').text().trim(), "0",
                "the mailbox counter of 'Inbox' should have reset to 0");
            assert.containsNone(discuss, '.o_thread_message',
                "there should no message in inbox anymore");

            discuss.destroy();
            done();
        });
    });
});

QUnit.test('drag and drop file in composer', function (assert) {
    assert.expect(8);
    var done = assert.async();

    this.data.initMessaging = {
        channel_slots: {
            channel_channel: [{
                id: 1,
                channel_type: "channel",
                name: "general",
            }],
        },
    };

    createDiscuss({
        id: 1,
        context: {},
        params: {},
        data: this.data,
        services: this.services,
    })
    .then(function (discuss) {
        var $general = discuss.$('.o_mail_discuss_sidebar')
                        .find('.o_mail_discuss_item[data-thread-id=1]');

        // click on general
        testUtils.dom.click($general);

        // first composer is active (basic), 2nd is hidden (extended)
        var $composer = discuss.$('.o_thread_composer').first();
        assert.containsNone($composer, '.o_attachments_list',
            "should not display any attachment on the composer initially");
        assert.containsOnce($composer, '.o_file_drop_zone_container',
            "should have a dropzone to drag-and-drop files");

        var $dropZoneContainer = $composer.find('.o_file_drop_zone_container');
        assert.isNotVisible($dropZoneContainer,
            "dropzone should not be visible");

        testUtils.file.createFile({
            name: 'text.txt',
            content: 'hello, world',
            contentType: 'text/plain',
        }).then(function (file) {
            testUtils.file.dragoverFile($dropZoneContainer, file);
            assert.isVisible($dropZoneContainer,
                "dropzone should be visible");

            testUtils.file.dropFile($dropZoneContainer, file);
            assert.containsOnce($composer, '.o_attachments_list',
                "should display some attachments on the composer");
            assert.containsOnce($composer, '.o_attachment',
                "should display one attachment on the composer");

            var filename = $('.o_attachment').find('.caption').first().text().trim();
            assert.strictEqual(filename, 'text.txt',
                "should display the correct filename");
            assert.hasClass($('.o_attachment_uploaded i'), 'fa-check',
                "text file should have been uploaded");

            discuss.destroy();
            done();
        });
    });
});

});
});
