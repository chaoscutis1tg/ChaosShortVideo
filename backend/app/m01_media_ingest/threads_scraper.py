"""Public Threads / Reddit / Social Post & Replies Scraper (`m01_media_ingest`).

Strictly adheres to M00 contracts with zero cross-module imports and standard HTTP APIs.
"""

import html as html_lib
import json
import re
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse
import uuid
import httpx

from app.m00_core_contracts import (
    MediaIngestError,
    ScrapedThreadBundleDTO,
    ThreadCommentItemDTO,
)

SCRIPT_JSON_RE = re.compile(
    r"<script[^>]*type=[\"']application/(?:ld\+)?json[\"'][^>]*>([\s\S]*?)</script>",
    re.IGNORECASE,
)
META_TAG_RE = re.compile(
    r"<meta[^>]+(?:property|name)=[\"']([^\"']+)[\"'][^>]+content=[\"']([^\"']*)[\"'][^>]*>",
    re.IGNORECASE,
)
META_TAG_REV_RE = re.compile(
    r"<meta[^>]+content=[\"']([^\"']*)[\"'][^>]+(?:property|name)=[\"']([^\"']+)[\"'][^>]*>",
    re.IGNORECASE,
)
HANDLE_LINE_RE = re.compile(r"^\s*@?([A-Za-z0-9_.-]{2,32})\s*[:：\-—]\s*(.+)$")
URL_CLEAN_RE = re.compile(r"https?://\S+")

# Vietnamese Threads / GenZ teen-code dictionary for smooth TTS speech synthesis
VN_SLANG_MAP: Dict[str, str] = {
    "ko": "không",
    "k": "không",
    "khum": "không",
    "hong": "không",
    "hok": "không",
    "đc": "được",
    "dc": "được",
    "dk": "được",
    "chx": "chưa",
    "bt": "bình thường",
    "bth": "bình thường",
    "mn": "mọi người",
    "mng": "mọi người",
    "ny": "người yêu",
    "nyc": "người yêu cũ",
    "nv": "nhân viên",
    "cty": "công ty",
    "gđ": "gia đình",
    "gd": "gia đình",
    "tr": "trời",
    "chời": "trời",
    "đhs": "chẳng hiểu sao",
    "dhs": "chẳng hiểu sao",
    "ntn": "như thế nào",
    "vs": "với",
    "j": "gì",
    "z": "vậy",
    "cx": "cũng",
    "sp": "sản phẩm",
    "kh": "khách hàng",
    "ib": "nhắn tin",
    "cmt": "bình luận",
    "rep": "trả lời",
    "mik": "mình",
    "mk": "mình",
    "bh": "bây giờ",
    "trc": "trước",
    "ng": "người",
    "ngta": "người ta",
    "nta": "người ta",
    "vl": "thật sự",
    "vcl": "thật sự",
    "kb": "kết bạn",
}


def format_compact_likes(count: int) -> str:
    """Format integer like count into compact Vietnamese social badge (e.g. `1,4K`)."""
    if count <= 0:
        return ""
    if count >= 1_000_000:
        return f"{count / 1_000_000:.1f}".replace(".", ",") + "Tr"
    if count >= 1_000:
        return f"{count / 1_000:.1f}".replace(".", ",") + "K"
    return str(count)


def normalize_vn_social_slang(text: str) -> str:
    """Expand Vietnamese social abbreviations and strip raw URLs so TTS pronounces naturally."""
    cleaned = URL_CLEAN_RE.sub("", text or "").strip()
    if not cleaned:
        return ""

    def _repl(match: re.Match[str]) -> str:
        word = match.group(0)
        low = word.lower()
        mapped = VN_SLANG_MAP.get(low)
        if not mapped:
            return word
        if word[0].isupper():
            return mapped.capitalize()
        return mapped

    pattern = r"\b(" + "|".join(re.escape(k) for k in VN_SLANG_MAP.keys()) + r")\b"
    out = re.sub(pattern, _repl, cleaned, flags=re.IGNORECASE)
    return re.sub(r"\s{2,}", " ", out).strip()


def _extract_meta_map(raw_html: str) -> Dict[str, str]:
    meta: Dict[str, str] = {}
    for m in META_TAG_RE.finditer(raw_html):
        meta[m.group(1).lower()] = html_lib.unescape(m.group(2)).strip()
    for m in META_TAG_REV_RE.finditer(raw_html):
        meta[m.group(2).lower()] = html_lib.unescape(m.group(1)).strip()
    return meta


def _walk_threads_posts(node: Any, collected: List[Dict[str, Any]], seen_texts: set[str]) -> None:
    """Recursively inspect Threads Relay SJS JSON structures for `post` items with captions."""
    if isinstance(node, dict):
        caption = node.get("caption")
        user = node.get("user")
        if isinstance(caption, dict) and isinstance(caption.get("text"), str):
            txt = caption["text"].strip()
            if len(txt) >= 3 and txt not in seen_texts:
                seen_texts.add(txt)
                uname = ""
                verified = False
                if isinstance(user, dict):
                    uname = str(user.get("username") or "").strip()
                    verified = bool(user.get("is_verified"))
                like_cnt = int(node.get("like_count") or 0)
                reply_cnt = 0
                t_info = node.get("text_post_app_info")
                if isinstance(t_info, dict):
                    reply_cnt = int(t_info.get("direct_reply_count") or 0)
                collected.append(
                    {
                        "username": f"@{uname.lstrip('@')}" if uname else "@threads_user",
                        "text": txt,
                        "likes": max(0, like_cnt),
                        "replies": max(0, reply_cnt),
                        "is_verified": verified,
                    }
                )
        for val in node.values():
            if isinstance(val, (dict, list)):
                _walk_threads_posts(val, collected, seen_texts)
    elif isinstance(node, list):
        for item in node:
            if isinstance(item, (dict, list)):
                _walk_threads_posts(item, collected, seen_texts)


class ThreadsScraperService:
    """Extracts OP post & community comments from Threads, Reddit, Web forums, or pasted text."""

    DEFAULT_HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8",
        "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7",
    }

    @classmethod
    async def scrape_post_and_comments(
        cls,
        post_url: str = "",
        raw_pasted_text: str = "",
    ) -> ScrapedThreadBundleDTO:
        """Fetch public post & replies from URL and/or parse pasted raw thread conversation."""
        clean_url = (post_url or "").strip()
        clean_paste = (raw_pasted_text or "").strip()

        if not clean_url and not clean_paste:
            raise MediaIngestError(
                "Vui lòng dán đường dẫn bài viết Threads/Reddit hoặc nội dung văn bản."
            )

        bundle: Optional[ScrapedThreadBundleDTO] = None
        if clean_url:
            host = (urlparse(clean_url).netloc or "").lower()
            if "reddit.com" in host or "redd.it" in host:
                bundle = await cls._scrape_reddit_json(clean_url)
            else:
                bundle = await cls._scrape_threads_or_web(clean_url)

        if clean_paste:
            pasted_bundle = cls._parse_pasted_text(clean_paste, source_url=clean_url)
            if bundle is None:
                bundle = pasted_bundle
            else:
                # Merge user-pasted comments into URL-scraped bundle!
                existing_texts = {c.raw_text.strip().lower() for c in bundle.comments}
                extra_items: List[ThreadCommentItemDTO] = []
                if (
                    bundle.op_display_text.startswith("Chủ đề thảo luận từ")
                    and len(pasted_bundle.op_display_text) > 10
                ):
                    bundle.op_display_text = pasted_bundle.op_display_text
                    bundle.op_spoken_vi_text = pasted_bundle.op_spoken_vi_text
                    bundle.topic_title = pasted_bundle.topic_title
                else:
                    # Treat all pasted blocks as extra comments if OP was already scraped from URL
                    pasted_all = [
                        ThreadCommentItemDTO(
                            comment_id=f"cmt_paste_0",
                            author_handle=pasted_bundle.op_author_handle,
                            raw_text=pasted_bundle.op_display_text,
                            display_text=pasted_bundle.op_display_text,
                            spoken_vi_text=pasted_bundle.op_spoken_vi_text,
                            likes_count=128,
                            likes_display="128",
                        ),
                        *pasted_bundle.comments,
                    ]
                    for pc in pasted_all:
                        if pc.raw_text.strip().lower() not in existing_texts:
                            existing_texts.add(pc.raw_text.strip().lower())
                            extra_items.append(pc)
                if extra_items:
                    bundle.comments = [*bundle.comments, *extra_items]

        if bundle is None:
            raise MediaIngestError(
                "Không thể trích xuất nội dung từ đường dẫn. Bạn hãy dán nhanh nội dung chữ vào ô bên dưới nhé."
            )
        return bundle

    @classmethod
    async def _scrape_reddit_json(cls, url: str) -> Optional[ScrapedThreadBundleDTO]:
        clean = url.split("?")[0].rstrip("/")
        json_url = f"{clean}.json?limit=35&raw_json=1"
        try:
            async with httpx.AsyncClient(
                headers={**cls.DEFAULT_HEADERS, "User-Agent": "ChaosShortVideoStudio/3.3"},
                follow_redirects=True,
                timeout=12.0,
            ) as client:
                resp = await client.get(json_url)
                if resp.status_code != 200:
                    return await cls._scrape_threads_or_web(url)
                payload = resp.json()

            if not isinstance(payload, list) or len(payload) < 1:
                return None

            post_data = payload[0]["data"]["children"][0]["data"]
            title = str(post_data.get("title") or "Chủ đề Reddit").strip()
            selftext = str(post_data.get("selftext") or "").strip()
            op_full = f"{title}\n{selftext}".strip() if selftext else title
            author = str(post_data.get("author") or "reddit_op").strip()
            ups = int(post_data.get("ups") or 0)
            num_c = int(post_data.get("num_comments") or 0)

            comments: List[ThreadCommentItemDTO] = []
            if len(payload) > 1:
                for idx, child in enumerate(payload[1].get("data", {}).get("children", [])):
                    if child.get("kind") != "t1":
                        continue
                    cd = child.get("data") or {}
                    body = str(cd.get("body") or "").strip()
                    c_author = str(cd.get("author") or f"user_{idx + 1}").strip()
                    if (
                        not body
                        or body in ("[deleted]", "[removed]")
                        or c_author.lower() == "automoderator"
                    ):
                        continue
                    c_ups = max(0, int(cd.get("ups") or 0))
                    comments.append(
                        ThreadCommentItemDTO(
                            comment_id=f"rd_{uuid.uuid4().hex[:8]}",
                            author_handle=f"@{c_author}",
                            raw_text=body[:1200],
                            display_text=body[:1200],
                            spoken_vi_text=normalize_vn_social_slang(body[:1200]),
                            likes_count=c_ups,
                            likes_display=format_compact_likes(c_ups) or "42",
                        )
                    )
                    if len(comments) >= 24:
                        break

            return ScrapedThreadBundleDTO(
                source_url=url,
                platform="reddit",
                topic_title=title[:180],
                op_author_handle=f"@{author}",
                op_display_text=op_full[:2000],
                op_spoken_vi_text=normalize_vn_social_slang(op_full[:2000]),
                op_likes_display=format_compact_likes(ups) or "1,5K",
                op_replies_display=format_compact_likes(num_c) or str(max(len(comments), 18)),
                comments=comments,
                extraction_note=f"Đã hút trực tiếp bài gốc + {len(comments)} bình luận từ Reddit.",
            )
        except Exception:
            return await cls._scrape_threads_or_web(url)

    @classmethod
    async def _scrape_threads_or_web(cls, url: str) -> Optional[ScrapedThreadBundleDTO]:
        platform = (
            "threads"
            if ("threads.net" in url.lower() or "threads.com" in url.lower())
            else "web"
        )
        url_handle = "@chuthot"
        m_handle = re.search(r"/@([A-Za-z0-9_.-]+)", url)
        if m_handle:
            url_handle = f"@{m_handle.group(1)}"

        extracted_posts: List[Dict[str, Any]] = []
        og_title = ""
        og_desc = ""

        # Step A: Direct HTML + Embedded Relay SJS JSON extraction
        try:
            async with httpx.AsyncClient(
                headers=cls.DEFAULT_HEADERS, follow_redirects=True, timeout=11.0
            ) as client:
                resp = await client.get(url)
                if resp.status_code < 400 and resp.text:
                    raw_html = resp.text
                    meta = _extract_meta_map(raw_html)
                    og_title = meta.get("og:title") or meta.get("twitter:title") or ""
                    og_desc = meta.get("og:description") or meta.get("description") or ""

                    seen_t: set[str] = set()
                    for sm in SCRIPT_JSON_RE.finditer(raw_html):
                        blob = sm.group(1).strip()
                        if not blob or ("caption" not in blob and "articleBody" not in blob):
                            continue
                        try:
                            parsed = json.loads(blob)
                            _walk_threads_posts(parsed, extracted_posts, seen_t)
                        except Exception:
                            continue
        except Exception:
            pass

        # Step B: If no reply items found yet, query clean Jina Reader text representation
        jina_lines: List[str] = []
        if len(extracted_posts) <= 1:
            try:
                async with httpx.AsyncClient(
                    headers={"Accept": "text/plain", "X-Return-Format": "text"},
                    follow_redirects=True,
                    timeout=11.0,
                ) as client:
                    j_resp = await client.get(f"https://r.jina.ai/{url}")
                    if j_resp.status_code == 200 and len(j_resp.text.strip()) > 30:
                        for ln in j_resp.text.splitlines():
                            s = ln.strip()
                            if (
                                len(s) >= 12
                                and not s.lower().startswith(("title:", "url source:", "markdown content:", "http", "![", "[log in", "log in"))
                            ):
                                jina_lines.append(s)
            except Exception:
                pass

        if extracted_posts:
            op = extracted_posts[0]
            op_text = op["text"]
            op_handle = op["username"] or url_handle
            comments: List[ThreadCommentItemDTO] = []
            for idx, item in enumerate(extracted_posts[1:25], start=1):
                c_txt = item["text"]
                likes_n = int(item.get("likes") or 0)
                comments.append(
                    ThreadCommentItemDTO(
                        comment_id=f"th_{uuid.uuid4().hex[:8]}",
                        author_handle=item.get("username") or f"@thanhvien_{idx:02d}",
                        raw_text=c_txt[:1200],
                        display_text=c_txt[:1200],
                        spoken_vi_text=normalize_vn_social_slang(c_txt[:1200]),
                        likes_count=likes_n,
                        likes_display=format_compact_likes(likes_n) or str(max(12, 180 - idx * 11)),
                        is_verified=bool(item.get("is_verified")),
                    )
                )
            title_short = op_text.splitlines()[0][:120] if op_text else (og_title or "Chủ đề Threads")
            return ScrapedThreadBundleDTO(
                source_url=url,
                platform=platform,
                topic_title=title_short[:180],
                op_author_handle=op_handle,
                op_display_text=op_text[:2000],
                op_spoken_vi_text=normalize_vn_social_slang(op_text[:2000]),
                op_likes_display=format_compact_likes(int(op.get("likes") or 0)) or "2,1K",
                op_replies_display=format_compact_likes(int(op.get("replies") or 0))
                or str(max(len(comments), 64)),
                op_is_verified=bool(op.get("is_verified")),
                comments=comments,
                extraction_note=(
                    f"Đã trích xuất bài gốc + {len(comments)} bình luận công khai từ liên kết."
                    if comments
                    else "Đã lấy bài gốc từ liên kết (phần bình luận công khai hạn chế, AI sẽ hỗ trợ triển khai bình luận tiêu biểu)."
                ),
            )

        # Fallback from OpenGraph or Jina text lines
        op_candidate = og_desc.strip()
        if not op_candidate and jina_lines:
            op_candidate = jina_lines[0]
        if not op_candidate and og_title:
            op_candidate = og_title.strip()

        if op_candidate:
            # Clean Threads meta prefix like `@user on Threads: "..."`
            op_candidate = re.sub(
                r"^.*?on Threads:\s*[\"“]?(.*?)[\"”]?\s*$",
                r"\1",
                op_candidate,
                flags=re.DOTALL,
            ).strip()
            extra_cmts: List[ThreadCommentItemDTO] = []
            for idx, jl in enumerate(jina_lines[1:16], start=1):
                if jl == op_candidate or len(jl) > 650:
                    continue
                hm = HANDLE_LINE_RE.match(jl)
                h_name = f"@{hm.group(1)}" if hm else f"@thanhvien_{idx:02d}"
                c_body = hm.group(2).strip() if hm else jl
                extra_cmts.append(
                    ThreadCommentItemDTO(
                        comment_id=f"web_{uuid.uuid4().hex[:8]}",
                        author_handle=h_name,
                        raw_text=c_body[:1000],
                        display_text=c_body[:1000],
                        spoken_vi_text=normalize_vn_social_slang(c_body[:1000]),
                        likes_count=max(8, 160 - idx * 12),
                        likes_display=str(max(8, 160 - idx * 12)),
                    )
                )

            clean_t = (og_title.split("•")[0].split("|")[0].strip() or op_candidate[:95])[:180]
            if len(clean_t) < 4:
                clean_t = op_candidate[:95]
            return ScrapedThreadBundleDTO(
                source_url=url,
                platform=platform,
                topic_title=clean_t,
                op_author_handle=url_handle,
                op_display_text=op_candidate[:2000],
                op_spoken_vi_text=normalize_vn_social_slang(op_candidate[:2000]),
                op_likes_display="1,8K",
                op_replies_display=str(max(len(extra_cmts), 52)),
                comments=extra_cmts,
                extraction_note=(
                    f"Đã lấy nội dung bài viết + {len(extra_cmts)} phản hồi từ trang."
                    if extra_cmts
                    else "Đã lấy nội dung bài gốc; AI sẽ bổ sung các góc nhìn bình luận tiêu biểu."
                ),
            )

        return ScrapedThreadBundleDTO(
            source_url=url,
            platform=platform,
            topic_title=f"Chủ đề thảo luận từ {url_handle}",
            op_author_handle=url_handle,
            op_display_text=f"Chủ đề thảo luận từ bài đăng của {url_handle}: {url}",
            op_spoken_vi_text=f"Cùng xem cộng đồng mạng đang bàn luận gì về bài đăng của {url_handle.lstrip('@')}",
            comments=[],
            extraction_note="Bài đăng yêu cầu đăng nhập để xem trực tiếp — bạn có thể dán nhanh chữ vào ô dự phòng hoặc để AI triển khai.",
        )

    @classmethod
    def _parse_pasted_text(cls, raw_text: str, source_url: str = "") -> ScrapedThreadBundleDTO:
        """Parse user-pasted Thread post + comments (newline blocks, bullets, or `@user: text`)."""
        blocks = [b.strip() for b in re.split(r"\n\s*\n|\r?\n(?=[@•\-*]|\d+[.)]\s)", raw_text) if b.strip()]
        if len(blocks) <= 1:
            blocks = [ln.strip() for ln in raw_text.splitlines() if ln.strip()]

        first = blocks[0] if blocks else raw_text.strip()
        op_handle = "@chuthot"
        m_op = HANDLE_LINE_RE.match(first)
        if m_op:
            op_handle = f"@{m_op.group(1).lstrip('@')}"
            op_body = m_op.group(2).strip()
        else:
            op_body = re.sub(r"^[-•*]\s*", "", first).strip()

        comments: List[ThreadCommentItemDTO] = []
        for idx, blk in enumerate(blocks[1:25], start=1):
            cleaned_blk = re.sub(r"^(?:[-•*]|\d+[.)])\s*", "", blk).strip()
            if len(cleaned_blk) < 2:
                continue
            hm = HANDLE_LINE_RE.match(cleaned_blk)
            c_handle = f"@{hm.group(1).lstrip('@')}" if hm else f"@binhluan_{idx:02d}"
            c_body = hm.group(2).strip() if hm else cleaned_blk
            likes_val = max(15, 420 - idx * 27)
            comments.append(
                ThreadCommentItemDTO(
                    comment_id=f"pst_{uuid.uuid4().hex[:8]}",
                    author_handle=c_handle,
                    raw_text=c_body[:1200],
                    display_text=c_body[:1200],
                    spoken_vi_text=normalize_vn_social_slang(c_body[:1200]),
                    likes_count=likes_val,
                    likes_display=format_compact_likes(likes_val),
                )
            )

        title = op_body.splitlines()[0][:110] if op_body else "Thảo luận nổi bật trên Threads"
        return ScrapedThreadBundleDTO(
            source_url=source_url,
            platform="threads",
            topic_title=title[:180],
            op_author_handle=op_handle,
            op_display_text=op_body[:2000],
            op_spoken_vi_text=normalize_vn_social_slang(op_body[:2000]),
            op_likes_display="2,4K",
            op_replies_display=str(max(len(comments), 68)),
            comments=comments,
            extraction_note=f"Đã tách bài gốc và {len(comments)} bình luận từ văn bản dán vào.",
        )

