# encoding: utf-8

from common import write_message, logger
from parser import ComWeibosParser, ComFollowsParser, ComFansParser,\
    ComInfosParser, ComRepostsParser, ComCommentsParser
from pyquery import PyQuery as pq  # @UnresolvedImport
from storage import FileStorage
from thread_pool import WorkerManager
import settings
import time

class ComWeiboCrawler(object):
    def __init__(self, fetcher, store_path, **kwargs):
        self.fetcher    = fetcher
        self.store_path = store_path
        
        self.uid     = kwargs.get('uid', None)
        self.msg_url = kwargs.get('msg_url', None)
        self.window  = kwargs.get('window', None)
        self.weibos_storage = kwargs.get('weibos_storage', None)
        self.uids_storage = kwargs.get('uids_storage', None)

        self.error = False
        
    def _check_page_right(self, html):
        '''
        check whether the page is got before login or after.
        '''
        
        return not (u'<title>' in html)
        
    def _fetch(self, url, query):
        html = self.fetcher.fetch(url, query)
        
        page_right = self._check_page_right(html)
        tries = 0
        while not page_right and tries <= 10:
            time.sleep(10)
            self.fetcher.check_cookie()
            
            sec = (tries + 1) * 10
            write_message('_fetch trying: %s, sleep: %s seconds' %(tries, sec), self.window)
            time.sleep(sec)
            
            html = self.fetcher.fetch(url, query)
            page_right = self._check_page_right(html)
            if page_right:
                return html
            
            tries += 1
        else:
            return html
        
        self.error = True
    
    def _fetch_msg_repost(self, msg_id, page=1):
        html, num_pages = self.fetcher.fetch_msg_reposts(msg_id, page)
        
        page_right = self._check_page_right(html)
        tries = 0
        while not page_right and tries <= 10:
            time.sleep(10)
            self.fetcher.check_cookie()
            
            sec = (tries + 1) * 10
            write_message('_fetch trying: %s, sleep: %s seconds' %(tries, sec), self.window)
            time.sleep(sec)
            
            html, num_pages = self.fetcher.fetch_msg_reposts(msg_id, page)
            page_right = self._check_page_right(html)
            if page_right:
                return html, num_pages
            
            tries += 1
        else:
            return html, num_pages
        
        self.error = True
 
    def _fetch_msg_comment(self, msg_id, page=1):
        html, num_pages = self.fetcher.fetch_msg_comments(msg_id, page)
        
        page_right = self._check_page_right(html)
        tries = 0
        while not page_right and tries <= 10:
            time.sleep(10)
            self.fetcher.check_cookie()
            
            sec = (tries + 1) * 10
            write_message('_fetch trying: %s, sleep: %s seconds' %(tries, sec), self.window)
            time.sleep(sec)
            
            html, num_pages = self.fetcher.fetch_msg_reposts(msg_id, page)
            page_right = self._check_page_right(html)
            if page_right:
                return html, num_pages
            
            tries += 1
        else:
            return html, num_pages
        
        self.error = True
                
    def _fetch_weibo(self, uid, page):
        html = self.fetcher.fetch_weibo(uid, page)
        
        page_right = self._check_page_right(html)
        tries = 0
        while not page_right and tries <= 10:
            time.sleep(10)
            self.fetcher.check_cookie()
            
            sec = (tries + 1) * 10
            write_message('_fetch trying: %s, sleep: %s seconds' %(tries, sec), self.window)
            time.sleep(sec)
            
            html = self.fetcher.fetch_weibo(uid, page)
            page_right = self._check_page_right(html)
            if page_right:
                return html
            
            tries += 1
        else:
            return html    
        
        self.error = True
        
    def crawl_weibos(self):
        def _crawl(parser, uid, page, num_pages=''):
            msg = 'Crawl user(%s)\'s weibos-page: %s:%s' %(self.uid, num_pages, page)
            write_message(msg, self.window)
        
            html = self._fetch_weibo(uid, page)
            
            try:
                pq_doc = pq(html)
                return parser.parse(pq_doc)
            except:
                return 0
            
        msg = 'Checking: whether user(%s) exists or not...' %self.uid
        write_message(msg, self.window)
        
        is_exist = self.fetcher.check_user(self.uid)
        
        if is_exist is None:
            return
        
        if not is_exist:
            msg = 'Not exist: %s.' %self.uid
            logger.info(msg)
            write_message(msg, self.window)
            
            return
        
        self.storage = FileStorage(self.uid, settings.MASK_WEIBO, self.store_path)
        
        start_time = time.time()
        
        parser = ComWeibosParser(self.uid, self.storage, weibos_storage=self.weibos_storage)
        
        num_pages = _crawl(parser, self.uid, page=1)
                
        pages = [i for i in xrange(2, num_pages+1)]
        if len(pages) > 0:
            n_threads = 5
            
            worker_manager = WorkerManager(n_threads)
            
            for pg in pages:
                worker_manager.add_job(_crawl, parser, self.uid, pg, num_pages)
            
            worker_manager.wait_all_complete()
        
        cost_time = int(time.time() - start_time)
        msg = ('Crawl user(%s)\'s weibos: total page=%s,'
               ' cost time=%s sec, connections=%s' 
               %(self.uid, num_pages, cost_time, self.fetcher.n_connections))
        logger.info(msg)
        write_message(msg, self.window)

    def check_new_weibos(self):
        def _crawl(parser, uid, page, num_pages=''):
            msg = 'check new weibo in user(%s)\'s weibos-page: %s:%s' %(self.uid, num_pages, page)
            write_message(msg, self.window)

            html = self._fetch_weibo(uid, page)

            try:
                pq_doc = pq(html)
                return parser.parse(pq_doc)
            except:
                return 0

        msg = 'Checking: whether user(%s) exists or not...' %self.uid
        write_message(msg, self.window)

        is_exist = self.fetcher.check_user(self.uid)

        if is_exist is None:
            return

        if not is_exist:
            msg = 'Not exist: %s.' %self.uid
            logger.info(msg)
            write_message(msg, self.window)

            return

        self.storage = FileStorage(self.uid, settings.MASK_WEIBO, self.store_path)

        start_time = time.time()

        parser = ComWeibosParser(self.uid, self.storage)

        num_pages = _crawl(parser, self.uid, page=1)

        cost_time = int(time.time() - start_time)
        msg = ('Crawl user(%s)\'s weibos: total page=%s,'
               ' cost time=%s sec, connections=%s'
               %(self.uid, num_pages, cost_time, self.fetcher.n_connections))
        logger.info(msg)
        write_message(msg, self.window)

    def crawl_follows(self):
        def _crawl(parser, uid, page, num_pages=''):
            msg = 'Crawl user(%s)\'s follows-page: %s:%s' %(self.uid, num_pages, page)
            write_message(msg, self.window)
        
            url  = 'http://weibo.com/%s/follow?page=%s' %(uid, page)
            html = self._fetch(url, query=settings.QUERY_FOLLOWS)
            
            try:
                pq_doc = pq(html)
                return parser.parse(pq_doc)
            except:
                return 0
        
        msg = 'Checking: whether user(%s) exists or not...' %self.uid
        write_message(msg, self.window)
        is_exist= self.fetcher.check_user(self.uid)
        
        if is_exist is None:
            return
        
        if not is_exist:
            msg = 'Not exist: %s.' %(self.uid)
            logger.info(msg)
            write_message(msg, self.window)
            
            return

        self.storage = FileStorage(self.uid, settings.MASK_FOLLOW, self.store_path)
        
        start_time = time.time()
        
        parser = ComFollowsParser(self.storage, uids_storage=self.uids_storage)
        
        num_pages = _crawl(parser, self.uid, page=1)
        if settings.PAGE_LIMIT != 0:
            if num_pages > settings.PAGE_LIMIT:
                msg = 'For sina policy, reduce page count from %s to %s' %(num_pages, settings.PAGE_LIMIT)
                write_message(msg, self.window)
        
                num_pages = settings.PAGE_LIMIT
        
        pages = [i for i in xrange(2, num_pages+1)]
        if len(pages) > 0:
            n_threads = 5
            
            worker_manager = WorkerManager(n_threads)
            
            for pg in pages:
                worker_manager.add_job(_crawl, parser, self.uid, pg, num_pages)
                
            worker_manager.wait_all_complete()

        cost_time = int(time.time() - start_time)
        
        msg = ('Crawl user(%s)\'s follows: total page=%s,'
               ' cost time=%s sec, connections=%s' 
               %(self.uid, num_pages, cost_time, self.fetcher.n_connections))
        logger.info(msg)
        write_message(msg, self.window)

    def crawl_fans(self):
        def _crawl(parser, uid, page, num_pages=''):
            msg = 'Crawl user(%s)\'s fans-page: %s:%s' %(self.uid, num_pages, page)
            write_message(msg, self.window)
            
            url  = 'http://weibo.com/%s/fans?page=%s' %(uid, page)
            html = self._fetch(url, query=settings.QUERY_FANS)
            try:
                pq_doc = pq(html)
                return parser.parse(pq_doc)
            except:
                return 0
            
        msg = 'Checking: whether user(%s) exists or not...' %self.uid
        write_message(msg, self.window)
        is_exist= self.fetcher.check_user(self.uid)
        
        if is_exist is None:
            return
        
        if not is_exist:
            msg = 'Not exist: %s.' %(self.uid)
            logger.info(msg)
            write_message(msg, self.window)
            return
        
        self.storage = FileStorage(self.uid, settings.MASK_FAN, self.store_path)
        
        start_time = time.time()
        
        parser = ComFansParser(self.storage, uids_storage=self.uids_storage)
        
        num_pages = _crawl(parser, self.uid, page=1)
        if settings.PAGE_LIMIT != 0:
            if num_pages > settings.PAGE_LIMIT:
                msg = 'For sina policy, reduce page count from %s to %s' %(num_pages, settings.PAGE_LIMIT)
                write_message(msg, self.window)
        
                num_pages = settings.PAGE_LIMIT
                
        pages = [i for i in xrange(2, num_pages+1)]
        if len(pages) > 0:
            n_threads = 5
            
            worker_manager = WorkerManager(n_threads)
            
            for pg in pages:
                worker_manager.add_job(_crawl, parser, self.uid, pg, num_pages)
            
            worker_manager.wait_all_complete()
            
        cost_time = int(time.time() - start_time)
        
        msg = ('Crawl user(%s)\'s fans: total page=%s,'
               ' cost time=%s sec, connections=%s' 
               %(self.uid, num_pages, cost_time, self.fetcher.n_connections))
        logger.info(msg)
        write_message(msg, self.window)
        
    def crawl_infos(self):
        msg = 'Checking: whether user(%s) exists or not...' %self.uid
        write_message(msg, self.window)
        is_exist= self.fetcher.check_user(self.uid)
        
        if is_exist is None:
            return
        
        if not is_exist:
            msg = 'Not exist: %s.' %self.uid
            logger.info(msg)
            write_message(msg, self.window)
            return
        
        msg = 'Crawl user(%s)\'s profile' %self.uid
        logger.info(msg)
        write_message(msg, self.window)
        
        self.storage = FileStorage(self.uid, settings.MASK_INFO, self.store_path)
        
        start_time = time.time()

        url    = 'http://weibo.com/%s/info' % self.uid
        parser = ComInfosParser(self.uid, self.storage)
        
        html   = self._fetch(url, query=settings.QUERY_INFO)
        try:
            pq_doc = pq(html)
            parser.parse(pq_doc)
        except:
            pass
    
        cost_time = int(time.time() - start_time)
        
        msg = ('Crawl user(%s)\'s infos: cost time=%s sec, connections=%s' 
               %(self.uid, cost_time, self.fetcher.n_connections))
        logger.info(msg)
        write_message(msg, self.window)

    def crawl_msg_reposts(self):
        def _crawl(parser, msg_id, page, num_pages=''):
            msg = 'Crawl message(%s)\'s reposts-page:%s:%s' %(self.msg_id, num_pages, page)
            write_message(msg, self.window)
        
            html, num_pages = self._fetch_msg_repost(msg_id, page)
            
            try:
                pq_doc = pq(html)
                parser.parse(pq_doc)
            except:
                pass
            
            return num_pages
        
        msg = 'Checking: whether message exists or not...'
        write_message(msg, self.window)
        msg_id = self.fetcher.check_message(self.msg_url)
        
        if msg_id is None:
            msg = 'Not exist: %s.' %self.msg_url            
            logger.info(msg)
            write_message(msg, self.window)
            
            return
          
        self.msg_id = msg_id
        self.storage= FileStorage(self.msg_id, settings.MASK_REPOST, self.store_path)
        
        start_time = time.time()
        
        parser = ComRepostsParser(msg_id, self.storage)
        num_pages = _crawl(parser, self.msg_id, 1)
        pages = [i for i in xrange(2, num_pages+1)]
        if len(pages) > 0:
            n_threads = 5
            
            worker_manager = WorkerManager(n_threads)
            
            for pg in pages:
                worker_manager.add_job(_crawl, parser, self.msg_id, pg, num_pages)
            
            worker_manager.wait_all_complete()
            
        cost_time = int(time.time() - start_time)
        
        msg = ('Crawl message(%s)\'s reposts: total page=%s,'
               ' cost time=%s sec, connections=%s' 
               %(self.msg_id, num_pages, cost_time, self.fetcher.n_connections))
        logger.info(msg)
        write_message(msg, self.window) 
    
    def crawl_msg_comments(self):
        def _crawl(parser, msg_id, page, num_pages=''):
            msg = 'Crawl message(%s)\'s comments-page:%s:%s' %(msg_id, num_pages, page)
            write_message(msg, self.window)
        
            html, num_pages = self._fetch_msg_comment(msg_id, page)
            try:
                pq_doc = pq(html)
                parser.parse(pq_doc)
            except:
                pass
            
            return num_pages
        
        msg = 'Checking: whether message exists or not...'
        write_message(msg, self.window)
        msg_id = self.fetcher.check_message(self.msg_url)
        
        if msg_id is None:
            msg = 'Not exist: %s.' %self.msg_url            
            logger.info(msg)
            write_message(msg, self.window)
            
            return 
        
        self.msg_id = msg_id
        self.storage= FileStorage(self.msg_id, settings.MASK_COMMENT, self.store_path)
        
        start_time = time.time()
        
        parser = ComCommentsParser(msg_id, self.storage)
        num_pages = _crawl(parser, self.msg_id, 1)
        pages = [i for i in xrange(2, num_pages+1)]
        if len(pages) > 0:
            n_threads = 5
            
            worker_manager = WorkerManager(n_threads)
            
            for pg in pages:
                worker_manager.add_job(_crawl, parser, self.msg_id, pg, num_pages)
            
            worker_manager.wait_all_complete()
        
        cost_time = int(time.time() - start_time)
            
        msg = ('Crawl message(%s)\'s comments: total page=%s,'
               ' cost time=%s sec, connections=%s' 
               %(self.msg_id, num_pages, cost_time, self.fetcher.n_connections))
        logger.info(msg)
        write_message(msg, self.window)