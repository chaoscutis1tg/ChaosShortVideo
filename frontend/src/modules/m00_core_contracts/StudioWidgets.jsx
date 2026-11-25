import React, { useRef, useState } from 'react';
import { Loader2, Music, Square, UploadCloud, Volume2 } from 'lucide-react';
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
                <Icon size={18} strokeWidth={1.8} />
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
        size={24}
        strokeWidth={1.75}
        style={{ color: '#38bdf8', margin: '0 auto 6px', display: 'block' }}
      />
      <div style={{ fontWeight: 600, fontSize: 13.5, color: '#f3f4f6' }}>{title}</div>
      {hint && (
        <div style={{ fontSize: 12, color: '#9ca3af', marginTop: 3 }}>{hint}</div>
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

/**
 * Inline voice dropdown with clean vector preview button.
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
  notify,
}) {
  const [loading, setLoading] = useState(false);
  const [playing, setPlaying] = useState(false);
  const audioRef = useRef(null);

  const selectedVoiceObj = voices.find((v) => v.profile_id === voiceId);
  const effSpeed = voiceSpeed ?? selectedVoiceObj?.speed_rate ?? 1.04;
  const effPitch = voicePitch ?? selectedVoiceObj?.pitch_hz ?? 0.0;

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
    <div className="form-group" style={{ marginBottom: 0 }}>
      <label className="form-label">{label}</label>
      <div style={{ display: 'flex', gap: 8 }}>
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
          {voices.map((v) => (
            <option key={v.profile_id} value={v.profile_id}>
              {stripLeadingEmoji(v.display_name)}
            </option>
          ))}
        </select>
        <button
          type="button"
          className={`btn ${playing ? 'btn-primary' : 'btn-secondary'}`}
          style={{ whiteSpace: 'nowrap', padding: '0 12px' }}
          disabled={loading}
          onClick={handleTogglePreview}
          title="Nghe thử giọng đọc với tốc độ & độ trầm hiện tại"
        >
          {loading ? (
            <Loader2 size={15} />
          ) : playing ? (
            <>
              <Square size={14} /> Dừng
            </>
          ) : (
            <>
              <Volume2 size={15} /> Nghe thử
            </>
          )}
        </button>
      </div>

      {(onSpeedChange || onPitchChange) && (
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: '1fr 1fr',
            gap: 10,
            marginTop: 7,
          }}
        >
          {onSpeedChange && (
            <div>
              <div style={{ fontSize: 11.2, color: '#9ca3af', display: 'flex', justifyContent: 'space-between' }}>
                <span>Tốc độ đọc</span>
                <strong style={{ color: '#e5e7eb' }}>{Number(effSpeed).toFixed(2)}x</strong>
              </div>
              <input
                type="range"
                min="0.82"
                max="1.32"
                step="0.02"
                style={{ width: '100%' }}
                value={effSpeed}
                onChange={(e) => onSpeedChange(parseFloat(e.target.value))}
              />
            </div>
          )}
          {onPitchChange && (
            <div>
              <div style={{ fontSize: 11.2, color: '#9ca3af', display: 'flex', justifyContent: 'space-between' }}>
                <span>Độ trầm ấm</span>
                <strong style={{ color: '#e5e7eb' }}>
                  {Number(effPitch) > 0 ? `+${Number(effPitch).toFixed(1)}` : Number(effPitch).toFixed(1)}
                </strong>
              </div>
              <input
                type="range"
                min="-5.0"
                max="5.0"
                step="0.4"
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
 * Inline background music selector with clean vector preview & volume control.
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
    <div className="form-group" style={{ marginBottom: 0 }}>
      <label className="form-label">
        {label}{' '}
        {hasActiveBgm && onVolumeChange && (
          <span style={{ color: '#9ca3af', fontWeight: 400 }}>
            ({Math.round(bgmVolume * 100)}%)
          </span>
        )}
      </label>
      <div style={{ display: 'flex', gap: 6, alignItems: 'center', flexWrap: 'wrap' }}>
        <select
          className="select"
          style={{ flex: 1, minWidth: 170 }}
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

        {activeAudioUrl && (
          <button
            type="button"
            className={`btn ${playing ? 'btn-primary' : 'btn-secondary'}`}
            style={{ whiteSpace: 'nowrap', padding: '0 10px' }}
            onClick={togglePlayBgm}
            title="Nghe thử nhạc nền"
          >
            {playing ? (
              <>
                <Square size={13} /> Dừng
              </>
            ) : (
              <>
                <Music size={14} /> Nghe
              </>
            )}
          </button>
        )}

        <label
          className="btn btn-secondary"
          style={{ whiteSpace: 'nowrap', padding: '0 10px', cursor: 'pointer' }}
          title="Tải tệp nhạc nền .mp3 / .wav riêng từ máy tính hoặc điện thoại"
        >
          {uploadingBgm ? <Loader2 size={14} /> : <UploadCloud size={14} />} Nhạc riêng
          <input
            type="file"
            accept="audio/*,.mp3,.wav,.m4a,.flac"
            hidden
            disabled={uploadingBgm}
            onChange={handleUploadCustomBgm}
          />
        </label>
      </div>

      {hasActiveBgm && onVolumeChange && (
        <input
          type="range"
          min="0.02"
          max="0.22"
          step="0.01"
          style={{ width: '100%', marginTop: 6 }}
          value={bgmVolume}
          onChange={(e) => onVolumeChange(parseFloat(e.target.value))}
        />
      )}
    </div>
  );
}
