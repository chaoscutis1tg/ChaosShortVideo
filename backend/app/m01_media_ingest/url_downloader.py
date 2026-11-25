"""Multi-platform video & m3u8 downloader built on `yt-dlp` with smart URL normalization."""

import asyncio
from dataclasses import dataclass
from pathlib import Path
import re
from typing import Any, Dict, Optional
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from app.m00_core_contracts import DownloadFailedError, ProgressCallback

URL_EXTRACT_RE = re.compile(r"https?://[^\s\"'<>]+", re.IGNORECASE)
# Matches localized or mobile Bilibili paths like `/vi/video/BV...`, `/en/video/av...`
BILIBILI_LOCALE_VIDEO_RE = re.compile(
    r"^/(?:[a-z]{2}(?:-[a-z]+)?/)?video/((?:BV[0-9A-Za-z]+)|(?:av\d+))/?$",
    re.IGNORECASE,
)
NOISY_QUERY_KEYS = {
    "trackid",
    "spm_id_from",
    "vd_source",
    "bstar_from",
    "from_spmid",
    "share_source",
    "share_medium",
    "share_plat",
    "share_session_id",
    "share_tag",
    "timestamp",
    "unique_k",
}

DEFAULT_CHROME_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)


def normalize_video_url(raw_input: str) -> str:
    """Extract and normalize video URLs (fixes Bilibili `/vi/video/BV...` & share text)."""
    text = raw_input.strip()
    m_url = URL_EXTRACT_RE.search(text)
    if m_url:
        text = m_url.group(0).rstrip(".,;!)")

    parsed = urlparse(text)
    host = (parsed.netloc or "").lower()
    path = parsed.path or ""
    query_dict = parse_qs(parsed.query, keep_blank_values=False)

    # Normalize bilibili.com/<lang>/video/BV... and m.bilibili.com/video/BV...
    if host.endswith("bilibili.com"):
        host = "www.bilibili.com"
        m_bv = BILIBILI_LOCALE_VIDEO_RE.match(path)
        if m_bv:
            vid_id = m_bv.group(1)
            path = f"/video/{vid_id}/"
        # Preserve only episode index `p` if present
        kept_q = {k: v for k, v in query_dict.items() if k in ("p",)}
        return urlunparse(
            (parsed.scheme or "https", host, path, "", urlencode(kept_q, doseq=True), "")
        )

    # Clean noisy tracking parameters on bilibili.tv & general video platforms
    cleaned_q = {k: v for k, v in query_dict.items() if k.lower() not in NOISY_QUERY_KEYS}
    return urlunparse(
        (
            parsed.scheme or "https",
            parsed.netloc,
            path,
            parsed.params,
            urlencode(cleaned_q, doseq=True),
            "",
        )
    )


def _build_http_headers(url: str) -> Dict[str, str]:
    headers = {"User-Agent": DEFAULT_CHROME_UA}
    low = url.lower()
    if "bilibili.com" in low:
        headers["Referer"] = "https://www.bilibili.com/"
    elif "bilibili.tv" in low:
        headers["Referer"] = "https://www.bilibili.tv/"
    return headers


@dataclass(frozen=True)
class DownloadedMediaBundle:
    """Result returned by YtDlpDownloader."""

    video_path: Path
    subtitle_path: Optional[Path]
    title: str
    normalized_url: str


class YtDlpDownloader:
    """Downloads videos (YouTube, TikTok, Bilibili .com/.tv, Douyin, HLS/m3u8) into MP4."""

    async def probe_url_info(self, raw_url: str) -> Dict[str, Any]:
        """Fetch lightweight metadata (title, duration, thumbnail) without downloading video."""
        clean_url = normalize_video_url(raw_url)
        return await asyncio.to_thread(self._probe_sync, clean_url)

    @staticmethod
    def _probe_sync(clean_url: str) -> Dict[str, Any]:
        try:
            import yt_dlp  # type: ignore
        except ImportError as exc:
            raise DownloadFailedError("Chưa cài đặt thư viện yt-dlp.") from exc

        opts = {
            "quiet": True,
            "no_warnings": True,
            "noplaylist": True,
            "http_headers": _build_http_headers(clean_url),
        }
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(clean_url, download=False) or {}
                return {
                    "normalized_url": clean_url,
                    "title": str(info.get("title") or "Video Trực Tuyến"),
                    "duration_sec": int(round(float(info.get("duration") or 0))),
                    "thumbnail": str(info.get("thumbnail") or ""),
                    "extractor": str(info.get("extractor_key") or ""),
                }
        except Exception as exc:
            raise DownloadFailedError(f"Không thể đọc thông tin liên kết ({clean_url}): {exc}") from exc

    async def download(
        self,
        url: str,
        dest_dir: Path,
        on_progress: Optional[ProgressCallback] = None,
    ) -> DownloadedMediaBundle:
        """Normalize URL and download remote video asynchronously."""
        dest_dir.mkdir(parents=True, exist_ok=True)
        clean_url = normalize_video_url(url)
        return await asyncio.to_thread(self._download_sync, clean_url, dest_dir, on_progress)

    @staticmethod
    def _download_sync(
        clean_url: str,
        dest_dir: Path,
        on_progress: Optional[ProgressCallback],
    ) -> DownloadedMediaBundle:
        try:
            import yt_dlp  # type: ignore
        except ImportError as exc:
            raise DownloadFailedError("Chưa cài đặt thư viện yt-dlp.") from exc

        # Clean stale partial downloads if retrying the same project folder
        for old_f in dest_dir.glob("source_video*"):
            old_f.unlink(missing_ok=True)

        def _hook(d: dict) -> None:
            if on_progress is None:
                return
            if d.get("status") == "downloading":
                total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
                downloaded = d.get("downloaded_bytes") or 0
                pct = (downloaded / total * 100.0) if total > 0 else 25.0
                on_progress(
                    "INGESTING",
                    round(min(pct, 95.0), 1),
                    f"Đang tải video từ liên kết ({round(downloaded / 1048576, 1)} MB)...",
                )

        out_tmpl = str(dest_dir / "source_video.%(ext)s")
        headers = _build_http_headers(clean_url)
        ydl_opts = {
            "format": "bestvideo[height<=1080]+bestaudio/best[height<=1080]/best",
            "merge_output_format": "mp4",
            "outtmpl": out_tmpl,
            "noplaylist": True,
            "quiet": True,
            "no_warnings": True,
            "retries": 4,
            "fragment_retries": 4,
            "http_headers": headers,
            "progress_hooks": [_hook],
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(clean_url, download=True)
                title = str((info or {}).get("title") or "Video Tai Ve")
        except Exception as exc:
            raise DownloadFailedError(f"Tải liên kết thất bại ({clean_url}): {exc}") from exc

        # Optional non-fatal pass to grab soft subtitles (.srt) if platform provides them publicly
        try:
            sub_opts = {
                "skip_download": True,
                "writesubtitles": True,
                "subtitleslangs": ["vi", "zh.*", "en.*"],
                "subtitlesformat": "srt",
                "outtmpl": out_tmpl,
                "noplaylist": True,
                "quiet": True,
                "no_warnings": True,
                "ignoreerrors": True,
                "http_headers": headers,
            }
            with yt_dlp.YoutubeDL(sub_opts) as ydl_sub:
                ydl_sub.download([clean_url])
        except Exception:
            pass

        candidates = sorted(
            [
                p
                for p in dest_dir.glob("source_video.*")
                if p.suffix.lower() in {".mp4", ".mkv", ".webm", ".mov", ".ts"}
            ],
            key=lambda p: p.stat().st_size,
            reverse=True,
        )
        if not candidates:
            raise DownloadFailedError("Tải xong nhưng không tìm thấy tệp video đầu ra.")

        srt_candidates = [p for p in dest_dir.glob("source_video*.srt") if p.stat().st_size > 32]
        sub_path = srt_candidates[0] if srt_candidates else None
        return DownloadedMediaBundle(
            video_path=candidates[0],
            subtitle_path=sub_path,
            title=title,
            normalized_url=clean_url,
        )
