# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.addons.payment_tipiregie.controllers.main import TipiRegieController
from odoo.addons.payment.models.payment_acquirer import ValidationError

import requests
from requests.exceptions import ConnectionError
from xml.etree import ElementTree
import urlparse
import logging

_logger = logging.getLogger(__name__)


class TipiRegieAcquirer(models.Model):
    _inherit = 'payment.acquirer'

    provider = fields.Selection(selection_add=[('tipiregie', 'Tipi Régie')])

    tipiregie_customer_number = fields.Char(string='Customer number', required_if_provider='tipiregie')
    tipiregie_form_action_url = fields.Char(string='Form action URL', required_if_provider='tipiregie')
    tipiregie_activation_mode = fields.Boolean(string='Activation mode', default=False)

    @api.constrains('tipiregie_customer_number')
    def _check_tipiregie_customer_number(self):
        self.ensure_one()
        if self.provider == 'tipiregie' and self.tipiregie_customer_number != 'dummy':
            self._tipiregie_check_web_service()

    @api.constrains('environment')
    def _check_environment(self):
        self.ensure_one()
        if self.provider == 'tipiregie' and self.environment != 'test':
            self.tipiregie_activation_mode = False

    @api.constrains('website_published')
    def _check_website_published(self):
        self.ensure_one()
        if self.provider == 'tipiregie' and self.website_published:
            self._tipiregie_check_web_service()
            self.tipiregie_activation_mode = False

    @api.constrains('tipiregie_activation_mode')
    def _check_tipiregie_activation_mode(self):
        self.ensure_one()
        if self.provider == 'tipiregie' and self.tipiregie_activation_mode and (
                not self.website_published or self.environment not in ['test']):
            raise ValidationError(_("TipiRégie: activation mode can be activate in test environment only and if "
                                    "the payment acquirer is published on the website."))

    @api.model
    def _get_soap_url(self):
        return "https://www.tipi.budget.gouv.fr/tpa/services/securite"

    @api.model
    def _get_soap_namespaces(self):
        return {
            'ns1': "http://securite.service.tpa.cp.finances.gouv.fr/services/mas_securite/"
                   "contrat_paiement_securise/PaiementSecuriseService"
        }

    @api.model
    def _get_feature_support(self):
        """Get advanced feature support by provider.

        Each provider should add its technical in the corresponding
        key for the following features:
            * fees: support payment fees computations
            * authorize: support authorizing payment (separates
                         authorization and capture)
            * tokenize: support saving payment data in a payment.tokenize
                        object
        """
        res = super(TipiRegieAcquirer, self)._get_feature_support()
        res['authorize'].append('tipiregie')
        return res

    @api.multi
    def tipiregie_get_form_action_url(self):
        self.ensure_one()
        return '/payment/tipiregie/pay'

    @api.multi
    def tipiregie_get_id_op_from_web_service(self, email, price, object, acquirer_reference):
        self.ensure_one()

        mode = 'TEST'
        if self.environment == 'prod':
            mode = 'PRODUCTION'

        base_url = self.env['ir.config_parameter'].get_param('web.base.url')
        exer = fields.Datetime.now()[:4]
        numcli = self.tipiregie_customer_number
        saisie = 'X' if self.tipiregie_activation_mode else ('T' if mode == 'TEST' else 'W')
        urlnotif = '%s' % urlparse.urljoin(base_url, '/payment/tipiregie/ipn')
        urlredirect = '%s' % urlparse.urljoin(base_url, '/payment/tipiregie/dpn')

        soap_body = '<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" ' \
                    'xmlns:pai="http://securite.service.tpa.cp.finances.gouv.fr/services/mas_securite/' \
                    'contrat_paiement_securise/PaiementSecuriseService">'
        soap_body += """
                <soapenv:Header/>
                <soapenv:Body>
                    <pai:creerPaiementSecurise>
                        <arg0>
                            <exer>%s</exer>
                            <mel>%s</mel>
                            <montant>%s</montant>
                            <numcli>%s</numcli>
                            <objet>%s</objet>
                            <refdet>%s</refdet>
                            <saisie>%s</saisie>
                            <urlnotif>%s</urlnotif>
                            <urlredirect>%s</urlredirect>
                        </arg0>
                    </pai:creerPaiementSecurise>
                </soapenv:Body>
            </soapenv:Envelope>
            """ % (exer, email, price, numcli, object, acquirer_reference, saisie, urlnotif, urlredirect)

        response = requests.post(self._get_soap_url(), data=soap_body, headers={'content-type': 'text/xml'})
        root = ElementTree.fromstring(response.content)

        namespaces = self._get_soap_namespaces()
        error_element = root.find('.//ns1:FonctionnelleErreur', namespaces) \
                        or root.find('.//ns1:TechDysfonctionnementErreur', namespaces) \
                        or root.find('.//ns1:TechIndisponibiliteErreur', namespaces) \
                        or root.find('.//ns1:TechProtocolaireErreur', namespaces)

        if error_element is not None:
            code = error_element.find('code').text
            descriptif = error_element.find('descriptif').text
            libelle = error_element.find('libelle').text
            severite = error_element.find('severite').text
            _logger.error(
                "An error occured during idOp negociation with Tipi Regie web service. Informations are: {"
                "code: %s, descriptif: %s, libelle: %s, severite: %s}" % (
                    code, descriptif, libelle, severite))

        idop_element = root.find('.//idOp')
        return idop_element.text if idop_element is not None else ''

    @api.model
    def tipiregie_get_result_from_web_service(self, idOp):
        soap_url = self._get_soap_url()
        soap_body = '<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" ' \
                    'xmlns:pai="http://securite.service.tpa.cp.finances.gouv.fr/services/mas_securite/' \
                    'contrat_paiement_securise/PaiementSecuriseService">'
        soap_body += """
                <soapenv:Header/>
                <soapenv:Body>
                    <pai:recupererDetailPaiementSecurise>
                        <arg0>
                            <idOp>%s</idOp>
                        </arg0>
                    </pai:recupererDetailPaiementSecurise>
                </soapenv:Body>
            </soapenv:Envelope>
            """ % idOp

        soap_response = requests.post(soap_url, data=soap_body, headers={'content-type': 'text/xml'})
        root = ElementTree.fromstring(soap_response.content)
        response = root.find('.//return')

        resultrans = response.find('resultrans').text
        data = {
            'resultrans': resultrans,
            'dattrans': response.find('dattrans').text,
            'heurtrans': response.find('heurtrans').text,
            'exer': response.find('exer').text,
            'idOp': response.find('idOp').text,
            'mel': response.find('mel').text,
            'montant': response.find('montant').text,
            'numcli': response.find('numcli').text,
            'objet': response.find('objet').text,
            'refdet': response.find('refdet').text,
            'saisie': response.find('saisie').text
        }

        if resultrans is None:
            raise ValidationError("No result found for transaction with idOp: %s" % idOp)

        return data

    @api.multi
    def _tipiregie_check_web_service(self):
        self.ensure_one()

        soap_url = self._get_soap_url()
        soap_body = """
                    <soapenv:Envelope %s %s>
                       <soapenv:Header/>
                       <soapenv:Body>
                          <pai:recupererDetailClient>
                             <arg0>
                                <numCli>%s</numCli>
                             </arg0>
                          </pai:recupererDetailClient>
                       </soapenv:Body>
                    </soapenv:Envelope>
                    """ % (
            'xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"',
            'xmlns:pai="http://securite.service.tpa.cp.finances.gouv.fr/services/mas_securite/'
            'contrat_paiement_securise/PaiementSecuriseService"',
            self.tipiregie_customer_number
        )

        try:
            soap_response = requests.post(soap_url, data=soap_body, headers={'content-type': 'text/xml'})
            root = ElementTree.fromstring(soap_response.content)
            fault = root.find('.//S:Fault', {'S': 'http://schemas.xmlsoap.org/soap/envelope/'})

            if fault is not None:
                error = _("It would appear that the customer number entered is not valid or that the Tipi Régie"
                          " contract is not properly configured.")
                error_desc = fault.find('.//descriptif')
                if error_desc is not None:
                    error += _("Tipi server returned the following error: \"%s\"") % error_desc.text
                raise ValidationError(error)
        except ConnectionError as e:
            raise ValidationError(_("It seems that the connection to the web service Tipi Régie is impossible.\n"
                                    "%s\n\n"
                                    "%s") % (
                                      self._get_soap_url(),
                                      e.message
                                  ))

    @api.multi
    def toggle_tipiregie_activation_mode_value(self):
        in_activation = self.filtered(lambda acquirer: acquirer.tipiregie_activation_mode)
        in_activation.write({'tipiregie_activation_mode': False})
        (self - in_activation).write({'tipiregie_activation_mode': True})
