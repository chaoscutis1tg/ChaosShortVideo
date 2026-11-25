import React, { useState } from 'react';
import {
  ChevronDown,
  ChevronUp,
  Edit3,
  FileText,
  Image,
  Layers,
  Play,
  Video,
} from 'lucide-react';
import { studioApi } from '../m00_core_contracts/apiClient';
import {
  InlineBgmSelector,
  InlineVoiceSelector,
  ModeChoiceGrid,
} from '../m00_core_contracts/StudioWidgets';

const VISUAL_SOURCE_CHOICES = [
  {
    value: 'AI_IMAGE',
    title: 'Ảnh minh họa chuyển động',
    subtitle: 'Tự tạo hình theo từng câu kèm hiệu ứng thu phóng',
    icon: Image,
  },
  {
    value: 'HYBRID',
    title: 'Kết hợp Ảnh & Video cảnh quay',
    subtitle: 'Đan xen hình minh họa và video quay thực tế',
    icon: Layers,
  },
  {
    value: 'STOCK_VIDEO',
    title: 'Ưu tiên Video cảnh quay',
    subtitle: 'Tìm các đoạn video dọc miễn phí từ Pexels / Pixabay',
    icon: Video,
  },
];

export default function TopicStudioForm({
  voices,
  bgmPresets,
  layoutConfig,
  onProjectStarted,
  notify,
}) {
  const [topicTitle, setTopicTitle] = useState('');
  const [keyPoints, setKeyPoints] = useState('');
  const [visualMode, setVisualMode] = useState('AI_IMAGE');
  const [voiceId, setVoiceId] = useState(voices[0]?.profile_id || 'edge_nam_minh_movie');
  const [bgmPresetId, setBgmPresetId] = useState('bgm_lofi_story');
  const [bgmVolume, setBgmVolume] = useState(0.08);
  const [subtitleStyle, setSubtitleStyle] = useState('KARAOKE_CAPCUT');

  const [showAdvanced, setShowAdvanced] = useState(false);
  const [durationSec, setDurationSec] = useState(85);
  const [partCount, setPartCount] = useState(1);
  const [tone, setTone] = useState('Mở đầu cuốn hút trong 3 giây đầu, mạch kể rõ ràng');
  const [submitting, setSubmitting] = useState(false);

  const handleStart = async (autoOneClick) => {
    if (topicTitle.trim().length < 3) {
      notify('Vui lòng nhập chủ đề video (ít nhất 3 ký tự).');
      return;
    }
    setSubmitting(true);
    try {
      const res = await studioApi.startTopicProject({
        topic_title: topicTitle.trim(),
        key_points: keyPoints,
        visual_mode: visualMode,
        target_duration_sec: Number(durationSec),
        part_count: Number(partCount),
        narrative_tone: tone,
        voice_profile_id: voiceId,
        subtitle_style: subtitleStyle,
        bgm_preset_id: bgmPresetId,
        bgm_volume: bgmVolume,
        layout_config: layoutConfig,
        auto_one_click: autoOneClick,
      });
      onProjectStarted(res.project_id, res.state);
    } catch (err) {
      notify(`Lỗi khởi tạo: ${err.message}`);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="card">
      <div className="page-header">
        <div>
          <div className="page-title">
            <FileText size={19} strokeWidth={1.9} /> Tạo Video Mới Từ Chủ Đề & Kịch Bản
          </div>
          <div className="page-subtitle">
            Nhập tiêu đề hoặc gạch đầu dòng ý chính — hệ thống tự viết lời dẫn, tạo hình minh họa và lồng tiếng hoàn chỉnh
          </div>
        </div>
      </div>

      {/* STEP 1 */}
      <div className="step-box">
        <div className="step-header">
          <span className="step-num">1</span>
          <div>
            <div className="step-title">Chủ đề & nội dung chính</div>
            <div className="step-desc">Có thể để trống phần ý chính nếu muốn hệ thống tự biên soạn toàn bộ</div>
          </div>
        </div>

        <div className="form-group">
          <label className="form-label">Chủ đề hoặc tiêu đề câu chuyện</label>
          <input
            className="input"
            placeholder="VD: Cách chọn cây đàn Violin đầu tiên phù hợp cho người mới học..."
            value={topicTitle}
            onChange={(e) => setTopicTitle(e.target.value)}
          />
        </div>

        <div className="form-group" style={{ marginBottom: 0 }}>
          <label className="form-label">Các ý chính muốn nhắc tới (mỗi dòng một ý, tùy chọn)</label>
          <textarea
            className="textarea"
            placeholder="- Cách chọn kích cỡ đàn theo sải tay&#10;- Phân biệt gỗ thịt tự nhiên và gỗ ép&#10;- Những phụ kiện cần có..."
            value={keyPoints}
            onChange={(e) => setKeyPoints(e.target.value)}
          />
        </div>
      </div>

      {/* STEP 2 */}
      <div className="step-box">
        <div className="step-header">
          <span className="step-num">2</span>
          <div>
            <div className="step-title">Nguồn hình ảnh, giọng đọc & nhạc nền</div>
            <div className="step-desc">Chọn phong cách hình ảnh và nghe thử giọng đọc ngay tại chỗ</div>
          </div>
        </div>

        <div style={{ marginBottom: 14 }}>
          <ModeChoiceGrid
            options={VISUAL_SOURCE_CHOICES}
            value={visualMode}
            onChange={setVisualMode}
          />
        </div>

        <div className="form-grid">
          <InlineVoiceSelector
            voices={voices}
            voiceId={voiceId}
            onChange={setVoiceId}
            sampleText="Chỉ với ba lưu ý đơn giản dưới đây, bạn sẽ chọn được sản phẩm ưng ý ngay từ lần đầu tiên."
            notify={notify}
          />
          <InlineBgmSelector
            bgmPresets={bgmPresets}
            bgmPresetId={bgmPresetId}
            onSelectPreset={setBgmPresetId}
            bgmVolume={bgmVolume}
            onVolumeChange={setBgmVolume}
          />
        </div>
      </div>

      <button
        type="button"
        className="adv-toggle"
        onClick={() => setShowAdvanced((prev) => !prev)}
      >
        <span>Tùy chỉnh nâng cao (Thời lượng {durationSec}s, chia {partCount} tập, kiểu chữ phụ đề)</span>
        {showAdvanced ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
      </button>

      {showAdvanced && (
        <div className="adv-body">
          <div className="form-grid">
            <div className="form-group">
              <label className="form-label">
                Thời lượng dự kiến mỗi tập: <strong>{durationSec} giây</strong>
              </label>
              <input
                type="range"
                min="30"
                max="160"
                step="5"
                style={{ width: '100%' }}
                value={durationSec}
                onChange={(e) => setDurationSec(Number(e.target.value))}
              />
            </div>
            <div className="form-group">
              <label className="form-label">Số tập muốn chia</label>
              <input
                type="number"
                className="input"
                min={1}
                max={10}
                value={partCount}
                onChange={(e) => setPartCount(e.target.value)}
              />
            </div>
          </div>
          <div className="form-grid">
            <div className="form-group" style={{ marginBottom: 0 }}>
              <label className="form-label">Kiểu chữ phụ đề</label>
              <select
                className="select"
                value={subtitleStyle}
                onChange={(e) => setSubtitleStyle(e.target.value)}
              >
                <option value="KARAOKE_CAPCUT">Chữ chạy nổi bật từng từ</option>
                <option value="CINEMA">Phụ đề câu gọn dưới màn hình</option>
                <option value="NONE">Không hiển thị chữ phụ đề</option>
              </select>
            </div>
            <div className="form-group" style={{ marginBottom: 0 }}>
              <label className="form-label">Phong cách viết lời dẫn</label>
              <input className="input" value={tone} onChange={(e) => setTone(e.target.value)} />
            </div>
          </div>
        </div>
      )}

      <div className="btn-row">
        <button
          className="btn btn-primary"
          style={{ flex: 1, minWidth: 220, minHeight: 42 }}
          disabled={submitting}
          onClick={() => handleStart(true)}
        >
          <Play size={16} /> Bắt đầu tạo video tự động
        </button>
        <button
          className="btn btn-secondary"
          style={{ minHeight: 42 }}
          disabled={submitting}
          onClick={() => handleStart(false)}
        >
          <Edit3 size={15} /> Xem và sửa kịch bản trước
        </button>
      </div>
    </div>
  );
}
