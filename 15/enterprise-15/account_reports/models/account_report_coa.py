# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
from copy import deepcopy

from odoo import models, api, _, fields
from odoo.tools.misc import DEFAULT_SERVER_DATE_FORMAT


class AccountChartOfAccountReport(models.AbstractModel):
    _name = "account.coa.report"
    _description = "Chart of Account Report"
    _inherit = "account.report"

    filter_date = {'mode': 'range', 'filter': 'this_month'}
    filter_comparison = {'date_from': '', 'date_to': '', 'filter': 'no_comparison', 'number_period': 1}
    filter_all_entries = False
    filter_journals = True
    filter_analytic = True
    filter_unfold_all = False
    filter_cash_basis = None
    filter_hierarchy = False
    MAX_LINES = None

    @api.model
    def _get_templates(self):
        templates = super(AccountChartOfAccountReport, self)._get_templates()
        templates['main_template'] = 'account_reports.main_template_with_filter_input_accounts'
        return templates

    @api.model
    def _get_columns(self, options):
        header1 = [
            {'name': '', 'style': 'width: 100%'},
            {'name': _('Initial Balance'), 'class': 'number', 'colspan': 2},
        ] + [
            {'name': period['string'], 'class': 'number', 'colspan': 2}
            for period in reversed(options['comparison'].get('periods', []))
        ] + [
            {'name': options['date']['string'], 'class': 'number', 'colspan': 2},
            {'name': _('End Balance'), 'class': 'number', 'colspan': 2},
        ]
        header2 = [
            {'name': '', 'style': 'width:40%'},
            {'name': _('Debit'), 'class': 'number o_account_coa_column_contrast'},
            {'name': _('Credit'), 'class': 'number o_account_coa_column_contrast'},
        ]
        if options.get('comparison') and options['comparison'].get('periods'):
            header2 += [
                {'name': _('Debit'), 'class': 'number o_account_coa_column_contrast'},
                {'name': _('Credit'), 'class': 'number o_account_coa_column_contrast'},
            ] * len(options['comparison']['periods'])
        header2 += [
            {'name': _('Debit'), 'class': 'number o_account_coa_column_contrast'},
            {'name': _('Credit'), 'class': 'number o_account_coa_column_contrast'},
            {'name': _('Debit'), 'class': 'number o_account_coa_column_contrast'},
            {'name': _('Credit'), 'class': 'number o_account_coa_column_contrast'},
        ]
        return [header1, header2]

    @api.model
    def _get_lines(self, options, line_id=None):
        # Create new options with 'unfold_all' to compute the initial balances.
        # Then, the '_do_query' will compute all sums/unaffected earnings/initial balances for all comparisons.
        new_options = options.copy()
        new_options['unfold_all'] = True

        # adding an end balance column computed over the entire period
        end_balance_date_to = new_options['date']['date_to']
        end_balance_date_from = new_options['comparison']['periods'][-1]['date_from'] if new_options['comparison']['periods'] else new_options['date']['date_from']
        period_options = new_options.copy()
        period_options['date'] = {
            'mode': 'range',
            'date_to': fields.Date.from_string(end_balance_date_to).strftime(DEFAULT_SERVER_DATE_FORMAT),
            'date_from': fields.Date.from_string(end_balance_date_from).strftime(DEFAULT_SERVER_DATE_FORMAT)
        }
        options_list = [period_options] + self._get_options_periods_list(new_options)

        accounts_results, taxes_results = self.env['account.general.ledger']._do_query(options_list, fetch_lines=False)

        lines = []
        totals = [0.0] * (2 * (len(options_list) + 1))

        # Add lines, one per account.account record.
        for account, periods_results in accounts_results:
            sums = []
            for i, period_values in enumerate(reversed(periods_results)):
                account_sum = period_values.get('sum', {})
                account_un_earn = period_values.get('unaffected_earnings', {})
                account_init_bal = period_values.get('initial_balance', {})

                if i == 0:
                    # Append the initial balances.
                    initial_balance = account_init_bal.get('balance', 0.0) + account_un_earn.get('balance', 0.0)
                    sums += [
                        initial_balance > 0 and initial_balance or 0.0,
                        initial_balance < 0 and -initial_balance or 0.0,
                    ]

                if i == len(periods_results) - 1:
                    # Append the end balances.
                    end_balance = account_sum.get('balance', 0.0) + account_un_earn.get('balance', 0.0)
                    sums += [
                        end_balance > 0 and end_balance or 0.0,
                        end_balance < 0 and -end_balance or 0.0,
                    ]
                else:
                    # Append the debit/credit columns.
                    sums += [
                        account_sum.get('debit', 0.0) - account_init_bal.get('debit', 0.0),
                        account_sum.get('credit', 0.0) - account_init_bal.get('credit', 0.0),
                    ]

            columns = []
            for i, value in enumerate(sums):
                # Update totals.
                totals[i] += value

                # Create columns.
                columns.append({'name': self.format_value(value, blank_if_zero=True), 'class': 'number', 'no_format_name': value})

            name = account.name_get()[0][1]

            lines.append({
                'id': self._get_generic_line_id('account.account', account.id),
                'name': name,
                'code': account.code,
                'title_hover': name,
                'columns': columns,
                'unfoldable': False,
                'caret_options': 'account.account',
                'class': 'o_account_searchable_line o_account_coa_column_contrast',
            })

        # Total report line.
        lines.append({
             'id': self._get_generic_line_id(None, None, markup='grouped_accounts_total'),
             'name': _('Total'),
             'class': 'total o_account_coa_column_contrast',
             'columns': [{'name': self.format_value(total), 'class': 'number'} for total in totals],
             'level': 1,
        })

        return lines

    @api.model
    def _get_report_name(self):
        return _("Trial Balance")
