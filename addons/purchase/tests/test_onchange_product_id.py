from openerp.tests.common import TransactionCase

class TestOnchangeProductId(TransactionCase):
    """Test that when an included tax is mapped by a fiscal position, the included tax must be
    subtracted to the price of the product.
    """

    def setUp(self):
        super(TestOnchangeProductId, self).setUp()
        self.fiscal_position_model = self.registry('account.fiscal.position')
        self.fiscal_position_tax_model = self.registry('account.fiscal.position.tax')
        self.tax_model = self.registry('account.tax')
        self.res_partner_model = self.registry('res.partner')
        self.product_model = self.registry('product.product')
        self.product_uom_model = self.registry('product.uom')
        self.po_line_model = self.registry('purchase.order.line')

    def test_onchange_product_id(self):
        cr, uid = self.cr, self.uid
        uom_id = self.product_uom_model.search(cr, uid, [('name', '=', 'Unit(s)')])[0]
        partner_id = self.res_partner_model.create(cr, uid, dict(name="George"))
        tax_include_id = self.tax_model.create(cr, uid, dict(name="Include tax",
                                                             amount_type='percent',
                                                             amount='21.0',
                                                             type_tax_use='purchase',
                                                             price_include=True))
        tax_exclude_id = self.tax_model.create(cr, uid, dict(name="Exclude tax",
                                                             amount_type='percent',
                                                             type_tax_use='purchase',
                                                             amount='0.00'))
        product_id = self.product_model.create(cr, uid, dict(name="Voiture",
                                                             list_price='121',
                                                             supplier_taxes_id=[(6, 0, [tax_include_id])]))
        fp_id = self.fiscal_position_model.create(cr, uid, dict(name="fiscal position",
                                                                sequence=1))
        self.fiscal_position_tax_model.create(cr, uid, dict(position_id=fp_id,
                                                            tax_src_id=tax_include_id,
                                                            tax_dest_id=tax_exclude_id))
        res = self.po_line_model.onchange_product_id(cr, uid, [], product_id, 1.0, uom_id, partner_id,
                                                     fiscal_position_id=fp_id)

        self.assertEquals(0, res['value']['price_unit'], "The default price for products having no seller set is 0")
        #TODO: add back a test on this
        #self.assertEquals(100, res['value']['price_unit'], "The included tax must be subtracted to the price")
