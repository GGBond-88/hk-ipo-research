# Environment Issues

## EI-001: System memory insufficient for Node.js/Vite build and dev server under Playwright
- **Description**: System has 4GB total RAM with typically < 600MB free. Node.js Vite build (`npm run build`) fails with "JavaScript heap out of memory" during esbuild transforms. Vite dev server started by Playwright tests also OOMs immediately. The `test_dev_server_starts_and_serves_expected_content` test passes only because it starts a lightweight Vite dev server without Playwright browser overhead.
- **Assumption**: These tests would pass on a system with >= 8GB RAM. The test logic is correct; the failure is purely an environment resource constraint.

## EI-002: OPENROUTER_API_KEY not configured
- **Description**: No OpenRouter API key is set in the environment, causing 5 pipeline E2E tests to skip. The tests use `api_key_present` fixture which calls `pytest.skip()` when the key is absent. This is by design.
- **Assumption**: Tests skip gracefully and intentionally. API-key-dependent tests will pass when a valid key is configured.
User comments: OPENROUTER_API_KEY location
C:\Users\Administrator\Documents\github\hk-ipo-research\.env