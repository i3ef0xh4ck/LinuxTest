#-*- coding: utf-8 -*-

import sys
import os
import traceback
import datetime
import json
import re


from sys import path
reload(sys)
sys.setdefaultencoding('utf-8')


'''
""" 脚本配置执行说明 """
该脚本不是单独的用例，仅用于获取环境中注册到nginx的API接口。
'''

'''
""" 可以在此处下方添加自己的代码（函数） """
'''
try:
    g_Log = None
    g_Global = None
    g_caseName = None
    g_registeredAPIExcel = None

    curFile = os.path.abspath(sys._getframe(0).f_code.co_filename)
    g_caseName = curFile.replace("\\","/")
    g_curDir = os.path.split(g_caseName)[0]
    path.append( g_caseName.split("TestCase")[0]+"PublicLib" )

    tempConfig = g_curDir+"/_tempConfig.ini"
    pathExist = os.path.exists(tempConfig)
    if pathExist:
        file = open(tempConfig)
        info = file.readlines()
        for line in info:
            if "startTime" in line:
                startTime = line.split("startTime:")[1].strip()
    if startTime == None:
        startTime = str(datetime.datetime.now())
    import GlobalValue as g_Global
    g_Global.init()
    g_Global.setValue("startTime",startTime)

    import Log
    import ExcelOperate
    import ContainerOperate
    import LinuxOperate
    import LocalOperate
    g_Log = Log.Log()
    g_Local = LocalOperate.Local()

    ##### 获取环境配置信息
    excelName = g_caseName.split("TestCase")[0]+"Config/config.xlsx"
    excel1 = ExcelOperate.Excel(excelName=excelName,sheetName="vmInfo")
    g_vmInfo = excel1.read()
    del g_vmInfo[0]
    g_omCoreInfo = []
    for vm in g_vmInfo:
        if vm[6]==1 or str(vm[6]).upper() == "TRUE":
            g_omCoreInfo = [ vm[0], vm[1], vm[2], vm[3], vm[4], vm[5]]

    codeAPIExcel = g_curDir + "/APIlist.xlsx"
    excel1 = ExcelOperate.Excel(excelName=codeAPIExcel,sheetName="API")
    g_codeAPI = excel1.read()
    del g_codeAPI[0]
    excel2 = ExcelOperate.Excel(excelName=codeAPIExcel,sheetName="parameter")
    g_config = excel2.read()
    del g_config[0]


except:
    errmsg = ''.join(traceback.format_exception(*sys.exc_info()))
    print errmsg
    exit(0)

def get_registeredAPI_from_hrs(linux): # 从er、ir、ber的注册文件中获取api注册的ip和端口等信息:[[LinuxIP,dir,urlNo,location_url,serverName,"ip_port,ip_port"]]
    registeredAPI = []
    command = "find / -type f -name \"nginx*\\.conf\" 2>/dev/null"
    output = linux.sendRootCommand(command)
    if output == False:
        return False
    nginxConf = output[0].split("\n")
    for conf in nginxConf:
        try:
            dir = os.path.split(conf)[0]
            output = linux.sendRootCommand("ls -l {dir}".format(dir=dir))
            if output == False:
                continue
            filelist = output[0]
            if " route_detail.json\n" in filelist and " upstream_ex.json\n" in filelist:
                routeFile = dir + "/" + "route_detail.json"
                upstreamFile = dir + "/" + "upstream_ex.json"
            else:
                continue
            ### 从nginx_*_ex.conf中获取 [[linuxIP,dir,urlNo,location_url]]
            output = linux.sendRootCommand("cat {nginxFile} |egrep \"urlNo|location_url\"".format(nginxFile=conf))
            if output == False:
                continue
            nginxConfig = []
            x = re.findall("set\s+\$urlNo\s+\'(\d+)\'\s*;\s*\n\s*set\s+\$location_url\s+\'(.*?)\';",output[0])
            for n in x:
                nginxConfig.append([dir,n[0],n[1]])
            ### 从route_detail.json中获取 [[urlNo,location_url,serverName]]
            routeConfig = []
            output = linux.sendRootCommand("cat {routeFile}".format(routeFile=routeFile))
            decoded = json.loads(output[0])
            for key in decoded['URLS'].keys():
                iffind = False
                for nc in nginxConfig:
                    dir = nc[0]
                    urlNo = nc[1]
                    location_url = nc[2]
                    if key == urlNo:
                        conf = decoded['URLS'][key]
                        conf = json.dumps(conf)
                        sName = re.findall("\"serverName\"\s*:\s*\"(.*?)\"",str(conf))
                        if sName == []:
                            serverName = "ERROR:URLS为{urlNo}的注册信息中没有serverName信息".format(urlNo=urlNo)
                        elif len(sName)>1:
                            serverName = "ERROR:URLS为{urlNo}的注册信息中含有多条serverName信息".format(urlNo=urlNo)
                        else:
                            serverName = sName[0]
                        routeConfig.append([dir,urlNo,location_url,serverName])
                        iffind = True
                if iffind == False:
                    serverName = "ERROR:route_detail.json中没有找到URLS为{urlNo}的注册信息"
                    routeConfig.append([dir,urlNo,location_url,serverName])
            ### 从upstream_ex.json中获取 [[LinuxIP,dir,urlNo,location_url,serverName,"ip_port,ip_port"]]
            upstreamConfig = []
            output = linux.sendRootCommand("cat {upstreamFile}".format(upstreamFile=upstreamFile))
            decoded = json.loads(output[0])
            for serversKey in decoded['servers'].keys():
                for rc in routeConfig:
                    dir = rc[0]
                    urlNo = rc[1]
                    location_url = rc[2]
                    serverName = rc[3]

                    if serversKey == serverName:
                        servers = decoded['servers'][serversKey]['cluster']
                        serversHttpInfo = []
                        for clusterKey in servers.keys():
                            cluster = servers[clusterKey]
                            httpInfo = []
                            for httpKey in cluster.keys():
                                if httpKey == "IP":
                                    ip = cluster[httpKey]
                                if httpKey == "port":
                                    port = cluster[httpKey]
                                if httpKey == "irIP":
                                    irIP = cluster[httpKey]
                                if httpKey == "irPort":
                                    irPort = cluster[httpKey]
                            if ip is not None and port is not None:
                                httpInfo.append(ip+":"+port)
                            if irIP is not None and irPort is not None:
                                httpInfo.append(irIP+":"+irPort)
                            #if httpInfo == []:
                            #    httpInfo = "ERROR:upstream_ex.json中没有找到cluster为{cluster}的IP和PORT信息".format(cluster=cluster)
                            serversHttpInfo = serversHttpInfo+httpInfo
                        if serversHttpInfo == []:
                            serversHttpInfo = ["ERROR:upstream_ex.json中没有找到servers为{servers}的IP和PORT信息".format(servers=servers)]
                        registeredAPI.append([linux.ip,dir,urlNo,location_url,serverName,",".join(serversHttpInfo)])
        except:
            errmsg = ''.join(traceback.format_exception(*sys.exc_info()))
            g_Log.writeLog(errmsg)

    return registeredAPI

def get_vmRealIP(linux):  # 根据虚机挂载的大网IP获取实际eth0信息
    try:
        output = linux.sendRootCommand("/usr/sbin/ifconfig eth0")
        readIP = re.findall("inet\s+(\d+\.\d+\.\d+\.\d+)",output[0])
        return readIP[0]
    except:
        errmsg = ''.join(traceback.format_exception(*sys.exc_info()))
        g_Log.writeLog(errmsg)
        return ""

def get_registeredAPI(): # 主要函数1：获取所有api注册信息：[[LinuxIP,eth0IP,dir,urlNo,location_url,serverName,"ip_port,ip_port"]]
    registeredAPI = []
    allExternalPort = get_allExternalPort()
    for vm in g_vmInfo:
        try:
            vmIP = vm[0]
            vmUser = vm[2]
            vmUserPasswd = vm[3]
            vmSuRoot = vm[4]
            vmRootPasswd = vm[5]
            tLinux = LinuxOperate.Linux(ip=vmIP,user=vmUser,password=vmUserPasswd,suRoot=vmSuRoot,rootPassword=vmRootPasswd)
            readIP = get_vmRealIP(tLinux)

            regHRS = get_registeredAPI_from_hrs(tLinux) # 从er、ir、ber的注册文件中获取api注册的ip和端口等信息

            if regHRS == False:
                continue
            for reg in regHRS:
                if readIP == reg[0]:
                    registeredAPI.append(["",readIP,reg[1],reg[2],reg[3],reg[4],reg[5]])
                else:
                    reg.insert(1,readIP)
                    registeredAPI.append(reg)
        except:
            errmsg = ''.join(traceback.format_exception(*sys.exc_info()))
            g_Log.writeLog(errmsg)

    tmpList = []
    registeredAPIs = []
    for api in registeredAPI:
        if [api[4],api[5],api[6]] not in tmpList: #优化项1：重复的注册信息，后续可以责成开发优化
            tmpList.append([api[4],api[5],api[6]])
            registeredAPIs.append([api[0],api[1],api[2],api[3],api[4],api[5],api[6]])

    result = []
    for reg in registeredAPIs: #[LinuxIP,eth0IP,dir,urlNo,location_url,serverName,"ip_port,ip_port"]
        try:
            regPorts = reg[6].split(",")
            tmpPort = reg[6]
            for externalPort in allExternalPort:#[serviceName,externalPort,endPoints]
                for regPort in regPorts:
                    if regPort in externalPort[2]:
                        tmpPort = tmpPort.replace(regPort,externalPort[1])
                        tmpPort = ",".join( list(set(tmpPort.split(","))) )
            result.append([reg[0],reg[1],reg[2],reg[3],reg[4],reg[5],tmpPort])
        except:
            errmsg = ''.join(traceback.format_exception(*sys.exc_info()))
            g_Log.writeLog(errmsg)
    return result


def get_externalPortBySVC(): # 通过kubectl get svc --all-namespaces命令获取虚机上启动的external IP和端口:[serviceName,externalPort,endPoints]
    externalPorts = []
    omCoreIP = g_omCoreInfo[0]
    omCoreUser = g_omCoreInfo[2]
    omCoreUserPasswd = g_omCoreInfo[3]
    omCoreSuRoot = g_omCoreInfo[4]
    omCoreRootPasswd = g_omCoreInfo[5]
    ssh = LinuxOperate.Linux(ip=omCoreIP,user=omCoreUser,password=omCoreUserPasswd,suRoot=omCoreSuRoot,rootPassword=omCoreRootPasswd)
    command = "ps -ef | grep /usr/local/bin/kubelet | grep -v grep | awk -F \"api-servers=\" '{print $2}' | awk '{print $1}'"
    output = ssh.sendCommand(command)
    kubernetes_master = output[0].strip()
    #for conf in g_config:
    #    if conf[0]=="KUBERNETES_MASTER":
    #        kubernetes_master = conf[1]
    command = "export KUBERNETES_MASTER={kubernetes_master};export PAAS_CRYPTO_PATH=/var/paas/srv/kubernetes;/var/paas/kubernetes/kubectl --client-certificate=${key1}/server.cer --client-key=${key1}/server_key.pem --certificate-authority=${key1}/ca.cer -s ${key2} get svc --all-namespaces".format(kubernetes_master=kubernetes_master,key1="{PAAS_CRYPTO_PATH}",key2="{KUBERNETES_MASTER}")
    output = ssh.sendRootCommand(command)
    svcInfo = output[0].split("\n")
    for svc in svcInfo:
        try:
            if svc.strip() == "":
                continue
            res = svc.split()
            namespace = res[0]
            serName = res[1]
            command = "export KUBERNETES_MASTER={kubernetes_master};export PAAS_CRYPTO_PATH=/var/paas/srv/kubernetes;/var/paas/kubernetes/kubectl --client-certificate=${key1}/server.cer --client-key=${key1}/server_key.pem --certificate-authority=${key1}/ca.cer -s ${key2} describe svc {serice} -n {namespace} |egrep \"IP:|Name:|Namespace:|Type:|External IPs:|LoadBalancer Ingress:|Port:|NodePort:|Endpoints:\"".format(kubernetes_master=kubernetes_master,key1="{PAAS_CRYPTO_PATH}",key2="{KUBERNETES_MASTER}",namespace=namespace,serice=serName)
            output = ssh.sendRootCommand(command)
            x = re.findall("Name:\s*(.*?)\s*\n",output[0])
            name = x[0]
            t1_port1 = re.findall("\W+Port:\s+[a-zA-Z0-9\<\>\s\-]+\s+(\d+)/\w+\s*\n\s*Endpoints:\s*([0-9:,\.]+)",output[0])
            t1_port2 = re.findall("\W+Port:\s+[a-zA-Z0-9\<\>\s\-]+\s+(\d+)/\w+\s*\n\s*NodePort:\s+[a-zA-Z0-9\s\-]+\s+\d+/\w+\s*\n\s*Endpoints:\s+([0-9:,\.]+)",output[0])
            t1_ports = t1_port1+t1_port2
            t1_ip = re.findall("IP:\s*(\d+\.\d+\.\d+\.\d+)",output[0])
            t1_externalip = re.findall("External IPs:\s*(\d+\.\d+\.\d+\.\d+)",output[0])
            t1_ingress = re.findall("LoadBalancer Ingress:\s*(\d+\.\d+\.\d+\.\d+)",output[0])
            #t1_nodeport = re.findall("NodePort:.*\s+(\d+)/\w+",output[0])
            t1_nodeport = re.findall("\W*NodePort:\s+[a-zA-Z0-9\s\-]+\s+(\d+)/\w+\s*\n\s*Endpoints:\s*([0-9:,\.]+)",output[0])

            ifFind = False
            if t1_ports != [] and t1_ip != []:
                for p in t1_ports:
                    endPoints = p[1]
                    externalPort = t1_ip[0]+":"+p[0]
                    externalPorts.append([name,externalPort,endPoints])
                ifFind = True
            if t1_ports != [] and t1_externalip != []:
                for p in t1_ports:
                    endPoints = p[1]
                    externalPort = t1_externalip[0]+":"+p[0]
                    externalPorts.append([name,externalPort,endPoints])
                ifFind = True
            if t1_ports != [] and t1_ingress != []:
                for p in t1_ports:
                    endPoints = p[1]
                    externalPort = t1_ingress[0]+":"+p[0]
                    externalPorts.append([name,externalPort,endPoints])
                ifFind = True
            if t1_nodeport != []:
                tmpcmd = "export KUBERNETES_MASTER={kubernetes_master};export PAAS_CRYPTO_PATH=/var/paas/srv/kubernetes;/var/paas/kubernetes/kubectl --client-certificate=${key1}/server.cer --client-key=${key1}/server_key.pem --certificate-authority=${key1}/ca.cer -s ${key2} get pods -n {namespace} |grep {serice}".format(kubernetes_master=kubernetes_master,key1="{PAAS_CRYPTO_PATH}",key2="{KUBERNETES_MASTER}",namespace=namespace,serice=serName)
                tmpout = ssh.sendRootCommand(tmpcmd)
                pods = re.findall("({serice}.*?)\s".format(serice=serName),tmpout[0])
                for pod in pods:
                    try:
                        tmpcmd1 = "export KUBERNETES_MASTER={kubernetes_master};export PAAS_CRYPTO_PATH=/var/paas/srv/kubernetes;/var/paas/kubernetes/kubectl --client-certificate=${key1}/server.cer --client-key=${key1}/server_key.pem --certificate-authority=${key1}/ca.cer -s ${key2} get pods {pod} -n {namespace} -o yaml |grep hostIP".format(kubernetes_master=kubernetes_master,key1="{PAAS_CRYPTO_PATH}",key2="{KUBERNETES_MASTER}",namespace=namespace,pod=pod)
                        tmpout1 = ssh.sendRootCommand(tmpcmd1)
                        tempx = re.findall("hostIP:\s*(\d+\.\d+\.\d+\.\d+)",tmpout1[0])
                        hostIP = tempx[0]
                        for p in t1_nodeport:
                            endPoints = p[1]
                            externalPort = hostIP+":"+p[0]
                            externalPorts.append([name,externalPort,endPoints])
                    except:
                        errmsg = ''.join(traceback.format_exception(*sys.exc_info()))
                        g_Log.writeLog(errmsg)
                ifFind = True
            if ifFind == False:
                g_Log.writeLog("以下服务的端口自动化判断为不涉及认证（api注册信息中不包含这些端口），无需测试：\n"+output[0])
                continue
        except:
            errmsg = ''.join(traceback.format_exception(*sys.exc_info()))
            g_Log.writeLog(errmsg)
    return externalPorts

def get_externalPortByDocker(): # 通过docker ps命令获取虚机上启动的容器中的所有IP和端口:[serviceName,externalPort,endPoints]
    externalPorts = []
    for vm in g_vmInfo:
        try:
            vmIP = vm[0]
            vmUser = vm[2]
            vmUserPasswd = vm[3]
            vmSuRoot = vm[4]
            vmRootPasswd = vm[5]
            tLinux = LinuxOperate.Linux(ip=vmIP,user=vmUser,password=vmUserPasswd,suRoot=vmSuRoot,rootPassword=vmRootPasswd)
            realIP = get_vmRealIP(tLinux)

            output = tLinux.sendRootCommand("/usr/bin/netstat -tunlp")
            vmPorts = re.findall("\d+\.\d+\.\d+\.\d+:\d+|:::\d+",output[0])
            vmPorts = ",".join(vmPorts)

            output = tLinux.sendRootCommand("docker ps |egrep -v \"pause|CONTAINER\"")
            dockerInfo = output[0].split("\n")
            for docker in dockerInfo:
                try:
                    if "k8s_" not in docker:
                        continue
                    dockerID = docker.split()[0]
                    x = re.findall("k8s_(.*?)\.\w+",docker)
                    serviceName = x[0]
                    output = tLinux.sendRootCommand("docker exec -u 0 {id} {cmd}".format(id=dockerID,cmd="/usr/sbin/ifconfig eth0"))
                    x = re.findall("inet\s+(\d+\.\d+\.\d+\.\d+)",output[0])
                    containerIP = x[0]
                    if realIP == containerIP:
                        continue
                    output = tLinux.sendRootCommand("docker exec -u 0 {id} {cmd}".format(id=dockerID,cmd="/usr/bin/netstat -tunlp"))
                    dockerPorts = re.findall("\d+\.\d+\.\d+\.\d+:\d+|:::\d+",output[0])
                    dockerPorts = ",".join(dockerPorts).replace("::",containerIP).replace("0.0.0.0",containerIP).replace("127.0.0.1",containerIP).split(",")
                    for dockerPort in dockerPorts:
                        x = re.findall("\d+\.\d+\.\d+\.\d+:{port}\D*|:::{port}\D*".format(port=dockerPort.split(":")[1]),vmPorts)
                        if x == []:
                            continue
                        externalPort = x[0].replace("::",realIP).replace("0.0.0.0",realIP).replace("127.0.0.1",realIP).replace(",","")
                        externalPorts.append([serviceName,externalPort,dockerPort])
                except:
                    errmsg = ''.join(traceback.format_exception(*sys.exc_info()))
                    g_Log.writeLog(errmsg)

        except:
            errmsg = ''.join(traceback.format_exception(*sys.exc_info()))
            g_Log.writeLog(errmsg)

    return externalPorts

def get_allExternalPort(): #获取虚机上所有启动的external IP和端口[serviceName,externalPort,endPoints]
    allExternalPort = []
    externalPortBySVC = get_externalPortBySVC()
    allExternalPort = allExternalPort + externalPortBySVC
    externalPortByDocker = get_externalPortByDocker()
    allExternalPort = allExternalPort + externalPortByDocker

    return allExternalPort

'''
""" 以下定义的函数，请在特定位置添加自己的代码 """
'''
# 执行前的准备操作
def prepare():
    try:
        ''''''''' 可以在此处下方添加自己的代码 '''''''''
    except:
        errmsg = ''.join(traceback.format_exception(*sys.exc_info()))
        g_Log.writeLog(errmsg)
        return 0
    return 1

# 执行用例
def run():
    try:
        ''''''''' 可以在此处下方添加自己的代码 '''''''''
        curDir = os.path.split(g_caseName)[0]
        resultDir = curDir.replace("TestCase","Report")
        startTimeSign = g_Global.getValue("startTime").replace(":","").replace(" ","").replace("-","")
        #startTimeSign = "20180228145712.735000"
        registeredAPIExcelName=resultDir+"/registeredAPIs-{startTime}.xls".format(startTime=startTimeSign)

        registeredAPI = get_registeredAPI()  # 输出格式：[LinuxIP,dir,urlNo,location_url,serverName,"ip_port,ip_port"]
        registeredAPIExcel = ExcelOperate.Excel(excelName=registeredAPIExcelName,sheetID=0)
        registeredAPIExcel.new()
        registeredAPIExcel.write([[u"虚机挂载IP",u"虚机IP",u"信息来源",u"urlNo",u"urlPrefix",u"所属服务",u"http端口信息"]])
        registeredAPIExcel.write(registeredAPI)

        global g_registeredAPIExcel
        g_registeredAPIExcel = registeredAPIExcelName
    except:
        errmsg = ''.join(traceback.format_exception(*sys.exc_info()))
        g_Log.writeLog(errmsg)
        return 0
    return 1

# 执行后清理环境
def clearup():
    try:
        ''''''''' 可以在此处下方添加自己的代码 '''''''''
        curDir = os.path.split(g_caseName)[0]
        tempConfig=curDir+"/_tempConfig.ini"
        file = open( tempConfig,'a' )
        file.write("registeredAPIExcel:"+g_registeredAPIExcel+"\n")
        file.close()
    except:
        errmsg = ''.join(traceback.format_exception(*sys.exc_info()))
        g_Log.writeLog(errmsg)
        return 0
    return 1


res = prepare()
if not res:
    print "执行用例prepare模块失败，结束用例{name}的执行".format(name=g_caseName)
else:
    run()
    clearup()

