# Offline demo setup

The fixture selector must use the same Python interpreter where the project is
installed. From the repository root in Windows PowerShell:

```powershell
py -3 -m venv .demo-venv
.\.demo-venv\Scripts\python.exe -m pip install -e .
.\.demo-venv\Scripts\python.exe -m brick_builder.fixture_demo_selector --run-root .\runs\fixture-demo
```

The dedicated `.demo-venv` uses the desktop Python selected by `py -3`, so it
does not reuse a development or Codex-managed virtual environment. The editable
install supplies `jsonschema`. The demo never installs dependencies or accesses
the network automatically; rerun the install command yourself when the launch
interpreter reports `SCHEMA_DEPENDENCY`.
