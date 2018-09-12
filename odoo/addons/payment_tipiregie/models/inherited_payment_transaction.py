# -*- coding: utf-8 -*-

from odoo import api, models, fields, _

from odoo.addons.payment.models.payment_acquirer import ValidationError

import logging
import uuid

_logger = logging.getLogger(__name__)


class TipiRegieTransaction(models.Model):
    _inherit = 'payment.transaction'

    tipiregie_operation_identifier = fields.Char(
        string='Operation identifier',
        help='Reference of the request of TX as stored in the acquirer database'
    )

    tipiregie_return_url = fields.Char(
        string='Return URL',
    )

    @api.model
    def _tipiregie_form_get_tx_from_data(self, idop):
        if not idop:
            error_msg = _('Tipi Regie: received data with missing idop!')
            _logger.error(error_msg)
            raise ValidationError(error_msg)

        # find tx -> @TDENOTE use txn_id ?
        txs = self.env['payment.transaction'].sudo().search([('tipiregie_operation_identifier', '=', idop)])
        if not txs or len(txs) > 1:
            error_msg = 'Tipi Regie: received data for idop %s' % idop
            if not txs:
                error_msg += '; no order found'
            else:
                error_msg += '; multiple order found'
            _logger.error(error_msg)
            raise ValidationError(error_msg)
        return txs[0]

    @api.multi
    def _tipiregie_form_validate(self, idop):
        self.ensure_one()

        if not idop:
            error_msg = _('Tipi Regie: received data with missing idop!')
            _logger.error(error_msg)
            raise ValidationError(error_msg)

        data = self.acquirer_id.tipiregie_get_result_from_web_service(idop)
        status = data.get('resultrans')

        if status in ['P']:
            _logger.info('Validated Tipi Regie payment for tx %s: set as done' % self.reference)
            self.write({
                'state': 'done',
                'date_validate': fields.Datetime.now()
            })
            return True
        elif status in ['A']:
            _logger.info('Received notification for Tipi Regie payment %s: set as canceled' % (self.reference))
            self.write({
                'state': 'cancel',
            })
            return True
        elif status in ['R']:
            error = 'Received notification for Tipi Regie payment %s: set as error' % self.reference, status
            _logger.info(error)
            self.write({
                'state': 'error',
                'state_message': error,
            })
            return True
        else:
            error = 'Received unrecognized status for Tipi Regie payment %s: %s, set as error' % (
                self.reference,
                status
            )
            _logger.error(error)
            self.write({
                'state': 'error',
                'state_message': error,
            })
            return False


    @api.multi
    def tipiregie_generate_operation(self):
        for tx in self:
            email = tx.partner_id.email
            price = int(tx.amount * 100)
            object = tx.reference.replace('/', '  slash  ')
            acquirer_reference = tx.acquirer_reference or '%.15d' % int(uuid.uuid4().int % 899999999999999)
            try:
                idop = tx.acquirer_id.tipiregie_get_id_op_from_web_service(email, price, object, acquirer_reference)
            except:
                idop = ''

            tx.write({
                'acquirer_reference': acquirer_reference,
                'tipiregie_operation_identifier': idop,
            })

        return
