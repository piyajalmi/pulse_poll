
# PulsePoll Testing Guide

## Scope Covered
- Authentication flows
  - signup page render
  - add user (duplicate + success)
  - login validation (invalid + admin success)
  - logout session cleanup
- Poll flows
  - create poll validation rules
  - vote page auth guard
- Vote flows
  - submit vote (not found, empty option, success)
  - results API response and realtime sync hook
- Utility modules
  - security hashing/encryption behavior
  - firebase payload write and failure handling

## Run Tests
From project root:

```powershell
pytest -q
```

If your machine shows pytest cache permission warnings:

```powershell
pytest -q -p no:cacheprovider
```

Run a single suite:

```powershell
pytest -q tests\test_app_flows.py
```

Run one test:

```powershell
pytest -q tests\test_vote_submit_routes.py::test_submit_vote_success_pushes_realtime_updates
```

## Generate Shareable Report
Create a JUnit XML report file (easy to share in CI or with teammates):

```powershell
pytest -q --junitxml=test-report.xml
```

This generates `test-report.xml` in the project root.

## How To Demonstrate To Someone
Use this quick 3-step demo in terminal:

1. Show test inventory:
```powershell
pytest --collect-only -q
```

2. Run all tests:
```powershell
pytest -q -p no:cacheprovider
```

3. Show report generation:
```powershell
pytest -q --junitxml=test-report.xml
```

Then explain:
- tests are isolated (mocked DB/Firebase/socket layers),
- they validate route behavior, status codes, and business rules,
- they are fast and can run in CI on every commit.
