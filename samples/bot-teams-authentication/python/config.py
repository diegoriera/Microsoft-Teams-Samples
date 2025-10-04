#!/usr/bin/env python3
# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

import os

""" Bot Configuration """


class DefaultConfig:
    """ Bot Configuration """

    PORT = 3978
    APP_ID = os.environ.get("MicrosoftAppId", "<REDACTED>")
    #APP_ID = os.environ.get("MicrosoftAppId", "<REDACTED>")
    APP_PASSWORD = os.environ.get("MicrosoftAppPassword", "<REDACTED>")
    #APP_PASSWORD = os.environ.get("MicrosoftAppPassword", "<REDACTED>")
    #APP_TYPE = os.environ.get("MicrosoftAppType", "SingleTenant")
    APP_TYPE = os.environ.get("MicrosoftAppType", "MultiTenant")
    APP_TENANTID = os.environ.get("MicrosoftAppTenantId", "<REDACTED>")
    CONNECTION_NAME = os.environ.get("ConnectionName", "<REDACTED>")