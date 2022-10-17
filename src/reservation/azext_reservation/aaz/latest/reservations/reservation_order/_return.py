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
    "reservations reservation-order return",
)
class Return(AAZCommand):
    """Return a reservation.

    :example: Return a reservation
        az reservations reservation-order return --reservation-order-id 50000000-aaaa-bbbb-cccc-200000000000 --return-reason mockReason --scope Reservation --quantity 1 --reservation-id /providers/microsoft.capacity/reservationOrders/50000000-aaaa-bbbb-cccc-200000000000/reservations/30000000-aaaa-bbbb-cccc-200000000011 --session-id 40000000-aaaa-bbbb-cccc-200000000012
    """

    _aaz_info = {
        "version": "2022-03-01",
        "resources": [
            ["mgmt-plane", "/providers/microsoft.capacity/reservationorders/{}/return", "2022-03-01"],
        ]
    }

    def _handler(self, command_args):
        super()._handler(command_args)
        self._execute_operations()
        return self._output()

    _args_schema = None

    @classmethod
    def _build_arguments_schema(cls, *args, **kwargs):
        if cls._args_schema is not None:
            return cls._args_schema
        cls._args_schema = super()._build_arguments_schema(*args, **kwargs)

        # define Arg Group ""

        _args_schema = cls._args_schema
        _args_schema.reservation_order_id = AAZStrArg(
            options=["--reservation-order-id"],
            help="Order Id of the reservation",
            required=True,
        )

        # define Arg Group "Properties"

        _args_schema = cls._args_schema
        _args_schema.return_reason = AAZStrArg(
            options=["--return-reason"],
            arg_group="Properties",
            help="The reason of returning the reservation",
        )
        _args_schema.scope = AAZStrArg(
            options=["--scope"],
            arg_group="Properties",
            help="The scope of the refund, e.g. Reservation",
        )
        _args_schema.session_id = AAZStrArg(
            options=["--session-id"],
            arg_group="Properties",
            help="SessionId that was returned by CalculateRefund API.",
        )

        # define Arg Group "ReservationToReturn"

        _args_schema = cls._args_schema
        _args_schema.quantity = AAZIntArg(
            options=["--quantity"],
            arg_group="ReservationToReturn",
            help="Quantity to be returned. Must be greater than zero.",
        )
        _args_schema.reservation_id = AAZStrArg(
            options=["--reservation-id"],
            arg_group="ReservationToReturn",
            help="Fully qualified identifier of the Reservation being returned",
        )
        return cls._args_schema

    def _execute_operations(self):
        self.pre_operations()
        self.ReturnPost(ctx=self.ctx)()
        self.post_operations()

    # @register_callback
    def pre_operations(self):
        pass

    # @register_callback
    def post_operations(self):
        pass

    def _output(self, *args, **kwargs):
        result = self.deserialize_output(self.ctx.vars.instance, client_flatten=True)
        return result

    class ReturnPost(AAZHttpOperation):
        CLIENT_TYPE = "MgmtClient"

        def __call__(self, *args, **kwargs):
            request = self.make_request()
            session = self.client.send_request(request=request, stream=False, **kwargs)
            if session.http_response.status_code in [202]:
                return self.on_202(session)

            return self.on_error(session.http_response)

        @property
        def url(self):
            return self.client.format_url(
                "/providers/Microsoft.Capacity/reservationOrders/{reservationOrderId}/return",
                **self.url_parameters
            )

        @property
        def method(self):
            return "POST"

        @property
        def error_format(self):
            return "ODataV4Format"

        @property
        def url_parameters(self):
            parameters = {
                **self.serialize_url_param(
                    "reservationOrderId", self.ctx.args.reservation_order_id,
                    required=True,
                ),
            }
            return parameters

        @property
        def query_parameters(self):
            parameters = {
                **self.serialize_query_param(
                    "api-version", "2022-03-01",
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
            _builder.set_prop("properties", AAZObjectType)

            properties = _builder.get(".properties")
            if properties is not None:
                properties.set_prop("reservationToReturn", AAZObjectType)
                properties.set_prop("returnReason", AAZStrType, ".return_reason")
                properties.set_prop("scope", AAZStrType, ".scope")
                properties.set_prop("sessionId", AAZStrType, ".session_id")

            reservation_to_return = _builder.get(".properties.reservationToReturn")
            if reservation_to_return is not None:
                reservation_to_return.set_prop("quantity", AAZIntType, ".quantity")
                reservation_to_return.set_prop("reservationId", AAZStrType, ".reservation_id")

            return self.serialize_content(_content_value)

        def on_202(self, session):
            data = self.deserialize_http_content(session)
            self.ctx.set_var(
                "instance",
                data,
                schema_builder=self._build_schema_on_202
            )

        _schema_on_202 = None

        @classmethod
        def _build_schema_on_202(cls):
            if cls._schema_on_202 is not None:
                return cls._schema_on_202

            cls._schema_on_202 = AAZObjectType()

            _schema_on_202 = cls._schema_on_202
            _schema_on_202.id = AAZStrType()
            _schema_on_202.properties = AAZObjectType()

            properties = cls._schema_on_202.properties
            properties.billing_information = AAZObjectType(
                serialized_name="billingInformation",
            )
            properties.billing_refund_amount = AAZObjectType(
                serialized_name="billingRefundAmount",
            )
            _build_schema_price_read(properties.billing_refund_amount)
            properties.policy_result = AAZObjectType(
                serialized_name="policyResult",
            )
            properties.pricing_refund_amount = AAZObjectType(
                serialized_name="pricingRefundAmount",
            )
            _build_schema_price_read(properties.pricing_refund_amount)
            properties.quantity = AAZIntType()
            properties.session_id = AAZStrType(
                serialized_name="sessionId",
            )

            billing_information = cls._schema_on_202.properties.billing_information
            billing_information.billing_currency_prorated_amount = AAZObjectType(
                serialized_name="billingCurrencyProratedAmount",
            )
            _build_schema_price_read(billing_information.billing_currency_prorated_amount)
            billing_information.billing_currency_remaining_commitment_amount = AAZObjectType(
                serialized_name="billingCurrencyRemainingCommitmentAmount",
            )
            _build_schema_price_read(billing_information.billing_currency_remaining_commitment_amount)
            billing_information.billing_currency_total_paid_amount = AAZObjectType(
                serialized_name="billingCurrencyTotalPaidAmount",
            )
            _build_schema_price_read(billing_information.billing_currency_total_paid_amount)
            billing_information.billing_plan = AAZStrType(
                serialized_name="billingPlan",
            )
            billing_information.completed_transactions = AAZIntType(
                serialized_name="completedTransactions",
            )
            billing_information.total_transactions = AAZIntType(
                serialized_name="totalTransactions",
            )

            policy_result = cls._schema_on_202.properties.policy_result
            policy_result.properties = AAZObjectType()

            properties = cls._schema_on_202.properties.policy_result.properties
            properties.consumed_refunds_total = AAZObjectType(
                serialized_name="consumedRefundsTotal",
            )
            _build_schema_price_read(properties.consumed_refunds_total)
            properties.max_refund_limit = AAZObjectType(
                serialized_name="maxRefundLimit",
            )
            _build_schema_price_read(properties.max_refund_limit)
            properties.policy_errors = AAZListType(
                serialized_name="policyErrors",
            )

            policy_errors = cls._schema_on_202.properties.policy_result.properties.policy_errors
            policy_errors.Element = AAZObjectType()

            _element = cls._schema_on_202.properties.policy_result.properties.policy_errors.Element
            _element.code = AAZStrType()
            _element.message = AAZStrType()

            return cls._schema_on_202


_schema_price_read = None


def _build_schema_price_read(_schema):
    global _schema_price_read
    if _schema_price_read is not None:
        _schema.amount = _schema_price_read.amount
        _schema.currency_code = _schema_price_read.currency_code
        return

    _schema_price_read = AAZObjectType()

    price_read = _schema_price_read
    price_read.amount = AAZFloatType()
    price_read.currency_code = AAZStrType(
        serialized_name="currencyCode",
    )

    _schema.amount = _schema_price_read.amount
    _schema.currency_code = _schema_price_read.currency_code


__all__ = ["Return"]