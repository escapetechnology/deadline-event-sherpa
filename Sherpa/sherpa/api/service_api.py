# coding: utf-8

"""
    Sherpa API

    Sherpa API  # noqa: E501

    The version of the OpenAPI document: delivered
    Generated by: https://openapi-generator.tech
"""


from __future__ import absolute_import

import re  # noqa: F401

# python 2 and python 3 compatibility library
import six

from sherpa.api_client import ApiClient
from sherpa.exceptions import (  # noqa: F401
    ApiTypeError,
    ApiValueError
)


class ServiceApi(object):
    """NOTE: This class is auto generated by OpenAPI Generator
    Ref: https://openapi-generator.tech

    Do not edit the class manually.
    """

    def __init__(self, api_client=None):
        if api_client is None:
            api_client = ApiClient()
        self.api_client = api_client

    def get_service_collection(self, **kwargs):  # noqa: E501
        """Retrieves the collection of Service resources.  # noqa: E501

        This method makes a synchronous HTTP request by default. To make an
        asynchronous HTTP request, please pass async_req=True

        >>> thread = api.get_service_collection(async_req=True)
        >>> result = thread.get()

        :param provider:
        :type provider: str
        :param page: The collection page number
        :type page: int
        :param items_per_page: The number of items per page
        :type items_per_page: int
        :param pagination: Enable or disable pagination
        :type pagination: bool
        :param async_req: Whether to execute the request asynchronously.
        :type async_req: bool, optional
        :param _preload_content: if False, the urllib3.HTTPResponse object will
                                 be returned without reading/decoding response
                                 data. Default is True.
        :type _preload_content: bool, optional
        :param _request_timeout: timeout setting for this request. If one
                                 number provided, it will be total request
                                 timeout. It can also be a pair (tuple) of
                                 (connection, read) timeouts.
        :return: Returns the result object.
                 If the method is called asynchronously,
                 returns the request thread.
        :rtype: InlineResponse2002
        """
        kwargs['_return_http_data_only'] = True
        return self.get_service_collection_with_http_info(**kwargs)  # noqa: E501

    def get_service_collection_with_http_info(self, **kwargs):  # noqa: E501
        """Retrieves the collection of Service resources.  # noqa: E501

        This method makes a synchronous HTTP request by default. To make an
        asynchronous HTTP request, please pass async_req=True

        >>> thread = api.get_service_collection_with_http_info(async_req=True)
        >>> result = thread.get()

        :param provider:
        :type provider: str
        :param page: The collection page number
        :type page: int
        :param items_per_page: The number of items per page
        :type items_per_page: int
        :param pagination: Enable or disable pagination
        :type pagination: bool
        :param async_req: Whether to execute the request asynchronously.
        :type async_req: bool, optional
        :param _return_http_data_only: response data without head status code
                                       and headers
        :type _return_http_data_only: bool, optional
        :param _preload_content: if False, the urllib3.HTTPResponse object will
                                 be returned without reading/decoding response
                                 data. Default is True.
        :type _preload_content: bool, optional
        :param _request_timeout: timeout setting for this request. If one
                                 number provided, it will be total request
                                 timeout. It can also be a pair (tuple) of
                                 (connection, read) timeouts.
        :param _request_auth: set to override the auth_settings for an a single
                              request; this effectively ignores the authentication
                              in the spec for a single request.
        :type _request_auth: dict, optional
        :return: Returns the result object.
                 If the method is called asynchronously,
                 returns the request thread.
        :rtype: tuple(InlineResponse2002, status_code(int), headers(HTTPHeaderDict))
        """

        local_var_params = locals()

        all_params = [
            'provider',
            'page',
            'items_per_page',
            'pagination'
        ]
        all_params.extend(
            [
                'async_req',
                '_return_http_data_only',
                '_preload_content',
                '_request_timeout',
                '_request_auth'
            ]
        )

        for key, val in six.iteritems(local_var_params['kwargs']):
            if key not in all_params:
                raise ApiTypeError(
                    "Got an unexpected keyword argument '%s'"
                    " to method get_service_collection" % key
                )
            local_var_params[key] = val
        del local_var_params['kwargs']

        if self.api_client.client_side_validation and 'items_per_page' in local_var_params and local_var_params['items_per_page'] < 0:  # noqa: E501
            raise ApiValueError("Invalid value for parameter `items_per_page` when calling `get_service_collection`, must be a value greater than or equal to `0`")  # noqa: E501
        collection_formats = {}

        path_params = {}

        query_params = []
        if 'provider' in local_var_params and local_var_params['provider'] is not None:  # noqa: E501
            query_params.append(('provider', local_var_params['provider']))  # noqa: E501
        if 'page' in local_var_params and local_var_params['page'] is not None:  # noqa: E501
            query_params.append(('page', local_var_params['page']))  # noqa: E501
        if 'items_per_page' in local_var_params and local_var_params['items_per_page'] is not None:  # noqa: E501
            query_params.append(('itemsPerPage', local_var_params['items_per_page']))  # noqa: E501
        if 'pagination' in local_var_params and local_var_params['pagination'] is not None:  # noqa: E501
            query_params.append(('pagination', local_var_params['pagination']))  # noqa: E501

        header_params = {}

        form_params = []
        local_var_files = {}

        body_params = None
        # HTTP header `Accept`
        header_params['Accept'] = self.api_client.select_header_accept(
            ['application/ld+json'])  # noqa: E501

        # Authentication setting
        auth_settings = ['token']  # noqa: E501

        return self.api_client.call_api(
            '/services', 'GET',
            path_params,
            query_params,
            header_params,
            body=body_params,
            post_params=form_params,
            files=local_var_files,
            response_type='InlineResponse2002',  # noqa: E501
            auth_settings=auth_settings,
            async_req=local_var_params.get('async_req'),
            _return_http_data_only=local_var_params.get('_return_http_data_only'),  # noqa: E501
            _preload_content=local_var_params.get('_preload_content', True),
            _request_timeout=local_var_params.get('_request_timeout'),
            collection_formats=collection_formats,
            _request_auth=local_var_params.get('_request_auth'))
