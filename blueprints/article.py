import logging
import time
import uuid
from datetime import datetime

from flask import Blueprint, jsonify, request, Flask

from Check.file_verify import allowed_file, save_file
from SqlManage.connect_mysql import MysqlPool
from Check.token_verify import token_required, generate_token

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(ascTime)s - %(levelName)s - %(message)s',
    filename='article.py.log',
    filemode='w',
    encoding='utf-8'
)
logger = logging.getLogger(__name__)


# 配置文件上传的路径和允许的文件格式
UPLOAD_FOLDER = 'static/image'  # 头像保存路径
UPLOAD_FILE_FOLDER = 'static/attachments'  # 附件保存路径

# Flask 配置
app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['UPLOAD_FILE_FOLDER'] = UPLOAD_FILE_FOLDER



# 定义文章蓝图
article_blueprint = Blueprint('article', __name__, template_folder='templates')

mysql_pool = MysqlPool()  # 初始化连接池


@article_blueprint.route('/')
def get_all_articles():
    """
    获取所有可见且未删除的文章，返回 JSON 格式。
    """
    query = 'SELECT * FROM yesapi_bjy_article WHERE is_show=1 AND is_delete=0'
    try:
        result = mysql_pool.fetch(query, one=False)
        return jsonify(result)  # 使用 jsonify 直接返回 Python 数据
    except Exception as e:
        logger.error(f"获取所有文章失败: {e}")
        return jsonify({"error": "获取文章失败"}), 500


@article_blueprint.route('/count')
def count_articles():
    """
    统计所有可见且未删除文章的数量。
    """
    query = 'SELECT COUNT(*) as count FROM yesapi_bjy_article WHERE is_show=1 AND is_delete=0'
    try:
        result = mysql_pool.fetch(query, one=True)
        return jsonify(result)
    except Exception as e:
        logger.error(f"统计文章数量失败: {e}")
        return jsonify({"error": "统计失败"}), 500


@article_blueprint.route('/article_id/<int:article_id>')
def get_article(article_id):
    """
    根据文章 ID 获取指定文章的详情，返回 JSON 格式。
    """
    query = 'SELECT * FROM yesapi_bjy_article WHERE aid=%s AND is_show=1 AND is_delete=0'
    try:
        result = mysql_pool.fetch(query, (article_id,), one=True)
        if result:
            return jsonify(result)
        else:
            return jsonify({"error": "文章未找到"}), 404
    except Exception as e:
        logger.error(f"获取文章 {article_id} 失败: {e}")
        return jsonify({"error": "获取文章失败"}), 500


@article_blueprint.route('/category/<int:cid>')
def get_articles_by_category(cid):
    """
    根据分类 ID 获取该分类下的所有可见且未删除的文章。
    """
    query = 'SELECT * FROM yesapi_bjy_article WHERE cid=%s AND is_show=1 AND is_delete=0'
    try:
        result = mysql_pool.fetch(query, (cid,))
        return jsonify(result)
    except Exception as e:
        logger.error(f"获取分类 {cid} 下的文章失败: {e}")
        return jsonify({"error": "获取文章失败"}), 500


@article_blueprint.route('/category_count/<int:cid>')
def count_articles_by_category(cid):
    """
    根据分类 ID 统计该分类下的所有可见且未删除的文章数量。
    """
    query = 'SELECT COUNT(*) as count FROM yesapi_bjy_article WHERE cid=%s AND is_show=1 AND is_delete=0'
    try:
        result = mysql_pool.fetch(query, (cid,), one=True)
        return jsonify(result)
    except Exception as e:
        logger.error(f"统计分类 {cid} 下的文章数量失败: {e}")
        return jsonify({"error": "统计失败"}), 500


@article_blueprint.route('/category_id')
def get_category_id():
    """
    获取所有分类 ID 和对应 yesapi_bjy_article_category的名字 。
    """
    query = 'SELECT cid, category_name FROM yesapi_bjy_article_category'
    try:
        result = mysql_pool.fetch(query, one=False)
        return jsonify(result)
    except Exception as e:
        logger.error(f"获取分类 ID 失败: {e}")
        return jsonify({"error": "获取分类失败"}), 500


@article_blueprint.route('/categories_with_count')
def get_categories_with_count():
    """
    获取所有分类及其对应的文章数量。
    """
    query = '''
        SELECT c.cid, c.category_name, COUNT(a.aid) as article_count
        FROM yesapi_bjy_article_category c
        LEFT JOIN yesapi_bjy_article a ON c.cid = a.cid AND a.is_show = 1 AND a.is_delete = 0
        GROUP BY c.cid, c.category_name
    '''
    try:
        result = mysql_pool.fetch(query, one=False)
        return jsonify(result)
    except Exception as e:
        logger.error(f"获取分类及文章数量失败: {e}")
        return jsonify({"error": "获取数据失败"}), 500


@article_blueprint.route('/get_hot_articles')
def get_hot_articles():
    """
    获取热门文章
    """
    query = 'SELECT * FROM yesapi_bjy_article WHERE is_show=1 AND is_delete=0 ORDER BY click DESC LIMIT 5'
    try:
        result = mysql_pool.fetch(query, one=False)
        return jsonify(result)
    except Exception as e:
        logger.error(f"获取热门文章失败: {e}")
        return jsonify({"error": "获取数据失败"}), 500


@article_blueprint.route('/update_click/<int:article_id>', methods=['POST'])
def update_click(article_id):
    """
    更新文章点击量
    """
    query = 'UPDATE yesapi_bjy_article SET click = click + 1 WHERE aid=%s'
    try:
        mysql_pool.execute(query, (article_id,))
        # 不需要手动提交，因为已设置自动提交
        return jsonify({"success": True})
    except Exception as e:
        logger.error(f"更新文章 {article_id} 点击量失败: {e}")
        return jsonify({"error": "更新失败"}), 500


@article_blueprint.route('/get_prev_next/<int:aid>', methods=['GET'])
def get_prev_next(aid):
    """
    根据当前文章 ID 获取上一篇和下一篇文章的标题和图片 URL。
    """
    try:
        # 获取上一篇文章
        prev_query = '''
            SELECT aid, title, image_url FROM yesapi_bjy_article
            WHERE aid < %s AND is_show=1 AND is_delete=0
            ORDER BY aid DESC LIMIT 1
        '''
        prev_article = mysql_pool.fetch(prev_query, (aid,), one=True)

        # 获取下一篇文章
        next_query = '''
            SELECT aid, title, image_url FROM yesapi_bjy_article
            WHERE aid > %s AND is_show=1 AND is_delete=0
            ORDER BY aid LIMIT 1
        '''
        next_article = mysql_pool.fetch(next_query, (aid,), one=True)

        # 构建响应数据
        response = {
            'prev': prev_article if prev_article else {
                'title': '没有上一篇文章',
                'image_url': 'https://pic.pngsucai.com/00/87/79/cc52e84e1fede602.webp'
            },
            'next': next_article if next_article else {
                'title': '没有下一篇文章',
                'image_url': 'https://pic.pngsucai.com/00/87/79/cc52e84e1fede602.webp'
            }
        }

        return jsonify(response)

    except Exception as e:
        logger.error(f"获取上一篇和下一篇文章时出错: {e}")
        return jsonify({'error': '服务器内部错误'}), 500


@article_blueprint.route('/get_recent_articles', methods=['GET'])
def get_recent_articles():
    """
    获取最近更新的文章
    :return:
    """
    query = '''
        SELECT aid, title, image_url, update_time, cid 
        FROM yesapi_bjy_article 
        WHERE is_show=1 AND is_delete=0 
        ORDER BY update_time DESC 
        LIMIT 3
    '''
    try:
        result = mysql_pool.fetch(query, one=False)
        # 使用 jsonify 返回 JSON 响应
        return jsonify({"success": True, "data": result}), 200
    except Exception as e:
        logger.error(f"获取最近更新的文章失败: {e}")
        return jsonify({"success": False, "error": "获取数据失败"}), 500


@article_blueprint.route('/get_category_articles/<int:cid>', methods=['GET'])
def get_category_articles(cid):
    """
    根据分类 ID 获取该分类下的所有文章
    """
    query = """
    SELECT 
        a.aid, 
        a.title, 
        a.author, 
        a.update_time, 
        a.image_url, 
        a.click, 
        a.description, 
        c.category_name AS category_name
    FROM 
        yesapi_bjy_article a
    JOIN 
        yesapi_bjy_article_category c ON a.cid = c.cid
    WHERE 
        a.cid = %s AND 
        a.is_show = 1 AND 
        a.is_delete = 0
    """
    try:
        result = mysql_pool.fetch(query, (cid,))
        return jsonify(result)
    except Exception as e:
        logger.error(f"获取分类 {cid} 下的文章失败: {e}")
        return jsonify({"error": "获取文章失败"}), 500

@article_blueprint.route('fuzzy_search/<string:keyword>', methods=['GET'])
def fuzzy_search(keyword):
    """
    根据关键词进行模糊搜索
    """
    query = """
    SELECT 
        aid, 
        title, 
        author, 
        update_time, 
        image_url, 
        click, 
        description
    FROM 
        yesapi_bjy_article
    WHERE 
        title LIKE %s  or keywords LIKE %s AND
        is_show = 1 AND 
        is_delete = 0
    """
    try:
        result = mysql_pool.fetch(query, (f'%{keyword}%', f'%{keyword}%'))
        return jsonify(result)
    except Exception as e:
        logger.error(f"搜索关键词 {keyword} 失败: {e}")
        return jsonify({"error": "搜索失败"}), 500


# 获取文章作者的用户ID
@article_blueprint.route('/get_author_id/<int:aid>', methods=['GET'])
def get_author_id(aid):
    """
    根据文章ID获取文章作者的用户ID
    """
    query = 'SELECT auth_id FROM yesapi_bjy_article WHERE aid=%s'
    try:
        result = mysql_pool.fetch(query, (aid,), one=True)
        return jsonify(result)
    except Exception as e:
        logger.error(f"获取文章作者ID失败: {e}")
        return jsonify({"error": "获取数据失败"}), 500


# 删除文章
@article_blueprint.route('/delete_article/<int:aid>', methods=['POST'])
@token_required
def delete_article(aid):
    """
    根据文章ID删除文章
    """
    query = 'UPDATE yesapi_bjy_article SET is_delete=1 WHERE aid=%s'
    try:
        mysql_pool.execute(query, (aid,))
        return jsonify({"success": True})
    except Exception as e:
        logger.error(f"删除文章 {aid} 失败: {e}")
        return jsonify({"error": "删除失败"}), 500

# 更新文章
@article_blueprint.route('/update_article', methods=['POST'])
@token_required
def update_article(current_user):
    """
    更新文章，包括文章内容、标签、描述、图片以及附件的处理。
    """
    try:
        # 获取表单数据
        aid = request.form.get('aid')
        title = request.form.get('title')
        keywords = request.form.get('keywords')
        content = request.form.get('content')
        description = request.form.get('description')

        # 验证和保存上传的图片文件
        image_url = None
        image = request.files.get('uphold_img')
        if image:
            image_path, error = save_file(image, UPLOAD_FOLDER, is_check=True)
            if error:
                return jsonify({"error": error}), 400  # 文件保存失败，返回错误信息
            image_url = f"http://localhost:8080/{image_path}"

        # 验证并处理附件文件
        # 处理附件文件
        attachments = request.files.getlist('attachments[]')
        attachment_names = request.form.getlist('attachment_names[]')  # 获取文件名称
        attachment_sizes = request.form.getlist('attachment_sizes[]')  # 获取文件大小
        attachment_urls = []

        for i, attachment in enumerate(attachments):
            if attachment:
                attachment_path, error = save_file(attachment, app.config['UPLOAD_FILE_FOLDER'])
                if error:
                    return jsonify({"error": f"附件上传失败: {error}"}), 400
                attachment_url = f"http://localhost:8080/{attachment_path}"
                attachment_name = attachment_names[i] if i < len(attachment_names) else '未知文件'
                attachment_size = attachment_sizes[i] if i < len(attachment_sizes) else 0
                attachment_urls.append({
                    "url": attachment_url,
                    "name": attachment_name,
                    "size": attachment_size
                })

        # 将附件信息保存到数据库
        upload_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        for attachment in attachment_urls:
            insert_attachment_query = '''
                INSERT INTO article_attachments (aid, attachment_url, attachment_name, size, upload_time)
                VALUES (%s, %s, %s, %s, %s)
            '''
            mysql_pool.execute(insert_attachment_query,
                               (aid, attachment['url'], attachment['name'], attachment['size'], upload_time))

        if image_url:  # 如果 image_url 不为空
            update_query = '''
                UPDATE yesapi_bjy_article
                SET title=%s, keywords=%s, content=%s, description=%s, image_url=%s, update_time=NOW()
                WHERE aid=%s
            '''
            update_params = (title, keywords, content, description, image_url, aid)
        else:
            update_query = '''
                UPDATE yesapi_bjy_article
                SET title=%s, keywords=%s, content=%s, description=%s, update_time=NOW()
                WHERE aid=%s
            '''
            update_params = (title, keywords, content, description, aid)

        mysql_pool.execute(update_query, update_params)
        return jsonify({"result": "success"}), 200

    except Exception as e:
        # 捕获异常并返回错误信息
        return jsonify({"error": f"更新文章失败: {str(e)}"}), 500



# 获取指定文章的附件
@article_blueprint.route('/get_attachments/<int:aid>', methods=['GET'])
def get_attachments(aid):
    query = 'SELECT id, attachment_url, attachment_name, size FROM article_attachments WHERE aid=%s'
    try:
        result = mysql_pool.fetch(query, (aid,), one=False)
        return jsonify(result)
    except Exception as e:
        logger.error(f"获取文章 {aid} 的附件失败: {e}")
        return jsonify({"error": "获取数据失败"}), 500



# 删除文章的附件
@article_blueprint.route('/delete_attachment/<int:attachment_id>', methods=['DELETE'])
def delete_attachment(attachment_id):
    """
    删除指定ID的附件
    """
    try:
        # 在日志中记录删除操作的 attachment_id
        print(f"准备删除附件，ID: {attachment_id}")

        # 执行删除操作
        delete_query = 'DELETE FROM article_attachments WHERE id = %s'
        rows_affected = mysql_pool.execute(delete_query, (attachment_id,))

        # 检查是否有记录被删除
        if rows_affected == 0:
            logger.warning(f"附件 {attachment_id} 不存在，删除失败")
            return jsonify({"error": "附件不存在"}), 404

        print(f"附件 {attachment_id} 删除成功")
        return jsonify({"result": "success"}), 200

    except Exception as e:
        print(f"删除附件失败: {str(e)}")
        return jsonify({"error": f"删除附件失败: {str(e)}"}), 500

import uuid
import time

@article_blueprint.route('/add_article', methods=['POST'])
@token_required
def add_article(current_user_id):
    try:
        # 根据用户ID查询用户信息
        query_user = "SELECT username FROM users WHERE id = %s"
        user_result = mysql_pool.fetch(query_user, (current_user_id,))

        if not user_result:
            return jsonify({"error": "用户不存在"}), 404

        current_user_username = user_result[0]['username']  # 获取用户名

        # 获取表单数据
        title = request.form.get('title')
        keywords = request.form.get('keywords')
        description = request.form.get('description')
        content = request.form.get('content')
        category_id = request.form.get('category_id')  # 获取分类ID

        # 验证必要字段是否存在
        if not all([title, keywords, content]):
            return jsonify({"error": "缺少必要的字段"}), 400

        # 生成一个长度不超过10的唯一aid
        aid = generate_numeric_uuid()

        # 保存文章封面图片
        cover_image = request.files.get('coverImage')
        cover_image_url = None
        if cover_image:
            cover_image_path, error = save_file(cover_image, app.config['UPLOAD_FOLDER'])
            if error:
                return jsonify({"error": f"封面图片上传失败: {error}"}), 400
            cover_image_url = f"http://localhost:8080/{cover_image_path}"

        # 保存文章到数据库
        insert_article_query = '''
            INSERT INTO yesapi_bjy_article (aid, title, keywords, description, content, addtime, author, auth_id, cid, image_url) 
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        '''
        addtime = int(time.time())  # 获取当前Unix时间戳
        params = (aid, title, keywords, description, content, addtime, current_user_username, current_user_id, category_id, cover_image_url)
        mysql_pool.execute(insert_article_query, params)

        # 返回成功响应
        return jsonify({"result": "文章发布成功", "article_id": aid, "cover_image_url": cover_image_url}), 200

    except Exception as e:
        print(f"发布文章失败，错误信息：{str(e)}")
        return jsonify({"error": f"发布文章失败: {str(e)}"}), 500




# 辅助函数，用于生成唯一 aid
def generate_numeric_uuid():
    return str(abs(hash(uuid.uuid4())) % (2**31 - 1))  # 2147483647 是 INT 的最大值









