"""
The OpenAI() client raises immediately at construction time if no API key
is present in the environment — even though these tests mock every actual
API call and never send a real request. Setting a dummy key here lets the
test suite run cleanly in CI or on a machine that hasn't configured a real
key yet, without ever touching the network.
"""
import os

os.environ.setdefault("OPENAI_API_KEY", "sk-test-dummy-key-for-unit-tests-only")
