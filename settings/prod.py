
from .base import *  # noqa

import json

with open('/srv/zeus/config/secrets.json') as f:
    SECRETS = json.load(f)

DEBUG = False

LANGUAGE_CODE = 'pl'
LANGUAGES = [('pl', _('Polish')), ('en', _('English'))]

# TODO make this a per-server secret
HELIOS_CRYPTOSYSTEM_PARAMS = {}
HELIOS_CRYPTOSYSTEM_PARAMS['p'] = 19936216778566278769000253703181821530777724513886984297472278095277636456087690955868900309738872419217596317525891498128424073395840060513894962337598264322558055230566786268714502738012916669517912719860309819086261817093999047426105645828097562635912023767088410684153615689914052935698627462693772783508681806906452733153116119222181911280990397752728529137894709311659730447623090500459340155653968608895572426146788021409657502780399150625362771073012861137005134355305397837208305921803153308069591184864176876279550962831273252563865904505239163777934648725590326075580394712644972925907314817076990800469107
HELIOS_CRYPTOSYSTEM_PARAMS['q'] = 9968108389283139384500126851590910765388862256943492148736139047638818228043845477934450154869436209608798158762945749064212036697920030256947481168799132161279027615283393134357251369006458334758956359930154909543130908546999523713052822914048781317956011883544205342076807844957026467849313731346886391754340903453226366576558059611090955640495198876364264568947354655829865223811545250229670077826984304447786213073394010704828751390199575312681385536506430568502567177652698918604152960901576654034795592432088438139775481415636626281932952252619581888967324362795163037790197356322486462953657408538495400234553
HELIOS_CRYPTOSYSTEM_PARAMS['g'] = 19167066187022047436478413372880824313438678797887170030948364708695623454002582820938932961803261022277829853214287063757589819807116677650566996585535208649540448432196806454948132946013329765141883558367653598679571199251774119976449205171262636938096065535299103638890429717713646407483320109071252653916730386204380996827449178389044942428078669947938163252615751345293014449317883432900504074626873215717661648356281447274508124643639202368368971023489627632546277201661921395442643626191532112873763159722062406562807440086883536046720111922074921528340803081581395273135050422967787911879683841394288935013751

SECRET_KEY = SECRETS['secret_key']

CELERY_TASK_ALWAYS_EAGER = False

if 'EMAIL_HOST' in SECRETS:
    EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
    EMAIL_HOST = SECRETS['EMAIL_HOST']
    EMAIL_PORT = SECRETS['EMAIL_PORT']
    EMAIL_HOST_USER = SECRETS['EMAIL_HOST_USER']
    EMAIL_HOST_PASSWORD = SECRETS['EMAIL_HOST_PASSWORD']
    EMAIL_USE_TLS = SECRETS['EMAIL_USE_TLS']
    EMAIL_USE_SSL = SECRETS['EMAIL_USE_SSL']
else:
    EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
