#encoding=utf-8
import sys
import os
import networkx as nx
import re

EDGE_INIT_VALUE = 0.5
EDGE_REPOST_VALUE = 0.2

FILE_DIR = './file'

class user:
	def __init__(self,args):
		
		assert re.search('^[\d]+$',args['uid'])

		self.uid = args['uid']
		self.info = {'uid':args['uid'],\
					 'n_follows':args['n_follows'],\
					 'n_fans':args['n_fans'],\
					 'n_weibos':args['n_weibos']}

	def __hash__(self):
		return int(self.uid)

def create_graph ( host, **kwargs ):
	G = nx.Graph()


	user_list={host.uid:host.info}
	#add node
	G.add_node(host.uid,host.info)
	for file in os.listdir(FILE_DIR):
		if not re.search('fans|follows',file):
			continue
		print file
		with open(FILE_DIR+"/"+file) as f:
			lines = f.readlines()
			head = lines[0].strip().split('\t')
			for l in lines[1:]:
				try:
					user_node = user(dict(zip(head,l.strip().split('\t'))))
					if not user_node.uid in user_list:
						G.add_node(user_node.uid,user_node.info)
						user_list.update({user_node.uid:user_node})
						p = (user_node.uid,user_node.info['nickname'])
						print "%s %s is ok\n"%p
				except:
					sys.stderr.write("ERROR:%s\n"%l)


	#add edge
	for file in os.listdir(FILE_DIR):
		m = re.search('^([\d]+)-(fans|follows)-',file)
		if m:
			uid = m.group(1)
			cat = m.group(2)
			u_node = user_list[uid]
			with open(FILE_DIR+"/"+file) as f:
				lines = f.readlines()
				for l in lines[1:]:
					try:
						v_node = user_list[l.strip().split('\t')[0]]
						if cat == 'fans':
							G.add_edge(v_node.uid,u_node.uid,weight=EDGE_INIT_VALUE)
							print "%s<-%s\n"%(uid,v_node.uid)
						else:
							G.add_edge(u_node.uid,v_node.uid,weight=EDGE_INIT_VALUE)
							print "%s->%s\n"%(uid,v_node.uid)
					except:
						sys.stderr.write("ERROR:%s\n"%l)

	#update weight
	for file in os.listdir(FILE_DIR):
		m = re.search('^([\d]+)-weibos-',file)
		if m:
			uid = m.group(1)
			u_node = user_list[uid]
			with open(FILE_DIR+"/"+file) as f:
				lines = f.readlines()
				head = lines[0]
				for l in lines[1:]:
					tmp = dict(zip(head.split('\t'),l.split('\t')))
					try:											
						v_node = user_list[tmp['forward_uid']]
						if (u_node.uid,v_node.uid) in G.edges():
							G[u_node.uid][v_node.uid]['weight']+=EDGE_REPOST_VALUE
						else:
							G.add_edge(u_node.uid,v_node.uid,weight=EDGE_INIT_VALUE) 
					except:
						sys.stderr.write("ERROR:FAIL TO UPDATE %s\n"%(l))
	
	print "#Node:%d\n"%(len(G.nodes()))
	print "#Edge:%d\n"%(len(G.edges()))
	return G

if __name__=="__main__":
	host = user(dict(zip(['uid','nickname','sex','addr','daren','verified','vip','n_follows','n_fans','n_weibos','intro','follow_from'],
		['1881798702','Izzzzzie','女','上海 黄浦区','','','','171','145','437'	,'','新浪微博手机版'])))
	G = create_graph(host)
	save_file = host.uid+".gml"
	nx.write_gml(G,save_file)


