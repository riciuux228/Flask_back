# 测试connection.py中的函数
from connect_mysql import MysqlPool


# 测试连接池
def test_pool():
    with MysqlPool() as pool:
        cursor = pool.get_cursor()
        cursor.execute('select * from yesapi_bjy_article')
        print(cursor.fetchall())


# 测试fetch_all
def test_fetch_all():
    with MysqlPool() as pool:
        print(pool.fetch_all('select * from yesapi_bjy_article'))


# 测试fetch_one
def test_fetch_one():
    with MysqlPool() as pool:
        print(pool.fetch_one('select * from yesapi_bjy_article'))


# # 测试execute
# def test_execute():
#     with MysqlPool() as pool:
#         print(pool.execute('insert into user values (null, "test", "test")'))
#         pool.commit()

if __name__ == '__main__':
    # test_pool()
    test_fetch_all()
    # test_fetch_one()
# test_execute()
