import random
import sys

from Deadline.Scripting import RepositoryUtils

eventPath = RepositoryUtils.GetEventPluginDirectory("Sherpa")

if eventPath not in sys.path:
    sys.path.append(eventPath)

# "ImportError : No module named certifi (Deadline.Events.DeadlineEventPluginException)"
# Import the (local) [certifi](https://github.com/certifi/python-certifi),
# as not available in OOTB Deadline installation...
import certifi

import sherpa
from sherpa.rest import ApiException

#  ____                 _ _ _                      ____  _                                _    ____ ___
# |  _ \  ___  __ _  __| | (_)_ __   ___     _    / ___|| |__   ___ _ __ _ __   __ _     / \  |  _ \_ _|
# | | | |/ _ \/ _` |/ _` | | | '_ \ / _ \  _| |_  \___ \| '_ \ / _ \ '__| '_ \ / _` |   / _ \ | |_) | |
# | |_| |  __/ (_| | (_| | | | | | |  __/ |_   _|  ___) | | | |  __/ |  | |_) | (_| |  / ___ \|  __/| |
# |____/ \___|\__,_|\__,_|_|_|_| |_|\___|   |_|   |____/|_| |_|\___|_|  | .__/ \__,_| /_/   \_\_|  |___|
#
# This utils class is the glue between callouts in the Deadline Sherpa event plugin and the Sherpa Python SDK;
# the underlying idea is to have the communication with the Sherpa API (via the SDK) separated out from any Deadline specific logic
#

TENURE_ONDEMAND = "on-demand"
TENURE_SPOT = "spot"

OPERATION_START = "start"
OPERATION_STOP = "stop"

MARKING_DELETING = "deleting"
MARKING_DELETED = "deleted"

def Authenticate(endpoint, key, secret):
    configuration = sherpa.Configuration(
        host = endpoint
    )

    api_instance = sherpa.AuthenticationApi(sherpa.ApiClient(configuration))

    body = sherpa.Authentication(username=key, password=secret)

    try:
        api_response = api_instance.login_collection(authentication=body)

        configuration = sherpa.Configuration(
            host = endpoint,
            api_key = {
                'token': 'Bearer ' + api_response.token
            }
        )

        return sherpa.ApiClient(configuration)
    except ApiException as e:
        print("Exception when calling AuthenticationApi->login_collection: %s\n" % e)

    return None

def ResourceHasOperation(apiClient, resourceID, operation):
    api_instance = sherpa.NodeApi(apiClient)

    needle = operation

    try:
        api_response = api_instance.get_node_item(resourceID)

        for operation in api_response.operations:
            if operation["name"] == needle:
                return True

                break
    except ApiException as e:
        print("Exception when calling NodeApi->get_node_item: %s\n" % e)

    return False

def ResourceHasEnabledOperation(apiClient, resourceID, enabled_operation):
    api_instance = sherpa.NodeApi(apiClient)

    needle = enabled_operation

    try:
        api_response = api_instance.get_node_item(resourceID)

        for enabled_operation in api_response.enabled_operations:
            if enabled_operation == needle:
                return True

                break
    except ApiException as e:
        print("Exception when calling NodeApi->get_node_item: %s\n" % e)

    return False

def GetResourceName(apiClient, resourceID):
    api_instance = sherpa.NodeApi(apiClient)

    try:
        api_response = api_instance.get_node_item(resourceID)

        return api_response.name
    except ApiException as e:
        print("Exception when calling NodeApi->get_node_item: %s\n" % e)

    return None

def GetResourceTenure(apiClient, resourceID):
    api_instance = sherpa.NodeApi(apiClient)

    try:
        api_response = api_instance.get_node_item(resourceID)

        return GetSizeTenure(apiClient, GetResourceSizeID(api_response))
    except ApiException as e:
        print("Exception when calling NodeApi->get_node_item: %s\n" % e)

    return None

def GetResourceSizeID(resource):
    return resource.size.replace("/sizes/", "")

def GetSizeTenure(apiClient, sizeID):
    api_instance = sherpa.SizeApi(apiClient)

    try:
        api_response = api_instance.get_size_item(id=sizeID)

        return api_response.tenure
    except ApiException as e:
        print("Exception when calling SizeApi->get_size_collection: %s\n" % e)

    return None

def GetResources(apiClient, projectID):
    api_instance = sherpa.NodeApi(apiClient)

    try:
        api_response = api_instance.get_node_collection(project=projectID, pagination=False)

        return api_response.hydramember
    except ApiException as e:
        print("Exception when calling NodeApi->get_node_collection: %s\n" % e)

    return []

def GetResourceMarking(apiClient, resourceID):
    api_instance = sherpa.NodeApi(apiClient)

    try:
        api_response = api_instance.get_node_item(id=resourceID)

        return api_response.marking
    except ApiException as e:
        print("Exception when calling NodeApi->get_node_item: %s\n" % e)

    return None

def StartResources(apiClient, resourceIDs):
    if resourceIDs == None or len(resourceIDs) == 0:
        return

    api_instance = sherpa.NodeApi(apiClient)

    for i in range(0, len(resourceIDs)):
        resourceID = resourceIDs[i]

        node = sherpa.Node()
        node.marking = OPERATION_START

        try:
            api_instance.put_node_item(resourceID, node=node)
        except ApiException as e:
            print("Exception when calling NodeApi->put_node_item: %s\n" % e)

def StopResources(apiClient, resourceIDs):
    if resourceIDs == None or len(resourceIDs) == 0:
        return

    api_instance = sherpa.NodeApi(apiClient)

    for i in range(0, len(resourceIDs)):
        resourceID = resourceIDs[i]

        node = sherpa.Node()
        node.marking = OPERATION_STOP

        try:
            api_instance.put_node_item(resourceID, node=node)
        except ApiException as e:
            print("Exception when calling NodeApi->put_node_item: %s\n" % e)

def CreateResources(apiClient, projectID, prefix, sizeID, imageID, volumeSize, count):
    try:
        api_instance = sherpa.ProjectApi(apiClient)
        api_response = api_instance.get_project_item(id=projectID)

        providerID = api_response.providers[0].replace("/providers/", "")
        regionID = api_response.regions[0].replace("/regions/", "")

        service_api_instance = sherpa.ServiceApi(apiClient)

        try:
            service_api_response = service_api_instance.get_service_collection(provider=providerID, pagination=False)

            for element in service_api_response.hydramember:
                if element.type == "NodeService":
                    serviceID = element.id

                    break
        except ApiException as e:
            print("Exception when calling ServiceApi->get_service_collection: %s\n" % e)

        r = lambda: random.randint(0, 255)

        nodes = []

        for i in range(count):
            name = prefix + "-" + ("%02X%02X%02X%02X%02X" % (r(), r(), r(), r(), r()))
            name = name.lower()

            nodes.append({
                "name": name,
                "description": "",
                "service": "/services/"+serviceID,
                "region": "/regions/"+regionID,
                "image": "/images/"+imageID,
                "size": "/sizes/"+sizeID,
                "volumeSize": volumeSize,
            })

        api_instance = sherpa.ProjectApi(apiClient)

        project_nodes = sherpa.ProjectNodes()
        project_nodes.nodes = nodes

        try:
            api_instance.post_nodes_project_item(projectID, project_nodes=project_nodes)
        except ApiException as e:
            print("Exception when calling ProjectApi->post_nodes_project_item: %s\n" % e)

    except ApiException as e:
        print("Exception when calling ProjectApi->get_project_item: %s\n" % e)

def DeleteResources(apiClient, resourceIDs):
    if resourceIDs == None or len(resourceIDs) == 0:
        return

    for i in range(0, len(resourceIDs)):
        resourceID = resourceIDs[i]

        api_instance = sherpa.NodeApi(apiClient)

        try:
            api_instance.delete_node_item(resourceID)
        except ApiException as e:
            print("Exception when calling NodeApi->delete_node_item: %s\n" % e)
