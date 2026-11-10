from channels.middleware import BaseMiddleware
from channels.db import database_sync_to_async
from django.contrib.auth.models import AnonymousUser
from urllib.parse import parse_qs
from drl_app.models import User

@database_sync_to_async
def get_user_from_token(token):
    if not token or not token.startswith('mock-token-for-'):
        return AnonymousUser()
    username = token.replace('mock-token-for-', '')
    try:
        return User.objects.get(username=username)
    except User.DoesNotExist:
        return AnonymousUser()

class WebSocketJWTAuthMiddleware(BaseMiddleware):
    async def __call__(self, scope, receive, send):
        query_string = scope.get('query_string', b'').decode('utf-8')
        query_params = parse_qs(query_string)
        token = query_params.get('token', [None])[0]
        
        scope['user'] = await get_user_from_token(token)
        return await super().__call__(scope, receive, send)
