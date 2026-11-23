structure-not-prose: The tests assert status codes, reason codes, JSON fields or returned values; none asserts on error message wording, log wording or other prose.
behavior-titles: Test and describe titles say the behavior in plain words; none contains a ticket key, a behavior or case number, or an artifact name.
no-own-mocks: No test mocks or replaces one of the app's own modules (vi.mock on a relative path); fakes go in through the app's dependencies.
no-derived-expectations: Expected values are literals or hand-built fixtures, never computed by calling the production function under test or importing its constants.
no-pins: No test asserts a constant's own value, such as expecting a limit constant to equal 120. Testing behavior at a boundary (120 characters accepted, 121 rejected) is not a pin.
