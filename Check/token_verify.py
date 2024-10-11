from datetime import datetime, timedelta
from functools import wraps

import jwt
from flask import jsonify, request

SECRET_KEY = 'yy401'  # JWT 密钥

def generate_token(user_id, user_name):
    """
    生成 JWT token
    """
    payload = {
        'user_id': user_id,
        'user_name': user_name,
        'exp': datetime.utcnow() + timedelta(hours=2),  # 2 小时后过期
        'iat': datetime.utcnow()  # 签发时间
    }
    token = jwt.encode(payload, SECRET_KEY, algorithm='HS256')
    print("生成的token:" + str(token))
    return token

def token_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        token = None

        # 从请求头获取token
        if 'Authorization' in request.headers:
            print("Authorization:" + request.headers['Authorization'])
            parts = request.headers['Authorization'].split()
            print("parts:" + str(parts))
            if len(parts) == 2 and parts[0].lower() == 'bearer':
                token = parts[1]
                print("token:" + token)
            else:
                print("Authorization header 格式不正确")
                return jsonify({"error": "Authorization header must be in the format 'Bearer <token>'"}), 403

        if not token:
            print("Token缺失")
            return jsonify({"error": "Token缺失，无法访问"}), 403

        try:
            # 尝试解码JWT
            data = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
            print("Decoded token data: " + str(data))  # 打印解码后的JWT数据
            current_user = data.get('user_id')
            print("current_user:" + str(current_user))
            print("user_id:" + str(data.get('user_id')))
            if not current_user:
                print("Token中缺少user_id")
                return jsonify({"error": "Token中缺少user_id"}), 403
        except jwt.ExpiredSignatureError:
            print("Token已过期")
            return jsonify({"error": "Token已过期"}), 403
        except jwt.InvalidTokenError as e:
            print(f"无效的Token: {e}")
            return jsonify({"error": "无效的Token"}), 403
        except Exception as e:
            print(f"JWT解码过程中发生其他错误: {e}")
            return jsonify({"error": "Token解码错误"}), 500

        # 确保成功进入视图函数
        print(type(current_user))
        print(f"成功解码用户ID: {current_user}")
        return f(current_user)

    return decorated_function