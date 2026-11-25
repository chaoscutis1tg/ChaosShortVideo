import React, { useState } from 'react';
import {
  ChevronDown,
  ChevronUp,
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
    subtitle: 'Đọc thuyết minh tiếng Việt và hiện chữ phụ đề',
    icon: Mic,
  },
  {
    value: 'VIET_SUB_KEEP_ORIG',
    title: 'Chỉ ghép Phụ đề Việt',
    subtitle: 'Giữ nguyên 100% âm thanh gốc của video',
    icon: Subtitles,
  },
  {
    value: 'VIET_DUB_NO_SUB',
    title: 'Chỉ Lồng tiếng Việt',
    subtitle: 'Đọc thuyết minh, không chèn thêm chữ phụ đề',
    icon: Languages,
  },
  {
    value: 'RAW_ORIGINAL',
    title: 'Giữ nguyên gốc',
    subtitle: 'Chỉ cắt chia tập dọc 9:16, không dịch',
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
  const [voiceId, setVoiceId] = useState(voices[0]?.profile_id || 'edge_nam_minh_movie');
  const [subtitleStyle, setSubtitleStyle] = useState('CINEMA');
  const [bgmPresetId, setBgmPresetId] = useState(null);
  const [bgmVolume, setBgmVolume] = useState(0.06);

  // Advanced
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [sourceLang, setSourceLang] = useState('auto');
  const [externalSrtPath, setExternalSrtPath] = useState('');
  const [cutStrategy, setCutStrategy] = useState('SEQUENTIAL_PARTS');
  const [minSec, setMinSec] = useState(65);
  const [maxSec, setMaxSec] = useState(120);
  const [maxHighlights, setMaxHighlights] = useState(5);
  const [dramaGenre, setDramaGenre] = useState('Phim bộ hiện đại');
  const [appendCta, setAppendCta] = useState(true);
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
          max_highlights: Number(maxHighlights),
          drama_genre: dramaGenre,
          series_title: cleanTitle,
          append_cta_outro: appendCta,
        },
        voice_profile_id: voiceId,
        bgm_preset_id: bgmPresetId,
        audio_config: {
          enable_narration: isDubbed,
          keep_original_audio: true,
          ducking_ratio: Number(duckingRatio),
          bgm_path: null,
          bgm_volume: Number(bgmVolume),
          subtitle_style: effSubStyle,
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
            <Film size={19} strokeWidth={1.9} /> Cắt & Dịch Video Dài Sang Khung Dọc 9:16
          </div>
          <div className="page-subtitle">
            Tự động tải từ liên kết hoặc tệp máy tính, nhận diện giọng nói, dịch sang tiếng Việt và chia thành các phần ngắn
          </div>
        </div>
      </div>

      {/* STEP 1 */}
      <div className="step-box">
        <div className="step-header">
          <span className="step-num">1</span>
          <div>
            <div className="step-title">Chọn nguồn video</div>
            <div className="step-desc">
              Dán liên kết (Bilibili, YouTube, TikTok...) hoặc kéo thả tệp video có sẵn từ thiết bị
            </div>
          </div>
        </div>

        <div className="form-group">
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
              style={{
                marginTop: 8,
                padding: '9px 12px',
                borderRadius: 8,
                background: 'rgba(16, 185, 129, 0.1)',
                border: '1px solid rgba(16, 185, 129, 0.35)',
                fontSize: 12.8,
                color: '#d1fae5',
                display: 'flex',
                alignItems: 'center',
                gap: 8,
              }}
            >
              <Link2 size={15} />
              <span>
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
          title={uploading ? 'Đang tải tệp video lên...' : 'Hoặc kéo thả tệp video (.mp4, .mkv, .mov) vào đây'}
          hint="Tương thích cả máy tính và thư viện video trên điện thoại"
          onFilesSelected={handleFilesSelected}
        />

        {localVideoPreviewUrl && (
          <div style={{ marginTop: 10 }}>
            <video
              controls
              src={localVideoPreviewUrl}
              style={{
                width: '100%',
                maxHeight: 210,
                borderRadius: 8,
                background: '#000',
                border: '1px solid var(--border)',
              }}
            />
          </div>
        )}

        <div className="form-group" style={{ marginTop: 12, marginBottom: 0 }}>
          <label className="form-label">Tiêu đề hiển thị trên đầu video</label>
          <input
            className="input"
            placeholder="Tự động lấy theo tên video hoặc tự nhập (VD: Tập Phim Đặc Sắc)"
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
            <div className="step-title">Chọn kiểu lồng tiếng & phụ đề</div>
            <div className="step-desc">Chọn 1 trong 4 hình thức xuất âm thanh dưới đây</div>
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
          />
        </div>
      </div>

      {/* ADVANCED */}
      <button
        type="button"
        className="adv-toggle"
        onClick={() => setShowAdvanced((prev) => !prev)}
      >
        <span>
          Tùy chỉnh nâng cao (Độ dài mỗi phần {minSec}–{maxSec}s, ngôn ngữ gốc, kiểu chữ phụ đề, phụ đề rời .SRT)
        </span>
        {showAdvanced ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
      </button>

      {showAdvanced && (
        <div className="adv-body">
          <div className="form-grid">
            <div className="form-group">
              <label className="form-label">Cách chia đoạn video</label>
              <select
                className="select"
                value={cutStrategy}
                onChange={(e) => setCutStrategy(e.target.value)}
              >
                <option value="SEQUENTIAL_PARTS">Chia nối tiếp thành Phần 1, 2, 3...</option>
                <option value="VIRAL_HIGHLIGHTS">Chỉ trích xuất các đoạn cao trào nhất</option>
              </select>
            </div>

            <div className="form-group">
              <label className="form-label">
                Độ dài mỗi phần (giây): <strong>{minSec}s – {maxSec}s</strong>
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
                <span>đến</span>
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
              <label className="form-label">Ngôn ngữ gốc của video</label>
              <select
                className="select"
                value={sourceLang}
                onChange={(e) => setSourceLang(e.target.value)}
              >
                <option value="auto">Tự động nhận diện</option>
                <option value="zh">Tiếng Trung</option>
                <option value="vi">Tiếng Việt (Không dịch)</option>
                <option value="ko">Tiếng Hàn</option>
                <option value="en">Tiếng Anh</option>
              </select>
            </div>

            <div className="form-group">
              <label className="form-label">Kiểu hiển thị chữ phụ đề</label>
              <select
                className="select"
                value={subtitleStyle === 'NONE' ? 'CINEMA' : subtitleStyle}
                onChange={(e) => setSubtitleStyle(e.target.value)}
              >
                <option value="CINEMA">Phụ đề gọn chuẩn điện ảnh</option>
                <option value="KARAOKE_CAPCUT">Chữ chạy nổi bật từng từ</option>
              </select>
            </div>
          </div>

          <div className="form-grid">
            <div className="form-group" style={{ marginBottom: 0 }}>
              <label className="form-label">Đính kèm tệp phụ đề rời (.srt)</label>
              <div style={{ display: 'flex', gap: 8 }}>
                <input
                  className="input"
                  placeholder="Để trống để hệ thống tự nghe lời thoại"
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
                Âm lượng tiếng gốc khi có thuyết minh: <strong>{Math.round(duckingRatio * 100)}%</strong>
              </label>
              <input
                type="range"
                min="0.05"
                max="0.50"
                step="0.02"
                style={{ width: '100%', marginTop: 8 }}
                value={duckingRatio}
                onChange={(e) => setDuckingRatio(parseFloat(e.target.value))}
              />
            </div>
          </div>
        </div>
      )}

      {/* ACTIONS */}
      <div className="btn-row">
        <button
          className="btn btn-primary"
          style={{ flex: 1, minWidth: 220, minHeight: 42 }}
          disabled={submitting}
          onClick={() => submitMovie(true)}
        >
          <Play size={16} /> Bắt đầu tạo video tự động
        </button>
        <button
          className="btn btn-secondary"
          style={{ minHeight: 42 }}
          disabled={submitting}
          onClick={() => submitMovie(false)}
        >
          <Edit3 size={15} /> Xem và chỉnh lời dịch trước khi xuất
        </button>
      </div>
    </div>
  );
}
