#https://github.com/sagemath/sagecell/blob/master/contrib/sagecell-client/sagecell-client.py
"""
A small client illustrating how to interact with the Sage Cell Server, version 2
Requires the websocket-client package: http://pypi.python.org/pypi/websocket-client
Websocker client repo: https://github.com/websocket-client/websocket-client
"""

import websocket
import json
import requests
import random

import warnings

from uuid import uuid4


import threading
import time

import json
import pprint
import sseclient

from IPython.utils import capture
import IPython

from json.decoder import JSONDecodeError 

def with_urllib3(url):
    """Get a streaming response for the given event feed using urllib3."""
    import urllib3
    http = urllib3.PoolManager()
    return http.request('GET', url, preload_content=False)

def with_requests(url):
    """Get a streaming response for the given event feed using requests."""
    import requests
    return requests.get(url, stream=True)

#https://stackoverflow.com/a/19846691/454773
def threaded(fn):
    def wrapper(*args, **kwargs):
        thread = threading.Thread(target=fn, args=args, kwargs=kwargs)
        thread.start()
        return thread
    return wrapper

class MyBinderCell(object):
        
    def __init__(self, binderURL, timeout=10, message='step'):
        response = with_urllib3(binderURL)  # or with_requests(url)
        client = sseclient.SSEClient(response)
        
        for event in client.events():
            msg = json.loads(event.data)
            if message=='full':
                pprint.pprint(msg)
            elif message=='step':
                if msg['message'].startswith(('Step', 'Built image', 'Launching server')):
                    pprint.pprint(msg)
            pass
        
        resp = json.loads(event.data)
        self._binder = resp
        
        randsessionId = random.getrandbits(32)

        r = requests.post('{}api/kernels?{}'.format(resp['url'], randsessionId),
             headers={'Authorization': 'token {}'.format(resp['token'])})
        
        wss = 'wss://{}api/kernels/{}/channels?token={}'.format(resp['url'].split('//')[1],
                                                                    r.json()['id'],
                                                                    resp['token'])

        self.kernel_url = wss
        print(self.kernel_url)
        #websocket.setdefaulttimeout(timeout)
        self._ws = websocket.WebSocket()
        self._ws.connect(wss)
        #The websocketApp connection appears to close?
        #self._ws = websocket.WebSocketApp(wss)
        
        #I think we need to create a heartbeat that pings the server every so often to keep the session alive
        #Will a simple websocket ping do that?
        #The following is DEFINED on .WebSocketApp but that route appears to break connections?
        #self._ws.run_forever(ping_interval=70, ping_timeout=10)
        #Do we also need a hearbeat sent to the Binder server / kernel so it knows our client it still alive?

        
        # initialize our list of messages
        self.shell_messages = []
        self.iopub_messages = []
        
        self.cnt = 0
        self.keep_running = True
        #self.heart = threading.Thread(target=self.keep_alive)
        #self.heart.start()
        self.keep_alive()
        
        
    def _wait_on_response(self, response):
        # Wait until we get both a kernel status idle message and an execute_reply message
        got_execute_reply = False
        got_idle_status = False
        while not (got_execute_reply and got_idle_status):
            msg = json.loads(self._ws.recv())
            if 'broken_pipe' in msg:
                break

            if msg['channel'] == 'shell':
                self.shell_messages.append(msg)
                # an execute_reply message signifies the computation is done
                if msg['header']['msg_type'] == response:
                    got_execute_reply = True
            elif msg['channel'] == 'iopub':
                self.iopub_messages.append(msg)
                # the kernel status idle message signifies the kernel is done
                if (msg['header']['msg_type'] == 'status' and
                    msg['content']['execution_state'] == 'idle'):
                        got_idle_status = True

        return {'shell': self.shell_messages, 'iopub': self.iopub_messages}

    def execute_request(self, code):
        # zero out our list of messages, in case this is not the first request
        self.shell_messages = []
        self.iopub_messages = []

        # Send the JSON execute_request message string down the shell channel
        msg = self._make_execute_request(code)
        try:
            self._ws.send(msg)
            return self._wait_on_response('execute_reply')
        except (BrokenPipeError, JSONDecodeError):
            warnings.warn('Binder kernel connection seems to have died...')
            self.keep_running = False
            return {'broken_pipe':True, 'shell':[], 'iopub':[]}
         
    def _make_execute_request(self, code):
        from uuid import uuid4
        session = str(uuid4())

        # Here is the general form for an execute_request message
        execute_request = {
            'channel': 'shell',
            'header': {
                'msg_type': 'execute_request',
                'msg_id': str(uuid4()), 
                'username': '', 'session': session,
            },
            'parent_header':{},
            'metadata': {},
            'content': {
                'code': code, 
                'silent': False,
                'stop_on_error': False,
                'user_expressions': {}, 
                'allow_stdin': True,
                'store_history': True,
            }
        }
        return json.dumps(execute_request)

    def _make_heartbeat(self):
        session = str(uuid4())
        _heartbeat = {
                'channel': 'heartbeat',
                'header': {
                    'msg_type': 'ping',
                    'msg_id': str(uuid4()), 
                    'username': '',
                    'session': session,
                    'version': "5.2"
                },
                'parent_header':{},
                'metadata': {},
                'content': {}
            }
        return json.dumps(_heartbeat)
    
    def _make_kernel_info_request(self):
        session = str(uuid4())
        kernel_info_request = {
                'channel': 'shell',
                'header': {
                    'msg_type': 'kernel_info_request',
                    'msg_id': str(uuid4()), 
                    'username': '',
                    'session': session,
                    'version': "5.2"
                },
                'parent_header':{},
                'metadata': {},
                'content': {}
            }
        return json.dumps(kernel_info_request)

    def kernel_info__request(self):
        # zero out our list of messages, in case this is not the first request
        self.shell_messages = []
        self.iopub_messages = []

        # Send the JSON execute_request message string down the shell channel
        msg = self._make_kernel_info_request()
        self._ws.send(msg)
        return self._wait_on_response('kernel_info_reply')
    
    def heartbeat_pulse(self):
            # Send the JSON execute_request message string down the heartbeat channel
            msg = self._make_heartbeat()
            
            #Using the new websocket inspector in Firefox against a MyBinder session
            #it looks like an empty message is sent every thirty seconds as the heartbeat
            #presumably just to keep the session alive?

            try:
                self._ws.send(msg)
                self.cnt = self.cnt + 1
                #print(self.cnt) #Keep tabs on how long we've been alive...
            except BrokenPipeError:
                warnings.warn('Binder kernel connection seems to have died...')
                self.keep_running = False
            #Don't bother with waiting for a response?
            #Send msg in try: block instead and say we're dead if we except?
    
    @threaded
    def keep_alive(self):
        while self.keep_running:
            self.heartbeat_pulse()
            time.sleep(30)
    
    def close(self):
        # If we define this, we can use the closing() context manager to automatically close the channels
        self._ws.close()

import urllib.parse

def binder_url(repo):
    '''Get MyBinder build URL from Github repo URL.'''
    
    url = 'https://mybinder.org'
    branch = 'master'

    repo = repo.replace('https://github.com/','').rstrip('/')

    binderURL = '{url}/build/gh/{repo}/{branch}'.format(url=url, repo=repo, branch=branch)

    return binderURL

from IPython.core.magic import magics_class, line_cell_magic, Magics
from IPython.core.magic_arguments import argument, magic_arguments, parse_argstring

@magics_class
class BinderMagic(Magics):
    def __init__(self, shell, cache_display_data=False):
        super(BinderMagic, self).__init__(shell)
        self.repo = None
        self.b = None

    @line_cell_magic
    @magic_arguments()
    @argument('--repo', '-r',
          default=None,
          help='Github repo URL'
    )
    def binder(self, line, cell=''):
        '''Simple example.'''
        
        args = parse_argstring(self.binder, line)
        if args.repo:
            self.repo = args.repo
            binderURL = binder_url(self.repo)
            self.b = MyBinderCell(binderURL, message='step')
            
        if self.b is None:
            print('No connection...')
            return
        
        if cell is None:
            print('Use block magic')
        else:
            #get_ipython().execution_count = 77
            items = self.b.execute_request(cell)
            for item in items['iopub']:
                if item['msg_type']=='execute_result':
                    return capture.RichOutput(data=item['content']['data'], metadata={})
                elif item['msg_type']=='stream':
                    IPython.display.display({'text/plain':item['content']['text']}, raw=True)
                
        
#ip = get_ipython()
#ip.register_magics(BinderMagic)
