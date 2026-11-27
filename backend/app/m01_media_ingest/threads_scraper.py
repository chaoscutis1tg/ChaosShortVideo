"""Public Threads / Reddit / Social Post, Replies & Comment-Images Scraper (`m01_media_ingest`).

Strictly adheres to M00 contracts with zero cross-module imports and standard HTTP APIs.
Supports extracting both post/comment text AND attached images on Threads, Reddit, and Web posts.
"""

import asyncio
import hashlib
import html as html_lib
from io import BytesIO
import json
from pathlib import Path
import re
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse
import uuid
import httpx
from PIL import Image, ImageOps

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
DIRECT_IMG_URL_RE = re.compile(
    r"(https?://\S+?\.(?:jpg|jpeg|png|webp)(?:\?\S*)?)",
    re.IGNORECASE,
)
MD_IMG_ANY_RE = re.compile(r"!\[([^\]]*)\]\((https?://[^)\s]+)\)")
MD_THREADS_POST_LINK_RE = re.compile(
    r"^\[([^\]]+)\]\(https?://(?:www\.)?threads\.(?:com|net)/@([A-Za-z0-9_.-]+)/post/([A-Za-z0-9_-]+)[^)]*\)\s*$"
)
MD_THREADS_HANDLE_LINK_RE = re.compile(
    r"^\[([A-Za-z0-9_.-]{2,40})\]\(https?://(?:www\.)?threads\.(?:com|net)/@([A-Za-z0-9_.-]+)\)\s*$"
)
ASCII_EMOTICON_RE = re.compile(r"(?:[:;=xX][\-^']*[)DdpPvV3/(|]+|=\)+|\^\^|-_-|T_T|><)", re.UNICODE)
EMOJI_STRIP_RE = re.compile(
    "["
    "\U0001F300-\U0001FAFF"
    "\U00002600-\U000027BF"
    "\U0000FE00-\U0000FE0F"
    "\U0001F1E6-\U0001F1FF"
    "]+",
    flags=re.UNICODE,
)
STRETCHED_CHAR_RE = re.compile(r"([a-zA-Zà-ỹÀ-Ỹ])\1{2,}", re.UNICODE)

# Vietnamese Threads / GenZ teen-code dictionary for smooth native Vietnamese TTS synthesis
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
    "nhaa": "nha",
    "nhaaa": "nha",
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
    """Expand Vietnamese social abbreviations, strip emojis/emoticons & URLs for crisp TTS."""
    cleaned = URL_CLEAN_RE.sub("", text or "")
    cleaned = ASCII_EMOTICON_RE.sub(" ", cleaned)
    cleaned = EMOJI_STRIP_RE.sub(" ", cleaned)
    cleaned = STRETCHED_CHAR_RE.sub(r"\1", cleaned).strip()
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
    return re.sub(r"\s{2,}", " ", out).strip(" -•|")


def _extract_meta_map(raw_html: str) -> Dict[str, str]:
    meta: Dict[str, str] = {}
    for m in META_TAG_RE.finditer(raw_html):
        meta[m.group(1).lower()] = html_lib.unescape(m.group(2)).strip()
    for m in META_TAG_REV_RE.finditer(raw_html):
        meta[m.group(2).lower()] = html_lib.unescape(m.group(1)).strip()
    return meta


def _extract_node_best_image(node: Dict[str, Any]) -> str:
    """Extract highest-resolution attached photo URL from a Threads Relay `post` dict."""
    img_v2 = node.get("image_versions2")
    if isinstance(img_v2, dict):
        cands = img_v2.get("candidates")
        if isinstance(cands, list) and cands:
            for c in cands:
                if isinstance(c, dict) and isinstance(c.get("url"), str):
                    u = c["url"]
                    if "s150x150" not in u:
                        return u
    carousel = node.get("carousel_media")
    if isinstance(carousel, list) and carousel:
        first_c = carousel[0]
        if isinstance(first_c, dict):
            sub_u = _extract_node_best_image(first_c)
            if sub_u:
                return sub_u
    return ""


def _walk_threads_posts(node: Any, collected: List[Dict[str, Any]], seen_keys: set[str]) -> None:
    """Recursively inspect Threads Relay SJS JSON structures for `post` items & media."""
    if isinstance(node, dict):
        caption = node.get("caption")
        user = node.get("user")
        attached_img = _extract_node_best_image(node)
        cap_txt = caption.get("text").strip() if (isinstance(caption, dict) and isinstance(caption.get("text"), str)) else ""
        if (len(cap_txt) >= 2 or attached_img) and isinstance(user, dict) and user.get("username"):
            uname = str(user.get("username") or "").strip()
            dedup_key = f"{uname}:{cap_txt[:120]}:{attached_img[:80]}"
            if dedup_key not in seen_keys:
                seen_keys.add(dedup_key)
                verified = bool(user.get("is_verified"))
                av_url = str(user.get("profile_pic_url") or "")
                like_cnt = int(node.get("like_count") or 0)
                reply_cnt = 0
                t_info = node.get("text_post_app_info")
                if isinstance(t_info, dict):
                    reply_cnt = int(t_info.get("direct_reply_count") or 0)
                collected.append(
                    {
                        "username": f"@{uname.lstrip('@')}",
                        "text": cap_txt or "Xem hình đính kèm bên dưới",
                        "likes": max(0, like_cnt),
                        "replies": max(0, reply_cnt),
                        "is_verified": verified,
                        "image_url": attached_img,
                        "avatar_url": av_url,
                    }
                )
        for val in node.values():
            if isinstance(val, (dict, list)):
                _walk_threads_posts(val, collected, seen_keys)
    elif isinstance(node, list):
        for item in node:
            if isinstance(item, (dict, list)):
                _walk_threads_posts(item, collected, seen_keys)


def _is_threads_ui_noise_line(line: str) -> bool:
    """Filter out Threads navigation chrome lines inside Jina Markdown."""
    s = line.strip()
    if not s:
        return True
    low = s.lower()
    if low in {
        "translate",
        "·author",
        "author",
        "home",
        "new thread",
        "search",
        "messages",
        "activity",
        "profile",
        "insights",
        "more",
        "verified",
        "pinned",
        "top",
        "recent",
        "view activity",
    }:
        return True
    if re.match(r"^[\d,.]+[KkMm]?\s+views?$", s, flags=re.IGNORECASE):
        return True
    if re.match(r"^\d[\d,.]*[KkMm]?$", s):
        return True
    if low.startswith(("[home](", "[search](", "[log in", "log in", "# [thread](", "[](http", "title:", "url source:", "final url:", "markdown content:")):
        return True
    if "continue with instagram" in low or "terms" in low and "privacy policy" in low:
        return True
    return False


def _parse_jina_threads_markdown(md_text: str) -> List[Dict[str, Any]]:
    """Parse full Jina Markdown of a Threads page into structured posts/comments WITH attached photos."""
    lines = md_text.splitlines()
    entries: List[Dict[str, Any]] = []
    cur: Optional[Dict[str, Any]] = None
    pending_avatar: str = ""
    pending_handle: str = ""

    def _flush_current() -> None:
        nonlocal cur
        if not cur:
            return
        body = "\n".join(cur["text_lines"]).strip()
        img_u = cur.get("image_url") or ""
        if len(body) >= 2 or img_u:
            entries.append(
                {
                    "username": cur["username"],
                    "text": body or "Hình ảnh bình luận đính kèm",
                    "likes": cur.get("likes") or 0,
                    "replies": cur.get("replies") or 0,
                    "is_verified": bool(cur.get("is_verified")),
                    "image_url": img_u,
                    "avatar_url": cur.get("avatar_url") or "",
                }
            )
        cur = None

    for raw_ln in lines:
        s = raw_ln.strip()
        if not s:
            continue

        # Check Markdown images (either profile picture or attached post/comment photo!)
        img_matches = MD_IMG_ANY_RE.findall(s)
        if img_matches:
            for alt, img_u in img_matches:
                alt_low = alt.lower()
                is_avatar = (
                    "profile picture" in alt_low
                    or "s150x150" in img_u
                    or "t51.2885-19" in img_u
                    or "t51.82787-19" in img_u
                )
                if is_avatar:
                    pending_avatar = img_u
                elif "rsrc.php" not in img_u and "static.cdninstagram" not in img_u:
                    if cur is not None and not cur.get("image_url"):
                        cur["image_url"] = img_u
            continue

        # Check `[username](https://www.threads.com/@username)`
        m_handle = MD_THREADS_HANDLE_LINK_RE.match(s)
        if m_handle:
            pending_handle = f"@{m_handle.group(2).lstrip('@')}"
            continue

        # Check timestamp/post anchor `[14h](https://www.threads.com/@user/post/POST_ID)` -> starts a post/comment block!
        m_post = MD_THREADS_POST_LINK_RE.match(s)
        if m_post:
            _flush_current()
            u_handle = f"@{m_post.group(2).lstrip('@')}"
            cur = {
                "username": pending_handle or u_handle,
                "post_code": m_post.group(3),
                "avatar_url": pending_avatar,
                "image_url": "",
                "text_lines": [],
                "likes": 0,
                "replies": 0,
                "is_verified": False,
                "seen_translate": False,
            }
            pending_handle = ""
            pending_avatar = ""
            continue

        if cur is None:
            continue

        if s.lower() == "verified":
            cur["is_verified"] = True
            continue

        if s.lower() == "translate":
            cur["seen_translate"] = True
            continue

        # Capture first standalone numeric metric as likes count
        if re.match(r"^\d+$", s):
            val = int(s)
            if cur["likes"] == 0:
                cur["likes"] = val
            elif cur["replies"] == 0:
                cur["replies"] = val
            continue

        if _is_threads_ui_noise_line(s):
            continue

        # Strip inline markdown links `[text](url)` -> `text`
        clean_line = re.sub(r"\[([^\]]+)\]\(https?://[^)]+\)", r"\1", s).strip()
        if clean_line and not _is_threads_ui_noise_line(clean_line):
            cur["text_lines"].append(clean_line)

    _flush_current()
    return entries


class ThreadsScraperService:
    """Extracts OP post, community comments & attached images from Threads, Reddit, Web, or text."""

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
        """Fetch public post, replies & comment images from URL and/or pasted raw conversation."""
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
                existing_texts = {c.raw_text.strip().lower() for c in bundle.comments}
                extra_items: List[ThreadCommentItemDTO] = []
                if (
                    bundle.op_display_text.startswith("Chủ đề thảo luận từ")
                    and len(pasted_bundle.op_display_text) > 10
                ):
                    bundle.op_display_text = pasted_bundle.op_display_text
                    bundle.op_spoken_vi_text = pasted_bundle.op_spoken_vi_text
                    bundle.topic_title = pasted_bundle.topic_title
                    if pasted_bundle.op_image_url and not bundle.op_image_url:
                        bundle.op_image_url = pasted_bundle.op_image_url
                else:
                    pasted_all = [
                        ThreadCommentItemDTO(
                            comment_id="cmt_paste_0",
                            author_handle=pasted_bundle.op_author_handle,
                            raw_text=pasted_bundle.op_display_text,
                            display_text=pasted_bundle.op_display_text,
                            spoken_vi_text=pasted_bundle.op_spoken_vi_text,
                            attached_image_url=pasted_bundle.op_image_url,
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
    async def download_bundle_images(
        cls,
        bundle: ScrapedThreadBundleDTO,
        media_dir: Path,
    ) -> ScrapedThreadBundleDTO:
        """Download OP & comment attached images locally (converting WEBP/PNG -> crisp RGB JPG)
        so browser previews bypass Instagram CORP headers and M04 renders them offline reliably.
        """
        media_dir.mkdir(parents=True, exist_ok=True)
        sem = asyncio.Semaphore(5)

        async def _fetch_and_save_jpg(img_url: str, prefix: str) -> str:
            u = (img_url or "").strip()
            if not u.startswith(("http://", "https://")):
                return ""
            digest = hashlib.md5(u.encode("utf-8")).hexdigest()[:12]
            dst_jpg = media_dir / f"{prefix}_{digest}.jpg"
            if dst_jpg.exists() and dst_jpg.stat().st_size > 1024:
                return str(dst_jpg)

            async with sem:
                try:
                    headers = {
                        **cls.DEFAULT_HEADERS,
                        "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
                        "Referer": "https://www.threads.com/",
                    }
                    async with httpx.AsyncClient(
                        headers=headers, follow_redirects=True, timeout=12.0
                    ) as client:
                        resp = await client.get(u)
                        if resp.status_code != 200 or len(resp.content) < 512:
                            return ""

                    def _decode_save(raw_bytes: bytes) -> str:
                        with Image.open(BytesIO(raw_bytes)) as im:
                            im_fixed = ImageOps.exif_transpose(im).convert("RGB")
                            max_dim = max(im_fixed.size)
                            if max_dim > 1440:
                                scale = 1440.0 / float(max_dim)
                                nw = max(64, int(round(im_fixed.width * scale)))
                                nh = max(64, int(round(im_fixed.height * scale)))
                                im_fixed = im_fixed.resize((nw, nh), Image.Resampling.LANCZOS)
                            im_fixed.save(dst_jpg, format="JPEG", quality=92)
                        return str(dst_jpg)

                    return await asyncio.to_thread(_decode_save, resp.content)
                except Exception:
                    return ""

        op_local = bundle.op_image_path
        if not (op_local and Path(op_local).exists()) and bundle.op_image_url:
            op_local = await _fetch_and_save_jpg(bundle.op_image_url, "op_img")

        async def _dl_comment(c: ThreadCommentItemDTO) -> ThreadCommentItemDTO:
            if c.attached_image_path and Path(c.attached_image_path).exists():
                return c
            if not c.attached_image_url:
                return c
            saved_p = await _fetch_and_save_jpg(c.attached_image_url, "cmt_img")
            return c.model_copy(update={"attached_image_path": saved_p}) if saved_p else c

        updated_cmts = list(await asyncio.gather(*(_dl_comment(c) for c in bundle.comments)))
        return bundle.model_copy(
            update={
                "op_image_path": op_local,
                "comments": updated_cmts,
            }
        )

    @staticmethod
    def _extract_reddit_media_url(data_obj: Dict[str, Any]) -> str:
        """Extract attached image URL from a Reddit post or comment `data` payload."""
        # 1. Reddit Comment / Gallery `media_metadata`
        media_meta = data_obj.get("media_metadata")
        if isinstance(media_meta, dict):
            for m_val in media_meta.values():
                if not isinstance(m_val, dict):
                    continue
                s_info = m_val.get("s") or {}
                cand = html_lib.unescape(str(s_info.get("u") or s_info.get("gif") or "")).strip()
                if cand.startswith("http"):
                    return cand

        # 2. Direct image link on post
        overridden = str(data_obj.get("url_overridden_by_dest") or data_obj.get("url") or "").strip()
        if overridden and re.search(r"\.(?:jpg|jpeg|png|webp)(?:\?|$)", overridden, re.I):
            return html_lib.unescape(overridden)

        # 3. Reddit `preview.images`
        prev = data_obj.get("preview")
        if isinstance(prev, dict):
            imgs = prev.get("images") or []
            if imgs and isinstance(imgs[0], dict):
                src_u = html_lib.unescape(str((imgs[0].get("source") or {}).get("url") or "")).strip()
                if src_u.startswith("http"):
                    return src_u

        # 4. Inline image URL inside comment markdown body
        body_txt = str(data_obj.get("body") or "")
        m_in = DIRECT_IMG_URL_RE.search(body_txt)
        if m_in:
            return html_lib.unescape(m_in.group(1))
        return ""

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
            op_img = cls._extract_reddit_media_url(post_data)
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
                    c_img = cls._extract_reddit_media_url(cd)
                    if (
                        (not body and not c_img)
                        or body in ("[deleted]", "[removed]")
                        or c_author.lower() == "automoderator"
                    ):
                        continue
                    clean_disp = URL_CLEAN_RE.sub("", body).strip() if c_img else body
                    if not clean_disp:
                        clean_disp = "Ảnh đính kèm từ bình luận"
                    c_ups = max(0, int(cd.get("ups") or 0))
                    comments.append(
                        ThreadCommentItemDTO(
                            comment_id=f"rd_{uuid.uuid4().hex[:8]}",
                            author_handle=f"@{c_author}",
                            raw_text=clean_disp[:1200],
                            display_text=clean_disp[:1200],
                            spoken_vi_text=normalize_vn_social_slang(clean_disp[:1200]) or "Cùng xem bức ảnh này nhé",
                            attached_image_url=c_img,
                            likes_count=c_ups,
                            likes_display=format_compact_likes(c_ups) or "42",
                        )
                    )
                    if len(comments) >= 26:
                        break

            img_count = sum(1 for c in comments if c.attached_image_url) + (1 if op_img else 0)
            return ScrapedThreadBundleDTO(
                source_url=url,
                platform="reddit",
                topic_title=title[:180],
                op_author_handle=f"@{author}",
                op_display_text=op_full[:2000],
                op_spoken_vi_text=normalize_vn_social_slang(op_full[:2000]),
                op_image_url=op_img,
                op_likes_display=format_compact_likes(ups) or "1,5K",
                op_replies_display=format_compact_likes(num_c) or str(max(len(comments), 18)),
                comments=comments,
                extraction_note=(
                    f"Đã hút bài gốc + {len(comments)} bình luận (kèm {img_count} ảnh đính kèm) từ Reddit."
                    if img_count > 0
                    else f"Đã hút trực tiếp bài gốc + {len(comments)} bình luận từ Reddit."
                ),
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

        relay_posts: List[Dict[str, Any]] = []
        og_title = ""
        og_desc = ""
        og_image = ""

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
                    cand_og_img = meta.get("og:image") or meta.get("twitter:image") or ""
                    if cand_og_img and "rsrc.php" not in cand_og_img and "s150x150" not in cand_og_img:
                        og_image = cand_og_img

                    seen_k: set[str] = set()
                    for sm in SCRIPT_JSON_RE.finditer(raw_html):
                        blob = sm.group(1).strip()
                        if not blob or ("caption" not in blob and "image_versions2" not in blob):
                            continue
                        try:
                            parsed = json.loads(blob)
                            _walk_threads_posts(parsed, relay_posts, seen_k)
                        except Exception:
                            continue
        except Exception:
            pass

        # Step B: Query full Jina Markdown (resolves `/share/...` links AND exposes all comment images!)
        jina_posts: List[Dict[str, Any]] = []
        jina_raw_md = ""
        if len(relay_posts) <= 1 or not any(p.get("image_url") for p in relay_posts):
            try:
                async with httpx.AsyncClient(
                    headers={"User-Agent": cls.DEFAULT_HEADERS["User-Agent"]},
                    follow_redirects=True,
                    timeout=15.0,
                ) as client:
                    j_resp = await client.get(f"https://r.jina.ai/{url}")
                    if j_resp.status_code == 200 and len(j_resp.text.strip()) > 40:
                        jina_raw_md = j_resp.text
                        m_final = re.search(
                            r"Final URL:\s*(https?://\S+/@([A-Za-z0-9_.-]+)/post/\S+)",
                            jina_raw_md,
                        )
                        if m_final:
                            url_handle = f"@{m_final.group(2)}"
                        jina_posts = _parse_jina_threads_markdown(jina_raw_md)
            except Exception:
                pass

        # Merge Relay & Jina posts so real comment/OP images from Jina are ALWAYS preserved!
        if jina_posts and relay_posts:
            for rp in relay_posts:
                rp_u = (rp.get("username") or "").lstrip("@").lower()
                rp_t = (rp.get("text") or "").strip().lower()[:32]
                for jp in jina_posts:
                    jp_u = (jp.get("username") or "").lstrip("@").lower()
                    jp_t = (jp.get("text") or "").strip().lower()[:32]
                    if (rp_u and rp_u == jp_u and (not rp_t or not jp_t or rp_t[:14] in jp_t or jp_t[:14] in rp_t)) or (
                        len(rp_t) >= 12 and rp_t == jp_t
                    ):
                        if jp.get("image_url") and not rp.get("image_url"):
                            rp["image_url"] = jp["image_url"]
                        if jp.get("avatar_url") and not rp.get("avatar_url"):
                            rp["avatar_url"] = jp["avatar_url"]
                        break
            # Also append any Jina post that has an image_url not yet in relay_posts
            existing_imgs = {rp.get("image_url") for rp in relay_posts if rp.get("image_url")}
            for jp in jina_posts[1:]:
                if jp.get("image_url") and jp["image_url"] not in existing_imgs:
                    relay_posts.append(jp)
                    existing_imgs.add(jp["image_url"])
            extracted_posts = relay_posts if len(relay_posts) >= len(jina_posts) else jina_posts
        else:
            extracted_posts = jina_posts if len(jina_posts) > len(relay_posts) else relay_posts

        if extracted_posts:
            op = extracted_posts[0]
            op_text = op["text"]
            op_handle = op["username"] or url_handle
            op_img = op.get("image_url") or ""
            # Prioritize replies that include attached images first so visual comments are never sliced off!
            ordered_replies = sorted(
                extracted_posts[1:],
                key=lambda it: (0 if it.get("image_url") else 1),
            )
            comments: List[ThreadCommentItemDTO] = []
            for idx, item in enumerate(ordered_replies[:50], start=1):
                c_txt = item["text"]
                c_img = item.get("image_url") or ""
                likes_n = int(item.get("likes") or 0)
                comments.append(
                    ThreadCommentItemDTO(
                        comment_id=f"th_{uuid.uuid4().hex[:8]}",
                        author_handle=item.get("username") or f"@thanhvien_{idx:02d}",
                        raw_text=c_txt[:1200],
                        display_text=c_txt[:1200],
                        spoken_vi_text=normalize_vn_social_slang(c_txt[:1200]) or c_txt[:300],
                        attached_image_url=c_img,
                        avatar_url=item.get("avatar_url") or "",
                        likes_count=likes_n,
                        likes_display=format_compact_likes(likes_n) or str(max(12, 180 - idx * 9)),
                        is_verified=bool(item.get("is_verified")),
                    )
                )
            title_short = op_text.splitlines()[0][:120] if op_text else (og_title or "Chủ đề Threads")
            img_total = sum(1 for c in comments if c.attached_image_url) + (1 if op_img else 0)
            note = (
                f"Đã trích xuất bài gốc + {len(comments)} bình luận thật (kèm {img_total} ảnh đính kèm) từ Threads!"
                if img_total > 0
                else (
                    f"Đã trích xuất bài gốc + {len(comments)} bình luận công khai từ Threads."
                    if comments
                    else "Đã lấy bài gốc từ liên kết; AI sẽ hỗ trợ chọn lọc bình luận tiêu biểu."
                )
            )
            return ScrapedThreadBundleDTO(
                source_url=url,
                platform=platform,
                topic_title=title_short[:180],
                op_author_handle=op_handle,
                op_display_text=op_text[:2000],
                op_spoken_vi_text=normalize_vn_social_slang(op_text[:2000]) or op_text[:500],
                op_image_url=op_img,
                op_avatar_url=op.get("avatar_url") or "",
                op_likes_display=format_compact_likes(int(op.get("likes") or 0)) or "1,8K",
                op_replies_display=format_compact_likes(int(op.get("replies") or 0))
                or str(max(len(comments), 48)),
                op_is_verified=bool(op.get("is_verified")),
                comments=comments,
                extraction_note=note,
            )

        # Fallback from OpenGraph or plain Jina lines
        op_candidate = og_desc.strip()
        plain_lines = [
            ln.strip()
            for ln in jina_raw_md.splitlines()
            if len(ln.strip()) >= 12 and not _is_threads_ui_noise_line(ln) and not ln.strip().startswith("![")
        ]
        if not op_candidate and plain_lines:
            op_candidate = plain_lines[0]
        if not op_candidate and og_title:
            op_candidate = og_title.strip()

        if op_candidate:
            op_candidate = re.sub(
                r"^.*?on Threads:\s*[\"“]?(.*?)[\"”]?\s*$",
                r"\1",
                op_candidate,
                flags=re.DOTALL,
            ).strip()
            extra_cmts: List[ThreadCommentItemDTO] = []
            for idx, jl in enumerate(plain_lines[1:16], start=1):
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
                op_image_url=og_image,
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
        """Parse user-pasted Thread post + comments (including any pasted image URLs)."""
        blocks = [b.strip() for b in re.split(r"\n\s*\n|\r?\n(?=[@•\-*]|\d+[.)]\s)", raw_text) if b.strip()]
        if len(blocks) <= 1:
            blocks = [ln.strip() for ln in raw_text.splitlines() if ln.strip()]

        first = blocks[0] if blocks else raw_text.strip()
        op_img_m = DIRECT_IMG_URL_RE.search(first)
        op_img_url = op_img_m.group(1) if op_img_m else ""
        first_no_img = DIRECT_IMG_URL_RE.sub("", first).strip() or first

        op_handle = "@chuthot"
        m_op = HANDLE_LINE_RE.match(first_no_img)
        if m_op:
            op_handle = f"@{m_op.group(1).lstrip('@')}"
            op_body = m_op.group(2).strip()
        else:
            op_body = re.sub(r"^[-•*]\s*", "", first_no_img).strip()

        comments: List[ThreadCommentItemDTO] = []
        for idx, blk in enumerate(blocks[1:25], start=1):
            cleaned_blk = re.sub(r"^(?:[-•*]|\d+[.)])\s*", "", blk).strip()
            if len(cleaned_blk) < 2:
                continue
            c_img_m = DIRECT_IMG_URL_RE.search(cleaned_blk)
            c_img_url = c_img_m.group(1) if c_img_m else ""
            txt_part = DIRECT_IMG_URL_RE.sub("", cleaned_blk).strip() or "Ảnh đính kèm từ bình luận"

            hm = HANDLE_LINE_RE.match(txt_part)
            c_handle = f"@{hm.group(1).lstrip('@')}" if hm else f"@binhluan_{idx:02d}"
            c_body = hm.group(2).strip() if hm else txt_part
            likes_val = max(15, 420 - idx * 27)
            comments.append(
                ThreadCommentItemDTO(
                    comment_id=f"pst_{uuid.uuid4().hex[:8]}",
                    author_handle=c_handle,
                    raw_text=c_body[:1200],
                    display_text=c_body[:1200],
                    spoken_vi_text=normalize_vn_social_slang(c_body[:1200]) or c_body[:300],
                    attached_image_url=c_img_url,
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
            op_spoken_vi_text=normalize_vn_social_slang(op_body[:2000]) or op_body[:500],
            op_image_url=op_img_url,
            op_likes_display="2,4K",
            op_replies_display=str(max(len(comments), 68)),
            comments=comments,
            extraction_note=f"Đã tách bài gốc và {len(comments)} bình luận từ văn bản dán vào.",
        )
