import React, { useState } from 'react';
import {
  Edit3,
  FileText,
  Image,
  Layers,
  Play,
  Sparkles,
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
    title: 'Ảnh minh họa chuyển động mượt',
    subtitle: 'Tự tạo hình theo từng câu kèm chuyển cảnh CapCut êm ái',
    icon: Image,
  },
  {
    value: 'HYBRID',
    title: 'Kết hợp Ảnh & Video cảnh quay',
    subtitle: 'Đan xen hình minh họa và cảnh quay thực tế sinh động',
    icon: Layers,
  },
  {
    value: 'STOCK_VIDEO',
    title: 'Ưu tiên Video cảnh quay thực',
    subtitle: 'Tìm các đoạn video dọc miễn phí từ kho Pexels / Pixabay',
    icon: Video,
  },
];

const QUICK_TOPICS = [
  {
    title: 'Cách chọn cây đàn Violin đầu tiên chuẩn âm cho người mới học',
    points: '- Phân biệt mặt đàn gỗ thịt tự nhiên và gỗ ép công nghiệp\n- Cách đo sải tay chọn size đàn phù hợp\n- Bộ phụ kiện thiết yếu cần kiểm tra khi nhận đàn',
  },
  {
    title: '3 mẹo bảo quản đàn gỗ tự nhiên luôn bền đẹp trong khí hậu ẩm',
    points: '- Giữ độ ẩm hộp đàn ổn định\n- Vệ sinh bụi nhựa thông trên mặt đàn và dây sau khi tập\n- Nới vừa phải lông vĩ kéo khi cất đàn',
  },
  {
    title: 'Bí quyết phối đồ thanh lịch tôn dáng cho ngày đi làm bận rộn',
    points: '- Chọn phom áo đứng dáng ít nhăn\n- Phối tông màu trung tính sang trọng\n- Điểm nhấn phụ kiện tinh tế',
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
  const [voiceId, setVoiceId] = useState(
    voices.find((v) => v.profile_id === 'edge_hoai_my_fast')?.profile_id ||
      voices.find((v) => v.profile_id === 'gemini_yt_orus')?.profile_id ||
      voices[0]?.profile_id ||
      'edge_hoai_my_fast'
  );
  const [voiceSpeed, setVoiceSpeed] = useState(1.15);
  const [voicePitch, setVoicePitch] = useState(0.4);
  const [bgmPresetId, setBgmPresetId] = useState('bgm_lofi_story');
  const [customBgmPath, setCustomBgmPath] = useState(null);
  const [bgmVolume, setBgmVolume] = useState(0.08);
  const [subtitleStyle, setSubtitleStyle] = useState('KARAOKE_CAPCUT');
  const [durationSec, setDurationSec] = useState(75);
  const [partCount, setPartCount] = useState(1);
  const [tone, setTone] = useState('Mở đầu cuốn hút trong 3 giây đầu, giọng kể tự nhiên sâu sắc');
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
        custom_bgm_path: customBgmPath,
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
            <FileText size={20} strokeWidth={2} /> Tạo Video Mới Từ Chủ Đề & Kiến Thức Chia Sẻ
          </div>
          <div className="page-subtitle">
            Nhập tiêu đề hoặc chọn nhanh gợi ý bên dưới — hệ thống tự biên soạn kịch bản, tạo hình minh họa và lồng tiếng hoàn chỉnh
          </div>
        </div>
        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
          <span className="badge badge-info">Thời lượng: ~{durationSec}s</span>
          <span className="badge">{partCount} tập</span>
        </div>
      </div>

      {/* QUICK STARTER CHIPS */}
      <div className="summary-bar">
        <span style={{ fontSize: 12.5, fontWeight: 700, display: 'inline-flex', alignItems: 'center', gap: 5 }}>
          <Sparkles size={14} style={{ color: 'var(--brand-text)' }} /> Điền nhanh chủ đề mẫu:
        </span>
        {QUICK_TOPICS.map((qt, idx) => (
          <button
            key={idx}
            type="button"
            className="btn btn-secondary btn-sm"
            onClick={() => {
              setTopicTitle(qt.title);
              setKeyPoints(qt.points);
            }}
          >
            Mẫu {idx + 1}: {qt.title.slice(0, 34)}...
          </button>
        ))}
      </div>

      {/* STEP 1 */}
      <div className="step-box">
        <div className="step-header">
          <span className="step-num">1</span>
          <div>
            <div className="step-title">Chủ đề câu chuyện & các ý chính</div>
            <div className="step-desc">
              Bạn có thể để trống phần ý chính nếu muốn AI tự triển khai trọn vẹn nội dung từ tiêu đề
            </div>
          </div>
        </div>

        <div className="form-group">
          <label className="form-label">Chủ đề hoặc tiêu đề video</label>
          <input
            className="input"
            placeholder="VD: Cách chọn cây đàn Violin đầu tiên phù hợp cho người mới học..."
            value={topicTitle}
            onChange={(e) => setTopicTitle(e.target.value)}
          />
        </div>

        <div className="form-group" style={{ marginBottom: 0 }}>
          <label className="form-label">Các ý chính muốn nhấn mạnh (mỗi dòng một ý, tùy chọn)</label>
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
            <div className="step-title">Nguồn hình ảnh minh họa, giọng đọc & nhạc nền</div>
            <div className="step-desc">
              Hiển thị đầy đủ tên giọng đọc, hỗ trợ tinh chỉnh tốc độ/độ trầm và nghe thử trực tiếp
            </div>
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
            voiceSpeed={voiceSpeed}
            onSpeedChange={setVoiceSpeed}
            voicePitch={voicePitch}
            onPitchChange={setVoicePitch}
            defaultCategory="TIKTOK_SHORT"
            label="Giọng đọc dẫn chuyện (Short TikTok / YouTube Shorts / Phim)"
            sampleText="Chỉ với ba lưu ý đơn giản dưới đây, bạn sẽ chọn được cây đàn ưng ý ngay từ lần đầu tiên."
            notify={notify}
          />
          <InlineBgmSelector
            bgmPresets={bgmPresets}
            bgmPresetId={bgmPresetId}
            onSelectPreset={setBgmPresetId}
            bgmVolume={bgmVolume}
            onVolumeChange={setBgmVolume}
            customBgmPath={customBgmPath}
            onCustomBgmChange={setCustomBgmPath}
            notify={notify}
            label="Nhạc nền kể chuyện / Acoustic"
          />
        </div>
      </div>

      {/* STEP 3: CLEAR VISIBLE DURATION, PARTS & SUBTITLES */}
      <div className="step-box">
        <div className="step-header">
          <span className="step-num">3</span>
          <div>
            <div className="step-title">Thời lượng, chia tập & phong cách hiển thị phụ đề</div>
            <div className="step-desc">
              Cấu hình trực quan ngay trên màn hình để kiểm soát chính xác độ dài video xuất ra
            </div>
          </div>
        </div>

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
              style={{ width: '100%', marginTop: 8 }}
              value={durationSec}
              onChange={(e) => setDurationSec(Number(e.target.value))}
            />
          </div>
          <div className="form-group">
            <label className="form-label">Số tập muốn chia liên tiếp</label>
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
            <label className="form-label">Kiểu chữ phụ đề trên video</label>
            <select
              className="select"
              value={subtitleStyle}
              onChange={(e) => setSubtitleStyle(e.target.value)}
            >
              <option value="KARAOKE_CAPCUT">Chữ chạy nổi bật từng từ</option>
              <option value="CINEMA">Phụ đề câu thanh lịch dưới màn hình</option>
              <option value="NONE">Không hiển thị chữ phụ đề</option>
            </select>
          </div>
          <div className="form-group" style={{ marginBottom: 0 }}>
            <label className="form-label">Ghi chú giọng văn mong muốn</label>
            <input className="input" value={tone} onChange={(e) => setTone(e.target.value)} />
          </div>
        </div>
      </div>

      <div className="btn-row">
        <button
          className="btn btn-primary"
          style={{ flex: 1, minWidth: 230, minHeight: 44, fontSize: 14.2 }}
          disabled={submitting}
          onClick={() => handleStart(true)}
        >
          <Play size={16} /> Bắt đầu tạo video tự động
        </button>
        <button
          className="btn btn-secondary"
          style={{ minHeight: 44 }}
          disabled={submitting}
          onClick={() => handleStart(false)}
        >
          <Edit3 size={15} /> Xem và sửa kịch bản trước khi xuất
        </button>
      </div>
    </div>
  );
}
