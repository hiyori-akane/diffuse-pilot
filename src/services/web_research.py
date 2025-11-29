"""
Webリサーチサービス

Google Custom Search APIを使用してプロンプトテクニックやベストプラクティスを検索
"""

import asyncio
import hashlib
import json
import time
from datetime import datetime, timedelta
from typing import Any

import httpx
from sqlalchemy import select

from src.config.logging import get_logger
from src.config.settings import get_settings
from src.database.connection import get_session_maker
from src.models.web_research import WebResearchCache
from src.services.error_handler import ApplicationError
from src.services.ollama_client import OllamaClient

logger = get_logger(__name__)


class WebResearchError(ApplicationError):
    """Webリサーチエラー"""

    def __init__(self, message: str, details: dict[str, Any] = None, **kwargs):
        # Use INTERNAL_ERROR unless a specific ErrorCode is available
        from src.services.error_handler import ErrorCode
        super().__init__(code=ErrorCode.INTERNAL_ERROR, message=message, details=details, **kwargs)


class WebResearchService:
    """Webリサーチサービス"""

    # キャッシュの有効期限（デフォルト: 7日間）
    CACHE_TTL_DAYS = 7

    # レート制限: リクエスト間の最小間隔（秒）
    MIN_REQUEST_INTERVAL = 1.0

    # リトライ設定
    MAX_RETRIES = 3
    INITIAL_BACKOFF = 2.0  # 初期バックオフ時間（秒）

    # ベストプラクティス抽出用のシステムプロンプト
    EXTRACTION_SYSTEM_PROMPT = """あなたはStable Diffusionの画像生成エキスパートです。
Web検索結果からプロンプトテクニック、推奨LoRA、推奨設定を抽出してください。

出力は以下のJSON形式で返してください：
{
  "summary": "検索結果の要約（2-3文で簡潔に）",
  "prompt_techniques": ["テクニック1", "テクニック2", ...],
  "recommended_loras": ["LoRA名1", "LoRA名2", ...],
  "recommended_settings": {
    "steps": 推奨ステップ数（整数）,
    "cfg_scale": 推奨CFGスケール（浮動小数点）,
    "sampler": "推奨サンプラー名",
    "scheduler": "推奨スケジューラ名（未指定も可）"
  },
  "sources": ["参照URL1", "参照URL2", ...]
}

明確な情報が見つからない項目は空のリストや空の辞書を返してください。
"""

    def __init__(self):
        self.settings = get_settings()
        self.session_maker = get_session_maker()
        self.llm_client = OllamaClient()
        self._last_request_time: float | None = None
        self._rate_limit_lock = asyncio.Lock()  # レート制限のスレッドセーフ保護

    async def close(self):
        """クライアントを閉じる"""
        await self.llm_client.close()

    async def research_best_practices(
        self, theme: str, use_cache: bool = True
    ) -> dict[str, Any] | None:
        """テーマに基づいてベストプラクティスをリサーチ

        Args:
            theme: リサーチテーマ（例: "アニメスタイルの風景画"）
            use_cache: キャッシュを使用するか

        Returns:
            リサーチ結果の辞書:
                {
                    "summary": "要約テキスト",
                    "prompt_techniques": ["technique1", "technique2", ...],
                    "recommended_loras": ["lora1", "lora2", ...],
                    "recommended_settings": {"steps": 30, "cfg_scale": 8.0, ...},
                    "sources": ["url1", "url2", ...]
                }
            Google Search APIキーが未設定の場合はNone

        Raises:
            WebResearchError: リサーチエラー
        """
        # Google Search APIキーが未設定の場合はスキップ
        if not self.settings.google_search_api_key or not self.settings.google_search_engine_id:
            logger.info("Google Search API not configured, skipping web research")
            return None

        try:
            logger.info(f"Starting web research for theme: {theme}")

            # クエリを構築
            query = self._build_search_query(theme)

            # キャッシュをチェック
            if use_cache:
                cached_result = await self._get_cached_result(query)
                if cached_result:
                    logger.info("Using cached research result")
                    return cached_result

            # Google検索を実行
            search_results = await self._search_google(query)

            if not search_results:
                logger.warning("No search results found")
                return None

            # LLMでベストプラクティスを抽出
            best_practices = await self._extract_best_practices(theme, search_results)

            # キャッシュに保存
            if use_cache:
                await self._cache_result(query, best_practices)

            logger.info("Web research completed successfully")
            return best_practices

        except Exception as e:
            logger.error(f"Error in web research: {str(e)}")
            if isinstance(e, WebResearchError):
                raise
            raise WebResearchError("Failed to perform web research", original_error=e)

    def _build_search_query(self, theme: str) -> str:
        """検索クエリを構築

        Args:
            theme: リサーチテーマ

        Returns:
            検索クエリ
        """
        # Stable Diffusion プロンプトに関連する検索クエリを構築
        query = f"Stable Diffusion {theme} prompt techniques best practices"
        logger.debug(f"Built search query: {query}")
        return query

    async def _get_cached_result(self, query: str) -> dict[str, Any] | None:
        """キャッシュから結果を取得

        Args:
            query: 検索クエリ

        Returns:
            キャッシュされた結果、存在しない場合はNone
        """
        query_hash = self._hash_query(query)

        async with self.session_maker() as session:
            stmt = (
                select(WebResearchCache)
                .where(WebResearchCache.query_hash == query_hash)
                .where(WebResearchCache.expires_at > datetime.utcnow())
            )
            result = await session.execute(stmt)
            cache_entry = result.scalar_one_or_none()

            if cache_entry:
                logger.debug(f"Cache hit for query hash: {query_hash}")
                return cache_entry.results

            logger.debug(f"Cache miss for query hash: {query_hash}")
            return None

    async def _cache_result(self, query: str, results: dict[str, Any]) -> None:
        """結果をキャッシュに保存

        Args:
            query: 検索クエリ
            results: リサーチ結果
        """
        query_hash = self._hash_query(query)
        expires_at = datetime.utcnow() + timedelta(days=self.CACHE_TTL_DAYS)

        async with self.session_maker() as session:
            # 既存のキャッシュエントリを検索
            stmt = select(WebResearchCache).where(WebResearchCache.query_hash == query_hash)
            result = await session.execute(stmt)
            existing_entry = result.scalar_one_or_none()

            if existing_entry:
                # 既存エントリを更新
                existing_entry.query = query
                existing_entry.results = results
                existing_entry.created_at = datetime.utcnow()
                existing_entry.expires_at = expires_at
            else:
                # 新しいキャッシュエントリを作成
                cache_entry = WebResearchCache(
                    query_hash=query_hash,
                    query=query,
                    results=results,
                    expires_at=expires_at,
                )
                session.add(cache_entry)

            await session.commit()
            logger.debug(f"Cached result for query hash: {query_hash}")

    def _hash_query(self, query: str) -> str:
        """クエリのハッシュを計算

        Args:
            query: 検索クエリ

        Returns:
            SHA-256 ハッシュ（16進数文字列）
        """
        return hashlib.sha256(query.encode("utf-8")).hexdigest()

    async def _search_google(self, query: str) -> list[dict[str, Any]]:
        """Google Custom Search APIで検索

        Args:
            query: 検索クエリ

        Returns:
            検索結果のリスト

        Raises:
            WebResearchError: API呼び出しエラー
        """
        # レート制限を適用（スレッドセーフ）
        async with self._rate_limit_lock:
            if self._last_request_time is not None:
                elapsed = time.time() - self._last_request_time
                if elapsed < self.MIN_REQUEST_INTERVAL:
                    await asyncio.sleep(self.MIN_REQUEST_INTERVAL - elapsed)

            # リクエスト時刻を記録
            request_time = time.time()

        url = "https://www.googleapis.com/customsearch/v1"
        params = {
            "key": self.settings.google_search_api_key,
            "cx": self.settings.google_search_engine_id,
            "q": query,
            "num": 5,  # 上位5件の結果を取得
        }

        # 指数バックオフでリトライ
        for attempt in range(self.MAX_RETRIES):
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.get(url, params=params)
                    # リクエスト時刻を更新（スレッドセーフ）
                    async with self._rate_limit_lock:
                        self._last_request_time = request_time

                    if response.status_code == 429:  # Too Many Requests
                        if attempt < self.MAX_RETRIES - 1:
                            backoff_time = self.INITIAL_BACKOFF * (2**attempt)
                            logger.warning(
                                f"Rate limit hit, backing off for {backoff_time}s (attempt {attempt + 1}/{self.MAX_RETRIES})"
                            )
                            await asyncio.sleep(backoff_time)
                            continue
                        else:
                            raise WebResearchError("Google Search API rate limit exceeded")

                    response.raise_for_status()
                    data = response.json()

                    items = data.get("items", [])
                    results = []
                    for item in items:
                        results.append(
                            {
                                "title": item.get("title", ""),
                                "snippet": item.get("snippet", ""),
                                "link": item.get("link", ""),
                            }
                        )

                    logger.info(f"Google Search returned {len(results)} results")
                    return results

            except httpx.HTTPError as e:
                if attempt < self.MAX_RETRIES - 1:
                    backoff_time = self.INITIAL_BACKOFF * (2**attempt)
                    logger.warning(
                        f"HTTP error in Google Search, retrying in {backoff_time}s: {str(e)}"
                    )
                    await asyncio.sleep(backoff_time)
                    continue
                else:
                    raise WebResearchError(f"Google Search API error: {str(e)}", original_error=e)

        # ここには到達しないはず
        raise WebResearchError("Google Search API failed after retries")

    async def _extract_best_practices(
        self, theme: str, search_results: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """検索結果からベストプラクティスを抽出

        Args:
            theme: リサーチテーマ
            search_results: Google検索結果

        Returns:
            ベストプラクティスの辞書

        Raises:
            WebResearchError: 抽出エラー
        """
        try:
            # 検索結果を整形
            search_summary = "\n\n".join(
                [
                    f"タイトル: {result['title']}\n説明: {result['snippet']}\nURL: {result['link']}"
                    for result in search_results
                ]
            )

            user_prompt = f"""テーマ: {theme}

検索結果:
{search_summary}

上記の検索結果から、{theme}の画像生成に役立つベストプラクティスを抽出してください。"""

            # JSON schema を生成
            json_schema = {
                "type": "object",
                "properties": {
                    "summary": {"type": "string"},
                    "prompt_techniques": {"type": "array", "items": {"type": "string"}},
                    "recommended_loras": {"type": "array", "items": {"type": "string"}},
                    "recommended_settings": {
                        "type": "object",
                        "properties": {
                            "steps": {"type": "integer"},
                            "cfg_scale": {"type": "number"},
                            "sampler": {"type": "string"},
                            "scheduler": {"type": "string"},
                        },
                    },
                    "sources": {"type": "array", "items": {"type": "string"}},
                },
                "required": [
                    "summary",
                    "prompt_techniques",
                    "recommended_loras",
                    "recommended_settings",
                    "sources",
                ],
            }

            response_text = await self.llm_client.chat(
                messages=[
                    {"role": "system", "content": self.EXTRACTION_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.3,  # より確定的な出力を得るために低めに設定
                format=json_schema,
            )

            # レスポンスをパース
            try:
                result = json.loads(response_text)
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse LLM response as JSON: {str(e)}")
                # エラーメッセージには機密情報を含めない
                raise WebResearchError("LLM returned invalid JSON format", original_error=e)

            # ソースURLを検索結果から取得（空リストの場合も対応）
            if not result.get("sources"):
                result["sources"] = [item["link"] for item in search_results]

            logger.info("Best practices extracted successfully")
            return result

        except WebResearchError:
            # WebResearchError はそのまま再スロー
            raise
        except Exception as e:
            logger.error(f"Error extracting best practices: {str(e)}")
            raise WebResearchError(
                "Failed to extract best practices from search results", original_error=e
            )
