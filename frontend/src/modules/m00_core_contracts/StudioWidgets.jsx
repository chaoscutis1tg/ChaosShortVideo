import React, { useRef, useState } from 'react';
import { Loader2, Music, RotateCcw, Square, UploadCloud, Volume2 } from 'lucide-react';
import { studioApi } from './apiClient';
import { stripLeadingEmoji } from './constants';

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
  title = 'Kéo thả tệp vào đây hoặc bấm để chọn từ thiết bị',
  hint = '',
  icon: CustomIcon = UploadCloud,
  onFilesSelected,
}) {
  const [dragging, setDragging] = useState(false);
  const inputRef = useRef(null);

  const handleDrop = (e) => {
    e.preventDefault();
    setDragging(false);
    if (disabled) return;
    const files = e.dataTransfer?.files;
    if (files && files.length > 0) {
      onFilesSelected(files);
    }
  };

  return (
    <div
      className={`media-dropzone ${dragging ? 'dragging' : ''}`}
      onClick={() => !disabled && inputRef.current?.click()}
      onDragOver={(e) => {
        e.preventDefault();
        if (!disabled) setDragging(true);
      }}
      onDragLeave={() => setDragging(false)}
      onDrop={handleDrop}
    >
      <CustomIcon
        size={26}
        strokeWidth={1.85}
        style={{ color: 'var(--brand-text)', margin: '0 auto 7px', display: 'block' }}
      />
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
        disabled={disabled}
        onChange={(e) => {
          if (e.target.files?.length) {
            onFilesSelected(e.target.files);
          }
          e.target.value = '';
        }}
      />
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

/**
 * Full-width readable Background Music Card with built-in tracks, custom MP3 upload & volume slider.
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
  const audioRef = useRef(null);

  const selectedObj = bgmPresets.find((b) => b.preset_id === bgmPresetId);
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
  };

  const togglePlayBgm = async () => {
    if (playing && audioRef.current) {
      stopPlayer();
      return;
    }
    if (!activeAudioUrl) return;
    stopPlayer();
    const player = new Audio(activeAudioUrl);
    player.volume = Math.min(1.0, Math.max(0.15, bgmVolume * 4));
    audioRef.current = player;
    player.onended = () => setPlaying(false);
    await player.play().catch(() => {});
    setPlaying(true);
  };

  const handleUploadCustomBgm = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
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

        <div style={{ display: 'flex', gap: 6 }}>
          {activeAudioUrl && (
            <button
              type="button"
              className={`btn btn-sm ${playing ? 'btn-primary' : 'btn-secondary'}`}
              onClick={togglePlayBgm}
              title="Nghe thử nhạc nền"
            >
              {playing ? (
                <>
                  <Square size={13} /> Dừng
                </>
              ) : (
                <>
                  <Music size={14} /> Nghe nhạc
                </>
              )}
            </button>
          )}

          <label
            className="btn btn-secondary btn-sm"
            style={{ cursor: 'pointer' }}
            title="Tải tệp nhạc nền .mp3 / .wav riêng từ máy tính hoặc điện thoại"
          >
            {uploadingBgm ? <Loader2 size={13} /> : <UploadCloud size={13} />} Tải nhạc riêng
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
        {bgmPresets.map((b) => (
          <option key={b.preset_id} value={b.preset_id}>
            {stripLeadingEmoji(b.display_name)}
          </option>
        ))}
      </select>

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
