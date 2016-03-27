#!/usr/bin/env python
from __future__ import print_function
import sys
import requests
import json
import time
import logging
# IF YOU NEED LOGGING UNCOMMENT THIS
#try: # for Python 3
#    from http.client import HTTPConnection
#except ImportError:
#    from httplib import HTTPConnection
#HTTPConnection.debuglevel = 1
#logging.basicConfig() # you need to initialize logging, otherwise you will not see anything from requests
#logging.getLogger().setLevel(logging.DEBUG)
#requests_log = logging.getLogger("requests.packages.urllib3")
#requests_log.setLevel(logging.DEBUG)
#requests_log.propagate = True


class CtlAPI:
    def __init__(self, baseurl, login, password):
        self.baseurl = baseurl
        self.login = login
        self.password = password
        self.client = requests.session()
        self.get_csrf_token()
        login_data = dict(j_username=self.login, j_password=self.password)
        print("Login as %s :" % self.login, end="")
        self.r = self.client.post(self.baseurl + "api/authentication", data=login_data, headers={'Referer':self.baseurl, 'X-CSRF-TOKEN':self.csrf})
        print("HTTP_Resp:%s" % self.r.status_code)
    def post(self, url, request):
        self.url = url
        self.request = json.dumps(request).encode('utf8')
        self.get_csrf_token()
        print("POST %s%s %s " % (self.baseurl, self.url, self.request), end="")
        self.r = self.client.post(self.baseurl + self.url, data=self.request, headers={"content-type": "application/json;charset=utf-8", 'X-CSRF-TOKEN': self.csrf})
        print("HTTP_Resp:%s" % self.r.status_code)
    def delete(self, url):
        self.url = url
        self.get_csrf_token()
        print("DELETE %s%s " % (self.baseurl, self.url), end="")
        self.r = self.client.delete(self.baseurl + self.url, headers={"content-type": "application/json;charset=utf-8", 'X-CSRF-TOKEN': self.csrf})
        print("HTTP_Resp:%s %s" % (self.r.status_code, self.r.text))
    def get(self, url):
        self.url = url
        self.get_csrf_token()
        print("GET %s%s " % (self.baseurl, self.url), end="")
        self.r = self.client.get(self.baseurl + self.url, headers={"content-type": "application/json;charset=utf-8", 'X-CSRF-TOKEN': self.csrf})
        print("HTTP_Resp:%s %s" % (self.r.status_code, self.r.text))
        return(self.r.json())
    def put(self, url, request):
        self.url = url
        self.request = json.dumps(request).encode('utf8')
        self.get_csrf_token()
        print("PUT %s%s %s " % (self.baseurl, self.url, self.request), end="")
        self.r = self.client.put(self.baseurl + self.url, self.request, headers={"content-type": "application/json;charset=utf-8", 'X-CSRF-TOKEN': self.csrf})
    def get_csrf_token(self):
        print("GET CSRF Token at %s " % self.baseurl, end="")
        self.r = self.client.get(self.baseurl)
        print("HTTP_Resp:%s " % self.r.status_code, end="")
        self.csrf = self.r.cookies['CSRF-TOKEN']
        print("Token:%s" % self.csrf)

c = CtlAPI('http://10.7.1.101:8080/', 'admin', 'admin')
"""
# get all clusters and switches
clusters=c.get('api/clusters')
if (clusters):
    for i in range(len(clusters)):
        clusters[i]['switches'] = c.get("api/cluster/%s/commutators?page=1&size=15" % clusters[i]['id'])

# get configured controllers
controllers=c.get("api/controllers")
if (controllers):
    print(controllers)

print(clusters)
# CODE BELOW DELETES ORC's CONFIGURATION SO MAY BE HARMFUL !!!
# DELETE all configured clusters
if (clusters):
    for cluster in clusters:
        c.delete("api/clusters/%s" % cluster['id'])

# DELETE all configured controllers
if (controllers):
    for controller in controllers:
        c.delete("api/controllers/%s" % controller['id'])

# CREATE CONTROLLERS
c.post('api/controllers',{"name":None,"ip":None,"id":None,"jgroupsPort":7800,"netconfPort":830,"address":"ctl1"})
c.post('api/controllers',{"name":None,"ip":None,"id":None,"jgroupsPort":7800,"netconfPort":830,"address":"ctl2"})
c.post('api/controllers',{"name":None,"ip":None,"id":None,"jgroupsPort":7800,"netconfPort":830,"address":"ctl3"})

# Wait untill all the controllers get connected
while True:
    controllers=c.get('api/controllers')
    print(controllers)
    if (len(controllers) == 3):
        break
    time.sleep(5)

# GET configured controllers and
# ADD them to the redundant cluster
controllers=c.get('api/controllers')
clust={"name":"Cluster1","ip":None,"clusterType":"MASTER_SLAVE","id":None,"nodes":controllers, "masterNode": controllers[1],"tagType":"STag_VLAN"}
c.post('api/clusters',clust)
"""
# Wait until cluster[0] become Active
while True:
    cluster=c.get('api/clusters')[0]
    print(cluster['clusterStatus'])
    if (cluster['clusterStatus'] == 'ACTIVE'):
        break
    time.sleep(5)

#Wait until all 4 switches become visible
while True:
    switches=c.get('api/cluster/%s/commutators?page=1&size=15' % cluster['id'])
    print("%s switches in cluster" % switches['totalSize'])
    if (switches['totalSize'] == 4):
        break
    time.sleep(5)

# Enable all inactive switches
for i in range(len(switches['content'])):
    if (switches['content'][i]['status'] == 'INACTIVE'):
        c.put("api/cluster/%s/commutators/enable/%s" % (cluster['id'],switches['content'][i]['id']), None)

# Show switches' MAC addresses
# Useful to copy-paste below for renaming
print("Switch MAC addresses are:")
for i in range(len(switches['content'])):
    print(switches['content'][i]['mac'])

# switch names to MAC mapping for renaming
sw_names={'00:e0:ed:2f:51:f8': 'HQ',
          '00:e0:ed:2a:74:e6': 'BR1',
          '00:e0:ed:2e:4e:e0': 'BR2',
          '00:e0:ed:2f:52:04': 'BR3'}

# rename switches which have MAC equal to name
for i in range(len(switches['content'])):
    if (switches['content'][i]['name'] == switches['content'][i]['mac']):
        switches['content'][i]['name'] = sw_names[switches['content'][i]['mac']]
        c.put("api/cluster/%s/commutators" % cluster['id'], switches['content'][i])
