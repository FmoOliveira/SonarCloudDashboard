import pytest
import aiohttp
from unittest.mock import MagicMock, AsyncMock
from sonarcloud_api import SonarCloudAPI

@pytest.mark.asyncio
async def test_request_timeout():
    """Test that API requests include a timeout"""
    mock_session = MagicMock()
    # Mock the context manager for session.get
    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.json.return_value = {"components": [], "paging": {"total": 0}}
    
    # Needs to return a context manager
    mock_session.get.return_value.__aenter__.return_value = mock_response
    
    api = SonarCloudAPI("test_token", session=mock_session)

    # Call a method that triggers a request
    await api.get_organization_projects("test_org")

    # Verify session.get was called
    mock_session.get.assert_called()
    
    # Check that timeout is passed
    call_kwargs = mock_session.get.call_args.kwargs
    assert 'timeout' in call_kwargs, "Timeout parameter missing in API request"
    assert isinstance(call_kwargs['timeout'], aiohttp.ClientTimeout)
    assert call_kwargs['timeout'].total == 30
