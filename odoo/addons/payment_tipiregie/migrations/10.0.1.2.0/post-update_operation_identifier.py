# -*- coding: utf-8 -*-

from odoo import api, SUPERUSER_ID

from odoo.addons.aquagliss_website_sale.models.aquagliss_transaction import TRANSACTION_TYPES, \
    TRANSACTION_TYPE_UNITARY, TRANSACTION_TYPE_RELOAD

__name__ = 'Update operation identifier'


def migrate(cr, version):
    """Update operation identifier."""
    if not version:
        return

    with api.Environment.manage():
        env = api.Environment(cr, SUPERUSER_ID, {})
        PaymentAcquirerModel = env['payment.acquirer']
        PaymentTransactionModel = env['payment.transaction']

        tipiregie_acquirers = PaymentAcquirerModel.search([('provider', '=', 'tipiregie')])
        txs = PaymentTransactionModel.search([('acquirer_id', 'in', tipiregie_acquirers.ids)])

        for tx in txs:
            if tx.acquirer_reference and len(tx.acquirer_reference) != 15:
                tx.write({
                    'tipiregie_operation_identifier': tx.acquirer_reference,
                    'acquirer_reference': ''
                 })

            if tx.acquirer_id.tipiregie_customer_number != 'dummy' \
                    and tx.tipiregie_operation_identifier \
                    and not tx.acquirer_reference:
                try:
                    data = tx.acquirer_id.tipiregie_get_result_from_web_service(tx.tipiregie_operation_identifier)
                except:
                    data = {}

                if 'refdet' in data:
                    tx.write({'acquirer_reference': data.get('refdet', '')})
