import telnetlib
from threading import Thread
from tornado.concurrent import run_on_executor
from tornado.ioloop import IOLoop
import json
import time
import traceback
from channels.generic.websocket import WebsocketConsumer
import os
import json
import base64
import re
import tornado.web
from webssh.handler import MixinHandler
import asyncio
class SendClientMessage(Thread):
    def __init__(self, websocker,message):
        self.websocker = websocker
        self.message = message
        asyncio.set_event_loop(asyncio.new_event_loop())
        loop = asyncio.get_event_loop()
        loop.run_until_complete(self.send_data(message))
        loop.close()

    async def send_data(self, message):
        await self.websocker.write_message(message)  # 调用回调函数发送后端消息给前端

class TelnetClient:
    """
    由于 telnetlib 库的原因，终端无法显示颜色以及设置终端大小
    """
    def __init__(self, websocker, message):
        self.websocker = websocker
        self.message = message
        self.cmd = ''
        self.res = ''
        self.tn = telnetlib.Telnet()

    def connect(self, host, user, password, port=23, timeout=30):
        try:
            self.tn.open(host=host, port=port, timeout=timeout)
            self.tn.read_until(b'login: ', timeout=30)
            user = '{0}\n'.format(user).encode('utf-8')
            self.tn.write(user)

            self.tn.read_until(b'Password: ', timeout=30)
            password = '{0}\n'.format(password).encode('utf-8')
            self.tn.write(password)

            time.sleep(0.5)     # 服务器响应慢的话需要多等待些时间
            command_result = self.tn.read_very_eager().decode('utf-8')

            self.message['status'] = 0
            self.message['message'] = command_result

            message = json.dumps(self.message)
            self.websocker.write_message(message)
            
            self.res += command_result
            if 'Login incorrect' in command_result:
                self.message['status'] = 2
                self.message['message'] = 'connection login faild...'
                message = json.dumps(self.message)
                self.websocker.write_message(message)
                self.websocker.close(3001)
            self.tn.write(b'export TERM=ansi\n')
            time.sleep(0.2)
            self.tn.read_very_eager().decode('utf-8')
            # 创建1线程将服务器返回的数据发送到django websocket, 多个的话会极容易导致前端显示数据错乱
            Thread(target=self.websocket_to_django).start()
        except Exception as e:
            print(traceback.format_exc())
            self.message['status'] = 2
            self.message['message'] = 'connection faild...'
            message = json.dumps(self.message)
            self.websocker.write_message(message)
            self.websocker.close(3001)

    def django_to_ssh(self, data):
        try:
            self.tn.write(data.encode('utf-8'))
            if data == '\r':
                data = '\n'
            self.cmd += data
        except:
            self.close()
    
    def websocket_to_django(self):
        try:
            while True:
                data = self.tn.read_very_eager().decode('utf-8')
                if not len(data):
                    continue
                self.message['status'] = 0
                self.message['message'] = data
                self.res += data
                message = json.dumps(self.message)
                self.websocker.mode = IOLoop.WRITE

                SendClientMessage(self.websocker,message)
                
        except Exception as e:
            print(e)
            self.close()

    def close(self):
        try:
            self.message['status'] = 1
            self.message['message'] = 'connection closed...'
            message = json.dumps(self.message)
            self.websocker.write_message(message)
            self.websocker.close()
            self.tn.close()
        except:
            pass

    def shell(self, data):
        self.django_to_ssh(data)
        #return self.websocket_to_django2()




class TelnetHandler(MixinHandler,tornado.websocket.WebSocketHandler):
    # 保存连接的用户，用于后续推送消息
    connect_users = set()
    message = {'status': 0, 'message': None}
    def initialize(self, loop):
        super(TelnetHandler, self).initialize(loop)
    def open(self):
        print("WebSocket opened")
        host = self.get_argument('host')
        port = int(self.get_argument('port'))
        user = self.get_argument('user')
        passwd = base64.b64decode(self.get_argument('password')).decode('utf-8')

        self.telnet = TelnetClient(websocker=self, message=self.message)
        telnet_connect_dict = {
            'host': host,
            'user': user,
            'port': port,
            'password': passwd,
            'timeout': 30,
        }
        self.telnet.connect(**telnet_connect_dict)
        # 打开连接时将用户保存到connect_users中
        self.connect_users.add(self)
    
    def on_message(self, message):
        print('收到的信息为：' + message)
        data = json.loads(message)
        if type(data) == dict:
            status = data['status']
            if status == 0:
                data = data['data']
                self.telnet.shell(data)
            else:
                pass
    
    @tornado.gen.coroutine
    def write_message(self,message):
        super(TelnetHandler,self).write_message(message)
        print(message)
        
    def on_close(self):
        print("WebSocket closed")
        # 关闭连接时将用户从connect_users中移除
        self.connect_users.remove(self)
        self.telnet.close()

    def check_origin(self, origin):
        # 此处用于跨域访问
        return True