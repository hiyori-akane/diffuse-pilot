"""
WebResearchService のユニットテスト
"""

import hashlib
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.services.web_research import WebResearchService


@pytest.fixture
def web_research_service():
    """WebResearchService のフィクスチャ"""
    with patch("src.services.web_research.get_settings") as mock_settings:
        mock_settings.return_value = MagicMock(
            google_search_api_key="test_api_key",
            google_search_engine_id="test_engine_id",
        )
        service = WebResearchService()
        yield service


@pytest.mark.asyncio
async def test_build_search_query(web_research_service):
    """検索クエリ構築のテスト"""
    query = web_research_service._build_search_query("アニメスタイルの風景画")
    assert "Stable Diffusion" in query
    assert "アニメスタイルの風景画" in query
    assert "prompt techniques" in query


@pytest.mark.asyncio
async def test_hash_query(web_research_service):
    """クエリのハッシュ計算のテスト"""
    query = "test query"
    expected_hash = hashlib.sha256(query.encode("utf-8")).hexdigest()
    actual_hash = web_research_service._hash_query(query)
    assert actual_hash == expected_hash


@pytest.mark.asyncio
async def test_get_cached_result_miss(web_research_service):
    """キャッシュミスのテスト"""
    with patch.object(web_research_service, "session_maker") as mock_session_maker:
        mock_session = AsyncMock()
        mock_result = AsyncMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=None)
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session_maker.return_value.__aenter__.return_value = mock_session

        result = await web_research_service._get_cached_result("test query")
        assert result is None


@pytest.mark.asyncio
async def test_research_best_practices_no_api_key():
    """Google Search APIキーが未設定の場合のテスト"""
    with patch("src.services.web_research.get_settings") as mock_settings:
        mock_settings.return_value = MagicMock(
            google_search_api_key="",
            google_search_engine_id="",
        )
        service = WebResearchService()
        result = await service.research_best_practices("test theme")
        assert result is None


@pytest.mark.asyncio
async def test_search_google_with_rate_limit(web_research_service):
    """レート制限のテスト"""
    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client_class.return_value.__aenter__.return_value = mock_client

        # 429エラーを返してからリトライで成功
        mock_response_429 = MagicMock()
        mock_response_429.status_code = 429
        mock_response_success = MagicMock()
        mock_response_success.status_code = 200
        mock_response_success.json.return_value = {
            "items": [
                {
                    "title": "Test Title",
                    "snippet": "Test Snippet",
                    "link": "https://example.com",
                }
            ]
        }

        mock_client.get.side_effect = [mock_response_429, mock_response_success]

        start_time = time.time()
        results = await web_research_service._search_google("test query")
        elapsed = time.time() - start_time

        # バックオフが発生していることを確認（少なくとも2秒はかかるはず）
        assert elapsed >= 2.0
        assert len(results) == 1
        assert results[0]["title"] == "Test Title"


@pytest.mark.asyncio
async def test_extract_best_practices(web_research_service):
    """ベストプラクティス抽出のテスト"""
    search_results = [
        {
            "title": "Stable Diffusion Tips",
            "snippet": "Use detailed prompts...",
            "link": "https://example.com/tips",
        }
    ]

    with patch.object(web_research_service.llm_client, "chat") as mock_chat:
        mock_chat.return_value = """
{
  "summary": "Test summary",
  "prompt_techniques": ["technique1", "technique2"],
  "recommended_loras": ["lora1"],
  "recommended_settings": {
    "steps": 30,
    "cfg_scale": 8.0,
    "sampler": "DPM++ 2M Karras"
  },
  "sources": ["https://example.com/tips"]
}
"""
        result = await web_research_service._extract_best_practices("test theme", search_results)

        assert result["summary"] == "Test summary"
        assert "technique1" in result["prompt_techniques"]
        assert result["recommended_settings"]["steps"] == 30
        assert "https://example.com/tips" in result["sources"]
