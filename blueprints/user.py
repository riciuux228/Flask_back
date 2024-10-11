import logging
import os
import uuid
from datetime import datetime
from flask import Blueprint, jsonify, request, Flask
from werkzeug.utils import secure_filename

from Check.file_verify import allowed_file, save_file
from Check.token_verify import token_required, generate_token
from SqlManage.connect_mysql import MysqlPool

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    filename='user.py.log',
    filemode='w',
    encoding='utf-8'
)
logger = logging.getLogger(__name__)



# 配置文件上传的路径和允许的文件格式
UPLOAD_FOLDER = 'static/user_icons'  # 头像保存路径
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}  # 允许的文件格式
app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# 定义用户蓝图
user_blueprint = Blueprint('user', __name__, template_folder='templates')

mysql_pool = MysqlPool()  # 初始化连接池

@user_blueprint.route('/check_permissions/<int:user_id>', methods=['GET'])
@token_required
def check_Permissions(user_id):
    """
    检查用户权限
    """
    query = 'SELECT role FROM users WHERE id = %s'
    result = mysql_pool.fetch(query, (user_id,), one=True)
    print("用户权限：:" + str(result))
    if result:
        return jsonify({"result": result['role']}), 200
    return jsonify({"error": "没有找到用户"}), 403

@user_blueprint.route('/register', methods=['POST'])
def register():
    """
    用户注册，并支持头像上传
    :return:
    """
    username = request.form.get('username')
    phone = request.form.get('phone')
    password = request.form.get('password')  # 这个密码是前端加密后的密码
    role = request.form.get('role')

    # 检查必填参数
    if not all([username, phone, password, role]):
        return jsonify({"error": "参数不完整"}), 400

    # 检查手机号是否已经存在
    query = 'SELECT * FROM users WHERE phone = %s'
    result = mysql_pool.fetch(query, (phone,), one=True)
    if result:
        return jsonify({"error": "手机号已存在"}), 400

    # 处理头像上传
    avatar = request.files.get('avatar')
    avatar_url = None

    if avatar:
        avatar_path, error = save_file(avatar, app.config['UPLOAD_FOLDER'])
        if error:
            return jsonify({"error": error}), 400  # 文件保存失败，返回错误信息
        avatar_url = f"http://localhost:8080/{avatar_path}"  # 成功保存后，返回URL路径
        if avatar_url is None:
            avatar_url = "http://localhost:8080/static/user_icons/default.png"

    created_at = updated_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    # 插入用户信息到数据库，包括头像的 URL
    insert_query = '''
        INSERT INTO users (username, phone, password, role, created_at, updated_at, is_phone_verified, user_icon_url) 
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
    '''
    try:
        mysql_pool.execute(insert_query,
                           (username, phone, password, role, created_at, updated_at, True, avatar_url))
        return jsonify({"result": "success"}), 200
    except Exception as e:
        logger.error(f"注册失败: {e}")
        return jsonify({"error": "注册失败"}), 500

@user_blueprint.route('/send_code', methods=['POST'])
def send_code():
    """
    发送验证码一个随机的六位数验证码
    """
    data = request.get_json()
    phone = data.get('phone')
    if not phone:
        return jsonify({"error": "参数不完整"}), 400
    random_code = '123456'  # 模拟发送验证码
    return jsonify({"random_code": random_code}, 200)

@user_blueprint.route('/login', methods=['POST'])
def login():
    """
    用户登录
    :return:
    """
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')  # 这个密码已经在前端加密过

    if not all([username, password]):
        return jsonify({"error": "参数不完整"}), 400

    # 直接查询数据库中的加密后的密码
    query = 'SELECT * FROM users WHERE username = %s AND password = %s'
    result = mysql_pool.fetch(query, (username, password), one=True)

    if not result:
        return jsonify({"error": "用户名或密码错误"}), 400

    # 生成JWT token
    token = generate_token(result['id'], result['username'])

    # 登录成功，返回 token 给前端
    return jsonify({
        "result": "success",
        "username": result['username'],
        "id": result['id'],
        "token": token
    }), 200

@user_blueprint.route('/user_info/<int:user_id>', methods=['GET'])
@token_required
def user_info(current_user):
    print("进入 get_user_info 函数")
    """
    获取用户信息（需要登录）
    :param current_user: JWT解码出的用户ID
    :return:
    """
    try:
        # 添加调试信息
        print(f"正在查询用户ID: {current_user}")
        query = 'SELECT username, phone, role, created_at, user_icon_url FROM users WHERE id = %s'
        result = mysql_pool.fetch(query, (current_user,), one=True)

        if not result:
            print("未找到用户")
            return jsonify({"error": "用户不存在"}), 404

        print(f"查询结果: {result}")
        return jsonify(result), 200

    except Exception as e:
        # 捕获并打印任何数据库查询的异常
        print(f"数据库查询出错: {e}")
        return jsonify({"error": "服务器内部错误"}), 500

"""
    根据作者id获取该作者的所有文章
"""
@user_blueprint.route('/get_author_articles/<int:auth_id>', methods=['GET'])
@token_required
def get_author_articles(auth_id):
    query = """
    SELECT 
    a.aid, 
    a.title, 
    a.author, 
    a.content, 
    a.keywords, 
    a.description, 
    a.is_show, 
    a.is_delete, 
    a.is_top, 
    a.is_original, 
    a.click, 
    a.addtime, 
    a.cid, 
    a.image_url, 
    a.comment_count, 
    a.update_time, 
    a.auth_id, 
    c.category_name 
FROM 
    users u 
JOIN 
    yesapi_bjy_article a ON u.id = a.auth_id 
JOIN 
    yesapi_bjy_article_category c ON a.cid = c.cid 
WHERE 
        u.id = %s AND
        a.is_show = 1 AND 
        a.is_delete = 0
    """
    try:
        result = mysql_pool.fetch(query, (auth_id,))
        return jsonify(result)
    except Exception as e:
        logger.error(f"获取作者 {auth_id} 的文章失败: {e}")
        return jsonify({"error": "获取文章失败"}), 500


@user_blueprint.route('/update_profile', methods=['POST'])
@token_required
def update_profile(current_user):
    """
    更新用户信息
    :param current_user: JWT解码出的用户ID
    :return:
    """
    username = request.form.get('username')
    password = request.form.get('password')
    image = request.files.get('user_icon')  # 使用 .files 获取上传文件
    user_icon_url = None

    # 处理头像上传
    if image:
        user_icon_url, error = save_file(image, app.config['UPLOAD_FOLDER'])
        if error:
            return jsonify({"error": error}), 400
        user_icon_url = f"http://localhost:8080/{user_icon_url}"

    # 如果没有上传新的头像，获取用户的原头像
    if user_icon_url is None:
        query = 'SELECT user_icon_url FROM users WHERE id=%s'
        result = mysql_pool.fetch(query, (current_user,), one=True)
        user_icon_url = result['user_icon_url']

    # 更新用户信息和密码（如果有新的密码）
    if password:
        query = 'UPDATE users SET username=%s, user_icon_url=%s, password=%s WHERE id=%s'
        try:
            mysql_pool.execute(query, (username, user_icon_url, password, current_user))
        except Exception as e:
            logger.error(f"更新用户信息失败: {e}")
            return jsonify({"error": "更新用户信息失败"}), 500
    else:
        # 如果没有更新密码
        query = 'UPDATE users SET username=%s, user_icon_url=%s WHERE id=%s'
        try:
            mysql_pool.execute(query, (username, user_icon_url, current_user))
        except Exception as e:
            logger.error(f"更新用户信息失败: {e}")
            return jsonify({"error": "更新用户信息失败"}), 500

    return jsonify({"result": "success"}), 200
