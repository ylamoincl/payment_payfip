# -*- coding: utf-8 -*-

from odoo import api, models, fields, _
from odoo.http import request
from odoo.addons.payment.models.payment_acquirer import ValidationError

import logging
from datetime import datetime
import pytz

_logger = logging.getLogger(__name__)


class TipiRegieTransaction(models.Model):
    _inherit = 'payment.transaction'

    @api.model
    def _tipiregie_form_get_tx_from_data(self, data):
        reference = data.get('objet')
        if not reference:
            error_msg = _('Tipi Regie: received data with missing reference (%s)') % reference
            _logger.info(error_msg)
            raise ValidationError(error_msg)

        # find tx -> @TDENOTE use txn_id ?
        txs = self.env['payment.transaction'].sudo().search([('reference', '=', reference)])
        if not txs or len(txs) > 1:
            error_msg = 'Tipi Regie: received data for reference %s' % reference
            if not txs:
                error_msg += '; no order found'
            else:
                error_msg += '; multiple order found'
            _logger.error(error_msg)
            raise ValidationError(error_msg)
        return txs[0]

    @api.multi
    def _tipiregie_form_validate(self, data):
        status = data.get('resultrans')
        res = {
            'acquirer_reference': data.get('idOp'),
        }

        if status in ['P']:
            _logger.info('Validated Tipi Regie payment for tx %s: set as done' % self.reference)
            date_validate = fields.Datetime.now()
            dattrans = data.get('dattrans')
            heurtrans = data.get('heurtrans')
            if dattrans and heurtrans:
                tz = pytz.timezone('Europe/Paris')
                date_validate = datetime.strptime(dattrans + heurtrans, '%d%m%Y%H%M')
                date_validate = tz.localize(date_validate).astimezone(pytz.UTC)

            res.update(state='done', date_validate=date_validate)
            request.session.update({
                'sale_order_id': False,
                'sale_transaction_id': False,
                'website_sale_current_pl': False,
            })
        elif status in ['A']:
            _logger.info('Received notification for Tipi Regie payment %s: set as canceled' % (self.reference))
            res.update(state='cancel')
        elif status in ['R']:
            error = 'Received notification for Tipi Regie payment %s: set as error' % self.reference, status
            _logger.info(error)
            res.update(state='error', state_message=error)
        else:
            error = 'Received unrecognized status for Tipi Regie payment %s: %s, set as error' % (
                self.reference,
                status
            )
            _logger.error(error)
            res.update(state='error', state_message=error)

        return self.write(res)
