from django.views import View
from django.http import JsonResponse
import datetime
import secrets
import copy
import logging
import redis
import os
import hashlib
import sentry_sdk
import requests
import time
from requests.exceptions import Timeout

from django.conf import settings

r = redis.Redis(db=2) if settings.DEBUG else redis.from_url(os.environ.get("REDIS_URL"))
# r = redis.Redis(db=2)

sentry_sdk.init(
    "https://cfddbb58ba23444bb691c9d588d06a7f@o438046.ingest.sentry.io/5423753",
    traces_sample_rate=1.0
)

error_log = logging.getLogger('error_log')


class BaseView(View):

    @staticmethod
    def authorization(roles):
        def decorator(func):
            def wrapper(*args, **kwargs):
                request = args[1]
                access_token = request.headers.get('Authorization')
                if access_token:
                    result = requests.post(settings.AUTH_SERVICE_BASE_URL + 'users/auth/', json={
                        'access_token': access_token
                    })
                    result = result.json()
                    if result['status'] != 'Success':
                        return result

                    if result['data']['type'] == 'User':
                        if result['data']['role'] in roles:
                            kwargs['client_id'] = str(result['data']['uuid'])
                            kwargs['client'] = 'User'
                            return func(*args, **kwargs)
                        else:
                            return {'status': 'Failed', 'message': 'No access', 'code': 403}

                    elif result['data']['type'] == 'Service':
                        from_service = request.headers.get('From')
                        to_service = request.headers.get('To')
                        if not from_service or not to_service:
                            return {'status': 'Failed', 'message': 'Bad request', 'code': 400}
                        if result['data']['from_service'].decode('UTF-8') != from_service or \
                                result['data']['to_service'].decode('UTF-8') != to_service:
                            return {'status': 'Failed', 'message': 'Bad request', 'code': 400}
                        kwargs['client_id'] = str(result['data']['from_service'])
                        kwargs['client'] = 'Service'
                        return func(*args, **kwargs)
                else:
                    if 'anonymous' in roles:
                        kwargs['client_id'] = 'anonymous'
                        kwargs['client'] = 'anonymous'
                        return func(*args, **kwargs)
                    else:
                        return {'status': 'Failed', 'message': 'No access', 'code': 403}

            return wrapper

        return decorator

    @staticmethod
    def my_authorization(service):
        access_token = r.get(service + '_access')
        refresh_token = r.get(service + '_refresh')

        if access_token:
            return {'status': 'Success', 'access_token': access_token.decode('UTF-8')}

        elif refresh_token:
            response = requests.post(settings.AUTH_SERVICE_BASE_URL + 'services/auth/', json={'refresh_token': refresh_token.decode('UTF-8')})
            data = response.json()
            r.setex(service + '_access', datetime.datetime.strptime(data['data']['access_token_valid_until'],
                                                                    '%d/%m/%y %H:%M:%S'), data['data']['access_token'])
            r.setex(service + '_refresh', datetime.datetime.strptime(data['data']['refresh_token_valid_until'],
                                                                     '%d/%m/%y %H:%M:%S'), data['data']['refresh_token'])

            return {'status': 'Success', 'access_token': data['data']['access_token']}

        else:
            response = requests.post(settings.AUTH_SERVICE_BASE_URL + 'services/auth/', json={
                'service_id': settings.SERVICE_ID,
                'service_secret': settings.SERVICE_SECRET,
                'service': service
            })
            data = response.json()

            end = datetime.datetime.strptime(data['data']['access_token_valid_until'], '%d/%m/%y %H:%M:%S')
            now = datetime.datetime.now()
            now_ts = time.mktime(now.timetuple())
            end_ts = time.mktime(end.timetuple())
            ttl = int(end_ts-now_ts) / 60

            r.setex(service + '_access', datetime.timedelta(minutes=ttl), data['data']['access_token'])

            r.setex(service + '_refresh', datetime.timedelta(minutes=ttl), data['data']['refresh_token'])

            return {'status': 'Success', 'access_token': data['data']['access_token']}


    def dispatch(self, request, *args, **kwargs):

        try:
            response = super().dispatch(request, *args, **kwargs)
        except Exception as e:
            sentry_sdk.capture_exception(error=e)
            BaseView.error_log(error_log, e, request)
            return JsonResponse({'status': 'Failed', 'message': 'Server error'}, status=500)

        if isinstance(response, (dict, list)):
            status = response.pop('code')
            return JsonResponse(response, safe=False, status=status)
        else:
            return response

    @staticmethod
    def log(logger, request, client, client_id):
        log_message = 'Method: {} - URL: {} - Client: {} - Client ID: {} - Params: {} - Headers: {} -  Data: {}'
        logger.info(log_message.format(request.method, request.build_absolute_uri(), client,
                                       client_id, request.GET, request.headers, request.body.decode('utf-8')
                                       ))

    @staticmethod
    def error_log(logger, error, request):
        log_message = 'ERROR: {} - Method: {} - URL: {} - Params: {} - Headers: {} -  Data: {}'
        logger.info(log_message.format(error, request.method, request.build_absolute_uri(),
                                       request.GET, request.headers, request.body.decode('utf-8')
                                       ))
    @staticmethod
    def send_stat_log(request, client, client_id, url=settings.STATISTIC_SERVICE_BASE_URL):
        data = {
            'time': str(datetime.datetime.now()),
            'method': request.method,
            'url': request.build_absolute_uri(),
            'client': str(client),
            'client_id': str(client_id),
            'params': request.GET,
            'headers': str(request.headers),
            'data': request.body.decode('utf-8'),
        }

        headers = {'Service': 'Clubs'}

        try:
            response = requests.post(url + 'statistics/dancers/logs/', json=data, timeout=3, headers=headers)
            if response.status_code != 200:
                return False
            return True
        except Timeout:
            return False
