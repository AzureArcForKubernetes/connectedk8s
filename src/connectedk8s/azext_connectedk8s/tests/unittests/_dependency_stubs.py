import sys
from types import ModuleType
from unittest.mock import MagicMock

azclierror_stub = ModuleType("azure.cli.core.azclierror")


class AzCLIError(Exception):
    def __init__(self, message="", **_kwargs):
        super().__init__(message)


class ArgumentUsageError(AzCLIError):
    pass


class AzureInternalError(AzCLIError):
    pass


class AzureResponseError(AzCLIError):
    pass


class ClientRequestError(AzCLIError):
    pass


class CLIInternalError(AzCLIError):
    pass


class FileOperationError(AzCLIError):
    pass


class InvalidArgumentValueError(AzCLIError):
    pass


class ManualInterrupt(AzCLIError):
    pass


class MutuallyExclusiveArgumentError(AzCLIError):
    pass


class RequiredArgumentMissingError(AzCLIError):
    pass


class ValidationError(AzCLIError):
    pass


for error_class in (
    AzCLIError,
    ArgumentUsageError,
    AzureInternalError,
    AzureResponseError,
    ClientRequestError,
    CLIInternalError,
    FileOperationError,
    InvalidArgumentValueError,
    ManualInterrupt,
    MutuallyExclusiveArgumentError,
    RequiredArgumentMissingError,
    ValidationError,
):
    setattr(azclierror_stub, error_class.__name__, error_class)

kubernetes_models_stub = ModuleType("kubernetes.client.models")


class _KubernetesModel:
    def __init__(self, **kwargs):
        for name, value in kwargs.items():
            setattr(self, name, value)


class V1Node(_KubernetesModel):
    pass


class V1NodeList(_KubernetesModel):
    pass


class V1NodeSpec(_KubernetesModel):
    pass


class V1ObjectMeta(_KubernetesModel):
    pass


for model_class in (V1Node, V1NodeList, V1NodeSpec, V1ObjectMeta):
    setattr(kubernetes_models_stub, model_class.__name__, model_class)


def install_dependency_stubs():
    stubs = {
        "azure": MagicMock(),
        "azure.cli": MagicMock(),
        "azure.cli.command_modules": MagicMock(),
        "azure.cli.command_modules.role": MagicMock(),
        "azure.cli.core": MagicMock(),
        "azure.cli.core._profile": MagicMock(),
        "azure.cli.core.azclierror": azclierror_stub,
        "azure.cli.core.commands": MagicMock(),
        "azure.cli.core.commands.client_factory": MagicMock(),
        "azure.cli.core.style": MagicMock(),
        "azure.cli.core.util": MagicMock(),
        "azure.core": MagicMock(),
        "azure.core.exceptions": MagicMock(),
        "azure.mgmt": MagicMock(),
        "azure.mgmt.core": MagicMock(),
        "azure.mgmt.core.tools": MagicMock(),
        "Crypto": MagicMock(),
        "Crypto.IO": MagicMock(),
        "Crypto.IO.PEM": MagicMock(),
        "Crypto.PublicKey": MagicMock(),
        "Crypto.PublicKey.RSA": MagicMock(),
        "Crypto.Util": MagicMock(),
        "Crypto.Util.asn1": MagicMock(),
        "knack": MagicMock(),
        "knack.log": MagicMock(),
        "knack.help_files": MagicMock(),
        "knack.util": MagicMock(),
        "knack.cli": MagicMock(),
        "knack.config": MagicMock(),
        "knack.prompting": MagicMock(),
        "knack.commands": MagicMock(),
        "knack.arguments": MagicMock(),
        "knack.events": MagicMock(),
        "kubernetes": MagicMock(),
        "kubernetes.client": MagicMock(),
        "kubernetes.client.models": kubernetes_models_stub,
        "kubernetes.client.rest": MagicMock(),
        "kubernetes.config": MagicMock(),
        "kubernetes.config.kube_config": MagicMock(),
        "oras": MagicMock(),
        "oras.client": MagicMock(),
        "psutil": MagicMock(),
        "msrest": MagicMock(),
        "msrest.exceptions": MagicMock(),
        "msrestazure": MagicMock(),
        "azext_connectedk8s._client_factory": MagicMock(),
        "azext_connectedk8s.clientproxyhelper": MagicMock(),
        "azext_connectedk8s.clientproxyhelper._binaryutils": MagicMock(),
        "azext_connectedk8s.clientproxyhelper._enums": MagicMock(),
        "azext_connectedk8s.clientproxyhelper._proxylogic": MagicMock(),
        "azext_connectedk8s.clientproxyhelper._utils": MagicMock(),
        "azext_connectedk8s.vendored_sdks.preview_2025_08_01.models": MagicMock(),
    }
    originals = {name: sys.modules.get(name) for name in stubs}
    for name, stub in stubs.items():
        sys.modules.setdefault(name, stub)
    return originals


def restore_dependency_modules(originals):
    for name, original in originals.items():
        if original is None:
            sys.modules.pop(name, None)
        else:
            sys.modules[name] = original
