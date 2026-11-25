import React, { useState } from 'react';
import {
  Edit3,
  FileText,
  Film,
  Languages,
  Link2,
  Mic,
  Play,
  Search,
  Subtitles,
  Upload,
  VolumeX,
} from 'lucide-react';
import { studioApi } from '../m00_core_contracts/apiClient';
import {
  InlineBgmSelector,
  InlineVoiceSelector,
  MediaDropzone,
  ModeChoiceGrid,
} from '../m00_core_contracts/StudioWidgets';

const AUDIO_SUB_CHOICES = [
  {
    value: 'VIET_DUB_AND_SUB',
    title: 'Lồng tiếng + Phụ đề Việt',
    subtitle: 'Đọc thuyết minh tiếng Việt truyền cảm và hiện chữ phụ đề',
    icon: Mic,
  },
  {
    value: 'VIET_SUB_KEEP_ORIG',
    title: 'Chỉ ghép Phụ đề Việt',
    subtitle: 'Giữ nguyên 100% âm thanh gốc của tập phim',
    icon: Subtitles,
  },
  {
    value: 'VIET_DUB_NO_SUB',
    title: 'Chỉ Lồng tiếng Việt',
    subtitle: 'Đọc thuyết minh, không chèn thêm chữ phụ đề dưới hình',
    icon: Languages,
  },
  {
    value: 'RAW_ORIGINAL',
    title: 'Chỉ cắt chia tập gốc',
    subtitle: 'Chia thành các phần dọc 9:16, giữ nguyên âm thanh gốc',
    icon: VolumeX,
  },
];

export default function MovieStudioForm({
  voices,
  bgmPresets,
  layoutConfig,
  onProjectStarted,
  notify,
}) {
  const [projectName, setProjectName] = useState('');
  const [pathOrUrl, setPathOrUrl] = useState('');
  const [sourceType, setSourceType] = useState('VIDEO_URL');
  const [localVideoPreviewUrl, setLocalVideoPreviewUrl] = useState('');
  const [probedInfo, setProbedInfo] = useState(null);
  const [probingUrl, setProbingUrl] = useState(false);

  // Step 2
  const [outputAudioSubMode, setOutputAudioSubMode] = useState('VIET_DUB_AND_SUB');
  const [voiceId, setVoiceId] = useState(
    voices.find((v) => v.profile_id === 'edge_nam_minh_movie')?.profile_id ||
      voices[0]?.profile_id ||
      'edge_nam_minh_movie'
  );
  const [voiceSpeed, setVoiceSpeed] = useState(1.08);
  const [voicePitch, setVoicePitch] = useState(-1.2);
  const [subtitleStyle, setSubtitleStyle] = useState('CINEMA');
  const [bgmPresetId, setBgmPresetId] = useState(null);
  const [customBgmPath, setCustomBgmPath] = useState(null);
  const [bgmVolume, setBgmVolume] = useState(0.06);

  // Step 3 (Visible & Clear!)
  const [sourceLang, setSourceLang] = useState('auto');
  const [externalSrtPath, setExternalSrtPath] = useState('');
  const [cutStrategy, setCutStrategy] = useState('SEQUENTIAL_PARTS');
  const [minSec, setMinSec] = useState(65);
  const [maxSec, setMaxSec] = useState(120);
  const [duckingRatio, setDuckingRatio] = useState(0.18);

  const [uploading, setUploading] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  const handleProbeUrl = async (rawVal) => {
    const candidate = (rawVal ?? pathOrUrl).trim();
    if (!candidate.includes('http://') && !candidate.includes('https://')) return;
    setSourceType('VIDEO_URL');
    setLocalVideoPreviewUrl('');
    setProbingUrl(true);
    try {
      const info = await studioApi.probeVideoUrl(candidate);
      setProbedInfo(info);
      setPathOrUrl(info.normalized_url);
      if (!projectName.trim() && info.title) {
        setProjectName(info.title.slice(0, 90));
      }
      notify(`Đã nhận diện video: ${info.title}`);
    } catch (err) {
      setProbedInfo(null);
      notify(`Kiểm tra liên kết: ${err.message}`);
    } finally {
      setProbingUrl(false);
    }
  };

  const handleFilesSelected = async (fileList) => {
    const file = fileList?.[0];
    if (!file) return;
    setUploading(true);
    try {
      const res = await studioApi.uploadStudioFile(file, 'video');
      setSourceType('LOCAL_FILE');
      setPathOrUrl(res.local_path);
      setLocalVideoPreviewUrl(res.media_url || '');
      setProbedInfo(null);
      if (!projectName.trim()) {
        setProjectName(file.name.replace(/\.[^.]+$/, ''));
      }
      notify(`Đã tải lên video: ${file.name}`);
    } catch (err) {
      notify(`Lỗi tải video: ${err.message}`);
    } finally {
      setUploading(false);
    }
  };

  const handleSrtUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    try {
      const res = await studioApi.uploadStudioFile(file, 'srt');
      setExternalSrtPath(res.local_path);
      notify(`Đã đính kèm phụ đề: ${file.name}`);
    } catch (err) {
      notify(`Lỗi tải phụ đề: ${err.message}`);
    }
  };

  const submitMovie = async (autoOneClick) => {
    if (!pathOrUrl.trim()) {
      notify('Vui lòng dán liên kết video hoặc chọn tệp video từ thiết bị.');
      return;
    }
    const cleanTitle = projectName.trim() || 'Tập Phim Mới';
    const isDubbed =
      outputAudioSubMode === 'VIET_DUB_AND_SUB' || outputAudioSubMode === 'VIET_DUB_NO_SUB';
    const effSubStyle =
      outputAudioSubMode === 'VIET_DUB_NO_SUB' || outputAudioSubMode === 'RAW_ORIGINAL'
        ? 'NONE'
        : subtitleStyle === 'NONE'
        ? 'CINEMA'
        : subtitleStyle;

    setSubmitting(true);
    try {
      const started = await studioApi.startMovieProject({
        project_name: cleanTitle,
        source_type: sourceType,
        path_or_url: pathOrUrl.trim(),
        external_srt_path: externalSrtPath || null,
        source_language: sourceLang,
        cut_config: {
          cut_strategy: cutStrategy,
          min_clip_sec: Number(minSec),
          max_clip_sec: Number(maxSec),
          max_highlights: 5,
          drama_genre: 'Phim bộ hiện đại',
          series_title: cleanTitle,
          append_cta_outro: true,
        },
        voice_profile_id: voiceId,
        bgm_preset_id: bgmPresetId,
        custom_bgm_path: customBgmPath,
        audio_config: {
          enable_narration: isDubbed,
          keep_original_audio: true,
          ducking_ratio: Number(duckingRatio),
          bgm_path: null,
          bgm_volume: Number(bgmVolume),
          subtitle_style: effSubStyle,
          subtitle_pos_y: layoutConfig.subtitle_pos_y ?? 0.84,
          subtitle_font_size: layoutConfig.subtitle_font_size ?? 52,
          voice_speed_global: Number(voiceSpeed),
          voice_pitch_global: Number(voicePitch),
        },
        layout_config: layoutConfig,
        auto_one_click: autoOneClick,
      });
      onProjectStarted(started.project_id, started.state);
    } catch (err) {
      notify(`Không thể bắt đầu: ${err.message}`);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="card">
      <div className="page-header">
        <div>
          <div className="page-title">
            <Film size={20} strokeWidth={2} /> Cắt & Dịch Video Dài Sang Khung Dọc
          </div>
          <div className="page-subtitle">
            Tự động tải video từ link hoặc máy tính, tách lời thoại bằng GPU, dịch chuẩn ngữ cảnh sang tiếng Việt và chia tập thông minh
          </div>
        </div>
        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
          <span className="badge badge-info">Độ dài cắt: {minSec}s – {maxSec}s</span>
          <span className="badge badge-ok">Tự dìm nền gốc {Math.round(duckingRatio * 100)}%</span>
        </div>
      </div>

      {/* STEP 1 */}
      <div className="step-box">
        <div className="step-header">
          <span className="step-num">1</span>
          <div>
            <div className="step-title">Nguồn video đầu vào & tên bộ phim</div>
            <div className="step-desc">
              Dán liên kết (Bilibili, YouTube, TikTok...) hoặc kéo thả tệp video có sẵn từ máy tính / điện thoại
            </div>
          </div>
        </div>

        <div className="form-group">
          <label className="form-label">Liên kết video trực tuyến</label>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            <div style={{ position: 'relative', flex: 1, minWidth: 220 }}>
              <input
                className="input"
                placeholder="Dán liên kết video (https://...) vào đây..."
                value={pathOrUrl}
                onChange={(e) => {
                  const v = e.target.value;
                  setPathOrUrl(v);
                  if (v.includes('http://') || v.includes('https://')) {
                    setSourceType('VIDEO_URL');
                  }
                }}
                onPaste={(e) => {
                  const pasted = e.clipboardData.getData('text');
                  if (pasted && (pasted.includes('http://') || pasted.includes('https://'))) {
                    setTimeout(() => handleProbeUrl(pasted), 80);
                  }
                }}
              />
            </div>
            <button
              type="button"
              className="btn btn-secondary"
              disabled={probingUrl}
              onClick={() => handleProbeUrl(pathOrUrl)}
            >
              <Search size={15} /> {probingUrl ? 'Đang kiểm tra...' : 'Kiểm tra link'}
            </button>
          </div>

          {probedInfo && (
            <div
              className="surface-box"
              style={{
                marginTop: 9,
                borderColor: 'rgba(16, 185, 129, 0.45)',
                display: 'flex',
                alignItems: 'center',
                gap: 8,
              }}
            >
              <Link2 size={16} style={{ color: 'var(--success-text)', flexShrink: 0 }} />
              <span style={{ fontSize: 13.2 }}>
                <strong>{probedInfo.title}</strong>
                {probedInfo.duration_sec > 0 &&
                  ` • Thời lượng ${Math.floor(probedInfo.duration_sec / 60)}p ${probedInfo.duration_sec % 60}s`}
              </span>
            </div>
          )}
        </div>

        <MediaDropzone
          accept="video/*"
          disabled={uploading}
          icon={Upload}
          title={
            uploading
              ? 'Đang tải tệp video lên...'
              : 'Hoặc kéo thả tệp video (.mp4, .mkv, .mov) trực tiếp từ máy tính / điện thoại'
          }
          hint="Tự động kiểm tra khung hình & tách luồng âm thanh stereo gốc"
          onFilesSelected={handleFilesSelected}
        />

        {localVideoPreviewUrl && (
          <div style={{ marginTop: 12 }}>
            <video
              controls
              src={localVideoPreviewUrl}
              style={{
                width: '100%',
                maxHeight: 220,
                borderRadius: 9,
                background: '#000',
                border: '1px solid var(--border)',
              }}
            />
          </div>
        )}

        <div className="form-group" style={{ marginTop: 13, marginBottom: 0 }}>
          <label className="form-label">Tiêu đề hiển thị trên đầu các phần video</label>
          <input
            className="input"
            placeholder="Tự động lấy theo tên video hoặc tự nhập (VD: Tổng Tài Trở Lại)"
            value={projectName}
            onChange={(e) => setProjectName(e.target.value)}
          />
        </div>
      </div>

      {/* STEP 2 */}
      <div className="step-box">
        <div className="step-header">
          <span className="step-num">2</span>
          <div>
            <div className="step-title">Hình thức lồng tiếng, chọn giọng thuyết minh & nhạc nền</div>
            <div className="step-desc">
              Chọn 1 trong 4 kiểu xuất âm thanh; nghe thử trực tiếp chất giọng trước khi bấm chạy
            </div>
          </div>
        </div>

        <div style={{ marginBottom: 14 }}>
          <ModeChoiceGrid
            options={AUDIO_SUB_CHOICES}
            value={outputAudioSubMode}
            onChange={setOutputAudioSubMode}
          />
        </div>

        <div className="form-grid">
          {(outputAudioSubMode === 'VIET_DUB_AND_SUB' ||
            outputAudioSubMode === 'VIET_DUB_NO_SUB') && (
            <InlineVoiceSelector
              voices={voices}
              voiceId={voiceId}
              onChange={setVoiceId}
              voiceSpeed={voiceSpeed}
              onSpeedChange={setVoiceSpeed}
              voicePitch={voicePitch}
              onPitchChange={setVoicePitch}
              label="Giọng đọc thuyết minh phim"
              sampleText="Không ai ngờ người đàn ông trầm lặng này lại chính là chủ tịch tập đoàn."
              notify={notify}
            />
          )}

          <InlineBgmSelector
            bgmPresets={bgmPresets}
            bgmPresetId={bgmPresetId}
            onSelectPreset={setBgmPresetId}
            bgmVolume={bgmVolume}
            onVolumeChange={setBgmVolume}
            customBgmPath={customBgmPath}
            onCustomBgmChange={setCustomBgmPath}
            notify={notify}
            label="Nhạc nền lót thêm (Tùy chọn)"
          />
        </div>
      </div>

      {/* STEP 3: CLEAR VISIBLE CUTTING & SUBTITLE SETTINGS */}
      <div className="step-box">
        <div className="step-header">
          <span className="step-num">3</span>
          <div>
            <div className="step-title">Cấu hình chia tập, ngôn ngữ gốc & phụ đề rời</div>
            <div className="step-desc">
              Hệ thống tự ngắt đúng dấu câu, không cắt cụt lời nhân vật giữa chừng
            </div>
          </div>
        </div>

        <div className="form-grid">
          <div className="form-group">
            <label className="form-label">Chiến lược chia đoạn video</label>
            <select
              className="select"
              value={cutStrategy}
              onChange={(e) => setCutStrategy(e.target.value)}
            >
              <option value="SEQUENTIAL_PARTS">Chia nối tiếp cả tập thành Phần 1, 2, 3...</option>
              <option value="VIRAL_HIGHLIGHTS">Chỉ lọc trích xuất các đoạn cao trào nhất</option>
            </select>
          </div>

          <div className="form-group">
            <label className="form-label">
              Khoảng thời lượng mỗi phần: <strong>{minSec} giây – {maxSec} giây</strong>
            </label>
            <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
              <input
                type="number"
                className="input"
                min={20}
                max={170}
                value={minSec}
                onChange={(e) => setMinSec(e.target.value)}
              />
              <span className="text-sub" style={{ fontWeight: 600 }}>
                đến
              </span>
              <input
                type="number"
                className="input"
                min={30}
                max={180}
                value={maxSec}
                onChange={(e) => setMaxSec(e.target.value)}
              />
            </div>
          </div>
        </div>

        <div className="form-grid">
          <div className="form-group">
            <label className="form-label">Ngôn ngữ gốc của phim</label>
            <select
              className="select"
              value={sourceLang}
              onChange={(e) => setSourceLang(e.target.value)}
            >
              <option value="auto">Tự động nhận diện ngôn ngữ (Khuyên dùng)</option>
              <option value="zh">Tiếng Trung</option>
              <option value="ko">Tiếng Hàn</option>
              <option value="en">Tiếng Anh</option>
              <option value="vi">Tiếng Việt (Giữ nguyên không dịch)</option>
            </select>
          </div>

          <div className="form-group">
            <label className="form-label">Kiểu chữ phụ đề tiếng Việt</label>
            <select
              className="select"
              value={subtitleStyle === 'NONE' ? 'CINEMA' : subtitleStyle}
              onChange={(e) => setSubtitleStyle(e.target.value)}
            >
              <option value="CINEMA">Phụ đề câu gọn chuẩn điện ảnh</option>
              <option value="KARAOKE_CAPCUT">Chữ chạy nổi bật từng từ</option>
            </select>
          </div>
        </div>

        <div className="form-grid">
          <div className="form-group" style={{ marginBottom: 0 }}>
            <label className="form-label">Đính kèm phụ đề rời .SRT (nếu có sẵn sẽ bỏ qua quét âm thanh)</label>
            <div style={{ display: 'flex', gap: 8 }}>
              <input
                className="input"
                placeholder="Mặc định để trống để GPU tự nghe lời thoại"
                value={externalSrtPath}
                onChange={(e) => setExternalSrtPath(e.target.value)}
              />
              <label className="btn btn-secondary" style={{ whiteSpace: 'nowrap', cursor: 'pointer' }}>
                <FileText size={14} /> Chọn .SRT
                <input type="file" accept=".srt,.vtt" hidden onChange={handleSrtUpload} />
              </label>
            </div>
          </div>

          <div className="form-group" style={{ marginBottom: 0 }}>
            <label className="form-label">
              Âm lượng tiếng phim gốc khi nhân vật thuyết minh nói: <strong>{Math.round(duckingRatio * 100)}%</strong>
            </label>
            <input
              type="range"
              min="0.05"
              max="0.50"
              step="0.02"
              style={{ width: '100%', marginTop: 10 }}
              value={duckingRatio}
              onChange={(e) => setDuckingRatio(parseFloat(e.target.value))}
            />
          </div>
        </div>
      </div>

      {/* ACTIONS */}
      <div className="btn-row">
        <button
          className="btn btn-primary"
          style={{ flex: 1, minWidth: 230, minHeight: 44, fontSize: 14.2 }}
          disabled={submitting}
          onClick={() => submitMovie(true)}
        >
          <Play size={16} /> Bắt đầu cắt & thuyết minh tự động
        </button>
        <button
          className="btn btn-secondary"
          style={{ minHeight: 44 }}
          disabled={submitting}
          onClick={() => submitMovie(false)}
        >
          <Edit3 size={15} /> Xem và chỉnh lời dịch trước khi xuất
        </button>
      </div>
    </div>
  );
}
