from odoo import models, fields
from odoo.tools import float_compare


class AccountMove(models.Model):
    _name = 'account.move'
    _inherit = ['account.move', 'account.avatax']

    avatax_tax_date = fields.Date(
        string="Avatax Date",
        help="Avatax will use this date to calculate the tax on this invoice. "
             "If not specified it will use the Invoice Date.",
    )

    def _post(self, soft=True):
        # Ensure taxes are correct before posting
        self.button_update_avatax()

        posted = super()._post(soft)

        # Update the invoice on Avatax's side with the invoice name and commit
        self.button_update_avatax(commit=True)

        return posted

    def _send_to_avatax(self, commit=False):
        self.ensure_one()

        # don't recalculate posted invoices unless we're setting the invoice name on Avatax's side
        if not commit and self.state == "posted":
            return False

        return self.fiscal_position_id.is_avatax and self.move_type in ("out_invoice", "out_refund")

    def button_draft(self):
        super().button_draft()
        for record in self.filtered(lambda m: m._send_to_avatax()):
            record._uncommit_avatax_transaction()

    def button_update_avatax(self, commit=False):
        for record in self.filtered(lambda m: m._send_to_avatax(commit=commit)):
            record._compute_avalara_taxes(commit)

    def unlink(self):
        for record in self.filtered(lambda m: m._send_to_avatax()):
            record._void_avatax_transaction()
        super().unlink()

    def _compute_avalara_taxes(self, commit):
        """
        param commit: used when creating a new Avatax transaction with the invoice name after an invoice was posted
        """
        mapped_taxes, summary = self._map_avatax(commit)

        # Do not change taxes of a committed and posted invoice
        if commit:
            return

        for line, detail in mapped_taxes.items():
            line.tax_ids = detail['tax_ids']
            line.price_total = detail['tax_amount'] + detail['total']
        self.with_context(check_move_validity=False)._recompute_dynamic_lines(recompute_all_taxes=True)

        # Check that Odoo computation = Avatax computation
        if not summary:
            return
        for record in self:
            for tax, avatax_amount in summary[record].items():
                tax_line = record.line_ids.filtered(lambda l: l.tax_line_id == tax)

                # Tax avatax returns is opposite from aml balance (avatax is positive on invoice, negative on refund)
                avatax_amount_currency = -avatax_amount
                avatax_balance = (
                    avatax_amount_currency
                    if tax_line.currency_id == tax_line.company_currency_id else
                    tax_line.currency_id._convert(avatax_amount, tax_line.company_currency_id, tax_line.company_id, tax_line.date)
                )

                # Check that the computed taxes are close enough. For exemptions this will never be the case
                # since Avatax will return the non-exempt rate%. In that case this will manually fix the tax
                # lines to what Avatax says they should be.
                if float_compare(tax_line.amount_currency, avatax_amount_currency, precision_rounding=record.currency_id.rounding) != 0:
                    tax_line.with_context(check_move_validity=False).amount_currency = avatax_amount_currency
                    if avatax_balance <= 0:
                        tax_line.with_context(check_move_validity=False).debit = 0.0
                        tax_line.with_context(check_move_validity=False).credit = abs(avatax_balance)
                    else:
                        tax_line.with_context(check_move_validity=False).debit = abs(avatax_balance)
                        tax_line.with_context(check_move_validity=False).credit = 0.0

                    record.with_context(check_move_validity=False)._recompute_dynamic_lines()
                elif not record.currency_id.is_zero(tax_line.amount_currency + avatax_amount):
                    # Correct rounding error if any
                    tax_line.write({
                        'amount_currency': avatax_amount_currency,
                        'debit': avatax_balance if avatax_balance < 0 else 0,
                        'credit': avatax_balance if avatax_balance > 0 else 0,
                    })

    def _get_avatax_invoice_lines(self):
        return [
            self._get_avatax_invoice_line(
                product=line.product_id,
                price_subtotal=line.price_subtotal if self.move_type == 'out_invoice' else -line.price_subtotal,
                quantity=line.quantity,
                line_id='%s,%s' % (line._name, line.id),
            )
            for line in self.invoice_line_ids.filtered(lambda l: not l.display_type)
        ]

    def _get_avatax_dates(self):
        if self.reversed_entry_id:
            reversed_override_date = self.reversed_entry_id.avatax_tax_date or self.reversed_entry_id.invoice_date
            return self.invoice_date, reversed_override_date
        return self.invoice_date, self.avatax_tax_date

    def _get_avatax_document_type(self):
        return {
            'out_invoice': 'SalesInvoice',
            'out_refund': 'ReturnInvoice',
            'in_invoice': 'PurchaseInvoice',
            'in_refund': 'ReturnInvoice',
            'entry': 'Any',
        }[self.move_type]

    def _get_avatax_description(self):
        return 'Journal Entry'
