# AZ CLI ConnectedK8s Release Process Guide

Reusable guide for releasing a new version of the `az connectedk8s` CLI extension.

> **Note:** Replace version numbers (e.g. `1.11.1`) and file paths with the values for your release.

---

## Prerequisites

| Requirement | Details |
|---|---|
| **Fork write access** | [AzureArcForKubernetes/connectedk8s](https://github.com/AzureArcForKubernetes/connectedk8s/) |
| **CI pipeline access** | [connectedk8s CLI Testing](https://dev.azure.com/ClusterConfigurationAgent/Extension%20CLI/_build?definitionId=643&_a=summary) in Azure DevOps — Org: `ClusterConfigurationAgent` / Project: `Extension CLI` |
| **Azure subscriptions** | Fairfax (USGov) and Mooncake (China) for sovereign cloud validation |
| **Test VMs** | AMD64 and ARM64 Linux VMs (or kind clusters) for manual validation |
| **Build tooling** | Python environment with `azdev` installed for building the WHL |

> **Important:** The CI pipeline source repository must be set to the **fork** (`AzureArcForKubernetes/connectedk8s`), **not** the upstream monorepo (`Azure/azure-cli-extensions`). When you run a pipeline on a branch like `release-v1.11.1`, ADO looks for the pipeline YAML definition file on that branch in whichever repo the pipeline is configured to point at. Release branches only exist on the fork — so if the pipeline source is set to upstream, ADO can't find the branch and fails with *"Could not find valid pipeline YAML file for this branch/tag"*. If you hit this error, edit the pipeline settings in ADO and change the source repository to the fork.

---

## Phase 1: Local Fork

### Step 1 — Create the release branch

Release branches are cut from the **fork's `main`**, not from upstream.

**Naming convention:** `release-vX.X.X` (e.g. `release-v1.11.1`)

Use a git worktree to keep `main` untouched:

```bash
git worktree add C:\Temp\ck8s-<version> origin/main
git -C C:\Temp\ck8s-<version> checkout -b release-v<version>
```

If the branch already exists on the remote:

```bash
git worktree add C:\Temp\ck8s-<version> origin/release-v<version>
```

### Step 2 — Make release changes

#### Required changes

| File | Change |
|---|---|
| `src/connectedk8s/setup.py` | `VERSION = "<version>"` |
| `src/connectedk8s/HISTORY.rst` | Add entry at the **very top** (see format below) |
| `src/connectedk8s/azext_connectedk8s/_constants.py` | Update `CLIENT_PROXY_VERSION` to match proxy version in the release notes |
| `src/connectedk8s/azext_connectedk8s/azext_metadata.json` | Only update `azext.minCliCoreVersion` if a newer az CLI is required (current minimum: `2.70.0`) |

**HISTORY.rst format:**

```rst
<version>
++++++++++
* <description of changes>
```

#### Optional changes

Bug fixes or improvements to any source file under `src/connectedk8s/azext_connectedk8s/` (e.g. `custom.py`, `_utils.py`).

#### Commit and push

```bash
git -C C:\Temp\ck8s-<version> add src/connectedk8s/
git -C C:\Temp\ck8s-<version> commit -m "Release v<version>: <description>"
git -C C:\Temp\ck8s-<version> push --set-upstream origin release-v<version>
```

### Step 3 — Run CI pipeline

**Pipeline:** "connectedk8s CLI Testing" (Azure DevOps)

1. Go to Azure DevOps > `ClusterConfigurationAgent` > `Extension CLI` > Pipelines
2. Open **"connectedk8s CLI Testing"** > click **"Run pipeline"**
3. In the **Branch/tag** dropdown, select: `release-v<version>`
4. Leave other fields as defaults and click **Run**
5. Wait for results — the job runs for up to 60 minutes

#### What the CI pipeline covers

The fork CI runs **PowerShell Pester tests** and a few **linting/style checks** that are required for the eventual check-in to upstream.

#### Interpreting results

- **"100% tests passed"** = SUCCESS, even if the job times out afterward.
- The Azure Pipelines agent has a **60-minute hard limit**. If tests finish near that limit, the cleanup/teardown phase gets killed by the timeout. This is **not** a test failure — look for "100% tests passed" in the logs.
- **`azdev style` and `verify extension index`** checks may show failures in the fork CI — this is expected. These checks are enforced by the **upstream** CI when you open the PR to `Azure/azure-cli-extensions`. Fix any style issues before submitting the upstream PR (Step 11).
- The Pester tests and core linting must pass before proceeding.

> **"Could not find valid pipeline YAML file for this branch/tag"** — The pipeline definition is pointing to the wrong repo. See [Troubleshooting](#troubleshooting).

### Step 4 — Build the WHL

```bash
azdev extension build connectedk8s
```

Output: `src/connectedk8s/connectedk8s-<version>-py2.py3-none-any.whl`

### Step 5 — Commit the WHL to a `-whl` branch

> **Important:** Keep the plain `release-v<version>` branch free of the WHL binary. Use a separate `-whl` branch.

```bash
git -C C:\Temp\ck8s-<version> checkout -b release-v<version>-whl origin/release-v<version>

Copy-Item src\connectedk8s\connectedk8s-<version>-py2.py3-none-any.whl `
           C:\Temp\ck8s-<version>\src\connectedk8s\

git -C C:\Temp\ck8s-<version> add src/connectedk8s/connectedk8s-<version>-py2.py3-none-any.whl
git -C C:\Temp\ck8s-<version> commit -m "Add WHL for release v<version>"
git -C C:\Temp\ck8s-<version> push --set-upstream origin release-v<version>-whl
```

**Raw URL pattern:**

```
https://raw.githubusercontent.com/AzureArcForKubernetes/connectedk8s/release-v<version>-whl/src/connectedk8s/connectedk8s-<version>-py2.py3-none-any.whl
```

**Example (v1.11.1):**

```
https://raw.githubusercontent.com/AzureArcForKubernetes/connectedk8s/release-v1.11.1-whl/src/connectedk8s/connectedk8s-1.11.1-py2.py3-none-any.whl
```

### Step 6 — Validate on AMD64 and ARM64 VMs

Install the WHL on each VM first:

```bash
az extension remove --name connectedk8s
az extension add --source <whl-raw-url> --yes
az connectedk8s version  # confirm version
```

> **Note:** `az extension show` and `az version` may show `"version": null` / `"Unknown"`. This is a known display-only bug — see [Troubleshooting](#version-null-in-az-extension-show).

#### Test matrix (run on **both** AMD64 and ARM64)

#### a. Basic connect / disconnect

```bash
rm -rf ~/.azure/helm
kind delete cluster --name test-cluster 2>/dev/null
kind create cluster --name test-cluster
az connectedk8s connect --name test-cluster --resource-group <rg> --subscription <sub>
file ~/.azure/helm/**/linux-**/helm   # must match VM architecture
az connectedk8s delete --name test-cluster --resource-group <rg> --yes
```

#### b. Helm 4 compatibility (if this release targets Helm 4)

The CLI auto-detects Helm 4 via `get_helm_major_version()` — no env var is needed if Helm 4 is on `PATH` or installed to `~/.azure/helm/`. Use `HELM_CLIENT_PATH` only to point to a Helm 4 binary in a non-standard location.

```bash
# Option 1: Helm 4 on PATH (auto-detected, no env var needed)
kind create cluster --name helm4-test
az connectedk8s connect --name helm4-test --resource-group <rg> --subscription <sub>

# Option 2: Helm 4 in a custom location
export HELM_CLIENT_PATH=/tmp/helm4
az connectedk8s connect --name helm4-test --resource-group <rg> --subscription <sub>
unset HELM_CLIENT_PATH
```

#### c. HELM_CLIENT_PATH override

```bash
export HELM_CLIENT_PATH=/path/to/custom/helm
az connectedk8s connect ... --debug 2>&1 | grep "helm binary"
# Expected: "Using helm binary: /path/to/custom/helm"
unset HELM_CLIENT_PATH
```

#### d. `--debug` flag verification

```bash
az connectedk8s connect ... --debug 2>&1 | grep -i "helm binary\|Downloading helm"
# Expected: "Using helm binary: /home/azureuser/.azure/helm/v3.x.x/linux-<arch>/helm"
```

### Step 7 — Run E2E tests

**Wiki:** [K8sExtensionConformanceTests — Run the E2E tests](https://github.com/devdiv-microsoft/K8sExtensionConformanceTests/wiki/5.-Run-the-E2E-tests)

**Pipeline settings:**

| Field | Value |
|---|---|
| Branch | `release-v<version>-whl` |
| Environment | `prod` |
| Scenario | `Arc` |
| IsProdInfra | `true` |
| Timeout | `50 min` |

**triggerParams** (use raw WHL URL from step 5):

```json
{ "overrideconnectedk8sextension": "<whl-raw-url>" }
```

<details>
<summary><strong>Past examples</strong></summary>

| Version | triggerParams |
|---|---|
| v1.11.1 | `{ "overrideconnectedk8sextension": "https://raw.githubusercontent.com/AzureArcForKubernetes/connectedk8s/release-v1.11.1-whl/src/connectedk8s/connectedk8s-1.11.1-py2.py3-none-any.whl" }` |
| v1.10.12 | `{ "overrideconnectedk8sextension": "https://raw.githubusercontent.com/AzureArcForKubernetes/connectedk8s/b75913fb58321a75ff9389eac5e745d4e56137b8/src/connectedk8s/connectedk8s-1.10.12-py2.py3-none-any.whl" }` |
| v1.10.8 | `{ "overrideconnectedk8sextension": "https://github.com/AzureArcForKubernetes/connectedk8s/raw/31a776a32057c310b3ccfba9803eefa78337a93b/connectedk8s-1.10.8-py2.py3-none-any.whl" }` |

</details>

### Step 8 — Partner signoff

Send the WHL URL from Step 5 to partner teams and request signoff. Use the email template and signoff table below.

#### Email template

**To:** junweihe@microsoft.com; Vineeth.Thumma@microsoft.com; safeerm@microsoft.com; revchandra@microsoft.com; jagamu@microsoft.com

**Cc:** Anubhuti.Manohar@microsoft.com; Nicoleta.Zlati@microsoft.com; Matthew.Resnick@microsoft.com; deesharma@microsoft.com; jianyunt@microsoft.com

> **Subject:** Connectedk8s CLI release `<version>` sign off
>
> Hi - we are releasing a new version of **az connectedk8s**.
>
> In this release:
> - *bullet point summary of changes (e.g. "We are upgrading Helm v3 to a newer version (CLI client side only)")*
> - *...*
>
> We would appreciate it if you could take some time to validate this release and share your feedback.
>
> Here is the connectedk8s WHL file:
> `<whl-raw-url>`
>
> ```
> az extension remove --name connectedk8s
> az version
> az extension add --source <whl-raw-url>
> az version
> ```
>
> | Scenario | Owner | Signoff |
> |---|---|---|
> | Arc pipeline test run (agent validation) | Ashlee | |
> | Runners | Ashlee | |
> | Onboarding — Public | Ashlee | |
> | Onboarding — Mooncake | Ashlee / Deeksha | |
> | Onboarding — Fairfax | Ashlee | |
> | Azure Gov cloud | Junwei He | |
> | Connectivity / Proxy | Safeer, Revanth | |
> | CL / RBAC | Vineeth | |
> | AIO on AKSEE | Jagadish | |

Wait for all partners to validate and sign off before proceeding to the upstream PR.

### Step 9 — Sovereign cloud validation (Fairfax / Mooncake)

Sovereign clouds (Fairfax, Mooncake) use separate identity endpoints (`login.microsoftonline.us`, `login.chinacloudapi.cn`) that require dedicated accounts — standard `@microsoft.com` credentials do not work. Rely on **partner signoff** for sovereign cloud coverage:

| Cloud | Partner | Signoff row |
|---|---|---|
| Fairfax (AzureUSGovernment) | Junwei He | Azure Gov cloud |
| Mooncake (AzureChinaCloud) | Deeksha | Onboarding — Mooncake |

If you **do** have sovereign cloud credentials, the test sequence is identical to Step 6a but with cloud switching:

```bash
az cloud set --name AzureUSGovernment   # or AzureChinaCloud
az login && az account set --subscription <sovereign-sub-id>
az extension remove --name connectedk8s
az extension add --source <whl-raw-url> --yes
rm -rf ~/.azure/helm
kind delete cluster --name sovereign-test && kind create cluster --name sovereign-test
az connectedk8s connect --name sovereign-test --resource-group <rg> --subscription <sovereign-sub-id>
file ~/.azure/helm/**/linux-**/helm
az cloud set --name AzureCloud   # always reset when done
```

---

## Phase 2: Upstream

### Step 10 — Sync the fork before opening the PR

**GitHub portal:** Fork main > **"Sync fork"** button

Or via terminal:

```bash
git fetch upstream && git merge upstream/main
```

### Step 11 — Open the upstream PR

| Field | Value |
|---|---|
| **From** | `AzureArcForKubernetes/connectedk8s` branch `release-v<version>` |
| **To** | `Azure/azure-cli-extensions` branch `main` |
| **PR title** | `connectedk8s: release v<version>` |

- Include `HISTORY.rst` changes in the PR description
- If no review after 2+ days, post in the [Azure CLI Teams channel](https://teams.microsoft.com/l/channel/19%3A31160a5ec7e24ba0b9d58a5e812c43dd%40thread.tacv2/Azure%20CLI?groupId=9a661795-1b01-4a5b-9dd5-be571422334c&tenantId=72f988bf-86f1-41af-91ab-2d7cd011db47). If still no response, reach out directly to the Azure CLI team's on-call reviewer or your team's CLI contact.

### Step 12 — Sync the fork after merge

After the upstream PR is merged, your extension will ship in the next az CLI release. Check the [Azure CLI milestones](https://github.com/Azure/azure-cli/milestones) to see when the next release is scheduled.

**GitHub portal:** "Sync fork" — or:

```bash
git fetch upstream && git merge upstream/main
```

---

## Troubleshooting

### CI Pipeline — "Could not find valid pipeline YAML file for this branch/tag"

**Cause:** Pipeline definition is connected to `Azure/azure-cli-extensions` (upstream). Release branches only exist on the fork (`AzureArcForKubernetes/connectedk8s`).

**Fix:** Edit the pipeline in ADO > change source repository to the fork > re-run with branch `release-v<version>`.

### CI Pipeline — Job times out at 60 minutes

Azure Pipelines has a 60-minute hard limit per job. If logs show **"100% tests passed"** before the timeout message, the release is validated. The timeout hits cleanup/teardown after the tests already finished. **This is not a test failure.** Proceed with the release.

### Verify helm binary architecture

Run on the VM after connect:

```bash
file ~/.azure/helm/**/linux-**/helm
```

| Architecture | Expected output |
|---|---|
| AMD64 | `ELF 64-bit LSB executable, x86-64` |
| ARM64 | `ELF 64-bit LSB executable, ARM aarch64` |

### See which helm binary was used

```bash
az connectedk8s connect ... --debug 2>&1 | grep -i "helm binary\|Downloading helm"
# Expected: "Using helm binary: /home/azureuser/.azure/helm/v3.20.1/linux-amd64/helm"
```

### Custom helm binary via HELM_CLIENT_PATH

Always use `export`, never inline:

```bash
export HELM_CLIENT_PATH=/tmp/helm4
az connectedk8s connect ... --debug 2>&1 | grep "helm binary"
# Expected: "Using helm binary: /tmp/helm4"
unset HELM_CLIENT_PATH
```

### "Different Kubernetes cluster" Arc error (stale cluster identity)

```bash
az connectedk8s delete --name <name> --resource-group <rg> --yes
kind delete cluster --name <name> && kind create cluster --name <name>
# re-run connect
```

### ARM64 VM — never pipe curl to tar

Piping can silently truncate. Use two steps:

```bash
curl -fsSL --retry 3 -o /tmp/helm.tar.gz <url>
tar -xz -C /tmp/ -f /tmp/helm.tar.gz
```

### ARM64 VM — free disk space

Can be triggered by kind node images filling the disk **or** by `az extension add --source` (pip install) when `/tmp` or the home directory is full (`[Errno 28] No space left on device`).

```bash
docker image prune -a --force
# Or for full cleanup:
docker system prune -a --force
```

### `version: null` in `az extension show` / `az version`

Affects **only** WHL-based connectedk8s installs (i.e. during pre-release validation via `az extension add --source <whl>`). Will **not** show up when the extension is released and installed from the official index.

Extension functionality is **completely unaffected**; this is display-only.

---

## References

| Resource | Link |
|---|---|
| Local fork | https://github.com/AzureArcForKubernetes/connectedk8s/ |
| Upstream repo | https://github.com/Azure/azure-cli-extensions/ |
| CI pipeline | [connectedk8s CLI Testing](https://dev.azure.com/ClusterConfigurationAgent/Extension%20CLI/_build?definitionId=643&_a=summary) |
| E2E wiki | [K8sExtensionConformanceTests](https://github.com/devdiv-microsoft/K8sExtensionConformanceTests/wiki/5.-Run-the-E2E-tests) |
| Azure CLI Teams channel | [Azure CLI](https://teams.microsoft.com/l/channel/19%3A31160a5ec7e24ba0b9d58a5e812c43dd%40thread.tacv2/Azure%20CLI?groupId=9a661795-1b01-4a5b-9dd5-be571422334c&tenantId=72f988bf-86f1-41af-91ab-2d7cd011db47) |
| Release process recording | [az cli connectedk8s release process (recording)](https://microsoft.sharepoint.com/:v:/t/AzureArcPlatform/cQrZoU5bJF8RT6qqVMnYJmtZEgUC3ddlZyu9xgvxLIYBeAB8pw) |

> **Reminder:** Periodically sync the local fork from upstream via the GitHub portal "Sync fork" button.
