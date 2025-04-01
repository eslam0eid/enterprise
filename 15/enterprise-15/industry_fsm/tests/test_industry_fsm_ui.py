# Part of Odoo. See LICENSE file for full copyright and licensing details.
# -*- coding: utf-8 -*-

import odoo.tests
from datetime import datetime


@odoo.tests.tagged('post_install', '-at_install')
class TestUi(odoo.tests.HttpCase):
    def test_ui(self):

        self.env['res.partner'].create([
            {'name': 'Leroy Philippe', 'email': 'leroy.philou@example.com'},
            {'name': 'Brandon Freeman', 'email': 'brandon.freeman55@example.com'},
        ])
        self.start_tour("/web", 'industry_fsm_tour', login="admin")

    def test_planned_date_begin_display_format(self):
        self.env['res.lang']._activate_lang('fr_FR')
        customer = self.env['res.partner'].create({'name': 'Leroy Philippe', 'email': 'leroy.philou@example.com'})
        task = self.env['project.task'].create({
            'name': 'test task',
            'project_id': self.env.ref('industry_fsm.fsm_project').id,
            'user_ids': self.env.ref('base.user_admin').ids,
            'partner_id': customer.id,
            'planned_date_begin': datetime(2020, 5, 14, 8, 0),
        })

        self.assertEqual(self.env['project.task'].with_context({'fsm_task_kanban_whole_date': False, 'lang': 'en_US'}).search([('id', '=', task.id)]).planned_date_begin_formatted, "8:00 AM")
        self.env['project.task'].invalidate_cache(fnames=['planned_date_begin_formatted'])
        self.assertEqual(self.env['project.task'].with_context({'fsm_task_kanban_whole_date': True, 'lang': 'en_US'}).search([('id', '=', task.id)]).planned_date_begin_formatted, "05/14/2020")
        self.env['project.task'].invalidate_cache(fnames=['planned_date_begin_formatted'])
        self.assertEqual(self.env['project.task'].with_context({'fsm_task_kanban_whole_date': False, 'lang': 'fr_FR'}).search([('id', '=', task.id)]).planned_date_begin_formatted, "08:00")
        self.env['project.task'].invalidate_cache(fnames=['planned_date_begin_formatted'])
        self.assertEqual(self.env['project.task'].with_context({'fsm_task_kanban_whole_date': True, 'lang': 'fr_FR'}).search([('id', '=', task.id)]).planned_date_begin_formatted, "14/05/2020")
