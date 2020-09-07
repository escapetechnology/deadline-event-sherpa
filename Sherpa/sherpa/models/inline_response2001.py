# coding: utf-8

"""
    Sherpa API

    Sherpa API  # noqa: E501

    The version of the OpenAPI document: delivered
    Generated by: https://openapi-generator.tech
"""


import pprint
import re  # noqa: F401

import six

from sherpa.configuration import Configuration


class InlineResponse2001(object):
    """NOTE: This class is auto generated by OpenAPI Generator.
    Ref: https://openapi-generator.tech

    Do not edit the class manually.
    """

    """
    Attributes:
      openapi_types (dict): The key is attribute name
                            and the value is attribute type.
      attribute_map (dict): The key is attribute name
                            and the value is json key in definition.
    """
    openapi_types = {
        'hydramember': 'list[Project]',
        'hydratotal_items': 'int',
        'hydraview': 'InlineResponse200HydraView',
        'hydrasearch': 'InlineResponse200HydraSearch'
    }

    attribute_map = {
        'hydramember': 'hydra:member',
        'hydratotal_items': 'hydra:totalItems',
        'hydraview': 'hydra:view',
        'hydrasearch': 'hydra:search'
    }

    def __init__(self, hydramember=None, hydratotal_items=None, hydraview=None, hydrasearch=None, local_vars_configuration=None):  # noqa: E501
        """InlineResponse2001 - a model defined in OpenAPI"""  # noqa: E501
        if local_vars_configuration is None:
            local_vars_configuration = Configuration()
        self.local_vars_configuration = local_vars_configuration

        self._hydramember = None
        self._hydratotal_items = None
        self._hydraview = None
        self._hydrasearch = None
        self.discriminator = None

        self.hydramember = hydramember
        if hydratotal_items is not None:
            self.hydratotal_items = hydratotal_items
        if hydraview is not None:
            self.hydraview = hydraview
        if hydrasearch is not None:
            self.hydrasearch = hydrasearch

    @property
    def hydramember(self):
        """Gets the hydramember of this InlineResponse2001.  # noqa: E501


        :return: The hydramember of this InlineResponse2001.  # noqa: E501
        :rtype: list[Project]
        """
        return self._hydramember

    @hydramember.setter
    def hydramember(self, hydramember):
        """Sets the hydramember of this InlineResponse2001.


        :param hydramember: The hydramember of this InlineResponse2001.  # noqa: E501
        :type hydramember: list[Project]
        """
        if self.local_vars_configuration.client_side_validation and hydramember is None:  # noqa: E501
            raise ValueError("Invalid value for `hydramember`, must not be `None`")  # noqa: E501

        self._hydramember = hydramember

    @property
    def hydratotal_items(self):
        """Gets the hydratotal_items of this InlineResponse2001.  # noqa: E501


        :return: The hydratotal_items of this InlineResponse2001.  # noqa: E501
        :rtype: int
        """
        return self._hydratotal_items

    @hydratotal_items.setter
    def hydratotal_items(self, hydratotal_items):
        """Sets the hydratotal_items of this InlineResponse2001.


        :param hydratotal_items: The hydratotal_items of this InlineResponse2001.  # noqa: E501
        :type hydratotal_items: int
        """
        if (self.local_vars_configuration.client_side_validation and
                hydratotal_items is not None and hydratotal_items < 0):  # noqa: E501
            raise ValueError("Invalid value for `hydratotal_items`, must be a value greater than or equal to `0`")  # noqa: E501

        self._hydratotal_items = hydratotal_items

    @property
    def hydraview(self):
        """Gets the hydraview of this InlineResponse2001.  # noqa: E501


        :return: The hydraview of this InlineResponse2001.  # noqa: E501
        :rtype: InlineResponse200HydraView
        """
        return self._hydraview

    @hydraview.setter
    def hydraview(self, hydraview):
        """Sets the hydraview of this InlineResponse2001.


        :param hydraview: The hydraview of this InlineResponse2001.  # noqa: E501
        :type hydraview: InlineResponse200HydraView
        """

        self._hydraview = hydraview

    @property
    def hydrasearch(self):
        """Gets the hydrasearch of this InlineResponse2001.  # noqa: E501


        :return: The hydrasearch of this InlineResponse2001.  # noqa: E501
        :rtype: InlineResponse200HydraSearch
        """
        return self._hydrasearch

    @hydrasearch.setter
    def hydrasearch(self, hydrasearch):
        """Sets the hydrasearch of this InlineResponse2001.


        :param hydrasearch: The hydrasearch of this InlineResponse2001.  # noqa: E501
        :type hydrasearch: InlineResponse200HydraSearch
        """

        self._hydrasearch = hydrasearch

    def to_dict(self):
        """Returns the model properties as a dict"""
        result = {}

        for attr, _ in six.iteritems(self.openapi_types):
            value = getattr(self, attr)
            if isinstance(value, list):
                result[attr] = list(map(
                    lambda x: x.to_dict() if hasattr(x, "to_dict") else x,
                    value
                ))
            elif hasattr(value, "to_dict"):
                result[attr] = value.to_dict()
            elif isinstance(value, dict):
                result[attr] = dict(map(
                    lambda item: (item[0], item[1].to_dict())
                    if hasattr(item[1], "to_dict") else item,
                    value.items()
                ))
            else:
                result[attr] = value

        return result

    def to_str(self):
        """Returns the string representation of the model"""
        return pprint.pformat(self.to_dict())

    def __repr__(self):
        """For `print` and `pprint`"""
        return self.to_str()

    def __eq__(self, other):
        """Returns true if both objects are equal"""
        if not isinstance(other, InlineResponse2001):
            return False

        return self.to_dict() == other.to_dict()

    def __ne__(self, other):
        """Returns true if both objects are not equal"""
        if not isinstance(other, InlineResponse2001):
            return True

        return self.to_dict() != other.to_dict()
