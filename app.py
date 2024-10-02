from flask import Flask
from flask_cors import CORS


from blueprints.article import article_blueprint  # 导入蓝图实例
from blueprints.user import user_blueprint  # 导入蓝图实例

app = Flask(__name__)
# 为整个app启用CORS
CORS(app, resources={r"/*": {"origins": "*"}})  # 允许所有来源
# 启用CORS
CORS(user_blueprint, resources={r"/*": {"origins": "*"}})  # 允许所有源访问
# 注册蓝图
app.register_blueprint(article_blueprint, url_prefix='/article')
app.register_blueprint(user_blueprint, url_prefix='/user')
print(app.url_map) # 打印所有的路由，检查是否有冲突或遗漏

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=8080)
    # 在启动应用时打印所有的路由，检查是否有冲突或遗漏

