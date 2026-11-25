import React, { useEffect, useRef, useState } from 'react';
import {
  Award,
  BookmarkCheck,
  ChevronDown,
  ChevronUp,
  Cpu,
  HardDrive,
  ImagePlus,
  Move,
  Smartphone,
  Trash2,
} from 'lucide-react';
import { studioApi } from '../m00_core_contracts/apiClient';

const ASPECT_META = {
  '9:16': { label: '9:16 Dọc', res: '1080×1920', height: 434 },
  '4:5': { label: '4:5 Feed', res: '1080×1350', height: 305 },
  '1:1': { label: '1:1 Vuông', res: '1080×1080', height: 244 },
};

export default function Canvas916Designer({
  layoutConfig,
  setLayoutConfig,
  previewFrameUrl,
  systemStatus,
  onSystemStatusUpdated,
  activeTab = 'movie',
  notify,
}) {
  const [showLayoutSettings, setShowLayoutSettings] = useState(false);
  const [showBrandKit, setShowBrandKit] = useState(false);
  const [savingBrandKit, setSavingBrandKit] = useState(false);
  const [cleaningTemp, setCleaningTemp] = useState(false);
  const [switchingGpu, setSwitchingGpu] = useState(false);

  const phoneRef = useRef(null);
  const movieRegionRef = useRef(null);
  const dragStateRef = useRef(null);

  const update = (patch) => setLayoutConfig((prev) => ({ ...prev, ...patch }));
  const updateRect = (rPatch) =>
    setLayoutConfig((prev) => ({
      ...prev,
      hardsub_rect: { ...prev.hardsub_rect, ...rPatch },
    }));

  // Load saved Store Brand Kit once on mount
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
      notify('Đã lưu Bộ Nhận Diện Cửa Hàng (Brand Kit) cho các dự án tiếp theo.');
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
      notify('Đã gắn Logo cửa hàng. Kéo thả trên màn hình xem trước để đổi vị trí.');
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

  const rect = layoutConfig.hardsub_rect;
  const isProductMode = activeTab === 'product';
  const aspectKey = layoutConfig.aspect_ratio || '9:16';
  const aspectInfo = ASPECT_META[aspectKey] || ASPECT_META['9:16'];
  const isSplit = !isProductMode && layoutConfig.layout_type === 'SPLIT_RETENTION';
  const isFull = isProductMode
    ? layoutConfig.product_framing === 'FULL_BLEED_LUXURY'
    : layoutConfig.layout_type === 'FACE_TRACK_FULL';
  const isVelvetDark =
    isProductMode &&
    (layoutConfig.product_framing === 'VELVET_DARK_LUXURY' || layoutConfig.studio_cutout_enabled);
  const showTopBanner = layoutConfig.show_top_banner !== false;
  const subPosY = layoutConfig.subtitle_pos_y ?? 0.84;
  const subFontSize = layoutConfig.subtitle_font_size ?? 52;
  const previewSubPx = Math.max(9.5, Math.min(15.5, +(subFontSize * 0.22).toFixed(1)));
  const gpus = systemStatus?.gpus || [];
  const storage = systemStatus?.storage || {};

  return (
    <div>
      {/* CARD 1: MULTI-ASPECT PREVIEW, DRAGGABLE SUBTITLES & BRAND KIT */}
      <div className="card" style={{ padding: 15 }}>
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            marginBottom: 8,
          }}
        >
          <span style={{ fontWeight: 600, fontSize: 13.8, display: 'flex', alignItems: 'center', gap: 7 }}>
            <Smartphone size={16} strokeWidth={1.8} /> Xem trước khung hình
          </span>
          <span className="badge">{aspectInfo.res}</span>
        </div>

        {/* Aspect Ratio Selector Pills */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 5, marginBottom: 10 }}>
          {Object.entries(ASPECT_META).map(([ratioKey, meta]) => (
            <button
              key={ratioKey}
              type="button"
              className={`btn btn-sm ${aspectKey === ratioKey ? 'btn-primary' : 'btn-secondary'}`}
              style={{ padding: '4px 6px', minHeight: 28, fontSize: 11.5 }}
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
                : previewFrameUrl
                ? `url(${previewFrameUrl}) center/cover no-repeat`
                : 'linear-gradient(165deg, #1b2230, #0d1118 65%)',
              filter: isFull || isVelvetDark ? 'none' : 'blur(11px) brightness(0.42)',
            }}
          />

          {/* Draggable Channel Logo */}
          {layoutConfig.logo_path && (
            <div
              onPointerDown={(e) => startDrag('logo_move', e)}
              title="Kéo để di chuyển vị trí Logo"
              style={{
                position: 'absolute',
                left: `${layoutConfig.logo_pos_x * 100}%`,
                top: `${layoutConfig.logo_pos_y * 100}%`,
                background: 'rgba(2, 132, 199, 0.9)',
                border: '1px solid rgba(255,255,255,0.8)',
                color: '#fff',
                fontSize: 9.5,
                fontWeight: 600,
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
              {isProductMode ? 'Tên Sản Phẩm Tinh Tế' : 'Tiêu Đề Video | Phần 1'}
            </div>
          )}

          {/* Optional Smoked-Obsidian & Champagne-Gold Offer Pill */}
          {layoutConfig.sales_badge_enabled && layoutConfig.sales_price_or_offer?.trim() && (
            <div
              style={{
                position: 'absolute',
                top: showTopBanner ? 48 : 22,
                left: 20,
                right: 20,
                background: 'rgba(16, 18, 23, 0.86)',
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

          {/* Main Video / Uncropped Product Card or Split A/B Preview */}
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
                  : '#161b24',
              border:
                isProductMode && !isFull
                  ? '1px solid rgba(212, 175, 55, 0.32)'
                  : isFull
                  ? 'none'
                  : '1px solid rgba(255,255,255,0.14)',
              boxShadow: isProductMode && !isFull ? '0 8px 20px rgba(0,0,0,0.45)' : 'none',
              overflow: 'hidden',
            }}
          >
            {isProductMode && layoutConfig.comparison_split_enabled ? (
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', height: '100%', gap: 4, padding: 5 }}>
                {[layoutConfig.comparison_label_a || 'Bản A', layoutConfig.comparison_label_b || 'Bản B'].map(
                  (lbl, cIdx) => (
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
                  )
                )}
              </div>
            ) : !previewFrameUrl ? (
              <div
                style={{
                  height: '100%',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  fontSize: 11,
                  color: '#9ca3af',
                  padding: 8,
                  textAlign: 'center',
                }}
              >
                {isProductMode
                  ? 'Ảnh / Clip sản phẩm giữ nguyên 100% tỷ lệ'
                  : isFull
                  ? 'Khung toàn màn hình dọc'
                  : 'Vùng hiển thị hình ảnh chính'}
              </div>
            ) : null}

            {!isProductMode && layoutConfig.hardsub_mask_enabled && (
              <div
                onPointerDown={(e) => startDrag('mask_move', e)}
                title="Giữ kéo lên hoặc xuống để che đúng dòng chữ gốc"
                style={{
                  position: 'absolute',
                  left: `${rect.x * 100}%`,
                  top: `${rect.y * 100}%`,
                  width: `${rect.w * 100}%`,
                  height: `${rect.h * 100}%`,
                  background:
                    rect.mode === 'DARK_BOX'
                      ? 'rgba(0,0,0,0.84)'
                      : 'rgba(148, 163, 184, 0.34)',
                  backdropFilter: rect.mode === 'BLUR' ? 'blur(6px)' : 'none',
                  border: '1px dashed #38bdf8',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  fontSize: 9,
                  color: '#e0f2fe',
                  fontWeight: 600,
                  cursor: 'ns-resize',
                }}
              >
                Kéo vùng che chữ gốc ({Math.round(rect.y * 100)}%)
                <span
                  onPointerDown={(e) => startDrag('mask_resize', e)}
                  title="Kéo để chỉnh độ dày"
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
            title="Giữ kéo lên hoặc xuống để đặt vị trí dòng phụ đề tiếng Việt"
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
              padding: '2px 6px',
              borderRadius: 5,
              border: '1px dashed rgba(253, 224, 71, 0.35)',
              background: 'rgba(0, 0, 0, 0.22)',
              cursor: 'ns-resize',
              zIndex: 11,
            }}
          >
            Kéo chỉnh vị trí phụ đề ({Math.round(subPosY * 100)}%)
          </div>

          {layoutConfig.sales_badge_enabled && layoutConfig.sales_contact_info?.trim() && (
            <div
              style={{
                position: 'absolute',
                bottom: 10,
                left: 14,
                right: 14,
                background: 'rgba(14, 16, 21, 0.88)',
                border: '1px solid rgba(222, 185, 110, 0.65)',
                color: '#f3f4f6',
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

        {/* Subtitle Size & Position Quick Control */}
        <div className="form-group" style={{ marginBottom: 8 }}>
          <div
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              fontSize: 11.4,
              color: '#9ca3af',
              marginBottom: 2,
            }}
          >
            <span>Cỡ chữ phụ đề: <strong>{subFontSize}px</strong></span>
            <span>Cao độ: <strong>{Math.round(subPosY * 100)}%</strong> (Kéo trên màn hình)</span>
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

        {/* Transition & Framing Controls */}
        <div className="form-group" style={{ marginBottom: 8 }}>
          <label className="form-label" style={{ fontSize: 11.8 }}>
            Hiệu ứng chuyển cảnh mượt chuẩn CapCut
          </label>
          <select
            className="select"
            style={{ fontSize: 12.4, minHeight: 34, padding: '5px 9px' }}
            value={layoutConfig.transition_style || 'CAPCUT_DISSOLVE'}
            onChange={(e) => update({ transition_style: e.target.value })}
          >
            <option value="CAPCUT_DISSOLVE">Mờ chồng êm ái (Mượt chuẩn CapCut)</option>
            <option value="CAPCUT_SMOOTH_SLIDE">Lướt ngang mượt mà (Smooth Slide)</option>
            <option value="CAPCUT_ZOOM_FLOW">Thu phóng mềm mại (Zoom Flow)</option>
            <option value="CAPCUT_FLASH_BEAT">Chớp sáng tinh tế (Soft Flash)</option>
            <option value="STATIC_LOOKBOOK">Đứng tĩnh 100% (Không zoom, không rung)</option>
          </select>
        </div>

        {isProductMode ? (
          <div className="form-group" style={{ marginBottom: 8 }}>
            <label className="form-label" style={{ fontSize: 11.8 }}>
              Kiểu nền tôn dáng sản phẩm
            </label>
            <select
              className="select"
              style={{ fontSize: 12.4, minHeight: 34, padding: '5px 9px' }}
              value={layoutConfig.product_framing || 'BLURRED_STUDIO_CARD'}
              onChange={(e) => update({ product_framing: e.target.value })}
            >
              <option value="BLURRED_STUDIO_CARD">Thẻ nguyên vẹn trên nền mờ nghệ thuật</option>
              <option value="VELVET_DARK_LUXURY">Thẻ nguyên vẹn trên nền Đen Nhung sang trọng</option>
              <option value="FULL_BLEED_LUXURY">Phóng vừa tràn khung (Dành cho ảnh dọc)</option>
            </select>
          </div>
        ) : (
          <div className="form-group" style={{ marginBottom: 8 }}>
            <select
              className="select"
              style={{ fontSize: 12.4, minHeight: 34, padding: '5px 9px' }}
              value={layoutConfig.layout_type}
              onChange={(e) => update({ layout_type: e.target.value })}
            >
              <option value="BLUR_CENTER">Khung ngang ở giữa + Nền mờ (Khuyên dùng)</option>
              <option value="FACE_TRACK_FULL">Phóng toàn màn hình dọc bám khuôn mặt</option>
              <option value="SPLIT_RETENTION">Chia đôi màn hình trên - dưới</option>
            </select>
          </div>
        )}

        <div
          style={{
            display: 'grid',
            gridTemplateColumns: '1fr 1fr',
            gap: 6,
            marginBottom: 8,
          }}
        >
          <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, cursor: 'pointer' }}>
            <input
              type="checkbox"
              checked={showTopBanner}
              onChange={(e) => update({ show_top_banner: e.target.checked })}
            />
            Hiện tiêu đề đầu
          </label>

          {!isProductMode ? (
            <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, cursor: 'pointer' }}>
              <input
                type="checkbox"
                checked={layoutConfig.hardsub_mask_enabled}
                onChange={(e) => update({ hardsub_mask_enabled: e.target.checked })}
              />
              Làm mờ chữ gốc
            </label>
          ) : (
            <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, cursor: 'pointer' }}>
              <input
                type="checkbox"
                checked={Boolean(layoutConfig.outro_card_enabled)}
                onChange={(e) => {
                  update({ outro_card_enabled: e.target.checked });
                  if (e.target.checked) setShowBrandKit(true);
                }}
              />
              Thẻ kết 2.5s cuối
            </label>
          )}
        </div>

        {/* BRAND KIT & LUXURY OUTRO 2.5S DRAWER */}
        <button
          type="button"
          className="adv-toggle"
          style={{ marginBottom: 8, padding: '7px 11px', fontSize: 12.2 }}
          onClick={() => setShowBrandKit((p) => !p)}
        >
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
            <Award size={14} /> Bộ nhận diện (Brand Kit) & Thẻ kết 2.5s
          </span>
          {showBrandKit ? <ChevronUp size={15} /> : <ChevronDown size={15} />}
        </button>

        {showBrandKit && (
          <div className="adv-body" style={{ padding: 11, marginBottom: 8 }}>
            <label
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 7,
                fontSize: 12.2,
                fontWeight: 600,
                marginBottom: 8,
                cursor: 'pointer',
              }}
            >
              <input
                type="checkbox"
                checked={Boolean(layoutConfig.outro_card_enabled)}
                onChange={(e) => update({ outro_card_enabled: e.target.checked })}
              />
              Bật thẻ kết sang trọng 2.5s ở cuối video
            </label>

            <div className="form-group" style={{ marginBottom: 7 }}>
              <input
                className="input"
                style={{ minHeight: 32, padding: '5px 9px', fontSize: 12.2 }}
                placeholder="Tên cửa hàng / thương hiệu (VD: Sơn Music Violin)"
                value={layoutConfig.outro_brand_title || ''}
                onChange={(e) => update({ outro_brand_title: e.target.value })}
              />
            </div>
            <div className="form-group" style={{ marginBottom: 7 }}>
              <input
                className="input"
                style={{ minHeight: 32, padding: '5px 9px', fontSize: 12.2 }}
                placeholder="Địa chỉ Showroom (VD: Test đàn trực tiếp tại Hà Nội)"
                value={layoutConfig.outro_subtitle || ''}
                onChange={(e) => update({ outro_subtitle: e.target.value })}
              />
            </div>
            <div className="form-group" style={{ marginBottom: 8 }}>
              <input
                className="input"
                style={{ minHeight: 32, padding: '5px 9px', fontSize: 12.2 }}
                placeholder="Website / Liên hệ (VD: www.sonmusic.vn)"
                value={layoutConfig.outro_contact_line || ''}
                onChange={(e) => update({ outro_contact_line: e.target.value })}
              />
            </div>

            <div style={{ display: 'grid', gap: 6 }}>
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

        {!isProductMode && (
          <>
            <button
              type="button"
              className="adv-toggle"
              style={{ marginBottom: showLayoutSettings ? 10 : 0, padding: '7px 11px', fontSize: 12.2 }}
              onClick={() => setShowLayoutSettings((p) => !p)}
            >
              <span>Tùy chỉnh che chữ gốc & lật khung hình</span>
              {showLayoutSettings ? <ChevronUp size={15} /> : <ChevronDown size={15} />}
            </button>

            {showLayoutSettings && (
              <div className="adv-body" style={{ padding: 11, marginBottom: 0 }}>
                {layoutConfig.hardsub_mask_enabled && (
                  <div className="form-group" style={{ marginBottom: 8 }}>
                    <label className="form-label">Kiểu che chữ gốc</label>
                    <select
                      className="select"
                      value={rect.mode}
                      onChange={(e) => updateRect({ mode: e.target.value })}
                    >
                      <option value="BLUR">Làm mờ tự nhiên</option>
                      <option value="DARK_BOX">Thanh nền tối</option>
                    </select>
                  </div>
                )}

                <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, marginBottom: 6 }}>
                  <input
                    type="checkbox"
                    checked={layoutConfig.anti_copyright_enabled}
                    onChange={(e) => update({ anti_copyright_enabled: e.target.checked })}
                  />
                  Biến đổi khung tránh trùng lặp ({layoutConfig.speed_factor}x)
                </label>
                {layoutConfig.anti_copyright_enabled && (
                  <div className="form-grid">
                    <div>
                      <label className="form-label">Tốc độ: {layoutConfig.speed_factor}x</label>
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
                    <div style={{ display: 'flex', alignItems: 'center', paddingTop: 14 }}>
                      <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12 }}>
                        <input
                          type="checkbox"
                          checked={layoutConfig.mirror_flip}
                          onChange={(e) => update({ mirror_flip: e.target.checked })}
                        />
                        Lật ngang hình
                      </label>
                    </div>
                  </div>
                )}
              </div>
            )}
          </>
        )}
      </div>

      {/* CARD 2: MULTI-GPU & STORAGE */}
      <div className="card" style={{ padding: 15, marginBottom: 0 }}>
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            marginBottom: 10,
          }}
        >
          <span style={{ fontWeight: 600, fontSize: 13.8, display: 'flex', alignItems: 'center', gap: 7 }}>
            <Cpu size={16} strokeWidth={1.8} /> Thiết bị xử lý ({gpus.length} GPU)
          </span>
          <span className={`badge ${systemStatus?.cuda_available ? 'badge-ok' : 'badge-warn'}`}>
            {systemStatus?.active_gpu_owner ? `Đang chạy: ${systemStatus.active_gpu_owner}` : 'Sẵn sàng'}
          </span>
        </div>

        <div className="form-group" style={{ marginBottom: 10 }}>
          <select
            className="select"
            style={{ fontSize: 12.8 }}
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
                <strong style={{ fontSize: 12.6 }}>
                  #{g.index} {g.name}
                </strong>
                <span className="badge" style={{ fontSize: 10.5, padding: '1px 6px' }}>
                  {g.vendor} {g.temperature_c !== null ? `• ${g.temperature_c}°C` : ''}
                </span>
              </div>

              {g.vram_total_mb > 0 && (
                <div style={{ marginTop: 6 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11.2, color: '#9ca3af' }}>
                    <span>
                      Bộ nhớ VRAM: {(g.vram_used_mb / 1024).toFixed(1)} / {(g.vram_total_mb / 1024).toFixed(1)} GB
                    </span>
                    <span>Tải GPU: {Math.round(g.utilization_pct)}%</span>
                  </div>
                  <div className="progress-track" style={{ height: 5, margin: '4px 0 0' }}>
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
          <div style={{ fontSize: 11.8, color: '#9ca3af', display: 'flex', alignItems: 'center', gap: 5 }}>
            <HardDrive size={14} /> Trống <strong>{storage.disk_free_gb ?? '--'} GB</strong> • Tạm{' '}
            <strong>{storage.work_temp_mb ?? 0} MB</strong>
          </div>
          <button
            type="button"
            className="btn btn-secondary btn-sm"
            disabled={cleaningTemp}
            onClick={handleCleanupTemp}
          >
            <Trash2 size={13} /> {cleaningTemp ? 'Đang dọn...' : 'Dọn tệp tạm'}
          </button>
        </div>
      </div>
    </div>
  );
}
