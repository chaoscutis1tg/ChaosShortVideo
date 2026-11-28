import React, { useEffect, useState } from 'react';
import {
  BarChart3,
  CheckCircle2,
  Columns,
  GitBranch,
  LayoutGrid,
  Loader2,
  Play,
  RotateCcw,
  Sparkles,
  Type,
  Wand2,
  Zap,
} from 'lucide-react';
import { studioApi } from '../m00_core_contracts/apiClient';

export const MOTION_THEME_OPTIONS = [
  {
    value: 'APPLE_GLASS_DARK',
    label: 'Apple Glass Tối Sang Trọng (Đa năng)',
    bg: 'linear-gradient(165deg, #0b0f1a 0%, #161f32 100%)',
    accent: '#38bdf8',
    cardBg: 'rgba(22, 31, 48, 0.9)',
    border: 'rgba(56, 189, 248, 0.45)',
    text: '#f8fafc',
    sub: '#94a3b8',
  },
  {
    value: 'DAN_KOE_MINIMAL',
    label: 'Dan Koe Đen-Trắng Tối Giản (Tư duy / Kể chuyện)',
    bg: 'linear-gradient(165deg, #060608 0%, #111115 100%)',
    accent: '#fafafa',
    cardBg: 'rgba(18, 18, 22, 0.94)',
    border: 'rgba(228, 228, 231, 0.55)',
    text: '#fafafa',
    sub: '#a1a1aa',
  },
  {
    value: 'WARM_ARTISAN_GOLD',
    label: 'Nghệ Nhân Vàng & Gỗ Ấm (Nhạc cụ / Bán hàng)',
    bg: 'linear-gradient(165deg, #140f0c 0%, #261b13 100%)',
    accent: '#f5bc52',
    cardBg: 'rgba(31, 23, 17, 0.92)',
    border: 'rgba(245, 188, 82, 0.52)',
    text: '#fef9ef',
    sub: '#d6c4ac',
  },
  {
    value: 'NEON_TECH_INFOGRAPHIC',
    label: 'Infographic Xanh Cyan (Khoa học / Số liệu)',
    bg: 'linear-gradient(165deg, #06101a 0%, #0a202e 100%)',
    accent: '#22d3ee',
    cardBg: 'rgba(11, 29, 44, 0.92)',
    border: 'rgba(34, 211, 238, 0.52)',
    text: '#f0fdfa',
    sub: '#94c5d4',
  },
];

const TEMPLATE_META = [
  { id: 'KINETIC_HOOK', label: 'Chữ động Kinetic', icon: Type },
  { id: 'STAT_COUNTER', label: 'Số chạy Counter', icon: Zap },
  { id: 'BAR_CHART', label: 'Biểu đồ Thanh', icon: BarChart3 },
  { id: 'VERSUS_SPLIT', label: 'So sánh A vs B', icon: Columns },
  { id: 'STEP_FLOW', label: 'Lộ trình Bước', icon: GitBranch },
  { id: 'SPEC_SPOTLIGHT', label: 'Bento Thông số', icon: LayoutGrid },
];

const QUICK_REFINE_PROMPTS = [
  'Đổi thành bảng so sánh 2 cột trực diện',
  'Đổi sang biểu đồ thanh % từ cao xuống thấp',
  'Làm con số 85% chạy tăng dần nổi bật',
  'Đổi sang sơ đồ lộ trình từng bước 01 - 02 - 03',
];

export default function MotionArtifactStudio({
  scenes = [],
  setScenes,
  motionTheme = 'APPLE_GLASS_DARK',
  onChangeTheme,
  usedBrainLabel = 'Claude / Gemini',
  submitting = false,
  onRenderMp4,
  notify,
}) {
  const [activeIdx, setActiveIdx] = useState(0);
  const [animKey, setAnimKey] = useState(0);
  const [autoPlaying, setAutoPlaying] = useState(false);
  const [promptInput, setPromptInput] = useState('');
  const [refining, setRefining] = useState(false);
  const [progressTick, setProgressTick] = useState(0);

  const safeIdx = Math.min(Math.max(0, activeIdx), Math.max(0, scenes.length - 1));
  const curScene = scenes[safeIdx] || null;
  const spec = curScene?.motion_spec || {
    template: 'KINETIC_HOOK',
    theme: motionTheme,
    badge_text: 'ĐIỂM NHẤN',
    headline: curScene?.vi_text || '',
    subheadline: '',
    stat_value: 85,
    stat_suffix: '%',
    items: ['Ý chính 1|92', 'Ý chính 2|68', 'Ý chính 3|45'],
    left_title: 'Chuẩn',
    right_title: 'Cũ',
    left_points: ['Hiệu quả cao', 'Ổn định lâu dài'],
    right_points: ['Hạn chế', 'Nhanh chững lại'],
  };

  const themeObj =
    MOTION_THEME_OPTIONS.find((t) => t.value === motionTheme) || MOTION_THEME_OPTIONS[0];

  useEffect(() => {
    setProgressTick(8);
    const t1 = setTimeout(() => setProgressTick(55), 90);
    const t2 = setTimeout(() => setProgressTick(100), 360);
    return () => {
      clearTimeout(t1);
      clearTimeout(t2);
    };
  }, [safeIdx, animKey, motionTheme, spec.template]);

  useEffect(() => {
    if (!autoPlaying || scenes.length <= 1) return undefined;
    const timer = setTimeout(() => {
      if (safeIdx < scenes.length - 1) {
        setActiveIdx(safeIdx + 1);
      } else {
        setAutoPlaying(false);
      }
    }, 2800);
    return () => clearTimeout(timer);
  }, [autoPlaying, safeIdx, scenes.length]);

  const patchScene = (idx, patch) => {
    setScenes((prev) => prev.map((sc, i) => (i !== idx ? sc : { ...sc, ...patch })));
  };

  const patchSpec = (idx, specPatch) => {
    setScenes((prev) =>
      prev.map((sc, i) =>
        i !== idx
          ? sc
          : {
              ...sc,
              motion_spec: {
                ...(sc.motion_spec || spec),
                theme: motionTheme,
                ...specPatch,
              },
            }
      )
    );
    setAnimKey((k) => k + 1);
  };

  const handleRefineByPrompt = async (overridePrompt = '') => {
    const cleanP = (overridePrompt || promptInput).trim();
    if (!curScene || cleanP.length < 3) {
      notify('Vui lòng nhập yêu cầu chỉnh sửa cho phân cảnh này (ít nhất 3 ký tự).');
      return;
    }
    setRefining(true);
    try {
      const res = await studioApi.refineMotionScene({
        vi_text: curScene.vi_text,
        user_instruction: cleanP,
        current_spec: spec,
        motion_theme: motionTheme,
      });
      patchScene(safeIdx, {
        vi_text: res.vi_text || curScene.vi_text,
        motion_spec: { ...res.motion_spec, theme: motionTheme },
      });
      setPromptInput('');
      setAnimKey((k) => k + 1);
      notify(res.note || 'Đã cập nhật hoạt ảnh phân cảnh!');
    } catch (err) {
      notify(`Lỗi chỉnh sửa phân cảnh: ${err.message}`);
    } finally {
      setRefining(false);
    }
  };

  if (!curScene) return null;

  const parsedBars = (spec.items?.length ? spec.items : ['Mức chuẩn|94', 'Trung bình|65', 'Cũ|40'])
    .slice(0, 4)
    .map((raw, idx) => {
      if (String(raw).includes('|')) {
        const [l, v] = String(raw).split('|');
        const num = Math.max(12, Math.min(100, parseFloat(v) || 80 - idx * 18));
        return { label: l.trim(), val: num };
      }
      return { label: String(raw), val: Math.max(30, 92 - idx * 20) };
    });

  return (
    <div
      className="surface-box fade-slide-in"
      style={{
        marginTop: 12,
        marginBottom: 16,
        borderColor: 'var(--brand-border)',
        padding: 16,
      }}
    >
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          gap: 10,
          flexWrap: 'wrap',
          marginBottom: 14,
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
          <span className="badge badge-ok">
            <CheckCircle2 size={12} /> Motion Artifacts • {usedBrainLabel}
          </span>
          <strong className="text-sm">
            Xem trước {scenes.length} phân cảnh &amp; gõ lệnh sửa trực tiếp trước khi xuất MP4
          </strong>
        </div>

        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
          <button
            type="button"
            className="btn btn-secondary btn-sm"
            onClick={() => setAnimKey((k) => k + 1)}
          >
            <RotateCcw size={13} /> Phát lại cảnh {safeIdx + 1}
          </button>
          <button
            type="button"
            className={`btn btn-sm ${autoPlaying ? 'btn-primary' : 'btn-secondary'}`}
            onClick={() => {
              if (!autoPlaying && safeIdx === scenes.length - 1) setActiveIdx(0);
              setAutoPlaying((p) => !p);
            }}
          >
            <Play size={13} /> {autoPlaying ? 'Đang chạy liên tiếp...' : 'Chạy thử cả chuỗi'}
          </button>
        </div>
      </div>

      {/* SCENE TIMELINE STRIP */}
      <div style={{ display: 'flex', gap: 8, overflowX: 'auto', paddingBottom: 8, marginBottom: 14 }}>
        {scenes.map((sc, idx) => {
          const isAct = idx === safeIdx;
          const tplId = sc.motion_spec?.template || 'KINETIC_HOOK';
          const tplObj = TEMPLATE_META.find((t) => t.id === tplId) || TEMPLATE_META[0];
          return (
            <button
              key={idx}
              type="button"
              onClick={() => {
                setAutoPlaying(false);
                setActiveIdx(idx);
              }}
              className={`btn btn-sm ${isAct ? 'btn-primary' : 'btn-secondary'}`}
              style={{
                flexShrink: 0,
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'flex-start',
                padding: '7px 12px',
                height: 'auto',
                minWidth: 148,
                textAlign: 'left',
              }}
            >
              <span className="text-xs fw-700">
                Cảnh {idx + 1} • {tplObj.label}
              </span>
              <span
                className="text-xs"
                style={{
                  opacity: 0.84,
                  maxWidth: 152,
                  whiteSpace: 'nowrap',
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                }}
              >
                {sc.vi_text}
              </span>
            </button>
          );
        })}
      </div>

      {/* 2-COLUMN LIVE ARTIFACT PREVIEW + NATURAL LANGUAGE EDITOR */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'minmax(240px, 272px) minmax(0, 1fr)',
          gap: 16,
          alignItems: 'start',
        }}
      >
        {/* LEFT: LIVE 9:16 INTERACTIVE MOTION GRAPHICS STAGE */}
        <div
          key={`${safeIdx}_${animKey}_${motionTheme}_${spec.template}`}
          style={{
            position: 'relative',
            width: '100%',
            aspectRatio: '9 / 16',
            borderRadius: 18,
            overflow: 'hidden',
            background: themeObj.bg,
            border: `2px solid ${themeObj.border}`,
            boxShadow: 'var(--shadow-elevated)',
            padding: '20px 14px',
            display: 'flex',
            flexDirection: 'column',
            justifyContent: 'center',
            color: themeObj.text,
          }}
        >
          <div
            style={{
              position: 'absolute',
              inset: 0,
              backgroundImage:
                'linear-gradient(rgba(255,255,255,0.04) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.04) 1px, transparent 1px)',
              backgroundSize: '22px 22px',
              pointerEvents: 'none',
            }}
          />

          <div style={{ position: 'relative', textAlign: 'center', marginBottom: 12 }}>
            <span
              style={{
                display: 'inline-block',
                padding: '3px 10px',
                borderRadius: 99,
                fontSize: 10,
                fontWeight: 700,
                letterSpacing: 0.5,
                color: themeObj.accent,
                border: `1px solid ${themeObj.accent}`,
                background: 'rgba(255,255,255,0.05)',
              }}
            >
              {(spec.badge_text || `CẢNH ${safeIdx + 1}`).toUpperCase()}
            </span>
          </div>

          <div style={{ position: 'relative', zIndex: 2 }}>
            {spec.template === 'STAT_COUNTER' ? (
              <div style={{ textAlign: 'center' }}>
                <div className="text-xs fw-700" style={{ marginBottom: 12 }}>
                  {spec.headline || curScene.vi_text.slice(0, 65)}
                </div>
                <div
                  style={{
                    width: 112,
                    height: 112,
                    margin: '0 auto 12px',
                    borderRadius: '50%',
                    border: `6px solid ${themeObj.accent}`,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    fontSize: 24,
                    fontWeight: 700,
                    color: themeObj.accent,
                    boxShadow: `0 0 24px ${themeObj.border}`,
                    transition: 'transform 0.45s cubic-bezier(0.22, 1, 0.36, 1)',
                    transform: progressTick > 20 ? 'scale(1)' : 'scale(0.75)',
                  }}
                >
                  {spec.stat_prefix || ''}
                  {Math.round(((spec.stat_value || 85) * progressTick) / 100)}
                  {spec.stat_suffix || '%'}
                </div>
                <div
                  style={{
                    padding: '8px 10px',
                    borderRadius: 10,
                    background: themeObj.cardBg,
                    border: `1px solid ${themeObj.border}`,
                    fontSize: 11,
                    color: themeObj.sub,
                    lineHeight: 1.4,
                  }}
                >
                  {(spec.subheadline || curScene.vi_text).slice(0, 110)}
                </div>
              </div>
            ) : spec.template === 'BAR_CHART' ? (
              <div>
                <div className="text-xs fw-700" style={{ textAlign: 'center', marginBottom: 10 }}>
                  {spec.headline || curScene.vi_text.slice(0, 60)}
                </div>
                <div
                  style={{
                    padding: 10,
                    borderRadius: 12,
                    background: themeObj.cardBg,
                    border: `1px solid ${themeObj.border}`,
                    display: 'grid',
                    gap: 9,
                  }}
                >
                  {parsedBars.map((b, bIdx) => (
                    <div key={bIdx}>
                      <div
                        style={{
                          display: 'flex',
                          justifyContent: 'space-between',
                          fontSize: 11,
                          fontWeight: 600,
                          marginBottom: 3,
                        }}
                      >
                        <span>{b.label.slice(0, 24)}</span>
                        <span style={{ color: themeObj.accent }}>
                          {Math.round((b.val * progressTick) / 100)}%
                        </span>
                      </div>
                      <div
                        style={{
                          height: 8,
                          borderRadius: 99,
                          background: 'rgba(255,255,255,0.12)',
                          overflow: 'hidden',
                        }}
                      >
                        <div
                          style={{
                            width: `${(b.val * progressTick) / 100}%`,
                            height: '100%',
                            borderRadius: 99,
                            background: themeObj.accent,
                            transition: 'width 0.55s cubic-bezier(0.22, 1, 0.36, 1)',
                          }}
                        />
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            ) : spec.template === 'VERSUS_SPLIT' ? (
              <div>
                <div className="text-xs fw-700" style={{ textAlign: 'center', marginBottom: 10 }}>
                  {spec.headline || curScene.vi_text.slice(0, 58)}
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 6 }}>
                  <div
                    style={{
                      padding: 8,
                      borderRadius: 10,
                      background: themeObj.cardBg,
                      border: '1.5px solid #34d399',
                      fontSize: 10,
                    }}
                  >
                    <div style={{ fontWeight: 700, color: '#34d399', marginBottom: 5 }}>
                      ✓ {(spec.left_title || 'Chuẩn').slice(0, 14)}
                    </div>
                    {(spec.left_points?.length
                      ? spec.left_points
                      : ['Âm vang dày ấm', 'Bền bỉ lâu dài']
                    )
                      .slice(0, 3)
                      .map((pt, i) => (
                        <div key={i} style={{ marginBottom: 4, lineHeight: 1.3 }}>
                          • {pt.slice(0, 34)}
                        </div>
                      ))}
                  </div>
                  <div
                    style={{
                      padding: 8,
                      borderRadius: 10,
                      background: themeObj.cardBg,
                      border: '1px solid rgba(251, 113, 133, 0.65)',
                      fontSize: 10,
                      color: themeObj.sub,
                    }}
                  >
                    <div style={{ fontWeight: 700, color: '#fb7185', marginBottom: 5 }}>
                      ✕ {(spec.right_title || 'Cũ').slice(0, 14)}
                    </div>
                    {(spec.right_points?.length
                      ? spec.right_points
                      : ['Âm mỏng ít ngân', 'Dễ mỏi tay']
                    )
                      .slice(0, 3)
                      .map((pt, i) => (
                        <div key={i} style={{ marginBottom: 4, lineHeight: 1.3 }}>
                          • {pt.slice(0, 34)}
                        </div>
                      ))}
                  </div>
                </div>
              </div>
            ) : spec.template === 'STEP_FLOW' || spec.template === 'SPEC_SPOTLIGHT' ? (
              <div>
                <div className="text-xs fw-700" style={{ textAlign: 'center', marginBottom: 10 }}>
                  {spec.headline || curScene.vi_text.slice(0, 58)}
                </div>
                <div style={{ display: 'grid', gap: 6 }}>
                  {(spec.items?.length
                    ? spec.items
                    : ['Bước 1: Nền tảng chuẩn', 'Bước 2: Luyện nhịp đều', 'Bước 3: Làm chủ cảm xúc']
                  )
                    .slice(0, 4)
                    .map((it, rIdx) => (
                      <div
                        key={rIdx}
                        style={{
                          display: 'flex',
                          alignItems: 'center',
                          gap: 7,
                          padding: '7px 9px',
                          borderRadius: 10,
                          background: themeObj.cardBg,
                          border: `1px solid ${rIdx === 0 ? themeObj.accent : themeObj.border}`,
                          fontSize: 11,
                          fontWeight: 600,
                          transform: progressTick > 20 ? 'translateY(0)' : 'translateY(10px)',
                          opacity: progressTick > 15 ? 1 : 0.2,
                          transition: `all ${0.28 + rIdx * 0.1}s ease`,
                        }}
                      >
                        <span
                          style={{
                            width: 20,
                            height: 20,
                            borderRadius: '50%',
                            background: themeObj.accent,
                            color: '#090d16',
                            fontSize: 10,
                            fontWeight: 700,
                            display: 'inline-flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            flexShrink: 0,
                          }}
                        >
                          0{rIdx + 1}
                        </span>
                        <span>{String(it).split('|')[0].slice(0, 44)}</span>
                      </div>
                    ))}
                </div>
              </div>
            ) : (
              <div style={{ textAlign: 'center', padding: '8px 4px' }}>
                <div
                  className="text-md fw-700"
                  style={{
                    marginBottom: 10,
                    transform: progressTick > 20 ? 'scale(1)' : 'scale(0.9)',
                    transition: 'transform 0.4s cubic-bezier(0.22, 1, 0.36, 1)',
                  }}
                >
                  {(spec.headline || curScene.vi_text).slice(0, 96)}
                </div>
                {spec.subheadline && (
                  <div style={{ fontSize: 11, color: themeObj.sub, lineHeight: 1.4 }}>
                    {spec.subheadline.slice(0, 90)}
                  </div>
                )}
              </div>
            )}
          </div>
        </div>

        {/* RIGHT: SCENE INSPECTOR + CLAUDE ARTIFACT NATURAL LANGUAGE PROMPT BAR */}
        <div style={{ display: 'grid', gap: 12 }}>
          <div className="form-grid" style={{ marginBottom: 0 }}>
            <div>
              <label className="form-label">Bảng màu thiết kế toàn video</label>
              <select
                className="select"
                value={motionTheme}
                onChange={(e) => onChangeTheme && onChangeTheme(e.target.value)}
              >
                {MOTION_THEME_OPTIONS.map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {opt.label}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="form-label">Nhãn tiêu điểm trên đỉnh cảnh {safeIdx + 1}</label>
              <input
                className="input"
                value={spec.badge_text || ''}
                onChange={(e) => patchSpec(safeIdx, { badge_text: e.target.value })}
                placeholder="VD: BÍ MẬT ÂM SẮC / CẤP ĐỘ 01"
              />
            </div>
          </div>

          <div>
            <label className="form-label">Kiểu bố cục hoạt ảnh của Cảnh {safeIdx + 1}</label>
            <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
              {TEMPLATE_META.map((tm) => {
                const Icon = tm.icon;
                const active = spec.template === tm.id;
                return (
                  <button
                    key={tm.id}
                    type="button"
                    className={`filter-pill ${active ? 'active' : ''}`}
                    onClick={() => patchSpec(safeIdx, { template: tm.id })}
                  >
                    <Icon size={13} /> {tm.label}
                  </button>
                );
              })}
            </div>
          </div>

          {/* CLAUDE ARTIFACT NATURAL LANGUAGE REFINER */}
          <div className="studio-callout studio-callout-brand">
            <label className="form-label">
              <Sparkles size={14} style={{ verticalAlign: '-2px', marginRight: 6, color: 'var(--brand-text)' }} />
              Gõ lệnh sửa riêng Cảnh {safeIdx + 1} bằng AI:
            </label>
            <div style={{ display: 'flex', gap: 8, marginBottom: 8 }}>
              <input
                className="input"
                style={{ flex: 1 }}
                placeholder="VD: Đổi thành bảng so sánh Gỗ thịt nguyên tấm và Gỗ ép 3 tiêu chí..."
                value={promptInput}
                onChange={(e) => setPromptInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') {
                    e.preventDefault();
                    handleRefineByPrompt();
                  }
                }}
              />
              <button
                type="button"
                className="btn btn-primary"
                style={{ whiteSpace: 'nowrap' }}
                disabled={refining}
                onClick={() => handleRefineByPrompt()}
              >
                {refining ? <Loader2 size={15} className="spin" /> : <Wand2 size={15} />}
                <span>{refining ? 'Đang sửa...' : 'Sửa cảnh này'}</span>
              </button>
            </div>
            <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
              {QUICK_REFINE_PROMPTS.map((qp, qIdx) => (
                <button
                  key={qIdx}
                  type="button"
                  className="filter-pill"
                  disabled={refining}
                  onClick={() => handleRefineByPrompt(qp)}
                >
                  {qp}
                </button>
              ))}
            </div>
          </div>

          <div className="form-grid" style={{ marginBottom: 0 }}>
            <div>
              <label className="form-label">Tiêu đề đồ họa trên Cảnh {safeIdx + 1}</label>
              <textarea
                className="textarea"
                style={{ minHeight: 68 }}
                value={spec.headline || ''}
                onChange={(e) => patchSpec(safeIdx, { headline: e.target.value })}
              />
            </div>
            <div>
              <label className="form-label">Lời đọc giọng Việt khớp hoạt ảnh</label>
              <textarea
                className="textarea"
                style={{ minHeight: 68 }}
                value={curScene.vi_text || ''}
                onChange={(e) => patchScene(safeIdx, { vi_text: e.target.value })}
              />
            </div>
          </div>

          <div
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              gap: 8,
              flexWrap: 'wrap',
              paddingTop: 10,
              borderTop: '1px solid var(--border)',
            }}
          >
            <span className="text-xs text-sub">
              Mỗi phân cảnh tự động co giãn hoạt ảnh 30fps khớp chính xác từng mili-giây giọng đọc tiếng Việt.
            </span>
            <button
              type="button"
              className="btn btn-primary"
              disabled={submitting}
              onClick={() => onRenderMp4 && onRenderMp4(scenes)}
            >
              {submitting ? <Loader2 size={15} className="spin" /> : <Play size={15} />}
              <span>Xuất Video MP4 1080p ({scenes.length} cảnh)</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
