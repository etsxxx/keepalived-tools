#!/usr/bin/python
# -*- coding: utf-8 -*-
'''
keepalived_checker.py
desc:
    check keeepalived.conf.
updated: 2017-08-24
'''
import os, sys, re
import glob
import optparse
version = "0.3.0"

options = None
def_conf_path = '/etc/keepalived/keepalived.conf'

regex_confline = re.compile(r'''^(?P<param>[^!#]+)(.*)$''', flags=re.IGNORECASE)
regex_include = re.compile(r'''^\s*include\s+(?P<path>[^\s]+).*$''', flags=re.IGNORECASE)


# config regex
regex_vrrp_instance = re.compile(r'''^\s*vrrp_instance\s+(?P<name>[^{\s]+).*$''', flags=re.IGNORECASE)
class VRRP_INSTANCE(dict):
    def __init__(self, name, index):
        dict.__init__(self)
        self['name'] = name
        self['index'] = index


regex_vrid = re.compile(r'''^\s*virtual_router_id\s+(?P<vrid>\d+).*$''', flags=re.IGNORECASE)
class VRID(dict):
    def __init__(self, vrid, index):
        dict.__init__(self)
        self['vrid'] = vrid
        self['index'] = index

regex_vip = re.compile(r'''^\s*(?P<vip>(\d{1,3}\.){3}\d{1,3}).*$''', flags=re.IGNORECASE)
class VIP(dict):
    def __init__(self, vip, index):
        dict.__init__(self)
        self['vip'] = vip
        self['index'] = index

regex_vs = re.compile(r'''^\s*virtual_server\s+(?P<vip>(\d{1,3}\.){3}\d{1,3})\s+(?P<port>\d+).*$''', flags=re.IGNORECASE)
class VirtrualServer(dict):
    def __init__(self, index, vip, port, proto='tcp'):
        dict.__init__(self)
        self['index'] = index
        self['vip'] = vip
        self['port'] = port
        self['proto'] = proto

regex_vsg = re.compile(r'''^\s*virtual_server_group\s+(?P<groupname>[^{\s]+).*$''', flags=re.IGNORECASE)
class VirtrualServerGroup(dict):
    def __init__(self, index, groupname):
        dict.__init__(self)
        self['index'] = index
        self['groupname'] = groupname

regex_vsg_endpoint = re.compile(r'''^\s*virtual_server\s+group\s+(?P<groupname>[^{\s]+).*$''', flags=re.IGNORECASE)
class VirtrualServerGroupEndpoint(dict):
    def __init__(self, index, groupname, proto='tcp'):
        dict.__init__(self)
        self['index'] = index
        self['groupname'] = groupname
        self['proto'] = proto

regex_protocol = re.compile(r'''^\s*protocol\s+(?P<proto>[^\s]+).*$''', flags=re.IGNORECASE)


class KeepalivedConfigChecker(object):
    conf_path = ""
    verbose = False

    vrrps = list()
    vrids = list()
    vips = list()
    virtual_servers = list()
    vsgs = list()
    vsg_endpoints = list()

    def __init__(self, conf_path, verbose=False):
        self.conf_path = conf_path
        self.verbose = verbose

    def __load(self, path=""):
        '''
        __load read configs with support include stetement,
        and remove comments or blank lines.
        returns:
            list of tupple(parameter, filename:index)
        '''
        conf_dir = os.path.dirname(path)

        try:
            num = 0
            config = list()

            if self.verbose:
                print("loading config file: '%s'" % path)
            for line in open(path):
                num += 1
                m = regex_confline.match(line)
                if m is None :
                    continue
                ### parse
                param = m.group('param').rstrip()
                m_include = regex_include.match(param)
                if m_include :
                    include_path = m_include.group('path')
                    for p in glob.glob('/'.join([conf_dir, include_path])):
                        config.extend(self.__load(p))
                else :
                    index = "%s:%i" % (path, num)
                    config.append((param, index))

            return config
        except Exception as e:
            raise e

    def parse_config(self):
        config = self.__load(path=self.conf_path)
        if self.verbose:
            print("loading config end")
            print("---")

        tmp_vs = None
        tmp_vsg = None
        tmp_vsg_endpoint = None
        in_vrrp = False

        nested = 0

        for line, index in config:
            nested += line.count('{')
            nested -= line.count('}')
            if nested == 0:
                # append previous info
                if tmp_vs:
                    self.virtual_servers.append(tmp_vs.copy())
                    if options.verbose:
                        print("virtual_server: '%(vip)s:%(port)s/%(proto)s' defined" % tmp_vs)
                if tmp_vsg:
                    self.vsgs.append(tmp_vsg.copy())
                    if options.verbose:
                        print("virtual_server_group: '%(groupname)s' defined" % tmp_vsg)
                if tmp_vsg_endpoint:
                    self.vsg_endpoints.append(tmp_vsg_endpoint.copy())
                    if options.verbose:
                        print("virtual_server_group backend: '%(groupname)s' defined with proto %(proto)s" % tmp_vsg_endpoint)

                # reset parameters
                tmp_vs = None
                tmp_vsg = None
                tmp_vsg_endpoint = None
                in_vrrp = False
            elif nested < 0:
                print("Error: config structure maybe wrong at: %s" % line)


            # vrrp_instance
            m = regex_vrrp_instance.match(line)
            if m :
                if self.verbose:
                    vrrp = VRRP_INSTANCE(
                        name=m.group('name'),
                        index=index
                    )
                    self.vrrps.append(vrrp)
                    if options.verbose:
                        print("vrrp_instance '%s' defined" % vrrp['name'] )
                in_vrrp = True
                continue

            if in_vrrp:
                # vrid
                m = regex_vrid.match(line)
                if m :
                    vrid = VRID(
                        vrid=m.group('vrid'),
                        index=index
                    )
                    self.vrids.append(vrid)
                    if options.verbose:
                        print("vrid: '%s' defined" % vrid['vrid'])

                    continue
                # vip
                m = regex_vip.match(line)
                if m :
                    vip = VIP(
                        index=index,
                        vip=m.group('vip')
                    )
                    self.vips.append(vip)
                    if options.verbose:
                        print("vip: '%s' defined" % vip['vip'])
                    continue

            # virtual_server
            m = regex_vs.match(line)
            if m :
                tmp_vs = VirtrualServer(
                    vip=m.group('vip'),
                    port=m.group('port'),
                    index=index
                )
                continue

            # virtual_server_group
            m = regex_vsg.match(line)
            if m :
                tmp_vsg = VirtrualServerGroup(
                    index=index,
                    groupname=m.group('groupname')
                )

            # virtual_server_group endpoint
            m = regex_vsg_endpoint.match(line)
            if m :
                tmp_vsg_endpoint = VirtrualServerGroupEndpoint(
                    groupname=m.group('groupname'),
                    index=index
                )
                continue

            # virtual_server proto
            m = regex_protocol.match(line)
            if m :
                if tmp_vs:
                    tmp_vs['proto'] = m.group('proto').lower()
                    continue
                if tmp_vsg_endpoint:
                    tmp_vsg_endpoint['proto'] = m.group('proto').lower()


        # append previous info finally
        if tmp_vs:
            self.virtual_servers.append(tmp_vs.copy())
            if options.verbose:
                print("virtual_server: '%(vip)s:%(port)s/%(proto)s' defined" % tmp_vs)
        if tmp_vsg:
            self.vsgs.append(tmp_vsg.copy())
            if options.verbose:
                print("virtual_server_group: '%(groupname)s' defined" % tmp_vsg)
        if tmp_vsg_endpoint:
            self.vsg_endpoints.append(tmp_vsg_endpoint.copy())
            if options.verbose:
                print("virtual_server_group backend: '%(groupname)s' defined with proto %(proto)s" % tmp_vsg_endpoint)

        if options.verbose:
            print("config parse end")
            print("---")
        return


    def check_vrrps(self):
        dups_vrrps = self.__check_vrrps_dup()
        dups_vrids = self.__check_vrids_dup()
        return (len(dups_vrrps) + len(dups_vrids)) == 0

    def __check_vrrps_dup(self):
        vrrp_list = list( map(lambda x: x['name'], self.vrrps) )
        unique_list = list(set(vrrp_list))

        for ele in unique_list:
            vrrp_list.remove(ele)

        if len(vrrp_list) > 0 :
            print("'vrrp_instance' duplications found:")
            for ele in vrrp_list:
                print("\t" + ele)
                for vrrp in self.vrrps:
                    if vrrp['name'] != ele :
                        continue
                    print("\t\t- %s" % vrrp['index'])
            print
        return vrrp_list

    def __check_vrids_dup(self):
        vrid_list = list( map(lambda x: x['vrid'], self.vrids) )
        unique_list = list(set(vrid_list))

        for ele in unique_list:
            vrid_list.remove(ele)

        if len(vrid_list) > 0 :
            print("'virtual_router_id' duplications found:")
            for ele in vrid_list:
                print("\t" + ele)
                for vrid in self.vrids:
                    if vrid['vrid'] != ele :
                        continue
                    print("\t\t- %s" % vrid['index'])
            print
        return vrid_list


    def check_vips(self):
        dups_vip = self.__check_vips_dup()
        dups_vs = self.__check_vs_dup()
        ng_vips = self.__check_vips_unmanaged()
        return (len(dups_vip) + len(dups_vs) + len(ng_vips)) == 0

    def __check_vips_dup(self):
        vip_list = map(lambda x: x['vip'], self.vips)
        unique_list = list(set(vip_list))

        for ele in unique_list:
            vip_list.remove(ele)

        if len(vip_list) > 0 :
            print("'virtual_ipaddress' duplications found:")
            for ele in vip_list:
                print("\t" + ele)
                for vip in self.vips:
                    if vip['vip'] != ele :
                        continue
                    print("\t\t- %s" % vip['index'])
            print

        return vip_list

    def __check_vs_dup(self):
        vs_list = map(lambda x: (x['vip'], x['port'], x['proto']), self.virtual_servers)
        unique_list = list(set(vs_list))

        for ele in unique_list:
            vs_list.remove(ele)

        if len(vs_list) > 0 :
            print("'virtual_server' duplications found:")
            for ele in vs_list:
                print("\t%s:%s/%s" % (ele))
                for vs in self.virtual_servers:
                    if (vs['vip'], vs['port'], vs['proto']) != ele :
                        continue
                    print("\t\t- %s" % vs['index'])
            print

        return vs_list


    def __check_vips_unmanaged(self):
        managed_list = map(lambda x: x['vip'], self.vips)
        unmanaged_list = list()

        for vs in self.virtual_servers:
            if vs['vip'] not in managed_list :
                unmanaged_list.append(vs)

        if len(unmanaged_list) > 0 :
            print("'virtual_server' uses unmanaged VIP:")
            for ele in unmanaged_list:
                print("\t%(vip)s:%(port)s" % vs)
                print("\t\t- %(index)s" % vs)
            print

        return unmanaged_list



    def check_vsgs(self):
        dups_vsg = self.__check_vsgs_dup()
        dups_vsge = self.__check_vsg_endpoints_dup()
        ng_vsg_endpoints = self.__check_vsgs_unmanaged()
        return (len(dups_vsg) + len(dups_vsge) + len(ng_vsg_endpoints)) == 0


    def __check_vsgs_dup(self):
        vsg_list = map(lambda x: x['groupname'], self.vsgs)
        unique_list = list(set(vsg_list))

        for ele in unique_list:
            vsg_list.remove(ele)

        if len(vsg_list) > 0 :
            print("'virtual_server_group XXXXX' duplications found:")
            for ele in vsg_list:
                print("\t" + ele)
                for vsg in self.vsgs:
                    if vsg['groupname'] != ele:
                        continue
                    print("\t\t- %s" % vsg['index'])
            print

        return vsg_list

    def __check_vsg_endpoints_dup(self):
        vsge_list = map(lambda x: x['groupname'], self.vsg_endpoints)
        unique_list = list(set(vsge_list))

        for ele in unique_list:
            vsge_list.remove(ele)

        if len(vsge_list) > 0 :
            print("'virtual_server group XXXXX' duplications found:")
            for ele in vsge_list:
                print("\t" + ele)
                for vsge in self.vsg_endpoints:
                    if vsge['groupname'] != ele:
                        continue
                    print("\t\t- %s" % vsge['index'])
            print
        return vsge_list

    def __check_vsgs_unmanaged(self):
        managed_list = map(lambda x: x['groupname'], self.vsgs)
        unmanaged_list = list()

        for vsge in self.vsg_endpoints:
            if vsge['groupname'] not in managed_list :
                unmanaged_list.append(vsge)

        if len(unmanaged_list) > 0 :
            print("'virtual_server group' uses undefined group name:")
            for vsge in unmanaged_list:
                print("\t%(groupname)s:%(proto)s\t\t- %(index)s" % vsge)
            print

        return unmanaged_list




if __name__ == "__main__":
    import optparse
    usage = """usage: %prog [options]"""

    parser = optparse.OptionParser(usage=usage, version=version)
    parser.add_option(
        "-f", "--file",
        action="store",
        dest="conf_path",
        default=def_conf_path,
        help="set keepalived config file path. (default:%s)" % def_conf_path
    )
    parser.add_option(
        "-v", "--verbose",
        action="store_true",
        dest="verbose",
        default=False,
        help="verbose mode"
    )
    (options, args) = parser.parse_args()
    if len(args) != 0 :
        parser.print_help()
        sys.exit(3)

    checker = KeepalivedConfigChecker(conf_path=options.conf_path, verbose=options.verbose)
    checker.parse_config()

    ret = 0
    if not checker.check_vrrps():
        ret = 1
    if not checker.check_vips():
        ret = 1
    if not checker.check_vsgs():
        ret = 1

    if ret == 0 :
        print("OK")
    else:
        print("NG")
    sys.exit(ret)
