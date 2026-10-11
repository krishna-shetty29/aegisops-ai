# Pipeline test failure runbook

If a Python test fails, first read the failed test name and its error message.

Check whether FORCE_PIPELINE_FAILURE was deliberately enabled.

If FORCE_PIPELINE_FAILURE is true, the expected solution is to run the
pipeline again with Force the test stage to fail unchecked.

Then run the Python tests again and confirm they pass.