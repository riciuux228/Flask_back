import logging
import os
import time
import uuid
from datetime import datetime

import jwt

from flask import Blueprint, jsonify, request, Flask, url_for
from functools import wraps

from werkzeug.utils import secure_filename

from SqlManage.connect_mysql import MysqlPool
from blueprints.article import generate_numeric_uuid

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(ascTime)s - %(levelName)s - %(message)s',
    filename='admin.py.log',
    filemode='w',
    encoding='utf-8'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config['SECRET_KEY'] = 'yy401'  # 设置密钥
app.config['UPLOAD_FOLDER'] = 'static/uploads'

UPLOAD_IMAGE_FOLDER = 'static/image'  # 替换为实际路径
UPLOAD_ATTACHMENT_FOLDER = 'static/attachments'  # 替换为实际路径
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'pdf', 'doc', 'docx', 'xlsx'}
BASE_IMAGE_URL = "http://localhost:8080/static/image/"
BASE_ATTACHMENT_URL = "http://localhost:8080/static/attachments/"



# 定义用户蓝图
admin_blueprint = Blueprint('admin', __name__, template_folder='templates')

mysql_pool = MysqlPool()  # 初始化连接池


def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        # 打印所有请求头
        print("Request headers:", request.headers)

        auth_header = request.headers.get('Authorization')
        if auth_header and auth_header.startswith('Bearer '):
            token = auth_header.split(' ')[1]
        else:
            # 如果没有在头部找到 token，可以选择从请求体或查询参数中获取
            token = request.form.get('access_token') or request.args.get('access_token')

        print(f"Extracted token: {token}")

        if not token:
            return jsonify({
                "code": 1001,
                "msg": "没有 Token"
            }), 403

        try:
            # 解析 token，进行验证
            data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=["HS256"])
            print(f"Token payload: {data}")
        except jwt.ExpiredSignatureError:
            return jsonify({
                "code": 1001,
                "msg": "Token 过期"
            }), 403
        except jwt.InvalidTokenError:
            return jsonify({
                "code": 1001,
                "msg": "无效的 Token"
            }), 403

        # 如果验证成功，返回 code 0
        return f(*args, **kwargs)

    return decorated

# verify_token
@admin_blueprint.route('/verify_token', methods=['POST'])
@token_required
def verify_token():
    """
    验证 Token 是否有效
    """
    return jsonify({
        "code": 0,
        "msg": "Token 有效"
    })




# 登录接口，生成access_token
@admin_blueprint.route('/admin_login', methods=['POST'])
def admin_login():
    """
    管理员登录，成功后返回access_token
    """
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')

    if not username or not password:
        return jsonify({
            "code": 1,
            "msg": "用户名或密码不能为空"
        })
    query = 'SELECT role FROM users WHERE username = %s AND password = %s'
    result = mysql_pool.fetch(query, (username, password), one=True)
    if result is None:
        return jsonify({
            "code": 2,
            "msg": "用户名或密码错误"
        })
    if result['role'] != 'admin':
        return jsonify({
            "code": 3,
            "msg": "非管理员用户"
        })
    # 如果验证通过，生成 access_token（不包含 'exp' 字段）
    token = jwt.encode({
        'user': username
        # 'exp' 字段被移除，使得 token 永不过期
    }, app.config['SECRET_KEY'], algorithm="HS256")

    return jsonify({
        "code": 0,
        "msg": "登入成功",
        "data": {
            "token": token
        }
    })


# 退出登录接口
@admin_blueprint.route('/logout', methods=['POST'])
@token_required
def logout():
    """
    注销用户
    """
    # 这里可以进行token黑名单处理，或者其他逻辑
    return jsonify({
        "code": 0,
        "msg": "注销成功"})


@admin_blueprint.route('/api/articles', methods=['GET'])
@token_required  # 确保该接口需要验证 Token
def get_articles():
    """
    查询文章列表，支持按条件查询，并包含分类名称
    """
    # 获取查询参数
    article_id = request.args.get('id')
    author = request.args.get('author')
    title = request.args.get('title')
    category_name = request.args.get('category_name')

    # 构造查询条件
    conditions = []
    args = []

    if article_id:
        conditions.append("a.aid = %s")
        args.append(article_id)
    if author:
        conditions.append("a.author LIKE %s")
        args.append(f"%{author}%")
    if title:
        conditions.append("a.title LIKE %s")
        args.append(f"%{title}%")
    if category_name:
        conditions.append("c.category_name = %s")
        args.append(category_name)

    # 拼接查询条件
    condition_sql = " AND ".join(conditions)
    base_query = """
        FROM yesapi_bjy_article a
        LEFT JOIN yesapi_bjy_article_category c ON a.cid = c.cid
        WHERE a.is_delete = 0
    """

    if condition_sql:
        base_query += f" AND {condition_sql}"

    # **第一步**：查询符合条件的文章总数
    count_query = f"SELECT COUNT(*) AS total {base_query}"
    total_count_result = mysql_pool.fetch(count_query, args)
    total_count = total_count_result[0]['total'] if total_count_result else 0

    # **第二步**：查询分页文章数据
    query = f"""
        SELECT 
            a.id, 
            a.aid, 
            a.title, 
            a.author, 
            a.keywords, 
            a.description,
            a.content, 
            a.is_show, 
            a.is_delete, 
            a.is_top, 
            a.is_original, 
            a.click, 
            a.addtime, 
            a.cid, 
            c.category_name as label,  -- 分类名称
            a.image_url, 
            a.comment_count, 
            a.update_time, 
            a.auth_id
        {base_query} ORDER BY a.aid ASC
    """

    # 分页处理
    page = int(request.args.get('page', 1))
    limit = int(request.args.get('limit', 10))
    offset = (page - 1) * limit
    query += " LIMIT %s, %s"
    args.extend([offset, limit])

    # 执行查询
    result = mysql_pool.fetch(query, args)

    return jsonify({
        "code": 0,
        "msg": "查询成功",
        "count": total_count,  # 总记录数
        "data": result  # 分页数据
    })


@admin_blueprint.route('/api/getArticle', methods=['GET'])
@token_required
def get_article():
    """
    获取单个文章的详细信息
    """
    aid = request.args.get('aid')
    if not aid:
        return jsonify({"code": 1, "msg": "缺少文章ID"}), 400

    query = """
        SELECT 
            a.id, 
            a.aid, 
            a.title, 
            a.author, 
            a.content,  -- 确保包含 content
            a.keywords, 
            a.description, 
            a.is_show, 
            a.is_delete, 
            a.is_top, 
            a.is_original, 
            a.click, 
            a.addtime, 
            a.cid, 
            c.category_name, 
            a.image_url, 
            a.comment_count, 
            a.update_time, 
            a.auth_id
        FROM 
            yesapi_bjy_article a
        LEFT JOIN 
            yesapi_bjy_article_category c 
        ON 
            a.cid = c.cid
        WHERE 
            a.aid = %s AND a.is_delete = 0
    """
    result = mysql_pool.fetch(query, (aid,), one=True)
    if not result:
        return jsonify({"code": 2, "msg": "文章不存在"}), 404

    return jsonify({
        "code": 0,
        "msg": "查询成功",
        "data": result
    })



# Fetch Attachments for an Article
@admin_blueprint.route('/api/getAttachments', methods=['GET'])
@token_required
def get_attachments():
    """
    获取文章的附件列表
    """
    aid = request.args.get('aid')
    if not aid:
        return jsonify({"code": 1, "msg": "缺少文章ID"}), 400

    query = """
        SELECT 
            id, attachment_url, attachment_name, size, upload_time 
        FROM 
            article_attachments 
        WHERE 
            aid = %s
    """
    results = mysql_pool.fetch(query, (aid,))
    print("results:", results)
    return jsonify({"code": 0, "msg": "附件获取成功", "data": results})

# Delete Attachment for an Article
@admin_blueprint.route('/api/deleteAttachment/<int:attachment_id>', methods=['DELETE'])
@token_required
def delete_attachment(attachment_id):
    """
    删除特定附件
    """
    delete_query = "DELETE FROM article_attachments WHERE id = %s"
    result = mysql_pool.execute(delete_query, (attachment_id,))
    if result:
        return jsonify({"code": 0, "msg": "附件删除成功"})
    else:
        return jsonify({"code": 1, "msg": "附件删除失败"}), 400




@admin_blueprint.route('/api/uploadImage', methods=['POST'])
@token_required
def upload_image():
    """
    处理 CKEditor 的图片上传
    """
    if 'upload' not in request.files:
        return jsonify({"error": {"message": "没有文件上传"}}), 400

    file = request.files['upload']

    # 检查文件类型
    if file.mimetype not in ['image/png', 'image/jpeg', 'image/gif']:
        return jsonify({"error": {"message": "不支持的文件类型"}}), 400

    # 创建保存路径
    upload_folder = app.config.get('UPLOAD_FOLDER', 'static/uploads')
    if not os.path.exists(upload_folder):
        os.makedirs(upload_folder)

    # 保存文件到指定目录
    filename = secure_filename(file.filename)
    file_path = os.path.join(upload_folder, filename)
    file.save(file_path)

    # 返回文件的访问 URL
    file_url = url_for('static', filename='uploads/' + filename, _external=True)
    return jsonify({"url": file_url})
@admin_blueprint.route('/api/addArticle', methods=['POST'])
@admin_blueprint.route('/api/updateArticle', methods=['PUT'])
@token_required
def update_article():
    """
    添加或更新文章
    """
    # 使用 request.form 来获取表单中的文本字段
    data = request.form

    # 获取文章主图和附件
    article_image = request.files.get('article_image')
    attachments = request.files.getlist('attachments')

    required_fields = ['title', 'author', 'cid', 'content']

    # 检查必要字段
    for field in required_fields:
        if field not in data or not data[field]:
            return jsonify({"code": 1, "msg": f"缺少必要的字段：{field}"}), 400

    try:
        # 准备数据
        aid = data.get('aid')  # aid 在添加模式中可能不存在
        title = data['title']
        author = data['author']
        cid = data['cid']
        content = data['content']
        keywords = data.get('keywords', '')
        description = data.get('description', '')
        is_show = int(data.get('is_show', 0))
        is_top = int(data.get('is_top', 0))
        is_original = int(data.get('is_original', 0))
        update_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        # 获取当前时间的 Unix 时间戳
        add_time = int(time.time())  # 以秒为单位的 Unix 时间戳，确保它是 int 类型

        # 打印日志以确保值正确
        logger.info(f"title: {title}, author: {author}, cid: {cid}, content: {content[:50]}...")
        logger.info(f"keywords: {keywords}, description: {description}, addtime: {add_time}, update_time: {update_time}")

        # 如果有新的主图，则处理文章主图上传
        if article_image and allowed_file(article_image.filename):
            filename = f"{uuid.uuid4().hex}_{secure_filename(article_image.filename)}"
            image_path = os.path.join(UPLOAD_IMAGE_FOLDER, filename)
            article_image.save(image_path)
            image_url = BASE_IMAGE_URL + filename
        else:
            image_url = None  # 表示不更新 image_url

        # 更新或插入数据库
        if aid:  # 更新文章
            # 创建基础 SQL 语句
            update_fields = [
                "title=%s",
                "author=%s",
                "cid=%s",
                "content=%s",
                "keywords=%s",
                "description=%s",
                "is_show=%s",
                "is_top=%s",
                "is_original=%s",
                "update_time=%s"
            ]
            args = [title, author, cid, content, keywords, description, is_show, is_top, is_original, update_time]

            # 如果有新的主图，则添加 image_url 的更新
            if image_url:
                update_fields.append("image_url=%s")
                args.append(image_url)

            # 构造最终的 SQL 查询
            update_query = f"UPDATE yesapi_bjy_article SET {', '.join(update_fields)} WHERE aid=%s"
            args.append(aid)

            # 执行 SQL 更新
            logger.info(f"Executing update query with args: {args}")
            mysql_pool.execute(update_query, args)
        else:  # 添加新文章
            aid = generate_numeric_uuid()  # 生成文章ID
            query = """
                INSERT INTO yesapi_bjy_article (aid,title, author, cid, content, image_url, keywords, description,
                is_show, is_top, is_original, addtime) 
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            args = (aid, title, author, cid, content, image_url or '', keywords, description, is_show, is_top, is_original, add_time)
            logger.info(f"Executing insert query with args: {args}")
            mysql_pool.execute(query, args)

        # 处理附件上传
        if attachments:
            for attachment in attachments:
                if attachment and allowed_file(attachment.filename):
                    attachment_filename = f"{uuid.uuid4().hex}_{secure_filename(attachment.filename)}"
                    attachment_path = os.path.join(UPLOAD_ATTACHMENT_FOLDER, attachment_filename)
                    attachment.save(attachment_path)

                    attachment_url = BASE_ATTACHMENT_URL + attachment_filename
                    attachment_name = attachment.filename
                    attachment_size = os.path.getsize(attachment_path)

                    # 插入附件表
                    attachment_query = """
                        INSERT INTO article_attachments (aid, attachment_url, attachment_name, size)
                        VALUES (%s, %s, %s, %s)
                    """
                    attachment_args = (aid, attachment_url, attachment_name, attachment_size)
                    logger.info(f"Inserting attachment: {attachment_args}")
                    mysql_pool.execute(attachment_query, attachment_args)

        return jsonify({"code": 0, "msg": "文章更新成功" if aid else "文章添加成功"})

    except Exception as e:
        logger.error(f"操作文章失败: {e}")
        return jsonify({"code": 1, "msg": "操作文章失败", "error": str(e)})





def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS




@admin_blueprint.route('/api/deleteArticles', methods=['POST'])
@token_required
def delete_articles():
    """
    删除文章，支持批量删除
    """
    data = request.get_json()
    ids = data.get('ids', [])
    if not ids:
        return jsonify({"code": 1, "msg": "没有指定要删除的文章"})

    placeholders = ','.join(['%s'] * len(ids))
    query = f"UPDATE yesapi_bjy_article SET is_delete = 1 WHERE aid IN ({placeholders})"

    try:
        mysql_pool.execute(query, ids)
        return jsonify({"code": 0, "msg": "文章删除成功"})
    except Exception as e:
        logger.error(f"删除文章失败: {e}")
        return jsonify({"code": 1, "msg": "删除失败", "error": str(e)})


@admin_blueprint.route('/api/categories', methods=['GET'])
@token_required
def get_categories():
    """
    获取文章分类列表，支持根据分类ID和分类名称筛选，支持分页
    """
    try:
        # 获取请求参数
        category_id = request.args.get('id', '').strip()  # 获取ID参数
        category_name = request.args.get('name', '').strip()  # 获取名称参数
        page = int(request.args.get('page', 1))  # 当前页码
        per_page = int(request.args.get('per_page', 10))  # 每页显示条目数

        # 基础SQL查询语句
        query = "SELECT cid, category_name FROM yesapi_bjy_article_category WHERE 1=1"
        count_query = "SELECT COUNT(*) as total FROM yesapi_bjy_article_category WHERE 1=1"  # 用于获取总条数的查询
        params = []

        # 如果有ID筛选条件
        if category_id:
            query += " AND cid = %s"
            count_query += " AND cid = %s"
            params.append(category_id)

        # 如果有名称筛选条件
        if category_name:
            query += " AND category_name LIKE %s"
            count_query += " AND category_name LIKE %s"
            params.append(f"%{category_name}%")

        # 执行总条数查询
        total_result = mysql_pool.fetch(count_query, params, one=True)
        total_items = total_result['total']  # 获取总条数
        total_pages = (total_items + per_page - 1) // per_page  # 计算总页数

        # 添加 ORDER BY 和分页的限制
        query += " ORDER BY cid ASC LIMIT %s OFFSET %s"
        params.append(per_page)
        params.append((page - 1) * per_page)

        # 执行查询
        result = mysql_pool.fetch(query, params)

        # 返回分页信息和查询结果
        return jsonify({
            "code": 0,
            "msg": "查询成功",
            "data": result,
            "pagination": {
                "currentPage": page,
                "totalPages": total_pages,
                "totalItems": total_items,
                "perPage": per_page
            }
        })
    except Exception as e:
        logger.error(f"获取分类失败: {e}")
        return jsonify({"code": 1, "msg": "获取分类失败", "error": str(e)})




@admin_blueprint.route('/api/add_category', methods=['POST'])
@token_required
def add_category():
    """
    添加文章分类
    """
    try:
        # 获取前端传递的数据
        data = request.get_json()
        category_name = data.get('name')

        # 验证分类名称
        if not category_name or category_name.strip() == '':
            return jsonify({"code": 1, "msg": "分类名称不能为空"})

        # 插入分类到数据库
        query = "INSERT INTO yesapi_bjy_article_category (category_name) VALUES (%s)"
        mysql_pool.execute(query, (category_name.strip(),))

        return jsonify({"code": 0, "msg": "分类添加成功"})
    except Exception as e:
        logger.error(f"添加分类失败: {e}")
        return jsonify({"code": 1, "msg": "添加分类失败", "error": str(e)})


@admin_blueprint.route('/api/categories/<int:cid>', methods=['DELETE'])
@token_required
def delete_category(cid):
    """
    删除文章分类，先检查该分类下是否有文章
    """
    try:
        # 先检查分类下是否有文章
        query_check_articles = "SELECT COUNT(*) as article_count FROM yesapi_bjy_article WHERE cid = %s"
        result = mysql_pool.fetch(query_check_articles, (cid,),one=True)  # 使用 fetch_one 查询文章数量

        # 从字典中提取文章数量
        article_count = result.get("article_count", 0)

        # 如果有文章，不能删除该分类
        if article_count > 0:
            return jsonify({"code": 1, "msg": "该分类下有文章，不能删除"})

        # 如果没有文章，执行删除分类操作
        query_delete_category = "DELETE FROM yesapi_bjy_article_category WHERE cid = %s"
        mysql_pool.execute(query_delete_category, (cid,))

        return jsonify({"code": 0, "msg": "删除成功"})

    except Exception as e:
        logger.error(f"删除分类失败: {e}")
        return jsonify({"code": 1, "msg": "删除分类失败", "error": str(e)})


# 评论管理部分


# 获取评论列表
@admin_blueprint.route('/api/comments', methods=['GET'])
@token_required
def get_comments():
    """
    获取文章评论列表，支持筛选和分页
    """
    try:
        # 获取筛选条件
        article_id = request.args.get('article_id', '').strip()
        user_id = request.args.get('user_id', '').strip()
        content = request.args.get('content', '').strip()
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 10))

        # 构造查询语句
        query = "SELECT id, article_id, user_id, content, parent_comment_id, like_count, created_at FROM comments WHERE 1=1"
        count_query = "SELECT COUNT(*) as total FROM comments WHERE 1=1"
        params = []

        # 根据筛选条件添加查询条件
        if article_id:
            query += " AND article_id = %s"
            count_query += " AND article_id = %s"
            params.append(article_id)

        if user_id:
            query += " AND user_id = %s"
            count_query += " AND user_id = %s"
            params.append(user_id)

        if content:
            query += " AND content LIKE %s"
            count_query += " AND content LIKE %s"
            params.append(f"%{content}%")

        # 查询总条数
        total_result = mysql_pool.fetch(count_query, params, one=True)
        total_items = total_result['total']
        total_pages = (total_items + per_page - 1) // per_page

        # 添加分页和排序
        query += " ORDER BY created_at DESC LIMIT %s OFFSET %s"
        params.append(per_page)
        params.append((page - 1) * per_page)

        # 执行查询
        result = mysql_pool.fetch(query, params)

        return jsonify({
            "code": 0,
            "msg": "查询成功",
            "data": result,
            "pagination": {
                "currentPage": page,
                "totalPages": total_pages,
                "totalItems": total_items,
                "perPage": per_page
            }
        })
    except Exception as e:
        logger.error(f"查询评论失败: {e}")
        return jsonify({"code": 1, "msg": "查询评论失败", "error": str(e)})


# 删除评论
@admin_blueprint.route('/api/comments/<int:comment_id>', methods=['DELETE'])
@token_required
def delete_comment(comment_id):
    """
    删除评论
    """
    try:
        query = "DELETE FROM comments WHERE id = %s"
        mysql_pool.execute(query, (comment_id,))
        return jsonify({"code": 0, "msg": "删除成功"})
    except Exception as e:
        logger.error(f"删除评论失败: {e}")
        return jsonify({"code": 1, "msg": "删除评论失败", "error": str(e)})







# 获取用户列表
@admin_blueprint.route('/api/users', methods=['GET'])
@token_required
def get_users():
    """
    获取普通用户列表，支持筛选和分页（基于手机号码）
    """
    try:
        # 获取筛选条件
        user_id = request.args.get('user_id', '').strip()
        username = request.args.get('username', '').strip()
        phone = request.args.get('phone', '').strip()
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 10))

        # 构造查询语句
        query = """
            SELECT id, username, phone, role, is_phone_verified, created_at, updated_at, user_icon_url 
            FROM users 
            WHERE role != 'admin'
        """
        count_query = "SELECT COUNT(*) as total FROM users WHERE role != 'admin'"
        params = []

        # 根据筛选条件添加查询条件
        if user_id:
            query += " AND id = %s"
            count_query += " AND id = %s"
            params.append(user_id)

        if username:
            query += " AND username LIKE %s"
            count_query += " AND username LIKE %s"
            params.append(f"%{username}%")

        if phone:
            query += " AND phone LIKE %s"
            count_query += " AND phone LIKE %s"
            params.append(f"%{phone}%")

        # 查询总条数
        total_result = mysql_pool.fetch(count_query, params, one=True)
        total_items = total_result['total']
        total_pages = (total_items + per_page - 1) // per_page

        # 添加分页和排序
        query += " ORDER BY created_at DESC LIMIT %s OFFSET %s"
        params.append(per_page)
        params.append((page - 1) * per_page)

        # 执行查询
        result = mysql_pool.fetch(query, params)

        return jsonify({
            "code": 0,
            "msg": "查询成功",
            "data": result,
            "pagination": {
                "currentPage": page,
                "totalPages": total_pages,
                "totalItems": total_items,
                "perPage": per_page
            }
        })
    except Exception as e:
        logger.error(f"查询用户失败: {e}")
        return jsonify({"code": 1, "msg": "查询用户失败", "error": str(e)})

# 获取单个用户详情
@admin_blueprint.route('/api/users/<int:user_id>', methods=['GET'])
@token_required
def get_user(user_id):
    """
    获取单个用户的详细信息
    """
    try:
        query = "SELECT id, username, phone, role, is_phone_verified, created_at, updated_at, user_icon_url FROM users WHERE id = %s AND role != 'admin'"
        user = mysql_pool.fetch(query, (user_id,), one=True)
        if user:
            return jsonify({"code": 0, "msg": "查询成功", "data": user})
        else:
            return jsonify({"code": 1, "msg": "用户未找到"}), 404
    except Exception as e:
        logger.error(f"获取用户详情失败: {e}")
        return jsonify({"code": 1, "msg": "获取用户详情失败", "error": str(e)})

# 添加用户
@admin_blueprint.route('/api/add_user', methods=['POST'])
@token_required
def add_user():
    """
    添加新用户（基于手机号码）
    """
    try:
        data = request.json
        username = data.get('username', '').strip()
        phone = data.get('phone', '').strip()
        password = data.get('password', '').strip()
        role = data.get('role', 'user').strip()

        # 基本验证
        if not username or not phone or not password:
            return jsonify({"code": 1, "msg": "缺少必填字段"})

        # 检查手机号是否已存在
        existing_user = mysql_pool.fetch("SELECT id FROM users WHERE phone = %s", (phone,), one=True)
        if existing_user:
            return jsonify({"code": 1, "msg": "手机号已存在"})

        # 插入新用户
        insert_query = """
            INSERT INTO users (username, phone, password, role) 
            VALUES (%s, %s, %s, %s)
        """
        mysql_pool.execute(insert_query, (username, phone, password, role))

        return jsonify({"code": 0, "msg": "添加用户成功"})
    except Exception as e:
        logger.error(f"添加用户失败: {e}")
        return jsonify({"code": 1, "msg": "添加用户失败", "error": str(e)})

# 删除用户
@admin_blueprint.route('/api/users/<int:user_id>', methods=['DELETE'])
@token_required
def delete_user(user_id):
    """
    删除用户
    """
    try:
        # 防止删除管理员
        user = mysql_pool.fetch("SELECT role FROM users WHERE id = %s", (user_id,), one=True)
        if not user:
            return jsonify({"code": 1, "msg": "用户不存在"})
        if user['role'] == 'admin':
            return jsonify({"code": 1, "msg": "无法删除管理员用户"})

        # 删除用户
        delete_query = "DELETE FROM users WHERE id = %s"
        mysql_pool.execute(delete_query, (user_id,))
        return jsonify({"code": 0, "msg": "删除用户成功"})
    except Exception as e:
        logger.error(f"删除用户失败: {e}")
        return jsonify({"code": 1, "msg": "删除用户失败", "error": str(e)})

# 更新用户信息
@admin_blueprint.route('/api/users/<int:user_id>', methods=['PUT'])
@token_required
def update_user(user_id):
    """
    更新用户信息（基于手机号码）
    """
    try:
        data = request.json
        username = data.get('username', '').strip()
        phone = data.get('phone', '').strip()
        role = data.get('role', '').strip()
        is_phone_verified = data.get('is_phone_verified')

        # 构造更新语句
        update_fields = []
        params = []

        if username:
            update_fields.append("username = %s")
            params.append(username)
        if phone:
            # 检查新的手机号是否已存在
            existing_user = mysql_pool.fetch("SELECT id FROM users WHERE phone = %s AND id != %s", (phone, user_id), one=True)
            if existing_user:
                return jsonify({"code": 1, "msg": "手机号已存在"})
            update_fields.append("phone = %s")
            params.append(phone)
        if role:
            update_fields.append("role = %s")
            params.append(role)
        if is_phone_verified is not None:
            update_fields.append("is_phone_verified = %s")
            params.append(int(is_phone_verified))

        if not update_fields:
            return jsonify({"code": 1, "msg": "没有需要更新的字段"})

        update_query = f"UPDATE users SET {', '.join(update_fields)} WHERE id = %s"
        params.append(user_id)

        mysql_pool.execute(update_query, tuple(params))

        return jsonify({"code": 0, "msg": "更新用户成功"})
    except Exception as e:
        logger.error(f"更新用户失败: {e}")
        return jsonify({"code": 1, "msg": "更新用户失败", "error": str(e)})


# 获取作者列表
@admin_blueprint.route('/api/authors', methods=['GET'])
@token_required
def get_authors():
    """
    获取作者列表，支持筛选和分页（角色为'author'）
    """
    try:
        # 获取筛选条件
        author_id = request.args.get('author_id', '').strip()
        username = request.args.get('username', '').strip()
        phone = request.args.get('phone', '').strip()
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 10))

        # 构造查询语句
        query = """
            SELECT id, username, phone, role, is_phone_verified, created_at, updated_at, user_icon_url 
            FROM users 
            WHERE role = 'author'
        """
        count_query = "SELECT COUNT(*) as total FROM users WHERE role = 'author'"
        params = []

        # 根据筛选条件添加查询条件
        if author_id:
            query += " AND id = %s"
            count_query += " AND id = %s"
            params.append(author_id)

        if username:
            query += " AND username LIKE %s"
            count_query += " AND username LIKE %s"
            params.append(f"%{username}%")

        if phone:
            query += " AND phone LIKE %s"
            count_query += " AND phone LIKE %s"
            params.append(f"%{phone}%")

        # 查询总条数
        total_result = mysql_pool.fetch(count_query, params, one=True)
        total_items = total_result['total']
        total_pages = (total_items + per_page - 1) // per_page

        # 添加分页和排序
        query += " ORDER BY created_at DESC LIMIT %s OFFSET %s"
        params.append(per_page)
        params.append((page - 1) * per_page)

        # 执行查询
        result = mysql_pool.fetch(query, params)

        return jsonify({
            "code": 0,
            "msg": "查询成功",
            "data": result,
            "pagination": {
                "currentPage": page,
                "totalPages": total_pages,
                "totalItems": total_items,
                "perPage": per_page
            }
        })
    except Exception as e:
        logger.error(f"查询作者失败: {e}")
        return jsonify({"code": 1, "msg": "查询作者失败", "error": str(e)})

# 获取单个作者详情
@admin_blueprint.route('/api/authors/<int:author_id>', methods=['GET'])
@token_required
def get_author(author_id):
    """
    获取单个作者的详细信息
    """
    try:
        query = "SELECT id, username, phone, role, is_phone_verified, created_at, updated_at, user_icon_url FROM users WHERE id = %s AND role = 'author'"
        author = mysql_pool.fetch(query, (author_id,), one=True)
        if author:
            return jsonify({"code": 0, "msg": "查询成功", "data": author})
        else:
            return jsonify({"code": 1, "msg": "作者未找到"}), 404
    except Exception as e:
        logger.error(f"获取作者详情失败: {e}")
        return jsonify({"code": 1, "msg": "获取作者详情失败", "error": str(e)})

# 添加作者
@admin_blueprint.route('/api/add_author', methods=['POST'])
@token_required
def add_author():
    """
    添加新作者
    """
    try:
        data = request.json
        username = data.get('username', '').strip()
        phone = data.get('phone', '').strip()
        password = data.get('password', '').strip()
        role = data.get('role', 'author').strip()

        # 基本验证
        if not username or not phone or not password:
            return jsonify({"code": 1, "msg": "缺少必填字段"})

        # 检查手机号是否已存在
        existing_user = mysql_pool.fetch("SELECT id FROM users WHERE phone = %s", (phone,), one=True)
        if existing_user:
            return jsonify({"code": 1, "msg": "手机号已存在"})

        # 插入新作者
        insert_query = """
            INSERT INTO users (username, phone, password, role) 
            VALUES (%s, %s, %s, %s)
        """
        mysql_pool.execute(insert_query, (username, phone, password, role))

        return jsonify({"code": 0, "msg": "添加作者成功"})
    except Exception as e:
        logger.error(f"添加作者失败: {e}")
        return jsonify({"code": 1, "msg": "添加作者失败", "error": str(e)})

# 删除作者
@admin_blueprint.route('/api/authors/<int:author_id>', methods=['DELETE'])
@token_required
def delete_author(author_id):
    """
    删除作者
    """
    try:
        # 防止删除管理员
        author = mysql_pool.fetch("SELECT role FROM users WHERE id = %s", (author_id,), one=True)
        if not author:
            return jsonify({"code": 1, "msg": "作者不存在"})
        if author['role'] == 'admin':
            return jsonify({"code": 1, "msg": "无法删除管理员用户"})

        # 删除作者
        delete_query = "DELETE FROM users WHERE id = %s"
        mysql_pool.execute(delete_query, (author_id,))
        return jsonify({"code": 0, "msg": "删除作者成功"})
    except Exception as e:
        logger.error(f"删除作者失败: {e}")
        return jsonify({"code": 1, "msg": "删除作者失败", "error": str(e)})

# 更新作者信息
@admin_blueprint.route('/api/authors/<int:author_id>', methods=['PUT'])
@token_required
def update_author(author_id):
    """
    更新作者信息
    """
    try:
        data = request.json
        username = data.get('username', '').strip()
        phone = data.get('phone', '').strip()
        role = data.get('role', 'author').strip()
        is_phone_verified = data.get('is_phone_verified')

        # 构造更新语句
        update_fields = []
        params = []

        if username:
            update_fields.append("username = %s")
            params.append(username)
        if phone:
            # 检查新的手机号是否已存在
            existing_author = mysql_pool.fetch("SELECT id FROM users WHERE phone = %s AND id != %s", (phone, author_id), one=True)
            if existing_author:
                return jsonify({"code": 1, "msg": "手机号已存在"})
            update_fields.append("phone = %s")
            params.append(phone)
        if role:
            update_fields.append("role = %s")
            params.append(role)
        if is_phone_verified is not None:
            update_fields.append("is_phone_verified = %s")
            params.append(int(is_phone_verified))

        if not update_fields:
            return jsonify({"code": 1, "msg": "没有需要更新的字段"})

        update_query = f"UPDATE users SET {', '.join(update_fields)} WHERE id = %s"
        params.append(author_id)

        mysql_pool.execute(update_query, tuple(params))

        return jsonify({"code": 0, "msg": "更新作者成功"})
    except Exception as e:
        logger.error(f"更新作者失败: {e}")
        return jsonify({"code": 1, "msg": "更新作者失败", "error": str(e)})


# 获取角色用户列表
@admin_blueprint.route('/api/roles', methods=['GET'])
@token_required
def get_roles():
    """
    获取用户列表，支持筛选和分页
    过滤条件包括用户ID、用户名、手机号码和角色
    """
    try:
        # 获取筛选条件
        user_id = request.args.get('user_id', '').strip()
        username = request.args.get('username', '').strip()
        phone = request.args.get('phone', '').strip()
        role = request.args.get('role', '').strip()
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 10))

        # 构造查询语句
        query = """
            SELECT id, username, phone, role, is_phone_verified, created_at, updated_at, user_icon_url 
            FROM users 
            WHERE role IN ('visitor', 'user', 'author', 'admin')
        """
        count_query = "SELECT COUNT(*) as total FROM users WHERE role IN ('visitor', 'user', 'author', 'admin')"
        params = []

        # 根据筛选条件添加查询条件
        if user_id:
            query += " AND id = %s"
            count_query += " AND id = %s"
            params.append(user_id)

        if username:
            query += " AND username LIKE %s"
            count_query += " AND username LIKE %s"
            params.append(f"%{username}%")

        if phone:
            query += " AND phone LIKE %s"
            count_query += " AND phone LIKE %s"
            params.append(f"%{phone}%")

        if role and role in ['visitor', 'user', 'author', 'admin']:
            query += " AND role = %s"
            count_query += " AND role = %s"
            params.append(role)

        # 查询总条数
        total_result = mysql_pool.fetch(count_query, params, one=True)
        total_items = total_result['total']
        total_pages = (total_items + per_page - 1) // per_page

        # 添加分页和排序
        query += " ORDER BY created_at DESC LIMIT %s OFFSET %s"
        params.append(per_page)
        params.append((page - 1) * per_page)

        # 执行查询
        result = mysql_pool.fetch(query, params)

        return jsonify({
            "code": 0,
            "msg": "查询成功",
            "data": result,
            "pagination": {
                "currentPage": page,
                "totalPages": total_pages,
                "totalItems": total_items,
                "perPage": per_page
            }
        })
    except Exception as e:
        logger.error(f"查询角色用户失败: {e}")
        return jsonify({"code": 1, "msg": "查询角色用户失败", "error": str(e)})


# 获取当前登录用户信息
def get_current_user(token):
    """
    获取当前登录用户的信息
    """
    try:
        payload = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
        user = payload.get('user')
        print("admin payload",payload)
        if not user:
            return None

        user = mysql_pool.fetch("SELECT id, username, phone, role FROM users WHERE username = %s", (user,), one=True)
        return user
    except Exception as e:
        logger.error(f"获取当前管理员失败: {e}")
        return None


@admin_blueprint.route('/api/roles/<int:user_id>', methods=['PUT'])
@token_required
def update_user_role(user_id):
    """
    更新单个用户的角色
    """
    try:
        data = request.json
        new_role = data.get('role', '').strip()

        if new_role not in ['visitor', 'user', 'author', 'admin']:
            return jsonify({"code": 1, "msg": "无效的角色"}), 400
        # 防止修改自己的角色为非管理员角色
        auth_header = request.headers.get('Authorization')
        token = auth_header.split(' ')[1]
        print("update_user_role token",token)
        current_user = get_current_user(token)  # 假设有一个函数获取当前登录用户
        print("current_user",current_user)
        if current_user['id'] == user_id and new_role != 'admin':
            return jsonify({"code": 1, "msg": "无法修改自己的角色"}), 403

        # 检查用户是否存在
        user = mysql_pool.fetch("SELECT id FROM users WHERE id = %s", (user_id,), one=True)
        if not user:
            return jsonify({"code": 1, "msg": "用户不存在"}), 404

        # 更新角色
        update_query = "UPDATE users SET role = %s WHERE id = %s"
        mysql_pool.execute(update_query, (new_role, user_id))

        return jsonify({"code": 0, "msg": "更新角色成功"})
    except Exception as e:
        logger.error(f"更新角色失败: {e}")
        return jsonify({"code": 1, "msg": "更新角色失败", "error": str(e)})



@admin_blueprint.route('/api/update_roles', methods=['PUT'])
@token_required
def bulk_update_roles():
    """
    批量更新用户角色
    """
    try:
        # 手动提取并解析 Token 以获取 current_user
        auth_header = request.headers.get('Authorization')
        if auth_header and auth_header.startswith('Bearer '):
            token = auth_header.split(' ')[1]
        else:
            # 如果没有在头部找到 token，可以选择从请求体或查询参数中获取
            token = request.form.get('access_token') or request.args.get('access_token')

        if not token:
            return jsonify({
                "code": 1001,
                "msg": "没有 Token"
            }), 403

        try:
            # 解析 Token，获取用户信息
            data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=["HS256"])
            current_user = mysql_pool.fetch("SELECT * FROM users WHERE username = %s", (data['user'],), one=True)
            if not current_user:
                return jsonify({"code": 1001, "msg": "用户不存在"}), 403
        except jwt.ExpiredSignatureError:
            return jsonify({
                "code": 1001,
                "msg": "Token 过期"
            }), 403
        except jwt.InvalidTokenError:
            return jsonify({
                "code": 1001,
                "msg": "无效的 Token"
            }), 403

        # 获取请求数据
        data = request.json
        user_ids = data.get('user_ids', [])
        new_role = data.get('role', '').strip()
        logger.debug(f"Received bulk update request: user_ids={user_ids}, new_role={new_role}")

        # 确保 user_ids 是列表
        if not isinstance(user_ids, list):
            return jsonify({"code": 1, "msg": "用户ID列表无效"}), 400

        # 尝试将 user_ids 转换为整数
        try:
            user_ids = [int(uid) for uid in user_ids]
        except ValueError:
            return jsonify({"code": 1, "msg": "用户ID必须为整数"}), 400

        # 验证 user_ids 是否为空
        if not user_ids:
            return jsonify({"code": 1, "msg": "未选择任何用户"}), 400

        # 验证每个 user_id 是否为正整数
        if not all(uid > 0 for uid in user_ids):
            return jsonify({"code": 1, "msg": "用户ID必须为正整数"}), 400

        # 验证 new_role 是否有效
        if new_role not in ['visitor', 'user', 'author', 'admin']:
            return jsonify({"code": 1, "msg": "无效的角色"}), 400

        # 防止批量修改为非管理员角色（可根据需求调整）
        if current_user['role'] == 'admin' and new_role != 'admin':
            # 检查是否试图修改自己的角色
            if current_user['id'] in user_ids:
                return jsonify({"code": 1, "msg": "无法修改自己的角色"}), 403

        # 检查所有 user_ids 是否存在
        placeholders = ','.join(['%s'] * len(user_ids))
        existing_users = mysql_pool.fetch(f"SELECT id FROM users WHERE id IN ({placeholders})", tuple(user_ids))
        existing_user_ids = [user['id'] for user in existing_users]

        missing_user_ids = set(user_ids) - set(existing_user_ids)
        if missing_user_ids:
            return jsonify({"code": 1, "msg": f"用户ID不存在: {', '.join(map(str, missing_user_ids))}"}), 404

        # 更新角色
        update_query = f"UPDATE users SET role = %s WHERE id IN ({placeholders})"
        params = [new_role] + user_ids
        mysql_pool.execute(update_query, tuple(params))

        return jsonify({"code": 0, "msg": "批量更新角色成功"})
    except Exception as e:
        logger.error(f"批量更新角色失败: {e}", exc_info=True)
        return jsonify({"code": 1, "msg": "批量更新角色失败", "error": str(e)}), 500


# 管理员信息

# 获取当前登录管理员的信息
@admin_blueprint.route('/api/admin/info', methods=['GET'])
@token_required
def get_admin_info():
    """
    获取当前登录管理员的信息
    """

    try:
        auth_header = request.headers.get('Authorization')
        token = auth_header.split(' ')[1]
        print("get_admin_info token", token)
        current_user = get_current_user(token)  # 假设有一个函数获取当前登录用户
        print("current_user", current_user)
        # 检查用户是否存在
        user = mysql_pool.fetch("SELECT id FROM users WHERE id = %s", (current_user['id'],), one=True)
        if not user:
            return jsonify({"code": 1, "msg": "用户不存在"}), 404
        admin_id = current_user['id']
        query = "SELECT id, username, phone, role, is_phone_verified, created_at, updated_at, user_icon_url FROM users WHERE id = %s AND role = 'admin'"
        admin_info = mysql_pool.fetch(query, (admin_id,), one=True)

        if admin_info:
            return jsonify({"code": 0, "msg": "查询成功", "data": admin_info})
        else:
            return jsonify({"code": 1, "msg": "管理员未找到"}), 404
    except Exception as e:
        logger.error(f"获取管理员信息失败: {e}")
        return jsonify({"code": 1, "msg": "获取管理员信息失败", "error": str(e)})



@admin_blueprint.route('/api/admin/<int:user_id>', methods=['PUT'])
@token_required
def update_admin(user_id):
    """
    更新用户信息（包括头像）
    """
    try:
        data = request.form  # 使用 request.form 获取表单数据
        username = data.get('username', '').strip()
        phone = data.get('phone', '').strip()
        role = data.get('role', '').strip()
        is_phone_verified = data.get('is_phone_verified')  # 获取手机验证状态

        # 处理 is_phone_verified
        if is_phone_verified is not None:
            # 将字符串 'true' / 'false' 转换为对应的整数 1 / 0
            is_phone_verified = 1 if is_phone_verified.lower() == 'true' else 0

        # 存储更新的字段和参数
        update_fields = []
        params = []

        if username:
            update_fields.append("username = %s")
            params.append(username)
        if phone:
            # 检查新的手机号是否已存在
            existing_user = mysql_pool.fetch("SELECT id FROM users WHERE phone = %s AND id != %s", (phone, user_id), one=True)
            if existing_user:
                return jsonify({"code": 1, "msg": "手机号已存在"})
            update_fields.append("phone = %s")
            params.append(phone)
        if role:
            update_fields.append("role = %s")
            params.append(role)
        if is_phone_verified is not None:
            update_fields.append("is_phone_verified = %s")
            params.append(is_phone_verified)  # 这里是整数 1 或 0

        # 处理头像更新
        if 'avatar' in request.files:  # 检查是否有新的头像文件
            avatar_file = request.files['avatar']
            if avatar_file:
                # 确保上传的文件是图像类型
                allowed_extensions = {'png', 'jpg', 'jpeg'}
                if '.' in avatar_file.filename and avatar_file.filename.rsplit('.', 1)[1].lower() in allowed_extensions:
                    # 生成安全的文件名
                    filename = secure_filename(avatar_file.filename)
                    avatar_path = os.path.join('static/user_icons', filename)  # 替换为您要保存文件的路径
                    avatar_file.save(avatar_path)  # 保存文件

                    # 拼接完整的 URL
                    base_image_url = 'http://localhost:8080/'
                    user_icon_url = f"{base_image_url}{avatar_path}"

                    # 添加到更新字段中
                    update_fields.append("user_icon_url = %s")
                    params.append(user_icon_url)

        # 如果没有要更新的字段，返回错误
        if not update_fields:
            return jsonify({"code": 1, "msg": "没有需要更新的字段"})

        # 执行更新操作
        update_query = f"UPDATE users SET {', '.join(update_fields)} WHERE id = %s"
        params.append(user_id)

        # 进行数据库操作
        mysql_pool.execute(update_query, tuple(params))

        return jsonify({"code": 0, "msg": "更新用户成功"})
    except Exception as e:
        logger.error(f"更新用户失败: {e}")
        return jsonify({"code": 1, "msg": "更新用户失败", "error": str(e)})



