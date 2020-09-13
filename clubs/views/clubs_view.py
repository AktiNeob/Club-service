import logging
from .base_view import BaseView
from ..models import Clubs
import json
import requests
from django.conf import settings

log = logging.getLogger('clubs_log')


class ClubsView(BaseView):

    @BaseView.authorization(('admin', 'anonymous'))
    def get(self, request, client, client_id):
        params = request.GET
        response = list(Clubs.objects.filter(**params).values())
        # stat = BaseView.send_stat_log(request, client, client_id)
        # if not stat:
        BaseView.log(log, request, client, client_id)
        return {'status': 'Success', 'data': response, 'code': 200}

    @BaseView.authorization(('admin', 'anonymous'))
    def post(self, request, client, client_id):
        data = json.loads(request.body.decode('utf-8'))
        response = Clubs.objects.create(**data).pk
        # stat = BaseView.send_stat_log(request, client, client_id)
        # if not stat:
        BaseView.log(log, request, client, client_id)
        return {'status': 'Success', 'data': response, 'code': 200}

class ClubView(BaseView):

    def dancers_get(self, club, token):
        try:
            rqst = requests.get(settings.DANCERS_SERVICE_BASE_URL + 'dancers/sportsmans/?club={}'.format(
                club),  timeout=3,  headers={'Authorization': token,
                                             'From': settings.SERVICE_ID,
                                             'To': 'Dancers'})
        except Timeout:
            return 400
        return rqst.json()
    
    def dancer_patch(self, uuid, token):
        try:
            rqst = requests.patch(settings.DANCERS_SERVICE_BASE_URL + 'dancers/sportsman/{}/'.format(
                uuid), json={'club': None}, timeout=3,  headers={'Authorization': token,
                                                                'From': settings.SERVICE_ID,
                                                                'To': 'Dancers'})
        except Timeout:
            return 400
        return rqst.status_code

    
    @BaseView.authorization(('admin', 'anonymous'))
    def get(self, request, uuid, client, client_id):
        response = list(Clubs.objects.filter(pk=uuid).values())
        if not response:
            return {'status': 'Failed', 'message': 'Object does not exist', 'code': 404}
        # stat = BaseView.send_stat_log(request, client, client_id)
        # if not stat:
        BaseView.log(log, request, client, client_id)
        return {'status': 'Success', 'data': response, 'code': 200}

    @BaseView.authorization(('admin', 'anonymous'))
    def patch(self, request, uuid, client, client_id):
        data = json.loads(request.body.decode('utf-8'))
        Clubs.objects.filter(pk=uuid).update(**data)
        response = list(Clubs.objects.filter(pk=uuid).values())
        # stat = BaseView.send_stat_log(request, client, client_id)
        # if not stat:
        BaseView.log(log, request, client, client_id)
        return {'status': 'Success', 'data': response, 'code': 200}

    @BaseView.authorization(('admin', 'anonymous'))
    def delete(self, request, uuid, client, client_id):

        auth = self.my_authorization('Dancers')
        response = self.dancers_get(str(uuid), auth['access_token'])
        if response == 400:
            return {'status': 'Failed', 'message': 'Service Error', 'code': 500}
        print(response)
        for dancer in response['data']:
            resp = self.dancer_patch(dancer['uuid'], auth['access_token'])
            if resp != 200:
                return {'status': 'Failed', 'message': 'Service Error', 'code': 500}

        entry = Clubs.objects.filter(pk=uuid)
        entry.delete()
        # stat = BaseView.send_stat_log(request, client, client_id)
        # if not stat:
        BaseView.log(log, request, client, client_id)
        return {'status': 'Success', 'code': 200}