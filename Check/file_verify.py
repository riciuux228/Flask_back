import os
import uuid
from werkzeug.utils import secure_filename

# 定义允许上传的文件扩展名
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}


def allowed_file(filename):
    """检查文件是否为允许的扩展名"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def save_file(file, upload_folder, is_check=False):
    """
    保存文件的通用方法
    :param file: 上传的文件对象
    :param upload_folder: 文件保存的文件夹路径
    :return: 文件保存后的URL路径或错误信息
    """
    # 检查文件是否符合要求

    if is_check:
        if file and allowed_file(file.filename):
            # 生成唯一文件名
            unique_filename = f"{uuid.uuid4()}.{file.filename.rsplit('.', 1)[1].lower()}"
            file_path = os.path.join(upload_folder, secure_filename(unique_filename))

            try:
                # 保存文件到指定路径
                file.save(file_path)
                # 返回文件的保存路径或URL
                return file_path, None
            except Exception as e:
                return None, str(e)
        else:
            return None, "文件格式不支持"
    else:
        unique_filename = f"{uuid.uuid4()}.{file.filename.rsplit('.', 1)[1].lower()}"
        file_path = os.path.join(upload_folder, secure_filename(unique_filename))

        try:
            # 保存文件到指定路径
            file.save(file_path)
            # 返回文件的保存路径或URL
            return file_path, None
        except Exception as e:
            return None, str(e)
