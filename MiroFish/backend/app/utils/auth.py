import functools
from flask import request, jsonify

def require_auth(f):
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        from ..config import Config

        # Check X-API-Key header
        api_key = request.headers.get('X-API-Key')
        if api_key and api_key == Config.API_KEY:
            return f(*args, **kwargs)

        # Check Authorization header (Bearer token)
        auth_header = request.headers.get('Authorization')
        if auth_header and auth_header.startswith('Bearer '):
            token = auth_header.split(' ')[1]
            if token == Config.API_KEY:
                return f(*args, **kwargs)

        return jsonify({
            "success": False,
            "error": "未提供有效的API Key或权限不足 (Unauthorized)"
        }), 401

    return decorated
