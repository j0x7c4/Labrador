# encoding: utf-8
'''
新浪微博的登录及cookie处理，来自爬盟, 部分修改
'''

from common import SOFT_PATH, write_message
from pyquery import PyQuery as pq
from rsa import transform
import StringIO
import base64
import contextlib
import cookielib
import datetime
import gzip
import json
import os
import random
import re
import rsa
import settings
import socket
import time
import urllib
import urllib2

socket.setdefaulttimeout(10)

class ComWeiboFetcher(object):
    n_connections = 0

    def __init__(self, **kwargs):
        self.cj = cookielib.LWPCookieJar()
        self.cookie_support = urllib2.HTTPCookieProcessor(self.cj)
        self.opener = urllib2.build_opener(self.cookie_support,
                                           urllib2.HTTPHandler)
        urllib2.install_opener(self.opener)

        self.soft_path = SOFT_PATH
        self.cookie_file = os.path.join(self.soft_path, 'cookie.txt')

        self.proxy_ip = kwargs.get('proxy_ip', None)

        self.username = kwargs.get('username', None)
        self.password = kwargs.get('password', None)

        self.window = kwargs.get('window', None)

        self.pcid = ''
        self.servertime = ''
        self.nonce = ''
        self.pubkey = ''
        self.rsakv = ''

    def gzip_data(self, data):
        if 0 == len(data) or data is None:
            return data

        data = StringIO.StringIO(data)
        data = gzip.GzipFile(fileobj=data).read()

        return data

    def urlopen_read(self, req):
        tries = 10

        for i in range(tries):
            try:
                self.n_connections += 1

                page = None
                with contextlib.closing(urllib2.urlopen(req)) as resp:
                    if resp.info().get('Content-Encoding') == 'gzip':
                        page = self.gzip_data(resp.read())
                    else:
                        page = resp.read()

                if '$CONFIG' in page and not ("$CONFIG['islogin'] = '1'" in page or
                                                      "$CONFIG['islogin']='1'" in page):
                    print 'Not login, try to login'
                    if not self.check_cookie():
                        msg = 'Error in urlopen_read. Login failed.'
                        write_message(msg, self.window)

                        return None
                else:
                    return page
            except Exception, e:
                if i < tries - 1:
                    sec = (i + 1) * 5
                    msg = ('Error in urlopen_read. Take a rest: %s seconds, and retry.'
                           % sec)
                    write_message(msg, self.window)

                    time.sleep(sec)
                else:
                    msg = 'Exit incorrect. %s' % str(e)
                    #logger.info(msg)
                    write_message(msg, self.window)

                    return None

    def get_milli_time(self):
        pre = str(int(time.time()))
        pos = str(datetime.datetime.now().microsecond)[:3]

        return pre + pos

    def get_domain(self, url):
        domain = ''

        p = re.compile(r'http[s]?://([^/]+)/', re.U | re.M)
        m = p.search(url)

        if (m and m.lastindex > 0):
            domain = m.group(1)

        return domain

    def get_headers(self, url, user_agent=''):
        headers = {}
        headers['Host'] = self.get_domain(url)

        if user_agent:
            headers['User-Agent'] = user_agent
        else:
            headers['User-Agent'] = ('Mozilla/5.0 (X11; Linux i686; rv:18.0)'
                                     ' Gecko/20100101 Firefox/18.0')
        headers['Accept'] = ('text/html,application/xhtml+xml,application/xml;'
                             'q=0.9,*/*;q=0.8')
        headers['Accept-Language'] = 'zh-cn,zh;q=0.8,en-us;q=0.5,en;q=0.3'
        headers['Accept-encoding'] = 'gzip, deflate'
        headers['Connection'] = 'keep-alive'
        #headers['Keep-Alive'] = '9000'

        return headers

    def pack_request(self, url='', headers={}, data=None):
        if data:
            headers['Content-Type'] = ('application/x-www-form-urlencoded;'
                                       ' charset=utf-8')
            data = urllib.urlencode(data)

        req = urllib2.Request(url=url, data=data, headers=headers)

        proxy_ip = self.proxy_ip
        if proxy_ip and '127.0.0.1' not in proxy_ip:
            if proxy_ip.startswith('http'):
                proxy_ip = proxy_ip.replace('http://', '')
            req.set_proxy(proxy_ip, 'http')

        return req

    def get_servertime(self):
        url = ('http://login.sina.com.cn/sso/prelogin.php?entry=account'
               '&callback=sinaSSOController.preloginCallBack&su=&rsakt=mod'
               '&client=ssologin.js(v1.4.5)&_=%s' % self.get_milli_time())

        headers = self.get_headers(url)
        headers['Accept'] = '*/*'
        headers['Referer'] = 'http://weibo.com/'
        del headers['Accept-encoding']

        result = {}
        req = self.pack_request(url, headers)

        for _ in range(3):
            data = None

            try:
                with contextlib.closing(urllib2.urlopen(req)) as resp:
                    data = resp.read()

                p = re.compile('\((.*)\)')

                json_data = p.search(data).group(1)
                data = json.loads(json_data)

                result['servertime'] = str(data['servertime'])
                result['nonce'] = data['nonce']
                result['rsakv'] = str(data['rsakv'])
                result['pubkey'] = str(data['pubkey'])
                self.pcid = str(data['pcid'])
                break
            except Exception, e:
                msg = 'Get severtime error. %s' % str(e)
                #logger.info(msg)
                write_message(msg, self.window)

        return result

    def get_global_id(self):
        '''
        get sina session id
        '''

        url = 'http://beacon.sina.com.cn/a.gif'
        headers = self.get_headers(url)
        headers['Accept'] = 'image/png,image/*;q=0.8,*/*;q=0.5'
        headers['Referer'] = 'http://weibo.com/'

        req = self.pack_request(url, headers)
        self.urlopen_read(req)

    def get_random_nonce(self, range_num=6):
        nonce = ''
        for _ in range(range_num):
            nonce += random.choice('QWERTYUIOPASDFGHJKLZXCVBNM1234567890')

        return nonce

    def dec2hex(self, string_num):
        base = [str(x) for x in range(10)] + [chr(x) for x in range(ord('A'),
                                                                    ord('A') + 6)]
        num = int(string_num)
        mid = []
        while True:
            if num == 0: break
            num, rem = divmod(num, 16)
            mid.append(base[rem])

        return ''.join([str(x) for x in mid[::-1]])

    def get_pwd(self, pwd, servertime, nonce):
        p = int(self.pubkey, 16)
        pub_key = rsa.PublicKey(p, int('10001', 16))
        pwd = '%s\t%s\n%s' % (servertime, nonce, pwd)
        pwd = (self.dec2hex(transform.bytes2int(rsa.encrypt(pwd.encode('utf-8'),
                                                            pub_key))))

        return pwd

    def get_user(self, username):
        username = urllib.quote(username)
        username = base64.encodestring(username)[:-1]

        return username

    def save_verify_code(self, url):
        try:
            cookie_str = ''
            for cookie in self.cj.as_lwp_str(True, True).split('\n'):
                cookie = cookie.split(';')[0]
                cookie = cookie.replace('\"', '').replace('Set-Cookie3: ', ' ').strip() + ';'
                cookie_str += cookie

            headers = self.get_headers(url)
            headers['Accept'] = 'image/png,image/*;q=0.8,*/*;q=0.5'
            headers['Referer'] = 'http://weibo.com/'
            headers['Cookie'] = cookie_str
            del headers['Accept-encoding']

            req = self.pack_request(url, headers)
            content = self.urlopen_read(req)

            f = open(os.path.join(self.soft_path, 'pin.png'), 'wb')
            f.write(content)
            f.flush()
            f.close()
        except Exception, e:
            msg = 'Save verify code error. %s' % str(e)
            #logger.info(msg)
            write_message(msg, self.window)

            return

    def do_login(self, login_user, login_pwd, door=''):
        login_ok = False

        try:
            username = login_user
            pwd = login_pwd

            url = 'http://login.sina.com.cn/sso/login.php?client=ssologin.js(v1.4.5)'

            postdata = {
                'entry': 'weibo',
                'gateway': '1',
                'from': '',
                'savestate': '7',
                'userticket': '1',
                'pagerefer': '',
                'ssosimplelogin': '1',
                'vsnf': '1',
                'vsnval': '',
                'service': 'miniblog',
                'pwencode': 'rsa2',
                'rsakv': self.rsakv,
                'encoding': 'utf-8',
                'url': 'http://weibo.com/ajaxlogin.php?framelogin=1&callback=parent.sinaSSOController.feedBackUrlCallBack',
                'returntype': 'META',
                'prelt': '26',
            }
            postdata['servertime'] = self.servertime
            postdata['nonce'] = self.nonce
            postdata['su'] = self.get_user(username)
            postdata['sp'] = self.get_pwd(pwd, self.servertime, self.nonce).lower()

            #当需要验证码登录的时候
            if door:
                postdata['pcid'] = self.pcid
                postdata['door'] = door.lower()

            headers = self.get_headers(url)
            headers['Referer'] = 'http://weibo.com/'

            req = self.pack_request(url, headers, postdata)

            text = self.urlopen_read(req)
            return text
        except Exception, e:
            msg = 'Error in do_login. %s' % str(e)
            #logger.info(msg)
            write_message(msg, self.window)

        return login_ok

    def redo_login(self, login_url):
        login_ok = False

        try:
            headers = self.get_headers(login_url)
            headers['Referer'] = 'http://login.sina.com.cn/sso/login.php?client=ssologin.js(v1.4.5)'

            req = self.pack_request(login_url, headers)
            if self.urlopen_read(req) is not None:
                self.cj.save(self.cookie_file, True, True)

                msg = 'login success'
                write_message(msg)
                login_ok = True
        except Exception, e:
            msg = 'Error in redo_login. %s' % str(e)
            #logger.info(msg)
            write_message(msg, self.window)

        return login_ok

    def login(self, login_user=None, login_pwd=None):
        if login_user is None or login_pwd is None:
            login_user = self.username
            login_pwd = self.password

        assert (login_user is not None and login_pwd is not None)

        login_ok = False
        try:
            try:
                stObj = self.get_servertime()

                self.servertime = stObj.get('servertime')
                self.nonce = stObj.get('nonce')
                self.pubkey = stObj.get('pubkey')
                self.rsakv = stObj.get('rsakv')
            except:
                return False

            self.get_global_id()

            try:
                login_html = self.do_login(login_user, login_pwd)
                login_html = login_html.replace('"', "'")

                p = re.compile('location\.replace\(\'(.*?)\'\)')
                login_url = p.search(login_html).group(1)

                if 'retcode=0' in login_html:
                    return self.redo_login(login_url)

                write_message(login_html)

                if 'retcode=5' in login_html:
                    msg = 'password or account error.'
                    #logger.info(msg)
                    write_message(msg, self.window)

                    return False

                if 'retcode=4040' in login_html:
                    msg = 'do login too much times.'
                    #logger.info(msg)
                    write_message(msg, self.window)

                    return False

                #是否需要手动输入验证码
                if 1:
                    msg = 'Allow user type verify code. Take a rest and relogin or change another account.'
                    #logger.info(msg)
                    write_message(msg, self.window)
                    pass
                else:
                    msg = 'Enable input verify code, return failure.'
                    #logger.info(msg)
                    write_message(msg, self.window)

                    return False

                #验证码code 4049
                if 'retcode=4049' in login_url:
                    for _ in range(3):
                        msg = 'need verify code.'
                        #logger.info(msg)
                        write_message(msg, self.window)

                        verifycode_url = 'http://login.sina.com.cn/cgi/pin.php?r=%s&s=0&p=%s' % (
                            random.randint(20000000, 99999999), self.pcid)
                        self.save_verifycode(verifycode_url)

                        codeimg = os.path.join(self.soft_path, 'pin.png')
                        msg = 'verify code img path:%s.' % codeimg
                        write_message(msg, self.window)

                        door = raw_input('please type login verify code:')
                        door = door.strip()
                        msg = 'get input verify code:%s' % door
                        write_message(msg, self.window)

                        #附加验证码再次登录
                        self.nonce = self.get_random_nonce()
                        login_html = self.do_login(login_user, login_pwd, door=door)
                        login_html = login_html.replace('"', "'")

                        p = re.compile('location\.replace\(\'(.*?)\'\)')
                        if p.search(login_html):
                            login_url = p.search(login_html).group(1)
                            return self.redo_login(login_url)
                        else:
                            if 'retcode=2070' in login_html:
                                msg = 'verify code:%s error.' % door
                                #logger.info(msg)
                                write_message(msg, self.window)

                                continue
                            else:
                                break
            except Exception, e:
                msg = 'Error in login. %s' % str(e)
                #logger.info(msg)
                write_message(msg, self.window)

                login_ok = False
        except Exception, e:
            msg = 'Error in login. %s' % str(e)
            #logger.info(msg)
            write_message(msg, self.window)

        return login_ok

    def get_content_head(self, url, headers={}, data=None):
        content = ''
        try:
            if os.path.exists(self.cookie_file):
                self.cj.revert(self.cookie_file, True, True)
                self.cookie_support = urllib2.HTTPCookieProcessor(self.cj)
                self.opener = urllib2.build_opener(self.cookie_support, urllib2.HTTPHandler)
                urllib2.install_opener(self.opener)
            else:
                return ''

            self.n_connections += 1

            req = self.pack_request(url=url, headers=headers, data=data)
            resp = self.opener.open(req, timeout=10)

            if resp.info().get('Content-Encoding') == 'gzip':
                content = self.gzip_data(resp.read())
            else:
                content = resp.read()
        except urllib2.HTTPError, e:
            return e.code
        except Exception, e:
            msg = 'Error in get_content. %s' % str(e)
            #logger.info(msg)
            write_message(msg, self.window)

            content = ''

        return content

    def clear_cookie(self, cookie_path):
        try:
            os.remove(cookie_path)
        except:
            pass

    def valid_cookie(self, html=''):
        html = str(html)

        if not html:
            url = 'http://weibo.com/kaifulee'
            headers = self.get_headers(url)
            html = self.get_content_head(url, headers=headers)

        if not html:
            msg = 'need relogin.'
            #logger.info(msg)
            write_message(msg, self.window)

            self.clear_cookie(self.cookie_file)

            return False

        html = str(html)
        html = html.replace('"', "'")

        if 'sinaSSOController' in html:
            p = re.compile('location\.replace\(\'(.*?)\'\)')

            try:
                login_url = p.search(html).group(1)
                headers = self.get_headers(login_url)

                req = self.pack_request(url=login_url, headers=headers)
                html = self.urlopen_read(req)

                self.cj.save(self.cookie_file, True, True)
            except Exception, e:
                msg = 'relogin failed. %s' % str(e)
                #logger.info(msg)
                write_message(msg, self.window)

                self.clear_cookie(self.cookie_file)

                return False

        if 'refresh' in html and 'location.replace' in html:
            msg = 'cookie failure. Please re-login'
            #logger.info(msg)
            write_message(msg, self.window)

            self.clear_cookie(self.cookie_file)

            return False
        elif u'您的帐号存在异常' in html and u'解除限制' in html:
            msg = u'账号被限制.'
            #logger.info(msg)
            write_message(msg, self.window)

            self.clear_cookie(self.cookie_file)

            return False
        elif "$CONFIG['islogin'] = '0'" in html or "$CONFIG['islogin']='0'" in html:
            msg = u'Login failed'
            #logger.info(msg)
            write_message(msg, self.window)

            self.clear_cookie(self.cookie_file)

            return False
        elif "$CONFIG['islogin'] = '1'" in html or "$CONFIG['islogin']='1'" in html:
            msg = 'cookie success.'
            write_message(msg)

            self.cj.save(self.cookie_file, True, True)

            return True
        else:
            msg = u'Login failed'
            #logger.info(msg)
            write_message(msg, self.window)

            self.clear_cookie(self.cookie_file)

            return False

    def check_cookie(self, user=None, pwd=None, soft_path=None):
        if user is None or pwd is None:
            user = self.username
            pwd = self.password

        assert (user is not None and pwd is not None)

        if soft_path is None:
            soft_path = self.soft_path

        login_ok = True

        self.cookie_file = os.path.join(soft_path, 'cookie.txt')
        if os.path.exists(self.cookie_file):
            msg = 'cookie exist.'
            write_message(msg)

            if 'Set-Cookie' not in open(self.cookie_file, 'r').read():
                msg = 'but does not contain a valid cookie.'
                write_message(msg)

                login_ok = self.login(user, pwd)
        else:
            login_ok = self.login(user, pwd)

        if login_ok:
            return self.valid_cookie()
        else:
            return False

        #

    def extract_content(self, html, query):
        '''to extract the useful content according to the query'''
        lines = html.splitlines()

        doc = ''
        for line in lines:
            if line.startswith(query):
                pos = line.find('html":"')
                if pos > 0:
                    line = line.decode('utf-8')
                    try:
                        line = eval("u'''" + line + "'''").encode('utf-8')
                        _doc = line[pos + 7:-12].decode('utf-8').replace('\/', '/')
                    except:
                        _doc = line[pos + 7:-12].replace('\/', '/').replace('\\"', '"').replace("\\'", "'")
                        _doc = _doc.replace('\\t', '').replace('\\n', '')

                    doc += _doc + '\n'

        return doc

    def check_user(self, uid):
        is_exist = False

        url = 'http://weibo.com/u/%s' % (uid)

        headers = self.get_headers(url)
        headers['Accept'] = '*/*'
        headers['Referer'] = 'http://weibo.com/'

        req = self.pack_request(url, headers)

        tries = 10
        for i in range(tries):
            try:
                self.n_connections += 1

                page = None
                with contextlib.closing(urllib2.urlopen(req)) as resp:
                    if resp.info().get('Content-Encoding') == 'gzip':
                        page = self.gzip_data(resp.read())
                    else:
                        page = resp.read()

                if "$CONFIG['islogin'] = '1'" in page or "$CONFIG['islogin']='1'" in page:
                    is_exist = not (u'错误提示 新浪微博' in page)

                    return is_exist
                else:
                    if not self.check_cookie():
                        msg = 'Error in check_user: login failed'
                        #logger.info(msg)
                        write_message(msg, self.window)

                        return None

            except urllib2.HTTPError, e:
                if e.code == 302 and e.geturl is not None:
                    is_exist = True
                else:
                    is_exist = False

                return is_exist
            except urllib2.URLError, e:
                if isinstance(e.reason, socket.timeout) and (i < tries - 1):
                    sec = (i + 1) * 5
                    msg = ('Error in check_user:timeout. Retry: (%s-%s)-sleep %s seconds'
                           % (tries, i, sec))
                    write_message(msg, self.window)
                    time.sleep(sec)
                else:
                    msg = 'Error in check_user: retry timeout. %s' % str(e)
                    #logger.info(msg)
                    write_message(msg, self.window)

                    return None
            except Exception, e:
                msg = 'Error in check_user: exit incorrect. %s' % str(e)
                #logger.info(msg)
                write_message(msg, self.window)

                return None

    def check_message(self, msg_url):
        '''
        msg_url looks like http://weibo.com/1657470871/A0TpPBtt3
        '''

        headers = self.get_headers(msg_url)
        headers['Accept'] = '*/*'
        headers['Referer'] = 'http://weibo.com/'

        req = self.pack_request(msg_url, headers)
        page = self.urlopen_read(req)

        if page is None:
            return None

        if u'抱歉，你访问的页面地址有误，或者该页面不存在' in page:
            return None

        query = settings.QUERY_WEIBOS
        doc = pq(self.extract_content(page, query))

        return doc.find(settings.QUERY_WEIBOS_MID).attr('mid')

    def search_user(self, query):
        raise NotImplementedError

    def search_message(self, query):
        raise NotImplementedError

    '''第一次访问博主的页面不需要参数
    第二次和第三次需要
    body={'__rnd':访问这一页面的时间，以秒表示的13位整数
    '_k':本次登录第一次访问此微薄的时间，16位整数
    '_t':0
    'count':第二次和第二次访问时都是15，第一次访问时是50
    'end_id':最新的这一项微博的mid
    'max_id':已经访问到的，也就是lazyload上面的这一项最旧的微博的mid
    'page':要访问的页码
    'pagebar':第二次是0，第三次是1，第一次没有这项
    'pre_page':第二次和第三次都是本页页码，第一次访问是上页页码
    'uid':博主的uid}
    '''

    def fetch_weibo(self, uid, page=1, **kwargs):
        def _get_first_part(headers, body, url):
            body['__rnd'] = str(int(time.time() * 1000))
            body['pre_page'] = body['page'] - 1

            url = url + urllib.urlencode(body)
            req = self.pack_request(url, headers)
            page = self.urlopen_read(req)

            try:
                return json.loads(page)['data']
            except ValueError:
                return ''
                #return page

        def _get_second_part(headers, body, url):
            body['__rnd'] = str(int(time.time() * 1000))
            body['count'] = '15'
            body['pagebar'] = 0
            body['pre_page'] = body['page']

            url = url + urllib.urlencode(body)
            req = self.pack_request(url, headers)
            page = self.urlopen_read(req)

            try:
                return json.loads(page)['data']
            except ValueError:
                return ''
                #return page

        def _get_third_part(headers, body, url):
            body['__rnd'] = str(int(time.time() * 1000))
            body['count'] = '15'
            body['pagebar'] = '1'
            body['pre_page'] = body['page']

            url = url + urllib.urlencode(body)
            req = self.pack_request(url, headers)
            page = self.urlopen_read(req)

            try:
                return json.loads(page)['data']
            except ValueError:
                return ''
                #return page

        url = 'http://weibo.com/aj/mblog/mbloglist?uid=%s' % uid

        headers = self.get_headers(url)
        headers['Accept'] = '*/*'
        headers['Referer'] = 'http://weibo.com/'
        del headers['Accept-encoding']

        body = {
            '__rnd': '',
            '_k': '',
            '_t': '0',
            'count': '50',
            'end_id': '',
            'max_id': '',
            'page': page,
            'pagebar': '',
            'pre_page': '0',
            'uid': uid
        }

        nodelayload = kwargs.get('nodelayload', False)
        feed_list = ''

        feed_list += _get_first_part(headers, body, url)
        if not nodelayload:
            time.sleep(1)
            feed_list += _get_second_part(headers, body, url)

            time.sleep(1)
            feed_list += _get_third_part(headers, body, url)

        return feed_list

    def fetch(self, url, query):
        headers = self.get_headers(url)
        headers['Accept'] = '*/*'
        headers['Referer'] = 'http://weibo.com/'

        req = self.pack_request(url, headers)
        page = self.urlopen_read(req)
        doc = self.extract_content(page, query)

        return doc

    def fetch_msg_reposts(self, msg_id, page=1):
        url = 'http://weibo.com/aj/mblog/info/big?_wv=5'

        headers = self.get_headers(url)
        headers['Accept'] = '*/*'
        headers['Referer'] = 'http://weibo.com/'
        del headers['Accept-encoding']

        body = {
            '__rnd': str(int(time.time() * 1000)),
            '_t': '0',
            'id': msg_id,
            'page': page
        }

        url = url + urllib.urlencode(body)
        req = self.pack_request(url, headers)
        page = self.urlopen_read(req)

        data = json.loads(page)['data']

        html = data['html']
        num_pages = int(data['page']['totalpage'])

        return html, num_pages

    def fetch_msg_comments(self, msg_id, page=1):
        url = 'http://weibo.com/aj/comment/big?_wv=5'

        headers = self.get_headers(url)
        headers['Accept'] = '*/*'
        headers['Referer'] = 'http://weibo.com/'
        del headers['Accept-encoding']

        body = {
            '__rnd': str(int(time.time() * 1000)),
            '_t': '0',
            'id': msg_id,
            'page': page
        }

        url = url + urllib.urlencode(body)
        req = self.pack_request(url, headers)
        page = self.urlopen_read(req)

        data = json.loads(page)['data']

        html = data['html']
        num_pages = int(data['page']['totalpage'])

        return html, num_pages    
