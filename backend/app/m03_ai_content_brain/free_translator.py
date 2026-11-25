"""Zero-API-key high-speed batch translator into natural Vietnamese for Module M03."""

import asyncio
import html
import re
from typing import List
import httpx

VIETNAMESE_DIACRITICS_RE = re.compile(
    r"[ăâđêôơưáàảãạấầẩẫậắằẳẵặéèẻẽẹếềểễệíìỉĩịóòỏõọốồổỗộớờởỡợúùủũụứừửữựýỳỷỹỵ]",
    re.IGNORECASE,
)
DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)


class FreeVietnameseTranslator:
    """Translates foreign subtitle lines (zh, en, ko, ja...) into Vietnamese with zero API keys."""

    @classmethod
    async def translate_lines(
        cls,
        texts: List[str],
        source_lang: str = "auto",
        concurrency: int = 8,
    ) -> List[str]:
        """Translate a list of subtitle strings preserving exact 1-to-1 line alignment."""
        if not texts:
            return []

        sem = asyncio.Semaphore(concurrency)
        sl = "auto" if not source_lang or source_lang.lower() == "auto" else source_lang

        async with httpx.AsyncClient(
            timeout=15.0,
            follow_redirects=True,
            headers={"User-Agent": DEFAULT_UA},
        ) as client:

            async def _one(idx: int, raw: str) -> tuple[int, str]:
                clean = raw.strip()
                if not clean or VIETNAMESE_DIACRITICS_RE.search(clean):
                    return idx, clean
                async with sem:
                    vi = await cls._translate_single(client, clean, sl)
                    return idx, vi

            pairs = await asyncio.gather(*[_one(i, t) for i, t in enumerate(texts)])

        ordered = [ txt for _, txt in sorted(pairs, key=lambda x: x[0]) ]
        return ordered

    @classmethod
    async def _translate_single(
        cls, client: httpx.AsyncClient, text: str, sl: str
    ) -> str:
        # Primary fast JSON endpoint (`clients5.google.com`)
        for attempt in range(2):
            try:
                resp = await client.get(
                    "https://clients5.google.com/translate_a/t",
                    params={"client": "dict-chrome-ex", "sl": sl, "tl": "vi", "q": text},
                )
                if resp.status_code == 200:
                    data = resp.json()
                    if isinstance(data, list) and data:
                        first = data[0]
                        if isinstance(first, list) and first:
                            return str(first[0]).strip() or text
                        if isinstance(first, str):
                            return first.strip() or text
            except Exception:
                if attempt == 0:
                    await asyncio.sleep(0.25)

        # Secondary mobile HTML fallback (`translate.google.com/m`)
        try:
            r_mob = await client.get(
                "https://translate.google.com/m",
                params={"sl": sl, "tl": "vi", "q": text},
            )
            if r_mob.status_code == 200:
                m = re.search(r'result-container[^>]*>(.*?)</div>', r_mob.text, re.S)
                if m:
                    return html.unescape(m.group(1)).strip() or text
        except Exception:
            pass

        return text

