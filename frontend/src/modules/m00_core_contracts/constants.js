// Shared Frontend Contracts & Defaults matching Module M00 (`m00_core_contracts`)

export const DEFAULT_LAYOUT_CONFIG = {
  layout_type: 'BLUR_CENTER',
  aspect_ratio: '9:16',
  transition_style: 'AUTO_DIRECTOR',
  product_framing: 'BLURRED_STUDIO_CARD',
  show_top_banner: true,
  show_photo_callouts: false,
  top_banner_template: '{hook_banner_title}',
  center_zoom_scale: 1.04,
  hardsub_mask_enabled: true,
  hardsub_rect: {
    x: 0.04,
    y: 0.78,
    w: 0.92,
    h: 0.11,
    mode: 'BLUR',
  },
  anti_copyright_enabled: true,
  speed_factor: 1.05,
  mirror_flip: false,
  color_contrast: 1.04,
  color_saturation: 1.05,
  logo_path: null,
  logo_pos_x: 0.04,
  logo_pos_y: 0.04,
  retention_video_path: null,
  sales_badge_enabled: false,
  sales_price_or_offer: '',
  sales_contact_info: '',
  qr_code_content: '',
  qr_code_label: 'Quét xem mẫu',
  studio_cutout_enabled: false,
  soundwave_enabled: true,
  comparison_split_enabled: false,
  comparison_label_a: 'Bản S2 • Giữ dây kim loại',
  comparison_label_b: 'Bản S2S • Giữ dây gỗ',
  feedback_image_paths: [],
  subtitle_pos_y: 0.84,
  subtitle_font_size: 52,
  outro_card_enabled: false,
  outro_brand_title: '',
  outro_subtitle: '',
  outro_contact_line: '',
  outro_duration_ms: 2500,
  cover_style: 'CLEAN_POSTER',
  cover_headline: '',
  cover_badge_text: '',
  cover_photo_index: 0,
  threads_card_theme: 'DARK_THREADS',
  threads_eye_guide_mode: 'ACTIVE_HIGHLIGHT',
  threads_anonymize_handles: false,
  threads_bg_dim: 0.28,
  auto_skip_black_intro: true,
  safe_zone_guard: true,
  smart_camera_motion: true,
  smart_micro_punch_in: true,
  dynamic_face_tracking: true,
};

export const DEFAULT_AUDIO_CONFIG = {
  enable_narration: true,
  keep_original_audio: true,
  ducking_ratio: 0.18,
  bgm_path: null,
  bgm_volume: 0.06,
  subtitle_style: 'CINEMA',
  enable_smart_sfx: true,
  smart_sfx_volume: 0.22,
  smart_keyword_highlight: true,
};

export const STAGE_LABELS = {
  DRAFT: 'Bản nháp',
  QUEUED: 'Đang chờ đến lượt',
  INGESTING: 'Đang tải video',
  TRANSCRIBING_GPU: 'Đang tách lời thoại',
  AI_ANALYZING: 'Đang biên tập kịch bản',
  AWAITING_REVIEW: 'Chờ duyệt nội dung',
  GENERATING_ASSETS: 'Đang thu âm & dựng cảnh',
  RENDERING_NVENC: 'Đang xuất video MP4',
  PACKAGING_SEO: 'Đang tạo tiêu đề & thẻ tag',
  PAUSED: 'Đang tạm dừng',
  COMPLETED: 'Đã hoàn thành',
  FAILED: 'Gặp sự cố',
  CANCELLED: 'Đã hủy',
};

export function stripLeadingEmoji(str = '') {
  return String(str).replace(/^[\u{1F300}-\u{1FAFF}\u{2600}-\u{27BF}\s]+/u, '').trim();
}

export function copyTextSafe(text) {
  if (navigator.clipboard && window.isSecureContext) {
    return navigator.clipboard.writeText(text);
  }
  return new Promise((resolve) => {
    const ta = document.createElement('textarea');
    ta.value = text;
    ta.style.position = 'fixed';
    ta.style.opacity = '0';
    document.body.appendChild(ta);
    ta.focus();
    ta.select();
    try {
      document.execCommand('copy');
    } catch {
      // ignore
    }
    document.body.removeChild(ta);
    resolve();
  });
}

export function formatSecondsVi(sec) {
  if (sec === null || sec === undefined || Number.isNaN(Number(sec))) return '--';
  const total = Math.max(0, Math.round(Number(sec)));
  if (total < 60) return `${total} giây`;
  const m = Math.floor(total / 60);
  const s = total % 60;
  if (m < 60) return s > 0 ? `${m}p ${s}s` : `${m} phút`;
  const h = Math.floor(m / 60);
  const rm = m % 60;
  return `${h}g ${rm}p`;
}
