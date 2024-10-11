import logging

from flask import Blueprint, jsonify, request

from SqlManage.connect_mysql import MysqlPool

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(ascTime)s - %(levelName)s - %(message)s',
    filename='comments.py.log',
    filemode='w',
    encoding='utf-8'
)
logger = logging.getLogger(__name__)

# 定义文章蓝图
comments_blueprint = Blueprint('comments', __name__, template_folder='templates')

mysql_pool = MysqlPool()  # 初始化连接池

# 获取评论
@comments_blueprint.route('/<int:article_id>')
def get_comments(article_id):
    """
    根据文章 ID 获取指定文章的评论，返回 JSON 格式。
    JSON 需要包含评论的 ID、父级评论 ID、评论内容、评论时间、评论用户的用户头像url、评论用户的用户名、评论用户的用户 ID。
    用户信息需要从users表中获取。

    """
    # 需要多表查询，获取评论用户的用户头像url、评论用户的用户名、评论用户的用户 ID
    query = 'SELECT c.*, u.user_icon_url, u.username ,u.role FROM comments c ' \
            'LEFT JOIN users u ON c.user_id=u.id ' \
            'WHERE article_id=%s ORDER BY c.like_count DESC'
    try:
        result = mysql_pool.fetch(query, (article_id,), one=False)
        return jsonify(result)  # 使用 jsonify 直接返回 Python 数据
    except Exception as e:
        logger.error(f"获取评论失败: {e}")
        return jsonify({"error": "获取评论失败"}), 500


# 统计评论数量
@comments_blueprint.route('/count/<int:article_id>')
def count_comments(article_id):
    """
    统计指定文章的评论数量。
    """
    query = 'SELECT COUNT(*) as count FROM comments WHERE article_id=%s'
    try:
        result = mysql_pool.fetch(query, (article_id,), one=True)
        return jsonify(result)
    except Exception as e:
        logger.error(f"统计评论数量失败: {e}")
        return jsonify({"error": "统计失败"}), 500


# 添加评论
@comments_blueprint.route('/add', methods=['POST'])
def add_comment():
    """
    添加评论
    :return:
    """
    article_id = request.form.get('article_id')
    user_id = request.form.get('user_id')
    parent_comment_id = request.form.get('parent_comment_id')
    content = request.form.get('content')

    # 检查必填参数
    if parent_comment_id == "null":
        parent_comment_id = None
    print(f"article_id: {article_id}, user_id: {user_id}, parent_comment_id: {parent_comment_id}, content: {content}")
    if not all([article_id, user_id, content]):
        return jsonify({"error": "参数不完整"}), 400

    # 插入评论
    query = 'INSERT INTO comments(article_id, user_id, parent_comment_id, content) VALUES (%s, %s, %s, %s)'
    try:
        mysql_pool.execute(query, (article_id, user_id, parent_comment_id, content))
        return jsonify({"result": "success"}), 200
    except Exception as e:
        logger.error(f"添加评论失败: {e}")
        return jsonify({"error": "添加评论失败"}), 500

# 为评论点赞
@comments_blueprint.route('/add_like', methods=['POST'])
def add_like():
    """
    为评论点赞
    :return:
    """
    comment_id = request.form.get('comment_id')

    # 检查必填参数
    if not comment_id:
        return jsonify({"error": "参数不完整"}), 400

    # 更新评论的点赞数
    update_query = 'UPDATE comments SET like_count = like_count + 1 WHERE id=%s'
    select_query = 'SELECT like_count FROM comments WHERE id=%s'
    try:
        mysql_pool.execute(update_query, (comment_id,))
        result = mysql_pool.fetch(select_query, (comment_id,), one=True)
        return jsonify(result)
    except Exception as e:
        logger.error(f"点赞失败: {e}")
        return jsonify({"error": "点赞失败"}), 500

# 取消评论点赞
@comments_blueprint.route('/add_dislike', methods=['POST'])
def add_dislike():
    """
    取消评论点赞
    :return:
    """
    comment_id = request.form.get('comment_id')

    # 检查必填参数
    if not comment_id:
        return jsonify({"error": "参数不完整"}), 400

    # 更新评论的点赞数
    update_query = 'UPDATE comments SET like_count = like_count - 1 WHERE id=%s'
    select_query = 'SELECT like_count FROM comments WHERE id=%s'
    try:
        mysql_pool.execute(update_query, (comment_id,))
        result = mysql_pool.fetch(select_query, (comment_id,), one=True)
        return jsonify(result)
    except Exception as e:
        logger.error(f"取消点赞失败: {e}")
        return jsonify({"error": "取消点赞失败"}), 500


