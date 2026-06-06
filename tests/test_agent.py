from unittest.mock import AsyncMock, patch, MagicMock
import pytest
from app.agent import QwenClient

@pytest.mark.asyncio
async def test_generate_response_success():
    # Mocking the HTTP call to verify schema handling
    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client_class.return_value.__aenter__.return_value = mock_client

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"choices": [{"message": {"content": "Hello!"}}]}
        # raise_for_status is a method, not async
        mock_response.raise_for_status = MagicMock()
        mock_client.post.return_value = mock_response

        client = QwenClient(api_key="test-key-for-unit-testing")
        result = await client.generate_response("Hi")

        assert result == {"choices": [{"message": {"content": "Hello!"}}]}
        mock_client.post.assert_called_once()
