# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

# Copyright (c) 2022 WT-IO-IT GmbH (https://www.wt-io-it.at)
#                    Mag. Wolfgang Taferner <wolfgang.taferner@wt-io-it.at>
from odoo import models, _


class ECSalesReport(models.AbstractModel):
    _inherit = 'account.sales.report'

    def _is_available(self):
        return bool(self.env.ref('l10n_at.tax_report_line_l10n_at_tva_line_3_zm_igl', raise_if_not_found=False))

    def _get_non_generic_country_codes(self, options):
        codes = super(ECSalesReport, self)._get_non_generic_country_codes(options)
        if self._is_available():
            codes.add('AT')
        return codes

    def _get_ec_sale_code_options_data(self, options):
        ec_sale_code_options = super(ECSalesReport, self)._get_ec_sale_code_options_data(options)

        if self._is_available() and self._get_report_country_code(options) == 'AT':
            ec_sale_code_options.update({
                'goods': {
                    'name': 'Innergemeinschaftliche Lieferungen ',
                    'tax_report_line_ids':
                        self.env.ref('l10n_at.tax_report_line_l10n_at_tva_line_3_zm_igl').ids +
                        self.env.ref('l10n_at.tax_report_line_l10n_at_tva_line_4_8').ids +
                        self.env.ref('l10n_at.tax_report_line_l10n_at_tva_line_4_9').ids,
                    'code': 'L',
                },
                'triangular': {
                    'name': 'Dreiecksgeschäfte',
                    'tax_report_line_ids':
                        self.env.ref('l10n_at.tax_report_line_l10n_at_tva_line_3_zm_igl3').ids,
                    'code': 'D',
                },
                'services': {
                    'name': 'Dienstleistungen',
                    'tax_report_line_ids':
                        self.env.ref('l10n_at.tax_report_line_l10n_at_tva_line_3_zm_dl').ids,
                    'code': 'S',
                },
            })

        return ec_sale_code_options

    def _get_columns_name(self, options):
        if not self._is_available() or self._get_report_country_code(options) != 'AT':
            return super(ECSalesReport, self)._get_columns_name(options)

        return [
            {},
            {'name': _('Country Code')},
            {'name': _('VAT Number')},
            {'name': _('Code')},
            {'name': _('Amount'), 'class': 'number'},
        ]
