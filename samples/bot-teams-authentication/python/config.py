#!/usr/bin/env python3
# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

import os

""" Bot Configuration """


class DefaultConfig:
    """ Bot Configuration """

    PORT = 3978
    APP_ID = os.environ.get("MicrosoftAppId", "6616c210-1d64-4777-97bb-67dac47968a7")
    #APP_ID = os.environ.get("MicrosoftAppId", "b7776e64-4fb7-4fbe-bfc1-69893eb71aa4")
    #APP_TYPE = os.environ.get("MicrosoftAppType", "SingleTenant")
    APP_TYPE = os.environ.get("MicrosoftAppType", "MultiTenant")
    APP_TENANTID = os.environ.get("MicrosoftAppTenantId", "e7db9eb6-7162-4d1c-a769-4834407d6c3c")
    CONNECTION_NAME = os.environ.get("ConnectionName", "OAuth")