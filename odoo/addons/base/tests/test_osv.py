# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.osv.query import Query
from odoo.tests.common import BaseCase


class QueryTestCase(BaseCase):

    def test_basic_query(self):
        query = Query()
        query.add_table('product_product')
        query.add_table('product_template')
        query.where_clause.append("product_product.template_id = product_template.id")
        query.add_join(("product_template", "product_category", "categ_id", "id", "categ_id"), implicit=False, outer=False)  # add normal join
        query.add_join(("product_product", "res_user", "user_id", "id", "user_id"), implicit=False, outer=True)  # outer join
        self.assertEqual(query.get_sql()[0].strip(),
            """"product_product" LEFT JOIN "res_user" as "product_product__user_id" ON ("product_product"."user_id" = "product_product__user_id"."id"),"product_template" JOIN "product_category" as "product_template__categ_id" ON ("product_template"."categ_id" = "product_template__categ_id"."id") """.strip())
        self.assertEqual(query.get_sql()[1].strip(), """product_product.template_id = product_template.id""".strip())

    def test_query_chained_explicit_joins(self):
        query = Query()
        query.add_table('product_product')
        query.add_table('product_template')
        query.where_clause.append("product_product.template_id = product_template.id")
        query.add_join(("product_template", "product_category", "categ_id", "id", "categ_id"), implicit=False, outer=False)  # add normal join
        query.add_join(("product_template__categ_id", "res_user", "user_id", "id", "user_id"), implicit=False, outer=True)  # CHAINED outer join
        self.assertEqual(query.get_sql()[0].strip(),
            """"product_product","product_template" JOIN "product_category" as "product_template__categ_id" ON ("product_template"."categ_id" = "product_template__categ_id"."id") LEFT JOIN "res_user" as "product_template__categ_id__user_id" ON ("product_template__categ_id"."user_id" = "product_template__categ_id__user_id"."id")""".strip())
        self.assertEqual(query.get_sql()[1].strip(), """product_product.template_id = product_template.id""".strip())

    def test_mixed_query_chained_explicit_implicit_joins(self):
        query = Query()
        query.add_table('product_product')
        query.add_table('product_template')
        query.where_clause.append("product_product.template_id = product_template.id")
        query.add_join(("product_template", "product_category", "categ_id", "id", "categ_id"), implicit=False, outer=False)  # add normal join
        query.add_join(("product_template__categ_id", "res_user", "user_id", "id", "user_id"), implicit=False, outer=True)  # CHAINED outer join
        query.add_table('account_account')
        query.where_clause.append("product_category.expense_account_id = account_account.id")  # additional implicit join
        self.assertEqual(query.get_sql()[0].strip(),
            """"product_product","product_template" JOIN "product_category" as "product_template__categ_id" ON ("product_template"."categ_id" = "product_template__categ_id"."id") LEFT JOIN "res_user" as "product_template__categ_id__user_id" ON ("product_template__categ_id"."user_id" = "product_template__categ_id__user_id"."id"),"account_account" """.strip())
        self.assertEqual(query.get_sql()[1].strip(), """product_product.template_id = product_template.id AND product_category.expense_account_id = account_account.id""".strip())

    def test_raise_missing_lhs(self):
        query = Query()
        query.add_table('product_product')
        self.assertRaises(AssertionError, query.add_join, ("product_template", "product_category", "categ_id", "id", "categ_id"), implicit=False, outer=False)
