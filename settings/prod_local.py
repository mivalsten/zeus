from .prod import *  # noqa

ADMIN_NAME = 'PKW Razem'
ADMIN_EMAIL = 'razem.pkw@gmail.com'

ADMINS = [
    ('Grzegorz Kawka-Osik', 'mivalsten@gmail.com'),
]
ELECTION_ADMINS = ADMINS
MANAGERS = ADMINS

DEFAULT_FROM_EMAIL = 'mivalsten@gmail.com'
SERVER_EMAIL = '%s <%s>' % (DEFAULT_FROM_NAME, DEFAULT_FROM_EMAIL)

HELP_EMAIL_ADDRESS = 'mivalsten@gmail.com'
