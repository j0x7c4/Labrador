# encoding: utf-8


from sina_weibo.fetcher import ComWeiboFetcher
import sina_weibo as sw
import sys
import time
import memstorage
import account


fetcher = ComWeiboFetcher(username=account.user, password=account.pwd)

login_ok = fetcher.check_cookie()

if not login_ok:
    print 'login failed.'
    sys.exit()

sw.main(fetcher,fetch_data='weibos',store_path='./file/',uids=memstorage.users_id_moniterd)

