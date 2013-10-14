#encoding=utf-8
import sys
import os
import networkx as nx
import re

FILE_DIR = './file'

class user:
	def __init__(self,args):
		
		assert re.search('^[\d]+$',args['uid'])

		self.uid = args['uid']
		self.info = args

	def __hash__(self):
		return int(self.uid)

if __name__=="__main__":

	G = nx.Graph()
	host = user(dict(zip(['uid','nickname','sex','addr','daren','verified','vip','n_follows','n_fans','n_weibos','intro','follow_from'],
		['1881798702','Izzzzzie','女','上海 黄浦区','','','','171','145','437'	,'','新浪微博手机版'])))
	user_list={host.uid:host.info}
	#add node
	G.add_node(host)
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
						user_list.update({user_node.uid:user_node})
						G.add_node(user_node)
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
							G.add_edge(v_node,u_node)
							print "%s<-%s\n"%(uid,v_node.uid)
						else:
							G.add_edge(u_node,v_node)
							print "%s->%s\n"%(uid,v_node.uid)
					except:
						sys.stderr.write("ERROR:%s\n"%l)


	print "#Node:%d\n"%(len(G.nodes()))
	print "#Edge:%d\n"%(len(G.edges()))
	nx.write_gml(G,'./user_network.gml')

