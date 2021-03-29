# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Web Editor',
    'category': 'Hidden',
    'description': """
Odoo Web Editor widget.
==========================

""",
    'depends': ['web'],
    'data': [
        'security/ir.model.access.csv',
        'data/editor_assets.xml',
        'views/editor.xml',
        'views/snippets.xml',
    ],
    'assets': {

        #----------------------------------------------------------------------
        # MAIN BUNDLES
        #----------------------------------------------------------------------

        'web.assets_qweb': [
            'web_editor/static/src/xml/*.xml',
        ],
        'web_editor.assets_wysiwyg': [

            # lib
            'web_editor/static/lib/cropperjs/cropper.css',
            'web_editor/static/lib/cropperjs/cropper.js',
            'web_editor/static/lib/jquery-cropper/jquery-cropper.js',
            'web_editor/static/lib/jQuery.transfo.js',
            'web/static/lib/nearest/jquery.nearest.js',
            'web_editor/static/lib/webgl-image-filter/webgl-image-filter.js',
            'web_editor/static/lib/odoo-editor/odoo-editor.css',
            'web_editor/static/lib/odoo-editor/odoo-editor.js',

            # odoo utils
            ('include', 'web._assets_helpers'),

            'web_editor/static/src/scss/bootstrap_overridden.scss',
            'web/static/lib/bootstrap/scss/_variables.scss',

            # integration
            'web_editor/static/src/scss/wysiwyg.scss',
            'web_editor/static/src/scss/wysiwyg_iframe.scss',
            'web_editor/static/src/scss/wysiwyg_snippets.scss',

            'web_editor/static/src/js/wysiwyg/fonts.js',
            'web_editor/static/src/js/base.js',
            'web_editor/static/src/js/editor/editor.js',
            'web_editor/static/src/js/editor/image_processing.js',

            # widgets & plugins
            'web_editor/static/src/js/wysiwyg/widgets/**/*',
            'web_editor/static/src/js/editor/snippets.editor.js',
            'web_editor/static/src/js/editor/snippets.options.js',

            # Launcher
            'web_editor/static/src/js/wysiwyg/wysiwyg.js',
            'web_editor/static/src/js/wysiwyg/wysiwyg_snippets.js',
            'web_editor/static/src/js/wysiwyg/wysiwyg_iframe.js',
        ],
        'web.assets_common': [
            'web_editor/static/lib/vkbeautify/**/*',
            'web_editor/static/src/js/common/**/*',
            'web_editor/static/src/js/wysiwyg/root.js',
        ],
        'web.assets_backend': [
            'web_editor/static/src/scss/web_editor.common.scss',
            'web_editor/static/src/scss/web_editor.backend.scss',

            'web_editor/static/src/js/backend/**/*',
        ],
        'web.assets_frontend_minimal': [
            'web_editor/static/src/js/frontend/loader_loading.js',
        ],
        'web.assets_frontend': [
            'web_editor/static/src/scss/web_editor.common.scss',
            'web_editor/static/src/scss/web_editor.frontend.scss',

            'web_editor/static/src/js/frontend/loader.js',
        ],

        #----------------------------------------------------------------------
        # SUB BUNDLES
        #----------------------------------------------------------------------

        'web._assets_primary_variables': [
            'web_editor/static/src/scss/web_editor.variables.scss',
        ],
        'web._assets_secondary_variables': [
            'web_editor/static/src/scss/secondary_variables.scss',
        ],
        'web._assets_backend_helpers': [
            'web_editor/static/src/scss/bootstrap_overridden_backend.scss',
            'web_editor/static/src/scss/bootstrap_overridden.scss',
        ],
        'web._assets_frontend_helpers': [
            ('prepend', 'web_editor/static/src/scss/bootstrap_overridden.scss'),
        ],

        # ----------------------------------------------------------------------
        # TESTS BUNDLES
        # ----------------------------------------------------------------------

        'web.qunit_suite_tests': [
            ('include', 'web_editor.assets_wysiwyg'),

            'web_editor/static/tests/**/*',
        ],
    },
    'auto_install': True
}
