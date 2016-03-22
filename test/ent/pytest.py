#!/usr/bin/env python3
import subprocess
import re
import signal
import sys
import time
import os
from random import choice
from string import ascii_lowercase


def signal_handler(signal, frame):
        sys.exit(0)
signal.signal(signal.SIGINT, signal_handler)

def discover_sut():
    sut={}
    for ins in subprocess.check_output("ip netns list", shell=True).decode("utf-8").splitlines():
        sut[ins]={'ip':[],'gw':''}
        for iip in subprocess.check_output("ip netns exec %s ip addr list" % ins, shell=True).decode("utf-8").splitlines():
            m = re.search(r'inet\s+(\d+\.\d+\.\d+\.\d+)/\d+', iip)
            if m:
                if not re.search(r"127.0.0.", m.group(1)):
                    sut[ins]['ip'].append((m.group(1)))
        exc=subprocess.check_output("ip netns exec %s ip route list" % ins, shell=True).decode("utf-8")
        m = re.search(r'via\s+(\d+\.\d+\.\d+\.\d+)\s+', exc)
        if m:
            sut[ins]['gw']=m.group(1)
    return sut

def make_res_array(sut):
    res=[]
    for src_ns in sut:
        for dst_ns in sut:
            if not src_ns == dst_ns:
                for src_ip in sut[src_ns]['ip']:
                    for dst_ip in sut[dst_ns]['ip']:
                        randstr=''.join(choice(ascii_lowercase) for i in range(12))
                        file="/var/"+randstr+".ping"
                        res.append({'src_ns': src_ns, 'dst_ns': dst_ns, 'src_ip': src_ip, 'dst_ip': dst_ip, 'file':file})
    print(res)
    return res

def ping_async_test(results):
    print("ASYNCRONOUS PING TESTS START")
    for res in results:
        print("%s.%s -> %s.%s" % (res['src_ns'], res['src_ip'], res['dst_ns'], res['dst_ip']))
        try:
            proc=subprocess.Popen("bash -c \"ip netns exec %s ping -c 10 -i 1 -q -I %s %s &> %s \"" % (res['src_ns'], res['src_ip'], res['dst_ip'],res['file']), shell=True)
            res['proc']=proc
        except subprocess.CalledProcessError as e:
            print("ERR")
    print("ASYNCRONOUS PING TESTS POLLING")
    still_work = 1
    while (still_work):
        still_work=0
        for res in results:
            if 'proc' in res.keys():
                poll_result = res['proc'].poll()
                if poll_result in [0,1]:
                    res.pop('proc')
                    if poll_result == 0:
                        poll_descr = "OK"
                    else:
                        poll_descr = "ERR"
                    res['pingresult'] = poll_descr
                    print("%s.%s -> %s.%s finished: %s" % (res['src_ns'], res['src_ip'], res['dst_ns'], res['dst_ip'], poll_descr))
                else:
                    still_work=1
                    time.sleep(0.1)
    print("ASYNCRONOUS PING TESTS: STATS")
    for res in results:
        f = open(res['file'], 'r')
        stats=f.read()
        os.remove(res['file'])
        m = re.search(r'(\d+) packets transmitted, (\d+) received,.+(\d+)\% packet loss', stats)
        if m:
            print(m)
            res['pingtx'] = m.group(1)
            res['pingrx'] = m.group(2)
            res['pingloss'] = m.group(3)
    for res in results:
        print("%s.%s -> %s.%s : %s %s/%s rcvd" % (res['src_ns'], res['src_ip'], res['dst_ns'], res['dst_ip'], res['pingresult'], res['pingrx'], res['pingtx'])) 
    
def iperf_test(results):
    print("IPERF TESTS: START SERVERS ON EACH NODE")
    ns=[]
    servers=[]
    for res in results:
        if res['src_ns'] not in ns:
            ns.append(res['src_ns'])
    for ins in ns:
        proc=subprocess.Popen("bash -c \"ip netns exec %s iperf -s\"" % ins, shell=True)
        servers.append(proc)
    for res in results:
        print("%s.%s -> %s.%s" % (res['src_ns'], res['src_ip'], res['dst_ns'], res['dst_ip']))
        try:
            proc=subprocess.Popen("bash -c \"ip netns exec %s iperf -B %s -c %s -o %s \"" % (res['src_ns'], res['src_ip'], res['dst_ip'],res['file']), shell=True)
            res['proc']=proc
        except subprocess.CalledProcessError as e:
            print("ERR")
    print("IPERF POLLING")
    still_work = 1
    while (still_work):
        still_work=0
        for res in results:
            if 'proc' in res.keys():
                poll_result = res['proc'].poll()
                if poll_result in [0,1]:
                    res.pop('proc')
                    if poll_result == 0:
                        poll_descr = "OK"
                    else:
                        poll_descr = "ERR"
                    res['pingresult'] = poll_descr
                    print("%s.%s -> %s.%s finished: %s" % (res['src_ns'], res['src_ip'], res['dst_ns'], res['dst_ip'], poll_descr))
                else:
                    still_work=1
                    time.sleep(0.1)
#    print("ASYNCRONOUS PING TESTS: STATS")
#    for res in results:
#        f = open(res['file'], 'r')
#        stats=f.read()
#        os.remove(res['file'])
#        m = re.search(r'(\d+) packets transmitted, (\d+) received,.+(\d+)\% packet loss', stats)
#        if m:
#            print(m)
#            res['pingtx'] = m.group(1)
#            res['pingrx'] = m.group(2)
#            res['pingloss'] = m.group(3)
#    for res in results:
#        print("%s.%s -> %s.%s : %s %s/%s rcvd" % (res['src_ns'], res['src_ip'], res['dst_ns'], res['dst_ip'], res['pingresult'], res['pingrx'], res['pingtx'])) 
    
def check_gw(sut):
    print ("CHECKING DEFAULT GW BY ARP PROBE")
    for ns in sut:
        print("%s -> gw:%s " % (ns, sut[ns]['gw']),end="",flush=True)
        try:
            caught=0
            for i in range(5):
                exc = subprocess.check_output("ip netns exec %s arping -c 1 -w 1000000 %s | grep extra" % (ns, sut[ns]['gw']), shell=True).decode("utf-8")
                m = re.search(r'(\d+)\s+packets\s+transmitted,\s+(\d+)\s+packets\s+received,\s+(\d+)%\s+unanswered\s+\((\d+)\s+extra\)', exc)
                if (int(m.group(2)) > 0):
                    print("+", end="",flush=True)
                    sut[ns]['gwok']=1
                    break
                else:
                    print(".", end="",flush=True)
        except subprocess.CalledProcessError:
            print('ERR',end="",flush=True)
        print("")
    return(sut)

def main():
    sut=discover_sut()
    #act_sut=check_gw(sut)
    res=make_res_array(sut)
    #ping_async_test(res)
    iperf_test(res)
    

if __name__ == "__main__":
   try:
      main()
   except KeyboardInterrupt:
      sys.exit()
