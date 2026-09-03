# Offline demo setup

The fixture selector must use the same desktop Python interpreter where the
project is installed. From the repository root in Windows PowerShell:

```powershell
python -m venv .demo-venv
.\.demo-venv\Scripts\python.exe -m pip install -e .
.\.demo-venv\Scripts\python.exe -m brick_builder.fixture_demo_selector --run-root .\runs\fixture-demo
```

The dedicated `.demo-venv` should be created from a desktop Python build with
working Tk support; do not create it from a runtime Python that lacks Tcl/Tk.
The editable install supplies `jsonschema`. The demo never installs
dependencies or accesses the network automatically; rerun the install command
yourself when the launch interpreter reports `SCHEMA_DEPENDENCY`.
