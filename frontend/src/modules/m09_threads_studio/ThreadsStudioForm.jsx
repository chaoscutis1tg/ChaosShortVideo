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
  Gauge,
  Heart,
  ImagePlus,
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
  X,
} from 'lucide-react';
import { studioApi } from '../m00_core_contracts/apiClient';
import { formatSecondsVi, stripLeadingEmoji } from '../m00_core_contracts/constants';
import {
  FieldError,
  hasAllowedExtension,
  InlineBgmSelector,
  isValidHttpUrl,
  isVideoOnlyPlatformUrl,
  MediaDropzone,
  ModeChoiceGrid,
  ParentGroupSelector,
  scrollToFirstValidationError,
  StudioLoadingBanner,
  SwitchCard,
} from '../m00_core_contracts/StudioWidgets';

const THREADS_DRAFT_KEY = 'chaos_draft_threads_v2';

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
    subtitle: 'Chọn lọc bình luận duyên dáng, kèm ưu tiên các bình luận có ảnh thật',
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
    title: 'Thẻ Trắng Sáng Tinh Gọn',
    subtitle: 'Nền trắng chuẩn Threads (đã bỏ nhãn số thứ tự bình luận rườm rà)',
    icon: Sun,
  },
  {
    value: 'FROSTED_GLASS',
    title: 'Thẻ Kính Mờ Trong Suốt',
    subtitle: 'Hiệu ứng kính mờ hiện đại nhìn xuyên chuyển động video nền',
    icon: Layers,
  },
];

const SPEED_PRESETS = [
  { label: '1.15x Vừa phải', val: 1.15 },
  { label: '1.25x Nhanh bắt tai (Khuyên dùng)', val: 1.25 },
  { label: '1.35x Siêu tốc TikTok', val: 1.35 },
];

const QUICK_THREAD_SAMPLES = [
  {
    label: 'Mẫu 1: Nỗi khổ tập đàn Guitar',
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
  const [maxComments, setMaxComments] = useState(savedDraft.maxComments || 6);
  const [filterVibe, setFilterVibe] = useState(savedDraft.filterVibe || 'FUNNY_VIRAL');
  const [expandSlang, setExpandSlang] = useState(savedDraft.expandSlang !== false);
  const [multiVoiceCast, setMultiVoiceCast] = useState(savedDraft.multiVoiceCast !== false);

  // Strictly 2 Main Voices: 1 Nữ chính & 1 Nam chính + Fast Reading Speed!
  const [femaleVoiceId, setFemaleVoiceId] = useState(
    savedDraft.femaleVoiceId || 'threads_nu_chinh'
  );
  const [maleVoiceId, setMaleVoiceId] = useState(
    savedDraft.maleVoiceId || 'threads_nam_chinh'
  );
  const [opSpeakerGender, setOpSpeakerGender] = useState(
    savedDraft.opSpeakerGender || 'FEMALE'
  );
  const [voiceSpeed, setVoiceSpeed] = useState(
    savedDraft.voiceSpeed ? Number(savedDraft.voiceSpeed) : 1.25
  );

  const hostVoiceId = opSpeakerGender === 'MALE' ? maleVoiceId : femaleVoiceId;

  const [extracting, setExtracting] = useState(false);
  const [bundle, setBundle] = useState(savedDraft.bundle || null);
  const [appendCtaComment, setAppendCtaComment] = useState(
    savedDraft.appendCtaComment !== undefined
      ? savedDraft.appendCtaComment
      : 'Còn góc nhìn của bạn về chủ đề này thì sao? Để lại bình luận bên dưới nhé!'
  );
  const [previewingAudioKey, setPreviewingAudioKey] = useState('');
  const [uploadingCardImgKey, setUploadingCardImgKey] = useState('');

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
  const [errors, setErrors] = useState({});

  const clearError = (...keys) => {
    setErrors((prev) => {
      let changed = false;
      const next = { ...prev };
      keys.forEach((k) => {
        if (next[k]) {
          delete next[k];
          changed = true;
        }
      });
      return changed ? next : prev;
    });
  };

  const femaleVoiceOptions = voices.filter((v) => {
    const label = `${v.display_name} ${v.dsp_preset || ''}`.toLowerCase();
    return (
      v.profile_id === 'threads_nu_chinh' ||
      label.includes('nữ') ||
      label.includes('female') ||
      label.includes('hoài my')
    );
  });
  const maleVoiceOptions = voices.filter((v) => {
    const label = `${v.display_name} ${v.dsp_preset || ''}`.toLowerCase();
    return (
      v.profile_id === 'threads_nam_chinh' ||
      label.includes('nam ') ||
      label.includes('male') ||
      label.includes('nam minh')
    );
  });

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

  // Re-cast existing bundle strictly to the 2 selected Main Voices whenever user changes Nam/Nữ/OP
  const applyTwoMainVoicesToBundle = (targetBundle, nextHost, nextMale, nextFemale, useMulti) => {
    if (!targetBundle) return targetBundle;
    const pair = nextHost === nextFemale ? [nextMale, nextFemale] : [nextFemale, nextMale];
    return {
      ...targetBundle,
      op_voice_profile_id: nextHost,
      male_voice_id: nextMale,
      female_voice_id: nextFemale,
      comments: (targetBundle.comments || []).map((c, i) => ({
        ...c,
        voice_profile_id: useMulti ? pair[i % 2] : nextHost,
      })),
    };
  };

  useEffect(() => {
    if (bundle) {
      setBundle((prev) =>
        applyTwoMainVoicesToBundle(prev, hostVoiceId, maleVoiceId, femaleVoiceId, multiVoiceCast)
      );
    }
  }, [femaleVoiceId, maleVoiceId, opSpeakerGender, multiVoiceCast]);

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
          femaleVoiceId,
          maleVoiceId,
          opSpeakerGender,
          voiceSpeed,
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
    femaleVoiceId,
    maleVoiceId,
    opSpeakerGender,
    voiceSpeed,
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
    const cleanUrl = postUrl.trim();
    const cleanRaw = rawPastedText.trim();
    const nextErrs = {};

    if (!cleanUrl && cleanRaw.length < 10) {
      if (!cleanRaw) {
        nextErrs.postUrl =
          'Vui lòng dán link bài viết Threads / Reddit công khai, hoặc nhập văn bản dự phòng ở ô bên dưới.';
      } else {
        nextErrs.rawPastedText =
          'Văn bản dự phòng quá ngắn (cần tối thiểu 10 ký tự gồm nội dung bài viết hoặc các bình luận).';
      }
    } else if (cleanUrl) {
      if (!isValidHttpUrl(cleanUrl)) {
        nextErrs.postUrl =
          'Đường dẫn chưa hợp lệ — vui lòng dán link đầy đủ bắt đầu bằng https://www.threads.com/... hoặc https://www.reddit.com/...';
      } else if (isVideoOnlyPlatformUrl(cleanUrl)) {
        nextErrs.postUrl =
          'Đây là link Video (YouTube/TikTok). Nếu muốn tải làm Video Nền hãy dán xuống Bước 2; ô này dành cho link bài viết Threads / Reddit.';
      }
    }

    if (Object.keys(nextErrs).length > 0) {
      setErrors((prev) => ({ ...prev, ...nextErrs }));
      scrollToFirstValidationError(rootRef);
      notify(Object.values(nextErrs)[0]);
      return;
    }

    const safeMax = Math.min(15, Math.max(2, Math.round(Number(maxComments) || 6)));
    setMaxComments(safeMax);
    setErrors((prev) => {
      const copy = { ...prev };
      delete copy.postUrl;
      delete copy.rawPastedText;
      delete copy.topicTitle;
      delete copy.opDisplay;
      delete copy.opSpoken;
      delete copy.comments;
      return copy;
    });

    setExtracting(true);
    try {
      const res = await studioApi.extractThreadsPost({
        post_url: cleanUrl,
        raw_pasted_text: cleanRaw,
        max_comments: safeMax,
        filter_vibe: filterVibe,
        expand_slang_and_translate: expandSlang,
        anonymize_handles: Boolean(layoutConfig.threads_anonymize_handles),
        multi_voice_cast: multiVoiceCast,
        host_voice_id: hostVoiceId,
        male_voice_id: maleVoiceId,
        female_voice_id: femaleVoiceId,
      });
      setBundle(res);
      const imgCount =
        (res.op_image_path ? 1 : 0) +
        (res.comments || []).filter((c) => Boolean(c.attached_image_path)).length;
      notify(
        imgCount > 0
          ? `Đã hút thành công bài viết + ${res.comments?.length || 0} bình luận (lấy được ${imgCount} ảnh đính kèm thực tế)!`
          : `Đã lọc ${res.comments?.length || 0} bình luận tiêu biểu & gán đúng 2 giọng chính Nam/Nữ!`
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
      const res = await studioApi.previewVoice(
        vId || hostVoiceId,
        text.trim(),
        Number(voiceSpeed),
        0.0
      );
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

  const handleAttachCardImage = async (targetKey, fileObj) => {
    if (!fileObj) return;
    if (!hasAllowedExtension(fileObj.name, ['.jpg', '.jpeg', '.png', '.webp', '.gif'])) {
      notify('Vui lòng chọn tệp hình ảnh hợp lệ (.jpg, .png, .webp).');
      return;
    }
    if (fileObj.size > 25 * 1024 * 1024) {
      notify('Ảnh đính kèm quá lớn (tối đa 25MB).');
      return;
    }
    setUploadingCardImgKey(targetKey);
    try {
      const up = await studioApi.uploadStudioFile(fileObj, 'threads_media');
      if (targetKey === 'OP') {
        setBundle((prev) =>
          prev
            ? {
                ...prev,
                op_image_path: up.local_path,
                op_image_media_url: up.media_url,
              }
            : prev
        );
      } else {
        const idx = Number(targetKey);
        patchComment(idx, {
          attached_image_path: up.local_path,
          attached_image_media_url: up.media_url,
        });
      }
      notify('Đã đính kèm hình ảnh vào thẻ Threads!');
    } catch (err) {
      notify(`Lỗi tải ảnh thẻ: ${err.message}`);
    } finally {
      setUploadingCardImgKey('');
    }
  };

  const patchComment = (idx, patchObj) => {
    clearError('comments');
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
    setBundle((prev) => {
      const curList = prev?.comments || [];
      const nextIdx = curList.length + 1;
      const nextVoice = nextIdx % 2 === 1 ? maleVoiceId : femaleVoiceId;
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
        attached_image_url: '',
        attached_image_path: '',
        attached_image_media_url: '',
        is_verified: false,
        is_ai_suggested: false,
        voice_profile_id: nextVoice,
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
          op_image_url: '',
          op_image_path: '',
          op_image_media_url: '',
          op_likes_display: '1,5K',
          op_replies_display: '45',
          op_is_verified: true,
          op_voice_profile_id: hostVoiceId,
          male_voice_id: maleVoiceId,
          female_voice_id: femaleVoiceId,
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
    if (!hasAllowedExtension(f.name, ['.mp4', '.mov', '.mkv', '.webm', '.avi', '.m4v'])) {
      setErrors((prev) => ({
        ...prev,
        bgVideo: 'Định dạng chưa hỗ trợ — vui lòng chọn tệp video (.mp4, .mov, .webm, .mkv).',
      }));
      notify('Vui lòng chọn tệp video hợp lệ (.mp4, .mov, .webm, .mkv).');
      return;
    }
    clearError('bgVideo', 'bgUrl');
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
    if (!isValidHttpUrl(clean)) {
      const msg = 'Vui lòng dán link video YouTube / TikTok hợp lệ (bắt đầu bằng https://...).';
      setErrors((prev) => ({ ...prev, bgUrl: msg }));
      scrollToFirstValidationError(rootRef);
      notify(msg);
      return;
    }
    clearError('bgUrl', 'bgVideo');
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
    const nextErrs = {};
    if (!bundle) {
      nextErrs.postUrl =
        'Vui lòng bấm nút "Hút bài viết, Ảnh & Lọc bình luận" ở Bước 1A để tạo danh sách thẻ trước khi xuất video.';
    } else {
      const cleanTopic = (bundle.topic_title || '').trim();
      if (cleanTopic.length < 3 || cleanTopic.length > 160) {
        nextErrs.topicTitle = 'Tiêu đề SEO của dự án cần từ 3 đến 160 ký tự.';
      }
      if ((bundle.op_display_text || '').trim().length < 2) {
        nextErrs.opDisplay = 'Chữ hiển thị trên Thẻ Bài Gốc (OP) cần ít nhất 2 ký tự.';
      }
      if ((bundle.op_spoken_vi_text || '').trim().length < 2) {
        nextErrs.opSpoken = 'Lời đọc tiếng Việt của Bài Gốc (OP) cần ít nhất 2 ký tự.';
      }
      const selectedComments = (bundle.comments || []).filter((c) => c.selected);
      if (selectedComments.length === 0) {
        nextErrs.comments = 'Vui lòng tích chọn ít nhất 1 thẻ bình luận để đưa vào video.';
      } else if (
        selectedComments.some(
          (c) => !(c.display_text || '').trim() || !(c.spoken_vi_text || '').trim()
        )
      ) {
        nextErrs.comments =
          'Có bình luận đang được tích chọn nhưng bị để trống chữ hiển thị hoặc lời đọc tiếng Việt.';
      }
    }

    const effBg = selectedBgPath.trim() || bgUrlInput.trim();
    if (!effBg) {
      nextErrs.bgVideo =
        'Bắt buộc chọn 1 Video Nền từ Kho, tải tệp video lên, hoặc dán link video nền ở Bước 2.';
    } else if (!selectedBgPath.trim() && !isValidHttpUrl(bgUrlInput)) {
      nextErrs.bgUrl = 'Link video nền ở Bước 2 chưa hợp lệ (cần bắt đầu bằng https://...).';
    }

    if (Object.keys(nextErrs).length > 0) {
      setErrors(nextErrs);
      scrollToFirstValidationError(rootRef);
      notify(Object.values(nextErrs)[0]);
      return;
    }

    const safeSpeed = Math.min(1.45, Math.max(1.0, Number(voiceSpeed) || 1.25));
    const normalizedBundle = {
      ...bundle,
      topic_title: (bundle.topic_title || '').trim(),
      op_author_handle: (bundle.op_author_handle || '@chuthot').trim() || '@chuthot',
      op_display_text: (bundle.op_display_text || '').trim(),
      op_spoken_vi_text: (bundle.op_spoken_vi_text || '').trim(),
      op_voice_profile_id: bundle.op_voice_profile_id || hostVoiceId,
      male_voice_id: maleVoiceId,
      female_voice_id: femaleVoiceId,
      comments: (bundle.comments || []).map((c, idx) => ({
        ...c,
        author_handle: (c.author_handle || `@thanhvien_${idx + 1}`).trim(),
        display_text: (c.display_text || '').trim(),
        spoken_vi_text: (c.spoken_vi_text || c.display_text || '').trim(),
      })),
    };

    setErrors({});
    setSubmitting(true);
    try {
      const isRemote = effBg.startsWith('http://') || effBg.startsWith('https://');
      const res = await studioApi.startThreadsProject({
        bundle: normalizedBundle,
        bg_source_type: isRemote ? 'VIDEO_URL' : 'LOCAL_FILE',
        bg_path_or_url: effBg,
        save_bg_to_library: false,
        bg_library_title: bgCustomTitle.trim(),
        keep_bg_audio: keepBgAudio,
        bg_audio_volume: Number(bgAudioVolume),
        append_cta_comment: appendCtaComment.trim(),
        enable_card_pop_sfx: enablePopSfx,
        voice_profile_id: normalizedBundle.op_voice_profile_id,
        voice_speed_global: safeSpeed,
        voice_pitch_global: 0.0,
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
  const attachedPhotosCount =
    (bundle?.op_image_path ? 1 : 0) +
    (bundle?.comments || []).filter((c) => c.selected && Boolean(c.attached_image_path)).length;
  const estTotalSec = bundle
    ? Math.max(
        10,
        Math.round(
          ((bundle.op_spoken_vi_text || '').split(/\s+/).length +
            (bundle.comments || [])
              .filter((c) => c.selected)
              .reduce((acc, c) => acc + (c.spoken_vi_text || '').split(/\s+/).length, 0)) /
            (2.85 * Math.max(1.0, Number(voiceSpeed)))
        ) +
          selectedCommentsCount +
          2
      )
    : Math.round((maxComments * 6 + 5) / Math.max(1.0, Number(voiceSpeed)));

  return (
    <div ref={rootRef} className="card">
      <div className="page-header">
        <div>
          <div className="page-title">
            <MessageSquareText size={20} strokeWidth={2} /> Video Chủ Đề Threads &amp; Bình Luận Cộng Đồng
          </div>
          <div className="page-subtitle">
            Hút bài viết, bình luận &amp; ảnh đính kèm trên Threads/Reddit → Đọc đối thoại 2 giọng chính Nam &amp; Nữ tốc độ cao trên nền video 9:16
          </div>
        </div>
        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', alignItems: 'center' }}>
          <span className={`badge ${apiKeyConfigured ? 'badge-ok' : 'badge-warn'}`}>
            <KeyRound size={12} /> {apiKeyConfigured ? 'API Key AI sẵn sàng' : 'Chưa gắn API Key'}
          </span>
          <span className="badge badge-info">
            {bundle ? `Đã chọn ${selectedCommentsCount} bình luận` : `Lấy ${maxComments} bình luận`}
          </span>
          {attachedPhotosCount > 0 && (
            <span className="badge badge-ok">{attachedPhotosCount} ảnh đính kèm</span>
          )}
          <span className="badge">
            {Number(voiceSpeed).toFixed(2)}x • ~{estTotalSec}s
          </span>
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

      {/* STEP 1: THREADS LINK + 2 MAIN VOICES + FAST READING SPEED */}
      <div className="step-box">
        <div className="step-header">
          <span className="step-num">1</span>
          <div style={{ flex: 1 }}>
            <div className="step-title">
              Dán Link Threads / Reddit, Hút Cả Ảnh Bình Luận &amp; Chỉnh 2 Giọng Chính (Nam / Nữ)
            </div>
            <div className="step-desc">
              Tự động bóc tách cả ảnh người dùng đăng kèm trên bài gốc &amp; dưới bình luận, đọc bằng đúng 2 giọng Việt bản ngữ ổn định
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
            Đường dẫn bài đăng Threads / Reddit / Diễn đàn (hỗ trợ cả link rút gọn <code>/share/...</code>)
          </label>
          <input
            className={`input ${errors.postUrl ? 'input-error' : ''}`}
            placeholder="VD: https://www.threads.com/share/... hoặc https://www.threads.net/@ten_tai_khoan/post/..."
            value={postUrl}
            onChange={(e) => {
              setPostUrl(e.target.value);
              clearError('postUrl', 'rawPastedText');
            }}
          />
          <FieldError message={errors.postUrl} />
        </div>

        <div className="form-group">
          <label className="form-label">
            Nội dung văn bản dự phòng (Tùy chọn — Dán thêm nếu bài riêng tư)
          </label>
          <textarea
            className={`textarea ${errors.rawPastedText ? 'input-error' : ''}`}
            style={{ minHeight: 74 }}
            placeholder={`Có thể để trống nếu đã dán link công khai ở trên...`}
            value={rawPastedText}
            onChange={(e) => {
              setRawPastedText(e.target.value);
              clearError('rawPastedText', 'postUrl');
            }}
          />
          <FieldError message={errors.rawPastedText} />
        </div>

        {/* STRICT 2 MAIN VOICES (NAM & NỮ) + FAST READING SPEED CONTROL */}
        <div
          className="surface-box"
          style={{
            marginBottom: 14,
            borderColor: 'var(--brand-border)',
            background: 'var(--bg-panel)',
          }}
        >
          <div
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              gap: 8,
              flexWrap: 'wrap',
              marginBottom: 10,
            }}
          >
            <div style={{ fontWeight: 700, fontSize: 13.4, display: 'flex', alignItems: 'center', gap: 6 }}>
              <Users size={15} style={{ color: 'var(--brand-text)' }} />
              Bộ Đôi 2 Giọng Đọc Chính Cố Định (1 Nữ &amp; 1 Nam Chuẩn Tiếng Việt) &amp; Tốc Độ Đọc
            </div>
            <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
              <button
                type="button"
                className={`btn btn-sm ${opSpeakerGender === 'FEMALE' ? 'btn-primary' : 'btn-secondary'}`}
                onClick={() => setOpSpeakerGender('FEMALE')}
              >
                Chủ thớt (OP): Giọng Nữ đọc
              </button>
              <button
                type="button"
                className={`btn btn-sm ${opSpeakerGender === 'MALE' ? 'btn-primary' : 'btn-secondary'}`}
                onClick={() => setOpSpeakerGender('MALE')}
              >
                Chủ thớt (OP): Giọng Nam đọc
              </button>
            </div>
          </div>

          <div className="form-grid" style={{ marginBottom: 12 }}>
            <div>
              <label className="form-label" style={{ fontSize: 12 }}>
                Giọng Nữ Chính (Đọc tự nhiên, truyền cảm)
              </label>
              <div style={{ display: 'flex', gap: 6 }}>
                <select
                  className="select"
                  style={{ flex: 1 }}
                  value={femaleVoiceId}
                  onChange={(e) => setFemaleVoiceId(e.target.value)}
                >
                  {(femaleVoiceOptions.length > 0 ? femaleVoiceOptions : voices).map((v) => (
                    <option key={v.profile_id} value={v.profile_id}>
                      {stripLeadingEmoji(v.display_name)}
                    </option>
                  ))}
                </select>
                <button
                  type="button"
                  className="btn btn-secondary btn-sm"
                  style={{ whiteSpace: 'nowrap' }}
                  onClick={() =>
                    handlePreviewVoiceSnippet(
                      'test_female',
                      femaleVoiceId,
                      'Mình đã hí hoáy một tiếng với cây đàn Guitar và mình sắp khóc rồi mọi người ơi!'
                    )
                  }
                >
                  {previewingAudioKey === 'test_female' ? (
                    <Loader2 size={13} />
                  ) : (
                    <Volume2 size={13} />
                  )}{' '}
                  Nghe Nữ
                </button>
              </div>
            </div>

            <div>
              <label className="form-label" style={{ fontSize: 12 }}>
                Giọng Nam Chính (Ấm rõ, dứt khoát)
              </label>
              <div style={{ display: 'flex', gap: 6 }}>
                <select
                  className="select"
                  style={{ flex: 1 }}
                  value={maleVoiceId}
                  onChange={(e) => setMaleVoiceId(e.target.value)}
                >
                  {(maleVoiceOptions.length > 0 ? maleVoiceOptions : voices).map((v) => (
                    <option key={v.profile_id} value={v.profile_id}>
                      {stripLeadingEmoji(v.display_name)}
                    </option>
                  ))}
                </select>
                <button
                  type="button"
                  className="btn btn-secondary btn-sm"
                  style={{ whiteSpace: 'nowrap' }}
                  onClick={() =>
                    handlePreviewVoiceSnippet(
                      'test_male',
                      maleVoiceId,
                      'Không hề muộn đâu bạn ơi, tập hai mươi phút mỗi tối là đệm hát ngon lành ngay!'
                    )
                  }
                >
                  {previewingAudioKey === 'test_male' ? (
                    <Loader2 size={13} />
                  ) : (
                    <Volume2 size={13} />
                  )}{' '}
                  Nghe Nam
                </button>
              </div>
            </div>
          </div>

          <div className="form-grid">
            <div>
              <div
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  fontSize: 12.4,
                  marginBottom: 4,
                }}
              >
                <span style={{ fontWeight: 700, display: 'inline-flex', alignItems: 'center', gap: 5 }}>
                  <Gauge size={14} style={{ color: 'var(--brand-text)' }} />
                  Tốc độ đọc cuốn hút: <strong>{Number(voiceSpeed).toFixed(2)}x</strong>
                </span>
                <div style={{ display: 'flex', gap: 4 }}>
                  {SPEED_PRESETS.map((sp) => (
                    <button
                      key={sp.val}
                      type="button"
                      className={`btn btn-sm ${
                        Math.abs(Number(voiceSpeed) - sp.val) < 0.02 ? 'btn-primary' : 'btn-secondary'
                      }`}
                      style={{ padding: '2px 7px', minHeight: 24, fontSize: 11 }}
                      onClick={() => setVoiceSpeed(sp.val)}
                    >
                      {sp.val}x
                    </button>
                  ))}
                </div>
              </div>
              <input
                type="range"
                min="1.00"
                max="1.45"
                step="0.05"
                style={{ width: '100%' }}
                value={voiceSpeed}
                onChange={(e) => setVoiceSpeed(parseFloat(e.target.value))}
              />
              <div
                className="text-muted"
                style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11.2, marginTop: 2 }}
              >
                <span>1.00x Chậm</span>
                <span>1.25x Nhanh bắt tai Shorts/TikTok</span>
                <span>1.45x Cực nhanh</span>
              </div>
            </div>

            <div>
              <label className="form-label" style={{ marginBottom: 4, fontSize: 12.4 }}>
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
                style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11.2, marginTop: 2 }}
              >
                <span>2 câu (~15s)</span>
                <span>6–8 câu (Chuẩn ~45s)</span>
                <span>15 câu (~95s)</span>
              </div>
            </div>
          </div>
        </div>

        <div className="form-group">
          <label className="form-label">Tiêu chí AI chọn lọc bình luận tiêu biểu</label>
          <ModeChoiceGrid options={VIBE_CHOICES} value={filterVibe} onChange={setFilterVibe} />
        </div>

        <div className="toggle-grid" style={{ marginBottom: 14 }}>
          <SwitchCard icon={Languages} checked={expandSlang} onChange={setExpandSlang}>
            Bung viết tắt teen-code (ko→không, đc→được) &amp; lọc sạch icon rác
          </SwitchCard>
          <SwitchCard icon={Users} checked={multiVoiceCast} onChange={setMultiVoiceCast}>
            Đan xen đối thoại chỉ dùng 2 Giọng Chính (Nam ↔ Nữ)
          </SwitchCard>
          <SwitchCard
            icon={EyeOff}
            checked={Boolean(layoutConfig.threads_anonymize_handles)}
            onChange={(val) => updateThreadsLayout({ threads_anonymize_handles: val })}
          >
            Che ẩn tên tài khoản (nguoila_01)
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
              Bước 1A: Hút bài viết, ảnh bình luận &amp; chọn ra {maxComments} phản hồi đắt giá nhất
            </div>
            <div className="text-sub" style={{ fontSize: 12.2, marginTop: 2 }}>
              Tự động giữ lại ảnh chụp dưới các bình luận và hiển thị ngay bên dưới để bạn duyệt trước khi ghép video
            </div>
          </div>
          <button
            type="button"
            className="btn btn-primary"
            style={{ minHeight: 41, fontWeight: 700 }}
            disabled={extracting || submitting}
            onClick={handleExtractThreads}
          >
            {extracting ? <Loader2 size={16} className="spin" /> : <Wand2 size={16} />}
            <span>
              {extracting
                ? 'Đang hút bài, ảnh & lọc bình luận...'
                : `Hút bài viết, Ảnh & Lọc ${maxComments} bình luận`}
            </span>
          </button>
        </div>

        <StudioLoadingBanner
          loading={extracting}
          showSkeleton={!bundle}
          title="Đang hút bài viết, tải Avatar tròn & lọc bình luận tiêu biểu bằng AI..."
          subtitle="Hệ thống đang tải song song ảnh đại diện, ảnh bình luận & phân vai đối thoại 2 giọng chính"
          steps={[
            'Kết nối bài viết Threads / Reddit',
            'Tải Avatar người dùng & Ảnh bình luận',
            'AI chọn lọc & bung viết tắt tiếng Việt',
          ]}
          stepIntervalMs={2800}
        />

        {/* INTERACTIVE CURATED THREAD & COMMENTS EDITOR (WITH ATTACHED PHOTOS!) */}
        {bundle && (
          <div
            className={extracting ? 'is-reloading-dim' : 'fade-slide-in'}
            style={{ marginTop: 15, display: 'grid', gap: 12 }}
          >
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
                  <span
                    style={{
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: 8,
                    }}
                  >
                    {bundle.op_avatar_media_url && !layoutConfig.threads_anonymize_handles && (
                      <img
                        src={bundle.op_avatar_media_url}
                        alt="OP Avatar"
                        style={{
                          width: 30,
                          height: 30,
                          borderRadius: '50%',
                          objectFit: 'cover',
                          border: '1.5px solid var(--brand)',
                        }}
                      />
                    )}
                    <span className="badge badge-info">Thẻ mở đầu • Bài đăng gốc (OP)</span>
                  </span>
                  <div style={{ display: 'flex', gap: 6, alignItems: 'center', flexWrap: 'wrap' }}>
                    <input
                      className="input"
                      style={{ width: 150, minHeight: 31, padding: '4px 9px', fontSize: 12.3 }}
                      value={bundle.op_author_handle}
                      onChange={(e) =>
                        setBundle((prev) => ({ ...prev, op_author_handle: e.target.value }))
                      }
                      title="Tên tài khoản hiển thị trên thẻ OP"
                    />
                    <input
                      className="input"
                      style={{ width: 78, minHeight: 31, padding: '4px 8px', fontSize: 12.3 }}
                      value={bundle.op_likes_display}
                      onChange={(e) =>
                        setBundle((prev) => ({ ...prev, op_likes_display: e.target.value }))
                      }
                      title="Số lượt tim hiển thị"
                    />
                    <button
                      type="button"
                      className="btn btn-secondary btn-sm"
                      style={{ minHeight: 31 }}
                      onClick={() => {
                        const nextId =
                          (bundle.op_voice_profile_id || hostVoiceId) === femaleVoiceId
                            ? maleVoiceId
                            : femaleVoiceId;
                        setBundle((prev) => ({ ...prev, op_voice_profile_id: nextId }));
                      }}
                    >
                      {(bundle.op_voice_profile_id || hostVoiceId) === maleVoiceId
                        ? 'Giọng Nam Chính'
                        : 'Giọng Nữ Chính'}
                    </button>
                    <button
                      type="button"
                      className="btn btn-secondary btn-sm"
                      style={{ minHeight: 31 }}
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
                    <label
                      className="btn btn-secondary btn-sm"
                      style={{ minHeight: 31, cursor: 'pointer' }}
                      title="Đính kèm hoặc đổi ảnh trong thẻ bài đăng gốc"
                    >
                      {uploadingCardImgKey === 'OP' ? (
                        <Loader2 size={13} />
                      ) : (
                        <ImagePlus size={13} />
                      )}{' '}
                      Ảnh bài gốc
                      <input
                        type="file"
                        accept="image/*"
                        hidden
                        onChange={(e) => {
                          const f = e.target.files?.[0];
                          if (f) handleAttachCardImage('OP', f);
                          e.target.value = '';
                        }}
                      />
                    </label>
                  </div>
                </div>

                <div className="form-group" style={{ marginBottom: 8 }}>
                  <label className="form-label" style={{ fontSize: 12 }}>
                    Tiêu đề SEO của dự án video
                  </label>
                  <input
                    className={`input ${errors.topicTitle ? 'input-error' : ''}`}
                    style={{ minHeight: 35 }}
                    value={bundle.topic_title}
                    onChange={(e) => {
                      setBundle((prev) => ({ ...prev, topic_title: e.target.value }));
                      clearError('topicTitle');
                    }}
                  />
                  <FieldError message={errors.topicTitle} />
                </div>

                <div className="form-grid">
                  <div>
                    <label className="form-label" style={{ fontSize: 11.8 }}>
                      Chữ hiển thị trên Thẻ Bài Gốc
                    </label>
                    <textarea
                      className={`textarea ${errors.opDisplay ? 'input-error' : ''}`}
                      style={{ minHeight: 66, fontSize: 13 }}
                      value={bundle.op_display_text}
                      onChange={(e) => {
                        setBundle((prev) => ({ ...prev, op_display_text: e.target.value }));
                        clearError('opDisplay');
                      }}
                    />
                    <FieldError message={errors.opDisplay} />
                  </div>
                  <div>
                    <label className="form-label" style={{ fontSize: 11.8 }}>
                      Lời đọc giọng Việt ({Number(voiceSpeed).toFixed(2)}x)
                    </label>
                    <textarea
                      className={`textarea ${errors.opSpoken ? 'input-error' : ''}`}
                      style={{ minHeight: 66, fontSize: 13 }}
                      value={bundle.op_spoken_vi_text}
                      onChange={(e) => {
                        setBundle((prev) => ({ ...prev, op_spoken_vi_text: e.target.value }));
                        clearError('opSpoken');
                      }}
                    />
                    <FieldError message={errors.opSpoken} />
                  </div>
                </div>

                {(bundle.op_image_media_url || bundle.op_image_path) && (
                  <div
                    style={{
                      marginTop: 8,
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: 10,
                      padding: 6,
                      borderRadius: 8,
                      background: 'var(--bg-step)',
                      border: '1px solid var(--border-strong)',
                    }}
                  >
                    {bundle.op_image_media_url && (
                      <img
                        src={bundle.op_image_media_url}
                        alt="OP attachment"
                        style={{
                          width: 68,
                          height: 68,
                          objectFit: 'cover',
                          borderRadius: 6,
                        }}
                      />
                    )}
                    <span style={{ fontSize: 12, fontWeight: 600 }}>
                      Ảnh đính kèm hiển thị trong Thẻ Bài Gốc
                    </span>
                    <button
                      type="button"
                      className="btn btn-danger btn-sm"
                      style={{ padding: '2px 7px', minHeight: 26 }}
                      onClick={() =>
                        setBundle((prev) => ({
                          ...prev,
                          op_image_path: '',
                          op_image_url: '',
                          op_image_media_url: '',
                        }))
                      }
                    >
                      <X size={12} /> Bỏ ảnh
                    </button>
                  </div>
                )}
              </div>

              {/* COMMENTS LIST */}
              <FieldError message={errors.comments} />
              <div style={{ display: 'grid', gap: 9, maxHeight: 500, overflowY: 'auto', paddingRight: 3 }}>
                {(bundle.comments || []).map((cmt, idx) => {
                  const pKey = `cmt_${idx}`;
                  const isMaleLine = (cmt.voice_profile_id || hostVoiceId) === maleVoiceId;
                  const hasCmtImg = Boolean(cmt.attached_image_media_url || cmt.attached_image_path);
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
                          {cmt.avatar_media_url && !layoutConfig.threads_anonymize_handles && (
                            <img
                              src={cmt.avatar_media_url}
                              alt={cmt.author_handle}
                              style={{
                                width: 26,
                                height: 26,
                                borderRadius: '50%',
                                objectFit: 'cover',
                                border: '1px solid var(--border-strong)',
                              }}
                            />
                          )}
                          <span>Thẻ trả lời {idx + 1}</span>
                          {hasCmtImg && (
                            <span className="badge badge-ok" style={{ fontSize: 10.5, padding: '1px 6px' }}>
                              Có ảnh bình luận
                            </span>
                          )}
                          {cmt.is_ai_suggested && (
                            <span className="badge badge-warn" style={{ fontSize: 10.5, padding: '1px 6px' }}>
                              Gợi ý AI
                            </span>
                          )}
                        </label>

                        <div style={{ display: 'flex', gap: 5, alignItems: 'center', flexWrap: 'wrap' }}>
                          <input
                            className="input"
                            style={{ width: 138, minHeight: 30, padding: '3px 8px', fontSize: 12.2 }}
                            value={cmt.author_handle}
                            onChange={(e) => patchComment(idx, { author_handle: e.target.value })}
                            title="Tên tài khoản bình luận"
                          />
                          <input
                            className="input"
                            style={{ width: 68, minHeight: 30, padding: '3px 7px', fontSize: 12.2 }}
                            value={cmt.likes_display}
                            onChange={(e) => patchComment(idx, { likes_display: e.target.value })}
                            title="Số lượt thích"
                          />
                          <button
                            type="button"
                            className="btn btn-secondary btn-sm"
                            style={{ minHeight: 30, padding: '0 9px', fontSize: 11.8 }}
                            title="Bấm để đổi nhanh giữa Giọng Nam Chính và Giọng Nữ Chính"
                            onClick={() =>
                              patchComment(idx, {
                                voice_profile_id: isMaleLine ? femaleVoiceId : maleVoiceId,
                              })
                            }
                          >
                            {isMaleLine ? 'Giọng Nam Chính' : 'Giọng Nữ Chính'}
                          </button>
                          <button
                            type="button"
                            className="btn btn-secondary btn-sm"
                            style={{ padding: '0 8px', minHeight: 30 }}
                            title="Nghe thử giọng đọc bình luận này ở tốc độ đã chọn"
                            onClick={() =>
                              handlePreviewVoiceSnippet(
                                pKey,
                                isMaleLine ? maleVoiceId : femaleVoiceId,
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
                          <label
                            className="btn btn-secondary btn-sm"
                            style={{ padding: '0 7px', minHeight: 30, cursor: 'pointer' }}
                            title="Đính kèm hoặc đổi ảnh trong bình luận này"
                          >
                            {uploadingCardImgKey === String(idx) ? (
                              <Loader2 size={12} />
                            ) : (
                              <ImagePlus size={12} />
                            )}
                            <input
                              type="file"
                              accept="image/*"
                              hidden
                              onChange={(e) => {
                                const f = e.target.files?.[0];
                                if (f) handleAttachCardImage(String(idx), f);
                                e.target.value = '';
                              }}
                            />
                          </label>
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
                          placeholder="Lời đọc giọng Việt (đã bung viết tắt)..."
                          value={cmt.spoken_vi_text}
                          onChange={(e) => patchComment(idx, { spoken_vi_text: e.target.value })}
                        />
                      </div>

                      {hasCmtImg && (
                        <div
                          style={{
                            marginTop: 7,
                            display: 'inline-flex',
                            alignItems: 'center',
                            gap: 9,
                            padding: 5,
                            borderRadius: 8,
                            background: 'var(--bg-step)',
                            border: '1px solid rgba(16, 185, 129, 0.45)',
                          }}
                        >
                          {cmt.attached_image_media_url && (
                            <img
                              src={cmt.attached_image_media_url}
                              alt="Comment attachment"
                              style={{
                                width: 62,
                                height: 62,
                                objectFit: 'cover',
                                borderRadius: 6,
                              }}
                            />
                          )}
                          <span style={{ fontSize: 11.8, fontWeight: 600 }}>
                            Ảnh đính kèm của bình luận (sẽ hiển thị ngay bên trong thẻ)
                          </span>
                          <button
                            type="button"
                            className="btn btn-danger btn-sm"
                            style={{ padding: '2px 6px', minHeight: 24, fontSize: 11 }}
                            onClick={() =>
                              patchComment(idx, {
                                attached_image_path: '',
                                attached_image_url: '',
                                attached_image_media_url: '',
                              })
                            }
                          >
                            <X size={11} /> Bỏ ảnh
                          </button>
                        </div>
                      )}
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
                      clearError('bgVideo', 'bgUrl');
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

        <StudioLoadingBanner
          loading={uploadingBg || savingBgUrl}
          title={
            savingBgUrl
              ? 'Đang tải video nền từ liên kết trực tuyến vào Kho Video Nền...'
              : 'Đang tải tệp video nền lên máy chủ cục bộ...'
          }
          subtitle="Hệ thống đang kiểm tra khung hình & lưu sẵn để tái sử dụng 1 chạm"
          steps={[
            'Tải luồng video gốc',
            'Kiểm tra thông số FFprobe & lưu vào Kho Video Nền',
          ]}
          stepIntervalMs={3000}
        />

        <div className="form-grid" style={{ marginBottom: 12 }}>
          <div>
            <MediaDropzone
              accept="video/*"
              disabled={uploadingBg}
              loading={uploadingBg}
              error={errors.bgVideo}
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

          <div
            className="surface-box"
            style={{ display: 'flex', flexDirection: 'column', justifyContent: 'space-between', gap: 10 }}
          >
            <div>
              <label className="form-label">
                Hoặc dán link YouTube / TikTok để tải về làm Video Nền
              </label>
              <div style={{ display: 'flex', gap: 6 }}>
                <input
                  className={`input ${errors.bgUrl ? 'input-error' : ''}`}
                  style={{ flex: 1, minHeight: 37 }}
                  placeholder="https://www.youtube.com/shorts/... hoặc TikTok..."
                  value={bgUrlInput}
                  onChange={(e) => {
                    setBgUrlInput(e.target.value);
                    clearError('bgUrl', 'bgVideo');
                  }}
                />
                <button
                  type="button"
                  className="btn btn-secondary btn-sm"
                  style={{ minHeight: 37, whiteSpace: 'nowrap' }}
                  disabled={savingBgUrl}
                  onClick={handleDownloadBgFromUrl}
                >
                  {savingBgUrl ? <Loader2 size={14} className="spin" /> : <Plus size={14} />}
                  <span>{savingBgUrl ? 'Đang tải...' : 'Tải vào Kho'}</span>
                </button>
              </div>
              <FieldError message={errors.bgUrl} />
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
              Giao diện Thẻ Bình Luận Nổi (Gọn Đẹp Không Đánh Số), Tiếng Pop &amp; Nhạc Nền
            </div>
            <div className="step-desc">
              Thẻ bình luận hiển thị tự nhiên đúng giao diện Threads kèm ảnh đính kèm bên trong thẻ
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
                Tắt phụ đề dưới đáy (Khuyên dùng vì chữ &amp; ảnh đã hiện rõ trên Thẻ Threads)
              </option>
              <option value="KARAOKE_CAPCUT">Bật thêm chữ Karaoke chạy từng từ</option>
              <option value="CINEMA">Bật thêm phụ đề câu thanh lịch</option>
            </select>
            <div className="text-muted" style={{ fontSize: 11.8 }}>
              Mỗi thẻ bình luận nổi đã tự động căn chữ &amp; ảnh đính kèm ngay tầm mắt người xem, khớp từng mili-giây giọng đọc.
            </div>
          </div>
        </div>
      </div>

      <StudioLoadingBanner
        loading={submitting}
        title="Đang khởi tạo dự án Video Threads & đưa vào tiến trình dựng..."
        subtitle="Hệ thống đang chuẩn bị thẻ giao diện Threads nổi và bộ đôi 2 giọng đọc chính"
        steps={[
          'Kiểm tra dữ liệu bài đăng & bình luận',
          'Khởi động tiến trình tổng hợp giọng đọc & ghép khung 9:16',
        ]}
        stepIntervalMs={1800}
      />

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
            disabled={submitting || extracting || uploadingBg || savingBgUrl}
            onClick={() => handleStartThreadsVideo(false)}
          >
            {submitting ? <Loader2 size={15} className="spin" /> : <Edit3 size={15} />}{' '}
            Đưa sang Chờ duyệt kịch bản
          </button>
          <button
            type="button"
            className="btn btn-primary"
            style={{ minWidth: 245, minHeight: 42, fontSize: 14, fontWeight: 700 }}
            disabled={submitting || extracting || uploadingBg || savingBgUrl}
            onClick={() => handleStartThreadsVideo(true)}
          >
            {submitting ? <Loader2 size={16} className="spin" /> : <Play size={16} />}{' '}
            {submitting ? 'Đang khởi tạo dự án...' : 'Bắt đầu dựng Video Threads ngay'}
          </button>
        </div>
      </div>
    </div>
  );
}
