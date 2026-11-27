import React, { useEffect, useRef, useState } from 'react';
import {
  ArrowDown,
  ArrowUp,
  BookmarkPlus,
  CheckCircle2,
  Edit3,
  EyeOff,
  Film,
  Flame,
  Heart,
  KeyRound,
  Languages,
  Layers,
  Link2,
  Loader2,
  MessageSquarePlus,
  MessageSquareText,
  Moon,
  Play,
  Plus,
  Smile,
  Sparkles,
  Sun,
  ThumbsUp,
  Trash2,
  Upload,
  Users,
  Volume2,
  Wand2,
} from 'lucide-react';
import { studioApi } from '../m00_core_contracts/apiClient';
import { formatSecondsVi, stripLeadingEmoji } from '../m00_core_contracts/constants';
import {
  InlineBgmSelector,
  InlineVoiceSelector,
  MediaDropzone,
  ModeChoiceGrid,
  ParentGroupSelector,
  SwitchCard,
} from '../m00_core_contracts/StudioWidgets';

const THREADS_DRAFT_KEY = 'chaos_draft_threads_v1';

function loadThreadsDraft() {
  try {
    const raw = localStorage.getItem(THREADS_DRAFT_KEY);
    return raw ? JSON.parse(raw) : {};
  } catch {
    return {};
  }
}

const VIBE_CHOICES = [
  {
    value: 'FUNNY_VIRAL',
    title: 'Hài hước & Mặn mòi',
    subtitle: 'Chọn lọc bình luận duyên dáng, bất ngờ chuẩn viral TikTok',
    icon: Smile,
  },
  {
    value: 'EMPATHY_STORY',
    title: 'Tâm sự & Đồng cảm',
    subtitle: 'Chia sẻ câu chuyện đời thực sâu sắc, chạm cảm xúc người nghe',
    icon: Heart,
  },
  {
    value: 'DEBATE_SPICY',
    title: 'Tranh luận đa chiều',
    subtitle: 'Góc nhìn trái ngược sắc sảo kích thích người xem để lại bình luận',
    icon: Flame,
  },
  {
    value: 'TOP_LIKED',
    title: 'Nhiều lượt thích nhất',
    subtitle: 'Ưu tiên các phản hồi súc tích có lượng tương tác cao nhất',
    icon: ThumbsUp,
  },
];

const CARD_THEME_CHOICES = [
  {
    value: 'DARK_THREADS',
    title: 'Thẻ Tối Chuẩn Threads',
    subtitle: 'Nền đen nhám sang trọng, chữ trắng sắc nét dễ đọc nhất',
    icon: Moon,
  },
  {
    value: 'LIGHT_THREADS',
    title: 'Thẻ Trắng Sáng Nổi Bật',
    subtitle: 'Nền trắng tinh tế nổi bật trên các video nền tối / cảnh đêm',
    icon: Sun,
  },
  {
    value: 'FROSTED_GLASS',
    title: 'Thẻ Kính Mờ Trong Suốt',
    subtitle: 'Hiệu ứng kính mờ hiện đại nhìn xuyên chuyển động video nền',
    icon: Layers,
  },
];

const QUICK_THREAD_SAMPLES = [
  {
    label: 'Mẫu 1: Học đàn Guitar tuổi 25+',
    rawText: `@minhanh.music: Mn ơi cho mik hỏi thật, 26 tuổi đi làm bận tối mắt mới bắt đầu tập chơi đàn Guitar thì có quá muộn ko ạ? Sợ tay cứng bấm hợp âm ko đc...

@tuan.acoustic: Tr ơi ko hề muộn nha b! Mik 31 tuổi mới cầm đàn lần đầu, mỗi tối tập đúng 20 phút sau 2 tháng đã tự đệm hát chill cuối tuần rồi.
@linhchi.98: Khó nhất là 2 tuần đầu đau đầu ngón tay thôi, vượt qua đc giai đoạn bấm hợp âm chặn F là nghiện luôn ko dứt ra đc đâu!
@hoangnam.guitar: Người đi làm học đàn còn nhanh hơn sinh viên vì biết đặt mục tiêu rõ ràng. Nhớ chọn cây đàn action thấp bấm cho êm tay nhé.
@thaovy.daily: Cứ tập đi b ơi, cảm giác tan làm về phòng tự gảy vài hợp âm bài mình thích nó chữa lành thực sự luôn á.`,
  },
  {
    label: 'Mẫu 2: Bài học đi làm công sở',
    rawText: `@chuyencongso.vn: Đâu là khoảnh khắc khiến mn nhận ra mình đã thực sự trưởng thành khi đi làm cty?

@anhduc.dev: Là lúc bị sếp góp ý thẳng mặt nhưng ko còn tự ái nữa, chỉ bình tĩnh mở sổ ghi lại cách sửa để lần sau làm tốt hơn.
@ngocmai.hr: Khi tan làm lúc 6h chiều ko còn thấy áy náy vì về đúng giờ, miễn là toàn bộ công việc trong ngày đã hoàn thành chỉn chu 100%.
@khoinguyen.mkt: Nhận ra đồng nghiệp hợp tác ăn ý là đủ quý rồi, ko nhất thiết ai ở cty cx phải trở thành bạn thân tâm sự mọi chuyện riêng tư.
@phuongthao.fin: Là tháng lương đầu tiên tự trích ra một khoản dự phòng 6 tháng chi tiêu thay vì mua sắm hết sạch trong một đêm.`,
  },
  {
    label: 'Mẫu 3: Thói quen nhỏ đổi đời',
    rawText: `@songchat.threads: Một món đồ hoặc thói quen nhỏ dưới 500k nhưng làm chất lượng cuộc sống của mn tăng vọt 180 độ là j?

@minhtriet.sg: Để điện thoại ở ngoài phòng khách trước 11h đêm! Tuần đầu hơi bứt rứt nhưng sau đó ngủ sâu tới sáng, dậy tỉnh táo hẳn luôn.
@haidang.fit: Mua một bình giữ nhiệt 1 lít để ngay bàn làm việc. Tự nhiên uống đủ nước mỗi ngày, da đỡ khô mà chiều ko bị uể oải.
@lananh.podcast: Dành 10 phút đi bộ ko đeo tai nghe sau bữa tối. Đầu óc nhẹ bẫng, bao nhiêu ý tưởng hay tự nhiên nảy ra lúc đó.`,
  },
];

export default function ThreadsStudioForm({
  voices = [],
  bgmPresets = [],
  layoutConfig,
  setLayoutConfig,
  projectGroups = [],
  onGroupsChanged,
  onPreviewFrameReady,
  onProjectStarted,
  notify,
  apiKeyConfigured = false,
  onOpenApiSettings,
}) {
  const savedDraft = loadThreadsDraft();
  const rootRef = useRef(null);
  const previewPlayerRef = useRef(null);

  const [parentGroupId, setParentGroupId] = useState(savedDraft.parentGroupId || '');
  const [postUrl, setPostUrl] = useState(savedDraft.postUrl || '');
  const [rawPastedText, setRawPastedText] = useState(savedDraft.rawPastedText || '');
  const [maxComments, setMaxComments] = useState(savedDraft.maxComments || 5);
  const [filterVibe, setFilterVibe] = useState(savedDraft.filterVibe || 'FUNNY_VIRAL');
  const [expandSlang, setExpandSlang] = useState(savedDraft.expandSlang !== false);
  const [multiVoiceCast, setMultiVoiceCast] = useState(savedDraft.multiVoiceCast !== false);

  const [hostVoiceId, setHostVoiceId] = useState(
    voices.find((v) => v.profile_id === 'edge_hoai_my_fast')?.profile_id ||
      voices.find((v) => v.profile_id === 'gemini_tiktok_zephyr')?.profile_id ||
      voices[0]?.profile_id ||
      'edge_hoai_my_fast'
  );
  const [extracting, setExtracting] = useState(false);
  const [bundle, setBundle] = useState(savedDraft.bundle || null);
  const [appendCtaComment, setAppendCtaComment] = useState(
    savedDraft.appendCtaComment ||
      'Còn góc nhìn của bạn về chủ đề này thì sao? Để lại bình luận bên dưới nhé!'
  );
  const [previewingAudioKey, setPreviewingAudioKey] = useState('');

  // Background Video & Kho Video Nền state
  const [bgLibrary, setBgLibrary] = useState([]);
  const [selectedBgPath, setSelectedBgPath] = useState(savedDraft.selectedBgPath || '');
  const [selectedBgPreviewUrl, setSelectedBgPreviewUrl] = useState(
    savedDraft.selectedBgPreviewUrl || ''
  );
  const [bgUrlInput, setBgUrlInput] = useState('');
  const [savingBgUrl, setSavingBgUrl] = useState(false);
  const [uploadingBg, setUploadingBg] = useState(false);
  const [saveUploadedToLib, setSaveUploadedToLib] = useState(true);
  const [bgCustomTitle, setBgCustomTitle] = useState('');
  const [keepBgAudio, setKeepBgAudio] = useState(false);
  const [bgAudioVolume, setBgAudioVolume] = useState(0.14);

  // Audio & Visual Presentation
  const [enablePopSfx, setEnablePopSfx] = useState(savedDraft.enablePopSfx !== false);
  const [subtitleStyle, setSubtitleStyle] = useState(savedDraft.subtitleStyle || 'NONE');
  const [bgmPresetId, setBgmPresetId] = useState('bgm_lofi_story');
  const [customBgmPath, setCustomBgmPath] = useState(null);
  const [bgmVolume, setBgmVolume] = useState(0.06);
  const [submitting, setSubmitting] = useState(false);

  const loadBgLibrary = async () => {
    try {
      const list = await studioApi.listBgVideos();
      setBgLibrary(list);
      if (!selectedBgPath && list.length > 0) {
        setSelectedBgPath(list[0].local_path);
        setSelectedBgPreviewUrl(list[0].media_url || '');
      }
    } catch {
      // ignore
    }
  };

  useEffect(() => {
    loadBgLibrary();
  }, []);

  useEffect(() => {
    try {
      localStorage.setItem(
        THREADS_DRAFT_KEY,
        JSON.stringify({
          parentGroupId,
          postUrl,
          rawPastedText,
          maxComments,
          filterVibe,
          expandSlang,
          multiVoiceCast,
          bundle,
          appendCtaComment,
          selectedBgPath,
          selectedBgPreviewUrl,
          enablePopSfx,
          subtitleStyle,
        })
      );
    } catch {
      // ignore quota
    }
  }, [
    parentGroupId,
    postUrl,
    rawPastedText,
    maxComments,
    filterVibe,
    expandSlang,
    multiVoiceCast,
    bundle,
    appendCtaComment,
    selectedBgPath,
    selectedBgPreviewUrl,
    enablePopSfx,
    subtitleStyle,
  ]);

  const updateThreadsLayout = (patch) => {
    if (setLayoutConfig) {
      setLayoutConfig((prev) => ({ ...prev, ...patch }));
    }
  };

  const handleExtractThreads = async () => {
    if ((postUrl.trim() + rawPastedText.trim()).length < 4) {
      notify('Vui lòng dán link bài viết Threads/Reddit hoặc dán văn bản vào ô bên dưới.');
      return;
    }
    setExtracting(true);
    try {
      const res = await studioApi.extractThreadsPost({
        post_url: postUrl.trim(),
        raw_pasted_text: rawPastedText.trim(),
        max_comments: Number(maxComments),
        filter_vibe: filterVibe,
        expand_slang_and_translate: expandSlang,
        anonymize_handles: Boolean(layoutConfig.threads_anonymize_handles),
        multi_voice_cast: multiVoiceCast,
        host_voice_id: hostVoiceId,
      });
      setBundle(res);
      notify(
        res.used_api_key
          ? `Đã gọi API AI chọn lọc ${res.comments?.length || 0} bình luận tiêu biểu & chuẩn hóa giọng đọc!`
          : `Đã trích xuất bài gốc và ${res.comments?.length || 0} bình luận tiêu biểu!`
      );
    } catch (err) {
      notify(`Lỗi hút nội dung Threads: ${err.message}`);
    } finally {
      setExtracting(false);
    }
  };

  const handlePreviewVoiceSnippet = async (key, vId, text) => {
    if (previewingAudioKey === key && previewPlayerRef.current) {
      previewPlayerRef.current.pause();
      setPreviewingAudioKey('');
      return;
    }
    if (!text?.trim()) return;
    setPreviewingAudioKey(key);
    try {
      const res = await studioApi.previewVoice(vId || hostVoiceId, text.trim());
      if (previewPlayerRef.current) previewPlayerRef.current.pause();
      const audio = new Audio(`${res.audio_url}?t=${Date.now()}`);
      previewPlayerRef.current = audio;
      audio.onended = () => setPreviewingAudioKey('');
      audio.onerror = () => setPreviewingAudioKey('');
      await audio.play();
    } catch (err) {
      setPreviewingAudioKey('');
      notify(`Lỗi nghe thử: ${err.message}`);
    }
  };

  const patchComment = (idx, patchObj) => {
    setBundle((prev) => {
      if (!prev) return prev;
      return {
        ...prev,
        comments: prev.comments.map((c, i) => (i !== idx ? c : { ...c, ...patchObj })),
      };
    });
  };

  const moveComment = (fromIdx, toIdx) => {
    setBundle((prev) => {
      if (!prev || toIdx < 0 || toIdx >= prev.comments.length) return prev;
      const copy = [...prev.comments];
      const [picked] = copy.splice(fromIdx, 1);
      copy.splice(toIdx, 0, picked);
      return { ...prev, comments: copy };
    });
  };

  const removeComment = (idx) => {
    setBundle((prev) => {
      if (!prev) return prev;
      return { ...prev, comments: prev.comments.filter((_, i) => i !== idx) };
    });
  };

  const addCustomComment = () => {
    const fallbackVoice =
      voices.find((v) => v.profile_id !== hostVoiceId)?.profile_id || hostVoiceId;
    setBundle((prev) => {
      const curList = prev?.comments || [];
      const nextIdx = curList.length + 1;
      const newCmt = {
        comment_id: `custom_${Date.now()}`,
        author_handle: layoutConfig.threads_anonymize_handles
          ? `@nguoila_${String(nextIdx).padStart(2, '0')}`
          : `@thanhvien_${nextIdx}`,
        display_name: '',
        raw_text: 'Nhập nội dung bình luận mới tại đây...',
        display_text: 'Nhập nội dung bình luận mới tại đây...',
        spoken_vi_text: 'Nhập nội dung bình luận mới tại đây.',
        likes_count: 168,
        likes_display: '168',
        is_verified: false,
        is_ai_suggested: false,
        voice_profile_id: fallbackVoice,
        selected: true,
      };
      if (!prev) {
        return {
          source_url: postUrl.trim(),
          platform: 'threads',
          topic_title: 'Chủ đề thảo luận trên Threads',
          op_author_handle: '@chuthot',
          op_display_text: 'Nhập nội dung bài đăng gốc tại đây...',
          op_spoken_vi_text: 'Nhập nội dung bài đăng gốc tại đây.',
          op_likes_display: '1,5K',
          op_replies_display: '45',
          op_is_verified: true,
          op_voice_profile_id: hostVoiceId,
          comments: [newCmt],
          used_api_key: false,
          extraction_note: '',
        };
      }
      return { ...prev, comments: [...curList, newCmt] };
    });
  };

  const handleUploadBgFiles = async (files) => {
    const f = files?.[0];
    if (!f) return;
    setUploadingBg(true);
    try {
      if (saveUploadedToLib) {
        const saved = await studioApi.uploadBgVideo(
          f,
          bgCustomTitle.trim() || f.name.replace(/\.[^.]+$/, ''),
          'Kho Video Nền'
        );
        await loadBgLibrary();
        setSelectedBgPath(saved.local_path);
        setSelectedBgPreviewUrl(saved.media_url || '');
        setBgCustomTitle('');
        notify(`Đã tải lên & lưu "${saved.title}" vào Kho Video Nền tái sử dụng!`);
      } else {
        const up = await studioApi.uploadStudioFile(f, 'threads_bg');
        setSelectedBgPath(up.local_path);
        setSelectedBgPreviewUrl(up.media_url || '');
        notify(`Đã chọn video nền: ${up.original_name}`);
      }
    } catch (err) {
      notify(`Lỗi tải video nền: ${err.message}`);
    } finally {
      setUploadingBg(false);
    }
  };

  const handleDownloadBgFromUrl = async () => {
    const clean = bgUrlInput.trim();
    if (!clean.startsWith('http://') && !clean.startsWith('https://')) {
      notify('Vui lòng dán link video YouTube / TikTok hợp lệ (bắt đầu bằng https://...).');
      return;
    }
    setSavingBgUrl(true);
    try {
      const saved = await studioApi.saveBgVideoFromUrl({
        video_url: clean,
        title: bgCustomTitle.trim(),
        category_tag: 'Tải từ Link',
      });
      await loadBgLibrary();
      setSelectedBgPath(saved.local_path);
      setSelectedBgPreviewUrl(saved.media_url || '');
      setBgUrlInput('');
      setBgCustomTitle('');
      if (onPreviewFrameReady) onPreviewFrameReady('');
      notify(`Đã tải & lưu video nền "${saved.title}" vào Kho Video Nền!`);
    } catch (err) {
      notify(`Lỗi tải video nền từ link: ${err.message}`);
    } finally {
      setSavingBgUrl(false);
    }
  };

  const handleDeleteSavedBg = async (bg, e) => {
    e.stopPropagation();
    try {
      await studioApi.deleteBgVideo(bg.bg_id);
      if (selectedBgPath === bg.local_path) {
        setSelectedBgPath('');
        setSelectedBgPreviewUrl('');
      }
      await loadBgLibrary();
      notify(`Đã xóa "${bg.title}" khỏi Kho Video Nền.`);
    } catch (err) {
      notify(`Lỗi xóa video nền: ${err.message}`);
    }
  };

  const handleStartThreadsVideo = async (autoOneClick) => {
    if (!bundle || !bundle.op_display_text?.trim()) {
      notify('Vui lòng bấm "Hút bài viết & Lọc bình luận tiêu biểu" trước khi xuất video.');
      return;
    }
    const effBg = selectedBgPath.trim() || bgUrlInput.trim();
    if (!effBg) {
      notify('Vui lòng chọn hoặc tải lên 1 Video Nền ở Bước 2.');
      return;
    }
    const activeCount = (bundle.comments || []).filter((c) => c.selected).length;
    if (activeCount === 0) {
      notify('Vui lòng tích chọn ít nhất 1 bình luận để hiển thị trong video.');
      return;
    }

    setSubmitting(true);
    try {
      const isRemote = effBg.startsWith('http://') || effBg.startsWith('https://');
      const res = await studioApi.startThreadsProject({
        bundle: {
          ...bundle,
          op_voice_profile_id: bundle.op_voice_profile_id || hostVoiceId,
        },
        bg_source_type: isRemote ? 'VIDEO_URL' : 'LOCAL_FILE',
        bg_path_or_url: effBg,
        save_bg_to_library: false,
        bg_library_title: bgCustomTitle.trim(),
        keep_bg_audio: keepBgAudio,
        bg_audio_volume: Number(bgAudioVolume),
        append_cta_comment: appendCtaComment.trim(),
        enable_card_pop_sfx: enablePopSfx,
        voice_profile_id: bundle.op_voice_profile_id || hostVoiceId,
        bgm_preset_id: bgmPresetId,
        custom_bgm_path: customBgmPath,
        bgm_volume: Number(bgmVolume),
        subtitle_style: subtitleStyle,
        layout_config: {
          ...layoutConfig,
          show_top_banner: false,
        },
        parent_group_id: parentGroupId || null,
        auto_one_click: autoOneClick,
      });
      onProjectStarted(res.project_id, res.state);
    } catch (err) {
      notify(`Không thể bắt đầu video Threads: ${err.message}`);
    } finally {
      setSubmitting(false);
    }
  };

  useEffect(() => {
    const onKeyDown = (e) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
        if (!rootRef.current || rootRef.current.offsetParent === null) return;
        if (submitting || extracting || uploadingBg) return;
        e.preventDefault();
        handleStartThreadsVideo(true);
      }
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  });

  const selectedCommentsCount = (bundle?.comments || []).filter((c) => c.selected).length;
  const estTotalSec = bundle
    ? Math.max(
        12,
        Math.round(
          ((bundle.op_spoken_vi_text || '').split(/\s+/).length +
            (bundle.comments || [])
              .filter((c) => c.selected)
              .reduce((acc, c) => acc + (c.spoken_vi_text || '').split(/\s+/).length, 0)) /
            2.75
        ) +
          selectedCommentsCount +
          2
      )
    : maxComments * 8 + 7;

  return (
    <div ref={rootRef} className="card">
      <div className="page-header">
        <div>
          <div className="page-title">
            <MessageSquareText size={20} strokeWidth={2} /> Video Chủ Đề Threads &amp; Bình Luận Cộng Đồng
          </div>
          <div className="page-subtitle">
            Dán link Threads / Reddit → AI lọc bình luận tiêu biểu &amp; bung từ viết tắt → Ghép thẻ bình luận nổi đa giọng đọc trên nền video lặp vòng 9:16
          </div>
        </div>
        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', alignItems: 'center' }}>
          <span className={`badge ${apiKeyConfigured ? 'badge-ok' : 'badge-warn'}`}>
            <KeyRound size={12} /> {apiKeyConfigured ? 'API Key AI sẵn sàng' : 'Chưa gắn API Key'}
          </span>
          <span className="badge badge-info">
            {bundle ? `Đã chọn ${selectedCommentsCount} bình luận` : `Lấy ${maxComments} bình luận`}
          </span>
          <span className="badge">~{estTotalSec}s</span>
        </div>
      </div>

      {/* QUICK THREADS SAMPLES */}
      <div className="summary-bar">
        <span
          style={{
            fontSize: 12.5,
            fontWeight: 700,
            display: 'inline-flex',
            alignItems: 'center',
            gap: 5,
          }}
        >
          <Sparkles size={14} style={{ color: 'var(--brand-text)' }} /> Thử nhanh chủ đề mẫu:
        </span>
        {QUICK_THREAD_SAMPLES.map((smp, idx) => (
          <button
            key={idx}
            type="button"
            className="btn btn-secondary btn-sm"
            onClick={() => {
              setPostUrl('');
              setRawPastedText(smp.rawText);
              notify(`Đã điền "${smp.label}" — bấm nút Hút & Lọc bình luận AI bên dưới để chạy thử!`);
            }}
          >
            {smp.label}
          </button>
        ))}
      </div>

      {/* STEP 1: THREADS LINK + CURATION CONTROLS */}
      <div className="step-box">
        <div className="step-header">
          <span className="step-num">1</span>
          <div style={{ flex: 1 }}>
            <div className="step-title">
              Dán Link Threads / Reddit &amp; Cài đặt số lượng bình luận tiêu biểu muốn lấy
            </div>
            <div className="step-desc">
              Hỗ trợ link công khai <code>threads.net</code>, <code>threads.com</code>, <code>reddit.com</code> hoặc dán trực tiếp đoạn hội thoại nếu bài khóa riêng tư
            </div>
          </div>
          {!apiKeyConfigured && onOpenApiSettings && (
            <button type="button" className="btn btn-secondary btn-sm" onClick={onOpenApiSettings}>
              <KeyRound size={13} /> Nhập API Key AI
            </button>
          )}
        </div>

        <ParentGroupSelector
          projectGroups={projectGroups}
          value={parentGroupId}
          onChange={setParentGroupId}
          onGroupsChanged={onGroupsChanged}
          notify={notify}
          label="Thuộc Dự Án Cha (Gom theo Series Chuyện Threads / Tâm sự / Hỏi đáp)"
        />

        <div className="form-group">
          <label className="form-label">
            <Link2 size={13} style={{ verticalAlign: '-2px', marginRight: 5 }} />
            Đường dẫn bài đăng Threads / Reddit / Diễn đàn
          </label>
          <input
            className="input"
            placeholder="VD: https://www.threads.net/@ten_tai_khoan/post/... hoặc https://www.reddit.com/r/..."
            value={postUrl}
            onChange={(e) => setPostUrl(e.target.value)}
          />
        </div>

        <div className="form-group">
          <label className="form-label">
            Nội dung văn bản bài đăng &amp; bình luận (Tùy chọn — Dán vào đây nếu bài khóa riêng tư hoặc muốn gộp thêm bình luận)
          </label>
          <textarea
            className="textarea"
            style={{ minHeight: 88 }}
            placeholder={`Có thể để trống nếu đã dán link ở trên, hoặc dán nhanh theo dạng:\n@chuthot: Nội dung câu hỏi chủ đề...\n@user1: Bình luận thứ nhất...\n@user2: Bình luận thứ hai...`}
            value={rawPastedText}
            onChange={(e) => setRawPastedText(e.target.value)}
          />
        </div>

        <div className="form-grid" style={{ marginBottom: 13 }}>
          <div className="surface-box">
            <label className="form-label" style={{ marginBottom: 4 }}>
              Số bình luận tiêu biểu muốn lấy: <strong>{maxComments} bình luận</strong>
            </label>
            <input
              type="range"
              min="2"
              max="15"
              step="1"
              style={{ width: '100%', marginTop: 4 }}
              value={maxComments}
              onChange={(e) => setMaxComments(Number(e.target.value))}
            />
            <div
              className="text-muted"
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                fontSize: 11.4,
                marginTop: 3,
              }}
            >
              <span>2 câu (Ngắn ~20s)</span>
              <span>5–7 câu (Chuẩn ~55s)</span>
              <span>15 câu (~120s)</span>
            </div>
          </div>

          <InlineVoiceSelector
            voices={voices}
            voiceId={hostVoiceId}
            onChange={setHostVoiceId}
            defaultCategory="TIKTOK_SHORT"
            label="Giọng đọc Chủ bài đăng (OP)"
            sampleText="Mọi người ơi cho mình hỏi thật, hai mươi sáu tuổi mới bắt đầu tập đàn Guitar thì có quá muộn không ạ?"
            notify={notify}
          />
        </div>

        <div className="form-group">
          <label className="form-label">Tiêu chí AI chọn lọc bình luận tiêu biểu</label>
          <ModeChoiceGrid options={VIBE_CHOICES} value={filterVibe} onChange={setFilterVibe} />
        </div>

        <div className="toggle-grid" style={{ marginBottom: 14 }}>
          <SwitchCard icon={Languages} checked={expandSlang} onChange={setExpandSlang}>
            Bung viết tắt teen-code (ko→không, đc→được) &amp; dịch Việt hóa
          </SwitchCard>
          <SwitchCard icon={Users} checked={multiVoiceCast} onChange={setMultiVoiceCast}>
            Đa giọng đọc đối thoại (Tự đổi giọng Nam/Nữ từng bình luận)
          </SwitchCard>
          <SwitchCard
            icon={EyeOff}
            checked={Boolean(layoutConfig.threads_anonymize_handles)}
            onChange={(val) => updateThreadsLayout({ threads_anonymize_handles: val })}
          >
            Che ẩn tên tài khoản (@nguoila_01)
          </SwitchCard>
        </div>

        {/* PROMINENT EXTRACT & AI CURATE BAR */}
        <div
          className="surface-box"
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            gap: 10,
            flexWrap: 'wrap',
            borderColor: 'var(--brand)',
          }}
        >
          <div style={{ minWidth: 220, flex: 1 }}>
            <div style={{ fontSize: 13.4, fontWeight: 700, color: 'var(--text-primary)' }}>
              Bước 1A: Hút bài viết &amp; gọi AI chọn ra {maxComments} bình luận đắt giá nhất
            </div>
            <div className="text-sub" style={{ fontSize: 12.2, marginTop: 2 }}>
              Bạn sẽ được xem trước, tích chọn, sửa chữ hoặc đổi giọng đọc từng bình luận ngay bên dưới trước khi ghép video
            </div>
          </div>
          <button
            type="button"
            className="btn btn-primary"
            style={{ minHeight: 41, fontWeight: 700 }}
            disabled={extracting || submitting}
            onClick={handleExtractThreads}
          >
            {extracting ? <Loader2 size={16} /> : <Wand2 size={16} />}
            <span>
              {extracting
                ? 'Đang hút bài & lọc bình luận AI...'
                : `Hút bài viết & Lọc ${maxComments} bình luận tiêu biểu`}
            </span>
          </button>
        </div>

        {/* INTERACTIVE CURATED THREAD & COMMENTS EDITOR */}
        {bundle && (
          <div style={{ marginTop: 15, display: 'grid', gap: 12 }}>
            <div
              className="surface-box"
              style={{
                borderColor: 'rgba(16, 185, 129, 0.5)',
                background: 'rgba(16, 185, 129, 0.06)',
              }}
            >
              <div
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  gap: 8,
                  flexWrap: 'wrap',
                  marginBottom: 8,
                }}
              >
                <span
                  style={{
                    fontWeight: 700,
                    fontSize: 13.4,
                    color: 'var(--success-text)',
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: 6,
                  }}
                >
                  <CheckCircle2 size={16} />
                  {bundle.extraction_note || 'Đã sẵn sàng danh sách bài đăng gốc & bình luận tiêu biểu'}
                </span>
                <button
                  type="button"
                  className="btn btn-secondary btn-sm"
                  onClick={addCustomComment}
                >
                  <MessageSquarePlus size={13} /> + Thêm 1 bình luận riêng
                </button>
              </div>

              {/* OP MAIN THREAD CARD EDITOR */}
              <div
                style={{
                  padding: 12,
                  borderRadius: 10,
                  background: 'var(--bg-panel)',
                  border: '1.5px solid var(--brand)',
                  marginBottom: 10,
                }}
              >
                <div
                  style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    gap: 8,
                    flexWrap: 'wrap',
                    marginBottom: 8,
                  }}
                >
                  <span className="badge badge-info">Thẻ mở đầu • Chủ bài đăng (OP)</span>
                  <div style={{ display: 'flex', gap: 6, alignItems: 'center', flexWrap: 'wrap' }}>
                    <input
                      className="input"
                      style={{ width: 155, minHeight: 32, padding: '4px 9px', fontSize: 12.4 }}
                      value={bundle.op_author_handle}
                      onChange={(e) =>
                        setBundle((prev) => ({ ...prev, op_author_handle: e.target.value }))
                      }
                      title="Tên @handle hiển thị trên thẻ OP"
                    />
                    <input
                      className="input"
                      style={{ width: 82, minHeight: 32, padding: '4px 8px', fontSize: 12.4 }}
                      value={bundle.op_likes_display}
                      onChange={(e) =>
                        setBundle((prev) => ({ ...prev, op_likes_display: e.target.value }))
                      }
                      title="Số lượt tim hiển thị"
                    />
                    <select
                      className="select"
                      style={{ width: 195, minHeight: 32, padding: '4px 8px', fontSize: 12.2 }}
                      value={bundle.op_voice_profile_id || hostVoiceId}
                      onChange={(e) =>
                        setBundle((prev) => ({ ...prev, op_voice_profile_id: e.target.value }))
                      }
                    >
                      {voices.map((v) => (
                        <option key={v.profile_id} value={v.profile_id}>
                          {stripLeadingEmoji(v.display_name).split('—')[0].trim()}
                        </option>
                      ))}
                    </select>
                    <button
                      type="button"
                      className="btn btn-secondary btn-sm"
                      onClick={() =>
                        handlePreviewVoiceSnippet(
                          'op_voice',
                          bundle.op_voice_profile_id || hostVoiceId,
                          bundle.op_spoken_vi_text || bundle.op_display_text
                        )
                      }
                    >
                      {previewingAudioKey === 'op_voice' ? (
                        <Loader2 size={13} />
                      ) : (
                        <Volume2 size={13} />
                      )}{' '}
                      Nghe OP
                    </button>
                  </div>
                </div>

                <div className="form-group" style={{ marginBottom: 8 }}>
                  <label className="form-label" style={{ fontSize: 12 }}>
                    Tiêu đề SEO của dự án video
                  </label>
                  <input
                    className="input"
                    style={{ minHeight: 35 }}
                    value={bundle.topic_title}
                    onChange={(e) =>
                      setBundle((prev) => ({ ...prev, topic_title: e.target.value }))
                    }
                  />
                </div>

                <div className="form-grid">
                  <div>
                    <label className="form-label" style={{ fontSize: 11.8 }}>
                      Chữ hiển thị trên Thẻ Bài Gốc
                    </label>
                    <textarea
                      className="textarea"
                      style={{ minHeight: 68, fontSize: 13 }}
                      value={bundle.op_display_text}
                      onChange={(e) =>
                        setBundle((prev) => ({ ...prev, op_display_text: e.target.value }))
                      }
                    />
                  </div>
                  <div>
                    <label className="form-label" style={{ fontSize: 11.8 }}>
                      Lời đọc lồng tiếng AI (đã bung từ viết tắt)
                    </label>
                    <textarea
                      className="textarea"
                      style={{ minHeight: 68, fontSize: 13 }}
                      value={bundle.op_spoken_vi_text}
                      onChange={(e) =>
                        setBundle((prev) => ({ ...prev, op_spoken_vi_text: e.target.value }))
                      }
                    />
                  </div>
                </div>
              </div>

              {/* COMMENTS LIST */}
              <div style={{ display: 'grid', gap: 9, maxHeight: 460, overflowY: 'auto', paddingRight: 3 }}>
                {(bundle.comments || []).map((cmt, idx) => {
                  const pKey = `cmt_${idx}`;
                  return (
                    <div
                      key={cmt.comment_id || idx}
                      style={{
                        padding: '10px 12px',
                        borderRadius: 9,
                        background: 'var(--bg-panel)',
                        border: cmt.selected
                          ? '1px solid var(--border-strong)'
                          : '1px dashed var(--border)',
                        opacity: cmt.selected ? 1 : 0.58,
                      }}
                    >
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
                          style={{
                            display: 'inline-flex',
                            alignItems: 'center',
                            gap: 7,
                            fontWeight: 700,
                            fontSize: 13,
                            cursor: 'pointer',
                          }}
                        >
                          <input
                            type="checkbox"
                            style={{ width: 16, height: 16, accentColor: 'var(--brand)' }}
                            checked={Boolean(cmt.selected)}
                            onChange={(e) => patchComment(idx, { selected: e.target.checked })}
                          />
                          <span>Bình luận #{idx + 1}</span>
                          {cmt.is_ai_suggested && (
                            <span className="badge badge-warn" style={{ fontSize: 10.5, padding: '1px 6px' }}>
                              Gợi ý AI
                            </span>
                          )}
                        </label>

                        <div style={{ display: 'flex', gap: 5, alignItems: 'center', flexWrap: 'wrap' }}>
                          <input
                            className="input"
                            style={{ width: 140, minHeight: 30, padding: '3px 8px', fontSize: 12.2 }}
                            value={cmt.author_handle}
                            onChange={(e) => patchComment(idx, { author_handle: e.target.value })}
                            title="Tên @handle người bình luận"
                          />
                          <input
                            className="input"
                            style={{ width: 72, minHeight: 30, padding: '3px 7px', fontSize: 12.2 }}
                            value={cmt.likes_display}
                            onChange={(e) => patchComment(idx, { likes_display: e.target.value })}
                            title="Số lượt thích"
                          />
                          <select
                            className="select"
                            style={{ width: 185, minHeight: 30, padding: '3px 7px', fontSize: 12 }}
                            value={cmt.voice_profile_id || hostVoiceId}
                            onChange={(e) =>
                              patchComment(idx, { voice_profile_id: e.target.value })
                            }
                            title="Giọng đọc riêng cho bình luận này"
                          >
                            {voices.map((v) => (
                              <option key={v.profile_id} value={v.profile_id}>
                                {stripLeadingEmoji(v.display_name).split('—')[0].trim()}
                              </option>
                            ))}
                          </select>
                          <button
                            type="button"
                            className="btn btn-secondary btn-sm"
                            style={{ padding: '0 8px', minHeight: 30 }}
                            title="Nghe thử giọng đọc bình luận này"
                            onClick={() =>
                              handlePreviewVoiceSnippet(
                                pKey,
                                cmt.voice_profile_id || hostVoiceId,
                                cmt.spoken_vi_text || cmt.display_text
                              )
                            }
                          >
                            {previewingAudioKey === pKey ? (
                              <Loader2 size={12} />
                            ) : (
                              <Volume2 size={12} />
                            )}
                          </button>
                          <button
                            type="button"
                            className="btn btn-secondary btn-sm"
                            style={{ padding: '0 6px', minHeight: 30 }}
                            disabled={idx === 0}
                            onClick={() => moveComment(idx, idx - 1)}
                            title="Đẩy lên trên"
                          >
                            <ArrowUp size={12} />
                          </button>
                          <button
                            type="button"
                            className="btn btn-secondary btn-sm"
                            style={{ padding: '0 6px', minHeight: 30 }}
                            disabled={idx === bundle.comments.length - 1}
                            onClick={() => moveComment(idx, idx + 1)}
                            title="Đẩy xuống dưới"
                          >
                            <ArrowDown size={12} />
                          </button>
                          <button
                            type="button"
                            className="btn btn-danger btn-sm"
                            style={{ padding: '0 6px', minHeight: 30 }}
                            onClick={() => removeComment(idx)}
                            title="Xóa bình luận này"
                          >
                            <Trash2 size={12} />
                          </button>
                        </div>
                      </div>

                      <div className="form-grid">
                        <input
                          className="input"
                          style={{ minHeight: 34, fontSize: 12.8 }}
                          placeholder="Chữ hiển thị trên thẻ..."
                          value={cmt.display_text}
                          onChange={(e) =>
                            patchComment(idx, {
                              display_text: e.target.value,
                              raw_text: e.target.value,
                            })
                          }
                        />
                        <input
                          className="input"
                          style={{ minHeight: 34, fontSize: 12.8 }}
                          placeholder="Lời đọc AI (đã bung viết tắt)..."
                          value={cmt.spoken_vi_text}
                          onChange={(e) => patchComment(idx, { spoken_vi_text: e.target.value })}
                        />
                      </div>
                    </div>
                  );
                })}
              </div>

              <div className="form-group" style={{ marginTop: 10, marginBottom: 0 }}>
                <label className="form-label" style={{ fontSize: 12.2 }}>
                  Thẻ câu hỏi tương tác cuối video (Để trống nếu muốn kết thúc ngay sau bình luận cuối)
                </label>
                <input
                  className="input"
                  placeholder="VD: Còn bạn nghĩ sao về câu chuyện này? Hãy để lại ý kiến dưới phần bình luận nhé!"
                  value={appendCtaComment}
                  onChange={(e) => setAppendCtaComment(e.target.value)}
                />
              </div>
            </div>
          </div>
        )}
      </div>

      {/* STEP 2: BACKGROUND VIDEO & REUSABLE KHO VIDEO NỀN */}
      <div className="step-box">
        <div className="step-header">
          <span className="step-num">2</span>
          <div style={{ flex: 1 }}>
            <div className="step-title">
              Chọn Video Nền Chạy Dưới Thẻ Bình Luận &amp; Kho Video Nền Tái Sử Dụng ({bgLibrary.length})
            </div>
            <div className="step-desc">
              Video nền sẽ tự động cắt khung dọc 9:16 và lặp vòng mượt mà vừa khít tổng thời lượng đọc toàn bộ bình luận
            </div>
          </div>
        </div>

        {/* SAVED BG VIDEO LIBRARY GRID */}
        {bgLibrary.length > 0 && (
          <div style={{ marginBottom: 14 }}>
            <div className="form-label">
              Chọn nhanh 1 chạm từ Kho Video Nền đã lưu ({bgLibrary.length} video):
            </div>
            <div style={{ display: 'flex', gap: 10, overflowX: 'auto', paddingBottom: 6 }}>
              {bgLibrary.map((bg) => {
                const isSelected = selectedBgPath === bg.local_path;
                return (
                  <div
                    key={bg.bg_id}
                    onClick={() => {
                      setSelectedBgPath(bg.local_path);
                      setSelectedBgPreviewUrl(bg.media_url || '');
                    }}
                    style={{
                      width: 142,
                      flexShrink: 0,
                      borderRadius: 10,
                      padding: 6,
                      cursor: 'pointer',
                      background: isSelected ? 'var(--brand-soft)' : 'var(--bg-panel)',
                      border: isSelected ? '2px solid var(--brand)' : '1px solid var(--border)',
                    }}
                  >
                    <video
                      src={bg.media_url}
                      muted
                      playsInline
                      onMouseEnter={(e) => e.currentTarget.play().catch(() => {})}
                      onMouseLeave={(e) => {
                        e.currentTarget.pause();
                        e.currentTarget.currentTime = 0;
                      }}
                      style={{
                        width: '100%',
                        height: 118,
                        objectFit: 'cover',
                        borderRadius: 7,
                        background: '#080b11',
                      }}
                    />
                    <div
                      style={{
                        fontSize: 12,
                        fontWeight: 700,
                        marginTop: 5,
                        whiteSpace: 'nowrap',
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                      }}
                      title={bg.title}
                    >
                      {bg.title}
                    </div>
                    <div
                      style={{
                        display: 'flex',
                        justifyContent: 'space-between',
                        alignItems: 'center',
                        marginTop: 3,
                      }}
                    >
                      <span className="text-muted" style={{ fontSize: 11 }}>
                        {formatSecondsVi(Math.round((bg.duration_ms || 0) / 1000))}
                      </span>
                      <button
                        type="button"
                        onClick={(e) => handleDeleteSavedBg(bg, e)}
                        title="Xóa khỏi Kho Video Nền"
                        style={{
                          border: 'none',
                          background: 'transparent',
                          color: 'var(--danger)',
                          cursor: 'pointer',
                          padding: 2,
                          display: 'inline-flex',
                        }}
                      >
                        <Trash2 size={12} />
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        <div className="form-grid" style={{ marginBottom: 12 }}>
          <div>
            <MediaDropzone
              accept="video/*"
              disabled={uploadingBg}
              icon={Upload}
              title={
                uploadingBg
                  ? 'Đang tải video nền lên máy chủ...'
                  : 'Kéo thả hoặc chọn tệp Video Nền (.mp4, .mov, .webm) từ máy tính / điện thoại'
              }
              hint="VD: Lái xe ban đêm, mưa chill bên cửa sổ, chơi đàn, Minecraft parkour, nấu ăn..."
              onFilesSelected={handleUploadBgFiles}
            />
            <div
              style={{
                display: 'flex',
                gap: 8,
                alignItems: 'center',
                marginTop: 8,
                flexWrap: 'wrap',
              }}
            >
              <SwitchCard
                icon={BookmarkPlus}
                checked={saveUploadedToLib}
                onChange={setSaveUploadedToLib}
              >
                Lưu luôn vào Kho Video Nền
              </SwitchCard>
              <input
                className="input"
                style={{ flex: 1, minWidth: 160, minHeight: 36 }}
                placeholder="Tên gợi nhớ khi lưu kho (tùy chọn)"
                value={bgCustomTitle}
                onChange={(e) => setBgCustomTitle(e.target.value)}
              />
            </div>
          </div>

          <div className="surface-box" style={{ display: 'flex', flexDirection: 'column', justifyContent: 'space-between', gap: 10 }}>
            <div>
              <label className="form-label">
                Hoặc dán link YouTube / TikTok để tải về làm Video Nền
              </label>
              <div style={{ display: 'flex', gap: 6 }}>
                <input
                  className="input"
                  style={{ flex: 1, minHeight: 37 }}
                  placeholder="https://www.youtube.com/shorts/... hoặc TikTok..."
                  value={bgUrlInput}
                  onChange={(e) => setBgUrlInput(e.target.value)}
                />
                <button
                  type="button"
                  className="btn btn-secondary btn-sm"
                  style={{ minHeight: 37, whiteSpace: 'nowrap' }}
                  disabled={savingBgUrl}
                  onClick={handleDownloadBgFromUrl}
                >
                  {savingBgUrl ? <Loader2 size={14} /> : <Plus size={14} />}
                  <span>{savingBgUrl ? 'Đang tải...' : 'Tải vào Kho'}</span>
                </button>
              </div>
            </div>

            {selectedBgPreviewUrl && (
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 10,
                  padding: 8,
                  borderRadius: 8,
                  background: 'var(--bg-step)',
                  border: '1px solid var(--brand-border)',
                }}
              >
                <video
                  src={selectedBgPreviewUrl}
                  muted
                  loop
                  autoPlay
                  playsInline
                  style={{ width: 54, height: 84, objectFit: 'cover', borderRadius: 6, background: '#000' }}
                />
                <div style={{ minWidth: 0, flex: 1 }}>
                  <div style={{ fontSize: 12.5, fontWeight: 700, color: 'var(--brand-text)' }}>
                    <Film size={13} style={{ verticalAlign: '-2px', marginRight: 4 }} />
                    Đã chọn Video Nền sẵn sàng
                  </div>
                  <div
                    className="text-muted"
                    style={{
                      fontSize: 11.5,
                      whiteSpace: 'nowrap',
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                    }}
                  >
                    {selectedBgPath}
                  </div>
                </div>
              </div>
            )}

            <div>
              <div
                className="text-sub"
                style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, marginBottom: 3 }}
              >
                <span>Độ phủ tối làm nổi bật Thẻ Bình Luận</span>
                <strong>{Math.round((layoutConfig.threads_bg_dim ?? 0.28) * 100)}%</strong>
              </div>
              <input
                type="range"
                min="0.05"
                max="0.65"
                step="0.03"
                style={{ width: '100%' }}
                value={layoutConfig.threads_bg_dim ?? 0.28}
                onChange={(e) =>
                  updateThreadsLayout({ threads_bg_dim: parseFloat(e.target.value) })
                }
              />
            </div>
          </div>
        </div>
      </div>

      {/* STEP 3: FLOATING CARD STYLE, POP SFX & AUDIO */}
      <div className="step-box">
        <div className="step-header">
          <span className="step-num">3</span>
          <div>
            <div className="step-title">
              Giao diện Thẻ Bình Luận Nổi, Tiếng Pop Chuyển Thẻ &amp; Nhạc Nền
            </div>
            <div className="step-desc">
              Tùy chỉnh màu sắc thẻ bình luận đồng bộ trực tiếp với khung mô phỏng 9:16 bên phải
            </div>
          </div>
        </div>

        <div style={{ marginBottom: 14 }}>
          <ModeChoiceGrid
            options={CARD_THEME_CHOICES}
            value={layoutConfig.threads_card_theme || 'DARK_THREADS'}
            onChange={(val) => updateThreadsLayout({ threads_card_theme: val })}
          />
        </div>

        <div className="toggle-grid" style={{ marginBottom: 14 }}>
          <SwitchCard checked={enablePopSfx} onChange={setEnablePopSfx}>
            Phát tiếng &ldquo;Pop&rdquo; nhẹ mỗi khi nảy thẻ bình luận mới
          </SwitchCard>
          <SwitchCard checked={keepBgAudio} onChange={setKeepBgAudio}>
            Giữ tiếng động gốc của video nền (mưa, đàn, phố đêm...)
          </SwitchCard>
        </div>

        {keepBgAudio && (
          <div className="surface-box" style={{ marginBottom: 14 }}>
            <div
              className="text-sub"
              style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, marginBottom: 3 }}
            >
              <span>Âm lượng tiếng gốc của video nền lót dưới giọng đọc</span>
              <strong>{Math.round(bgAudioVolume * 100)}%</strong>
            </div>
            <input
              type="range"
              min="0.04"
              max="0.45"
              step="0.02"
              style={{ width: '100%' }}
              value={bgAudioVolume}
              onChange={(e) => setBgAudioVolume(parseFloat(e.target.value))}
            />
          </div>
        )}

        <div className="form-grid">
          <InlineBgmSelector
            bgmPresets={bgmPresets}
            bgmPresetId={bgmPresetId}
            onSelectPreset={setBgmPresetId}
            bgmVolume={bgmVolume}
            onVolumeChange={setBgmVolume}
            customBgmPath={customBgmPath}
            onCustomBgmChange={setCustomBgmPath}
            notify={notify}
            label="Nhạc nền Lofi / Chill lót nhẹ"
          />

          <div className="selector-card">
            <label className="form-label" style={{ marginBottom: 0 }}>
              Phụ đề chạy thêm dưới đáy video (Tùy chọn)
            </label>
            <select
              className="select"
              value={subtitleStyle}
              onChange={(e) => setSubtitleStyle(e.target.value)}
            >
              <option value="NONE">
                Tắt phụ đề dưới đáy (Khuyên dùng vì chữ đã hiện rõ trên Thẻ Threads)
              </option>
              <option value="KARAOKE_CAPCUT">Bật thêm chữ Karaoke chạy từng từ</option>
              <option value="CINEMA">Bật thêm phụ đề câu thanh lịch</option>
            </select>
            <div className="text-muted" style={{ fontSize: 11.8 }}>
              Mỗi thẻ bình luận nổi đã tự động căn chữ to rõ ngay tầm mắt người xem và chuyển thẻ khớp từng mili-giây giọng đọc.
            </div>
          </div>
        </div>
      </div>

      {/* STICKY ACTION BAR */}
      <div className="sticky-action-bar">
        <span className="text-sub" style={{ fontSize: 12.2 }}>
          Tự động lưu nháp • <strong>Ctrl + Enter</strong> để xuất ngay
        </span>
        <div
          style={{
            display: 'flex',
            gap: 8,
            flexWrap: 'wrap',
            flex: 1,
            justifyContent: 'flex-end',
          }}
        >
          <button
            type="button"
            className="btn btn-secondary"
            style={{ minHeight: 42 }}
            disabled={submitting || extracting || uploadingBg}
            onClick={() => handleStartThreadsVideo(false)}
          >
            <Edit3 size={15} /> Đưa sang Chờ duyệt kịch bản
          </button>
          <button
            type="button"
            className="btn btn-primary"
            style={{ minWidth: 245, minHeight: 42, fontSize: 14, fontWeight: 700 }}
            disabled={submitting || extracting || uploadingBg}
            onClick={() => handleStartThreadsVideo(true)}
          >
            <Play size={16} /> Bắt đầu dựng Video Threads ngay
          </button>
        </div>
      </div>
    </div>
  );
}

