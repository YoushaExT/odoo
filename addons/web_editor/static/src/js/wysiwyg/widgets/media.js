odoo.define('wysiwyg.widgets.media', function (require) {
'use strict';

var concurrency = require('web.concurrency');
var config = require('web.config');
var core = require('web.core');
var Dialog = require('web.Dialog');
var dom = require('web.dom');
var fonts = require('wysiwyg.fonts');
var ImageOptimizeDialog = require('wysiwyg.widgets.image_optimize_dialog').ImageOptimizeDialog;
var utils = require('web.utils');
var Widget = require('web.Widget');
var session = require('web.session');

var QWeb = core.qweb;
var _t = core._t;

var MediaWidget = Widget.extend({
    xmlDependencies: ['/web_editor/static/src/xml/wysiwyg.xml'],

    /**
     * @constructor
     * @param {Element} media: the target Element for which we select a media
     * @param {Object} options: useful parameters such as res_id, res_model,
     *  context, user_id, ...
     */
    init: function (parent, media, options) {
        this._super.apply(this, arguments);
        this.media = media;
        this.$media = $(media);
    },

    //--------------------------------------------------------------------------
    // Public
    //--------------------------------------------------------------------------

    /**
     * @todo comment
     */
    clear: function () {
        if (!this.media) {
            return;
        }
        this._clear();
    },
    /**
     * Saves the currently configured media on the target media.
     *
     * @abstract
     * @returns {Promise}
     */
    save: function () {},

    //--------------------------------------------------------------------------
    // Private
    //--------------------------------------------------------------------------

    /**
     * @abstract
     */
    _clear: function () {},
});

var SearchableMediaWidget = MediaWidget.extend({
    events: _.extend({}, MediaWidget.prototype.events || {}, {
        'input .o_we_search': '_onSearchInput',
    }),

    /**
     * @constructor
     */
    init: function () {
        this._super.apply(this, arguments);
        this._onSearchInput = _.debounce(this._onSearchInput, 500);
    },

    //--------------------------------------------------------------------------
    // Public
    //--------------------------------------------------------------------------

    /**
     * Finds and displays existing attachments related to the target media.
     *
     * @abstract
     * @param {string} needle: only return attachments matching this parameter
     * @returns {Promise}
     */
    search: function (needle) {},

    //--------------------------------------------------------------------------
    // Private
    //--------------------------------------------------------------------------

    /**
     * Renders thumbnails for the attachments.
     *
     * @abstract
     * @returns {Promise}
     */
    _renderThumbnails: function () {},

    //--------------------------------------------------------------------------
    // Handlers
    //--------------------------------------------------------------------------

    /**
     * @private
     */
    _onSearchInput: function (ev) {
        this.search($(ev.currentTarget).val() || '').then(() => this._renderThumbnails());
        this.hasSearched = true;
    },
});

/**
 * Let users choose a file, including uploading a new file in odoo.
 */
var FileWidget = SearchableMediaWidget.extend({
    events: _.extend({}, SearchableMediaWidget.prototype.events || {}, {
        'click .o_upload_media_button': '_onUploadButtonClick',
        'change .o_file_input': '_onFileInputChange',
        'click .o_upload_media_url_button': '_onUploadURLButtonClick',
        'input .o_we_url_input': '_onURLInputChange',
        'click .o_existing_attachment_cell': '_onAttachmentClick',
        'click .o_existing_attachment_remove': '_onRemoveClick',
        'click .o_existing_attachment_optimize': '_onExistingOptimizeClick',
        'click .o_load_more': '_onLoadMoreClick',
    }),
    existingAttachmentsTemplate: undefined,

    IMAGE_MIMETYPES: ['image/gif', 'image/jpe', 'image/jpeg', 'image/jpg', 'image/gif', 'image/png', 'image/svg+xml'],
    NUMBER_OF_ATTACHMENTS_TO_DISPLAY: 30,

    // This factor is used to take into account that an image displayed in a BS
    // column might get bigger when displayed on a smaller breakpoint if that
    // breakpoint leads to have less columns.
    // Eg. col-lg-6 -> 480px per column -> col-md-12 -> 720px per column -> 1.5
    // However this will not be enough if going from 3 or more columns to 1, but
    // in that case, we consider it a snippet issue.
    OPTIMIZE_SIZE_FACTOR: 1.5,

    /**
     * @constructor
     */
    init: function (parent, media, options) {
        this._super.apply(this, arguments);
        this._mutex = new concurrency.Mutex();

        this.numberOfAttachmentsToDisplay = this.NUMBER_OF_ATTACHMENTS_TO_DISPLAY;

        this.options = _.extend({
            mediaWidth: media && media.parentElement && $(media.parentElement).width(),
        }, options || {});

        this.attachments = [];
        this.selectedAttachments = [];

        this._onUploadURLButtonClick = dom.makeAsyncHandler(this._onUploadURLButtonClick);
    },
    /**
     * @override
     */
    start: function () {
        var def = this._super.apply(this, arguments);
        var self = this;
        this.$urlInput = this.$('.o_we_url_input');
        this.$form = this.$('form');
        this.$fileInput = this.$('.o_file_input');
        this.$uploadButton = this.$('.o_upload_media_button');
        this.$addUrlButton = this.$('.o_upload_media_url_button');
        this.$urlSuccess = this.$('.o_we_url_success');
        this.$urlWarning = this.$('.o_we_url_warning');
        this.$urlError = this.$('.o_we_url_error');
        this.$errorText = this.$('.o_we_error_text');

        // If there is already an attachment on the target, select by default
        // that attachment if it is among the loaded images.
        var o = {
            url: null,
            alt: null,
        };
        if (this.$media.is('img')) {
            o.url = this.$media.attr('src');
        } else if (this.$media.is('a.o_image')) {
            o.url = this.$media.attr('href').replace(/[?].*/, '');
            o.id = +o.url.match(/\/web\/content\/(\d+)/, '')[1];
        }

        return this.search('').then(async () => {
            await this._renderThumbnails();
            if (o.url) {
                self._selectAttachement(_.find(self.attachments, function (attachment) {
                    return o.url === attachment.image_src;
                }) || o);
            }
            return def;
        });
    },

    //--------------------------------------------------------------------------
    // Public
    //--------------------------------------------------------------------------

    /**
     * Saves the currently selected image on the target media. If new files are
     * currently being added, delays the save until all files have been added.
     *
     * @override
     */
    save: function () {
        return this._mutex.exec(this._save.bind(this));
    },
    /**
     * @override
     */
    search: function (needle) {
        this.attachments = [];
        this.needle = needle;
        return this.fetchAttachments(this.NUMBER_OF_ATTACHMENTS_TO_DISPLAY, 0);
    },
    /**
     * @param {Number} number - the number of attachments to fetch
     * @param {Number} offset - from which result to start fetching
     */
    fetchAttachments: function (number, offset) {
        return this._rpc({
            model: 'ir.attachment',
            method: 'search_read',
            args: [],
            kwargs: {
                domain: this._getAttachmentsDomain(this.needle),
                fields: ['name', 'mimetype', 'description', 'checksum', 'url', 'type', 'res_id', 'res_model', 'public', 'access_token', 'image_src', 'image_width', 'image_height', 'original_id'],
                order: [{name: 'id', asc: false}],
                context: this.options.context,
                // Try to fetch first record of next page just to know whether there is a next page.
                limit: number + 1,
                offset: offset,
            },
        }).then(attachments => {
            this.attachments = this.attachments.slice();
            Array.prototype.splice.apply(this.attachments, [offset, attachments.length].concat(attachments));
        });
    },

    //--------------------------------------------------------------------------
    // Private
    //--------------------------------------------------------------------------

    /**
     * @override
     */
    _clear: function () {
        if (this.$media.is('img')) {
            return;
        }
        var allImgClasses = /(^|\s+)((img(\s|$)|img-(?!circle|rounded|thumbnail))[^\s]*)/g;
        var allImgClassModifiers = /(^|\s+)(rounded-circle|shadow|rounded|img-thumbnail|mx-auto)([^\s]*)/g;
        this.media.className = this.media.className && this.media.className
            .replace('o_we_custom_image', '')
            .replace(allImgClasses, ' ')
            .replace(allImgClassModifiers, ' ');
    },
    /**
     * Computes and returns the width that a new attachment should have to
     * ideally occupy the space where it will be inserted.
     * Only relevant for images.
     *
     * @see options.mediaWidth
     * @see OPTIMIZE_SIZE_FACTOR
     *
     * @private
     * @returns {integer}
     */
    _computeOptimizedWidth: function () {
        return Math.min(1920, parseInt(this.options.mediaWidth * this.OPTIMIZE_SIZE_FACTOR));
    },
    /**
     * Returns the domain for attachments used in media dialog.
     * We look for attachments related to the current document. If there is a value for the model
     * field, it is used to search attachments, and the attachments from the current document are
     * filtered to display only user-created documents.
     * In the case of a wizard such as mail, we have the documents uploaded and those of the model
     *
     * @private
     * @params {string} needle
     * @returns {Array} "ir.attachment" odoo domain.
     */
    _getAttachmentsDomain: function (needle) {
        var domain = this.options.attachmentIDs && this.options.attachmentIDs.length ? ['|', ['id', 'in', this.options.attachmentIDs]] : [];

        var attachedDocumentDomain = [
            '&',
            ['res_model', '=', this.options.res_model],
            ['res_id', '=', this.options.res_id|0]
        ];
        // if the document is not yet created, do not see the documents of other users
        if (!this.options.res_id) {
            attachedDocumentDomain.unshift('&');
            attachedDocumentDomain.push(['create_uid', '=', this.options.user_id]);
        }
        if (this.options.data_res_model) {
            var relatedDomain = ['&',
                ['res_model', '=', this.options.data_res_model],
                ['res_id', '=', this.options.data_res_id|0]];
            if (!this.options.data_res_id) {
                relatedDomain.unshift('&');
                relatedDomain.push(['create_uid', '=', session.uid]);
            }
            domain = domain.concat(['|'], attachedDocumentDomain, relatedDomain);
        } else {
            domain = domain.concat(attachedDocumentDomain);
        }
        domain = ['|', ['public', '=', true]].concat(domain);
        domain = domain.concat(this.options.mimetypeDomain);
        if (needle && needle.length) {
            domain.push(['name', 'ilike', needle]);
        }
        domain.push('!', ['name', '=like', '%.crop']);
        domain.push('|', ['type', '=', 'binary'], ['url', '!=', false]);
        return domain;
    },
    /**
     * @private
     */
    _highlightSelected: function () {
        var self = this;
        this.$('.o_existing_attachment_cell.o_we_attachment_selected').removeClass("o_we_attachment_selected");
        _.each(this.selectedAttachments, function (attachment) {
            self.$('.o_existing_attachment_cell[data-id=' + attachment.id + ']')
                .addClass("o_we_attachment_selected").css('display', '');
        });
    },
    /**
     * @private
     * @param {object} attachment
     */
    _handleNewAttachment: function (attachment) {
        this.attachments = this.attachments.filter(att => att.id !== attachment.id);
        this.attachments.unshift(attachment);
        this._renderThumbnails();
        this._selectAttachement(attachment);
    },
    /**
     * @private
     * @returns {Promise}
     */
    _loadMoreImages: function (forceSearch) {
        return this.fetchAttachments(10, this.numberOfAttachmentsToDisplay).then(() => {
            this.numberOfAttachmentsToDisplay += 10;
            if (!forceSearch) {
                this._renderThumbnails();
                return Promise.resolve();
            } else {
                return this.search(this.$('.o_we_search').val() || '');
            }
        });
    },
    /**
     * Opens the image optimize dialog for the given attachment.
     *
     * Hides the media dialog while the optimize dialog is open to avoid an
     * overlap of modals.
     *
     * @private
     * @param {object} attachment
     * @param {boolean} isExisting: whether this is a new attachment that was
     *  just uploaded, or an existing attachment
     * @returns {Promise} resolved with the updated attachment object when the
     *  optimize dialog is saved. Rejected if the dialog is otherwise closed.
     */
    _openImageOptimizeDialog: function (attachment, isExisting, $attachmentCell) {
        var self = this;
        var promise = new Promise(function (resolve, reject) {
            self.trigger_up('hide_parent_dialog_request');
            var optimizeDialog = new ImageOptimizeDialog(self, {
                attachment: attachment,
                isExisting: isExisting,
                optimizedWidth: self._computeOptimizedWidth(),
            }).open();
            optimizeDialog.on('attachment_updated', self, function (ev) {
                optimizeDialog.off('closed');
                if (self.$media[0].getAttribute('src') === attachment.image_src) {
                    self.$media[0].src = ev.data.image_src;
                }
                Object.assign(attachment, ev.data);
                $attachmentCell.find('img')[0].src = attachment.image_src;
                resolve(attachment);
            });
            optimizeDialog.on('closed', self, function () {
                self.noSave = true;
                if (isExisting) {
                    reject();
                } else {
                    resolve(attachment);
                }
            });
        });
        var always = () => {
            self.trigger_up('show_parent_dialog_request');
        };
        promise.then(always).guardedCatch(always);
        return promise;
    },
    /**
     * Renders the existing attachments and returns the result as a string.
     *
     * @param {Object[]} attachments
     * @returns {string}
     */
    _renderExisting: function (attachments) {
        return QWeb.render(this.existingAttachmentsTemplate, {
            attachments: attachments,
            widget: this,
        });
    },
    /**
     * @private
     */
    _renderThumbnails: function () {
        var attachments = this.attachments.slice(0, this.numberOfAttachmentsToDisplay);

        // Render menu & content
        this.$('.o_we_existing_attachments').replaceWith(
            this._renderExisting(attachments)
        );

        this._highlightSelected();

        // adapt load more
        var noLoadMoreButton = this.NUMBER_OF_ATTACHMENTS_TO_DISPLAY >= this.attachments.length;
        var noMoreImgToLoad = this.numberOfAttachmentsToDisplay >= this.attachments.length;
        this.$('.o_load_done_msg').toggleClass('d-none', noLoadMoreButton || !noMoreImgToLoad);
        this.$('.o_load_more').toggleClass('d-none', noMoreImgToLoad);
    },
    /**
     * @private
     * @returns {Promise}
     */
    _save: async function () {
        if (this.options.multiImages) {
            return this.selectedAttachments;
        }

        var img = this.selectedAttachments[0];
        if (!img || !img.id) {
            return this.media;
        }

        // Auto optimize unoptimized images.
        if (['image/jpeg', 'image/jpe', 'image/jpg', 'image/png'].includes(img.mimetype) && img.type === 'binary' && !img.original_id) {
            img = await this._optimizeAttachment(img);
        }

        if (!img.public && !img.access_token) {
            await this._rpc({
                model: 'ir.attachment',
                method: 'generate_access_token',
                args: [[img.id]]
            }).then(function (access_token) {
                img.access_token = access_token[0];
            });
        }

        if (img.image_src) {
            var src = img.image_src;
            if (!img.public && img.access_token) {
                src += _.str.sprintf('?access_token=%s', img.access_token);
            }
            if (!this.$media.is('img')) {

                // Note: by default the images receive the bootstrap opt-in
                // img-fluid class. We cannot make them all responsive
                // by design because of libraries and client databases img.
                this.$media = $('<img/>', {class: 'img-fluid o_we_custom_image'});
                this.media = this.$media[0];
            }
            this.$media.attr('src', src);
        } else {
            if (!this.$media.is('a')) {
                $('.note-control-selection').hide();
                this.$media = $('<a/>');
                this.media = this.$media[0];
            }
            var href = '/web/content/' + img.id + '?';
            if (!img.public && img.access_token) {
                href += _.str.sprintf('access_token=%s&', img.access_token);
            }
            href += 'unique=' + img.checksum + '&download=true';
            this.$media.attr('href', href);
            this.$media.addClass('o_image').attr('title', img.name).attr('data-mimetype', img.mimetype);
        }

        this.$media.attr('alt', img.alt || img.description || '');
        var style = this.style;
        if (style) {
            this.$media.css(style);
        }

        // Remove crop related attributes
        if (this.$media.attr('data-aspect-ratio')) {
            var attrs = ['aspect-ratio', 'x', 'y', 'width', 'height', 'rotate', 'scale-x', 'scale-y', 'crop:originalSrc'];
            this.$media.removeClass('o_cropped_img_to_save');
            attrs.forEach(attr => {
                this.$media.removeData(attr);
                this.$media.removeAttr('data-' + attr);
            });
        }
        return this.media;
    },
    /**
     * Creates and returns an optimized copy of an attachment.
     *
     * @private
     * @param {object} attachment
     */
    _optimizeAttachment: function (attachment) {
        return this._rpc({
            route: `/web_editor/attachment/${attachment.id}/update`,
            params: {
                copy: true,
                name: attachment.name,
                quality: attachment.mimetype === 'image/png' ? 0 : 80,
                width: this._computeOptimizedWidth(),
            },
        });
    },
    /**
     * @param {object} attachment
     * @param {boolean} [save=true] to save the given attachment in the DOM and
     *  and to close the media dialog
     * @private
     */
    _selectAttachement: function (attachment, save) {
        if (this.options.multiImages) {
            // if the clicked attachment is already selected then unselect it
            // unless it was a save request (then keep the current selection)
            var index = this.selectedAttachments.indexOf(attachment);
            if (index !== -1) {
                if (!save) {
                    this.selectedAttachments.splice(index, 1);
                }
            } else {
                // if the clicked attachment is not selected, add it to selected
                this.selectedAttachments.push(attachment);
            }
        } else {
            // select the clicked attachment
            this.selectedAttachments = [attachment];
        }
        this._highlightSelected();
        if (save) {
            this.trigger_up('save_request');
        }
    },
    /**
     * Updates the add by URL UI.
     *
     * @private
     * @param {boolean} emptyValue
     * @param {boolean} isURL
     * @param {boolean} isImage
     */
    _updateAddUrlUi: function (emptyValue, isURL, isImage) {
        this.$addUrlButton.toggleClass('btn-secondary', emptyValue)
            .toggleClass('btn-primary', !emptyValue)
            .prop('disabled', !isURL);
        this.$urlSuccess.toggleClass('d-none', !isURL);
        this.$urlError.toggleClass('d-none', emptyValue || isURL);
    },

    //--------------------------------------------------------------------------
    // Handlers
    //--------------------------------------------------------------------------

    /**
     * @private
     */
    _onAttachmentClick: function (ev) {
        var $attachment = $(ev.currentTarget);
        var attachment = _.find(this.attachments, {id: $attachment.data('id')});
        this._selectAttachement(attachment, !this.options.multiImages);
    },
    /**
     * @private
     */
    _onExistingOptimizeClick: function (ev) {
        var $a = $(ev.currentTarget).closest('.o_existing_attachment_cell');
        var id = parseInt($a.data('id'), 10);
        var attachment = _.findWhere(this.attachments, {id: id});
        ev.stopPropagation();
        return this._openImageOptimizeDialog(attachment, true, $a).then(newAttachment => {
            this._handleNewAttachment(newAttachment);
        });
    },
    /**
     * Handles change of the file input: create attachments with the new files
     * and open the Preview dialog for each of them. Locks the save button until
     * all new files have been processed.
     *
     * @private
     * @returns {Promise}
     */
    _onFileInputChange: function () {
        return this._mutex.exec(this._addData.bind(this));
    },
    /**
     * Uploads the files that are currently selected on the file input, which
     * creates new attachments. Then inserts them on the media dialog and
     * selects them. If multiImages is not set, also triggers up the
     * save_request event to insert the attachment in the DOM.
     *
     * @private
     * @returns {Promise}
     */
    _addData: function () {
        var self = this;
        var uploadMutex = new concurrency.Mutex();

        // Upload the smallest file first to block the user the least possible.
        var files = _.sortBy(this.$fileInput[0].files, 'size');

        _.each(files, function (file) {
            // Upload one file at a time: no need to parallel as upload is
            // limited by bandwidth.
            uploadMutex.exec(function () {
                return utils.getDataURLFromFile(file).then(function (result) {
                    return self._rpc({
                        route: '/web_editor/attachment/add_data',
                        params: {
                            'name': file.name,
                            'data': result.split(',')[1],
                            'res_id': self.options.res_id,
                            'res_model': self.options.res_model,
                            'width': 0,
                            'quality': 0,
                        },
                    }).then(function (attachment) {
                        self._handleNewAttachment(attachment);
                    });
                });
            });
        });

        return uploadMutex.getUnlockedDef().then(function () {
            if (!self.options.multiImages && !self.noSave) {
                self.trigger_up('save_request');
            }
            self.noSave = false;
        });
    },
    /**
     * @private
     */
    _onRemoveClick: function (ev) {
        var self = this;
        ev.stopPropagation();
        Dialog.confirm(this, _t("Are you sure you want to delete this file ?"), {
            confirm_callback: function () {
                var $a = $(ev.currentTarget).closest('.o_existing_attachment_cell');
                var id = parseInt($a.data('id'), 10);
                var attachment = _.findWhere(self.attachments, {id: id});
                 return self._rpc({
                    route: '/web_editor/attachment/remove',
                    params: {
                        ids: [id],
                    },
                }).then(function (prevented) {
                    if (_.isEmpty(prevented)) {
                        self.attachments = _.without(self.attachments, attachment);
                        self.attachments.filter(at => at.original_id[0] === attachment.id).forEach(at => delete at.original_id);
                        if (!self.attachments.length) {
                            self._renderThumbnails(); //render the message and image if empty
                        } else {
                            $a.closest('.o_existing_attachment_cell').remove();
                        }
                        return;
                    }
                    self.$errorText.replaceWith(QWeb.render('wysiwyg.widgets.image.existing.error', {
                        views: prevented[id],
                        widget: self,
                    }));
                });
            }
        });
    },
    /**
     * @private
     */
    _onURLInputChange: function () {
        var inputValue = this.$urlInput.val();
        var emptyValue = (inputValue === '');

        var isURL = /^.+\..+$/.test(inputValue); // TODO improve
        var isImage = _.any(['.gif', '.jpeg', '.jpe', '.jpg', '.png'], function (format) {
            return inputValue.endsWith(format);
        });

        this._updateAddUrlUi(emptyValue, isURL, isImage);
    },
    /**
     * @private
     */
    _onUploadButtonClick: function () {
        this.$fileInput.click();
    },
    /**
     * @private
     */
    _onUploadURLButtonClick: function () {
        if (this.$urlInput.is('.o_we_horizontal_collapse')) {
            this.$urlInput.removeClass('o_we_horizontal_collapse');
            this.$addUrlButton.attr('disabled', 'disabled');
            return;
        }
        return this._mutex.exec(this._addUrl.bind(this));
    },
    /**
     * @private
     * @returns {Promise}
     */
    _addUrl: function () {
        var self = this;
        return this._rpc({
            route: '/web_editor/attachment/add_url',
            params: {
                'url': this.$urlInput.val(),
                'res_id': this.options.res_id,
                'res_model': this.options.res_model,
            },
        }).then(function (attachment) {
            self.$urlInput.val('');
            self._onURLInputChange();
            self._handleNewAttachment(attachment);
            if (!self.options.multiImages) {
                self.trigger_up('save_request');
            }
        });
    },
    /**
     * @private
     */
    _onLoadMoreClick: function () {
        this._loadMoreImages();
    },
    /**
     * @override
     */
    _onSearchInput: function () {
        this.numberOfAttachmentsToDisplay = this.NUMBER_OF_ATTACHMENTS_TO_DISPLAY;
        this._super.apply(this, arguments);
    },
});

/**
 * Let users choose an image, including uploading a new image in odoo.
 */
var ImageWidget = FileWidget.extend({
    template: 'wysiwyg.widgets.image',
    existingAttachmentsTemplate: 'wysiwyg.widgets.image.existing.attachments',
    events: Object.assign({}, FileWidget.prototype.events, {
        'change input.o_we_show_optimized': '_onShowOptimizedChange',
    }),
    MIN_ROW_HEIGHT: 128,

    /**
     * @constructor
     */
    init: function (parent, media, options) {
        options = _.extend({
            accept: 'image/*',
            mimetypeDomain: [['mimetype', 'in', this.IMAGE_MIMETYPES]],
        }, options || {});
        // Binding so we can add/remove it as an addEventListener
        this._onAttachmentImageLoad = this._onAttachmentImageLoad.bind(this);
        this._super(parent, media, options);
    },
    /**
     * @override
     */
    start: async function () {
        await this._super(...arguments);
        this.el.addEventListener('load', this._onAttachmentImageLoad, true);
    },
    /**
     * @override
     */
    destroy: function () {
        this.el.removeEventListener('load', this._onAttachmentImageLoad, true);
        return this._super(...arguments);
    },

    //--------------------------------------------------------------------------
    // Private
    //--------------------------------------------------------------------------

    /**
     * @override
     */
    _updateAddUrlUi: function (emptyValue, isURL, isImage) {
        this._super.apply(this, arguments);
        this.$addUrlButton.text((isURL && !isImage) ? _t("Add as document") : _t("Add image"));
        const warning = isURL && !isImage;
        this.$urlWarning.toggleClass('d-none', !warning);
        if (warning) {
            this.$urlSuccess.addClass('d-none');
        }
    },
    /**
     * @override
     */
    _renderThumbnails: function () {
        const alreadyLoaded = this.$('.o_existing_attachment_cell[data-loaded="true"]');
        this._super(...arguments);
        // Hide images until they're loaded
        this.$('.o_existing_attachment_cell').addClass('d-none');
        // Replace images that had been previously loaded if any to prevent scroll resetting to top
        alreadyLoaded.each((index, el) => {
            const toReplace = this.$(`.o_existing_attachment_cell[data-id="${el.dataset.id}"]`);
            if (toReplace.length) {
                toReplace.replaceWith(el);
            }
        });
        this._toggleOptimized(this.$('input.o_we_show_optimized')[0].checked);
        // Placeholders have a 3:2 aspect ratio like most photos.
        const placeholderWidth = 3 / 2 * this.MIN_ROW_HEIGHT;
        this.$('.o_we_attachment_placeholder').css({
            flexGrow: placeholderWidth,
            flexBasis: placeholderWidth,
        });
    },
    /**
     * @override
     */
    _renderExisting: function (attachments) {
        return QWeb.render(this.existingAttachmentsTemplate, {
            attachments: attachments,
            widget: this,
        });
    },
    /**
     * @private
     *
     * @param {boolean} value whether to toggle optimized attachments on or off
     */
    _toggleOptimized: function (value) {
        this.$('.o_we_attachment_optimized').each((i, cell) => cell.style.setProperty('display', value ? null : 'none', 'important'));
    },

    //--------------------------------------------------------------------------
    // Handlers
    //--------------------------------------------------------------------------

    /**
     * @override
     */
    _onAttachmentImageLoad: function (ev) {
        const img = ev.target;
        const cell = img.closest('.o_existing_attachment_cell');
        if (!cell) {
            return;
        }
        const aspectRatio = img.naturalWidth / img.naturalHeight;
        const width = aspectRatio * this.MIN_ROW_HEIGHT;
        cell.style.flexGrow = width;
        cell.style.flexBasis = `${width}px`;
        cell.classList.remove('d-none');
        cell.classList.add('d-flex');
        cell.dataset.loaded = 'true';
    },
    /**
     * @override
     */
    _onShowOptimizedChange: function (ev) {
        this._toggleOptimized(ev.target.checked);
    },
});


/**
 * Let users choose a document, including uploading a new document in odoo.
 */
var DocumentWidget = FileWidget.extend({
    template: 'wysiwyg.widgets.document',
    existingAttachmentsTemplate: 'wysiwyg.widgets.document.existing.attachments',

    /**
     * @constructor
     */
    init: function (parent, media, options) {
        options = _.extend({
            accept: '*/*',
            mimetypeDomain: [['mimetype', 'not in', this.IMAGE_MIMETYPES]],
        }, options || {});
        this._super(parent, media, options);
    },

    //--------------------------------------------------------------------------
    // Private
    //--------------------------------------------------------------------------

    /**
     * @override
     */
    _updateAddUrlUi: function (emptyValue, isURL, isImage) {
        this._super.apply(this, arguments);
        this.$addUrlButton.text((isURL && isImage) ? _t("Add as image") : _t("Add document"));
        const warning = isURL && isImage;
        this.$urlWarning.toggleClass('d-none', !warning);
        if (warning) {
            this.$urlSuccess.addClass('d-none');
        }
    },
    /**
     * @override
     */
    _getAttachmentsDomain: function (needle) {
        var domain = this._super.apply(this, arguments);
        // the assets should not be part of the documents
        return domain.concat('!', utils.assetsDomain());
    },
});

/**
 * Let users choose a font awesome icon, support all font awesome loaded in the
 * css files.
 */
var IconWidget = SearchableMediaWidget.extend({
    template: 'wysiwyg.widgets.font-icons',
    events: _.extend({}, SearchableMediaWidget.prototype.events || {}, {
        'click .font-icons-icon': '_onIconClick',
    }),

    /**
     * @constructor
     */
    init: function (parent, media) {
        this._super.apply(this, arguments);

        fonts.computeFonts();
        this.iconsParser = fonts.fontIcons;
        this.alias = _.flatten(_.map(this.iconsParser, function (data) {
            return data.alias;
        }));
    },
    /**
     * @override
     */
    start: function () {
        this.$icons = this.$('.font-icons-icon');
        var classes = (this.media && this.media.className || '').split(/\s+/);
        for (var i = 0; i < classes.length; i++) {
            var cls = classes[i];
            if (_.contains(this.alias, cls)) {
                this.selectedIcon = cls;
                this._highlightSelectedIcon();
            }
        }
        this.nonIconClasses = _.without(classes, 'media_iframe_video', this.selectedIcon);

        return this._super.apply(this, arguments);
    },

    //--------------------------------------------------------------------------
    // Public
    //--------------------------------------------------------------------------

    /**
     * @override
     */
    save: function () {
        var style = this.$media.attr('style') || '';
        var iconFont = this._getFont(this.selectedIcon) || {base: 'fa', font: ''};
        var finalClasses = _.uniq(this.nonIconClasses.concat([iconFont.base, iconFont.font]));
        if (!this.$media.is('span')) {
            var $span = $('<span/>');
            $span.data(this.$media.data());
            this.$media = $span;
            this.media = this.$media[0];
            style = style.replace(/\s*width:[^;]+/, '');
        }
        this.$media.attr({
            class: _.compact(finalClasses).join(' '),
            style: style || null,
        });
        return Promise.resolve(this.media);
    },
    /**
     * @override
     */
    search: function (needle) {
        var iconsParser = this.iconsParser;
        if (needle && needle.length) {
            iconsParser = [];
            _.filter(this.iconsParser, function (data) {
                var cssData = _.filter(data.cssData, function (cssData) {
                    return _.find(cssData.names, function (alias) {
                        return alias.indexOf(needle) >= 0;
                    });
                });
                if (cssData.length) {
                    iconsParser.push({
                        base: data.base,
                        cssData: cssData,
                    });
                }
            });
        }
        this.$('div.font-icons-icons').html(
            QWeb.render('wysiwyg.widgets.font-icons.icons', {iconsParser: iconsParser, widget: this})
        );
        return Promise.resolve();
    },

    //--------------------------------------------------------------------------
    // Private
    //--------------------------------------------------------------------------

    /**
     * @override
     */
    _clear: function () {
        var allFaClasses = /(^|\s)(fa(\s|$)|fa-[^\s]*)/g;
        this.media.className = this.media.className && this.media.className.replace(allFaClasses, ' ');
    },
    /**
     * @private
     */
    _getFont: function (classNames) {
        if (!(classNames instanceof Array)) {
            classNames = (classNames || "").split(/\s+/);
        }
        var fontIcon, cssData;
        for (var k = 0; k < this.iconsParser.length; k++) {
            fontIcon = this.iconsParser[k];
            for (var s = 0; s < fontIcon.cssData.length; s++) {
                cssData = fontIcon.cssData[s];
                if (_.intersection(classNames, cssData.names).length) {
                    return {
                        base: fontIcon.base,
                        parser: fontIcon.parser,
                        font: cssData.names[0],
                    };
                }
            }
        }
        return null;
    },
    /**
     * @private
     */
    _highlightSelectedIcon: function () {
        var self = this;
        this.$icons.removeClass('o_we_attachment_selected');
        this.$icons.filter(function (i, el) {
            return _.contains($(el).data('alias').split(','), self.selectedIcon);
        }).addClass('o_we_attachment_selected');
    },

    //--------------------------------------------------------------------------
    // Handlers
    //--------------------------------------------------------------------------

    /**
     * @private
     */
    _onIconClick: function (ev) {
        ev.preventDefault();
        ev.stopPropagation();

        this.selectedIcon = $(ev.currentTarget).data('id');
        this._highlightSelectedIcon();
        this.trigger_up('save_request');
    },
});

/**
 * Let users choose a video, support all summernote video, and embed iframe.
 */
var VideoWidget = MediaWidget.extend({
    template: 'wysiwyg.widgets.video',
    events: _.extend({}, MediaWidget.prototype.events || {}, {
        'change .o_video_dialog_options input': '_onUpdateVideoOption',
        'input textarea#o_video_text': '_onVideoCodeInput',
        'change textarea#o_video_text': '_onVideoCodeChange',
    }),

    /**
     * @constructor
     */
    init: function (parent, media, options) {
        this._super.apply(this, arguments);
        this.isForBgVideo = !!options.isForBgVideo;
        this._onVideoCodeInput = _.debounce(this._onVideoCodeInput, 1000);
    },
    /**
     * @override
     */
    start: function () {
        this.$content = this.$('.o_video_dialog_iframe');

        if (this.media) {
            var $media = $(this.media);
            var src = $media.data('oe-expression') || $media.data('src') || ($media.is('iframe') ? $media.attr('src') : '') || '';
            this.$('textarea#o_video_text').val(src);

            this.$('input#o_video_autoplay').prop('checked', src.indexOf('autoplay=1') >= 0);
            this.$('input#o_video_hide_controls').prop('checked', src.indexOf('controls=0') >= 0);
            this.$('input#o_video_loop').prop('checked', src.indexOf('loop=1') >= 0);
            this.$('input#o_video_hide_fullscreen').prop('checked', src.indexOf('fs=0') >= 0);
            this.$('input#o_video_hide_yt_logo').prop('checked', src.indexOf('modestbranding=1') >= 0);
            this.$('input#o_video_hide_dm_logo').prop('checked', src.indexOf('ui-logo=0') >= 0);
            this.$('input#o_video_hide_dm_share').prop('checked', src.indexOf('sharing-enable=0') >= 0);

            this._updateVideo();
        }

        return this._super.apply(this, arguments);
    },

    //--------------------------------------------------------------------------
    // Public
    //--------------------------------------------------------------------------

    /**
     * @override
     */
    save: function () {
        this._updateVideo();
        if (this.isForBgVideo) {
            return Promise.resolve({bgVideoSrc: this.$content.attr('src')});
        }
        if (this.$('.o_video_dialog_iframe').is('iframe')) {
            this.$media = $(
                '<div class="media_iframe_video" data-oe-expression="' + this.$content.attr('src') + '">' +
                    '<div class="css_editable_mode_display">&nbsp;</div>' +
                    '<div class="media_iframe_video_size" contenteditable="false">&nbsp;</div>' +
                    '<iframe src="' + this.$content.attr('src') + '" frameborder="0" contenteditable="false"></iframe>' +
                '</div>'
            );
            this.media = this.$media[0];
        }
        return Promise.resolve(this.media);
    },

    //--------------------------------------------------------------------------
    // Private
    //--------------------------------------------------------------------------

    /**
     * @override
     */
    _clear: function () {
        if (this.media.dataset.src) {
            try {
                delete this.media.dataset.src;
            } catch (e) {
                this.media.dataset.src = undefined;
            }
        }
        var allVideoClasses = /(^|\s)media_iframe_video(\s|$)/g;
        var isVideo = this.media.className && this.media.className.match(allVideoClasses);
        if (isVideo) {
            this.media.className = this.media.className.replace(allVideoClasses, ' ');
            this.media.innerHTML = '';
        }
    },
    /**
     * Creates a video node according to the given URL and options. If not
     * possible, returns an error code.
     *
     * @private
     * @param {string} url
     * @param {Object} options
     * @returns {Object}
     *          $video -> the created video jQuery node
     *          type -> the type of the created video
     *          errorCode -> if defined, either '0' for invalid URL or '1' for
     *              unsupported video provider
     */
    _createVideoNode: function (url, options) {
        options = options || {};
        const videoData = this._getVideoURLData(url, options);
        if (videoData.error) {
            return {errorCode: 0};
        }
        if (!videoData.type) {
            return {errorCode: 1};
        }
        const $video = $('<iframe>').width(1280).height(720)
            .attr('frameborder', 0)
            .attr('src', videoData.embedURL)
            .addClass('o_video_dialog_iframe');

        return {$video: $video, type: videoData.type};
    },
    /**
     * Updates the video preview according to video code and enabled options.
     *
     * @private
     */
    _updateVideo: function () {
        // Reset the feedback
        this.$content.empty();
        this.$('#o_video_form_group').removeClass('o_has_error o_has_success').find('.form-control, .custom-select').removeClass('is-invalid is-valid');
        this.$('.o_video_dialog_options div').addClass('d-none');

        // Check video code
        var $textarea = this.$('textarea#o_video_text');
        var code = $textarea.val().trim();
        if (!code) {
            return;
        }

        // Detect if we have an embed code rather than an URL
        var embedMatch = code.match(/(src|href)=["']?([^"']+)?/);
        if (embedMatch && embedMatch[2].length > 0 && embedMatch[2].indexOf('instagram')) {
            embedMatch[1] = embedMatch[2]; // Instagram embed code is different
        }
        var url = embedMatch ? embedMatch[1] : code;

        var query = this._createVideoNode(url, {
            'autoplay': this.isForBgVideo || this.$('input#o_video_autoplay').is(':checked'),
            'hide_controls': this.isForBgVideo || this.$('input#o_video_hide_controls').is(':checked'),
            'loop': this.isForBgVideo || this.$('input#o_video_loop').is(':checked'),
            'hide_fullscreen': this.isForBgVideo || this.$('input#o_video_hide_fullscreen').is(':checked'),
            'hide_yt_logo': this.isForBgVideo || this.$('input#o_video_hide_yt_logo').is(':checked'),
            'hide_dm_logo': this.isForBgVideo || this.$('input#o_video_hide_dm_logo').is(':checked'),
            'hide_dm_share': this.isForBgVideo || this.$('input#o_video_hide_dm_share').is(':checked'),
        });

        var $optBox = this.$('.o_video_dialog_options');

        // Show / Hide preview elements
        this.$el.find('.o_video_dialog_preview_text, .media_iframe_video_size').add($optBox).toggleClass('d-none', !query.$video);
        // Toggle validation classes
        this.$el.find('#o_video_form_group')
            .toggleClass('o_has_error', !query.$video).find('.form-control, .custom-select').toggleClass('is-invalid', !query.$video)
            .end()
            .toggleClass('o_has_success', !!query.$video).find('.form-control, .custom-select').toggleClass('is-valid', !!query.$video);

        // Individually show / hide options base on the video provider
        $optBox.find('div.o_' + query.type + '_option').removeClass('d-none');

        // Hide the entire options box if no options are available or if the
        // dialog is opened for a background-video
        $optBox.toggleClass('d-none', this.isForBgVideo || $optBox.find('div:not(.d-none)').length === 0);

        if (query.type === 'yt') {
            // Youtube only: If 'hide controls' is checked, hide 'fullscreen'
            // and 'youtube logo' options too
            this.$('input#o_video_hide_fullscreen, input#o_video_hide_yt_logo').closest('div').toggleClass('d-none', this.$('input#o_video_hide_controls').is(':checked'));
        }

        var $content = query.$video;
        if (!$content) {
            switch (query.errorCode) {
                case 0:
                    $content = $('<div/>', {
                        class: 'alert alert-danger o_video_dialog_iframe mb-2 mt-2',
                        text: _t("The provided url is not valid"),
                    });
                    break;
                case 1:
                    $content = $('<div/>', {
                        class: 'alert alert-warning o_video_dialog_iframe mb-2 mt-2',
                        text: _t("The provided url does not reference any supported video"),
                    });
                    break;
            }
        }
        this.$content.replaceWith($content);
        this.$content = $content;
    },

    //--------------------------------------------------------------------------
    // Handlers
    //--------------------------------------------------------------------------

    /**
     * Called when a video option changes -> Updates the video preview.
     *
     * @private
     */
    _onUpdateVideoOption: function () {
        this._updateVideo();
    },
    /**
     * Called when the video code (URL / Iframe) change is confirmed -> Updates
     * the video preview immediately.
     *
     * @private
     */
    _onVideoCodeChange: function () {
        this._updateVideo();
    },
    /**
     * Called when the video code (URL / Iframe) changes -> Updates the video
     * preview (note: this function is automatically debounced).
     *
     * @private
     */
    _onVideoCodeInput: function () {
        this._updateVideo();
    },
    /**
     * Parses a URL and returns the provider type and an emebedable URL.
     *
     * @private
     */
    _getVideoURLData: function (url, options) {
        if (!url.match(/^(http:\/\/|https:\/\/|\/\/)[a-z0-9]+([-.]{1}[a-z0-9]+)*\.[a-z]{2,5}(:[0-9]{1,5})?(\/.*)?$/i)) {
            return {
                error: true,
                message: 'The provided url is invalid',
            };
        }
        const regexes = {
            youtube: /^(?:(?:https?:)?\/\/)?(?:www\.)?(?:youtu\.be\/|youtube(-nocookie)?\.com\/(?:embed\/|v\/|watch\?v=|watch\?.+&v=))((?:\w|-){11})(?:\S+)?$/,
            instagram: /(.*)instagram.com\/p\/(.[a-zA-Z0-9]*)/,
            vine: /\/\/vine.co\/v\/(.[a-zA-Z0-9]*)/,
            vimeo: /\/\/(player.)?vimeo.com\/([a-z]*\/)*([0-9]{6,11})[?]?.*/,
            dailymotion: /.+dailymotion.com\/(video|hub|embed)\/([^_?]+)[^#]*(#video=([^_&]+))?/,
            youku: /(.*).youku\.com\/(v_show\/id_|embed\/)(.+)/,
        };
        const matches = _.mapObject(regexes, regex => url.match(regex));
        const autoplay = options.autoplay ? '?autoplay=1&mute=1' : '?autoplay=0';
        const controls = options.hide_controls ? '&controls=0' : '';
        const loop = options.loop ? '&loop=1' : '';

        let embedURL;
        let type;
        if (matches.youtube && matches.youtube[2].length === 11) {
            const fullscreen = options.hide_fullscreen ? '&fs=0' : '';
            const ytLoop = loop ? loop + `&playlist=${matches.youtube[2]}` : '';
            const logo = options.hide_yt_logo ? '&modestbranding=1' : '';
            embedURL = `//www.youtube${matches.youtube[1] || ''}.com/embed/${matches.youtube[2]}${autoplay}&rel=0${ytLoop}${controls}${fullscreen}${logo}`;
            type = 'youtube';
        } else if (matches.instagram && matches.instagram[2].length) {
            embedURL = `//www.instagram.com/p/${matches.instagram[2]}/embed/`;
            type = 'instagram';
        } else if (matches.vine && matches.vine[0].length) {
            embedURL = `${matches.vine[0]}/embed/simple`;
            type = 'vine';
        } else if (matches.vimeo && matches.vimeo[3].length) {
            const vimeoAutoplay = autoplay.replace('mute', 'muted');
            embedURL = `//player.vimeo.com/video/${matches.vimeo[3]}${vimeoAutoplay}${loop}`;
            type = 'vimeo';
        } else if (matches.dailymotion && matches.dailymotion[2].length) {
            const videoId = matches.dailymotion[2].replace('video/', '');
            const logo = options.hide_dm_logo ? '&ui-logo=0' : '';
            const share = options.hide_dm_share ? '&sharing-enable=0' : '';
            embedURL = `//www.dailymotion.com/embed/video/${videoId}${autoplay}${controls}${logo}${share}`;
            type = 'dailymotion';
        } else if (matches.youku && matches.youku[3].length) {
            const videoId = matches.youku[3].indexOf('.html?') >= 0 ? matches.youku[3].substring(0, matches.youku[3].indexOf('.html?')) : matches.youku[3];
            embedURL = `//player.youku.com/embed/${videoId}`;
            type = 'youku';
        }

        return {type: type, embedURL: embedURL};
    },
});

return {
    MediaWidget: MediaWidget,
    SearchableMediaWidget: SearchableMediaWidget,
    FileWidget: FileWidget,
    ImageWidget: ImageWidget,
    DocumentWidget: DocumentWidget,
    IconWidget: IconWidget,
    VideoWidget: VideoWidget,
};
});
