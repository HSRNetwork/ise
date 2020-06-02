"""Class to configure Cisco ISE via the ERS API."""
import json
import os
import re
from furl import furl

import requests

base_dir = os.path.dirname(__file__)


class InvalidMacAddress(Exception):
    def __init__(self, value):
        self.value = value

    def __str__(self):
        return repr(self.value)


class ERS(object):
    def __init__(self, ise_node, ers_user, ers_pass, verify=False, disable_warnings=False, timeout=2, protocol='https'):
        """
        Class to interact with Cisco ISE via the ERS API.

        :param ise_node: IP Address of the primary admin ISE node
        :param ers_user: ERS username
        :param ers_pass: ERS password
        :param verify: Verify SSL cert
        :param disable_warnings: Disable requests warnings
        :param timeout: Query timeout
        """
        self.ise_node = ise_node
        self.user_name = ers_user
        self.user_pass = ers_pass
        self.protocol = protocol

        self.url_base = '{0}://{1}:9060/ers'.format(self.protocol, self.ise_node)
        self.ise = requests.session()
        self.ise.auth = (self.user_name, self.user_pass)
        # http://docs.python-requests.org/en/latest/user/advanced/#ssl-cert-verification
        self.ise.verify = verify
        self.disable_warnings = disable_warnings
        self.timeout = timeout
        self.ise.headers.update({'Connection': 'keep_alive'})

        if self.disable_warnings:
            requests.packages.urllib3.disable_warnings()

    @staticmethod
    def _mac_test(mac):
        """
        Test for valid mac address.

        :param mac: MAC address in the form of AA:BB:CC:00:11:22
        :return: True/False
        """
        if re.search(r'([0-9A-F]{2}[:]){5}([0-9A-F]){2}', mac.upper()) is not None:
            return True
        else:
            return False

    @staticmethod
    def _pass_ersresponse(result, resp):
        result['response'] = resp.json()['ERSResponse']['messages'][0]['title']
        result['error'] = resp.status_code
        return result

    def _get_groups(self, url, filter: str = None, size: int = 20, page: int = 1):
        """
        Get generic group lists.

        :param url: Base URL for requesting lists
        :param size: size of the page to return. Default: 20
        :param page: page to return. Default: 1
        :return: result dictionary
        """
        result = {
            'success': False,
            'response': '',
            'error': '',
        }

        # https://github.com/gruns/furl
        f = furl(url)
        # TODO test for valid size 1<=x>=100
        f.args['size'] = size
        # TODO test for valid page number?
        f.args['page'] = page
        # TODO add filter valication
        if filter:
            f.args['filter'] = filter

        self.ise.headers.update(
            {'ACCEPT': 'application/json', 'Content-Type': 'application/json'})
        resp = self.ise.get(f.url)

        if resp.status_code == 200:
            result['success'] = True
            result['response'] = [(i['name'], i['id'], i['description'])
                                  for i in resp.json()['SearchResult']['resources']]
            return result
        else:
            return ERS._pass_ersresponse(result, resp)

    def _get_objects(self, url, filter: str = None, size: int = 20, page: int = 1):
        """
        Generic method for requesting objects lists.

        :param url: Base URL for requesting lists
        :param filter: argument side of a ERS filter string. Default: None
        :param size: size of the page to return. Default: 20
        :param page: page to return. Default: 1
        :return: result dictionary
        """
        result = {
            'success': False,
            'response': '',
            'error': '',
        }

        self.ise.headers.update(
            {'Accept': 'application/json', 'Content-Type': 'application/json'})

        f = furl(url)
        # TODO test for valid size 1<=x>=100
        f.args['size'] = size
        # TODO test for valid page number?
        f.args['page'] = page
        # TODO add filter valication
        if filter:
            f.args['filter'] = filter

        resp = self.ise.get(f.url)

        # TODO add dynamic paging?
        if resp.status_code == 200:
            json_res = resp.json()['SearchResult']
            if int(json_res['total']) >= 1:
                result['success'] = True
                result['response'] = [(i['name'], i['id'])
                                      for i in json_res['resources']]
                return result

            elif int(json_res['total']) == 0:
                result['success'] = True
                result['response'] = []
                return result
        else:
            return ERS._pass_ersresponse(result, resp)

    def get_endpoint_groups(self, size):
        """
        Get all endpoint identity groups.

        :param size: Size of the number of identity groups before pagination starts
        :return: result dictionary
        """
        return self._get_groups('{0}/config/endpointgroup'.format(self.url_base), size=size)

    def get_endpoint_group(self, group):
        """
        Get endpoint identity group details.

        :param group: Name of the identity group
        :return: result dictionary
        """
        self.ise.headers.update(
            {'ACCEPT': 'application/json', 'Content-Type': 'application/json'})

        result = {
            'success': False,
            'response': '',
            'error': '',
        }

        resp = self.ise.get(
            '{0}/config/endpointgroup?filter=name.EQ.{1}'.format(self.url_base, group))
        found_group = resp.json()

        if found_group['SearchResult']['total'] == 1:
            result = self.get_object('{0}/config/endpointgroup'.format(self.url_base), found_group['SearchResult']['resources'][0]['id'], "EndPointGroup")  # noqa E501

            return result
        else:
            return ERS._pass_ersresponse(result, resp)

    def get_endpoints(self, groupID=None):
        """
        Get all endpoints.

        :param groupID: List only endpoints in a specific GroupID. Default: None
        :return: result dictionary
        """
        if groupID:
            filter = 'groupId.EQ.{1}'.format(groupID)
        else:
            filter = None

        return self._get_objects('{0}/config/endpoint'.format(self.url_base), filter)

    def get_object(self, url: str, objectid: str, objecttype: str):
        """
        Get generic object lists.

        :param url: Base URL for requesting lists
        :param objectid: ID retreved from previous search.
        :param objecttype: "ERSEndPoint", etc...
        :return: result dictionary
        """
        result = {
            'success': False,
            'response': '',
            'error': '',
        }

        self.ise.headers.update(
            {'Accept': 'application/json', 'Content-Type': 'application/json'})

        f = furl(url)
        f.path /= objectid
        resp = self.ise.get(f.url)

        if resp.status_code == 200:
            result['success'] = True
            result['response'] = resp.json()[objecttype]
            return result
        else:
            return ERS._pass_ersresponse(result, resp)

    def get_endpoint(self, mac_address):
        """
        Get endpoint details.

        :param mac_address: MAC address of the endpoint
        :return: result dictionary
        """
        is_valid = ERS._mac_test(mac_address)

        if not is_valid:
            raise InvalidMacAddress(
                '{0}. Must be in the form of AA:BB:CC:00:11:22'.format(mac_address))
        else:
            self.ise.headers.update(
                {'ACCEPT': 'application/json', 'Content-Type': 'application/json'})

            result = {
                'success': False,
                'response': '',
                'error': '',
            }

            resp = self.ise.get(
                '{0}/config/endpoint?filter=mac.EQ.{1}'.format(self.url_base, mac_address))
            found_endpoint = resp.json()

            if found_endpoint['SearchResult']['total'] == 1:
                result = self.get_object('{0}/config/endpoint/'.format(self.url_base), found_endpoint['SearchResult']['resources'][0]['id'], 'ERSEndPoint')  # noqa E501
                return result
            elif found_endpoint['SearchResult']['total'] == 0:
                result['response'] = '{0} not found'.format(mac_address)
                result['error'] = 404
                return result

            else:
                result['response'] = '{0} not found'.format(mac_address)
                result['error'] = resp.status_code
                return result

    def add_endpoint(self,
                     name,
                     mac,
                     group_id,
                     static_profile_assigment='false',
                     static_group_assignment='true',
                     profile_id='',
                     description='',
                     portalUser='',
                     customAttributes={}):
        """
        Add a user to the local user store.

        :param name: Name
        :param mac: Macaddress
        :param group_id: OID of group to add endpoint in
        :param static_profile_assigment: Set static profile
        :param static_group_assignment: Set static group
        :param profile_id: OID of profile
        :param description: User description
        :param portaluser: Portal username
        :param customAttributes: key value pairs of custom attributes
        :return: result dictionary
        """
        is_valid = ERS._mac_test(mac)
        if not is_valid:
            raise InvalidMacAddress(
                '{0}. Must be in the form of AA:BB:CC:00:11:22'.format(mac))
        else:
            self.ise.headers.update(
                {'ACCEPT': 'application/json', 'Content-Type': 'application/json'})

            result = {
                'success': False,
                'response': '',
                'error': '',
            }

            data = {"ERSEndPoint": {'name': name, 'description': description, 'mac': mac,
                                    'profileId': profile_id, 'staticProfileAssignment': static_profile_assigment,
                                    'groupId': group_id, 'staticGroupAssignment': static_group_assignment,
                                    'portalUser': portalUser, 'customAttributes': {'customAttributes': customAttributes}
                                    }
                    }

            resp = self.ise.post('{0}/config/endpoint'.format(self.url_base),
                                 data=json.dumps(data), timeout=self.timeout)
            if resp.status_code == 201:
                result['success'] = True
                result['response'] = '{0} Added Successfully'.format(name)
                return result
            else:
                return ERS._pass_ersresponse(result, resp)

    def delete_endpoint(self, mac):
        """
        Delete an endpoint.

        :param mac: Endpoint Macaddress
        :return: Result dictionary
        """
        self.ise.headers.update(
            {'ACCEPT': 'application/json', 'Content-Type': 'application/json'})

        result = {
            'success': False,
            'response': '',
            'error': '',
        }

        resp = self.ise.get(
            '{0}/config/endpoint?filter=mac.EQ.{1}'.format(self.url_base, mac))
        found_endpoint = resp.json()
        if found_endpoint['SearchResult']['total'] == 1:
            endpoint_oid = found_endpoint['SearchResult']['resources'][0]['id']
            resp = self.ise.delete(
                '{0}/config/endpoint/{1}'.format(self.url_base, endpoint_oid), timeout=self.timeout)

            if resp.status_code == 204:
                result['success'] = True
                result['response'] = '{0} Deleted Successfully'.format(mac)
                return result
            elif resp.status_code == 404:
                result['response'] = '{0} not found'.format(mac)
                result['error'] = resp.status_code
                return result
            else:
                return ERS._pass_ersresponse(result, resp)
        elif found_endpoint['SearchResult']['total'] == 0:
            result['response'] = '{0} not found'.format(mac)
            result['error'] = 404
            return result
        else:
            return ERS._pass_ersresponse(result, resp)

    def get_identity_groups(self, filter=None):
        """
        Get all identity groups.

        :param filter: ISE style filter syntax. Default: None
        :return: result dictionary
        """
        return self._get_groups('{0}/config/identitygroup'.format(self.url_base), filter=filter)

    def get_identity_group(self, group):
        """
        Get identity group details.

        :param group: Name of the identity group
        :return: result dictionary
        """
        self.ise.headers.update(
            {'ACCEPT': 'application/json', 'Content-Type': 'application/json'})

        result = {
            'success': False,
            'response': '',
            'error': '',
        }

        resp = self.ise.get(
            '{0}/config/identitygroup?filter=name.EQ.{1}'.format(self.url_base, group))
        found_group = resp.json()

        if found_group['SearchResult']['total'] == 1:
            result = self.get_object('{0}/config/identitygroup/'.format(
                self.url_base), found_group['SearchResult']['resources'][0]['id'], 'IdentityGroup')
            return result
        elif found_group['SearchResult']['total'] == 0:
            result['response'] = '{0} not found'.format(group)
            result['error'] = 404
            return result

        else:
            result['response'] = '{0} not found'.format(group)
            result['error'] = resp.status_code
            return result

    def get_users(self):
        """
        Get all internal users.

        :return: List of tuples of user details
        """
        return self._get_objects('{0}/config/internaluser'.format(self.url_base))

    def get_user(self, user_id):
        """
        Get user detailed info.

        :param user_id: User ID
        :return: result dictionary
        """
        self.ise.headers.update(
            {'ACCEPT': 'application/json', 'Content-Type': 'application/json'})

        result = {
            'success': False,
            'response': '',
            'error': '',
        }

        resp = self.ise.get(
            '{0}/config/internaluser?filter=name.EQ.{1}'.format(self.url_base, user_id))
        found_user = resp.json()

        if found_user['SearchResult']['total'] == 1:
            result = self.get_object('{0}/config/internaluser/'.format(
                self.url_base), found_user['SearchResult']['resources'][0]['id'], 'InternalUser')
            return result
        elif found_user['SearchResult']['total'] == 0:
            result['response'] = '{0} not found'.format(user_id)
            result['error'] = 404
            return result
        else:
            result['response'] = 'Unknown error'
            result['error'] = resp.status_code
            return result

    def add_user(self,
                 user_id,
                 password,
                 user_group_oid,
                 enable='',
                 first_name='',
                 last_name='',
                 email='',
                 description=''):
        """
        Add a user to the local user store.

        :param user_id: User ID
        :param password: User password
        :param user_group_oid: OID of group to add user to
        :param enable: Enable password used for Tacacs
        :param first_name: First name
        :param last_name: Last name
        :param email: email address
        :param description: User description
        :return: result dictionary
        """
        result = {
            'success': False,
            'response': '',
            'error': '',
        }

        self.ise.headers.update(
            {'ACCEPT': 'application/json', 'Content-Type': 'application/json'})

        data = {"InternalUser": {'name': user_id, 'password': password, 'enablePassword': enable,
                                 'firstName': first_name, 'lastName': last_name, 'email': email,
                                 'description': description, 'identityGroups': user_group_oid}}

        resp = self.ise.post('{0}/config/internaluser'.format(self.url_base),
                             data=json.dumps(data), timeout=self.timeout)
        if resp.status_code == 201:
            result['success'] = True
            result['response'] = '{0} Added Successfully'.format(user_id)
            return result
        else:
            return ERS._pass_ersresponse(result, resp)

    def delete_user(self, user_id):
        """
        Delete a user.

        :param user_id: User ID
        :return: Result dictionary
        """
        self.ise.headers.update(
            {'ACCEPT': 'application/json', 'Content-Type': 'application/json'})

        result = {
            'success': False,
            'response': '',
            'error': '',
        }

        resp = self.ise.get(
            '{0}/config/internaluser?filter=name.EQ.{1}'.format(self.url_base, user_id))
        found_user = resp.json()

        if found_user['SearchResult']['total'] == 1:
            user_oid = found_user['SearchResult']['resources'][0]['id']
            resp = self.ise.delete(
                '{0}/config/internaluser/{1}'.format(self.url_base, user_oid), timeout=self.timeout)

            if resp.status_code == 204:
                result['success'] = True
                result['response'] = '{0} Deleted Successfully'.format(user_id)
                return result
            elif resp.status_code == 404:
                result['response'] = '{0} not found'.format(user_id)
                result['error'] = resp.status_code
                return result
            else:
                return ERS._pass_ersresponse(result, resp)
        elif found_user['SearchResult']['total'] == 0:
            result['response'] = '{0} not found'.format(user_id)
            result['error'] = 404
            return result
        else:
            return ERS._pass_ersresponse(result, resp)

    def get_device_groups(self):
        """
        Get a list tuples of device groups.

        :return:
        """
        return self._get_groups('{0}/config/networkdevicegroup'.format(self.url_base))

    def get_device_group(self, device_group_oid):
        """
        Get a device group details.

        :param device_group_oid: oid of the device group
        :return: result dictionary
        """
        self.ise.headers.update(
            {'ACCEPT': 'application/json', 'Content-Type': 'application/json'})

        return self.get_object('{0}/config/networkdevicegroup/'.format(self.url_base), device_group_oid, 'NetworkDeviceGroup')  # noqa E501

    def get_devices(self, filter=None):
        """
        Get a list of devices.

        :return: result dictionary
        """
        return self._get_objects('{0}/config/networkdevice'.format(self.url_base), filter)

    def get_device(self, device):
        """
        Get a device detailed info.

        :param device: device_name
        :return: result dictionary
        """
        self.ise.headers.update(
            {'ACCEPT': 'application/json', 'Content-Type': 'application/json'})

        result = {
            'success': False,
            'response': '',
            'error': '',
        }

        resp = self.ise.get(
            '{0}/config/networkdevice?filter=name.EQ.{1}'.format(self.url_base, device))
        found_device = resp.json()

        if found_device['SearchResult']['total'] == 1:
            result = self.get_object('{0}/config/networkdevice/'.format(self.url_base),
                                     found_device['SearchResult']['resources'][0]['id'], 'NetworkDevice')  # noqa E501
            return result
        elif found_device['SearchResult']['total'] == 0:
            result['response'] = '{0} not found'.format(device)
            result['error'] = 404
            return result
        else:
            return ERS._pass_ersresponse(result, resp)

    def add_device(self,
                   name,
                   ip_address,
                   radius_key=None,
                   snmp_ro=None,
                   dev_groups=None,
                   description=None,
                   snmp_v='TWO_C',
                   dev_profile=None,
                   tacacs_shared_secret=None,
                   tacas_connect_mode_options='ON_LEGACY',
                   coa_port=None
                   ):
        """
        Add a device.

        :param name: name of device
        :param ip_address: IP address of device
        :param radius_key: Radius shared secret
        :param snmp_ro: SNMP read only community string
        :param dev_group: Device group name
        :param dev_location: Device location
        :param dev_type: Device type
        :param description: Device description
        :param dev_profile: Device profile
        :return: Result dictionary
        """
        result = {
            'success': False,
            'response': '',
            'error': '',
        }

        self.ise.headers.update(
            {'ACCEPT': 'application/json', 'Content-Type': 'application/json'})

        data = {
            'NetworkDevice': {
                'name': name,
                'NetworkDeviceIPList': [{'ipaddress': ip_address, 'mask': 32}]
            }
        }

        if description is not None:
            data['NetworkDevice']['description'] = description
        if radius_key is not None:
            data['NetworkDevice']['authenticationSettings'] = {
                'networkProtocol': 'RADIUS',
                'radiusSharedSecret': radius_key,
                'enableKeyWrap': 'false',
            }
        if snmp_ro is not None:
            data['NetworkDevice']['snmpsettings'] = {
                'version': snmp_v,
                'roCommunity': snmp_ro,
                'pollingInterval': 3600,
                'linkTrapQuery': 'true',
                'macTrapQuery': 'true',
                'originatingPolicyServicesNode': 'Auto'
            }
        if dev_profile is not None:
            data['NetworkDevice']['profileName'] = dev_profile
        if coa_port is not None:
            data['NetworkDevice']['coaPort'] = coa_port
        if dev_groups is not None:
            data['NetworkDevice']['NetworkDeviceGroupList'] = dev_groups
        if tacacs_shared_secret is not None:
            data['NetworkDevice']['tacacsSettings'] = {
              'sharedSecret': tacacs_shared_secret,
              'connectModeOptions': tacas_connect_mode_options
            }

        resp = self.ise.post('{0}/config/networkdevice'.format(self.url_base),
                             data=json.dumps(data), timeout=self.timeout)

        if resp.status_code == 201:
            result['success'] = True
            result['response'] = '{0} Added Successfully'.format(name)
            return result
        else:
            return ERS._pass_ersresponse(result, resp)

    def delete_device(self, device):
        """
        Delete a device.

        :param device: device_name
        :return: Result dictionary
        """
        self.ise.headers.update(
            {'ACCEPT': 'application/json', 'Content-Type': 'application/json'})

        result = {
            'success': False,
            'response': '',
            'error': '',
        }

        resp = self.ise.get(
            '{0}/config/networkdevice?filter=name.EQ.{1}'.format(self.url_base, device))
        found_device = resp.json()
        if found_device['SearchResult']['total'] == 1:
            device_oid = found_device['SearchResult']['resources'][0]['id']
            resp = self.ise.delete(
                '{0}/config/networkdevice/{1}'.format(self.url_base, device_oid), timeout=self.timeout)

            if resp.status_code == 204:
                result['success'] = True
                result['response'] = '{0} Deleted Successfully'.format(device)
                return result
            elif resp.status_code == 404:
                result['response'] = '{0} not found'.format(device)
                result['error'] = resp.status_code
                return result
            else:
                return ERS._pass_ersresponse(result, resp)
        elif found_device['SearchResult']['total'] == 0:
            result['response'] = '{0} not found'.format(device)
            result['error'] = 404
            return result
        else:
            return ERS._pass_ersresponse(result, resp)

    def get_nodes(self):
        """
        Get all nodes.
        :return: result dictionary
        """
        return self._get_objects('{0}/config/node'.format(self.url_base))

    def get_node_details(self, node_id):
        """
         Get the details of a node.
         :param node_id the id of the node to fetch
         :return: the details of the node
         """
        return self.get_object('{0}/config/node/'.format(
            self.url_base), node_id, 'Node')

    def get_node_details_by_name(self, name):
        """
         Get the details of a node by its name.
         :param name the name of the node to fetch
         :return: the details of the node
         """
        return self.get_object('{0}/config/node/name/'.format(
            self.url_base), name, 'Node')
