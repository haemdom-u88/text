import requests

# 请根据实际服务端口调整
BASE_URL = 'http://127.0.0.1:5000'
API = '/api/upload_extract_and_graph'

# 测试用txt文件路径
TEST_FILE = 'data/sample.txt'

def test_upload_extract_and_graph():
    with open(TEST_FILE, 'rb') as f:
        files = {'file': f}
        resp = requests.post(BASE_URL + API, files=files)
        print('Status:', resp.status_code)
        try:
            data = resp.json()
            print('Response:', data)
            assert data['success']
            assert 'graph' in data and 'nodes' in data['graph']
            print('Test passed!')
        except Exception as e:
            print('Test failed:', e)

if __name__ == '__main__':
    test_upload_extract_and_graph()
