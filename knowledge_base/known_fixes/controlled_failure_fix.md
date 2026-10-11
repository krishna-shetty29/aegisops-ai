# Known fix: controlled pipeline failure

Problem:
The sample application test failed with:
Controlled failure: the pipeline was told to fail.

Successful resolution:
Run the Azure Pipeline with the Force the test stage to fail option unchecked.

Expected result:
The tests pass and the pipeline succeeds.