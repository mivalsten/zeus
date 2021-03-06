
import re

from base64 import b64decode

from functools import wraps

from django.core.exceptions import PermissionDenied
from django.urls import reverse
from django.shortcuts import get_object_or_404
from django.conf import settings

from helios.models import Election, Poll, Trustee, Voter
from heliosauth.models import User

from zeus.log import _locals

import logging
logger = logging.getLogger(__name__)


AUTH_RE = re.compile(r'Basic (\w+[=]*)')


def get_ip(request):
    ip = request.META.get('HTTP_X_FORWARDER_FOR', None)
    if not ip:
        ip = request.META.get('REMOTE_ADDR')
    return ip


def class_method(func):
    def wrapper(self, request, *args, **kwargs):
        return func(request, *args, **kwargs)

    return wrapper


def trustee_view(func):
    @wraps(func)
    @election_view()
    def wrapper(request, election, *args, **kwargs):
        if not request.zeususer.is_trustee:
            raise PermissionDenied("Only election trustees can access this"
                                   "view")
        kwargs['trustee'] = request.trustee
        kwargs['election'] = election
        return func(request, *args, **kwargs)
    return wrapper


def election_view(check_access=True):
    def wrapper(func):
        @wraps(func)
        def inner(request, *args, **kwargs):
            allow_manager = getattr(func, '_allow_manager', False)
            _check_access = check_access
            user = request.zeususer
            if user.is_authenticated():
                try:
                    _locals.user_id = user.user_id
                except Exception:
                    raise PermissionDenied("Election cannot be accessed by you")
            _locals.ip = get_ip(request)

            if allow_manager and user.is_manager:
                _check_access = False

            if 'election_uuid' in kwargs:
                uuid = kwargs.pop('election_uuid')
                election = get_object_or_404(Election, uuid=uuid)
                if not user.can_access_election(election) and _check_access:
                    raise PermissionDenied("Election cannot be accessed by you")
                kwargs['election'] = election

            if 'poll_uuid' in kwargs:
                uuid = kwargs.pop('poll_uuid')
                poll = get_object_or_404(Poll, uuid=uuid)
                if not user.can_access_poll(poll) and _check_access:
                    raise PermissionDenied("Poll cannot be accessed by you")
                kwargs['poll'] = poll

            return func(request, *args, **kwargs)
        return inner
    return wrapper


def poll_voter_required(func):
    @election_view()
    @wraps(func)
    def wrapper(request, *args, **kwargs):
        if not request.zeususer.is_voter:
            raise PermissionDenied("Authenticated user required")
        return func(request, *args, **kwargs)
    return wrapper


def user_required(func):
    @wraps(func)
    def wrapper(request, *args, **kwargs):
        if not request.zeususer or not request.zeususer.is_authenticated():
            raise PermissionDenied("Authenticated user required")
        return func(request, *args, **kwargs)
    return wrapper


def superadmin_required(func):
    @user_required
    @wraps(func)
    def wrapper(request, *args, **kwargs):
        if not request.zeususer._user.superadmin_p:
            raise PermissionDenied("Superadmin user required")
        return func(request, *args, **kwargs)
    return wrapper


def manager_or_superadmin_required(func):
    @user_required
    @wraps(func)
    def wrapper(request, *args, **kwargs):
        if not (request.zeususer.is_superadmin
                or request.zeususer.is_manager):
            raise PermissionDenied("Superadmin or manager required")
        return func(request, *args, **kwargs)
    return wrapper


def election_poll_required(func):
    @election_view(check_access=True)
    @wraps(func)
    def wrapper(request, *args, **kwargs):
        if not request.zeususer.is_voter:
            raise PermissionDenied("Authenticated user required")
        return func(request, *args, **kwargs)
    return wrapper


def election_user_required(func):
    @wraps(func)
    @election_view()
    @user_required
    def wrapper(request, *args, **kwargs):
        return func(request, *args, **kwargs)
    return wrapper


def election_admin_required(func):
    @election_view()
    @user_required
    @wraps(func)
    def wrapper(request, *args, **kwargs):
        user = request.zeususer
        if not user.is_admin:
            raise PermissionDenied("Elections administrator required")
        return func(request, *args, **kwargs)

    return wrapper


def unauthenticated_user_required(func):
    from zeus.views.site import error as error_view

    @wraps(func)
    def wrapper(request, *args, **kwargs):
        if request.zeususer.is_authenticated():
            return error_view(request, 403, "Please logout to access this view")
        return func(request, *args, **kwargs)
    return wrapper


def requires_election_features(*features):
    def wrapper(func):
        @wraps(func)
        def inner(*args, **kwargs):
            election = kwargs.get('election')
            if not election.check_features(*features):
                status = election.check_features_verbose(*features)
                msg = ("Unmet election %s required "
                      "features %r") % (election.uuid, status)
                logger.error(msg)
                raise PermissionDenied(msg)
            return func(*args, **kwargs)
        return inner
    return wrapper


def requires_poll_features(*features):
    def wrapper(func):
        @wraps(func)
        def inner(*args, **kwargs):
            poll = kwargs.get('poll')
            if not poll.check_features(*features):
                status = poll.check_features_verbose(*features)
                msg = ("Unmet poll %s required "
                       "features %r") % (poll.uuid, status)
                logger.error(msg)
                raise PermissionDenied(msg)
            return func(*args, **kwargs)
        return inner
    return wrapper


TRUSTEE_SESSION_KEY = 'zeus_trustee_uuid'
USER_SESSION_KEY = 'user'
VOTER_SESSION_KEY = 'CURRENT_VOTER'


class ZeusUser(object):

    is_user = False
    is_trustee = False
    is_voter = False
    is_admin = False
    is_manager = False
    is_superadmin = False

    @classmethod
    def from_request(self, request):
        users = get_users_from_request(request)
        for user in users:
            if user:
                return ZeusUser(user)
        return ZeusUser(None)

    def __init__(self, user_obj):
        self._user = user_obj
        if isinstance(self._user, User):
            self.is_user = True
            if self._user.superadmin_p:
                self.is_superadmin = True
            if self._user.management_p or self._user.superadmin_p:
                self.is_manager = True
            if self._user.admin_p or self._user.superadmin_p:
                self.is_admin = True
                self.institution = self._user.institution
                return
            return

        if isinstance(self._user, Trustee):
            self.is_trustee = True

        if isinstance(self._user, Voter):
            if not self._user.excluded_at:
                self.is_voter = True

    @property
    def user_id(self):
        if self.is_admin:
            return "ADMIN:%s" % self._user.user_id
        if self.is_trustee:
            return "TRUSTEE:%s" % self._user.email
        if self.is_voter:
            prefix = "VOTER"
            voter = self._user
            if voter.excluded_at:
                prefix = "EXCLUDED_VOTER"
            return "%s:%s" % (prefix, voter.voter_login_id)
        raise Exception("Unknown user")

    def is_authenticated(self):
        return bool(self._user)

    def is_anonymous(self):
        return not bool(self._user)

    def authenticate(self, request):
        session = request.session

        if self.is_trustee:
            key = TRUSTEE_SESSION_KEY
            expiry = settings.TRUSTEE_SESSION_AGE
        if self.is_admin:
            key = USER_SESSION_KEY
            expiry = settings.USER_SESSION_AGE
        if self.is_voter:
            key = VOTER_SESSION_KEY
            expiry = settings.VOTER_SESSION_AGE

        self._clear_session(request)
        session[key] = self._user.pk
        session.set_expiry(expiry)

    def logout(self, request):
        self._clear_session(request)
        self._user = None
        self.is_voter = False
        self.is_admin = False
        self.is_trustee = False
        self.is_manager = False
        self.is_superadmin = False

    def _clear_session(self, request):
        for sess_key in [TRUSTEE_SESSION_KEY, USER_SESSION_KEY,
                         VOTER_SESSION_KEY]:
            if sess_key in request.session:
                del request.session[sess_key]

    def can_access_poll(self, poll):
        if self.is_voter:
            return self._user.poll.uuid == poll.uuid
        if self.is_admin:
            if self._user.superadmin_p:
                return True
            return self._user.elections.filter(polls__in=[poll]).count() > 0
        if self.is_trustee:
            return self._user.election.polls.filter(
                pk__in=[poll.pk]).count() > 0
        return False

    def can_access_election(self, election):
        if self.is_voter:
            return self._user.poll.election.uuid == election.uuid
        if self.is_trustee:
            return self._user.election == election
        if self.is_admin:
            if self._user.superadmin_p:
                return True
            return self._user.elections.filter(
                pk__in=[election.pk]).count() > 0
        return False


def get_users_from_request(request):
    session = getattr(request, 'session', {})
    user, admin, trustee, voter = None, None, None, None

    # identify user and admin
    if USER_SESSION_KEY in session:
        user = request.session[USER_SESSION_KEY]
        try:
            user = User.objects.get(pk=user)
            if user.admin_p or user.superadmin_p:
                admin = user
        except User.DoesNotExist:
            pass

    # idenitfy voter
    if VOTER_SESSION_KEY in session:
        voter = request.session[VOTER_SESSION_KEY]

        try:
            voter = Voter.objects.get(pk=voter)
        except Voter.DoesNotExist:
            voter = None

        if not voter or voter.excluded_at:
            del request.session[VOTER_SESSION_KEY]
            #TODO: move this in middleware ??? raise PermissionDenied

    # idenitfy trustee
    if session.get(TRUSTEE_SESSION_KEY, None):
        try:
            trustee_pk = session.get(TRUSTEE_SESSION_KEY, None)
            if trustee_pk:
                trustee = Trustee.objects.get(pk=int(trustee_pk))
        except Trustee.DoesNotExist:
            pass

    # identify trustee http basic authentication
    api_auth_header = request.META.get('HTTP_AUTHORIZATION', None)
    if api_auth_header:
        #TODO: allow other type of users to login this way ???
        try:
            auth = AUTH_RE.findall(api_auth_header)
            election, username, password = b64decode(auth[0]).split(":")
        except Exception:
            raise PermissionDenied

        try:
            auth_trustee = Trustee.objects.get(email=username,
                                               election__uuid=election)
        except Trustee.DoesNotExist:
            raise PermissionDenied

        if auth_trustee.secret == password:
            trustee = auth_trustee
            setattr(request, '_dont_enforce_csrf_checks', True)
        else:
            raise PermissionDenied

    if user and not admin:
        del session[USER_SESSION_KEY]
        user = None
        admin = None

    # cleanup duplicate logins
    if len([x for x in [voter, trustee, admin] if bool(x)]) > 1:
        if voter:
            if trustee:
                del session[TRUSTEE_SESSION_KEY]
            if admin:
                del session[USER_SESSION_KEY]
        if trustee:
            if admin:
                del session[USER_SESSION_KEY]

    return voter, trustee, admin


def allow_manager_access(func):
    func._allow_manager = True
    func.__globals__['foo'] = 'bar'
    return func


def make_shibboleth_login_url(endpoint):
    shibboleth_login = reverse('shibboleth_login', kwargs={'endpoint': endpoint})
    url = '/'.join(s.strip('/') for s in filter(bool, [
        shibboleth_login]))
    return '/%s' % url
