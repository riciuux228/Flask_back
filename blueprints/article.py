from SqlManage.connect_mysql import MysqlPool
from flask import Blueprint, jsonify
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    filename='article.py.log',
    filemode='w',
    encoding='utf-8'
)
logger = logging.getLogger(__name__)

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
            ORDER BY aid ASC LIMIT 1
        '''
        next_article = mysql_pool.fetch(next_query, (aid,), one=True)

        # 构建响应数据
        response = {
            'prev': prev_article if prev_article else {
                'title': '没有上一篇文章',
                'image_url': ''
            },
            'next': next_article if next_article else {
                'title': '没有下一篇文章',
                'image_url': ''
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
