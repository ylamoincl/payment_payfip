from odoo.addons.payment import reset_payment_provider, setup_provider


def post_init_hook(env):
    setup_provider(env, 'payfip')


def uninstall_hook(env):
    reset_payment_provider(env, 'payfip')
