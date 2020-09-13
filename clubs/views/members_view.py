import logging
from .base_view import BaseView
from ..models import Clubs, Members
import json
from django.conf import settings
import requests
from requests.exceptions import Timeout

log = logging.getLogger('members_log')

class BaseMembersView(BaseView):

    def dancer_club_update(self, dancer_uuid, data, token):
        try:
            rqst = requests.patch(settings.DANCERS_SERVICE_BASE_URL + 'dancers/sportsman/{}/'.format(
                dancer_uuid), json={'club': data}, timeout=3,  headers={'Authorization': token,
                                                                        'From': settings.SERVICE_ID,
                                                                        'To': 'Dancers'})
        except Timeout:
            return 400
        print(rqst.text)
        return rqst.status_code
    
    
    def dancer_get(self, uuid, token):
        try:
            rqst = requests.get(settings.DANCERS_SERVICE_BASE_URL + 'dancers/sportsman/{}/'.format(
                uuid),  timeout=3,  headers={'Authorization': token,
                                             'From': settings.SERVICE_ID,
                                             'To': 'Dancers'})
                                            
        except Timeout:
            return 400
      
        if rqst.json()['data'][0]['club']:
            return 400

        return rqst.status_code


class MembersView(BaseMembersView):

    @BaseView.authorization(('admin', 'anonymous'))
    def get(self, request, club_uuid, client, client_id):
        params = dict(request.GET)
        params['club'] = str(club_uuid)
        response = list(Members.objects.filter(**params).values())
        if not response:
            return {'status': 'Failed', 'message': 'Not found', 'code': 404}
        # stat = BaseView.send_stat_log(request, client, client_id)
        # if not stat:
        BaseView.log(log, request, client, client_id)
        return {'status': 'Success', 'data': response, 'code': 200}


    @BaseView.authorization(('admin', 'anonymous'))
    def post(self, request, club_uuid, client, client_id):
        data = json.loads(request.body.decode('utf-8'))
        club = Clubs.objects.filter(pk=club_uuid)
        auth = BaseView.my_authorization('Dancers')

        if not club:
            return {'status': 'Failed', 'message': 'Not found', 'code': 404}

        # Если танцор уже в клубе, то добавить его нельзя
        if self.dancer_get(data['dancer_uuid'], auth['access_token']) != 200:
            return {'status': 'Failed', 'message': 'User is already a member of the club', 'code': 400}

        
        data['club'] = club[0]
        member = Members.objects.create(**data)
        response = member.pk

        # При добавлении танцора в клуб, клуб должен измениться в карточке танцора
        if self.dancer_club_update(data['dancer_uuid'], str(club_uuid), auth['access_token']) != 200:
            # откат записи в бд, если сервис недоступен
            member.delete()
            return {'status': 'Failed', 'message': 'Service error', 'code': 500}

        # stat = BaseView.send_stat_log(request, client, client_id)
        # if not stat:
        BaseView.log(log, request, client, client_id)
        return {'status': 'Success', 'data': response, 'code': 200}

class MemberView(BaseMembersView):

    @BaseView.authorization(('admin', 'anonymous'))
    def get(self, request, uuid, client, client_id):
        response = list(Members.objects.filter(pk=uuid).values())
        if not response:
            return {'status': 'Failed', 'message': 'Object does not exist', 'code': 404}
        # stat = BaseView.send_stat_log(request, client, client_id)
        # if not stat:
        BaseView.log(log, request, client, client_id)
        return {'status': 'Success', 'data': response, 'code': 200}


    @BaseView.authorization(('admin', 'anonymous'))
    def delete(self, request, uuid, client, client_id):
        entry = Members.objects.filter(pk=uuid)

        if not entry:
            return {'status': 'Failed', 'message': 'Not found', 'code': 404}
        # При удалении танцора из клуба, клуб должен быть удален в карточке танцора
        auth = BaseView.my_authorization('Dancers')
        if self.dancer_club_update(str(entry[0].dancer_uuid), None, auth['access_token']) != 200:
            # запрет на удалении если серви  недоступен
            return {'status': 'Failed', 'message': 'Service error', 'code': 500}

        entry.delete()
        # stat = BaseView.send_stat_log(request, client, client_id)
        # if not stat:
        BaseView.log(log, request, client, client_id)
        return {'status': 'Success', 'code': 200}