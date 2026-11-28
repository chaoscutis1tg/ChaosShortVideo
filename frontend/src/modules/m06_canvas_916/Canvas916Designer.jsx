import React, { useEffect, useRef, useState } from 'react';
import {
  Award,
  BookmarkCheck,
  Camera,
  ChevronDown,
  ChevronUp,
  Cpu,
  Download,
  Eye,
  HardDrive,
  ImagePlus,
  Loader2,
  Move,
  Smartphone,
  Sparkles,
  Trash2,
  X,
} from 'lucide-react';
import { studioApi } from '../m00_core_contracts/apiClient';
import { StudioLoadingBanner, SwitchCard } from '../m00_core_contracts/StudioWidgets';

const ASPECT_META = {
  '9:16': { label: '9:16 Dọc', res: '1080×1920', height: 434 },
  '4:5': { label: '4:5 Feed', res: '1080×1350', height: 305 },
  '1:1': { label: '1:1 Vuông', res: '1080×1080', height: 244 },
};

const MODE_BADGE_MAP = {
  product: 'Video Bán Hàng',
  movie: 'Cắt & Dịch Video',
  topic: 'Video Chủ Đề',
  threads: 'Threads & Bình Luận',
  workspace: 'Dự Án Đang Chọn',
  voices: 'Phòng Giọng Đọc',
};

const AMBIENCE_OPTIONS = [
  { value: 'NONE', label: 'Tắt hiệu ứng (Mặc định — Nguyên bản)', short: '' },
  { value: 'GOLDEN_BOKEH', label: '✨ Hạt bụi nắng vàng (Golden Bokeh)', short: '✨ Bokeh nắng' },
  { value: 'NIGHT_RAIN', label: '🌧️ Mưa đêm phố thị (Night Rain)', short: '🌧️ Mưa đêm' },
  { value: 'WARM_LIGHT_LEAK', label: '🌅 Vệt nắng chiều ấm (Light Leak)', short: '🌅 Nắng chiều' },
  { value: 'VINTAGE_FILM_35MM', label: '🎞️ Phim nhựa cổ điển 35mm', short: '🎞️ Phim 35mm' },
];

export default function Canvas916Designer({
  layoutConfig,
  setLayoutConfig,
  previewFrameUrl,
  systemStatus,
  onSystemStatusUpdated,
  activeTab = 'product',
  contextMode = null,
  notify,
}) {
  const [showLayoutSettings, setShowLayoutSettings] = useState(false);
  const [showSmartEdit, setShowSmartEdit] = useState(false);
  const [showBrandKit, setShowBrandKit] = useState(false);
  const [savingBrandKit, setSavingBrandKit] = useState(false);
  const [cleaningTemp, setCleaningTemp] = useState(false);
  const [switchingGpu, setSwitchingGpu] = useState(false);
  const [renderingSnapshot, setRenderingSnapshot] = useState(false);
  const [snapshotModal, setSnapshotModal] = useState(null);

  const phoneRef = useRef(null);
  const movieRegionRef = useRef(null);
  const dragStateRef = useRef(null);

  const update = (patch) => setLayoutConfig((prev) => ({ ...prev, ...patch }));
  const updateRect = (rPatch) =>
    setLayoutConfig((prev) => ({
      ...prev,
      hardsub_rect: { ...prev.hardsub_rect, ...rPatch },
    }));

  useEffect(() => {
    studioApi
      .getBrandKit()
      .then((kit) => {
        if (!kit) return;
        const hasSavedBrand = Boolean(
          kit.brand_name || kit.showroom_address || kit.hotline_or_web || kit.logo_path
        );
        if (hasSavedBrand) {
          setLayoutConfig((prev) => ({
            ...prev,
            logo_path: kit.logo_path || prev.logo_path,
            logo_pos_x: kit.logo_pos_x ?? prev.logo_pos_x,
            logo_pos_y: kit.logo_pos_y ?? prev.logo_pos_y,
            subtitle_pos_y: kit.subtitle_pos_y ?? prev.subtitle_pos_y,
            subtitle_font_size: kit.subtitle_font_size ?? prev.subtitle_font_size,
            outro_card_enabled: Boolean(kit.outro_card_enabled),
            outro_brand_title: kit.brand_name || prev.outro_brand_title,
            outro_subtitle: kit.showroom_address || prev.outro_subtitle,
            outro_contact_line: kit.hotline_or_web || prev.outro_contact_line,
            qr_code_content: kit.qr_code_content || prev.qr_code_content,
            qr_code_label: kit.qr_code_label || prev.qr_code_label,
          }));
        }
      })
      .catch(() => {});
  }, []);

  const handleSaveBrandKit = async () => {
    setSavingBrandKit(true);
    try {
      await studioApi.saveBrandKit({
        brand_name: layoutConfig.outro_brand_title || '',
        logo_path: layoutConfig.logo_path || null,
        logo_pos_x: layoutConfig.logo_pos_x ?? 0.04,
        logo_pos_y: layoutConfig.logo_pos_y ?? 0.04,
        showroom_address: layoutConfig.outro_subtitle || '',
        hotline_or_web: layoutConfig.outro_contact_line || '',
        qr_code_content: layoutConfig.qr_code_content || '',
        qr_code_label: layoutConfig.qr_code_label || 'Quét xem chi tiết',
        subtitle_pos_y: layoutConfig.subtitle_pos_y ?? 0.84,
        subtitle_font_size: layoutConfig.subtitle_font_size ?? 52,
        outro_card_enabled: Boolean(layoutConfig.outro_card_enabled),
        preferred_framing: layoutConfig.product_framing || 'BLURRED_STUDIO_CARD',
        preferred_transition: layoutConfig.transition_style || 'CAPCUT_DISSOLVE',
      });
      notify('Đã lưu Bộ Nhận Diện Mặc Định cho ChaosShortVideo.');
    } catch (err) {
      notify(`Lỗi lưu Brand Kit: ${err.message}`);
    } finally {
      setSavingBrandKit(false);
    }
  };

  const handleLogoUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    try {
      const res = await studioApi.uploadStudioFile(file, 'logo');
      update({ logo_path: res.local_path });
      notify('Đã gắn Logo. Kéo thả trực tiếp trên màn hình mô phỏng để đổi vị trí.');
    } catch (err) {
      notify(`Lỗi tải Logo: ${err.message}`);
    }
  };

  const startDrag = (type, e) => {
    e.preventDefault();
    e.stopPropagation();
    dragStateRef.current = {
      type,
      startX: e.clientX,
      startY: e.clientY,
      origRect: { ...layoutConfig.hardsub_rect },
      origLogoX: layoutConfig.logo_pos_x,
      origLogoY: layoutConfig.logo_pos_y,
      origSubY: layoutConfig.subtitle_pos_y ?? 0.84,
    };

    const onMove = (ev) => {
      const st = dragStateRef.current;
      if (!st) return;

      if ((st.type === 'mask_move' || st.type === 'mask_resize') && movieRegionRef.current) {
        const box = movieRegionRef.current.getBoundingClientRect();
        const dyNorm = (ev.clientY - st.startY) / Math.max(box.height, 1);
        if (st.type === 'mask_move') {
          const newY = Math.min(1.0 - st.origRect.h, Math.max(0.45, st.origRect.y + dyNorm));
          updateRect({ y: +newY.toFixed(3) });
        } else {
          const newH = Math.min(1.0 - st.origRect.y, Math.max(0.05, st.origRect.h + dyNorm));
          updateRect({ h: +newH.toFixed(3) });
        }
      } else if (st.type === 'logo_move' && phoneRef.current) {
        const pBox = phoneRef.current.getBoundingClientRect();
        const dxNorm = (ev.clientX - st.startX) / Math.max(pBox.width, 1);
        const dyNorm = (ev.clientY - st.startY) / Math.max(pBox.height, 1);
        update({
          logo_pos_x: +Math.min(0.82, Math.max(0.02, st.origLogoX + dxNorm)).toFixed(3),
          logo_pos_y: +Math.min(0.9, Math.max(0.02, st.origLogoY + dyNorm)).toFixed(3),
        });
      } else if (st.type === 'sub_move' && phoneRef.current) {
        const pBox = phoneRef.current.getBoundingClientRect();
        const dyNorm = (ev.clientY - st.startY) / Math.max(pBox.height, 1);
        update({
          subtitle_pos_y: +Math.min(0.93, Math.max(0.2, st.origSubY + dyNorm)).toFixed(3),
        });
      }
    };

    const onUp = () => {
      dragStateRef.current = null;
      window.removeEventListener('pointermove', onMove);
      window.removeEventListener('pointerup', onUp);
    };

    window.addEventListener('pointermove', onMove);
    window.addEventListener('pointerup', onUp);
  };

  const handleSelectGpu = async (deviceId) => {
    setSwitchingGpu(true);
    try {
      const st = await studioApi.selectGpuDevice(deviceId);
      if (onSystemStatusUpdated) onSystemStatusUpdated(st);
      notify(`Đã chuyển thiết bị xử lý sang ${deviceId.toUpperCase()}.`);
    } catch (err) {
      notify(`Lỗi chuyển thiết bị: ${err.message}`);
    } finally {
      setSwitchingGpu(false);
    }
  };

  const handleCleanupTemp = async () => {
    setCleaningTemp(true);
    try {
      const res = await studioApi.cleanupTempStorage();
      const fresh = await studioApi.getSystemStatus();
      if (onSystemStatusUpdated) onSystemStatusUpdated(fresh);
      notify(`Đã giải phóng ${res.freed_mb} MB bộ nhớ tạm (giữ nguyên toàn bộ video MP4).`);
    } catch (err) {
      notify(`Lỗi dọn bộ nhớ tạm: ${err.message}`);
    } finally {
      setCleaningTemp(false);
    }
  };

  const handleRenderTrueSnapshot = async (asCover = false) => {
    const modeForSnap = contextMode || activeTab;
    setRenderingSnapshot(true);
    try {
      const res = await studioApi.renderTrueFrameSnapshot({
        active_tab: modeForSnap,
        sample_media_url: previewFrameUrl || '',
        banner_title:
          layoutConfig.cover_headline ||
          layoutConfig.outro_brand_title ||
          (modeForSnap === 'threads'
            ? 'Thảo Luận Nổi Bật Trên Threads'
            : modeForSnap === 'topic'
            ? 'Chủ Đề Câu Chuyện Hấp Dẫn'
            : modeForSnap === 'movie'
            ? 'Tiêu Đề Tập Phim | Phần 1'
            : 'Đàn Violin Avaro Gỗ Thịt Tự Nhiên'),
        sample_subtitle:
          modeForSnap === 'threads'
            ? 'Hai mươi sáu tuổi mới bắt đầu học chơi đàn Guitar thì có quá muộn không mọi người ơi?'
            : modeForSnap === 'topic'
            ? 'Hình ảnh minh họa chuyển cảnh mượt mà theo đúng từng câu dẫn chuyện.'
            : modeForSnap === 'movie'
            ? 'Nhưng khi mọi chuyện sáng tỏ thì tất cả đã hoàn toàn thay đổi.'
            : 'Mặt đàn gỗ thịt tự nhiên nguyên tấm cho tiếng đàn vang dày và ấm.',
        preview_as_cover: asCover,
        layout_config: layoutConfig,
      });
      setSnapshotModal({ ...res, asCover });
    } catch (err) {
      notify(`Lỗi kết xuất khung xem thử: ${err.message}`);
    } finally {
      setRenderingSnapshot(false);
    }
  };

  const rect = layoutConfig.hardsub_rect;
  const effMode = contextMode || activeTab;
  const isMovieMode = effMode === 'movie';
  const isThreadsMode = effMode === 'threads';
  const isTopicMode = effMode === 'topic' || isThreadsMode;
  const isProductMode = !isMovieMode && !isTopicMode;

  const aspectKey = layoutConfig.aspect_ratio || '9:16';
  const aspectInfo = ASPECT_META[aspectKey] || ASPECT_META['9:16'];
  const isSplit = isMovieMode && layoutConfig.layout_type === 'SPLIT_RETENTION';
  const isFull = isTopicMode
    ? true
    : isMovieMode
    ? layoutConfig.layout_type === 'FACE_TRACK_FULL'
    : layoutConfig.product_framing === 'FULL_BLEED_LUXURY';
  const isVelvetDark =
    isProductMode &&
    (layoutConfig.product_framing === 'VELVET_DARK_LUXURY' || layoutConfig.studio_cutout_enabled);
  const showTopBanner = layoutConfig.show_top_banner !== false;
  const subPosY = layoutConfig.subtitle_pos_y ?? 0.84;
  const subFontSize = layoutConfig.subtitle_font_size ?? 52;
  const previewSubPx = Math.max(9.5, Math.min(15.5, +(subFontSize * 0.22).toFixed(1)));
  const ambienceMode = layoutConfig.ambience_overlay || 'NONE';
  const ambienceMeta =
    AMBIENCE_OPTIONS.find((a) => a.value === ambienceMode) || AMBIENCE_OPTIONS[0];
  const storyBarEnabled = Boolean(layoutConfig.story_progress_bar_enabled);
  const dynamicModeBadge = isThreadsMode
    ? layoutConfig.threads_card_theme === 'MIDNIGHT_VINYL_LYRIC'
      ? 'Threads • Đĩa Than'
      : layoutConfig.threads_card_theme === 'QUIZ_COUNTDOWN_CARD'
      ? 'Threads • Đố Vui 3-2-1'
      : layoutConfig.threads_card_theme === 'CHAT_MESSENGER_ZALO' ||
        layoutConfig.threads_card_theme === 'CHAT_IMESSAGE_LIGHT'
      ? 'Threads • Chat'
      : 'Threads & Bình Luận'
    : effMode === 'topic' && layoutConfig.motion_preview_active
    ? 'Chủ Đề • Motion Graphics'
    : MODE_BADGE_MAP[effMode] || MODE_BADGE_MAP[activeTab] || 'Studio';
  const gpus = systemStatus?.gpus || [];
  const storage = systemStatus?.storage || {};

  return (
    <div>
      {/* CARD 1: MULTI-ASPECT PREVIEW, DRAGGABLE SUBTITLES & BRAND KIT */}
      <div className="card" style={{ padding: 16 }}>
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            gap: 6,
            marginBottom: 12,
          }}
        >
          <span className="text-sm fw-700" style={{ display: 'flex', alignItems: 'center', gap: 7 }}>
            <Smartphone size={16} strokeWidth={2} style={{ color: 'var(--brand-text)' }} /> Mô phỏng khung xuất
          </span>
          <div style={{ display: 'flex', gap: 5, alignItems: 'center', flexWrap: 'wrap', justifyContent: 'flex-end' }}>
            <span className="badge badge-info">{dynamicModeBadge}</span>
            <span className="badge">{aspectInfo.res}</span>
          </div>
        </div>

        {/* Aspect Ratio Selector Pills */}
        <div className="studio-segmented" style={{ width: '100%', display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', marginBottom: 14 }}>
          {Object.entries(ASPECT_META).map(([ratioKey, meta]) => (
            <button
              key={ratioKey}
              type="button"
              className={`studio-seg-btn ${aspectKey === ratioKey ? 'active' : ''}`}
              style={{ justifyContent: 'center', padding: '5px 6px' }}
              onClick={() => update({ aspect_ratio: ratioKey })}
            >
              {meta.label}
            </button>
          ))}
        </div>

        <div
          className="phone-frame"
          ref={phoneRef}
          style={{
            width: 244,
            height: aspectInfo.height,
            transition: 'height 0.22s ease',
          }}
        >
          <div
            style={{
              position: 'absolute',
              inset: 0,
              background: isVelvetDark
                ? 'radial-gradient(circle at 50% 45%, #23201c 0%, #0d0e12 85%)'
                : isTopicMode && !previewFrameUrl
                ? 'linear-gradient(160deg, #172554 0%, #0f172a 55%, #090d16 100%)'
                : previewFrameUrl
                ? `url(${previewFrameUrl}) center/cover no-repeat`
                : 'linear-gradient(165deg, #1e293b, #0f172a 68%)',
              filter: isFull || isVelvetDark ? 'none' : 'blur(11px) brightness(0.45)',
            }}
          />

          {/* OPT-IN TOP SEGMENTED STORY PROGRESS BAR PREVIEW */}
          {storyBarEnabled && (
            <div
              title="Thanh tiến trình đốt truyện trên đỉnh đang BẬT"
              style={{
                position: 'absolute',
                top: 9,
                left: 11,
                right: 11,
                display: 'grid',
                gridTemplateColumns: 'repeat(5, 1fr)',
                gap: 3,
                zIndex: 14,
                pointerEvents: 'none',
              }}
            >
              {[1, 1, 0.55, 0, 0].map((fillFrac, sIdx) => (
                <div
                  key={sIdx}
                  style={{
                    height: 3.2,
                    borderRadius: 99,
                    background: 'rgba(255, 255, 255, 0.28)',
                    overflow: 'hidden',
                  }}
                >
                  {fillFrac > 0 && (
                    <div
                      style={{
                        width: `${fillFrac * 100}%`,
                        height: '100%',
                        background: '#ffffff',
                        borderRadius: 99,
                      }}
                    />
                  )}
                </div>
              ))}
            </div>
          )}

          {/* OPT-IN CINEMATIC AMBIENCE OVERLAY PREVIEW */}
          {ambienceMode !== 'NONE' && (
            <div
              style={{
                position: 'absolute',
                inset: 0,
                pointerEvents: 'none',
                zIndex: 10,
                background:
                  ambienceMode === 'GOLDEN_BOKEH'
                    ? 'radial-gradient(circle at 20% 22%, rgba(253,224,71,0.30) 0%, transparent 18%), radial-gradient(circle at 82% 18%, rgba(251,191,36,0.26) 0%, transparent 22%), radial-gradient(circle at 78% 76%, rgba(245,158,11,0.26) 0%, transparent 20%), radial-gradient(circle at 18% 72%, rgba(254,240,138,0.24) 0%, transparent 16%)'
                    : ambienceMode === 'NIGHT_RAIN'
                    ? 'repeating-linear-gradient(102deg, transparent 0px, transparent 18px, rgba(186,230,253,0.18) 18px, rgba(186,230,253,0.18) 19.5px)'
                    : ambienceMode === 'WARM_LIGHT_LEAK'
                    ? 'radial-gradient(circle at 0% 0%, rgba(251,146,60,0.38) 0%, transparent 46%), radial-gradient(circle at 100% 100%, rgba(244,63,94,0.30) 0%, transparent 44%)'
                    : 'inset 0 0 28px rgba(0,0,0,0.65)',
                boxShadow:
                  ambienceMode === 'VINTAGE_FILM_35MM'
                    ? 'inset 0 0 0 6px rgba(10,12,18,0.58), inset 0 0 24px rgba(245,208,144,0.18)'
                    : 'none',
              }}
            >
              <span
                style={{
                  position: 'absolute',
                  top: storyBarEnabled ? 16 : 8,
                  right: 8,
                  padding: '1.5px 6px',
                  borderRadius: 99,
                  background: 'rgba(15, 23, 42, 0.78)',
                  border: '1px solid rgba(250, 204, 21, 0.55)',
                  color: '#fef08a',
                  fontSize: 7.5,
                  fontWeight: 700,
                }}
              >
                {ambienceMeta.short}
              </span>
            </div>
          )}

          {/* Draggable Channel Logo */}
          {layoutConfig.logo_path && (
            <div
              onPointerDown={(e) => startDrag('logo_move', e)}
              title="Giữ kéo để đổi vị trí Logo"
              style={{
                position: 'absolute',
                left: `${layoutConfig.logo_pos_x * 100}%`,
                top: `${layoutConfig.logo_pos_y * 100}%`,
                background: 'rgba(2, 132, 199, 0.92)',
                border: '1px solid rgba(255,255,255,0.85)',
                color: '#fff',
                fontSize: 9.5,
                fontWeight: 700,
                padding: '2px 7px',
                borderRadius: 5,
                cursor: 'grab',
                display: 'inline-flex',
                alignItems: 'center',
                gap: 4,
                zIndex: 12,
              }}
            >
              <Move size={10} /> Logo
            </div>
          )}

          {/* Optional Top Title */}
          {showTopBanner && (
            <div
              style={{
                position: 'absolute',
                top: layoutConfig.sales_badge_enabled ? 24 : 32,
                left: 14,
                right: 14,
                color: '#ffffff',
                fontSize: 12.5,
                fontWeight: 700,
                textAlign: 'center',
                textShadow: '0 2px 6px rgba(0, 0, 0, 0.92), 0 0 3px rgba(0, 0, 0, 0.85)',
                zIndex: 8,
              }}
            >
              {isProductMode
                ? 'Tên Sản Phẩm Tinh Tế'
                : isTopicMode
                ? 'Chủ Đề Câu Chuyện'
                : 'Tiêu Đề Tập Phim | Phần 1'}
            </div>
          )}

          {/* Optional Smoked-Obsidian & Champagne-Gold Offer Pill */}
          {isProductMode &&
            layoutConfig.sales_badge_enabled &&
            layoutConfig.sales_price_or_offer?.trim() && (
              <div
                style={{
                  position: 'absolute',
                  top: showTopBanner ? 48 : 22,
                  left: 20,
                  right: 20,
                  background: 'rgba(16, 18, 23, 0.88)',
                  border: '1px solid #deb96e',
                  color: '#fef3c7',
                  fontSize: 9.2,
                  fontWeight: 600,
                  textAlign: 'center',
                  padding: '2.5px 8px',
                  borderRadius: 999,
                  zIndex: 8,
                  whiteSpace: 'nowrap',
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                }}
              >
                {layoutConfig.sales_price_or_offer}
              </div>
            )}

          {/* Main Video / Product / Topic Frame */}
          <div
            ref={movieRegionRef}
            style={{
              position: 'absolute',
              left: isProductMode && !isFull ? 14 : 0,
              right: isProductMode && !isFull ? 14 : 0,
              top: isFull ? 0 : isSplit ? 0 : isProductMode ? '13%' : '28%',
              height: isFull ? '100%' : isSplit ? '54%' : isProductMode ? '66%' : '42%',
              borderRadius: isProductMode && !isFull ? 10 : 0,
              background:
                isProductMode && layoutConfig.comparison_split_enabled
                  ? 'rgba(17, 20, 27, 0.92)'
                  : previewFrameUrl
                  ? `url(${previewFrameUrl}) center/${isProductMode && !isFull ? 'contain' : 'cover'} no-repeat`
                  : isTopicMode
                  ? 'transparent'
                  : '#141b26',
              border:
                isProductMode && !isFull
                  ? '1px solid rgba(212, 175, 55, 0.35)'
                  : isFull
                  ? 'none'
                  : '1px solid rgba(255,255,255,0.16)',
              boxShadow: isProductMode && !isFull ? '0 8px 20px rgba(0,0,0,0.45)' : 'none',
              overflow: 'hidden',
            }}
          >
            {isProductMode && layoutConfig.comparison_split_enabled ? (
              <div
                style={{
                  display: 'grid',
                  gridTemplateColumns: '1fr 1fr',
                  height: '100%',
                  gap: 4,
                  padding: 5,
                }}
              >
                {[
                  layoutConfig.comparison_label_a || 'Bản A',
                  layoutConfig.comparison_label_b || 'Bản B',
                ].map((lbl, cIdx) => (
                  <div
                    key={cIdx}
                    style={{
                      border: '1px solid rgba(212,175,55,0.45)',
                      borderRadius: 6,
                      background: previewFrameUrl
                        ? `url(${previewFrameUrl}) center/contain no-repeat`
                        : '#11141c',
                      position: 'relative',
                      display: 'flex',
                      alignItems: 'flex-end',
                      justifyContent: 'center',
                      paddingBottom: 5,
                    }}
                  >
                    <span
                      style={{
                        fontSize: 7.5,
                        fontWeight: 700,
                        padding: '1px 5px',
                        borderRadius: 99,
                        background: 'rgba(12,15,21,0.9)',
                        border: '1px solid #deb96e',
                        color: '#fef3c7',
                      }}
                    >
                      {lbl.slice(0, 14)}
                    </span>
                  </div>
                ))}
              </div>
            ) : isThreadsMode ? (
              <div
                style={{
                  height: '100%',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  padding: 12,
                  background: `rgba(0, 0, 0, ${layoutConfig.threads_bg_dim ?? 0.28})`,
                }}
              >
                {layoutConfig.threads_card_theme === 'MIDNIGHT_VINYL_LYRIC' ? (
                  <div
                    style={{
                      width: '100%',
                      padding: '10px 10px 9px',
                      borderRadius: 14,
                      background: 'rgba(11, 15, 26, 0.94)',
                      border: '1px solid rgba(56, 189, 248, 0.48)',
                      color: '#f8fafc',
                      boxShadow: '0 8px 20px rgba(0,0,0,0.5)',
                      textAlign: 'center',
                    }}
                  >
                    <div style={{ fontSize: 7.5, fontWeight: 700, color: '#38bdf8', letterSpacing: 0.6, marginBottom: 5 }}>
                      MIDNIGHT VINYL • LIVE LYRICS
                    </div>
                    <div
                      className="spin"
                      style={{
                        width: 58,
                        height: 58,
                        margin: '0 auto 6px',
                        borderRadius: '50%',
                        background:
                          'radial-gradient(circle, #0f172a 0% 11%, #38bdf8 12% 33%, #111827 34% 68%, #1e293b 69% 72%, #0b0f19 73% 100%)',
                        border: '1.5px solid rgba(148,163,184,0.45)',
                        animationDuration: '4.5s',
                      }}
                    />
                    <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', gap: 2, height: 12, marginBottom: 6 }}>
                      {[5, 9, 12, 7, 11, 6, 10, 12, 8, 5].map((bh, bi) => (
                        <span
                          key={bi}
                          style={{
                            width: 2.5,
                            height: bh,
                            borderRadius: 2,
                            background: '#38bdf8',
                          }}
                        />
                      ))}
                    </div>
                    <div style={{ fontSize: 8.8, fontWeight: 700, lineHeight: 1.35 }}>
                      Đĩa than xoay tròn &amp; lời nhạc sáng rõ
                    </div>
                    <div style={{ fontSize: 8, opacity: 0.5, marginTop: 2 }}>
                      Câu tiếp theo mờ dịu chuẩn Spotify...
                    </div>
                  </div>
                ) : layoutConfig.threads_card_theme === 'QUIZ_COUNTDOWN_CARD' ? (
                  <div
                    style={{
                      width: '100%',
                      padding: '9px 10px',
                      borderRadius: 14,
                      background: 'rgba(15, 23, 42, 0.95)',
                      border: '1.5px solid rgba(56, 189, 248, 0.75)',
                      color: '#f8fafc',
                      boxShadow: '0 8px 20px rgba(0,0,0,0.5)',
                      textAlign: 'left',
                    }}
                  >
                    <span
                      style={{
                        display: 'inline-block',
                        padding: '1.5px 6px',
                        borderRadius: 99,
                        background: '#0284c7',
                        fontSize: 7.2,
                        fontWeight: 800,
                        marginBottom: 5,
                      }}
                    >
                      ⏱ ĐỐ VUI PHẢN XẠ • COMMENT ĐÁP ÁN
                    </span>
                    <div style={{ fontSize: 8.8, fontWeight: 700, lineHeight: 1.3, marginBottom: 5 }}>
                      Câu 1: Tiếng đàn ấm dày này là gỗ gì?
                    </div>
                    <div style={{ display: 'grid', gap: 3, fontSize: 7.8, marginBottom: 6 }}>
                      <div style={{ padding: '2.5px 6px', borderRadius: 6, background: '#1e293b', border: '1px solid rgba(148,163,184,0.3)' }}>
                        A. Gỗ Thông nguyên tấm
                      </div>
                      <div style={{ padding: '2.5px 6px', borderRadius: 6, background: '#1e293b', border: '1px solid rgba(148,163,184,0.3)' }}>
                        B. Gỗ ép công nghiệp
                      </div>
                    </div>
                    <div
                      style={{
                        width: 24,
                        height: 24,
                        margin: '0 auto',
                        borderRadius: '50%',
                        border: '2.5px solid #f59e0b',
                        color: '#fef08a',
                        fontSize: 9.5,
                        fontWeight: 800,
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                      }}
                    >
                      {layoutConfig.quiz_countdown_sec || 3}
                    </div>
                  </div>
                ) : layoutConfig.threads_card_theme === 'CHAT_MESSENGER_ZALO' ||
                layoutConfig.threads_card_theme === 'CHAT_IMESSAGE_LIGHT' ? (
                  <div
                    style={{
                      width: '100%',
                      borderRadius: 14,
                      overflow: 'hidden',
                      background:
                        layoutConfig.threads_card_theme === 'CHAT_IMESSAGE_LIGHT'
                          ? 'rgba(250,251,254,0.97)'
                          : 'rgba(13,17,26,0.95)',
                      color:
                        layoutConfig.threads_card_theme === 'CHAT_IMESSAGE_LIGHT'
                          ? '#0f172a'
                          : '#f8fafc',
                      border: '1px solid rgba(148,163,184,0.35)',
                      boxShadow: '0 8px 20px rgba(0,0,0,0.45)',
                      textAlign: 'left',
                    }}
                  >
                    <div
                      style={{
                        padding: '6px 9px',
                        borderBottom: '1px solid rgba(148,163,184,0.22)',
                        display: 'flex',
                        alignItems: 'center',
                        gap: 6,
                        fontSize: 8.8,
                      }}
                    >
                      <span style={{ color: '#0ea5e9', fontWeight: 800 }}>&lt;</span>
                      <span
                        style={{
                          width: 16,
                          height: 16,
                          borderRadius: 99,
                          background: '#ec4899',
                          color: '#fff',
                          fontSize: 7.5,
                          fontWeight: 800,
                          display: 'inline-flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                        }}
                      >
                        CR
                      </span>
                      <div>
                        <div style={{ fontWeight: 700, lineHeight: 1.1 }}>Crush</div>
                        <div style={{ fontSize: 7.2, color: '#22c55e' }}>● Đang hoạt động</div>
                      </div>
                    </div>
                    <div style={{ padding: '8px 8px 6px', display: 'grid', gap: 5, fontSize: 8.5 }}>
                      <div
                        style={{
                          justifySelf: 'end',
                          maxWidth: '82%',
                          padding: '5px 8px',
                          borderRadius: '11px 11px 3px 11px',
                          background: '#0e74f4',
                          color: '#fff',
                        }}
                      >
                        Ngủ chưa đấy? Hỏi thật câu này nhé...
                      </div>
                      <div
                        style={{
                          justifySelf: 'start',
                          maxWidth: '82%',
                          padding: '5px 8px',
                          borderRadius: '11px 11px 11px 3px',
                          background:
                            layoutConfig.threads_card_theme === 'CHAT_IMESSAGE_LIGHT'
                              ? '#e9ebef'
                              : '#222938',
                        }}
                      >
                        Chưa ngủ nè, nhắn thế làm tim đập loạn nhịp á!
                      </div>
                      <div
                        style={{
                          justifySelf: 'start',
                          padding: '3px 9px',
                          borderRadius: 99,
                          fontSize: 9,
                          opacity: 0.75,
                          background:
                            layoutConfig.threads_card_theme === 'CHAT_IMESSAGE_LIGHT'
                              ? '#e9ebef'
                              : '#222938',
                        }}
                      >
                        • • •
                      </div>
                    </div>
                  </div>
                ) : (
                  <div
                    style={{
                      width: '100%',
                      padding: '10px 11px',
                      borderRadius: 12,
                      background:
                        layoutConfig.threads_card_theme === 'LIGHT_THREADS'
                          ? 'rgba(255,255,255,0.96)'
                          : layoutConfig.threads_card_theme === 'FROSTED_GLASS'
                          ? 'rgba(17,24,39,0.76)'
                          : 'rgba(18,20,25,0.95)',
                      color:
                        layoutConfig.threads_card_theme === 'LIGHT_THREADS'
                          ? '#0f172a'
                          : '#f8fafc',
                      border:
                        layoutConfig.threads_card_theme === 'FROSTED_GLASS'
                          ? '1px solid rgba(125,211,252,0.65)'
                          : '1px solid rgba(148,163,184,0.35)',
                      boxShadow: '0 8px 20px rgba(0,0,0,0.45)',
                      textAlign: 'left',
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 5 }}>
                      <span
                        style={{
                          width: 18,
                          height: 18,
                          borderRadius: 99,
                          background: '#0ea5e9',
                          color: '#fff',
                          fontSize: 8,
                          fontWeight: 800,
                          display: 'inline-flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                        }}
                      >
                        TH
                      </span>
                      <strong style={{ fontSize: 9.5 }}>
                        {layoutConfig.threads_anonymize_handles
                          ? 'nguoila_01'
                          : 'minhanh.threads'}
                      </strong>
                      <span
                        style={{
                          marginLeft: 'auto',
                          fontSize: 8,
                          opacity: 0.6,
                        }}
                      >
                        18 phút •••
                      </span>
                    </div>
                    <div style={{ fontSize: 9.2, lineHeight: 1.4, marginBottom: 5 }}>
                      {(layoutConfig.threads_eye_guide_mode || 'ACTIVE_HIGHLIGHT') === 'ACTIVE_HIGHLIGHT' ? (
                        <div style={{ borderLeft: '2.5px solid #38bdf8', paddingLeft: 6 }}>
                          <div>Thẻ bình luận dẫn mắt sáng rõ câu đang đọc!</div>
                          <div style={{ opacity: 0.52 }}>Câu tiếp theo dịu nhẹ giúp mắt không mỏi.</div>
                        </div>
                      ) : layoutConfig.threads_eye_guide_mode === 'PROGRESSIVE_REVEAL' ? (
                        <div style={{ borderLeft: '2.5px solid #38bdf8', paddingLeft: 6 }}>
                          Chữ mở dần từng câu khớp đúng nhịp giọng đọc...
                        </div>
                      ) : (
                        'Thẻ bình luận nổi tự động nảy lên khớp từng giọng đọc trên video nền lặp vòng!'
                      )}
                    </div>
                    <div style={{ fontSize: 8, opacity: 0.72 }}>♥ 1,4K • Trả lời • Đăng lại</div>
                  </div>
                )}
              </div>
            ) : !isThreadsMode && isTopicMode && layoutConfig.motion_preview_active ? (
              <div
                style={{
                  height: '100%',
                  display: 'flex',
                  flexDirection: 'column',
                  justifyContent: 'center',
                  padding: 13,
                  background:
                    layoutConfig.motion_theme === 'DAN_KOE_MINIMAL'
                      ? 'linear-gradient(165deg, #060608 0%, #121216 100%)'
                      : layoutConfig.motion_theme === 'WARM_ARTISAN_GOLD'
                      ? 'linear-gradient(165deg, #140f0c 0%, #261b13 100%)'
                      : layoutConfig.motion_theme === 'NEON_TECH_INFOGRAPHIC'
                      ? 'linear-gradient(165deg, #06101a 0%, #0a202e 100%)'
                      : 'linear-gradient(165deg, #0b0f1a 0%, #161f32 100%)',
                  color: '#f8fafc',
                }}
              >
                <div style={{ textAlign: 'center', marginBottom: 7 }}>
                  <span
                    style={{
                      padding: '2px 7px',
                      borderRadius: 99,
                      fontSize: 7.5,
                      fontWeight: 800,
                      border: '1px solid rgba(56,189,248,0.65)',
                      color:
                        layoutConfig.motion_theme === 'WARM_ARTISAN_GOLD'
                          ? '#f5bc52'
                          : layoutConfig.motion_theme === 'DAN_KOE_MINIMAL'
                          ? '#fafafa'
                          : '#38bdf8',
                    }}
                  >
                    MOTION GRAPHICS • 30FPS
                  </span>
                </div>
                <div style={{ fontSize: 10, fontWeight: 800, textAlign: 'center', marginBottom: 8 }}>
                  Đồ họa &amp; Biểu đồ tự khớp giọng đọc
                </div>
                <div
                  style={{
                    padding: 8,
                    borderRadius: 10,
                    background: 'rgba(255,255,255,0.05)',
                    border: '1px solid rgba(148,163,184,0.28)',
                    display: 'grid',
                    gap: 5,
                    fontSize: 8,
                  }}
                >
                  {[
                    ['Độ vang & chiều sâu', '94%'],
                    ['Trải nghiệm thực tế', '78%'],
                    ['Phổ thông cũ', '42%'],
                  ].map(([lbl, pct], bi) => (
                    <div key={bi}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 2 }}>
                        <span>{lbl}</span>
                        <strong>{pct}</strong>
                      </div>
                      <div style={{ height: 5, borderRadius: 99, background: 'rgba(255,255,255,0.14)' }}>
                        <div
                          style={{
                            width: pct,
                            height: '100%',
                            borderRadius: 99,
                            background:
                              layoutConfig.motion_theme === 'WARM_ARTISAN_GOLD'
                                ? '#f5bc52'
                                : layoutConfig.motion_theme === 'DAN_KOE_MINIMAL'
                                ? '#fafafa'
                                : '#38bdf8',
                          }}
                        />
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            ) : !previewFrameUrl ? (
              <div
                style={{
                  height: '100%',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  fontSize: 11.5,
                  color: '#cbd5e1',
                  padding: 14,
                  textAlign: 'center',
                  lineHeight: 1.45,
                }}
              >
                {isProductMode
                  ? 'Ảnh & Video sản phẩm hiển thị nguyên vẹn 100% khung hình tại đây'
                  : isTopicMode
                  ? 'Hình minh họa AI / Stock Video chuyển cảnh mượt theo từng câu dẫn'
                  : 'Khung hiển thị video phim gốc'}
              </div>
            ) : null}

            {/* Hardsub Mask ONLY shown in Movie Clipper Mode */}
            {isMovieMode && layoutConfig.hardsub_mask_enabled && (
              <div
                onPointerDown={(e) => startDrag('mask_move', e)}
                title="Giữ kéo lên hoặc xuống để che đúng dòng chữ gốc ngoại ngữ"
                style={{
                  position: 'absolute',
                  left: `${rect.x * 100}%`,
                  top: `${rect.y * 100}%`,
                  width: `${rect.w * 100}%`,
                  height: `${rect.h * 100}%`,
                  background:
                    rect.mode === 'DARK_BOX'
                      ? 'rgba(0,0,0,0.84)'
                      : 'rgba(148, 163, 184, 0.36)',
                  backdropFilter: rect.mode === 'BLUR' ? 'blur(6px)' : 'none',
                  border: '1px dashed #38bdf8',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  fontSize: 9.2,
                  color: '#e0f2fe',
                  fontWeight: 700,
                  cursor: 'ns-resize',
                }}
              >
                Kéo vùng che chữ gốc ({Math.round(rect.y * 100)}%)
                <span
                  onPointerDown={(e) => startDrag('mask_resize', e)}
                  title="Kéo để chỉnh độ dày thanh che"
                  style={{
                    position: 'absolute',
                    right: 3,
                    bottom: 0,
                    fontSize: 9,
                    background: '#0284c7',
                    padding: '0 4px',
                    borderRadius: 3,
                    cursor: 'row-resize',
                  }}
                >
                  ↕
                </span>
              </div>
            )}
          </div>

          {isSplit && (
            <div
              style={{
                position: 'absolute',
                left: 0,
                right: 0,
                bottom: 0,
                height: '46%',
                background: '#0f172a',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontSize: 11,
                color: '#cbd5e1',
              }}
            >
              Video phụ giữ chân người xem (46% dưới)
            </div>
          )}

          {/* QR Code Preview */}
          {layoutConfig.qr_code_content?.trim() && (
            <div
              style={{
                position: 'absolute',
                right: 10,
                bottom: 66,
                width: 44,
                padding: '4px 3px',
                borderRadius: 6,
                background: '#ffffff',
                border: '1px solid #deb96e',
                color: '#0f172a',
                textAlign: 'center',
                zIndex: 9,
              }}
            >
              <div
                style={{
                  width: 30,
                  height: 30,
                  margin: '0 auto 2px',
                  background:
                    'repeating-conic-gradient(#0f172a 0% 25%, #fff 0% 50%) 50% / 8px 8px',
                  border: '1px solid #0f172a',
                }}
              />
              <div style={{ fontSize: 6.5, fontWeight: 700, lineHeight: 1.1 }}>
                {layoutConfig.qr_code_label || 'Quét QR'}
              </div>
            </div>
          )}

          {/* DRAGGABLE VIETNAMESE SUBTITLE BAR */}
          <div
            onPointerDown={(e) => startDrag('sub_move', e)}
            title="Giữ chuột kéo lên hoặc xuống để chỉnh vị trí phụ đề tiếng Việt"
            style={{
              position: 'absolute',
              top: `${subPosY * 100}%`,
              transform: 'translateY(-50%)',
              left: 10,
              right: 10,
              textAlign: 'center',
              color: '#fde047',
              fontWeight: 700,
              fontSize: previewSubPx,
              textShadow: '0 2px 4px #000, 0 0 3px #000',
              padding: '3px 6px',
              borderRadius: 6,
              border: '1px dashed rgba(253, 224, 71, 0.45)',
              background: 'rgba(0, 0, 0, 0.34)',
              cursor: 'ns-resize',
              zIndex: 11,
            }}
          >
            Kéo chỉnh vị trí phụ đề ({Math.round(subPosY * 100)}%)
          </div>

          {isProductMode &&
            layoutConfig.sales_badge_enabled &&
            layoutConfig.sales_contact_info?.trim() && (
              <div
                style={{
                  position: 'absolute',
                  bottom: 10,
                  left: 14,
                  right: 14,
                  background: 'rgba(14, 16, 21, 0.9)',
                  border: '1px solid rgba(222, 185, 110, 0.65)',
                  color: '#f8fafc',
                  fontSize: 8.8,
                  fontWeight: 600,
                  textAlign: 'center',
                  padding: '3px 8px',
                  borderRadius: 999,
                  zIndex: 6,
                  whiteSpace: 'nowrap',
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                }}
              >
                {layoutConfig.sales_contact_info}
              </div>
            )}
        </div>

        {/* TRUE 1080P FRAME & COVER SNAPSHOT BUTTONS */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, marginBottom: 12 }}>
          <button
            type="button"
            className="btn btn-primary btn-sm"
            disabled={renderingSnapshot}
            onClick={() => handleRenderTrueSnapshot(false)}
            title="Xuất thử 1 bức ảnh Full HD qua đúng bộ dựng thật"
          >
            {renderingSnapshot ? <Loader2 size={13} className="spin" /> : <Eye size={13} />} Khung thật 1080p
          </button>
          <button
            type="button"
            className="btn btn-secondary btn-sm"
            disabled={renderingSnapshot}
            onClick={() => handleRenderTrueSnapshot(true)}
            title="Xem trước Ảnh Bìa TikTok / Shorts thực tế"
          >
            {renderingSnapshot ? <Loader2 size={13} className="spin" /> : <Camera size={13} />} Xem Ảnh bìa
          </button>
        </div>

        <StudioLoadingBanner
          loading={renderingSnapshot}
          title="Đang dựng khung 1080p thực tế..."
          subtitle="Kết xuất qua bộ dựng FFmpeg"
        />

        {/* Subtitle Size & Position Quick Control */}
        <div className="surface-box" style={{ padding: '10px 12px', marginBottom: 12 }}>
          <div
            className="text-xs text-sub"
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              marginBottom: 4,
            }}
          >
            <span>
              Cỡ phụ đề: <strong>{subFontSize}px</strong>
            </span>
            <span>
              Vị trí dọc: <strong>{Math.round(subPosY * 100)}%</strong>
            </span>
          </div>
          <input
            type="range"
            min="32"
            max="76"
            step="2"
            style={{ width: '100%' }}
            value={subFontSize}
            onChange={(e) => update({ subtitle_font_size: Number(e.target.value) })}
          />
        </div>

        {/* Mode-Specific Framing & Transition Controls */}
        {!isMovieMode && !isThreadsMode && (
          <div className="form-group" style={{ marginBottom: 12 }}>
            <label className="form-label text-xs">Chuyển cảnh mượt chuẩn CapCut</label>
            <select
              className="select select-sm"
              value={layoutConfig.transition_style || 'AUTO_DIRECTOR'}
              onChange={(e) => update({ transition_style: e.target.value })}
            >
              <option value="AUTO_DIRECTOR">Đạo diễn tự động theo mạch nội dung</option>
              <option value="CAPCUT_DISSOLVE">Mờ chồng êm ái (Mượt chuẩn CapCut)</option>
              <option value="CAPCUT_SMOOTH_SLIDE">Lướt ngang mượt mà (Smooth Slide)</option>
              <option value="CAPCUT_ZOOM_FLOW">Thu phóng mềm mại (Zoom Flow)</option>
              <option value="CAPCUT_FLASH_BEAT">Chớp sáng tinh tế (Soft Flash)</option>
              <option value="STATIC_LOOKBOOK">Đứng tĩnh 100%</option>
            </select>
          </div>
        )}

        {isProductMode && (
          <div className="form-group" style={{ marginBottom: 12 }}>
            <label className="form-label text-xs">Kiểu nền tôn dáng sản phẩm</label>
            <select
              className="select select-sm"
              value={layoutConfig.product_framing || 'BLURRED_STUDIO_CARD'}
              onChange={(e) => update({ product_framing: e.target.value })}
            >
              <option value="BLURRED_STUDIO_CARD">Thẻ nguyên vẹn trên nền mờ</option>
              <option value="VELVET_DARK_LUXURY">Thẻ nguyên vẹn trên nền Đen Nhung</option>
              <option value="FULL_BLEED_LUXURY">Phóng vừa tràn khung</option>
            </select>
          </div>
        )}

        {isMovieMode && (
          <div className="form-group" style={{ marginBottom: 12 }}>
            <label className="form-label text-xs">Bố cục dựng phim dọc</label>
            <select
              className="select select-sm"
              value={layoutConfig.layout_type}
              onChange={(e) => update({ layout_type: e.target.value })}
            >
              <option value="BLUR_CENTER">Khung ngang ở giữa + Nền mờ</option>
              <option value="FACE_TRACK_FULL">Phóng toàn màn hình dọc bám khuôn mặt</option>
              <option value="SPLIT_RETENTION">Chia đôi màn hình trên - dưới</option>
            </select>
          </div>
        )}

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, marginBottom: 12 }}>
          <SwitchCard
            checked={showTopBanner}
            onChange={(val) => update({ show_top_banner: val })}
          >
            Tiêu đề đầu
          </SwitchCard>

          {isMovieMode ? (
            <SwitchCard
              checked={layoutConfig.hardsub_mask_enabled}
              onChange={(val) => update({ hardsub_mask_enabled: val })}
            >
              Che chữ gốc
            </SwitchCard>
          ) : (
            <SwitchCard
              checked={Boolean(layoutConfig.outro_card_enabled)}
              onChange={(val) => {
                update({ outro_card_enabled: val });
                if (val) setShowBrandKit(true);
              }}
            >
              Thẻ kết 2.5s
            </SwitchCard>
          )}
        </div>

        {/* SMART HUMAN-EYE EDITING & AMBIENCE DRAWER */}
        <button
          type="button"
          className="adv-toggle"
          onClick={() => setShowSmartEdit((p) => !p)}
        >
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
            <Sparkles size={15} style={{ color: 'var(--brand-text)' }} /> Smart Edit &amp; Không khí
          </span>
          {showSmartEdit ? <ChevronUp size={15} /> : <ChevronDown size={15} />}
        </button>

        {showSmartEdit && (
          <div className="adv-body" style={{ padding: 12, display: 'grid', gap: 8 }}>
            <div>
              <label className="form-label text-xs">Lớp phủ không khí điện ảnh</label>
              <select
                className="select select-sm"
                value={ambienceMode}
                onChange={(e) => update({ ambience_overlay: e.target.value })}
              >
                {AMBIENCE_OPTIONS.map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {opt.label}
                  </option>
                ))}
              </select>
            </div>
            <SwitchCard
              checked={storyBarEnabled}
              onChange={(val) => update({ story_progress_bar_enabled: val })}
            >
              Thanh tiến trình đốt truyện trên đỉnh
            </SwitchCard>
            <SwitchCard
              checked={layoutConfig.safe_zone_guard !== false}
              onChange={(val) => update({ safe_zone_guard: val })}
            >
              Khóa vùng an toàn TikTok/Shorts
            </SwitchCard>

            {!isMovieMode && !isThreadsMode && (
              <>
                <SwitchCard
                  checked={layoutConfig.smart_camera_motion !== false}
                  onChange={(val) => update({ smart_camera_motion: val })}
                >
                  Góc máy bám tâm chủ thể (5 hướng mượt)
                </SwitchCard>
                <SwitchCard
                  checked={layoutConfig.smart_micro_punch_in !== false}
                  onChange={(val) => update({ smart_micro_punch_in: val })}
                >
                  Nhịp cận cảnh nhẹ (106%) ở câu dài &gt;6s
                </SwitchCard>
              </>
            )}

            {!isMovieMode && (
              <SwitchCard
                checked={layoutConfig.auto_skip_black_intro !== false}
                onChange={(val) => update({ auto_skip_black_intro: val })}
              >
                Tự bỏ 1–3s đầu tối đen
              </SwitchCard>
            )}

            {isMovieMode && (
              <SwitchCard
                checked={layoutConfig.dynamic_face_tracking !== false}
                onChange={(val) => update({ dynamic_face_tracking: val })}
              >
                Bám khuôn mặt động theo nhân vật
              </SwitchCard>
            )}
          </div>
        )}

        {/* BRAND KIT & LUXURY OUTRO 2.5S DRAWER */}
        <button
          type="button"
          className="adv-toggle"
          style={{ marginBottom: showBrandKit || isMovieMode ? 8 : 0 }}
          onClick={() => setShowBrandKit((p) => !p)}
        >
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
            <Award size={15} style={{ color: 'var(--brand-text)' }} /> Brand Kit &amp; Thẻ kết
          </span>
          {showBrandKit ? <ChevronUp size={15} /> : <ChevronDown size={15} />}
        </button>

        {showBrandKit && (
          <div className="adv-body" style={{ padding: 12, marginBottom: isMovieMode ? 8 : 0 }}>
            <div style={{ marginBottom: 9 }}>
              <SwitchCard
                checked={Boolean(layoutConfig.outro_card_enabled)}
                onChange={(val) => update({ outro_card_enabled: val })}
              >
                Bật thẻ kết sang trọng 2.5s cuối video
              </SwitchCard>
            </div>

            <div className="form-group" style={{ marginBottom: 8 }}>
              <input
                className="input input-sm"
                placeholder="Tên cửa hàng / kênh (VD: Sơn Music Violin)"
                value={layoutConfig.outro_brand_title || ''}
                onChange={(e) => update({ outro_brand_title: e.target.value })}
              />
            </div>
            <div className="form-group" style={{ marginBottom: 8 }}>
              <input
                className="input input-sm"
                placeholder="Địa chỉ Showroom (VD: Test đàn trực tiếp tại Hà Nội)"
                value={layoutConfig.outro_subtitle || ''}
                onChange={(e) => update({ outro_subtitle: e.target.value })}
              />
            </div>
            <div className="form-group" style={{ marginBottom: 10 }}>
              <input
                className="input input-sm"
                placeholder="Website / Liên hệ (VD: www.sonmusic.vn)"
                value={layoutConfig.outro_contact_line || ''}
                onChange={(e) => update({ outro_contact_line: e.target.value })}
              />
            </div>

            <div style={{ display: 'grid', gap: 7 }}>
              <label className="btn btn-secondary btn-sm" style={{ width: '100%', cursor: 'pointer' }}>
                <ImagePlus size={14} />{' '}
                {layoutConfig.logo_path ? 'Đổi ảnh Logo thương hiệu' : 'Tải Logo thương hiệu (.png)'}
                <input type="file" accept="image/png,image/jpeg" hidden onChange={handleLogoUpload} />
              </label>

              <button
                type="button"
                className="btn btn-primary btn-sm"
                style={{ width: '100%' }}
                disabled={savingBrandKit}
                onClick={handleSaveBrandKit}
              >
                <BookmarkCheck size={14} />{' '}
                {savingBrandKit ? 'Đang lưu...' : 'Lưu làm Bộ Nhận Diện Mặc Định'}
              </button>
            </div>
          </div>
        )}

        {isMovieMode && (
          <>
            <button
              type="button"
              className="adv-toggle"
              style={{ marginBottom: showLayoutSettings ? 8 : 0 }}
              onClick={() => setShowLayoutSettings((p) => !p)}
            >
              <span>Che chữ gốc &amp; lật khung</span>
              {showLayoutSettings ? <ChevronUp size={15} /> : <ChevronDown size={15} />}
            </button>

            {showLayoutSettings && (
              <div className="adv-body" style={{ padding: 12, marginBottom: 0 }}>
                {layoutConfig.hardsub_mask_enabled && (
                  <div className="form-group" style={{ marginBottom: 9 }}>
                    <label className="form-label text-xs">Kiểu thanh che chữ ngoại ngữ gốc</label>
                    <select
                      className="select select-sm"
                      value={rect.mode}
                      onChange={(e) => updateRect({ mode: e.target.value })}
                    >
                      <option value="BLUR">Làm mờ mịn tự nhiên</option>
                      <option value="DARK_BOX">Thanh nền tối rõ nét</option>
                    </select>
                  </div>
                )}

                <div style={{ marginBottom: 8 }}>
                  <SwitchCard
                    checked={layoutConfig.anti_copyright_enabled}
                    onChange={(val) => update({ anti_copyright_enabled: val })}
                  >
                    Biến đổi tốc độ &amp; màu ({layoutConfig.speed_factor}x)
                  </SwitchCard>
                </div>

                {layoutConfig.anti_copyright_enabled && (
                  <div className="form-grid">
                    <div>
                      <label className="form-label text-xs">Tốc độ: {layoutConfig.speed_factor}x</label>
                      <input
                        type="range"
                        min="1.00"
                        max="1.12"
                        step="0.01"
                        style={{ width: '100%' }}
                        value={layoutConfig.speed_factor}
                        onChange={(e) => update({ speed_factor: parseFloat(e.target.value) })}
                      />
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', paddingTop: 12 }}>
                      <SwitchCard
                        checked={layoutConfig.mirror_flip}
                        onChange={(val) => update({ mirror_flip: val })}
                      >
                        Lật ngang hình
                      </SwitchCard>
                    </div>
                  </div>
                )}
              </div>
            )}
          </>
        )}
      </div>

      {/* CARD 2: MULTI-GPU & STORAGE */}
      <div className="card" style={{ padding: 16, marginBottom: 0 }}>
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            marginBottom: 10,
          }}
        >
          <span className="text-sm fw-700" style={{ display: 'flex', alignItems: 'center', gap: 7 }}>
            <Cpu size={16} strokeWidth={2} style={{ color: 'var(--brand-text)' }} /> Phần cứng ({gpus.length} GPU)
          </span>
          <span className={`badge ${systemStatus?.cuda_available ? 'badge-ok' : 'badge-warn'}`}>
            {systemStatus?.active_gpu_owner
              ? `Đang chạy: ${systemStatus.active_gpu_owner}`
              : systemStatus?.nvenc_available
              ? 'NVENC Sẵn sàng'
              : 'Sẵn sàng'}
          </span>
        </div>

        <div className="form-group" style={{ marginBottom: 10 }}>
          <select
            className="select select-sm"
            disabled={switchingGpu}
            value={systemStatus?.preferred_device || 'auto'}
            onChange={(e) => handleSelectGpu(e.target.value)}
          >
            <option value="auto">Tự động chọn Card đồ họa mạnh nhất</option>
            {gpus.map((g) => (
              <option key={g.device_id} value={g.device_id}>
                GPU #{g.index}: {g.name}{' '}
                {g.vram_total_mb > 0 ? `(${Math.round(g.vram_total_mb / 1024)}GB)` : ''}
              </option>
            ))}
            <option value="cpu">Chỉ sử dụng vi xử lý CPU</option>
          </select>
        </div>

        {gpus.map((g) => {
          const vramPct =
            g.vram_total_mb > 0
              ? Math.min(100, Math.round((g.vram_used_mb / g.vram_total_mb) * 100))
              : 0;
          return (
            <div key={g.device_id} className="gpu-card-item">
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 6 }}>
                <strong className="text-xs">
                  #{g.index} {g.name}
                </strong>
                <span className="badge">
                  {g.vendor} {g.temperature_c !== null ? `• ${g.temperature_c}°C` : ''}
                </span>
              </div>

              {g.vram_total_mb > 0 && (
                <div style={{ marginTop: 6 }}>
                  <div className="text-xs text-sub" style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <span>
                      VRAM: {(g.vram_used_mb / 1024).toFixed(1)} / {(g.vram_total_mb / 1024).toFixed(1)} GB
                    </span>
                    <span>Tải GPU: {Math.round(g.utilization_pct)}%</span>
                  </div>
                  <div className="progress-track" style={{ height: 6, margin: '4px 0 0' }}>
                    <div className="progress-fill" style={{ width: `${Math.max(4, vramPct)}%` }} />
                  </div>
                </div>
              )}
            </div>
          );
        })}

        <div
          style={{
            marginTop: 10,
            paddingTop: 10,
            borderTop: '1px solid var(--border)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: 8,
            flexWrap: 'wrap',
          }}
        >
          <div className="text-xs text-sub" style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
            <HardDrive size={14} /> Trống <strong>{storage.disk_free_gb ?? '--'} GB</strong> • Nháp{' '}
            <strong>{storage.work_temp_mb ?? 0} MB</strong>
          </div>
          <button
            type="button"
            className="btn btn-secondary btn-sm"
            disabled={cleaningTemp}
            onClick={handleCleanupTemp}
          >
            <Trash2 size={13} /> {cleaningTemp ? 'Đang dọn...' : 'Dọn tệp nháp'}
          </button>
        </div>
      </div>

      {/* TRUE 1080P COMPOSITOR SNAPSHOT MODAL */}
      {snapshotModal && (
        <div className="modal-backdrop" onClick={() => setSnapshotModal(null)}>
          <div
            className="card"
            onClick={(e) => e.stopPropagation()}
            style={{ width: '100%', maxWidth: 480, marginBottom: 0 }}
          >
            <div className="page-header" style={{ marginBottom: 12 }}>
              <div>
                <div className="text-md fw-700" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <Camera size={18} />{' '}
                  {snapshotModal.asCover
                    ? 'Ảnh Bìa Kết Xuất Thật (Cover Studio)'
                    : 'Khung Hình Kết Xuất Thật 100%'}
                </div>
                <div className="text-xs text-sub" style={{ marginTop: 3 }}>
                  {snapshotModal.width}×{snapshotModal.height}px • Dựng trong{' '}
                  {snapshotModal.elapsed_ms}ms •{' '}
                  {snapshotModal.nvenc_active ? 'Tăng tốc GPU h264_nvenc' : 'CPU x264'}
                </div>
              </div>
              <button
                type="button"
                className="btn btn-secondary btn-sm"
                onClick={() => setSnapshotModal(null)}
              >
                <X size={14} /> Đóng
              </button>
            </div>

            <div
              style={{
                background: '#05070b',
                borderRadius: 10,
                border: '1px solid var(--border-strong)',
                padding: 8,
                textAlign: 'center',
                marginBottom: 12,
              }}
            >
              <img
                src={`${snapshotModal.image_url}?t=${Date.now()}`}
                alt="True Frame Preview"
                style={{
                  maxWidth: '100%',
                  maxHeight: '64vh',
                  borderRadius: 6,
                  objectFit: 'contain',
                }}
              />
            </div>

            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
              <button
                type="button"
                className={`btn btn-sm ${!snapshotModal.asCover ? 'btn-primary' : 'btn-secondary'}`}
                style={{ flex: 1 }}
                disabled={renderingSnapshot}
                onClick={() => handleRenderTrueSnapshot(false)}
              >
                <Eye size={14} /> Khung trong Video
              </button>
              <button
                type="button"
                className={`btn btn-sm ${snapshotModal.asCover ? 'btn-primary' : 'btn-secondary'}`}
                style={{ flex: 1 }}
                disabled={renderingSnapshot}
                onClick={() => handleRenderTrueSnapshot(true)}
              >
                <Camera size={14} /> Khung Ảnh Bìa
              </button>
              <a
                href={snapshotModal.image_url}
                download={snapshotModal.asCover ? 'Anh_Bia_Thu.jpg' : 'Khung_Xem_Thu_1080p.jpg'}
                className="btn btn-secondary btn-sm"
              >
                <Download size={14} /> Tải ảnh
              </a>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
