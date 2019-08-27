# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import random
import re
from unittest.mock import patch
import textwrap
from datetime import datetime, timedelta
from lxml import etree

from odoo.tests.common import BaseCase, tagged
from odoo.tools import topological_sort
from odoo.addons.web.controllers.main import HomeStaticTemplateHelpers


def sample(population):
    return random.sample(
        population,
            random.randint(0, min(len(population), 5)))


class TestModulesLoading(BaseCase):
    def setUp(self):
        self.mods = [str(i) for i in range(1000)]

    def test_topological_sort(self):
        random.shuffle(self.mods)
        modules = [
            (k, sample(self.mods[:i]))
            for i, k in enumerate(self.mods)]
        random.shuffle(modules)
        ms = dict(modules)

        seen = set()
        sorted_modules = topological_sort(ms)
        for module in sorted_modules:
            deps = ms[module]
            self.assertGreaterEqual(
                seen, set(deps),
                        'Module %s (index %d), ' \
                        'missing dependencies %s from loaded modules %s' % (
                    module, sorted_modules.index(module), deps, seen
                ))
            seen.add(module)


@tagged('static_templates')
class TestStaticInheritance(BaseCase):

    def setUp(self):
        super(TestStaticInheritance, self).setUp()
        # output is "manifest_glob" return
        self.modules = [
            ('module_1_file_1', None, 'module_1'),
            ('module_2_file_1', None, 'module_2'),
        ]

        self.template_files = {
            'module_1_file_1': b"""
                <templates id="template" xml:space="preserve">
                    <form t-name="template_1_1" random-attr="gloria">
                        <div>At first I was afraid</div>
                        <div>Kept thinking I could never live without you by my side</div>
                    </form>
                    <t t-name="template_1_2">
                        <div>And I grew strong</div>
                    </t>
                </templates>
                """,

            'module_2_file_1': b"""
                <templates id="template" xml:space="preserve">
                    <form t-name="template_2_1" t-inherit="module_1.template_1_1" t-inherit-mode="primary">
                        <xpath expr="//div[1]" position="after">
                            <div>I was petrified</div>
                        </xpath>
                        <xpath expr="//div[2]" position="after">
                            <div>But then I spent so many nights thinking how you did me wrong</div>
                        </xpath>
                    </form>
                    <div t-name="template_2_2">
                        <div>And I learned how to get along</div>
                    </div>
                    <form t-inherit="module_1.template_1_2" t-inherit-mode="extension">
                        <xpath expr="//div[1]" position="after">
                            <div>And I learned how to get along</div>
                        </xpath>
                    </form>
                </templates>
                """,
        }
        self._set_patchers()
        self._toggle_patchers('start')
        self._reg_replace_ws = r"\s|\t"

    def tearDown(self):
        super(TestStaticInheritance, self).tearDown()
        self._toggle_patchers('stop')

    # Custom Assert
    def assertXMLEqual(self, output, expected):
        self.assertTrue(output)
        self.assertTrue(expected)
        output = textwrap.dedent(output.decode('UTF-8')).strip()
        output = re.sub(self._reg_replace_ws, '', output)

        expected = textwrap.dedent(expected.decode('UTF-8')).strip()
        expected = re.sub(self._reg_replace_ws, '', expected)
        self.assertEqual(output, expected)

    # Private methods
    def _get_module_names(self):
        return ','.join([glob[2] for glob in self.modules])

    def _set_patchers(self):
        def _patched_for_manifest_glob(*args, **kwargs):
            # Ordered by module
            return self.modules

        def _patch_for_read_addon_file(*args, **kwargs):
            return self.template_files[args[1]]

        self.patchers = [
            patch.object(HomeStaticTemplateHelpers, '_manifest_glob', _patched_for_manifest_glob),
            patch.object(HomeStaticTemplateHelpers, '_read_addon_file', _patch_for_read_addon_file),
        ]

    def _toggle_patchers(self, mode):
        self.assertTrue(mode in ('start', 'stop'))
        for p in self.patchers:
            getattr(p, mode)()

    # Actual test cases
    def test_static_inheritance_01(self):
        contents = HomeStaticTemplateHelpers.get_qweb_templates(addons=self._get_module_names(), debug=True)
        expected = b"""
            <templates>
                <form t-name="template_1_1" random-attr="gloria">
                    <div>At first I was afraid</div>
                    <div>Kept thinking I could never live without you by my side</div>
                </form>
                <t t-name="template_1_2">
                    <div>And I grew strong</div>
                    <!-- Modified by anonymous_template_2 from module_2 -->
                    <div>And I learned how to get along</div>
                </t>
                <form t-name="template_2_1" random-attr="gloria" t-inherit="module_1.template_1_1">
                    <div>At first I was afraid</div>
                    <div>I was petrified</div>
                    <div>But then I spent so many nights thinking how you did me wrong</div>
                    <div>Kept thinking I could never live without you by my side</div>
                </form>
                <div t-name="template_2_2">
                    <div>And I learned how to get along</div>
                </div>
            </templates>
        """

        self.assertXMLEqual(contents, expected)

    def test_static_inheritance_in_same_module(self):
        self.modules = [
            ('module_1_file_1', None, 'module_1'),
            ('module_1_file_2', None, 'module_1'),
        ]

        self.template_files = {
            'module_1_file_1': b'''
                <templates id="template" xml:space="preserve">
                    <form t-name="template_1_1">
                        <div>At first I was afraid</div>
                        <div>Kept thinking I could never live without you by my side</div>
                    </form>
                </templates>
            ''',

            'module_1_file_2': b'''
                <templates id="template" xml:space="preserve">
                    <form t-name="template_1_2" t-inherit="template_1_1" t-inherit-mode="primary">
                        <xpath expr="//div[1]" position="after">
                            <div>I was petrified</div>
                        </xpath>
                    </form>
                </templates>
            '''
        }
        contents = HomeStaticTemplateHelpers.get_qweb_templates(addons=self._get_module_names(), debug=True)
        expected = b"""
            <templates>
                <form t-name="template_1_1">
                    <div>At first I was afraid</div>
                    <div>Kept thinking I could never live without you by my side</div>
                </form>
                <form t-name="template_1_2" t-inherit="template_1_1">
                    <div>At first I was afraid</div>
                    <div>I was petrified</div>
                    <div>Kept thinking I could never live without you by my side</div>
                </form>
            </templates>
        """

        self.assertXMLEqual(contents, expected)

    def test_static_inheritance_in_same_file(self):
        self.modules = [
            ('module_1_file_1', None, 'module_1'),
        ]

        self.template_files = {
            'module_1_file_1': b'''
                <templates id="template" xml:space="preserve">
                    <form t-name="template_1_1">
                        <div>At first I was afraid</div>
                        <div>Kept thinking I could never live without you by my side</div>
                    </form>
                    <form t-name="template_1_2" t-inherit="template_1_1" t-inherit-mode="primary">
                        <xpath expr="//div[1]" position="after">
                            <div>I was petrified</div>
                        </xpath>
                    </form>
                </templates>
            ''',
        }
        contents = HomeStaticTemplateHelpers.get_qweb_templates(addons=self._get_module_names(), debug=True)
        expected = b"""
            <templates>
                <form t-name="template_1_1">
                    <div>At first I was afraid</div>
                    <div>Kept thinking I could never live without you by my side</div>
                </form>
                <form t-name="template_1_2" t-inherit="template_1_1">
                    <div>At first I was afraid</div>
                    <div>I was petrified</div>
                    <div>Kept thinking I could never live without you by my side</div>
                </form>
            </templates>
        """

        self.assertXMLEqual(contents, expected)

    def test_static_inherit_extended_template(self):
        self.modules = [
            ('module_1_file_1', None, 'module_1'),
        ]
        self.template_files = {
            'module_1_file_1': b'''
                <templates id="template" xml:space="preserve">
                    <form t-name="template_1_1">
                        <div>At first I was afraid</div>
                        <div>Kept thinking I could never live without you by my side</div>
                    </form>
                    <form t-name="template_1_2" t-inherit="template_1_1" t-inherit-mode="extension">
                        <xpath expr="//div[1]" position="after">
                            <div>I was petrified</div>
                        </xpath>
                    </form>
                    <form t-name="template_1_3" t-inherit="template_1_1" t-inherit-mode="primary">
                        <xpath expr="//div[3]" position="after">
                            <div>But then I spent so many nights thinking how you did me wrong</div>
                        </xpath>
                    </form>
                </templates>
            ''',
        }
        contents = HomeStaticTemplateHelpers.get_qweb_templates(addons=self._get_module_names(), debug=True)
        expected = b"""
            <templates>
                <form t-name="template_1_1">
                    <div>At first I was afraid</div>
                    <!-- Modified by template_1_2 from module_1 -->
                    <div>I was petrified</div>
                    <div>Kept thinking I could never live without you by my side</div>
                </form>
                <form t-name="template_1_3" t-inherit="template_1_1">
                    <div>At first I was afraid</div>
                    <div>I was petrified</div>
                    <div>Kept thinking I could never live without you by my side</div>
                    <div>But then I spent so many nights thinking how you did me wrong</div>
                </form>
            </templates>
        """

        self.assertXMLEqual(contents, expected)

    def test_sibling_extension(self):
        self.modules = [
            ('module_1_file_1', None, 'module_1'),
            ('module_2_file_1', None, 'module_2'),
            ('module_3_file_1', None, 'module_3'),
        ]
        self.template_files = {
            'module_1_file_1': b'''
                <templates id="template" xml:space="preserve">
                    <form t-name="template_1_1">
                        <div>I am a man of constant sorrow</div>
                        <div>I've seen trouble all my days</div>
                    </form>
                </templates>
            ''',

            'module_2_file_1': b'''
                <templates id="template" xml:space="preserve">
                    <form t-name="template_2_1" t-inherit="module_1.template_1_1" t-inherit-mode="extension">
                        <xpath expr="//div[1]" position="after">
                            <div>In constant sorrow all through his days</div>
                        </xpath>
                    </form>
                </templates>
            ''',

            'module_3_file_1': b'''
                <templates id="template" xml:space="preserve">
                    <form t-name="template_3_1" t-inherit="module_1.template_1_1" t-inherit-mode="extension">
                        <xpath expr="//div[2]" position="after">
                            <div>Oh Brother !</div>
                        </xpath>
                    </form>
                </templates>
            '''
        }

        contents = HomeStaticTemplateHelpers.get_qweb_templates(addons=self._get_module_names(), debug=True)
        expected = b"""
            <templates>
                <form t-name="template_1_1">
                    <div>I am a man of constant sorrow</div>
                    <!-- Modified by template_2_1 from module_2 -->
                    <div>In constant sorrow all through his days</div>
                    <!-- Modified by template_3_1 from module_3 -->
                    <div>Oh Brother !</div>
                    <div>I've seen trouble all my days</div>
                </form>
            </templates>
        """

        self.assertXMLEqual(contents, expected)

    def test_static_misordered_modules(self):
        self.modules.reverse()
        with self.assertRaises(ValueError) as ve:
            HomeStaticTemplateHelpers.get_qweb_templates(addons=self._get_module_names(), debug=True)

        self.assertEqual(
            str(ve.exception),
            'Module module_1 not loaded or inexistent, or templates of addon being loaded (module_2) are misordered'
        )

    def test_static_misordered_templates(self):
        self.template_files['module_2_file_1'] = b"""
            <templates id="template" xml:space="preserve">
                <form t-name="template_2_1" t-inherit="module_2.template_2_2" t-inherit-mode="primary">
                    <xpath expr="//div[1]" position="after">
                        <div>I was petrified</div>
                    </xpath>
                </form>
                <div t-name="template_2_2">
                    <div>And I learned how to get along</div>
                </div>
            </templates>
        """
        with self.assertRaises(ValueError) as ve:
            HomeStaticTemplateHelpers.get_qweb_templates(addons=self._get_module_names(), debug=True)

        self.assertEqual(
            str(ve.exception),
            'No template found to inherit from. Module module_2 and template name template_2_2'
        )

    def _sick_script(self, nMod, nFilePerMod, nTemplatePerFile, stepInheritInModule=2, stepInheritPreviousModule=3):
        """
        Make a sick amount of templates to test perf
        nMod modules
        each module: has nFilesPerModule files, each of which contains nTemplatePerFile templates
        """
        self.modules = []
        self.template_files = {}
        number_templates = 0
        for m in range(nMod):
            for f in range(nFilePerMod):
                mname = 'mod_%s' % m
                fname = 'mod_%s_file_%s' % (m, f)
                self.modules.append((fname, None, mname))

                _file = '<templates id="template" xml:space="preserve">'

                for t in range(nTemplatePerFile):
                    _template = ''
                    if t % stepInheritInModule or t % stepInheritPreviousModule or t == 0:
                        _template += """
                            <div t-name="template_%(t_number)s_mod_%(m_number)s">
                                <div>Parent</div>
                            </div>
                        """

                    elif not t % stepInheritInModule and t >= 1:
                        _template += """
                            <div t-name="template_%(t_number)s_mod_%(m_number)s"
                                t-inherit="template_%(t_inherit)s_mod_%(m_number)s"
                                t-inherit-mode="primary">
                                <xpath expr="//div[1]" position="before">
                                    <div>Sick XPath</div>
                                </xpath>
                            </div>
                        """

                    elif not t % stepInheritPreviousModule and m >= 1:
                        _template += """
                            <div t-name="template_%(t_number)s_mod_%(m_number)s"
                                t-inherit="mod_%(m_module_inherit)s.template_%(t_module_inherit)s_mod_%(m_module_inherit)s"
                                t-inherit-mode="primary">
                                <xpath expr="//div[1]" position="inside">
                                    <div>Mental XPath</div>
                                </xpath>
                            </div>
                        """
                    if _template:
                        number_templates += 1

                    _template_number = 1000 * f + t
                    _file += _template % {
                        't_number': _template_number,
                        'm_number': m,
                        't_inherit': _template_number - 1,
                        't_module_inherit': _template_number,
                        'm_module_inherit': m - 1,
                    }
                _file += '</templates>'

                self.template_files[fname] = _file.encode()
        self.assertEqual(number_templates, nMod * nFilePerMod * nTemplatePerFile)

    def test_performance_2500(self):
        nMod, nFilePerMod, nTemplatePerFile = 50, 5, 10
        self._sick_script(nMod, nFilePerMod, nTemplatePerFile)

        before = datetime.now()
        contents = HomeStaticTemplateHelpers.get_qweb_templates(addons=self._get_module_names(), debug=True)
        after = datetime.now()
        self.assertLessEqual(after - before, timedelta(milliseconds=130))

        whole_tree = etree.fromstring(contents)
        self.assertEqual(len(whole_tree), nMod * nFilePerMod * nTemplatePerFile)

    def test_performance_25000(self):
        nMod, nFilePerMod, nTemplatePerFile = 50, 5, 100
        self._sick_script(nMod, nFilePerMod, nTemplatePerFile)

        before = datetime.now()
        HomeStaticTemplateHelpers.get_qweb_templates(addons=self._get_module_names(), debug=True)
        after = datetime.now()

        self.assertLessEqual(after - before, timedelta(milliseconds=1000))
