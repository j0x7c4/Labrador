# encoding: utf-8


from sina_weibo.fetcher import ComWeiboFetcher
import sina_weibo as sw
import sys
import time
import memstorage
import account
from thread_pool import WorkerManager

fetcher = ComWeiboFetcher(username=account.user, password=account.pwd)

login_ok = fetcher.check_cookie()

if not login_ok:
    print 'login failed.'
    sys.exit()

fans = []
follows = []

sw.main(fetcher, fetch_data='follows', store_path='./file/', uids=memstorage.users_id_moniterd, uids_storage=follows)
sw.main(fetcher, fetch_data='fans', store_path='./file/', uids=memstorage.users_id_moniterd, uids_storage=fans)

friends_list = list(set(fans)|set(follows))

print friends_list
#host's weibo
sw.main(fetcher,fetch_data='weibos',store_path='./file/',uids=memstorage.users_id_moniterd)
#friends' weibo
n_threads = 10
n_paritions = 10
len_partition = len(friends_list)/n_paritions

worker_manager = WorkerManager(n_threads)
'''
for i in range(0,len(friends_list),len_partition):
	worker_manager.add_job(sw.main, fetcher, fetch_data='weibos',store_path='./file/',
		uids=friends_list[i:min(i+len_partition,len(friends_list))] )  
'''
len_fans_partition =  len(fans)/n_paritions
for i in range(0,len(fans),len_partition):
	worker_manager.add_job(sw.main, fetcher, fetch_data='fans',store_path='./file/',
		uids=fans[i:min(i+len_partition,len(fans))] )	
worker_manager.wait_all_complete()

worker_manager = WorkerManager(n_threads)
len_follows_partition =  len(follows)/n_paritions
for i in range(0,len(follows),len_partition):
	worker_manager.add_job(sw.main, fetcher, fetch_data='follows',store_path='./file/',
		uids=follows[i:min(i+len_partition,len(follows))] )	
worker_manager.wait_all_complete()
