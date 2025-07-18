# --------------------------------------------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License. See License.txt in the project root for license information.
#
# Code generated by aaz-dev-tools
# --------------------------------------------------------------------------------------------

# pylint: skip-file
# flake8: noqa

from azure.cli.core.aaz import *


@register_command(
    "data-transfer connection flow create",
    is_preview=True,
)
class Create(AAZCommand):
    """Create data flow for the approved connection

    :example: Creates the flow resource
        az data-transfer connection flow create --resource-group testRG --connection-name testConnection --flow-name testFlow --location East US --connection --flow-type Complex --storage-account /subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/rpaas-rg/providers/Private.AzureDataTransfer/storageAccounts/testsa --storage-container-name testcontainer
    """

    _aaz_info = {
        "version": "2025-05-21",
        "resources": [
            ["mgmt-plane", "/subscriptions/{}/resourcegroups/{}/providers/microsoft.azuredatatransfer/connections/{}/flows/{}", "2025-05-21"],
        ]
    }

    AZ_SUPPORT_NO_WAIT = True

    def _handler(self, command_args):
        super()._handler(command_args)
        return self.build_lro_poller(self._execute_operations, self._output)

    _args_schema = None

    @classmethod
    def _build_arguments_schema(cls, *args, **kwargs):
        if cls._args_schema is not None:
            return cls._args_schema
        cls._args_schema = super()._build_arguments_schema(*args, **kwargs)

        # define Arg Group ""

        _args_schema = cls._args_schema
        _args_schema.connection_name = AAZStrArg(
            options=["--connection-name"],
            help="The name for the connection to perform the operation on.",
            required=True,
            fmt=AAZStrArgFormat(
                pattern="^[a-zA-Z0-9-]{3,64}$",
                max_length=64,
                min_length=3,
            ),
        )
        _args_schema.flow_name = AAZStrArg(
            options=["-n", "--name", "--flow-name"],
            help="The name for the flow to perform the operation on.",
            required=True,
            fmt=AAZStrArgFormat(
                pattern="^[a-zA-Z0-9-]{3,64}$",
                max_length=64,
                min_length=3,
            ),
        )
        _args_schema.resource_group = AAZResourceGroupNameArg(
            required=True,
        )

        # define Arg Group "Flow"

        _args_schema = cls._args_schema
        _args_schema.location = AAZResourceLocationArg(
            arg_group="Flow",
            help="The geo-location where the resource lives",
            required=True,
            fmt=AAZResourceLocationArgFormat(
                resource_group_arg="resource_group",
            ),
        )
        _args_schema.plan = AAZObjectArg(
            options=["--plan"],
            arg_group="Flow",
            help="Details of the resource plan.",
        )
        _args_schema.tags = AAZDictArg(
            options=["--tags"],
            arg_group="Flow",
            help="Resource tags.",
        )

        plan = cls._args_schema.plan
        plan.name = AAZStrArg(
            options=["name"],
            help="A user defined name of the 3rd Party Artifact that is being procured.",
            required=True,
        )
        plan.product = AAZStrArg(
            options=["product"],
            help="The 3rd Party artifact that is being procured. E.g. NewRelic. Product maps to the OfferID specified for the artifact at the time of Data Market onboarding. ",
            required=True,
        )
        plan.promotion_code = AAZStrArg(
            options=["promotion-code"],
            help="A publisher provided promotion code as provisioned in Data Market for the said product/artifact.",
        )
        plan.publisher = AAZStrArg(
            options=["publisher"],
            help="The publisher of the 3rd Party Artifact that is being bought. E.g. NewRelic",
            required=True,
        )
        plan.version = AAZStrArg(
            options=["version"],
            help="The version of the desired product/artifact.",
        )

        tags = cls._args_schema.tags
        tags.Element = AAZStrArg()

        # define Arg Group "Identity"

        _args_schema = cls._args_schema
        _args_schema.mi_system_assigned = AAZStrArg(
            options=["--system-assigned", "--mi-system-assigned"],
            arg_group="Identity",
            help="Set the system managed identity.",
            blank="True",
        )
        _args_schema.mi_user_assigned = AAZListArg(
            options=["--user-assigned", "--mi-user-assigned"],
            arg_group="Identity",
            help="Set the user managed identities.",
            blank=[],
        )

        mi_user_assigned = cls._args_schema.mi_user_assigned
        mi_user_assigned.Element = AAZStrArg()

        # define Arg Group "Properties"

        _args_schema = cls._args_schema
        _args_schema.api_flow_options = AAZObjectArg(
            options=["--api-flow-options"],
            arg_group="Properties",
            help="The API Flow configuration options for Azure Data Transfer API Flow type.",
        )
        _args_schema.consumer_group = AAZStrArg(
            options=["--consumer-group"],
            arg_group="Properties",
            help="Event Hub Consumer Group",
        )
        _args_schema.customer_key_vault_uri = AAZStrArg(
            options=["--customer-key-vault-uri"],
            arg_group="Properties",
            help="The URI to the customer managed key for this flow",
        )
        _args_schema.data_type = AAZStrArg(
            options=["--data-type"],
            arg_group="Properties",
            help="Type of data to transfer via the flow.",
            enum={"Blob": "Blob", "Table": "Table"},
        )
        _args_schema.endpoint_ports = AAZListArg(
            options=["--endpoint-ports"],
            arg_group="Properties",
            help="The destination endpoint ports of the stream",
        )
        _args_schema.destination_endpoints = AAZListArg(
            options=["--destination-endpoints"],
            arg_group="Properties",
            help="The destination endpoints of the stream",
        )
        _args_schema.event_hub_id = AAZResourceIdArg(
            options=["--event-hub-id"],
            arg_group="Properties",
            help="Event Hub ID",
        )
        _args_schema.flow_type = AAZStrArg(
            options=["--flow-type"],
            arg_group="Properties",
            help="The flow type for this flow",
            enum={"API": "API", "BasicFiles": "BasicFiles", "Complex": "Complex", "Data": "Data", "DevSecOps": "DevSecOps", "DiskImages": "DiskImages", "Messaging": "Messaging", "MicrosoftInternal": "MicrosoftInternal", "Mission": "Mission", "MissionOpaqueXML": "MissionOpaqueXML", "Opaque": "Opaque", "Standard": "Standard", "StreamingVideo": "StreamingVideo", "Unknown": "Unknown"},
        )
        _args_schema.messaging_options = AAZObjectArg(
            options=["--messaging-options"],
            arg_group="Properties",
            help="The messaging options for this flow",
        )
        _args_schema.passphrase = AAZStrArg(
            options=["--passphrase"],
            arg_group="Properties",
            help="The passphrase used for SRT streams",
        )
        _args_schema.schema = AAZObjectArg(
            options=["--schema"],
            arg_group="Properties",
            help="The selected schema for this flow",
        )
        _args_schema.service_bus_queue_id = AAZResourceIdArg(
            options=["--service-bus-queue-id"],
            arg_group="Properties",
            help="Service Bus Queue ID",
        )
        _args_schema.source_addresses = AAZObjectArg(
            options=["--source-addresses"],
            arg_group="Properties",
            help="The source IP address and CIDR ranges of the stream",
        )
        _args_schema.status = AAZStrArg(
            options=["--status"],
            arg_group="Properties",
            help="Status of the current flow",
            enum={"Disabled": "Disabled", "Enabled": "Enabled"},
        )
        _args_schema.storage_account = AAZStrArg(
            options=["--storage-account"],
            arg_group="Properties",
            help="Storage Account Id",
        )
        _args_schema.storage_container_name = AAZStrArg(
            options=["--storage-container-name"],
            arg_group="Properties",
            help="Storage Container Name",
        )
        _args_schema.storage_table_name = AAZStrArg(
            options=["--storage-table-name"],
            arg_group="Properties",
            help="Storage Table Name",
        )
        _args_schema.stream_id = AAZStrArg(
            options=["--stream-id"],
            arg_group="Properties",
            help="The flow stream identifier",
        )
        _args_schema.stream_latency = AAZIntArg(
            options=["--stream-latency"],
            arg_group="Properties",
            help="The latency of the stream in milliseconds",
        )
        _args_schema.stream_protocol = AAZStrArg(
            options=["--stream-protocol"],
            arg_group="Properties",
            help="The protocol of the stream",
            enum={"RTP": "RTP", "SRT": "SRT", "UDP": "UDP"},
        )

        api_flow_options = cls._args_schema.api_flow_options
        api_flow_options.api_mode = AAZStrArg(
            options=["api-mode"],
            help="Remote Calling Mode in the Azure Data Transfer API Flow, which describes how the API Flow will be invoked",
            enum={"Endpoint": "Endpoint", "SDK": "SDK"},
        )
        api_flow_options.audience_override = AAZStrArg(
            options=["audience-override"],
            help="Optional field to override the audience of the remote endpoint",
        )
        api_flow_options.cname = AAZStrArg(
            options=["cname"],
            help="Unique CNAME to represent the Azure Data Transfer API Flow instance",
        )
        api_flow_options.identity_translation = AAZStrArg(
            options=["identity-translation"],
            help="Flag for if Azure Data Transfer API Flow should extract the user token",
            enum={"ServiceIdentity": "ServiceIdentity", "UserIdentity": "UserIdentity"},
        )
        api_flow_options.remote_calling_mode_client_id = AAZStrArg(
            options=["remote-calling-mode-client-id"],
            help="Remote stub app registration Client ID",
        )
        api_flow_options.remote_endpoint = AAZStrArg(
            options=["remote-endpoint"],
            help="Remote host to which communication needs to be made",
        )
        api_flow_options.sender_client_id = AAZStrArg(
            options=["sender-client-id"],
            help="Sender's app user assigned Manage Identity client ID",
        )

        endpoint_ports = cls._args_schema.endpoint_ports
        endpoint_ports.Element = AAZIntArg()

        destination_endpoints = cls._args_schema.destination_endpoints
        destination_endpoints.Element = AAZStrArg()

        messaging_options = cls._args_schema.messaging_options
        messaging_options.billing_tier = AAZStrArg(
            options=["billing-tier"],
            help="Billing tier for this messaging flow",
            enum={"BlobTransport": "BlobTransport", "Premium": "Premium", "Standard": "Standard"},
        )

        schema = cls._args_schema.schema
        schema.connection_id = AAZStrArg(
            options=["connection-id"],
            help="Connection ID associated with this schema",
        )
        schema.content = AAZStrArg(
            options=["content"],
            help="Content of the schema",
        )
        schema.direction = AAZStrArg(
            options=["direction"],
            help="The direction of the schema.",
            enum={"Receive": "Receive", "Send": "Send"},
        )
        schema.id = AAZStrArg(
            options=["id"],
            help="ID associated with this schema",
        )
        schema.name = AAZStrArg(
            options=["name"],
            help="Name of the schema",
        )
        schema.schema_type = AAZStrArg(
            options=["schema-type"],
            help="The Schema Type",
            enum={"Xsd": "Xsd", "Zip": "Zip"},
        )
        schema.schema_uri = AAZStrArg(
            options=["schema-uri"],
            help="Uri containing SAS token for the zipped schema",
        )
        schema.status = AAZStrArg(
            options=["status"],
            help="Status of the schema",
            enum={"Approved": "Approved", "New": "New"},
        )

        source_addresses = cls._args_schema.source_addresses
        source_addresses.source_addresses = AAZListArg(
            options=["source-addresses"],
            help="A source IP address or CIDR range",
        )

        source_addresses = cls._args_schema.source_addresses.source_addresses
        source_addresses.Element = AAZStrArg()
        return cls._args_schema

    def _execute_operations(self):
        self.pre_operations()
        yield self.FlowsCreateOrUpdate(ctx=self.ctx)()
        self.post_operations()

    @register_callback
    def pre_operations(self):
        pass

    @register_callback
    def post_operations(self):
        pass

    def _output(self, *args, **kwargs):
        result = self.deserialize_output(self.ctx.vars.instance, client_flatten=True)
        return result

    class FlowsCreateOrUpdate(AAZHttpOperation):
        CLIENT_TYPE = "MgmtClient"

        def __call__(self, *args, **kwargs):
            request = self.make_request()
            session = self.client.send_request(request=request, stream=False, **kwargs)
            if session.http_response.status_code in [202]:
                return self.client.build_lro_polling(
                    self.ctx.args.no_wait,
                    session,
                    self.on_200_201,
                    self.on_error,
                    lro_options={"final-state-via": "azure-async-operation"},
                    path_format_arguments=self.url_parameters,
                )
            if session.http_response.status_code in [200, 201]:
                return self.client.build_lro_polling(
                    self.ctx.args.no_wait,
                    session,
                    self.on_200_201,
                    self.on_error,
                    lro_options={"final-state-via": "azure-async-operation"},
                    path_format_arguments=self.url_parameters,
                )

            return self.on_error(session.http_response)

        @property
        def url(self):
            return self.client.format_url(
                "/subscriptions/{subscriptionId}/resourceGroups/{resourceGroupName}/providers/Microsoft.AzureDataTransfer/connections/{connectionName}/flows/{flowName}",
                **self.url_parameters
            )

        @property
        def method(self):
            return "PUT"

        @property
        def error_format(self):
            return "MgmtErrorFormat"

        @property
        def url_parameters(self):
            parameters = {
                **self.serialize_url_param(
                    "connectionName", self.ctx.args.connection_name,
                    required=True,
                ),
                **self.serialize_url_param(
                    "flowName", self.ctx.args.flow_name,
                    required=True,
                ),
                **self.serialize_url_param(
                    "resourceGroupName", self.ctx.args.resource_group,
                    required=True,
                ),
                **self.serialize_url_param(
                    "subscriptionId", self.ctx.subscription_id,
                    required=True,
                ),
            }
            return parameters

        @property
        def query_parameters(self):
            parameters = {
                **self.serialize_query_param(
                    "api-version", "2025-05-21",
                    required=True,
                ),
            }
            return parameters

        @property
        def header_parameters(self):
            parameters = {
                **self.serialize_header_param(
                    "Content-Type", "application/json",
                ),
                **self.serialize_header_param(
                    "Accept", "application/json",
                ),
            }
            return parameters

        @property
        def content(self):
            _content_value, _builder = self.new_content_builder(
                self.ctx.args,
                typ=AAZObjectType,
                typ_kwargs={"flags": {"required": True, "client_flatten": True}}
            )
            _builder.set_prop("identity", AAZIdentityObjectType)
            _builder.set_prop("location", AAZStrType, ".location", typ_kwargs={"flags": {"required": True}})
            _builder.set_prop("plan", AAZObjectType, ".plan")
            _builder.set_prop("properties", AAZObjectType)
            _builder.set_prop("tags", AAZDictType, ".tags")

            identity = _builder.get(".identity")
            if identity is not None:
                identity.set_prop("userAssigned", AAZListType, ".mi_user_assigned", typ_kwargs={"flags": {"action": "create"}})
                identity.set_prop("systemAssigned", AAZStrType, ".mi_system_assigned", typ_kwargs={"flags": {"action": "create"}})

            user_assigned = _builder.get(".identity.userAssigned")
            if user_assigned is not None:
                user_assigned.set_elements(AAZStrType, ".")

            plan = _builder.get(".plan")
            if plan is not None:
                plan.set_prop("name", AAZStrType, ".name", typ_kwargs={"flags": {"required": True}})
                plan.set_prop("product", AAZStrType, ".product", typ_kwargs={"flags": {"required": True}})
                plan.set_prop("promotionCode", AAZStrType, ".promotion_code")
                plan.set_prop("publisher", AAZStrType, ".publisher", typ_kwargs={"flags": {"required": True}})
                plan.set_prop("version", AAZStrType, ".version")

            properties = _builder.get(".properties")
            if properties is not None:
                properties.set_prop("apiFlowOptions", AAZObjectType, ".api_flow_options")
                properties.set_prop("consumerGroup", AAZStrType, ".consumer_group")
                properties.set_prop("customerManagedKeyVaultUri", AAZStrType, ".customer_key_vault_uri")
                properties.set_prop("dataType", AAZStrType, ".data_type")
                properties.set_prop("destinationEndpointPorts", AAZListType, ".endpoint_ports")
                properties.set_prop("destinationEndpoints", AAZListType, ".destination_endpoints")
                properties.set_prop("eventHubId", AAZStrType, ".event_hub_id")
                properties.set_prop("flowType", AAZStrType, ".flow_type")
                properties.set_prop("messagingOptions", AAZObjectType, ".messaging_options")
                properties.set_prop("passphrase", AAZStrType, ".passphrase")
                properties.set_prop("schema", AAZObjectType, ".schema")
                properties.set_prop("serviceBusQueueId", AAZStrType, ".service_bus_queue_id")
                properties.set_prop("sourceAddresses", AAZObjectType, ".source_addresses")
                properties.set_prop("status", AAZStrType, ".status")
                properties.set_prop("storageAccountName", AAZStrType, ".storage_account")
                properties.set_prop("storageContainerName", AAZStrType, ".storage_container_name")
                properties.set_prop("storageTableName", AAZStrType, ".storage_table_name")
                properties.set_prop("streamId", AAZStrType, ".stream_id")
                properties.set_prop("streamLatency", AAZIntType, ".stream_latency")
                properties.set_prop("streamProtocol", AAZStrType, ".stream_protocol")

            api_flow_options = _builder.get(".properties.apiFlowOptions")
            if api_flow_options is not None:
                api_flow_options.set_prop("apiMode", AAZStrType, ".api_mode")
                api_flow_options.set_prop("audienceOverride", AAZStrType, ".audience_override")
                api_flow_options.set_prop("cname", AAZStrType, ".cname")
                api_flow_options.set_prop("identityTranslation", AAZStrType, ".identity_translation")
                api_flow_options.set_prop("remoteCallingModeClientId", AAZStrType, ".remote_calling_mode_client_id")
                api_flow_options.set_prop("remoteEndpoint", AAZStrType, ".remote_endpoint")
                api_flow_options.set_prop("senderClientId", AAZStrType, ".sender_client_id")

            destination_endpoint_ports = _builder.get(".properties.destinationEndpointPorts")
            if destination_endpoint_ports is not None:
                destination_endpoint_ports.set_elements(AAZIntType, ".")

            destination_endpoints = _builder.get(".properties.destinationEndpoints")
            if destination_endpoints is not None:
                destination_endpoints.set_elements(AAZStrType, ".")

            messaging_options = _builder.get(".properties.messagingOptions")
            if messaging_options is not None:
                messaging_options.set_prop("billingTier", AAZStrType, ".billing_tier")

            schema = _builder.get(".properties.schema")
            if schema is not None:
                schema.set_prop("connectionId", AAZStrType, ".connection_id")
                schema.set_prop("content", AAZStrType, ".content")
                schema.set_prop("direction", AAZStrType, ".direction")
                schema.set_prop("id", AAZStrType, ".id")
                schema.set_prop("name", AAZStrType, ".name")
                schema.set_prop("schemaType", AAZStrType, ".schema_type")
                schema.set_prop("schemaUri", AAZStrType, ".schema_uri")
                schema.set_prop("status", AAZStrType, ".status")

            source_addresses = _builder.get(".properties.sourceAddresses")
            if source_addresses is not None:
                source_addresses.set_prop("sourceAddresses", AAZListType, ".source_addresses")

            source_addresses = _builder.get(".properties.sourceAddresses.sourceAddresses")
            if source_addresses is not None:
                source_addresses.set_elements(AAZStrType, ".")

            tags = _builder.get(".tags")
            if tags is not None:
                tags.set_elements(AAZStrType, ".")

            return self.serialize_content(_content_value)

        def on_200_201(self, session):
            data = self.deserialize_http_content(session)
            self.ctx.set_var(
                "instance",
                data,
                schema_builder=self._build_schema_on_200_201
            )

        _schema_on_200_201 = None

        @classmethod
        def _build_schema_on_200_201(cls):
            if cls._schema_on_200_201 is not None:
                return cls._schema_on_200_201

            cls._schema_on_200_201 = AAZObjectType()

            _schema_on_200_201 = cls._schema_on_200_201
            _schema_on_200_201.id = AAZStrType(
                flags={"read_only": True},
            )
            _schema_on_200_201.identity = AAZIdentityObjectType()
            _schema_on_200_201.location = AAZStrType(
                flags={"required": True},
            )
            _schema_on_200_201.name = AAZStrType(
                flags={"read_only": True},
            )
            _schema_on_200_201.plan = AAZObjectType()
            _schema_on_200_201.properties = AAZObjectType()
            _schema_on_200_201.system_data = AAZObjectType(
                serialized_name="systemData",
                flags={"read_only": True},
            )
            _schema_on_200_201.tags = AAZDictType()
            _schema_on_200_201.type = AAZStrType(
                flags={"read_only": True},
            )

            identity = cls._schema_on_200_201.identity
            identity.principal_id = AAZStrType(
                serialized_name="principalId",
                flags={"read_only": True},
            )
            identity.tenant_id = AAZStrType(
                serialized_name="tenantId",
                flags={"read_only": True},
            )
            identity.type = AAZStrType(
                flags={"required": True},
            )
            identity.user_assigned_identities = AAZDictType(
                serialized_name="userAssignedIdentities",
            )

            user_assigned_identities = cls._schema_on_200_201.identity.user_assigned_identities
            user_assigned_identities.Element = AAZObjectType(
                nullable=True,
            )

            _element = cls._schema_on_200_201.identity.user_assigned_identities.Element
            _element.client_id = AAZStrType(
                serialized_name="clientId",
                flags={"read_only": True},
            )
            _element.principal_id = AAZStrType(
                serialized_name="principalId",
                flags={"read_only": True},
            )

            plan = cls._schema_on_200_201.plan
            plan.name = AAZStrType(
                flags={"required": True},
            )
            plan.product = AAZStrType(
                flags={"required": True},
            )
            plan.promotion_code = AAZStrType(
                serialized_name="promotionCode",
            )
            plan.publisher = AAZStrType(
                flags={"required": True},
            )
            plan.version = AAZStrType()

            properties = cls._schema_on_200_201.properties
            properties.api_flow_options = AAZObjectType(
                serialized_name="apiFlowOptions",
            )
            properties.connection = AAZObjectType()
            properties.consumer_group = AAZStrType(
                serialized_name="consumerGroup",
            )
            properties.customer_managed_key_vault_uri = AAZStrType(
                serialized_name="customerManagedKeyVaultUri",
            )
            properties.data_type = AAZStrType(
                serialized_name="dataType",
            )
            properties.destination_endpoint_ports = AAZListType(
                serialized_name="destinationEndpointPorts",
            )
            properties.destination_endpoints = AAZListType(
                serialized_name="destinationEndpoints",
            )
            properties.event_hub_id = AAZStrType(
                serialized_name="eventHubId",
            )
            properties.flow_id = AAZStrType(
                serialized_name="flowId",
                flags={"read_only": True},
            )
            properties.flow_type = AAZStrType(
                serialized_name="flowType",
            )
            properties.force_disabled_status = AAZListType(
                serialized_name="forceDisabledStatus",
                flags={"read_only": True},
            )
            properties.key_vault_uri = AAZStrType(
                serialized_name="keyVaultUri",
            )
            properties.link_status = AAZStrType(
                serialized_name="linkStatus",
                flags={"read_only": True},
            )
            properties.linked_flow_id = AAZStrType(
                serialized_name="linkedFlowId",
                flags={"read_only": True},
            )
            properties.messaging_options = AAZObjectType(
                serialized_name="messagingOptions",
            )
            properties.passphrase = AAZStrType()
            properties.policies = AAZListType()
            properties.provisioning_state = AAZStrType(
                serialized_name="provisioningState",
                flags={"read_only": True},
            )
            properties.schema = AAZObjectType()
            properties.service_bus_queue_id = AAZStrType(
                serialized_name="serviceBusQueueId",
            )
            properties.source_addresses = AAZObjectType(
                serialized_name="sourceAddresses",
            )
            properties.status = AAZStrType()
            properties.storage_account_id = AAZStrType(
                serialized_name="storageAccountId",
            )
            properties.storage_account_name = AAZStrType(
                serialized_name="storageAccountName",
            )
            properties.storage_container_name = AAZStrType(
                serialized_name="storageContainerName",
            )
            properties.storage_table_name = AAZStrType(
                serialized_name="storageTableName",
            )
            properties.stream_id = AAZStrType(
                serialized_name="streamId",
            )
            properties.stream_latency = AAZIntType(
                serialized_name="streamLatency",
            )
            properties.stream_protocol = AAZStrType(
                serialized_name="streamProtocol",
            )

            api_flow_options = cls._schema_on_200_201.properties.api_flow_options
            api_flow_options.api_mode = AAZStrType(
                serialized_name="apiMode",
            )
            api_flow_options.audience_override = AAZStrType(
                serialized_name="audienceOverride",
            )
            api_flow_options.cname = AAZStrType()
            api_flow_options.identity_translation = AAZStrType(
                serialized_name="identityTranslation",
            )
            api_flow_options.remote_calling_mode_client_id = AAZStrType(
                serialized_name="remoteCallingModeClientId",
            )
            api_flow_options.remote_endpoint = AAZStrType(
                serialized_name="remoteEndpoint",
            )
            api_flow_options.sender_client_id = AAZStrType(
                serialized_name="senderClientId",
            )

            connection = cls._schema_on_200_201.properties.connection
            connection.id = AAZStrType(
                flags={"required": True},
            )
            connection.location = AAZStrType()
            connection.name = AAZStrType()
            connection.subscription_name = AAZStrType(
                serialized_name="subscriptionName",
            )

            destination_endpoint_ports = cls._schema_on_200_201.properties.destination_endpoint_ports
            destination_endpoint_ports.Element = AAZIntType()

            destination_endpoints = cls._schema_on_200_201.properties.destination_endpoints
            destination_endpoints.Element = AAZStrType()

            force_disabled_status = cls._schema_on_200_201.properties.force_disabled_status
            force_disabled_status.Element = AAZStrType()

            messaging_options = cls._schema_on_200_201.properties.messaging_options
            messaging_options.billing_tier = AAZStrType(
                serialized_name="billingTier",
            )

            policies = cls._schema_on_200_201.properties.policies
            policies.Element = AAZStrType()

            schema = cls._schema_on_200_201.properties.schema
            schema.connection_id = AAZStrType(
                serialized_name="connectionId",
            )
            schema.content = AAZStrType()
            schema.direction = AAZStrType()
            schema.id = AAZStrType()
            schema.name = AAZStrType()
            schema.schema_type = AAZStrType(
                serialized_name="schemaType",
            )
            schema.schema_uri = AAZStrType(
                serialized_name="schemaUri",
            )
            schema.status = AAZStrType()

            source_addresses = cls._schema_on_200_201.properties.source_addresses
            source_addresses.source_addresses = AAZListType(
                serialized_name="sourceAddresses",
            )

            source_addresses = cls._schema_on_200_201.properties.source_addresses.source_addresses
            source_addresses.Element = AAZStrType()

            system_data = cls._schema_on_200_201.system_data
            system_data.created_at = AAZStrType(
                serialized_name="createdAt",
            )
            system_data.created_by = AAZStrType(
                serialized_name="createdBy",
            )
            system_data.created_by_type = AAZStrType(
                serialized_name="createdByType",
            )
            system_data.last_modified_at = AAZStrType(
                serialized_name="lastModifiedAt",
            )
            system_data.last_modified_by = AAZStrType(
                serialized_name="lastModifiedBy",
            )
            system_data.last_modified_by_type = AAZStrType(
                serialized_name="lastModifiedByType",
            )

            tags = cls._schema_on_200_201.tags
            tags.Element = AAZStrType()

            return cls._schema_on_200_201


class _CreateHelper:
    """Helper class for Create"""


__all__ = ["Create"]
