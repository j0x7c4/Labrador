#encoding=utf-8
import make_network as mn
import networkx as nx
from make_network import user
import os
import sys

if __name__ == "__main__":
	
	host = user(dict(zip(['uid','nickname','sex','addr','daren','verified','vip','n_follows','n_fans','n_weibos','intro','follow_from'],
		['1881798702','Izzzzzie','女','上海 黄浦区','','','','171','145','437'	,'','新浪微博手机版'])))
	file_name = "%s.gml"%host.uid
	
	try:
		G = nx.read_gml(file_name)
	except:
		G = mn.create_graph(host)
		nx.write_gml(G,file_name)
	

