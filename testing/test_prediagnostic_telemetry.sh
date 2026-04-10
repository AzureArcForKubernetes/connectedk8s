#!/bin/bash
# test_prediagnostic_telemetry.sh
# Exercises all prediagnostic failing scenarios and verifies az connectedk8s connect fails.
# Usage: bash test_prediagnostic_telemetry.sh [resource_group] [location]
# Prerequisites: kubectl configured, az cli with connectedk8s extension installed, kubeconfig set.

RESOURCE_GROUP="${1:-audittest}"
LOCATION="${2:-eastus2euap}"
ORIGINAL_COREFILE=""
PASS_COUNT=0
FAIL_COUNT=0

# ── Colors ───────────────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
MAGENTA='\033[0;35m'
GRAY='\033[0;37m'
NC='\033[0m' # No Color

log_info()  { echo -e "${CYAN}[INFO]${NC} $1"; }
log_pass()  { echo -e "${GREEN}[PASS]${NC} $1"; ((PASS_COUNT++)); }
log_fail()  { echo -e "${RED}[FAIL]${NC} $1"; ((FAIL_COUNT++)); }
log_sep()   { echo -e "\n${GRAY}$(printf '─%.0s' {1..70})${NC}"; }

# ── CoreDNS helpers ──────────────────────────────────────────────────────────

save_coredns() {
    ORIGINAL_COREFILE=$(kubectl get configmap coredns -n kube-system -o jsonpath='{.data.Corefile}' 2>&1)
    log_info "CoreDNS original config saved."
}

restore_coredns() {
    if [[ -z "$ORIGINAL_COREFILE" ]]; then return; fi
    log_info "Restoring CoreDNS..."
    kubectl patch configmap coredns -n kube-system --type merge \
        -p "{\"data\":{\"Corefile\":$(echo "$ORIGINAL_COREFILE" | python3 -c 'import json,sys; print(json.dumps(sys.stdin.read()))')}}" \
        > /dev/null 2>&1
    kubectl rollout restart deployment/coredns -n kube-system > /dev/null 2>&1
    kubectl rollout status deployment/coredns -n kube-system --timeout=60s > /dev/null 2>&1
    log_info "CoreDNS restored."
}

# Apply a CoreDNS hosts block redirecting specified hostnames to 192.0.2.1 (black-hole)
# Usage: apply_coredns_block "host1 host2 ..."
apply_coredns_block() {
    local hosts_entries=""
    for host in $1; do
        hosts_entries+="      192.0.2.1 ${host}\n"
    done

    local new_corefile
    new_corefile=$(cat <<EOF
.:53 {
    errors
    ready
    health {
      lameduck 5s
    }
    hosts {
${hosts_entries}      fallthrough
    }
    kubernetes cluster.local in-addr.arpa ip6.arpa {
      pods insecure
      fallthrough in-addr.arpa ip6.arpa
      ttl 30
    }
    prometheus :9153
    forward . /etc/resolv.conf
    cache 30
    loop
    reload
    loadbalance
    import custom/*.override
    template ANY ANY internal.cloudapp.net {
      match "^(?:[^.]+\\.){4,}internal\\.cloudapp\\.net\\.$"
      rcode NXDOMAIN
      fallthrough
    }
    template ANY ANY reddog.microsoft.com {
      rcode NXDOMAIN
    }
}
import custom/*.server
EOF
)
    kubectl patch configmap coredns -n kube-system --type merge \
        -p "{\"data\":{\"Corefile\":$(echo "$new_corefile" | python3 -c 'import json,sys; print(json.dumps(sys.stdin.read()))')}}" \
        > /dev/null 2>&1
    kubectl rollout restart deployment/coredns -n kube-system > /dev/null 2>&1
    kubectl rollout status deployment/coredns -n kube-system --timeout=60s > /dev/null 2>&1
    log_info "CoreDNS block applied for: $1"
}

# ── Test runner ──────────────────────────────────────────────────────────────

run_connect_test() {
    local cluster_name="$1"
    local test_desc="$2"

    log_info "Running: az connectedk8s connect -g $RESOURCE_GROUP -n $cluster_name"
    output=$(az connectedk8s connect -g "$RESOURCE_GROUP" -n "$cluster_name" --location "$LOCATION" 2>&1)
    exit_code=$?

    echo ""
    echo "  ── Output excerpt ──"
    echo "$output" | grep -E "Pre-onboarding Diagnostic|Precheck summary|pre-checks|required pre-checks" \
        | while IFS= read -r line; do echo -e "  ${YELLOW}${line}${NC}"; done
    echo "$output" | grep "\[Telemetry\]" \
        | while IFS= read -r line; do echo -e "  ${MAGENTA}${line}${NC}"; done

    if [[ $exit_code -ne 0 ]]; then
        log_pass "$test_desc → command failed as expected (exit $exit_code)"
        if ! echo "$output" | grep -q "\[Telemetry\]"; then
            echo -e "  ${YELLOW}WARNING: No [Telemetry] line found in output.${NC}"
        fi
    else
        log_fail "$test_desc → command SUCCEEDED but was expected to FAIL"
    fi
}

cleanup_az_resource() {
    local cluster_name="$1"
    log_info "Cleaning up ARM resource: $cluster_name (if it exists)"
    az connectedk8s delete -g "$RESOURCE_GROUP" -n "$cluster_name" --force -y > /dev/null 2>&1
}

apply_bad_crd() {
    local crd_name="$1"
    kubectl apply -f - > /dev/null 2>&1 <<EOF
apiVersion: apiextensions.k8s.io/v1
kind: CustomResourceDefinition
metadata:
  name: ${crd_name}
  annotations:
    meta.helm.sh/release-name: some-other-component
    meta.helm.sh/release-namespace: default
spec:
  group: clusterconfig.azure.com
  names:
    kind: FakeResource
    listKind: FakeResourceList
    plural: $(echo "$crd_name" | cut -d. -f1)
    singular: fakeresource
  scope: Cluster
  versions:
  - name: v1
    served: true
    storage: true
    schema:
      openAPIV3Schema:
        type: object
EOF
    log_info "Bad CRD applied: $crd_name"
}

remove_crd() {
    kubectl delete crd "$1" --ignore-not-found=true > /dev/null 2>&1
    log_info "CRD removed: $1"
}

apply_pod_quota() {
    kubectl create namespace azure-arc-release --dry-run=client -o yaml | kubectl apply -f - > /dev/null 2>&1
    kubectl apply -f - > /dev/null 2>&1 <<EOF
apiVersion: v1
kind: ResourceQuota
metadata:
  name: block-pods
  namespace: azure-arc-release
spec:
  hard:
    pods: "0"
EOF
    log_info "ResourceQuota applied: pods=0 in azure-arc-release"
}

remove_pod_quota() {
    kubectl delete resourcequota block-pods -n azure-arc-release --ignore-not-found=true > /dev/null 2>&1
    log_info "ResourceQuota removed."
}

# ── Main ─────────────────────────────────────────────────────────────────────

echo -e "\n${CYAN}Pre-onboarding Diagnostic Telemetry Test Suite${NC}"
echo -e "${CYAN}Resource Group: $RESOURCE_GROUP | Location: $LOCATION${NC}"

save_coredns

# ─────────────────────────────────────────────────────────────────────────────
log_sep
log_info "TEST 1: Block MCR (outbound connectivity failure)"
log_info "Expected telemetry: onboardingErrorType=prediagnostics-failure, outboundConnectivityCheck=Failed"
# ─────────────────────────────────────────────────────────────────────────────
CLUSTER="adblocktest-mcr"
cleanup_az_resource "$CLUSTER"
apply_coredns_block "mcr.microsoft.com"
run_connect_test "$CLUSTER" "MCR outbound block"
restore_coredns
cleanup_az_resource "$CLUSTER"

# ─────────────────────────────────────────────────────────────────────────────
log_sep
log_info "TEST 2: Block Entra auth endpoint (Entra check failure)"
log_info "Expected telemetry: onboardingErrorType=prediagnostics-failure, entraCheck=Failed"
# ─────────────────────────────────────────────────────────────────────────────
CLUSTER="adblocktest-entra"
cleanup_az_resource "$CLUSTER"
apply_coredns_block "login.microsoftonline.com"
run_connect_test "$CLUSTER" "Entra endpoint block"
restore_coredns
cleanup_az_resource "$CLUSTER"

# ─────────────────────────────────────────────────────────────────────────────
log_sep
log_info "TEST 3: Block BOTH MCR + Entra (combined outbound failure)"
log_info "Expected telemetry: outboundConnectivityCheck=Failed, entraCheck=Failed"
# ─────────────────────────────────────────────────────────────────────────────
CLUSTER="adblocktest-all-outbound"
cleanup_az_resource "$CLUSTER"
apply_coredns_block "mcr.microsoft.com login.microsoftonline.com"
run_connect_test "$CLUSTER" "MCR + Entra combined block"
restore_coredns
cleanup_az_resource "$CLUSTER"

# ─────────────────────────────────────────────────────────────────────────────
log_sep
log_info "TEST 4: CRD ownership conflict (crdCheck failure)"
log_info "Expected telemetry: onboardingErrorType=prediagnostics-failure, crdCheck=Failed"
# ─────────────────────────────────────────────────────────────────────────────
CLUSTER="adblocktest-crd"
cleanup_az_resource "$CLUSTER"
apply_bad_crd "extensionconfigs.clusterconfig.azure.com"
run_connect_test "$CLUSTER" "CRD ownership conflict"
remove_crd "extensionconfigs.clusterconfig.azure.com"
cleanup_az_resource "$CLUSTER"

# ─────────────────────────────────────────────────────────────────────────────
log_sep
log_info "TEST 5: Job cannot be scheduled (ResourceQuota pods=0)"
log_info "Expected telemetry: onboardingErrorType=prediagnostics-job-execution-error, jobExecutionStatus=NotScheduled"
# ─────────────────────────────────────────────────────────────────────────────
CLUSTER="adblocktest-nojob"
cleanup_az_resource "$CLUSTER"
apply_pod_quota
run_connect_test "$CLUSTER" "Job not schedulable"
remove_pod_quota
cleanup_az_resource "$CLUSTER"

# ─────────────────────────────────────────────────────────────────────────────
log_sep
log_info "TEST 6: Happy path (all checks pass — command should SUCCEED)"
log_info "Expected: no [Telemetry] failure lines, command exits 0"
# ─────────────────────────────────────────────────────────────────────────────
CLUSTER="adblocktest-happy"
log_info "Running: az connectedk8s connect -g $RESOURCE_GROUP -n $CLUSTER"
output=$(az connectedk8s connect -g "$RESOURCE_GROUP" -n "$CLUSTER" --location "$LOCATION" 2>&1)
exit_code=$?
telemetry_fail=$(echo "$output" | grep "\[Telemetry\].*prediagnostics")

if [[ $exit_code -eq 0 && -z "$telemetry_fail" ]]; then
    log_pass "Happy path → command succeeded, no failure telemetry"
elif [[ $exit_code -eq 0 && -n "$telemetry_fail" ]]; then
    log_fail "Happy path → command succeeded BUT unexpected [Telemetry] failure lines found:"
    echo "$telemetry_fail" | while IFS= read -r line; do echo -e "  ${RED}${line}${NC}"; done
else
    log_fail "Happy path → command FAILED unexpectedly (exit $exit_code)"
fi
cleanup_az_resource "$CLUSTER"

# ─────────────────────────────────────────────────────────────────────────────
log_sep
echo ""
echo -e "${CYAN}Test run complete.${NC}"
echo -e "  ${GREEN}Passed: $PASS_COUNT${NC}"
echo -e "  ${RED}Failed: $FAIL_COUNT${NC}"
log_sep
