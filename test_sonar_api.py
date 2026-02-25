import pytest
import aiohttp
import re
from aioresponses import aioresponses
from aiohttp import ClientResponseError
from tenacity import wait_none

# Import the retry object from our module
from app import fetch_sonar_history_async

# Strip all artificial latency from the test suite
fetch_sonar_history_async.retry.wait = wait_none()

# --- Pytest Configuration ---
pytestmark = pytest.mark.asyncio

@pytest.fixture
def mock_url():
    """Returns the regex pattern matching the SonarCloud API endpoint."""
    return re.compile(r'^https://sonarcloud\.io/api/measures/search_history\?.*$')

async def test_retry_on_rate_limit_recovers_successfully(mock_url):
    """
    Validates that the pipeline successfully suppresses HTTP 429 and 502 errors,
    executes the backoff, and eventually resolves the payload.
    """
    with aioresponses() as m:
        # Arrange: Queue a sequence of HTTP responses.
        m.get(mock_url, status=429) # Attempt 1: Rate Limited
        m.get(mock_url, status=502) # Attempt 2: Bad Gateway
        
        # Successful payload expected by our specific app.py parser
        payload = {
            "measures": [
                {
                    "metric": "vulnerabilities",
                    "history": [
                        {"date": "2026-02-23T00:00:00Z", "value": "12"}
                    ]
                }
            ]
        }
        m.get(mock_url, status=200, payload=payload) # Attempt 3: Success

        async with aiohttp.ClientSession() as session:
            # Act
            result = await fetch_sonar_history_async(session, "test_project", "dummy_token", days=30)

            # Assert
            assert len(result) == 1
            assert result[0]["project_key"] == "test_project"
            assert result[0]["vulnerabilities"] == 12
            
            # Architectural Verification: Ensure exactly 3 network calls were attempted
            total_requests = sum(len(req_list) for req_list in m.requests.values())
            assert total_requests == 3

async def test_fail_fast_on_deterministic_error(mock_url):
    """
    Validates that the pipeline does NOT retry on deterministic 4xx errors,
    preventing wasted CPU cycles and immediate exception surfacing.
    """
    with aioresponses() as m:
        # Arrange: Return a 404 Not Found
        m.get(mock_url, status=404)

        async with aiohttp.ClientSession() as session:
            # Act & Assert
            with pytest.raises(ClientResponseError) as exc_info:
                await fetch_sonar_history_async(session, "test_project", "dummy_token", days=30)
            
            assert exc_info.value.status == 404
            
            # Architectural Verification: Ensure strictly 1 call was made (no retries)
            total_requests = sum(len(req_list) for req_list in m.requests.values())
            assert total_requests == 1
