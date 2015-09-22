from __future__ import absolute_import, print_function

from django import forms
from sentry.auth.view import AuthView, ConfigureView

from .client import GitHubClient
from .constants import ERR_NO_ORG_ACCESS
from .constants import REQUIRE_VERIFIED_EMAIL
from .constants import (
    ERR_NO_SINGLE_VERIFIED_PRIMARY_EMAIL, ERR_NO_SINGLE_PRIMARY_EMAIL,
    ERR_NO_VERIFIED_PRIMARY_EMAIL, ERR_NO_PRIMARY_EMAIL,
)


class FetchUser(AuthView):
    def __init__(self, client_id, client_secret, org=None, *args, **kwargs):
        self.org = org
        self.client = GitHubClient(client_id, client_secret)
        super(FetchUser, self).__init__(*args, **kwargs)

    def handle(self, request, helper):
        access_token = helper.fetch_state('data')['access_token']

        if self.org is not None:
            if not self.client.is_org_member(access_token, self.org['id']):
                return helper.error(ERR_NO_ORG_ACCESS)

        user = self.client.get_user(access_token)

        if not user.get('email'):
            emails = self.client.get_user_emails(access_token)
            email = [e['email'] for e in emails if ((not REQUIRE_VERIFIED_EMAIL) | e['verified']) and e['primary']]
            if len(email) == 0:
                if REQUIRE_VERIFIED_EMAIL:
                    msg = ERR_NO_VERIFIED_PRIMARY_EMAIL
                else:
                    msg = ERR_NO_PRIMARY_EMAIL
                return helper.error(msg)
            elif len(email) > 1:
                if REQUIRE_VERIFIED_EMAIL:
                    msg = ERR_NO_SINGLE_VERIFIED_PRIMARY_EMAIL
                else:
                    msg = ERR_NO_SINGLE_PRIMARY_EMAIL
                return helper.error(msg)
            else:
                user['email'] = email[0]

        helper.bind_state('user', user)

        return helper.next_step()


class SelectOrganizationForm(forms.Form):
    org = forms.ChoiceField(label='Organization')

    def __init__(self, org_list, *args, **kwargs):
        super(SelectOrganizationForm, self).__init__(*args, **kwargs)

        self.fields['org'].choices = [
            (o['id'], o['login']) for o in org_list
        ]
        self.fields['org'].widget.choices = self.fields['org'].choices


class SelectOrganization(AuthView):
    def __init__(self, client_id, client_secret, *args, **kwargs):
        self.client = GitHubClient(client_id, client_secret)
        super(SelectOrganization, self).__init__(*args, **kwargs)

    def handle(self, request, helper):
        access_token = helper.fetch_state('data')['access_token']
        org_list = self.client.get_org_list(access_token)

        form = SelectOrganizationForm(org_list, request.POST or None)
        if form.is_valid():
            org_id = form.cleaned_data['org']
            org = [o for o in org_list if org_id == str(o['id'])][0]
            helper.bind_state('org', org)
            return helper.next_step()

        return self.respond('sentry_auth_github/select-organization.html', {
            'form': form,
            'org_list': org_list,
        })


class GitHubConfigureView(ConfigureView):
    def dispatch(self, request, organization, auth_provider):
        return self.render('sentry_auth_github/configure.html')
