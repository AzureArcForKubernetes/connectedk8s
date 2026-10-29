# Connectedk8s Testing

Tests need to be configured before running.

1. Make a copy of `config.json.dist` and rename it to `config.json` (the config.json is git ignored).
1. Fill in the details of the newly created `config.json` file:
    - Note that the code doesn't verify that you have a valid RBAC service principal application, so a fake one can be used for testing.
    - `customLocationsOid`: The custom locations RP service principal object ID for enabling the custom locations feature.
1. Please make sure to test using a service principal with minimal privileges to replicate customer scenarios.
    - Make sure you test with a service principal without Graph API permissions, as some customers don't expect to need it.

## Linux source-test runner compatibility

On Linux, `azdev test connectedk8s` uses `pytest-forked` to isolate each test.
`pytest-forked` 1.7.5 cannot serialize the `NodeId` objects in pytest 9.2 test
reports. Both passing and skipped tests can therefore fail with
`running the test EXITED with status 3` before their results reach the parent
process.

The pipeline's source-test job installs `pytest<9.2` after `azdev setup` so that
setup cannot replace the compatible version. Use the same order locally:

```bash
azdev setup -c ../azure-cli -r ./ -e connectedk8s
python -m pip install 'pytest<9.2'
azdev test connectedk8s
```

Remove this cap once the forked runner supports pytest 9.2 report serialization
and both passing and skipped tests have been verified with fork isolation.
This does not change live-test selection or the Pester onboarding jobs.