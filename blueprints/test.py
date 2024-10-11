import requests


# 测试注册功能
def test_register():
    data ={
        "username": "test_user2",
        "phone": "12345678903",
        "password": "123456",
        "role": "author"
    }
    response = requests.post('http://localhost:8080/user/register', json=data)
    print(response.json())

test_register()

