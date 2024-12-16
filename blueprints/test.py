import socket

def get_local_ip():
    """ 获取本机的局域网IP地址 """
    try:
        # 通过UDP连接来获取本机IP地址（无需实际连接）
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))  # 使用Google的DNS服务器来获取本地IP
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception as e:
        return "无法获取本机IP地址: " + str(e)

if __name__ == '__main__':
    print(get_local_ip())