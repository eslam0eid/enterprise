# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from collections import defaultdict

from odoo import models

from odoo.addons.sale_timesheet_enterprise.models.sale import DEFAULT_INVOICED_TIMESHEET


class ProjectTask(models.Model):
    _inherit = 'project.task'

    def read(self, fields=None, load='_classic_read'):
        """ Override read method to filter timesheets in the task(s) is the user is portal user
            and the sale.invoiced_timesheet configuration is set to 'approved'
            Then we need to give the id of timesheets which is validated.
        """
        result = super().read(fields=fields, load=load)
        if fields and 'timesheet_ids' in fields and self.env.user.has_group('base.group_portal'):
            # We need to check if configuration
            param_invoiced_timesheet = self.env['ir.config_parameter'].sudo().get_param('sale.invoiced_timesheet', DEFAULT_INVOICED_TIMESHEET)
            if param_invoiced_timesheet == 'approved':
                timesheets_read_group = self.env['account.analytic.line'].read_group(
                    [('task_id', 'in', self.ids), ('validated', '=', True)],
                    ['ids:array_agg(id)', 'task_id'],
                    ['task_id'],
                )
                timesheets_dict = {res['task_id'][0]: res['ids'] for res in timesheets_read_group}
                for record_read in result:
                    record_read['timesheet_ids'] = timesheets_dict.get(record_read['id'], [])
        return result

    def _get_portal_effective_hours_per_task_id(self):
        is_portal_user = self.user_has_groups('base.group_portal')
        timesheets_per_task = None
        if is_portal_user:
            timesheet_read_group = self.env['account.analytic.line'].sudo().read_group(
                [
                    ('project_id', '!=', False),
                    ('task_id', 'in', self.ids),
                    ('validated', 'in', [True, self.env['ir.config_parameter'].sudo().get_param('sale.invoiced_timesheet', DEFAULT_INVOICED_TIMESHEET) == 'approved'])
                ],
                ['task_id', 'unit_amount'],
                ['task_id'],
            )
            timesheets_per_task = {res['task_id'][0]: res['unit_amount'] for res in timesheet_read_group}
        effective_hours_per_task_id = defaultdict(lambda: 0.0)
        for task in self:
            effective_hours = 0.0
            if not is_portal_user:
                effective_hours = task.effective_hours
            elif timesheets_per_task:
                effective_hours = timesheets_per_task.get(task.id, 0.0)
            effective_hours_per_task_id[task.id] = effective_hours
        return effective_hours_per_task_id
