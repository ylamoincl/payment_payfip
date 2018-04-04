# coding: utf8

from odoo import http
from odoo.http import request
from odoo.addons.payment.models.payment_acquirer import ValidationError

import pprint
import logging
import werkzeug
import urlparse

_logger = logging.getLogger(__name__)


class TipiRegieController(http.Controller):
    _notify_url = '/payment/tipiregie/ipn/'
    _return_url = '/payment/tipiregie/dpn/'
    _cancel_url = '/payment/tipiregie/cancel/'

    @http.route('/payment/tipiregie/ipn/', type='http', auth='none', methods=['POST'], csrf=False)
    def tipiregie_ipn(self, **post):
        """Process Tipi Regie IPN."""
        _logger.debug('Beginning Tipi Regie IPN form_feedback with post data %s', pprint.pformat(post))
        try:
            self.tipiregie_validate_data(**post)
        except ValidationError:
            _logger.exception('Unable to validate the Tipi Regie payment')
        return ''

    @http.route('/payment/tipiregie/dpn', type='http', auth="none", methods=['POST', 'GET'], csrf=False)
    def tipiregie_dpn(self, **post):
        """Process Tipi Regie DPN."""
        _logger.debug('Beginning Tipi Regie DPN form_feedback with post data %s', pprint.pformat(post))
        self.tipiregie_validate_data(**post)
        base_url = http.request.env['ir.config_parameter'].get_param('web.base.url')
        return_url = request.env['payment.acquirer'].search(
            [('provider', '=', 'tipiregie')]).tipiregie_return_payment_url_confirm

        return werkzeug.utils.redirect('%s' % urlparse.urljoin(base_url, return_url))

    @http.route('/payment/tipiregie/cancel', type='http', auth="none", csrf=False)
    def tipiregie_cancel(self, **post):
        """Process Tipi Regie cancel."""
        _logger.debug('Beginning Tipi Regie cancel with post data %s', pprint.pformat(post))
        self.tipiregie_validate_data(**post)
        base_url = http.request.env['ir.config_parameter'].get_param('web.base.url')
        return_url = request.env['payment.acquirer'].search(
            [('provider', '=', 'tipiregie')]).tipiregie_return_payment_url_cancel
        return werkzeug.utils.redirect('%s' % urlparse.urljoin(base_url, return_url))

    def tipiregie_validate_data(self, **post):
        """Check data returned from Tipi Regie."""
        if not post or not post.get('idop'):
            raise ValidationError("No idOp found for transaction on Tipi Regie")

        data = request.env['payment.acquirer'].tipiregie_get_result_from_web_service(post.get('idop'))
        return request.env['payment.transaction'].form_feedback(data, 'tipiregie')
