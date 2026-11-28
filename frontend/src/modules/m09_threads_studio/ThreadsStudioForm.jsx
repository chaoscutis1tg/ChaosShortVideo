import React, { useEffect, useRef, useState } from 'react';
import {
  ArrowDown,
  ArrowUp,
  ArrowUpWideNarrow,
  BookmarkPlus,
  BookOpen,
  CheckCircle2,
  Clock,
  Edit3,
  EyeOff,
  Film,
  Flame,
  Gauge,
  Heart,
  HelpCircle,
  ImagePlus,
  KeyRound,
  Languages,
  Layers,
  Link2,
  Loader2,
  MessageSquarePlus,
  MessageSquareText,
  Moon,
  Music,
  Play,
  Plus,
  SlidersHorizontal,
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
  StudioCollapsible,
  StudioLoadingBanner,
  StudioPageHeader,
  StudioStepFooter,
  StudioStepNav,
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
    value: 'LONG_STORY',
    title: 'Kể chuyện dài & Tâm sự sâu',
    subtitle: 'Săn các bình luận dài nhiều câu, kể chuyện đầu-cuối chi tiết nhất',
    icon: BookOpen,
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
    subtitle: 'Ưu tiên các phản hồi có lượng tương tác cao nhất',
    icon: ThumbsUp,
  },
];

const COMMENT_LENGTH_MODES = [
  {
    id: 'ALL',
    label: 'Mọi độ dài',
    preferLong: false,
    minChars: 0,
  },
  {
    id: 'MEDIUM_LONG',
    label: 'Vừa & dài (≥ 65 ký tự)',
    preferLong: true,
    minChars: 65,
  },
  {
    id: 'DEEP_STORY',
    label: 'Chuyện dài (≥ 105 ký tự)',
    preferLong: true,
    minChars: 105,
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
    subtitle: 'Nền trắng chuẩn Threads, gọn gàng hiện đại',
    icon: Sun,
  },
  {
    value: 'FROSTED_GLASS',
    title: 'Thẻ Kính Mờ Trong Suốt',
    subtitle: 'Hiệu ứng kính mờ hiện đại nhìn xuyên chuyển động video nền',
    icon: Layers,
  },
  {
    value: 'CHAT_MESSENGER_ZALO',
    title: 'Chat Messenger / Zalo Tối',
    subtitle: 'Khung điện thoại chat 2 chiều tự cuộn mượt, bong bóng đang nhập & tiếng Ting',
    icon: MessageSquareText,
  },
  {
    value: 'CHAT_IMESSAGE_LIGHT',
    title: 'Chat iMessage Sáng Tinh Tế',
    subtitle: 'Phong cách tin nhắn iPhone sáng thanh lịch cho chuyện Crush & tư vấn',
    icon: MessageSquarePlus,
  },
  {
    value: 'MIDNIGHT_VINYL_LYRIC',
    title: 'Đĩa Than Đêm Khuya & Lời Spotify',
    subtitle: 'Đĩa than xoay tròn + Sóng nhạc nhạy theo giọng + Lời chữ sáng rõ từng câu',
    icon: Music,
  },
  {
    value: 'QUIZ_COUNTDOWN_CARD',
    title: 'Đố Vui Phản Xạ 3 - 2 - 1',
    subtitle: 'Thẻ trắc nghiệm A/B/C kèm đồng hồ đếm ngược 3s tiếng Tích-tắc & Ding lật đáp án',
    icon: Clock,
  },
];

const QUIZ_CATEGORY_OPTIONS = [
  { id: 'MUSIC_EAR', label: 'Cảm âm & Kiến thức Nhạc cụ (Guitar / Violin / Piano)' },
  { id: 'CRUSH_LOVE', label: 'Giải mã tâm lý Tình cảm & Crush' },
  { id: 'PSYCHOLOGY_EQ', label: 'Tâm lý học & Phản xạ EQ sắc bén' },
  { id: 'FUN_TRIVIA', label: 'Đố vui kiến thức thú vị gây bất ngờ' },
];

const CHILL_BG_PRESETS = [
  { id: 'STARRY_LOFI_BOKEH', label: 'Đêm Sao Lofi & Đom Đóm' },
  { id: 'RAINY_WINDOW_NEON', label: 'Mưa Đêm Phố Thị Neon' },
  { id: 'SUNSET_OCEAN_WAVES', label: 'Hoàng Hôn Tím & Bụi Nắng' },
  { id: 'CYBER_SYNTH_GRID', label: 'Không Gian Đêm Tối Giản' },
];

const RADAR_NICHES = [
  { id: 'ALL_HOT', label: 'Đang Hot Nhất' },
  { id: 'CRUSH_LOVE', label: 'Tình cảm & Crush' },
  { id: 'CONFESSION_SECRET', label: 'Bí mật thầm kín' },
  { id: 'VN_COMMUNITY', label: 'Cộng đồng Việt' },
  { id: 'WORK_CAREER', label: 'Chuyện công sở' },
  { id: 'MUSIC_HOBBY', label: 'Nhạc cụ & Đam mê' },
];

const CHAT_VIBE_OPTIONS = [
  { id: 'CRUSH_ROMANTIC', label: 'Thả thính Crush / Rung động' },
  { id: 'DRAMA_PLOT_TWIST', label: 'Kịch tính & Lật kèo cuối bài' },
  { id: 'FUNNY_BANTER', label: 'Trêu nhau lầy lội hài hước' },
  { id: 'SALES_CONSULT', label: 'Khách hỏi — Shop tư vấn chốt đơn' },
];

const EYE_GUIDE_CHOICES = [
  {
    value: 'ACTIVE_HIGHLIGHT',
    title: 'Làm nổi câu đang đọc (Khuyên dùng)',
    subtitle: 'Giữ nguyên khung thẻ ổn định, câu đang đọc sáng 100% kèm vạch dẫn mắt',
    icon: Sparkles,
  },
  {
    value: 'PROGRESSIVE_REVEAL',
    title: 'Hiện dần từng câu theo giọng đọc',
    subtitle: 'Khung thẻ cố định không nhảy giật, chữ mở dần từng câu khớp nhịp thuyết minh',
    icon: MessageSquareText,
  },
  {
    value: 'STATIC_FULL',
    title: 'Hiện tĩnh toàn bộ thẻ',
    subtitle: 'Hiển thị đồng đều 100% toàn bộ văn bản từ lúc thẻ trượt lên đến khi chuyển thẻ',
    icon: Layers,
  },
];

const SPEED_PRESETS = [
  { label: '1.15x', val: 1.15 },
  { label: '1.25x', val: 1.25 },
  { label: '1.35x', val: 1.35 },
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
  onNavigateTab,
  showAllSteps = false,
  onToggleShowAllSteps,
  notify,
  apiKeyConfigured = false,
  onOpenApiSettings,
}) {
  const savedDraft = loadThreadsDraft();
  const rootRef = useRef(null);
  const previewPlayerRef = useRef(null);

  const [activeStep, setActiveStep] = useState(1);
  const [parentGroupId, setParentGroupId] = useState(savedDraft.parentGroupId || '');
  const [postUrl, setPostUrl] = useState(savedDraft.postUrl || '');
  const [rawPastedText, setRawPastedText] = useState(savedDraft.rawPastedText || '');
  const [maxComments, setMaxComments] = useState(savedDraft.maxComments || 6);
  const [filterVibe, setFilterVibe] = useState(savedDraft.filterVibe || 'FUNNY_VIRAL');
  const [commentLengthMode, setCommentLengthMode] = useState(
    savedDraft.commentLengthMode || 'ALL'
  );
  const [expandSlang, setExpandSlang] = useState(savedDraft.expandSlang !== false);
  const [multiVoiceCast, setMultiVoiceCast] = useState(savedDraft.multiVoiceCast !== false);

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
  const [batchMode, setBatchMode] = useState(false);
  const [chatStoryMode, setChatStoryMode] = useState(false);
  const [chatIdea, setChatIdea] = useState('');
  const [chatSenderA, setChatSenderA] = useState('Mình');
  const [chatSenderB, setChatSenderB] = useState('Crush');
  const [chatMsgCount, setChatMsgCount] = useState(8);
  const [chatVibe, setChatVibe] = useState('CRUSH_ROMANTIC');
  const [generatingChat, setGeneratingChat] = useState(false);

  const [quizMode, setQuizMode] = useState(false);
  const [quizTopic, setQuizTopic] = useState('');
  const [quizCategory, setQuizCategory] = useState('MUSIC_EAR');
  const [quizQuestionCount, setQuizQuestionCount] = useState(3);
  const [generatingQuiz, setGeneratingQuiz] = useState(false);
  const [generatingChillBg, setGeneratingChillBg] = useState('');
  const [seriesParts, setSeriesParts] = useState(1);

  const [radarOpen, setRadarOpen] = useState(false);
  const [radarNiche, setRadarNiche] = useState('ALL_HOT');
  const [radarItems, setRadarItems] = useState([]);
  const [loadingRadar, setLoadingRadar] = useState(false);
  const [hookScoreRes, setHookScoreRes] = useState(null);
  const [scoringHook, setScoringHook] = useState(false);
  const [batchUrlsText, setBatchUrlsText] = useState('');
  const [rotateBgLibrary, setRotateBgLibrary] = useState(true);
  const [rotateLofiBgm, setRotateLofiBgm] = useState(true);
  const [enableSmartSfx, setEnableSmartSfx] = useState(true);
  const [smartKeywordHighlight, setSmartKeywordHighlight] = useState(true);
  const [appendCtaComment, setAppendCtaComment] = useState(
    savedDraft.appendCtaComment !== undefined
      ? savedDraft.appendCtaComment
      : 'Còn góc nhìn của bạn về chủ đề này thì sao? Để lại bình luận bên dưới nhé!'
  );
  const [previewingAudioKey, setPreviewingAudioKey] = useState('');
  const [uploadingCardImgKey, setUploadingCardImgKey] = useState('');

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

  const [enablePopSfx, setEnablePopSfx] = useState(savedDraft.enablePopSfx !== false);
  const [subtitleStyle, setSubtitleStyle] = useState(savedDraft.subtitleStyle || 'NONE');
  const [bgmPresetId, setBgmPresetId] = useState(savedDraft.bgmPresetId || 'lofi_vanilla_chill');
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
    const t = setTimeout(() => {
      try {
        localStorage.setItem(
          THREADS_DRAFT_KEY,
          JSON.stringify({
            parentGroupId,
            postUrl,
            rawPastedText,
            maxComments,
            filterVibe,
            commentLengthMode,
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
            bgmPresetId,
          })
        );
      } catch {
        // ignore quota
      }
    }, 450);
    return () => clearTimeout(t);
  }, [
    parentGroupId,
    postUrl,
    rawPastedText,
    maxComments,
    filterVibe,
    commentLengthMode,
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
    bgmPresetId,
  ]);

  const updateThreadsLayout = (patch) => {
    if (setLayoutConfig) {
      setLayoutConfig((prev) => ({ ...prev, ...patch }));
    }
  };

  const handleLoadViralRadar = async (nextNiche = radarNiche) => {
    setRadarNiche(nextNiche);
    setRadarOpen(true);
    setLoadingRadar(true);
    try {
      const items = await studioApi.fetchViralRadar(nextNiche, 8);
      setRadarItems(items || []);
    } catch (err) {
      notify(`Lỗi quét Radar chủ đề: ${err.message}`);
    } finally {
      setLoadingRadar(false);
    }
  };

  const handleGenerateChatStory = async () => {
    const cleanIdea = chatIdea.trim();
    if (cleanIdea.length < 4) {
      setActiveStep(1);
      setErrors({
        chatIdea: 'Vui lòng nhập tình huống hoặc chủ đề cuộc trò chuyện (ít nhất 4 ký tự).',
      });
      notify('Vui lòng nhập tình huống tin nhắn Chat trước khi gọi AI.');
      return;
    }
    clearError('chatIdea');
    setGeneratingChat(true);
    try {
      const res = await studioApi.generateChatStory({
        story_idea: cleanIdea,
        sender_a_name: chatSenderA.trim() || 'Mình',
        sender_b_name: chatSenderB.trim() || 'Crush',
        message_count: Number(chatMsgCount) || 8,
        story_vibe: chatVibe,
        male_voice_id: maleVoiceId,
        female_voice_id: femaleVoiceId,
        sender_a_is_female: opSpeakerGender !== 'MALE',
      });
      setBundle(res);
      setHookScoreRes(null);
      if (
        layoutConfig.threads_card_theme !== 'CHAT_MESSENGER_ZALO' &&
        layoutConfig.threads_card_theme !== 'CHAT_IMESSAGE_LIGHT'
      ) {
        updateThreadsLayout({ threads_card_theme: 'CHAT_MESSENGER_ZALO' });
      }
      notify(
        `Đã dựng kịch bản ${(res.comments?.length || 0) + 1} tin nhắn Chat & bật sẵn giao diện Bong Bóng Chat!`
      );
    } catch (err) {
      notify(`Lỗi viết kịch bản Chat: ${err.message}`);
    } finally {
      setGeneratingChat(false);
    }
  };

  const handleScoreOpeningHook = async () => {
    if (!bundle) return;
    const hookTxt = (bundle.op_display_text || bundle.topic_title || '').trim();
    if (hookTxt.length < 3) {
      notify('Vui lòng nhập nội dung Thẻ mở đầu trước khi chấm điểm Hook.');
      return;
    }
    setScoringHook(true);
    try {
      const ctx = (bundle.comments || [])
        .slice(0, 3)
        .map((c) => c.display_text)
        .join(' | ');
      const res = await studioApi.scoreOpeningHook({
        hook_text: hookTxt,
        body_context: ctx,
        mode: 'THREADS_TOPIC',
      });
      setHookScoreRes(res);
      notify(`Điểm giữ chân 3 giây đầu: ${res.overall_score}/100 — Đã gợi ý 3 biến thể A/B!`);
    } catch (err) {
      notify(`Lỗi chấm điểm Hook: ${err.message}`);
    } finally {
      setScoringHook(false);
    }
  };

  const handleGenerateQuiz = async () => {
    setGeneratingQuiz(true);
    try {
      const cdSec = Number(layoutConfig.quiz_countdown_sec || 3);
      const res = await studioApi.generateQuizBundle({
        quiz_topic:
          quizTopic.trim() ||
          (quizCategory === 'MUSIC_EAR'
            ? 'Thử tài phân biệt âm sắc nhạc cụ và cảm âm'
            : quizCategory === 'CRUSH_LOVE'
            ? 'Giải mã tín hiệu tâm lý tinh tế của Crush'
            : 'Thử thách phản xạ tâm lý học trong 3 giây'),
        quiz_category: quizCategory,
        question_count: Number(quizQuestionCount) || 3,
        countdown_sec: cdSec,
        host_voice_id: femaleVoiceId,
        answer_voice_id: maleVoiceId,
      });
      setBundle(res);
      setHookScoreRes(null);
      updateThreadsLayout({ threads_card_theme: 'QUIZ_COUNTDOWN_CARD' });
      notify(
        `Đã tạo bộ ${quizQuestionCount} câu đố phản xạ kèm đồng hồ đếm ngược ${cdSec}s & tiếng Tích-tắc / Ding!`
      );
    } catch (err) {
      notify(`Lỗi tạo bộ câu đố: ${err.message}`);
    } finally {
      setGeneratingQuiz(false);
    }
  };

  const handleGenerateChillBg = async (presetId) => {
    setGeneratingChillBg(presetId);
    clearError('bgVideo', 'bgUrl');
    try {
      const saved = await studioApi.generateChillBgVideo({
        preset_id: presetId,
        duration_sec: 6,
      });
      await loadBgLibrary();
      setSelectedBgPath(saved.local_path);
      setSelectedBgPreviewUrl(saved.media_url || '');
      notify(`Đã tạo & chọn Video Nền Chill 9:16 sạch bản quyền: "${saved.title}"!`);
    } catch (err) {
      notify(`Lỗi tạo video nền Chill: ${err.message}`);
    } finally {
      setGeneratingChillBg('');
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
          'Đây là link Video (YouTube/TikTok). Nếu muốn tải làm Video Nền hãy sang Bước 2; ô này dành cho link bài viết Threads / Reddit.';
      }
    }

    if (Object.keys(nextErrs).length > 0) {
      setActiveStep(1);
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
      const lengthCfg =
        COMMENT_LENGTH_MODES.find((m) => m.id === commentLengthMode) || COMMENT_LENGTH_MODES[0];
      const res = await studioApi.extractThreadsPost({
        post_url: cleanUrl,
        raw_pasted_text: cleanRaw,
        max_comments: safeMax,
        filter_vibe: filterVibe,
        prefer_long_comments: Boolean(lengthCfg.preferLong || filterVibe === 'LONG_STORY'),
        min_comment_chars:
          filterVibe === 'LONG_STORY' ? Math.max(95, lengthCfg.minChars) : lengthCfg.minChars,
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
      const longCount = (res.comments || []).filter(
        (c) => (c.display_text || '').trim().length >= 95
      ).length;
      notify(
        longCount > 0
          ? `Đã hút thành công ${res.comments?.length || 0} bình luận (có ${longCount} bình luận kể chuyện dài${imgCount > 0 ? ` + ${imgCount} ảnh` : ''})!`
          : imgCount > 0
          ? `Đã hút thành công bài viết + ${res.comments?.length || 0} bình luận (${imgCount} ảnh đính kèm)!`
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
      setActiveStep(2);
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
    let errStep = null;

    if (!bundle) {
      nextErrs.postUrl =
        'Vui lòng bấm nút tạo / hút nội dung ở Bước 1 để lên danh sách thẻ trước khi xuất video.';
      errStep = 1;
    } else {
      const cleanTopic = (bundle.topic_title || '').trim();
      if (cleanTopic.length < 3 || cleanTopic.length > 160) {
        nextErrs.topicTitle = 'Tiêu đề SEO của dự án cần từ 3 đến 160 ký tự.';
        errStep = 1;
      }
      if ((bundle.op_display_text || '').trim().length < 2) {
        nextErrs.opDisplay = 'Chữ hiển thị trên Thẻ Bài Gốc (OP) cần ít nhất 2 ký tự.';
        errStep = 1;
      }
      if ((bundle.op_spoken_vi_text || '').trim().length < 2) {
        nextErrs.opSpoken = 'Lời đọc tiếng Việt của Bài Gốc (OP) cần ít nhất 2 ký tự.';
        errStep = 1;
      }
      const selectedComments = (bundle.comments || []).filter((c) => c.selected);
      if (selectedComments.length === 0) {
        nextErrs.comments = 'Vui lòng tích chọn ít nhất 1 thẻ bình luận để đưa vào video.';
        errStep = 1;
      } else if (
        selectedComments.some(
          (c) => !(c.display_text || '').trim() || !(c.spoken_vi_text || '').trim()
        )
      ) {
        nextErrs.comments =
          'Có bình luận đang được tích chọn nhưng bị để trống chữ hiển thị hoặc lời đọc tiếng Việt.';
        errStep = 1;
      }
    }

    const effBg = selectedBgPath.trim() || bgUrlInput.trim();
    if (!effBg) {
      nextErrs.bgVideo =
        'Bắt buộc chọn 1 Video Nền từ Kho, tạo Video Nền Chill 1 chạm, hoặc tải tệp lên ở Bước 2.';
      if (!errStep) errStep = 2;
    } else if (!selectedBgPath.trim() && !isValidHttpUrl(bgUrlInput)) {
      nextErrs.bgUrl = 'Link video nền ở Bước 2 chưa hợp lệ (cần bắt đầu bằng https://...).';
      if (!errStep) errStep = 2;
    }

    if (Object.keys(nextErrs).length > 0) {
      if (errStep) setActiveStep(errStep);
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
        enable_smart_sfx: enableSmartSfx,
        smart_keyword_highlight: smartKeywordHighlight,
        voice_profile_id: normalizedBundle.op_voice_profile_id,
        voice_speed_global: safeSpeed,
        voice_pitch_global: 0.0,
        bgm_preset_id: bgmPresetId,
        custom_bgm_path: customBgmPath,
        bgm_volume: Number(bgmVolume),
        subtitle_style: subtitleStyle,
        series_parts: Math.min(4, Math.max(1, Number(seriesParts) || 1)),
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

  const handleStartBatchThreads = async () => {
    const rawLines = batchUrlsText
      .split(/\r?\n/)
      .map((s) => s.trim())
      .filter(Boolean);
    const validUrls = rawLines.filter((u) => isValidHttpUrl(u) && !isVideoOnlyPlatformUrl(u));
    if (validUrls.length === 0) {
      setActiveStep(1);
      setErrors({
        batchUrls:
          'Vui lòng dán ít nhất 1 đường dẫn Threads hoặc Reddit hợp lệ (mỗi dòng 1 link https://...).',
      });
      scrollToFirstValidationError(rootRef);
      notify('Vui lòng dán danh sách link Threads hoặc Reddit cần chạy hàng loạt.');
      return;
    }
    if (validUrls.length > 15) {
      setActiveStep(1);
      setErrors({ batchUrls: 'Mỗi mẻ chạy tối đa 15 link để đảm bảo tốc độ và ổn định GPU.' });
      notify('Tối đa 15 link mỗi mẻ chạy.');
      return;
    }
    const effBg = selectedBgPath.trim() || bgUrlInput.trim();
    if (!effBg && (!rotateBgLibrary || bgLibrary.length === 0)) {
      setActiveStep(2);
      setErrors({
        bgVideo:
          'Vui lòng lưu ít nhất 1 Video Nền vào Kho hoặc chọn 1 Video Nền ở Bước 2 trước khi chạy hàng loạt.',
      });
      scrollToFirstValidationError(rootRef);
      notify('Chưa có Video Nền ở Bước 2 để chạy hàng loạt.');
      return;
    }

    const lenCfg =
      COMMENT_LENGTH_MODES.find((m) => m.id === commentLengthMode) || COMMENT_LENGTH_MODES[0];
    const safeSpeed = Math.min(1.45, Math.max(1.0, Number(voiceSpeed) || 1.25));
    setErrors({});
    setSubmitting(true);
    try {
      const res = await studioApi.startThreadsBatch({
        urls: validUrls,
        max_comments: Math.min(20, Math.max(1, Number(maxComments) || 6)),
        filter_vibe: filterVibe,
        prefer_long_comments: Boolean(lenCfg.preferLong || filterVibe === 'LONG_STORY'),
        min_comment_chars: Number(lenCfg.minChars || 0),
        expand_slang_and_translate: expandSlang,
        multi_voice_cast: multiVoiceCast,
        host_voice_id: hostVoiceId,
        male_voice_id: maleVoiceId,
        female_voice_id: femaleVoiceId,
        bg_path_or_url: effBg,
        rotate_bg_library: rotateBgLibrary,
        keep_bg_audio: keepBgAudio,
        bg_audio_volume: Number(bgAudioVolume),
        append_cta_comment: appendCtaComment.trim(),
        enable_card_pop_sfx: enablePopSfx,
        enable_smart_sfx: enableSmartSfx,
        smart_keyword_highlight: smartKeywordHighlight,
        voice_speed_global: safeSpeed,
        voice_pitch_global: 0.0,
        bgm_preset_id: bgmPresetId,
        rotate_lofi_bgm: rotateLofiBgm,
        bgm_volume: Number(bgmVolume),
        subtitle_style: subtitleStyle,
        layout_config: {
          ...layoutConfig,
          show_top_banner: false,
        },
        parent_group_id: parentGroupId || null,
        auto_one_click: true,
      });
      setBatchUrlsText('');
      notify(
        `Đã đưa ${res.queued_count} link Threads/Reddit vào hàng đợi tự động (xoay vòng Video Nền & Nhạc Lofi)!`
      );
      if (res.project_ids?.[0]) {
        onProjectStarted(res.project_ids[0], 'QUEUED');
      }
    } catch (err) {
      notify(`Lỗi chạy hàng loạt: ${err.message}`);
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
  const isQuizThemeActive = layoutConfig.threads_card_theme === 'QUIZ_COUNTDOWN_CARD';
  const isChatThemeActive =
    layoutConfig.threads_card_theme === 'CHAT_MESSENGER_ZALO' ||
    layoutConfig.threads_card_theme === 'CHAT_IMESSAGE_LIGHT';
  const isVinylThemeActive = layoutConfig.threads_card_theme === 'MIDNIGHT_VINYL_LYRIC';
  const quizCountdownBonusSec = isQuizThemeActive
    ? (bundle?.comments || [])
        .filter((c) => c.selected && String(c.author_handle || '').toLowerCase().startsWith('@cau_do'))
        .length * Number(layoutConfig.quiz_countdown_sec || 3)
    : 0;
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
          quizCountdownBonusSec +
          2
      )
    : Math.round((maxComments * 6 + 5) / Math.max(1.0, Number(voiceSpeed)));
  const itemUnitLabel = isQuizThemeActive
    ? 'thẻ đố & đáp'
    : isChatThemeActive
    ? 'tin nhắn'
    : 'bình luận';

  const stepItems = [
    {
      title: 'Bài đăng & Hội thoại',
      meta: bundle
        ? `Đã sẵn sàng ${selectedCommentsCount} ${itemUnitLabel}`
        : 'Threads / Reddit / Chat / Đố vui',
      done: Boolean(bundle && selectedCommentsCount > 0),
    },
    {
      title: 'Video nền 9:16 & Nhạc',
      meta: selectedBgPath ? 'Đã chọn Video Nền' : `Kho nền (${bgLibrary.length} video)`,
      done: Boolean(selectedBgPath || bgUrlInput.trim()),
    },
    {
      title: 'Giao diện Thẻ & Xuất bản',
      meta: `${Number(voiceSpeed).toFixed(2)}x • ~${estTotalSec}s`,
      done: false,
    },
  ];

  const showStep1 = showAllSteps || activeStep === 1;
  const showStep2 = showAllSteps || activeStep === 2;
  const showStep3 = showAllSteps || activeStep === 3;

  return (
    <div ref={rootRef} className="card">
      <StudioPageHeader
        icon={MessageSquareText}
        title="Threads, Hội Thoại Chat & Đố Vui Cộng Đồng"
        subtitle="Hút bài đăng & ảnh bình luận trên Threads/Reddit, tạo tin nhắn Chat hoặc Đố vui 3-2-1 với bộ đôi giọng đọc Nam & Nữ"
        badges={[
          {
            label: apiKeyConfigured ? 'AI sẵn sàng' : 'Chưa gắn API Key',
            cls: apiKeyConfigured ? 'badge-ok' : 'badge-warn',
            icon: KeyRound,
          },
          {
            label: bundle
              ? `${selectedCommentsCount} ${itemUnitLabel}`
              : `Lấy ${maxComments} ${itemUnitLabel}`,
            cls: 'badge-info',
          },
          attachedPhotosCount > 0
            ? { label: `${attachedPhotosCount} ảnh đính kèm`, cls: 'badge-ok' }
            : null,
          { label: `${Number(voiceSpeed).toFixed(2)}x • ~${estTotalSec}s`, cls: '' },
        ]}
        actions={
          !apiKeyConfigured && onOpenApiSettings ? (
            <button type="button" className="btn btn-secondary btn-sm" onClick={onOpenApiSettings}>
              <KeyRound size={13} /> Cấu hình API
            </button>
          ) : null
        }
      />

      <StudioStepNav
        steps={stepItems}
        activeStep={activeStep}
        onStepChange={setActiveStep}
        showAllSteps={showAllSteps}
        onToggleShowAll={onToggleShowAllSteps}
      />

      {/* ==================== BƯỚC 1: BÀI ĐĂNG, KỊCH BẢN & ĐÔI GIỌNG ĐỌC ==================== */}
      {showStep1 && (
        <div className="step-box fade-slide-in">
          <div className="step-header">
            <span className="step-num">1</span>
            <div style={{ flex: 1 }}>
              <div className="step-title">Chọn định dạng &amp; Chuẩn bị danh sách thẻ nội dung</div>
              <div className="step-desc">
                Hút trực tiếp từ liên kết Threads/Reddit (tự dịch bài tiếng Anh &amp; giữ ảnh đính kèm), hoặc dựng kịch bản Chat / Đố vui bằng AI
              </div>
            </div>

            <button
              type="button"
              className={`btn btn-sm ${radarOpen ? 'btn-primary' : 'btn-secondary'}`}
              onClick={() => (radarOpen ? setRadarOpen(false) : handleLoadViralRadar(radarNiche))}
            >
              <Flame size={14} /> {radarOpen ? 'Đóng xu hướng' : 'Săn bài đang Viral'}
            </button>
          </div>

          {/* CLEAN FORMAT SEGMENTED BAR */}
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center', marginBottom: 16 }}>
            <div className="studio-segmented">
              <button
                type="button"
                className={`studio-seg-btn ${
                  !batchMode && !chatStoryMode && !quizMode ? 'active' : ''
                }`}
                onClick={() => {
                  setBatchMode(false);
                  setChatStoryMode(false);
                  setQuizMode(false);
                  if (
                    layoutConfig.threads_card_theme === 'CHAT_MESSENGER_ZALO' ||
                    layoutConfig.threads_card_theme === 'CHAT_IMESSAGE_LIGHT' ||
                    layoutConfig.threads_card_theme === 'QUIZ_COUNTDOWN_CARD'
                  ) {
                    updateThreadsLayout({ threads_card_theme: 'DARK_THREADS' });
                  }
                }}
              >
                Bài Threads / Reddit
              </button>
              <button
                type="button"
                className={`studio-seg-btn ${chatStoryMode && !batchMode ? 'active' : ''}`}
                onClick={() => {
                  setBatchMode(false);
                  setQuizMode(false);
                  setChatStoryMode(true);
                  if (
                    layoutConfig.threads_card_theme !== 'CHAT_MESSENGER_ZALO' &&
                    layoutConfig.threads_card_theme !== 'CHAT_IMESSAGE_LIGHT'
                  ) {
                    updateThreadsLayout({ threads_card_theme: 'CHAT_MESSENGER_ZALO' });
                  }
                }}
              >
                Tin nhắn Chat
              </button>
              <button
                type="button"
                className={`studio-seg-btn ${quizMode && !batchMode ? 'active' : ''}`}
                onClick={() => {
                  setBatchMode(false);
                  setChatStoryMode(false);
                  setQuizMode(true);
                  updateThreadsLayout({ threads_card_theme: 'QUIZ_COUNTDOWN_CARD' });
                }}
              >
                Đố vui 3-2-1
              </button>
              <button
                type="button"
                className={`studio-seg-btn ${batchMode ? 'active' : ''}`}
                onClick={() => {
                  setBatchMode(true);
                  setChatStoryMode(false);
                  setQuizMode(false);
                }}
              >
                Hàng loạt (Batch)
              </button>
            </div>

            <button
              type="button"
              className={`btn btn-sm ${isVinylThemeActive ? 'btn-primary' : 'btn-secondary'}`}
              onClick={() =>
                updateThreadsLayout({
                  threads_card_theme: isVinylThemeActive ? 'DARK_THREADS' : 'MIDNIGHT_VINYL_LYRIC',
                })
              }
            >
              <Music size={13} /> Đĩa than Vinyl
            </button>
          </div>

          {/* QUICK THREADS SAMPLES */}
          {!batchMode && !chatStoryMode && !quizMode && !bundle && (
            <div className="summary-bar">
              <span
                className="text-xs fw-600 text-brand"
                style={{ display: 'inline-flex', alignItems: 'center', gap: 5 }}
              >
                <Sparkles size={14} /> Điền nhanh mẫu thử:
              </span>
              {QUICK_THREAD_SAMPLES.map((smp, idx) => (
                <button
                  key={idx}
                  type="button"
                  className="filter-pill"
                  onClick={() => {
                    setPostUrl('');
                    setRawPastedText(smp.rawText);
                    notify(`Đã điền "${smp.label}" — bấm Hút & Lọc bình luận bên dưới!`);
                  }}
                >
                  {smp.label}
                </button>
              ))}
            </div>
          )}

          {/* VIRAL RADAR DRAWER */}
          {radarOpen && (
            <div className="studio-callout studio-callout-brand fade-slide-in" style={{ marginBottom: 16 }}>
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
                <div className="text-sm fw-700" style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  <Flame size={15} style={{ color: 'var(--brand-text)' }} />
                  <span>Bài thảo luận đang nhiều bình luận nhất (Tự dịch sang tiếng Việt)</span>
                </div>
                <div style={{ display: 'flex', gap: 5, flexWrap: 'wrap' }}>
                  {RADAR_NICHES.map((nc) => (
                    <button
                      key={nc.id}
                      type="button"
                      className={`filter-pill ${radarNiche === nc.id ? 'active' : ''}`}
                      disabled={loadingRadar}
                      onClick={() => handleLoadViralRadar(nc.id)}
                    >
                      {nc.label}
                    </button>
                  ))}
                </div>
              </div>

              {loadingRadar ? (
                <div className="text-xs text-sub" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <Loader2 size={15} className="spin" /> Đang quét các bài thảo luận sôi nổi...
                </div>
              ) : (
                <div style={{ display: 'grid', gap: 7, maxHeight: 250, overflowY: 'auto', paddingRight: 4 }}>
                  {radarItems.map((it) => (
                    <div
                      key={it.item_id}
                      style={{
                        display: 'flex',
                        justifyContent: 'space-between',
                        alignItems: 'center',
                        gap: 10,
                        padding: '9px 12px',
                        borderRadius: 8,
                        background: 'var(--bg-panel)',
                        border: '1px solid var(--border)',
                        flexWrap: 'wrap',
                      }}
                    >
                      <div style={{ flex: 1, minWidth: 220 }}>
                        <div style={{ display: 'flex', gap: 6, alignItems: 'center', marginBottom: 3 }}>
                          <span className="badge badge-info">{it.community_label}</span>
                          <span className="text-xs text-muted">
                            {it.upvotes} lượt thích • {it.comments_count} bình luận
                          </span>
                        </div>
                        <div className="text-sm fw-600">{it.title_vi}</div>
                        {it.preview_snippet && (
                          <div className="text-xs text-sub" style={{ marginTop: 2 }}>
                            {it.preview_snippet.slice(0, 125)}
                          </div>
                        )}
                      </div>
                      <div style={{ display: 'flex', gap: 6 }}>
                        <button
                          type="button"
                          className="btn btn-primary btn-sm"
                          onClick={() => {
                            setBatchMode(false);
                            if (it.post_url) {
                              setChatStoryMode(false);
                              setPostUrl(it.post_url);
                              setRawPastedText('');
                              setRadarOpen(false);
                              notify('Đã điền link bài Viral — bấm Hút bài viết bên dưới!');
                            } else {
                              setChatStoryMode(true);
                              setChatIdea(it.title_vi);
                              setRadarOpen(false);
                              notify('Đã nạp chủ đề vào trình viết Hội Thoại Chat!');
                            }
                          }}
                        >
                          Dùng ngay
                        </button>
                        {it.post_url && (
                          <button
                            type="button"
                            className="btn btn-secondary btn-sm"
                            onClick={() => {
                              setBatchUrlsText((prev) =>
                                prev.includes(it.post_url)
                                  ? prev
                                  : `${prev ? `${prev}\n` : ''}${it.post_url}`
                              );
                              notify('Đã thêm link vào danh sách Batch!');
                            }}
                          >
                            + Batch
                          </button>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* INPUT AREA BY FORMAT */}
          {batchMode ? (
            <div className="studio-callout studio-callout-brand" style={{ marginBottom: 16 }}>
              <label className="form-label">
                Danh sách link Threads hoặc Reddit quốc tế (Mỗi dòng 1 link, tối đa 15 link)
              </label>
              <textarea
                className={`textarea ${errors.batchUrls ? 'input-error' : ''}`}
                style={{ minHeight: 125 }}
                placeholder={`https://www.threads.com/@nhonaytennhi/post/DU8UhpTgT6a\nhttps://www.reddit.com/r/AskReddit/comments/...`}
                value={batchUrlsText}
                onChange={(e) => {
                  setBatchUrlsText(e.target.value);
                  clearError('batchUrls');
                }}
              />
              <FieldError message={errors.batchUrls} />
              <div className="toggle-grid" style={{ marginTop: 12, marginBottom: 12 }}>
                <SwitchCard checked={rotateBgLibrary} onChange={setRotateBgLibrary}>
                  Tự xoay vòng đổi Video Nền qua Kho ({bgLibrary.length} video)
                </SwitchCard>
                <SwitchCard checked={rotateLofiBgm} onChange={setRotateLofiBgm}>
                  Tự xoay vòng đổi bài Nhạc nền Lofi CC0
                </SwitchCard>
              </div>
              <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
                <button
                  type="button"
                  className="btn btn-primary"
                  disabled={submitting}
                  onClick={handleStartBatchThreads}
                >
                  {submitting ? <Loader2 size={15} className="spin" /> : <Play size={15} />}
                  <span>{submitting ? 'Đang đưa vào hàng đợi...' : 'Xếp hàng chạy toàn bộ lô'}</span>
                </button>
              </div>
            </div>
          ) : chatStoryMode ? (
            <div className="studio-callout studio-callout-brand" style={{ marginBottom: 16 }}>
              <div className="text-sm fw-700" style={{ marginBottom: 10, display: 'flex', alignItems: 'center', gap: 7 }}>
                <MessageSquareText size={16} style={{ color: 'var(--brand-text)' }} />
                <span>Tạo Kịch Bản Hội Thoại Tin Nhắn Chat 2 Chiều (Messenger / Zalo / iMessage)</span>
              </div>
              <div className="form-group">
                <label className="form-label">Ý tưởng tình huống cuộc trò chuyện</label>
                <input
                  className={`input ${errors.chatIdea ? 'input-error' : ''}`}
                  placeholder="VD: Nhắn tin thử lòng Crush lúc 11h đêm và câu trả lời khiến tim đập loạn nhịp..."
                  value={chatIdea}
                  onChange={(e) => {
                    setChatIdea(e.target.value);
                    clearError('chatIdea');
                  }}
                />
                <FieldError message={errors.chatIdea} />
              </div>

              <div className="form-grid" style={{ marginBottom: 12 }}>
                <div>
                  <label className="form-label">Tên người nhắn bên Phải (Bong bóng Xanh)</label>
                  <input
                    className="input"
                    value={chatSenderA}
                    onChange={(e) => setChatSenderA(e.target.value)}
                    placeholder="VD: Mình / Chủ shop"
                  />
                </div>
                <div>
                  <label className="form-label">Tên người đối thoại bên Trái</label>
                  <input
                    className="input"
                    value={chatSenderB}
                    onChange={(e) => setChatSenderB(e.target.value)}
                    placeholder="VD: Crush / Khách hàng"
                  />
                </div>
              </div>

              <div className="form-grid" style={{ marginBottom: 12 }}>
                <div>
                  <label className="form-label">Tông màu câu chuyện Chat</label>
                  <select
                    className="select"
                    value={chatVibe}
                    onChange={(e) => setChatVibe(e.target.value)}
                  >
                    {CHAT_VIBE_OPTIONS.map((v) => (
                      <option key={v.id} value={v.id}>
                        {v.label}
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="form-label">
                    Số lượng tin nhắn qua lại: <strong>{chatMsgCount} tin nhắn</strong>
                  </label>
                  <input
                    type="range"
                    min="4"
                    max="16"
                    step="1"
                    style={{ width: '100%', marginTop: 8 }}
                    value={chatMsgCount}
                    onChange={(e) => setChatMsgCount(Number(e.target.value))}
                  />
                </div>
              </div>

              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                <span className="text-xs text-sub">
                  Tự động chèn hiệu ứng <strong>• • • đang nhập</strong> &amp; tiếng <strong>Ting</strong> gửi/nhận tin nhắn 2 chiều
                </span>
                <button
                  type="button"
                  className="btn btn-primary"
                  disabled={generatingChat || submitting}
                  onClick={handleGenerateChatStory}
                >
                  {generatingChat ? <Loader2 size={15} className="spin" /> : <Sparkles size={15} />}
                  <span>
                    {generatingChat ? 'Đang viết hội thoại...' : `AI Viết ${chatMsgCount} Tin Nhắn Chat`}
                  </span>
                </button>
              </div>
            </div>
          ) : quizMode ? (
            <div className="studio-callout studio-callout-brand" style={{ marginBottom: 16 }}>
              <div className="text-sm fw-700" style={{ marginBottom: 10, display: 'flex', alignItems: 'center', gap: 7 }}>
                <HelpCircle size={16} style={{ color: 'var(--brand-text)' }} />
                <span>Tạo Video Đố Vui Phản Xạ Kèm Đồng Hồ Đếm Ngược 3 - 2 - 1</span>
              </div>
              <div className="form-grid" style={{ marginBottom: 12 }}>
                <div>
                  <label className="form-label">Chủ đề bộ câu đố (Tùy chọn)</label>
                  <input
                    className="input"
                    placeholder="VD: Phân biệt tiếng Guitar gỗ thịt vs gỗ ép / Giải mã tâm lý Crush..."
                    value={quizTopic}
                    onChange={(e) => setQuizTopic(e.target.value)}
                  />
                </div>
                <div>
                  <label className="form-label">Lĩnh vực đố vui</label>
                  <select
                    className="select"
                    value={quizCategory}
                    onChange={(e) => setQuizCategory(e.target.value)}
                  >
                    {QUIZ_CATEGORY_OPTIONS.map((q) => (
                      <option key={q.id} value={q.id}>
                        {q.label}
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              <div className="form-grid" style={{ marginBottom: 12 }}>
                <div>
                  <label className="form-label">
                    Số câu đố trong video: <strong>{quizQuestionCount} câu</strong>
                  </label>
                  <input
                    type="range"
                    min="2"
                    max="5"
                    step="1"
                    style={{ width: '100%', marginTop: 8 }}
                    value={quizQuestionCount}
                    onChange={(e) => setQuizQuestionCount(Number(e.target.value))}
                  />
                </div>
                <div>
                  <label className="form-label">
                    Thời gian đếm ngược mỗi câu: <strong>{layoutConfig.quiz_countdown_sec || 3} giây</strong>
                  </label>
                  <input
                    type="range"
                    min="2"
                    max="5"
                    step="1"
                    style={{ width: '100%', marginTop: 8 }}
                    value={layoutConfig.quiz_countdown_sec || 3}
                    onChange={(e) =>
                      updateThreadsLayout({ quiz_countdown_sec: Number(e.target.value) })
                    }
                  />
                </div>
              </div>

              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                <span className="text-xs text-sub">
                  Mỗi câu đố tự giữ hình <strong>{layoutConfig.quiz_countdown_sec || 3}s</strong> kèm tiếng <strong>Tích-tắc</strong> &amp; chuông <strong>Ding</strong> khi lật đáp án
                </span>
                <button
                  type="button"
                  className="btn btn-primary"
                  disabled={generatingQuiz || submitting}
                  onClick={handleGenerateQuiz}
                >
                  {generatingQuiz ? <Loader2 size={15} className="spin" /> : <Clock size={15} />}
                  <span>
                    {generatingQuiz
                      ? 'Đang biên soạn...'
                      : `AI Tạo ${quizQuestionCount} Câu Đố & Đáp Án`}
                  </span>
                </button>
              </div>
            </div>
          ) : (
            <>
              <div className="form-group">
                <label className="form-label">
                  <Link2 size={14} style={{ verticalAlign: '-2px', marginRight: 6 }} />
                  Đường dẫn bài đăng Threads hoặc Reddit quốc tế (tự dịch sang tiếng Việt)
                </label>
                <input
                  className={`input ${errors.postUrl ? 'input-error' : ''}`}
                  placeholder="VD: https://www.threads.com/@.../post/... hoặc https://www.reddit.com/r/AskReddit/comments/..."
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
                  Hoặc dán trực tiếp nội dung bài viết &amp; bình luận (Tùy chọn)
                </label>
                <textarea
                  className={`textarea ${errors.rawPastedText ? 'input-error' : ''}`}
                  style={{ minHeight: 78 }}
                  placeholder="Có thể để trống nếu đã dán link công khai ở trên..."
                  value={rawPastedText}
                  onChange={(e) => {
                    setRawPastedText(e.target.value);
                    clearError('rawPastedText', 'postUrl');
                  }}
                />
                <FieldError message={errors.rawPastedText} />
              </div>

              <div
                className="studio-callout studio-callout-brand"
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  gap: 12,
                  flexWrap: 'wrap',
                  marginBottom: 14,
                }}
              >
                <div style={{ minWidth: 220, flex: 1 }}>
                  <div className="text-sm fw-700 text-main">
                    Hút bài viết, ảnh bình luận &amp; chọn ra {maxComments} phản hồi đắt giá nhất
                  </div>
                  <div className="text-xs text-sub" style={{ marginTop: 2 }}>
                    Tự động giữ lại ảnh chụp dưới các bình luận và gán đối thoại 2 giọng chính Nam &amp; Nữ
                  </div>
                </div>
                <button
                  type="button"
                  className="btn btn-primary"
                  disabled={extracting || submitting}
                  onClick={handleExtractThreads}
                >
                  {extracting ? <Loader2 size={16} className="spin" /> : <Wand2 size={16} />}
                  <span>
                    {extracting ? 'Đang hút bài & lọc...' : `Hút bài & Lọc ${maxComments} bình luận`}
                  </span>
                </button>
              </div>
            </>
          )}

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

          {/* INTERACTIVE CURATED THREAD & COMMENTS EDITOR */}
          {bundle && (
            <div
              className={`studio-callout studio-callout-success ${
                extracting ? 'is-reloading-dim' : 'fade-slide-in'
              }`}
              style={{ marginBottom: 14 }}
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
                <span
                  className="text-sm fw-700 text-success"
                  style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}
                >
                  <CheckCircle2 size={16} />
                  <span>
                    {bundle.extraction_note ||
                      'Đã sẵn sàng danh sách bài đăng gốc & bình luận tiêu biểu'}
                  </span>
                </span>
                <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                  {(bundle.comments || []).length > 1 && (
                    <button
                      type="button"
                      className="btn btn-secondary btn-sm"
                      onClick={() => {
                        setBundle((prev) => {
                          if (!prev) return prev;
                          const sorted = [...(prev.comments || [])].sort(
                            (a, b) =>
                              (b.display_text || '').trim().length -
                              (a.display_text || '').trim().length
                          );
                          return applyTwoMainVoicesToBundle(
                            { ...prev, comments: sorted },
                            hostVoiceId,
                            maleVoiceId,
                            femaleVoiceId,
                            multiVoiceCast
                          );
                        });
                        notify('Đã sắp xếp các bình luận dài nhất lên đầu danh sách!');
                      }}
                    >
                      <ArrowUpWideNarrow size={13} /> Xếp bình luận dài lên đầu
                    </button>
                  )}
                  <button
                    type="button"
                    className="btn btn-secondary btn-sm"
                    onClick={addCustomComment}
                  >
                    <MessageSquarePlus size={13} /> Thêm 1 thẻ
                  </button>
                </div>
              </div>

              {/* OP MAIN THREAD CARD EDITOR */}
              <div
                className="surface-box"
                style={{
                  borderColor: 'var(--brand)',
                  marginBottom: 12,
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
                  <span style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}>
                    {bundle.op_avatar_media_url && !layoutConfig.threads_anonymize_handles && (
                      <img
                        src={bundle.op_avatar_media_url}
                        alt="OP Avatar"
                        style={{
                          width: 28,
                          height: 28,
                          borderRadius: '50%',
                          objectFit: 'cover',
                          border: '1.5px solid var(--brand)',
                        }}
                      />
                    )}
                    <span className="badge badge-info">Thẻ mở đầu • Bài gốc (OP)</span>
                  </span>
                  <div style={{ display: 'flex', gap: 6, alignItems: 'center', flexWrap: 'wrap' }}>
                    <input
                      className="input input-sm"
                      style={{ width: 148 }}
                      value={bundle.op_author_handle}
                      onChange={(e) =>
                        setBundle((prev) => ({ ...prev, op_author_handle: e.target.value }))
                      }
                      title="Tên tài khoản hiển thị trên thẻ OP"
                    />
                    <input
                      className="input input-sm"
                      style={{ width: 78 }}
                      value={bundle.op_likes_display}
                      onChange={(e) =>
                        setBundle((prev) => ({ ...prev, op_likes_display: e.target.value }))
                      }
                      title="Số lượt tim hiển thị"
                    />
                    <button
                      type="button"
                      className="btn btn-secondary btn-sm"
                      onClick={() => {
                        const nextId =
                          (bundle.op_voice_profile_id || hostVoiceId) === femaleVoiceId
                            ? maleVoiceId
                            : femaleVoiceId;
                        setBundle((prev) => ({ ...prev, op_voice_profile_id: nextId }));
                      }}
                    >
                      {(bundle.op_voice_profile_id || hostVoiceId) === maleVoiceId
                        ? 'Giọng Nam'
                        : 'Giọng Nữ'}
                    </button>
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
                    <label className="btn btn-secondary btn-sm" style={{ cursor: 'pointer' }}>
                      {uploadingCardImgKey === 'OP' ? (
                        <Loader2 size={13} />
                      ) : (
                        <ImagePlus size={13} />
                      )}{' '}
                      Ảnh OP
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

                <div className="form-group" style={{ marginBottom: 10 }}>
                  <div
                    style={{
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                      gap: 8,
                      flexWrap: 'wrap',
                      marginBottom: 5,
                    }}
                  >
                    <label className="form-label" style={{ marginBottom: 0 }}>
                      Tiêu đề SEO của dự án video
                    </label>
                    <button
                      type="button"
                      className="btn btn-secondary btn-sm"
                      disabled={scoringHook}
                      onClick={handleScoreOpeningHook}
                    >
                      {scoringHook ? <Loader2 size={12} className="spin" /> : <Sparkles size={12} />}
                      <span>
                        {scoringHook ? 'Đang chấm...' : 'Chấm điểm Hook 3 giây & Gợi ý A/B'}
                      </span>
                    </button>
                  </div>
                  <input
                    className={`input ${errors.topicTitle ? 'input-error' : ''}`}
                    value={bundle.topic_title}
                    onChange={(e) => {
                      setBundle((prev) => ({ ...prev, topic_title: e.target.value }));
                      clearError('topicTitle');
                    }}
                  />
                  <FieldError message={errors.topicTitle} />
                </div>

                {hookScoreRes && (
                  <div className="studio-callout studio-callout-brand fade-slide-in" style={{ marginBottom: 10 }}>
                    <div
                      style={{
                        display: 'flex',
                        justifyContent: 'space-between',
                        alignItems: 'center',
                        gap: 8,
                        flexWrap: 'wrap',
                        marginBottom: 6,
                      }}
                    >
                      <div className="text-sm fw-700">
                        Điểm Giữ Chân 3 Giây Đầu:{' '}
                        <span className="text-brand">{hookScoreRes.overall_score}/100</span> —{' '}
                        {hookScoreRes.verdict_label}
                      </div>
                      <span className="badge badge-info">
                        Mở đầu ~{hookScoreRes.estimated_intro_sec}s
                      </span>
                    </div>
                    {hookScoreRes.weakness_note && (
                      <div className="text-xs text-sub" style={{ marginBottom: 8 }}>
                        Gợi ý cải thiện: {hookScoreRes.weakness_note}
                      </div>
                    )}
                    <div style={{ display: 'grid', gap: 6 }}>
                      {(hookScoreRes.variants || []).map((v, vIdx) => (
                        <div
                          key={vIdx}
                          style={{
                            display: 'flex',
                            justifyContent: 'space-between',
                            alignItems: 'center',
                            gap: 8,
                            padding: '7px 10px',
                            borderRadius: 8,
                            background: 'var(--bg-panel)',
                            border: '1px solid var(--border)',
                          }}
                        >
                          <div className="text-xs" style={{ flex: 1 }}>
                            <strong className="text-brand">
                              [{v.style_label} • {v.predicted_score}đ]
                            </strong>{' '}
                            {v.hook_text}
                          </div>
                          <button
                            type="button"
                            className="btn btn-primary btn-sm"
                            style={{ whiteSpace: 'nowrap' }}
                            onClick={() => {
                              setBundle((prev) => ({
                                ...prev,
                                op_display_text: v.hook_text,
                                op_spoken_vi_text: v.spoken_vi_text || v.hook_text,
                              }));
                              notify(`Đã áp dụng Hook "${v.style_label}" vào Thẻ Mở Đầu!`);
                            }}
                          >
                            Áp dụng
                          </button>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                <div className="form-grid">
                  <div>
                    <label className="form-label text-xs">Chữ hiển thị trên Thẻ Bài Gốc</label>
                    <textarea
                      className={`textarea ${errors.opDisplay ? 'input-error' : ''}`}
                      style={{ minHeight: 68 }}
                      value={bundle.op_display_text}
                      onChange={(e) => {
                        setBundle((prev) => ({ ...prev, op_display_text: e.target.value }));
                        clearError('opDisplay');
                      }}
                    />
                    <FieldError message={errors.opDisplay} />
                  </div>
                  <div>
                    <label className="form-label text-xs">
                      Lời đọc giọng Việt ({Number(voiceSpeed).toFixed(2)}x)
                    </label>
                    <textarea
                      className={`textarea ${errors.opSpoken ? 'input-error' : ''}`}
                      style={{ minHeight: 68 }}
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
                      border: '1px solid var(--border)',
                    }}
                  >
                    {bundle.op_image_media_url && (
                      <img
                        src={bundle.op_image_media_url}
                        alt="OP attachment"
                        style={{
                          width: 64,
                          height: 64,
                          objectFit: 'cover',
                          borderRadius: 6,
                        }}
                      />
                    )}
                    <span className="text-xs fw-600">Ảnh đính kèm trong Thẻ Bài Gốc</span>
                    <button
                      type="button"
                      className="btn btn-danger btn-sm"
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
              <div style={{ display: 'grid', gap: 10, maxHeight: 580, overflowY: 'auto', paddingRight: 4 }}>
                {(bundle.comments || []).map((cmt, idx) => {
                  const pKey = `cmt_${idx}`;
                  const isMaleLine = (cmt.voice_profile_id || hostVoiceId) === maleVoiceId;
                  const hasCmtImg = Boolean(cmt.attached_image_media_url || cmt.attached_image_path);
                  const dispLen = (cmt.display_text || '').trim().length;
                  const estReadSec = Math.max(
                    2,
                    Math.round(
                      ((cmt.spoken_vi_text || cmt.display_text || '').trim().split(/\s+/).length ||
                        1) /
                        (2.85 * Math.max(1.0, Number(voiceSpeed) || 1.25))
                    )
                  );
                  const boxMinH = dispLen > 200 ? 108 : dispLen > 95 ? 80 : 58;
                  return (
                    <div
                      key={cmt.comment_id || idx}
                      className="surface-box"
                      style={{
                        borderStyle: cmt.selected ? 'solid' : 'dashed',
                        opacity: cmt.selected ? 1 : 0.56,
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
                        <label
                          className="text-sm fw-600"
                          style={{
                            display: 'inline-flex',
                            alignItems: 'center',
                            gap: 8,
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
                                width: 24,
                                height: 24,
                                borderRadius: '50%',
                                objectFit: 'cover',
                                border: '1px solid var(--border-strong)',
                              }}
                            />
                          )}
                          <span>Thẻ {idx + 1}</span>
                          <span className="text-xs text-muted fw-500">
                            {dispLen} ký tự (~{estReadSec}s)
                          </span>
                          {hasCmtImg && <span className="badge badge-ok">Có ảnh</span>}
                        </label>

                        <div style={{ display: 'flex', gap: 5, alignItems: 'center', flexWrap: 'wrap' }}>
                          <input
                            className="input input-sm"
                            style={{ width: 136 }}
                            value={cmt.author_handle}
                            onChange={(e) => patchComment(idx, { author_handle: e.target.value })}
                            title="Tên tài khoản bình luận"
                          />
                          <input
                            className="input input-sm"
                            style={{ width: 68 }}
                            value={cmt.likes_display}
                            onChange={(e) => patchComment(idx, { likes_display: e.target.value })}
                            title="Số lượt thích"
                          />
                          <button
                            type="button"
                            className="btn btn-secondary btn-sm"
                            onClick={() =>
                              patchComment(idx, {
                                voice_profile_id: isMaleLine ? femaleVoiceId : maleVoiceId,
                              })
                            }
                          >
                            {isMaleLine ? 'Giọng Nam' : 'Giọng Nữ'}
                          </button>
                          <button
                            type="button"
                            className="btn btn-secondary btn-sm"
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
                          <label className="btn btn-secondary btn-sm" style={{ cursor: 'pointer' }}>
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
                            disabled={idx === 0}
                            onClick={() => moveComment(idx, idx - 1)}
                          >
                            <ArrowUp size={12} />
                          </button>
                          <button
                            type="button"
                            className="btn btn-secondary btn-sm"
                            disabled={idx === bundle.comments.length - 1}
                            onClick={() => moveComment(idx, idx + 1)}
                          >
                            <ArrowDown size={12} />
                          </button>
                          <button
                            type="button"
                            className="btn btn-danger btn-sm"
                            onClick={() => removeComment(idx)}
                          >
                            <Trash2 size={12} />
                          </button>
                        </div>
                      </div>

                      <div className="form-grid">
                        <div>
                          <div className="text-xs text-muted fw-600" style={{ marginBottom: 4 }}>
                            Chữ hiển thị trên thẻ
                          </div>
                          <textarea
                            className="textarea"
                            style={{ minHeight: boxMinH }}
                            value={cmt.display_text}
                            onChange={(e) =>
                              patchComment(idx, {
                                display_text: e.target.value,
                                raw_text: e.target.value,
                              })
                            }
                          />
                        </div>
                        <div>
                          <div className="text-xs text-muted fw-600" style={{ marginBottom: 4 }}>
                            Lời đọc giọng Việt
                          </div>
                          <textarea
                            className="textarea"
                            style={{ minHeight: boxMinH }}
                            value={cmt.spoken_vi_text}
                            onChange={(e) => patchComment(idx, { spoken_vi_text: e.target.value })}
                          />
                        </div>
                      </div>

                      {hasCmtImg && (
                        <div
                          style={{
                            marginTop: 8,
                            display: 'inline-flex',
                            alignItems: 'center',
                            gap: 9,
                            padding: 6,
                            borderRadius: 8,
                            background: 'var(--bg-step)',
                            border: '1px solid var(--success-border)',
                          }}
                        >
                          {cmt.attached_image_media_url && (
                            <img
                              src={cmt.attached_image_media_url}
                              alt="Comment attachment"
                              style={{
                                width: 58,
                                height: 58,
                                objectFit: 'cover',
                                borderRadius: 6,
                              }}
                            />
                          )}
                          <span className="text-xs fw-600">Ảnh đính kèm của bình luận</span>
                          <button
                            type="button"
                            className="btn btn-danger btn-sm"
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

              <div style={{ marginTop: 12 }}>
                <label className="form-label text-xs">
                  Thẻ câu hỏi tương tác cuối video (Để trống nếu kết thúc ngay sau bình luận cuối)
                </label>
                <input
                  className="input"
                  value={appendCtaComment}
                  onChange={(e) => setAppendCtaComment(e.target.value)}
                />
              </div>
            </div>
          )}

          {/* COLLAPSIBLE VOICE CASTING, FILTERING & PARENT SERIES */}
          <StudioCollapsible
            icon={Users}
            title="Bộ đôi 2 Giọng Đọc Chính (Nam & Nữ), Tiêu chí lọc AI & Nhóm Series"
            subtitle="Chỉnh giọng Nữ/Nam đối thoại, tốc độ đọc, tiêu chí chọn bình luận dài và thư mục Dự Án Cha"
            defaultOpen={!bundle}
            badge={`${Number(voiceSpeed).toFixed(2)}x`}
          >
            <div className="surface-box" style={{ marginBottom: 14 }}>
              <div
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  gap: 8,
                  flexWrap: 'wrap',
                  marginBottom: 12,
                }}
              >
                <div className="text-sm fw-700" style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  <Users size={15} style={{ color: 'var(--brand-text)' }} />
                  <span>Bộ Đôi 2 Giọng Đọc Chính Cố Định (1 Nữ &amp; 1 Nam)</span>
                </div>
                <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                  {onNavigateTab && (
                    <button
                      type="button"
                      className="btn btn-ghost btn-sm"
                      onClick={() => onNavigateTab('voices')}
                    >
                      Kho giọng
                    </button>
                  )}
                  <div className="studio-segmented">
                    <button
                      type="button"
                      className={`studio-seg-btn ${opSpeakerGender === 'FEMALE' ? 'active' : ''}`}
                      onClick={() => setOpSpeakerGender('FEMALE')}
                    >
                      OP: Giọng Nữ
                    </button>
                    <button
                      type="button"
                      className={`studio-seg-btn ${opSpeakerGender === 'MALE' ? 'active' : ''}`}
                      onClick={() => setOpSpeakerGender('MALE')}
                    >
                      OP: Giọng Nam
                    </button>
                  </div>
                </div>
              </div>

              <div className="form-grid" style={{ marginBottom: 14 }}>
                <div>
                  <label className="form-label">Giọng Nữ Chính</label>
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
                      style={{ minHeight: 40, whiteSpace: 'nowrap' }}
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
                  <label className="form-label">Giọng Nam Chính</label>
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
                      style={{ minHeight: 40, whiteSpace: 'nowrap' }}
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
                      marginBottom: 4,
                    }}
                  >
                    <span className="text-xs fw-600" style={{ display: 'inline-flex', alignItems: 'center', gap: 5 }}>
                      <Gauge size={14} style={{ color: 'var(--brand-text)' }} />
                      Tốc độ đọc: <strong>{Number(voiceSpeed).toFixed(2)}x</strong>
                    </span>
                    <div style={{ display: 'flex', gap: 4 }}>
                      {SPEED_PRESETS.map((sp) => (
                        <button
                          key={sp.val}
                          type="button"
                          className={`filter-pill ${
                            Math.abs(Number(voiceSpeed) - sp.val) < 0.02 ? 'active' : ''
                          }`}
                          onClick={() => setVoiceSpeed(sp.val)}
                        >
                          {sp.label}
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
                </div>

                <div>
                  <label className="form-label text-xs">
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
                </div>
              </div>
            </div>

            {!chatStoryMode && !quizMode && (
              <>
                <div className="form-group">
                  <label className="form-label">Tiêu chí AI chọn lọc bình luận</label>
                  <ModeChoiceGrid
                    options={VIBE_CHOICES}
                    value={filterVibe}
                    onChange={(nextVibe) => {
                      setFilterVibe(nextVibe);
                      if (nextVibe === 'LONG_STORY' && commentLengthMode === 'ALL') {
                        setCommentLengthMode('DEEP_STORY');
                      }
                    }}
                  />
                </div>

                <div
                  className="surface-box"
                  style={{
                    marginBottom: 14,
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    gap: 10,
                    flexWrap: 'wrap',
                  }}
                >
                  <div>
                    <div className="text-sm fw-600">Độ dài bình luận ưu tiên</div>
                    <div className="text-xs text-sub">
                      Giữ nguyên 100% câu chuyện dài không bị tóm tắt
                    </div>
                  </div>
                  <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                    {COMMENT_LENGTH_MODES.map((m) => (
                      <button
                        key={m.id}
                        type="button"
                        className={`filter-pill ${commentLengthMode === m.id ? 'active' : ''}`}
                        onClick={() => setCommentLengthMode(m.id)}
                      >
                        {m.label}
                      </button>
                    ))}
                  </div>
                </div>
              </>
            )}

            <div className="toggle-grid" style={{ marginBottom: 14 }}>
              <SwitchCard icon={Languages} checked={expandSlang} onChange={setExpandSlang}>
                Bung viết tắt teen-code (ko→không, đc→được)
              </SwitchCard>
              <SwitchCard icon={Users} checked={multiVoiceCast} onChange={setMultiVoiceCast}>
                Đan xen đối thoại 2 Giọng Chính (Nam ↔ Nữ)
              </SwitchCard>
              <SwitchCard
                icon={EyeOff}
                checked={Boolean(layoutConfig.threads_anonymize_handles)}
                onChange={(val) => updateThreadsLayout({ threads_anonymize_handles: val })}
              >
                Che ẩn tên tài khoản (@nguoila_01)
              </SwitchCard>
            </div>

            <ParentGroupSelector
              projectGroups={projectGroups}
              value={parentGroupId}
              onChange={setParentGroupId}
              onGroupsChanged={onGroupsChanged}
              notify={notify}
              label="Thuộc Nhóm Dự Án Cha (Series Threads / Reddit)"
            />
          </StudioCollapsible>
        </div>
      )}

      {/* ==================== BƯỚC 2: VIDEO NỀN 9:16 & NHẠC NỀN ==================== */}
      {showStep2 && (
        <div className="step-box fade-slide-in">
          <div className="step-header">
            <span className="step-num">2</span>
            <div style={{ flex: 1 }}>
              <div className="step-title">
                Video Nền Chạy Dưới Thẻ Bình Luận ({bgLibrary.length} trong kho) &amp; Nhạc Nền
              </div>
              <div className="step-desc">
                Video nền tự cắt khung dọc 9:16 và lặp vòng mượt mà vừa khít tổng thời lượng đọc toàn bộ bình luận
              </div>
            </div>
          </div>

          {/* 1-CLICK ZERO-COPYRIGHT CHILL 9:16 LOOP GENERATOR */}
          <div
            className="studio-callout studio-callout-brand"
            style={{
              marginBottom: 16,
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              gap: 10,
              flexWrap: 'wrap',
            }}
          >
            <div className="text-sm">
              <strong>Tạo nhanh Video Nền Chill 9:16 Sạch Bản Quyền</strong>{' '}
              <span className="text-xs text-sub">(1 chạm vào Kho — Không cần tải YouTube):</span>
            </div>
            <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
              {CHILL_BG_PRESETS.map((cp) => (
                <button
                  key={cp.id}
                  type="button"
                  className="btn btn-secondary btn-sm"
                  disabled={Boolean(generatingChillBg)}
                  onClick={() => handleGenerateChillBg(cp.id)}
                >
                  {generatingChillBg === cp.id ? <Loader2 size={12} className="spin" /> : <Sparkles size={12} />}
                  <span>{cp.label}</span>
                </button>
              ))}
            </div>
          </div>

          {bgLibrary.length > 0 && (
            <div style={{ marginBottom: 16 }}>
              <div className="form-label">
                Chọn 1 chạm từ Kho Video Nền đã lưu ({bgLibrary.length} video):
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
                        width: 144,
                        flexShrink: 0,
                        borderRadius: 10,
                        padding: 7,
                        cursor: 'pointer',
                        background: isSelected ? 'var(--brand-soft)' : 'var(--bg-panel)',
                        border: isSelected ? '1.5px solid var(--brand)' : '1px solid var(--border)',
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
                        className="text-xs fw-600"
                        style={{
                          marginTop: 6,
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
                        <span className="text-xs text-muted">
                          {formatSecondsVi(Math.round((bg.duration_ms || 0) / 1000))}
                        </span>
                        <button
                          type="button"
                          onClick={(e) => handleDeleteSavedBg(bg, e)}
                          title="Xóa khỏi Kho Video Nền"
                          style={{
                            border: 'none',
                            background: 'transparent',
                            color: 'var(--danger-text)',
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

          <div className="form-grid" style={{ marginBottom: 16 }}>
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
                    : 'Kéo thả hoặc chọn tệp Video Nền (.mp4, .mov, .webm)'
                }
                hint="VD: Lái xe ban đêm, mưa chill bên cửa sổ, chơi đàn, nấu ăn..."
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
                  Lưu vào Kho Video Nền
                </SwitchCard>
                <input
                  className="input"
                  style={{ flex: 1, minWidth: 160 }}
                  placeholder="Tên gợi nhớ khi lưu kho (tùy chọn)"
                  value={bgCustomTitle}
                  onChange={(e) => setBgCustomTitle(e.target.value)}
                />
              </div>
            </div>

            <div
              className="surface-box"
              style={{ display: 'flex', flexDirection: 'column', justifyContent: 'space-between', gap: 12 }}
            >
              <div>
                <label className="form-label">Hoặc dán link YouTube / TikTok để tải làm Video Nền</label>
                <div style={{ display: 'flex', gap: 6 }}>
                  <input
                    className={`input ${errors.bgUrl ? 'input-error' : ''}`}
                    style={{ flex: 1 }}
                    placeholder="https://www.youtube.com/shorts/... hoặc TikTok..."
                    value={bgUrlInput}
                    onChange={(e) => {
                      setBgUrlInput(e.target.value);
                      clearError('bgUrl', 'bgVideo');
                    }}
                  />
                  <button
                    type="button"
                    className="btn btn-secondary"
                    style={{ whiteSpace: 'nowrap' }}
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
                    style={{
                      width: 52,
                      height: 80,
                      objectFit: 'cover',
                      borderRadius: 6,
                      background: '#000',
                    }}
                  />
                  <div style={{ minWidth: 0, flex: 1 }}>
                    <div className="text-xs fw-700 text-brand">
                      <Film size={13} style={{ verticalAlign: '-2px', marginRight: 4 }} />
                      Đã chọn Video Nền sẵn sàng
                    </div>
                    <div
                      className="text-xs text-muted"
                      style={{
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
                  className="text-xs text-sub"
                  style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}
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

              <SwitchCard
                checked={layoutConfig.auto_skip_black_intro !== false}
                onChange={(val) => updateThreadsLayout({ auto_skip_black_intro: val })}
              >
                Tự bỏ 1–3s đầu nếu bị tối đen
              </SwitchCard>
            </div>
          </div>

          <InlineBgmSelector
            bgmPresets={bgmPresets}
            bgmPresetId={bgmPresetId}
            onSelectPreset={setBgmPresetId}
            bgmVolume={bgmVolume}
            onVolumeChange={setBgmVolume}
            customBgmPath={customBgmPath}
            onCustomBgmChange={setCustomBgmPath}
            notify={notify}
            label="Nhạc nền Lofi / Chill lót nhẹ dưới cuộc trò chuyện"
          />
        </div>
      )}

      {/* ==================== BƯỚC 3: GIAO DIỆN THẺ NỔI & XUẤT BẢN ==================== */}
      {showStep3 && (
        <div className="step-box fade-slide-in">
          <div className="step-header">
            <span className="step-num">3</span>
            <div>
              <div className="step-title">Giao diện Thẻ nổi, Dẫn mắt người đọc &amp; Xuất bản</div>
              <div className="step-desc">
                Chọn giao diện thẻ hiển thị trên nền 9:16 và các âm hiệu chuyển thẻ
              </div>
            </div>
          </div>

          <div style={{ marginBottom: 16 }}>
            <label className="form-label">Chủ đề giao diện Thẻ nổi</label>
            <ModeChoiceGrid
              options={CARD_THEME_CHOICES}
              value={layoutConfig.threads_card_theme || 'DARK_THREADS'}
              onChange={(val) => updateThreadsLayout({ threads_card_theme: val })}
            />
          </div>

          <div style={{ marginBottom: 16 }}>
            <label className="form-label">Hiệu ứng dẫn mắt người đọc theo giọng nói</label>
            <ModeChoiceGrid
              options={EYE_GUIDE_CHOICES}
              value={layoutConfig.threads_eye_guide_mode || 'ACTIVE_HIGHLIGHT'}
              onChange={(val) => updateThreadsLayout({ threads_eye_guide_mode: val })}
            />
          </div>

          <div className="toggle-grid" style={{ marginBottom: 16 }}>
            <SwitchCard checked={enablePopSfx} onChange={setEnablePopSfx}>
              Phát tiếng &ldquo;Pop&rdquo; nhẹ mỗi khi nảy thẻ mới
            </SwitchCard>
            <SwitchCard checked={keepBgAudio} onChange={setKeepBgAudio}>
              Giữ tiếng động gốc của video nền (mưa, đàn, phố đêm...)
            </SwitchCard>
            <SwitchCard
              checked={layoutConfig.safe_zone_guard !== false}
              onChange={(val) => updateThreadsLayout({ safe_zone_guard: val })}
            >
              Tự căn vùng an toàn TikTok / Shorts
            </SwitchCard>
            <SwitchCard checked={enableSmartSfx} onChange={setEnableSmartSfx}>
              Âm hiệu điểm nhấn (Chuông mở đầu 3s &amp; Click ảnh)
            </SwitchCard>
          </div>

          {keepBgAudio && (
            <div className="surface-box" style={{ marginBottom: 16 }}>
              <div
                className="text-xs text-sub"
                style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}
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

          <div className="form-group" style={{ marginBottom: 0 }}>
            <label className="form-label">Phụ đề chạy thêm dưới đáy video (Tùy chọn)</label>
            <select
              className="select"
              value={subtitleStyle}
              onChange={(e) => setSubtitleStyle(e.target.value)}
            >
              <option value="NONE">
                Tắt phụ đề dưới đáy (Khuyên dùng vì chữ đã hiện rõ trên Thẻ nổi)
              </option>
              <option value="KARAOKE_CAPCUT">Bật thêm chữ Karaoke chạy từng từ</option>
              <option value="CINEMA">Bật thêm phụ đề câu thanh lịch</option>
            </select>
          </div>

          <StudioCollapsible
            icon={SlidersHorizontal}
            title="Chia Series nhiều phần, Lớp phủ điện ảnh & Thanh đốt truyện (Tùy chọn)"
            subtitle="Tự tách bài dài thành Phần 1 - 2 - 3 hoặc bật hiệu ứng hạt nắng / mưa đêm"
            badge={
              Number(seriesParts) > 1 ||
              (layoutConfig.ambience_overlay && layoutConfig.ambience_overlay !== 'NONE') ||
              layoutConfig.story_progress_bar_enabled
                ? 'Đang bật'
                : ''
            }
          >
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
                gap: 12,
                alignItems: 'end',
              }}
            >
              <div>
                <label className="form-label">Chia Series nhiều phần</label>
                <select
                  className="select"
                  value={seriesParts}
                  onChange={(e) => setSeriesParts(Number(e.target.value))}
                >
                  <option value={1}>1 phần trọn vẹn (Mặc định)</option>
                  <option value={2}>Chia 2 phần (Tự chèn thẻ sang Phần 2)</option>
                  <option value={3}>Chia 3 phần (Series Phần 1 - 2 - 3)</option>
                </select>
              </div>

              <div>
                <label className="form-label">Lớp phủ không khí điện ảnh</label>
                <select
                  className="select"
                  value={layoutConfig.ambience_overlay || 'NONE'}
                  onChange={(e) => updateThreadsLayout({ ambience_overlay: e.target.value })}
                >
                  <option value="NONE">Tắt hiệu ứng (Giữ nguyên bản 100%)</option>
                  <option value="GOLDEN_BOKEH">Hạt bụi nắng vàng (Golden Bokeh)</option>
                  <option value="NIGHT_RAIN">Mưa đêm phố thị (Night Rain)</option>
                  <option value="WARM_LIGHT_LEAK">Vệt nắng chiều ấm (Warm Light Leak)</option>
                  <option value="VINTAGE_FILM_35MM">Phim nhựa cổ điển 35mm</option>
                </select>
              </div>

              <SwitchCard
                checked={Boolean(layoutConfig.story_progress_bar_enabled)}
                onChange={(val) => updateThreadsLayout({ story_progress_bar_enabled: val })}
              >
                Thanh tiến trình đốt truyện trên đỉnh
              </SwitchCard>
            </div>
          </StudioCollapsible>
        </div>
      )}

      <StudioLoadingBanner
        loading={submitting}
        title="Đang khởi tạo dự án Video Threads & đưa vào tiến trình dựng..."
        subtitle="Hệ thống đang chuẩn bị thẻ giao diện nổi và bộ đôi 2 giọng đọc chính"
        steps={[
          'Kiểm tra dữ liệu bài đăng & bình luận',
          'Khởi động tiến trình tổng hợp giọng đọc & ghép khung 9:16',
        ]}
        stepIntervalMs={1800}
      />

      <StudioStepFooter
        activeStep={activeStep}
        totalSteps={3}
        showAllSteps={showAllSteps}
        onStepChange={setActiveStep}
        nextStepLabel={
          activeStep === 1 ? 'Tiếp tục: Chọn Video Nền & Nhạc' : 'Tiếp tục: Giao diện Thẻ & Xuất'
        }
        hintText="Tự động lưu nháp • Ctrl + Enter để xuất ngay"
        secondaryAction={{
          label: 'Duyệt kịch bản trước',
          icon: submitting ? <Loader2 size={15} className="spin" /> : <Edit3 size={15} />,
          disabled: submitting || extracting || uploadingBg || savingBgUrl,
          onClick: () => handleStartThreadsVideo(false),
        }}
        primaryAction={{
          label: submitting ? 'Đang khởi tạo...' : 'Bắt đầu dựng Video ngay',
          icon: submitting ? <Loader2 size={16} className="spin" /> : <Play size={16} />,
          disabled: submitting || extracting || uploadingBg || savingBgUrl,
          onClick: () => handleStartThreadsVideo(true),
        }}
      />
    </div>
  );
}
