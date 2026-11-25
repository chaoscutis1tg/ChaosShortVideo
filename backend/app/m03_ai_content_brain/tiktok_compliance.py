"""TikTok Shop & Vietnam Advertising Law Policy Compliance Scanner & Auto-Sanitizer (Module M03)."""

import re
from typing import List, Tuple

from app.m00_core_contracts import ComplianceIssueDTO, ComplianceReportDTO

# (regex_pattern, category, reason, compliant_replacement)
POLICY_RULES: Tuple[Tuple[str, str, str, str], ...] = (
    (
        r"\bsố\s*1\s*(?:việt\s*nam|thế\s*giới|thị\s*trường)\b",
        "TUYỆT_ĐỐI_HÓA",
        "Luật Quảng cáo & TikTok Shop hạn chế từ 'Số 1' nếu không có giấy chứng nhận.",
        "hàng đầu trong tầm giá",
    ),
    (
        r"\btốt\s*nhất\s*(?:thế\s*giới|việt\s*nam|hiện\s*nay|thị\s*trường)\b",
        "TUYỆT_ĐỐI_HÓA",
        "Từ khẳng định tuyệt đối dễ bị bóp hiển thị trên TikTok Shop.",
        "cực kỳ đáng cân nhắc trên thị trường",
    ),
    (
        r"\brẻ\s*nhất\s*(?:thị\s*trường|việt\s*nam|vịnh\s*bắc\s*bộ)\b",
        "TUYỆT_ĐỐI_HÓA",
        "Từ so sánh giá tuyệt đối dễ bị quét hạn chế phân phối.",
        "mức giá vô cùng hợp lý",
    ),
    (
        r"\bcam\s*kết\s*100\s*%\b",
        "TUYỆT_ĐỐI_HÓA",
        "Cụm 'cam kết 100%' thường bị thuật toán kiểm duyệt quảng cáo gắn cờ.",
        "cam kết chuẩn thực tế",
    ),
    (
        r"\b100\s*%\s*(?:không\s*hỏng|vĩnh\s*viễn|tuyệt\s*đối)\b",
        "TUYỆT_ĐỐI_HÓA",
        "Khẳng định độ bền tuyệt đối dễ vi phạm chính sách quảng cáo.",
        "độ bền vượt trội theo thời gian",
    ),
    (
        r"\b(?:kết\s*bạn\s*zalo|nhắn\s*zalo|ib\s*zalo|qua\s*zalo)\b",
        "ĐIỀU_HƯỚNG_NGOÀI_SÀN",
        "Đọc trực tiếp tên nền tảng ngoài trong lời thoại dễ bị TikTok bóp tương tác.",
        "nhắn trực tiếp vào hộp thư của shop",
    ),
    (
        r"\b(?:chuyển\s*khoản\s*trước|đặt\s*cọc\s*chuyển\s*khoản)\b",
        "ĐIỀU_HƯỚNG_NGOÀI_SÀN",
        "Từ khóa giao dịch riêng dễ bị TikTok cảnh báo an toàn mua sắm.",
        "đặt hàng an toàn nhận kiểm tra trực tiếp",
    ),
    (
        r"\b(?:link\s*shopee|qua\s*shopee|mua\s*trên\s*lazada)\b",
        "ĐIỀU_HƯỚNG_NGOÀI_SÀN",
        "Nhắc tên sàn đối thủ trực tiếp sẽ bị hạn chế hiển thị video.",
        "bấm vào giỏ hàng hoặc nhắn cho shop",
    ),
    (
        r"\b(?:hàng\s*fake|super\s*fake|like\s*auth|rep\s*1\s*:\s*1|hàng\s*nhái)\b",
        "VI_PHẠM_THƯƠNG_HIỆU",
        "Từ khóa hàng giả/nhái bị cấm nghiêm ngặt và có nguy cơ khóa tài khoản.",
        "phiên bản thiết kế hoàn thiện cao",
    ),
)


class TikTokShopComplianceChecker:
    """Audits product descriptions/scripts and rewrites shadowban/ad-policy risky phrases."""

    @classmethod
    def check_and_sanitize(cls, text: str) -> ComplianceReportDTO:
        """Scan `text` for policy risks and return score + auto-sanitized version."""
        sanitized = text or ""
        issues: List[ComplianceIssueDTO] = []

        for pattern, category, reason, replacement in POLICY_RULES:
            regex = re.compile(pattern, flags=re.IGNORECASE)
            matches = list(regex.finditer(sanitized))
            if matches:
                sample_phrase = matches[0].group(0)
                issues.append(
                    ComplianceIssueDTO(
                        phrase=sample_phrase,
                        category=category,
                        reason=reason,
                        suggestion=replacement,
                    )
                )
                sanitized = regex.sub(replacement, sanitized)

        penalty = sum(18 if it.category != "VI_PHẠM_THƯƠNG_HIỆU" else 40 for it in issues)
        score = max(10, 100 - penalty) if issues else 100
        return ComplianceReportDTO(
            safety_score=score,
            is_safe=(len(issues) == 0),
            issues=issues,
            sanitized_text=sanitized,
        )

