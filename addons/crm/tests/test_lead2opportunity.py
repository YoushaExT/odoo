# -*- coding: utf-8 -*-

from .common import TestCrmCommon


class TestLead2opportunity2win(TestCrmCommon):

    def test_lead2opportunity2win(self):
        """ Tests for Test Lead 2 opportunity 2 win """
        CrmLead2OpportunityPartnerMass = self.env['crm.lead2opportunity.partner.mass']
        default_stage_id = self.stage_gen_1.id

        crm_case_2 = self.env['crm.lead'].create({
            'name': 'Design Software',
            'type': 'lead',
        })
        crm_case_3 = self.env['crm.lead'].create({
            'name': 'Pricing for 25 desks',
            'type': 'lead',
        })
        crm_case_13 = self.env['crm.lead'].create({
            'name': 'Quote for 600 Chairs',
            'type': 'opportunity',
            'contact_name': 'Will McEncroe',
        })

        # In order to test the conversion of a lead into a opportunity,
        # I set lead to open stage.
        crm_case_3.write({'stage_id': default_stage_id})

        # I check if the lead stage is "Open".
        # self.assertEqual(crm_case_3.stage_id.sequence, 1, 'Lead stage is Open')

        # Giving access rights of salesman to convert the lead into opportunity.
        # I convert lead into opportunity for exiting customer.
        crm_case_3.with_user(self.user_sales_manager).convert_opportunity(self.contact_2.id)

        # I check details of converted opportunity.
        self.assertEqual(crm_case_3.type, 'opportunity', 'Lead is not converted to opportunity!')
        self.assertEqual(crm_case_3.partner_id.id, self.contact_2.id, 'Partner mismatch!')
        self.assertEqual(crm_case_3.stage_id.id, default_stage_id, 'Stage of opportunity is incorrect!')

        # Now I schedule meeting with customer.
        crm_case_3.action_schedule_meeting()

        # After communicated  with customer, I put some notes with contract details.
        crm_case_3.message_post(subject='Test note', body='Détails envoyés par le client sur ​​le FAX pour la qualité')

        # I convert mass lead into opportunity customer.
        mass = CrmLead2OpportunityPartnerMass.with_user(self.user_sales_manager).with_context({'active_model': 'crm.lead', 'active_ids': [crm_case_13.id, crm_case_2.id], 'active_id': crm_case_13.id}).create({
            'user_ids': [(6, 0, self.env.ref('base.user_root').ids)],
            'team_id': self.env.ref("sales_team.team_sales_department").id
        })
        mass.with_user(self.user_sales_manager).mass_convert()

        # Now I check first lead converted on opportunity.
        self.assertEqual(crm_case_13.name, "Quote for 600 Chairs", "Opportunity name not correct")
        self.assertEqual(crm_case_13.type, 'opportunity', "Lead is not converted to opportunity!")
        expected_partner = "Will McEncroe"
        self.assertEqual(crm_case_13.partner_id.name, expected_partner, "Partner mismatch! %s vs %s" % (crm_case_13.partner_id.name, expected_partner))
        self.assertEqual(crm_case_13.stage_id.id, default_stage_id, "Stage of probability is incorrect!")

        # Then check for second lead converted on opportunity.
        self.assertEqual(crm_case_2.name, "Design Software", "Opportunity name not correct")
        self.assertEqual(crm_case_2.type, "opportunity", "Lead is not converted to opportunity!")
        self.assertEqual(crm_case_2.stage_id.id, default_stage_id, "Stage of probability is incorrect!")

        # I loose the second opportunity
        crm_case_2.action_set_lost()

        # I check details of the opportunity after the loose
        self.assertEqual(crm_case_2.probability, 0.0, "Revenue probability should be 0.0!")

    def test_lead2opportunity_assign_salesmen(self):
        """ Tests for Test Lead2opportunity Assign Salesmen """
        CrmLead2OpportunityPartnerMass = self.env['crm.lead2opportunity.partner.mass']
        LeadSaleman = self.env['crm.lead'].with_user(self.user_sales_manager)
        default_stage_id = self.stage_gen_1.id

        # During a lead to opp conversion, salesmen should be assigned to leads following the round-robin method.  Start by creating 4 salesmen (A to D) and 6 leads (1 to 6).
        test_res_user_01 = self.env['res.users'].create({
            'name': 'Test user A',
            'login': 'tua@example.com',
        })
        test_res_user_02 = self.env['res.users'].create({
            'name': 'Test user B',
            'login': 'tub@example.com',
        })
        test_res_user_03 = self.env['res.users'].create({
            'name': 'Test user C',
            'login': 'tuc@example.com',
        })
        test_res_user_04 = self.env['res.users'].create({
            'name': 'Test user D',
            'login': 'tud@example.com',
        })

        # Salesman also creates lead so giving access rights of salesman.
        test_crm_lead_01 = LeadSaleman.create({
            'type': 'lead',
            'name': 'Test lead 1',
            'email_from': 'Raoul Grosbedon <raoul@grosbedon.fr>',
            'stage_id': default_stage_id
        })
        test_crm_lead_02 = LeadSaleman.create({
            'type': 'lead',
            'name': 'Test lead 2',
            'email_from': 'Raoul Grosbedon <raoul@grosbedon.fr>',
            'stage_id': default_stage_id
        })
        test_crm_lead_03 = LeadSaleman.create({
            'type': 'lead',
            'name': 'Test lead 3',
            'email_from': 'Raoul Grosbedon <raoul@grosbedon.fr>',
            'stage_id': default_stage_id
        })
        test_crm_lead_04 = LeadSaleman.create({
            'type': 'lead',
            'name': 'Test lead 4',
            'email_from': 'Fabrice Lepoilu',
            'stage_id': default_stage_id
        })
        test_crm_lead_05 = LeadSaleman.create({
            'type': 'lead',
            'name': 'Test lead 5',
            'email_from': 'Fabrice Lepoilu',
            'stage_id': default_stage_id
        })
        test_crm_lead_06 = LeadSaleman.create({
            'type': 'lead',
            'name': 'Test lead 6',
            'email_from': 'Agrolait SuperSeed SA',
            'stage_id': default_stage_id
        })

        lead_ids = [test_crm_lead_01.id, test_crm_lead_02.id, test_crm_lead_03.id, test_crm_lead_04.id, test_crm_lead_05.id, test_crm_lead_06.id]
        salesmen_ids = [test_res_user_01.id, test_res_user_02.id, test_res_user_03.id, test_res_user_04.id]

        # Salesman create a mass convert wizard and convert all the leads.
        additionnal_context = {'active_model': 'crm.lead', 'active_ids': lead_ids, 'active_id': test_crm_lead_01.id}
        mass = CrmLead2OpportunityPartnerMass.with_user(self.user_sales_manager).with_context(**additionnal_context).create({
            'user_ids': [(6, 0, salesmen_ids)],
            'team_id': self.env.ref("sales_team.team_sales_department").id,
            'deduplicate': False,
            'force_assignation': True
        })
        mass.with_user(self.user_sales_manager).mass_convert()

        # The leads should now be opps with a salesman and a salesteam.  Also, salesmen should have been assigned following a round-robin method.
        opps = self.env['crm.lead'].with_user(self.user_sales_manager).browse(lead_ids)
        i = 0
        for opp in opps:
            self.assertEqual(opp.type, 'opportunity', 'Type mismatch: this should be an opp, not a lead')
            self.assertEqual(opp.user_id.id, salesmen_ids[i], 'Salesman mismatch: expected salesman %r, got %r' % (salesmen_ids[i], opp.user_id.id))
            i = i + 1 if (i < len(salesmen_ids) - 1) else 0
