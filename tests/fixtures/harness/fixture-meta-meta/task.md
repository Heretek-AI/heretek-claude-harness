# Fixture Meta-Meta

This fixture is a self-test. Its task: write the minimum files needed to make
`harness_test.py` succeed against an empty fixture directory.

In a real harness run, `claude` reads this file and acts on it. In tests,
`subprocess.run` is mocked so no `claude` invocation happens.

Expected behavior: runner reads task.md, captures no diff (nothing to change),
writes empty artifact bundle.
