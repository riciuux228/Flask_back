import logging

import pymysql
from dbutils.pooled_db import PooledDB

from SqlManage import config

# 配置日志
logging.basicConfig(
    level=logging.DEBUG,  # 修改为 DEBUG 级别，确保所有日志输出
    format='%(asctime)s - %(levelname)s - %(message)s',
    filename='mysql_pool.log',
    filemode='w',
    encoding='utf-8'
)
logger = logging.getLogger(__name__)


class MysqlPool:
    __pool = None

    def __init__(self):
        if not MysqlPool.__pool:
            try:
                MysqlPool.__pool = PooledDB(
                    creator=pymysql,
                    mincached=5,
                    maxcached=100,
                    maxconnections=200,
                    host=config.host,
                    port=config.port,
                    user=config.user,
                    passwd=config.passwd,
                    db=config.db,
                    use_unicode=True,
                    charset=config.charset,
                    blocking=True,  # 如果连接池耗尽，等待而不是抛出错误
                    setsession=['SET AUTOCOMMIT = 1'],  # 设置自动提交，避免长时间占用事务
                )
                logger.info("数据库连接池创建成功")
            except Exception as e:
                logger.error(f"创建连接池失败: {e}")
                raise

    def get_conn(self):
        try:
            conn = self.__pool.connection()
            conn.ping(reconnect=True)  # 检查并重连
            logger.debug("成功获取数据库连接")
            return conn
        except Exception as e:
            logger.error(f"获取数据库连接失败: {e}")
            raise

    def fetch(self, sql, args=None, one=False):
        conn = self.get_conn()
        try:
            with conn.cursor(pymysql.cursors.DictCursor) as cursor:
                logger.info(f"执行查询: {sql}, 参数: {args}")
                cursor.execute(sql, args)
                result = cursor.fetchone() if one else cursor.fetchall()
                logger.info(f"查询结果: {result}")
                return result
        except Exception as e:
            logger.error(f"查询执行失败: {sql}, 错误: {e}")
            raise
        finally:
            conn.close()
            logger.debug("数据库连接已关闭")

    def execute(self, sql, args=None):
        conn = self.get_conn()
        try:
            with conn.cursor() as cursor:
                logger.info(f"执行命令: {sql}, 参数: {args}")
                result = cursor.execute(sql, args)
                conn.commit()
                logger.info(f"执行成功，影响行数: {result}")
                return result
        except Exception as e:
            logger.error(f"执行命令失败: {sql}, 错误: {e}")
            conn.rollback()
            raise
        finally:
            conn.close()
            logger.debug("数据库连接已关闭")