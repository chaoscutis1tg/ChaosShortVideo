import React, { useEffect, useRef, useState } from 'react';
import {
  AlertCircle,
  CheckCircle2,
  Download,
  FolderPlus,
  FolderTree,
  Globe,
  Loader2,
  Music,
  Play,
  Plus,
  RotateCcw,
  Search,
  Square,
  UploadCloud,
  Volume2,
  X,
} from 'lucide-react';
import { studioApi } from './apiClient';
import { stripLeadingEmoji } from './constants';

export const GROUP_COLOR_PALETTE = ['#0ea5e9', '#10b981', '#f59e0b', '#a855f7', '#ef4444'];

/**
 * Shared parameter validation helpers across all Studio forms.
 */
export function isValidHttpUrl(raw) {
  const clean = (raw || '').trim();
  if (!clean) return false;
  try {
    const parsed = new URL(clean);
    if (parsed.protocol !== 'http:' && parsed.protocol !== 'https:') return false;
    const host = parsed.hostname || '';
    return host === 'localhost' || host.includes('.');
  } catch {
    return false;
  }
}

export function isVideoOnlyPlatformUrl(raw) {
  const clean = (raw || '').trim().toLowerCase();
  if (!clean) return false;
  return (
    clean.includes('youtube.com/watch') ||
    clean.includes('youtube.com/shorts/') ||
    clean.includes('youtu.be/') ||
    clean.includes('tiktok.com/') ||
    clean.includes('vt.tiktok.com/') ||
    clean.includes('bilibili.com/video') ||
    clean.includes('douyin.com/')
  );
}

export function hasAllowedExtension(fileName, allowedExts = []) {
  if (!fileName || allowedExts.length === 0) return true;
  const lower = String(fileName).toLowerCase();
  return allowedExts.some((ext) => lower.endsWith(ext.toLowerCase()));
}

export function scrollToFirstValidationError(containerRef) {
  setTimeout(() => {
    const root = containerRef?.current || document;
    const el = root.querySelector('.input-error, .dropzone-error, .field-error-msg');
    if (el && typeof el.scrollIntoView === 'function') {
      el.scrollIntoView({ behavior: 'smooth', block: 'center' });
      if (typeof el.focus === 'function' && (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA')) {
        el.focus({ preventScroll: true });
      }
    }
  }, 40);
}

/**
 * Crisp inline field validation message rendered directly below an invalid input.
 */
export function FieldError({ message }) {
  if (!message) return null;
  return (
    <div className="field-error-msg" role="alert">
      <AlertCircle size={14} style={{ flexShrink: 0, marginTop: 1 }} />
      <span>{message}</span>
    </div>
  );
}

/**
 * Live Multi-Step Animated Loading Banner with elapsed timer & shimmer progress bar.
 */
export function StudioLoadingBanner({
  loading = false,
  title = 'Hệ thống đang xử lý dữ liệu...',
  subtitle = '',
  steps = [],
  stepIntervalMs = 2600,
  showSkeleton = false,
}) {
  const [elapsedTenths, setElapsedTenths] = useState(0);

  useEffect(() => {
    if (!loading) {
      setElapsedTenths(0);
      return undefined;
    }
    const started = Date.now();
    const timer = setInterval(() => {
      setElapsedTenths(Math.floor((Date.now() - started) / 100));
    }, 200);
    return () => clearInterval(timer);
  }, [loading]);

  if (!loading) return null;

  const elapsedMs = elapsedTenths * 100;
  const activeStepIdx =
    steps.length > 0
      ? Math.min(steps.length - 1, Math.floor(elapsedMs / Math.max(800, stepIntervalMs)))
      : 0;

  return (
    <div className="loading-stage-banner" role="status" aria-live="polite">
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          gap: 10,
          flexWrap: 'wrap',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 9, minWidth: 0 }}>
          <Loader2 size={18} className="spin" style={{ color: 'var(--brand-text)' }} />
          <div style={{ minWidth: 0 }}>
            <div style={{ fontWeight: 700, fontSize: 13.5, color: 'var(--text-primary)' }}>
              {title}
            </div>
            {subtitle && (
              <div className="text-sub" style={{ fontSize: 12.1, marginTop: 1 }}>
                {subtitle}
              </div>
            )}
          </div>
        </div>
        <span className="badge badge-info" style={{ fontVariantNumeric: 'tabular-nums' }}>
          <span className="pulse-dot" style={{ width: 6, height: 6 }} />
          {(elapsedTenths / 10).toFixed(1)}s
        </span>
      </div>

      <div className="loading-indeterminate-track">
        <div className="loading-indeterminate-bar" />
      </div>

      {steps.length > 0 && (
        <div className="loading-steps-row">
          {steps.map((stLabel, idx) => {
            const isDone = idx < activeStepIdx;
            const isAct = idx === activeStepIdx;
            return (
              <span
                key={idx}
                className={`loading-step-pill ${isAct ? 'active' : isDone ? 'done' : ''}`}
              >
                {isDone ? (
                  <CheckCircle2 size={12} />
                ) : isAct ? (
                  <Loader2 size={12} className="spin" />
                ) : (
                  <span style={{ opacity: 0.65 }}>{idx + 1}.</span>
                )}
                <span>{stLabel}</span>
              </span>
            );
          })}
        </div>
      )}

      {showSkeleton && (
        <div style={{ display: 'grid', gap: 7, marginTop: 10 }}>
          <div className="skeleton-line" style={{ width: '78%' }} />
          <div className="skeleton-line" style={{ width: '94%' }} />
          <div className="skeleton-line" style={{ width: '62%' }} />
        </div>
      )}
    </div>
  );
}

/**
 * Reusable Parent Project (Series / Campaign / Collection) selector + inline quick creator.
 */
export function ParentGroupSelector({
  projectGroups = [],
  value = '',
  onChange,
  onGroupsChanged,
  notify,
  label = 'Thuộc Dự Án Cha (Quản lý theo Series / Chiến dịch / Bộ sưu tập)',
}) {
  const [creating, setCreating] = useState(false);
  const [newName, setNewName] = useState('');
  const [newColor, setNewColor] = useState(GROUP_COLOR_PALETTE[0]);
  const [saving, setSaving] = useState(false);

  const handleQuickCreate = async () => {
    const clean = newName.trim();
    if (clean.length < 2) {
      if (notify) notify('Vui lòng nhập tên Dự Án Cha (ít nhất 2 ký tự).');
      return;
    }
    setSaving(true);
    try {
      const saved = await studioApi.saveProjectGroup({
        name: clean,
        description: '',
        color_tag: newColor,
      });
      if (onGroupsChanged) await onGroupsChanged();
      if (onChange) onChange(saved.group_id);
      setNewName('');
      setCreating(false);
      if (notify) notify(`Đã tạo Dự Án Cha "${saved.name}" và chọn cho dự án này.`);
    } catch (err) {
      if (notify) notify(`Lỗi tạo Dự Án Cha: ${err.message}`);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="surface-box" style={{ marginBottom: 13 }}>
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          gap: 8,
          flexWrap: 'wrap',
          marginBottom: 7,
        }}
      >
        <label
          className="form-label"
          style={{ marginBottom: 0, display: 'inline-flex', alignItems: 'center', gap: 6 }}
        >
          <FolderTree size={14} style={{ color: 'var(--brand-text)' }} />
          <span>{label}</span>
        </label>
        <button
          type="button"
          className="btn btn-secondary btn-sm"
          style={{ padding: '3px 10px', minHeight: 29, fontSize: 11.8 }}
          onClick={() => setCreating((p) => !p)}
        >
          {creating ? (
            <>
              <X size={12} /> Đóng
            </>
          ) : (
            <>
              <FolderPlus size={12} /> + Tạo Dự Án Cha mới
            </>
          )}
        </button>
      </div>

      {creating ? (
        <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
          <input
            className="input"
            style={{ flex: 1, minWidth: 210, minHeight: 36, padding: '6px 11px' }}
            placeholder="VD: Series Học Guitar Cơ Bản / Chiến dịch Violin Mùa Tựu Trường..."
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') {
                e.preventDefault();
                handleQuickCreate();
              }
            }}
          />
          <div style={{ display: 'inline-flex', gap: 5, alignItems: 'center' }}>
            {GROUP_COLOR_PALETTE.map((hex) => (
              <button
                key={hex}
                type="button"
                onClick={() => setNewColor(hex)}
                title="Chọn màu đánh dấu Dự Án Cha"
                style={{
                  width: 20,
                  height: 20,
                  borderRadius: 999,
                  background: hex,
                  border: newColor === hex ? '2.5px solid #ffffff' : '1px solid rgba(255,255,255,0.25)',
                  cursor: 'pointer',
                  boxShadow: newColor === hex ? `0 0 0 2px ${hex}` : 'none',
                }}
              />
            ))}
          </div>
          <button
            type="button"
            className="btn btn-primary btn-sm"
            style={{ minHeight: 36 }}
            disabled={saving}
            onClick={handleQuickCreate}
          >
            <Plus size={13} /> {saving ? 'Đang lưu...' : 'Tạo & Chọn'}
          </button>
        </div>
      ) : (
        <select
          className="select"
          style={{ minHeight: 38, padding: '7px 11px' }}
          value={value || ''}
          onChange={(e) => onChange && onChange(e.target.value)}
        >
          <option value="">-- Dự án độc lập (Không nằm trong Dự Án Cha) --</option>
          {projectGroups.map((grp) => (
            <option key={grp.group_id} value={grp.group_id}>
              Dự Án Cha: {grp.name} ({grp.project_count || 0} dự án con)
            </option>
          ))}
        </select>
      )}
    </div>
  );
}

/**
 * Clean visual card selector so users can pick modes at a glance without hunting in dropdowns.
 */
export function ModeChoiceGrid({ options, value, onChange }) {
  return (
    <div className="choice-grid">
      {options.map((opt) => {
        const Icon = opt.icon;
        const selected = value === opt.value;
        return (
          <button
            key={opt.value}
            type="button"
            className={`choice-card ${selected ? 'selected' : ''}`}
            onClick={() => onChange(opt.value)}
          >
            {Icon && (
              <span className="choice-card-icon">
                <Icon size={18} strokeWidth={1.9} />
              </span>
            )}
            <div>
              <div className="choice-card-title">{opt.title}</div>
              {opt.subtitle && <div className="choice-card-sub">{opt.subtitle}</div>}
            </div>
          </button>
        );
      })}
    </div>
  );
}

/**
 * High-clarity Toggle Switch Card replacing tiny raw checkboxes.
 */
export function SwitchCard({ checked, onChange, children, icon: Icon = null }) {
  return (
    <label className={`toggle-item ${checked ? 'active' : ''}`}>
      <input
        type="checkbox"
        checked={Boolean(checked)}
        onChange={(e) => onChange(e.target.checked)}
      />
      {Icon && <Icon size={15} style={{ flexShrink: 0, color: 'var(--brand-text)' }} />}
      <span style={{ lineHeight: 1.35 }}>{children}</span>
    </label>
  );
}

/**
 * Touch & Drag-and-Drop Multimedia Upload Zone (supports Video, Multiple Photos, Audio).
 */
export function MediaDropzone({
  accept = '*/*',
  multiple = false,
  disabled = false,
  loading = false,
  error = '',
  title = 'Kéo thả tệp vào đây hoặc bấm để chọn từ thiết bị',
  hint = '',
  icon: CustomIcon = UploadCloud,
  onFilesSelected,
}) {
  const [dragging, setDragging] = useState(false);
  const inputRef = useRef(null);
  const isBusy = Boolean(disabled || loading);

  const handleDrop = (e) => {
    e.preventDefault();
    setDragging(false);
    if (isBusy) return;
    const files = e.dataTransfer?.files;
    if (files && files.length > 0) {
      onFilesSelected(files);
    }
  };

  return (
    <div>
      <div
        className={`media-dropzone ${dragging ? 'dragging' : ''} ${
          error ? 'dropzone-error' : ''
        } ${loading ? 'dropzone-loading' : ''}`}
        onClick={() => !isBusy && inputRef.current?.click()}
        onDragOver={(e) => {
          e.preventDefault();
          if (!isBusy) setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={handleDrop}
      >
        {loading ? (
          <Loader2
            size={26}
            strokeWidth={2}
            className="spin"
            style={{ color: 'var(--brand-text)', margin: '0 auto 7px', display: 'block' }}
          />
        ) : (
          <CustomIcon
            size={26}
            strokeWidth={1.85}
            style={{
              color: error ? '#ef4444' : 'var(--brand-text)',
              margin: '0 auto 7px',
              display: 'block',
            }}
          />
        )}
        <div style={{ fontWeight: 700, fontSize: 14, color: 'var(--text-primary)' }}>{title}</div>
        {hint && (
          <div className="text-sub" style={{ fontSize: 12.5, marginTop: 4 }}>
            {hint}
          </div>
        )}
        <input
          ref={inputRef}
          type="file"
          accept={accept}
          multiple={multiple}
          hidden
          disabled={isBusy}
          onChange={(e) => {
            if (e.target.files?.length) {
              onFilesSelected(e.target.files);
            }
            e.target.value = '';
          }}
        />
      </div>
      <FieldError message={error} />
    </div>
  );
}

export const VOICE_CATEGORY_META = [
  { id: 'ALL', label: 'Tất cả', groupTitle: 'Tất cả giọng đọc' },
  { id: 'TIKTOK_SHORT', label: 'Short TikTok', groupTitle: 'Chuyên Short TikTok (Nhịp nhanh • Bắt trend)' },
  { id: 'YOUTUBE_SHORT', label: 'YouTube Shorts', groupTitle: 'Chuyên YouTube Shorts (Chiều sâu • Tri thức)' },
  { id: 'MOVIE_DUB', label: 'Thuyết minh Phim', groupTitle: 'Lồng tiếng & Thuyết minh Phim (Chiếu rạp USLT • Phim bộ)' },
  { id: 'ECOMMERCE_SALES', label: 'Bán hàng', groupTitle: 'Tư vấn Bán hàng & Showroom' },
];

/**
 * Full-width readable Voice Selector Card with Platform Category Filter Pills + Speed & Pitch sliders.
 */
export function InlineVoiceSelector({
  voices = [],
  voiceId,
  onChange,
  label = 'Giọng đọc lồng tiếng',
  sampleText = 'Một lựa chọn đáng cân nhắc với chất lượng hoàn thiện vượt trội trong tầm giá.',
  voiceSpeed = null,
  onSpeedChange = null,
  voicePitch = null,
  onPitchChange = null,
  defaultCategory = 'ALL',
  notify,
}) {
  const [loading, setLoading] = useState(false);
  const [playing, setPlaying] = useState(false);
  const [categoryFilter, setCategoryFilter] = useState(defaultCategory || 'ALL');
  const audioRef = useRef(null);

  const selectedVoiceObj = voices.find((v) => v.profile_id === voiceId);
  const effSpeed = voiceSpeed ?? selectedVoiceObj?.speed_rate ?? 1.04;
  const effPitch = voicePitch ?? selectedVoiceObj?.pitch_hz ?? 0.0;

  const filteredVoices =
    categoryFilter === 'ALL'
      ? voices
      : voices.filter((v) => (v.category || 'MOVIE_DUB') === categoryFilter);
  const effectiveVoices = filteredVoices.length > 0 ? filteredVoices : voices;

  const handleSelectCategory = (catId) => {
    setCategoryFilter(catId);
    if (catId === 'ALL') return;
    const matching = voices.filter((v) => (v.category || 'MOVIE_DUB') === catId);
    if (matching.length > 0 && !matching.some((v) => v.profile_id === voiceId)) {
      const topVoice = matching[0];
      onChange(topVoice.profile_id);
      if (onSpeedChange) onSpeedChange(topVoice.speed_rate);
      if (onPitchChange) onPitchChange(topVoice.pitch_hz);
    }
  };

  const handleTogglePreview = async () => {
    if (playing && audioRef.current) {
      audioRef.current.pause();
      audioRef.current.currentTime = 0;
      setPlaying(false);
      return;
    }
    if (!voiceId) return;
    setLoading(true);
    try {
      const res = await studioApi.previewVoice(
        voiceId,
        sampleText,
        onSpeedChange ? effSpeed : null,
        onPitchChange ? effPitch : null
      );
      if (audioRef.current) audioRef.current.pause();
      const player = new Audio(`${res.audio_url}?t=${Date.now()}`);
      audioRef.current = player;
      player.onended = () => setPlaying(false);
      player.onerror = () => setPlaying(false);
      await player.play();
      setPlaying(true);
    } catch (err) {
      if (notify) notify(`Lỗi nghe thử giọng: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="selector-card">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 8 }}>
        <label className="form-label" style={{ marginBottom: 0 }}>
          {label}
        </label>
        <button
          type="button"
          className={`btn btn-sm ${playing ? 'btn-primary' : 'btn-secondary'}`}
          disabled={loading}
          onClick={handleTogglePreview}
          title="Nghe thử giọng đọc với tốc độ & độ trầm hiện tại"
        >
          {loading ? (
            <Loader2 size={14} />
          ) : playing ? (
            <>
              <Square size={13} /> Dừng nghe
            </>
          ) : (
            <>
              <Volume2 size={14} /> Nghe thử giọng
            </>
          )}
        </button>
      </div>

      {/* Quick Platform / Purpose Filter Pills */}
      <div style={{ display: 'flex', gap: 5, flexWrap: 'wrap' }}>
        {VOICE_CATEGORY_META.map((cat) => {
          const count =
            cat.id === 'ALL'
              ? voices.length
              : voices.filter((v) => (v.category || 'MOVIE_DUB') === cat.id).length;
          const active = categoryFilter === cat.id;
          return (
            <button
              key={cat.id}
              type="button"
              onClick={() => handleSelectCategory(cat.id)}
              style={{
                padding: '4px 9px',
                fontSize: 11.5,
                fontWeight: active ? 700 : 500,
                borderRadius: 999,
                cursor: 'pointer',
                border: active ? '1px solid var(--brand)' : '1px solid var(--border)',
                background: active ? 'var(--brand-soft)' : 'transparent',
                color: active ? 'var(--brand-text)' : 'var(--text-secondary)',
                transition: 'all 0.15s ease',
              }}
            >
              {cat.label} ({count})
            </button>
          );
        })}
      </div>

      <select
        className="select"
        value={voiceId}
        onChange={(e) => {
          if (audioRef.current) {
            audioRef.current.pause();
            setPlaying(false);
          }
          const nextId = e.target.value;
          onChange(nextId);
          const found = voices.find((x) => x.profile_id === nextId);
          if (found && onSpeedChange) onSpeedChange(found.speed_rate);
          if (found && onPitchChange) onPitchChange(found.pitch_hz);
        }}
      >
        {categoryFilter === 'ALL'
          ? VOICE_CATEGORY_META.filter((c) => c.id !== 'ALL').map((cat) => {
              const items = voices.filter((v) => (v.category || 'MOVIE_DUB') === cat.id);
              if (items.length === 0) return null;
              return (
                <optgroup key={cat.id} label={cat.groupTitle}>
                  {items.map((v) => (
                    <option key={v.profile_id} value={v.profile_id}>
                      {stripLeadingEmoji(v.display_name)}
                    </option>
                  ))}
                </optgroup>
              );
            })
          : effectiveVoices.map((v) => (
              <option key={v.profile_id} value={v.profile_id}>
                {stripLeadingEmoji(v.display_name)}
              </option>
            ))}
      </select>

      {selectedVoiceObj && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
          {Array.isArray(selectedVoiceObj.tags) && selectedVoiceObj.tags.length > 0 && (
            <div style={{ display: 'flex', gap: 5, flexWrap: 'wrap' }}>
              {selectedVoiceObj.tags.map((tg, i) => (
                <span key={i} className="badge badge-info" style={{ fontSize: 10.6, padding: '2px 7px' }}>
                  {tg}
                </span>
              ))}
            </div>
          )}
          {selectedVoiceObj.emotion_prompt && (
            <div className="text-muted" style={{ fontSize: 11.8, lineHeight: 1.35 }}>
              Phong cách: {selectedVoiceObj.emotion_prompt}
            </div>
          )}
        </div>
      )}

      {(onSpeedChange || onPitchChange) && (
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: '1fr 1fr',
            gap: 12,
            paddingTop: 4,
            borderTop: '1px solid var(--border)',
          }}
        >
          {onSpeedChange && (
            <div>
              <div
                className="text-sub"
                style={{ fontSize: 11.8, display: 'flex', justifyContent: 'space-between', marginBottom: 2 }}
              >
                <span>Tốc độ đọc</span>
                <strong>{Number(effSpeed).toFixed(2)}x</strong>
              </div>
              <input
                type="range"
                min="0.80"
                max="1.35"
                step="0.02"
                style={{ width: '100%' }}
                value={effSpeed}
                onChange={(e) => onSpeedChange(parseFloat(e.target.value))}
              />
            </div>
          )}

          {onPitchChange && (
            <div>
              <div
                className="text-sub"
                style={{ fontSize: 11.8, display: 'flex', justifyContent: 'space-between', marginBottom: 2 }}
              >
                <span>Độ trầm ấm</span>
                <span style={{ display: 'inline-flex', alignItems: 'center', gap: 5 }}>
                  <strong>
                    {Number(effPitch) > 0 ? `+${Number(effPitch).toFixed(1)}` : Number(effPitch).toFixed(1)}
                  </strong>
                  {selectedVoiceObj &&
                    (Math.abs(effSpeed - selectedVoiceObj.speed_rate) > 0.01 ||
                      Math.abs(effPitch - selectedVoiceObj.pitch_hz) > 0.1) && (
                      <button
                        type="button"
                        onClick={() => {
                          if (onSpeedChange) onSpeedChange(selectedVoiceObj.speed_rate);
                          if (onPitchChange) onPitchChange(selectedVoiceObj.pitch_hz);
                        }}
                        title="Khôi phục mặc định giọng này"
                        style={{
                          border: 'none',
                          background: 'transparent',
                          color: 'var(--brand-text)',
                          cursor: 'pointer',
                          padding: 0,
                          display: 'inline-flex',
                        }}
                      >
                        <RotateCcw size={11} />
                      </button>
                    )}
                </span>
              </div>
              <input
                type="range"
                min="-6.0"
                max="6.0"
                step="0.2"
                style={{ width: '100%' }}
                value={effPitch}
                onChange={(e) => onPitchChange(parseFloat(e.target.value))}
              />
            </div>
          )}
        </div>
      )}
    </div>
  );
}

const ONLINE_LOFI_QUICK_TAGS = [
  'lofi chill',
  'lofi piano',
  'lofi guitar',
  'chillhop',
  'lofi jazz',
];

/**
 * Full-width readable Background Music Card with 10+ CC0 Online Lofi tracks, live Online CC0 Search, custom MP3 upload & volume slider.
 */
export function InlineBgmSelector({
  bgmPresets = [],
  bgmPresetId,
  onSelectPreset,
  bgmVolume = 0.06,
  onVolumeChange,
  customBgmPath = null,
  onCustomBgmChange = null,
  notify = null,
  label = 'Nhạc nền không bản quyền',
}) {
  const [playing, setPlaying] = useState(false);
  const [uploadingBgm, setUploadingBgm] = useState(false);
  const [customBgmMeta, setCustomBgmMeta] = useState(null);
  const [extraPresets, setExtraPresets] = useState([]);
  const [showOnlineFinder, setShowOnlineFinder] = useState(false);
  const [onlineQuery, setOnlineQuery] = useState('lofi chill');
  const [searchingOnline, setSearchingOnline] = useState(false);
  const [onlineResults, setOnlineResults] = useState([]);
  const [previewOnlineUrl, setPreviewOnlineUrl] = useState('');
  const [importingUrl, setImportingUrl] = useState('');
  const audioRef = useRef(null);

  const mergedPresets = [
    ...extraPresets.filter((ep) => !bgmPresets.some((bp) => bp.preset_id === ep.preset_id)),
    ...bgmPresets,
  ];
  const lofiGroup = mergedPresets.filter((b) => b.mood_category === 'LOFI');
  const acousticGroup = mergedPresets.filter((b) => b.mood_category !== 'LOFI');

  const selectedObj = mergedPresets.find((b) => b.preset_id === bgmPresetId);
  const effectiveCustomPath = customBgmPath ?? customBgmMeta?.local_path ?? null;
  const activeAudioUrl = effectiveCustomPath
    ? customBgmMeta?.media_url || ''
    : selectedObj?.audio_url || '';
  const hasActiveBgm = Boolean(effectiveCustomPath || (bgmPresetId && bgmPresetId !== 'NONE'));

  const stopPlayer = () => {
    if (audioRef.current) {
      audioRef.current.pause();
      setPlaying(false);
    }
    setPreviewOnlineUrl('');
  };

  const togglePlayBgm = async () => {
    if (playing && !previewOnlineUrl && audioRef.current) {
      stopPlayer();
      return;
    }
    if (!activeAudioUrl) return;
    stopPlayer();
    const player = new Audio(activeAudioUrl);
    player.volume = Math.min(1.0, Math.max(0.2, bgmVolume * 4.5));
    audioRef.current = player;
    player.onended = () => setPlaying(false);
    await player.play().catch(() => {});
    setPlaying(true);
  };

  const handleToggleOnlinePreview = async (url) => {
    if (previewOnlineUrl === url && audioRef.current) {
      stopPlayer();
      return;
    }
    stopPlayer();
    const player = new Audio(url);
    player.volume = 0.55;
    audioRef.current = player;
    player.onended = () => setPreviewOnlineUrl('');
    player.onerror = () => setPreviewOnlineUrl('');
    await player.play().catch(() => {});
    setPreviewOnlineUrl(url);
  };

  const handleSearchOnlineLofi = async (qOverride = null) => {
    const effQ = (qOverride ?? onlineQuery).trim() || 'lofi chill';
    if (qOverride !== null) setOnlineQuery(effQ);
    setSearchingOnline(true);
    try {
      const list = await studioApi.searchOnlineBgm(effQ);
      setOnlineResults(list || []);
      if ((!list || list.length === 0) && notify) {
        notify('Không tìm thấy bản nhạc phù hợp — hãy thử từ khóa khác như lofi piano, chillhop...');
      }
    } catch (err) {
      if (notify) notify(`Lỗi tìm nhạc Lofi online: ${err.message}`);
    } finally {
      setSearchingOnline(false);
    }
  };

  const handleImportOnlineTrack = async (track) => {
    stopPlayer();
    setImportingUrl(track.audio_url);
    try {
      const saved = await studioApi.importOnlineBgm({
        title: track.title,
        audio_url: track.audio_url,
        creator: track.creator || '',
      });
      setExtraPresets((prev) => [saved, ...prev]);
      setCustomBgmMeta(null);
      if (onCustomBgmChange) onCustomBgmChange(null);
      if (onSelectPreset) onSelectPreset(saved.preset_id);
      setShowOnlineFinder(false);
      if (notify) {
        notify(`Đã tải & thêm "${saved.display_name}" vào Kho Nhạc Nền không bản quyền!`);
      }
    } catch (err) {
      if (notify) notify(`Lỗi tải nhạc Lofi về kho: ${err.message}`);
    } finally {
      setImportingUrl('');
    }
  };

  const handleUploadCustomBgm = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    if (!hasAllowedExtension(file.name, ['.mp3', '.wav', '.m4a', '.flac', '.ogg', '.aac'])) {
      if (notify) {
        notify('Vui lòng chọn tệp âm thanh nhạc nền hợp lệ (.mp3, .wav, .m4a, .flac, .ogg).');
      }
      e.target.value = '';
      return;
    }
    if (file.size > 150 * 1024 * 1024) {
      if (notify) notify('Tệp nhạc nền quá lớn (tối đa 150MB).');
      e.target.value = '';
      return;
    }
    stopPlayer();
    setUploadingBgm(true);
    try {
      const res = await studioApi.uploadStudioFile(file, 'bgm');
      setCustomBgmMeta(res);
      if (onCustomBgmChange) onCustomBgmChange(res.local_path);
      if (notify) notify(`Đã chọn nhạc nền riêng: ${res.original_name}`);
    } catch (err) {
      if (notify) notify(`Lỗi tải nhạc nền: ${err.message}`);
    } finally {
      setUploadingBgm(false);
      e.target.value = '';
    }
  };

  const selectValue = effectiveCustomPath ? '__CUSTOM_UPLOAD__' : bgmPresetId || 'NONE';

  return (
    <div className="selector-card">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
        <label className="form-label" style={{ marginBottom: 0 }}>
          {label}
        </label>

        <div style={{ display: 'flex', gap: 5, flexWrap: 'wrap' }}>
          {activeAudioUrl && (
            <button
              type="button"
              className={`btn btn-sm ${playing && !previewOnlineUrl ? 'btn-primary' : 'btn-secondary'}`}
              onClick={togglePlayBgm}
              title="Nghe thử bản nhạc nền đang chọn"
            >
              {playing && !previewOnlineUrl ? (
                <>
                  <Square size={13} /> Dừng
                </>
              ) : (
                <>
                  <Music size={14} /> Nghe thử
                </>
              )}
            </button>
          )}

          <button
            type="button"
            className={`btn btn-sm ${showOnlineFinder ? 'btn-primary' : 'btn-secondary'}`}
            onClick={() => {
              const nextOpen = !showOnlineFinder;
              setShowOnlineFinder(nextOpen);
              if (nextOpen && onlineResults.length === 0 && !searchingOnline) {
                handleSearchOnlineLofi('lofi chill');
              }
            }}
            title="Tìm & tải thêm nhạc Lofi CC0 1.0 hoàn toàn miễn bản quyền từ trên mạng"
          >
            <Globe size={13} /> + Kho Lofi Online (CC0)
          </button>

          <label
            className="btn btn-secondary btn-sm"
            style={{ cursor: 'pointer' }}
            title="Tải tệp nhạc nền .mp3 / .wav riêng từ máy tính hoặc điện thoại"
          >
            {uploadingBgm ? <Loader2 size={13} className="spin" /> : <UploadCloud size={13} />} Tải tệp
            <input
              type="file"
              accept="audio/*,.mp3,.wav,.m4a,.flac"
              hidden
              disabled={uploadingBgm}
              onChange={handleUploadCustomBgm}
            />
          </label>
        </div>
      </div>

      <select
        className="select"
        value={selectValue}
        onChange={(e) => {
          stopPlayer();
          const v = e.target.value;
          if (v === '__CUSTOM_UPLOAD__') return;
          setCustomBgmMeta(null);
          if (onCustomBgmChange) onCustomBgmChange(null);
          onSelectPreset(v === 'NONE' ? null : v);
        }}
      >
        <option value="NONE">Không chèn nhạc nền</option>
        {effectiveCustomPath && (
          <option value="__CUSTOM_UPLOAD__">
            Nhạc riêng: {customBgmMeta?.original_name || 'Tệp nhạc đã tải lên'}
          </option>
        )}
        {lofiGroup.length > 0 && (
          <optgroup label={`Nhạc Lofi & Chillhop Không Bản Quyền (${lofiGroup.length} bản CC0)`}>
            {lofiGroup.map((b) => (
              <option key={b.preset_id} value={b.preset_id}>
                {stripLeadingEmoji(b.display_name)}
              </option>
            ))}
          </optgroup>
        )}
        {acousticGroup.length > 0 && (
          <optgroup label="Hòa Tấu Đàn Acoustic, Violin & Điện Ảnh">
            {acousticGroup.map((b) => (
              <option key={b.preset_id} value={b.preset_id}>
                {stripLeadingEmoji(b.display_name)}
              </option>
            ))}
          </optgroup>
        )}
      </select>

      {selectedObj && !effectiveCustomPath && (
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            gap: 6,
            flexWrap: 'wrap',
          }}
        >
          <span className="text-muted" style={{ fontSize: 11.6, lineHeight: 1.35, flex: 1 }}>
            {selectedObj.description}
          </span>
          {selectedObj.mood_category === 'LOFI' && (
            <span className="badge badge-ok" style={{ fontSize: 10.2, padding: '1px 7px' }}>
              CC0 Sạch Bản Quyền
            </span>
          )}
        </div>
      )}

      {/* INLINE ONLINE CC0 LOFI FINDER & 1-CLICK IMPORTER */}
      {showOnlineFinder && (
        <div
          className="surface-box fade-slide-in"
          style={{
            padding: '10px 11px',
            borderColor: 'var(--brand)',
            background: 'var(--bg-step)',
          }}
        >
          <div
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              gap: 6,
              marginBottom: 7,
            }}
          >
            <strong style={{ fontSize: 12.4, color: 'var(--brand-text)' }}>
              Kho Nhạc Lofi Trực Tuyến Chuẩn CC0 1.0 (Đăng TikTok / YouTube Shorts 100% không dính bản quyền)
            </strong>
            <button
              type="button"
              className="btn btn-secondary btn-sm"
              style={{ padding: '2px 7px', minHeight: 24 }}
              onClick={() => {
                stopPlayer();
                setShowOnlineFinder(false);
              }}
            >
              <X size={12} />
            </button>
          </div>

          <div style={{ display: 'flex', gap: 5, flexWrap: 'wrap', marginBottom: 7 }}>
            {ONLINE_LOFI_QUICK_TAGS.map((tg) => (
              <button
                key={tg}
                type="button"
                className={`btn btn-sm ${onlineQuery === tg ? 'btn-primary' : 'btn-secondary'}`}
                style={{ padding: '2px 8px', minHeight: 25, fontSize: 11.2 }}
                disabled={searchingOnline}
                onClick={() => handleSearchOnlineLofi(tg)}
              >
                {tg}
              </button>
            ))}
          </div>

          <div style={{ display: 'flex', gap: 6, marginBottom: 8 }}>
            <input
              className="input"
              style={{ flex: 1, minHeight: 33, padding: '4px 9px', fontSize: 12.4 }}
              placeholder="Tìm thêm chủ đề nhạc CC0 (VD: lofi night, chill beat, piano...)"
              value={onlineQuery}
              onChange={(e) => setOnlineQuery(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') {
                  e.preventDefault();
                  handleSearchOnlineLofi();
                }
              }}
            />
            <button
              type="button"
              className="btn btn-primary btn-sm"
              style={{ minHeight: 33 }}
              disabled={searchingOnline}
              onClick={() => handleSearchOnlineLofi()}
            >
              {searchingOnline ? <Loader2 size={13} className="spin" /> : <Search size={13} />} Tìm
            </button>
          </div>

          {searchingOnline ? (
            <div className="text-sub" style={{ fontSize: 12, display: 'flex', alignItems: 'center', gap: 7, padding: '6px 2px' }}>
              <Loader2 size={14} className="spin" /> Đang tìm các bản Lofi CC0 miễn bản quyền trên mạng...
            </div>
          ) : (
            <div style={{ display: 'grid', gap: 6, maxHeight: 195, overflowY: 'auto', paddingRight: 2 }}>
              {onlineResults.map((tr, idx) => {
                const isPrev = previewOnlineUrl === tr.preview_url;
                const isImp = importingUrl === tr.audio_url;
                return (
                  <div
                    key={`${tr.audio_url}_${idx}`}
                    style={{
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                      gap: 8,
                      padding: '6px 8px',
                      borderRadius: 7,
                      background: 'var(--bg-panel)',
                      border: '1px solid var(--border)',
                    }}
                  >
                    <div style={{ minWidth: 0, flex: 1 }}>
                      <div
                        style={{
                          fontSize: 12.3,
                          fontWeight: 700,
                          whiteSpace: 'nowrap',
                          overflow: 'hidden',
                          textOverflow: 'ellipsis',
                        }}
                        title={tr.title}
                      >
                        {tr.title}
                      </div>
                      <div className="text-muted" style={{ fontSize: 11 }}>
                        {tr.creator} • {tr.duration_sec}s • CC0 Public Domain
                      </div>
                    </div>
                    <div style={{ display: 'flex', gap: 5, flexShrink: 0 }}>
                      <button
                        type="button"
                        className={`btn btn-sm ${isPrev ? 'btn-primary' : 'btn-secondary'}`}
                        style={{ padding: '2px 8px', minHeight: 27, fontSize: 11.2 }}
                        onClick={() => handleToggleOnlinePreview(tr.preview_url)}
                      >
                        {isPrev ? <Square size={11} /> : <Play size={11} />}{' '}
                        {isPrev ? 'Dừng' : 'Nghe'}
                      </button>
                      <button
                        type="button"
                        className="btn btn-primary btn-sm"
                        style={{ padding: '2px 8px', minHeight: 27, fontSize: 11.2 }}
                        disabled={Boolean(importingUrl)}
                        onClick={() => handleImportOnlineTrack(tr)}
                      >
                        {isImp ? <Loader2 size={11} className="spin" /> : <Download size={11} />}{' '}
                        {isImp ? 'Đang lưu...' : 'Lưu & Chọn'}
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}

      {hasActiveBgm && onVolumeChange && (
        <div style={{ paddingTop: 4, borderTop: '1px solid var(--border)' }}>
          <div
            className="text-sub"
            style={{ fontSize: 11.8, display: 'flex', justifyContent: 'space-between', marginBottom: 2 }}
          >
            <span>Âm lượng nhạc nền lót dưới giọng đọc</span>
            <strong>{Math.round(bgmVolume * 100)}%</strong>
          </div>
          <input
            type="range"
            min="0.02"
            max="0.22"
            step="0.01"
            style={{ width: '100%' }}
            value={bgmVolume}
            onChange={(e) => onVolumeChange(parseFloat(e.target.value))}
          />
        </div>
      )}
    </div>
  );
}
