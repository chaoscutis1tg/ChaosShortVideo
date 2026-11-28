import React, { useEffect, useRef, useState } from 'react';
import {
  ArrowLeft,
  ArrowRight,
  Award,
  BookmarkPlus,
  Camera,
  CheckCircle2,
  ClipboardPaste,
  Columns,
  Edit3,
  Feather,
  Film,
  Gift,
  Globe,
  HelpCircle,
  Images,
  KeyRound,
  Layers,
  Loader2,
  MessageSquareHeart,
  MessageSquarePlus,
  Music2,
  Package,
  Play,
  QrCode,
  Scale,
  Scissors,
  ShieldCheck,
  ShoppingBag,
  SlidersHorizontal,
  Sparkles,
  Star,
  Trash2,
  Wand2,
  X,
} from 'lucide-react';
import { studioApi } from '../m00_core_contracts/apiClient';
import { stripLeadingEmoji } from '../m00_core_contracts/constants';
import {
  FieldError,
  hasAllowedExtension,
  InlineBgmSelector,
  InlineVoiceSelector,
  isValidHttpUrl,
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

const PRODUCT_DRAFT_KEY = 'chaos_draft_product_v1';

function loadProductDraft() {
  try {
    const raw = localStorage.getItem(PRODUCT_DRAFT_KEY);
    return raw ? JSON.parse(raw) : {};
  } catch {
    return {};
  }
}

const VIDEO_EXT_RE = /\.(mp4|mov|mkv|webm|avi|flv|ts)$/i;

function InlineClipTrimmer({ mediaItem, playerRef, onTrimApplied, notify }) {
  const totalSecRaw = Math.max(2, Number(((mediaItem?.duration_ms || 20000) / 1000).toFixed(1)));
  const [totalSec, setTotalSec] = useState(totalSecRaw);
  const [startSec, setStartSec] = useState(0);
  const [endSec, setEndSec] = useState(Math.min(totalSecRaw, 15));
  const [trimming, setTrimming] = useState(false);

  useEffect(() => {
    const nextTot = Math.max(2, Number(((mediaItem?.duration_ms || 20000) / 1000).toFixed(1)));
    setTotalSec(nextTot);
    setStartSec(0);
    setEndSec(Math.min(nextTot, 18));
  }, [mediaItem?.local_path, mediaItem?.duration_ms]);

  const handlePreviewSlice = () => {
    const el = playerRef?.current;
    if (!el) return;
    el.currentTime = startSec;
    const onTimeUpdate = () => {
      if (el.currentTime >= endSec) {
        el.pause();
        el.removeEventListener('timeupdate', onTimeUpdate);
      }
    };
    el.addEventListener('timeupdate', onTimeUpdate);
    el.play().catch(() => {});
  };

  const handleApplyTrim = async () => {
    if (endSec - startSec < 0.8) {
      notify('Đoạn cắt cần dài tối thiểu 1 giây.');
      return;
    }
    setTrimming(true);
    try {
      const res = await studioApi.trimMediaSegment(
        mediaItem.local_path,
        Math.round(startSec * 1000),
        Math.round(endSec * 1000)
      );
      onTrimApplied(res);
      notify(
        `Đã cắt gọn đoạn hay nhất (${startSec.toFixed(1)}s – ${endSec.toFixed(1)}s, dài ${(
          res.duration_ms / 1000
        ).toFixed(1)}s).`
      );
    } catch (err) {
      notify(`Lỗi cắt đoạn: ${err.message}`);
    } finally {
      setTrimming(false);
    }
  };

  return (
    <div className="studio-callout studio-callout-brand" style={{ marginTop: 10 }}>
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          gap: 6,
          flexWrap: 'wrap',
          marginBottom: 8,
        }}
      >
        <span className="text-xs fw-700 text-brand">
          <Scissors size={12} style={{ verticalAlign: '-2px', marginRight: 5 }} />
          Chọn đoạn hay nhất: {startSec.toFixed(1)}s → {endSec.toFixed(1)}s (Lấy{' '}
          {Math.max(0, endSec - startSec).toFixed(1)}s / {totalSec.toFixed(1)}s)
        </span>
        {mediaItem?.trimmedDone && <span className="badge badge-ok">Đã cắt chuẩn</span>}
      </div>

      <div className="form-grid" style={{ marginBottom: 8 }}>
        <div>
          <div className="text-xs text-sub">
            Bắt đầu từ: <strong>{startSec.toFixed(1)} giây</strong>
          </div>
          <input
            type="range"
            min="0"
            max={Math.max(0.5, totalSec - 0.8)}
            step="0.5"
            style={{ width: '100%' }}
            value={startSec}
            onChange={(e) => {
              const v = parseFloat(e.target.value);
              setStartSec(v);
              if (endSec <= v + 0.5) setEndSec(Math.min(totalSec, v + 1.0));
            }}
          />
        </div>
        <div>
          <div className="text-xs text-sub">
            Kết thúc tại: <strong>{endSec.toFixed(1)} giây</strong>
          </div>
          <input
            type="range"
            min="1"
            max={totalSec}
            step="0.5"
            style={{ width: '100%' }}
            value={endSec}
            onChange={(e) => {
              const v = parseFloat(e.target.value);
              setEndSec(v);
              if (startSec >= v - 0.5) setStartSec(Math.max(0, v - 1.0));
            }}
          />
        </div>
      </div>

      <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
        {playerRef && (
          <button type="button" className="btn btn-secondary btn-sm" onClick={handlePreviewSlice}>
            <Play size={12} /> Nghe / Xem thử
          </button>
        )}
        <button
          type="button"
          className="btn btn-primary btn-sm"
          disabled={trimming}
          onClick={handleApplyTrim}
        >
          <Scissors size={12} /> {trimming ? 'Đang cắt...' : 'Cắt lấy đúng đoạn này'}
        </button>
      </div>
    </div>
  );
}

const TONE_CHOICES = [
  {
    value: 'ARTISAN_STORYTELLER',
    title: 'Nghệ nhân chia sẻ truyền cảm',
    subtitle: 'Văn phong có hồn, êm ái, tôn vinh chất gỗ, độ hoàn thiện và cảm xúc thực tế',
    icon: Feather,
  },
  {
    value: 'MODERN_CONSULTANT',
    title: 'Tư vấn thực tế, gọn gàng',
    subtitle: 'Đi thẳng vào điểm đáng giá, trải nghiệm sử dụng và quyền lợi đi kèm',
    icon: MessageSquareHeart,
  },
  {
    value: 'LUXURY_MINIMAL',
    title: 'Tối giản sang trọng, ít lời',
    subtitle: 'Câu ngắn tinh tế, nhịp chậm, nhường không gian cho hình ảnh và âm thanh mộc',
    icon: Sparkles,
  },
];

const ANGLE_CHOICES = [
  {
    value: 'EXPERT_SPEC_REVIEW',
    title: 'Phân tích cấu hình & chất liệu',
    subtitle: 'Cảm nhận mặt gỗ, vân lưng, chất vải thực tế',
    icon: Award,
  },
  {
    value: 'BEGINNER_CONSULT',
    title: 'Tư vấn cho người mới mua',
    subtitle: 'Dễ hiểu, trọn gói phụ kiện mua về dùng ngay',
    icon: HelpCircle,
  },
  {
    value: 'UNBOXING_AND_GIFT',
    title: 'Trải nghiệm & quyền lợi đi kèm',
    subtitle: 'Nhấn mạnh phụ kiện tặng kèm và hỗ trợ test thực tế',
    icon: Gift,
  },
  {
    value: 'PRICE_COMPARISON_DEAL',
    title: 'Phân biệt phiên bản & tầm giá',
    subtitle: 'Giúp khách chọn đúng bản phù hợp (VD: S2 và S2S)',
    icon: Scale,
  },
];

export default function ProductStudioForm({
  voices,
  bgmPresets,
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
  const savedDraft = loadProductDraft();
  const rootRef = useRef(null);

  const [activeStep, setActiveStep] = useState(1);
  const [templates, setTemplates] = useState([]);
  const [selectedTplId, setSelectedTplId] = useState('');
  const [parentGroupId, setParentGroupId] = useState(savedDraft.parentGroupId || '');
  const [scrapeUrl, setScrapeUrl] = useState('');
  const [scrapingUrl, setScrapingUrl] = useState(false);
  const [showBatchPanel, setShowBatchPanel] = useState(false);
  const [batchUrlsText, setBatchUrlsText] = useState('');
  const [batchDiversify, setBatchDiversify] = useState(true);
  const [startingBatch, setStartingBatch] = useState(false);
  const [trimOpenIdx, setTrimOpenIdx] = useState(null);
  const demoPlayerRef = useRef(null);

  const [productName, setProductName] = useState(
    savedDraft.productName ?? 'Đàn Violin Avaro S2 & S2S Gỗ Thịt Tự Nhiên'
  );
  const [category, setCategory] = useState(savedDraft.category || 'MUSICAL_INSTRUMENT');
  const [copywritingTone, setCopywritingTone] = useState(
    savedDraft.copywritingTone || 'ARTISAN_STORYTELLER'
  );
  const [salesAngle, setSalesAngle] = useState(savedDraft.salesAngle || 'EXPERT_SPEC_REVIEW');
  const [variantCount, setVariantCount] = useState(1);
  const [rawDescription, setRawDescription] = useState(
    savedDraft.rawDescription ??
      `- Mặt top: Gỗ thịt (Solid Wood) cho âm vang dày và ấm.\n- Lưng và hông: Gỗ Maple cao cấp vân đẹp sắc nét.\n- Mặt phím: Gỗ mun (Ebony) bền bỉ, bấm êm tay.\n- Bộ khóa Peg: Gỗ cao cấp giữ dây chuẩn xác.\n- Giữ dây: Kim loại đối với bản S2; bản S2S dùng chất liệu gỗ.\n- Tặng trọn bộ phụ kiện: Vĩ kéo, Nhựa thông, Kê vai KPE, Sách học violin.\n- Hỗ trợ: Qua cửa hàng tại Hà Nội test trực tiếp âm thanh mộc hoặc nhận clip test riêng từng cây.`
  );
  const [ctaText, setCtaText] = useState(
    savedDraft.ctaText ??
      'Bạn ở Hà Nội có thể ghé trực tiếp để cầm đàn và nghe thử âm mộc, hoặc nhắn tin để mình gửi video test riêng từng cây nhé.'
  );

  const [uploadedPhotos, setUploadedPhotos] = useState([]);
  const [feedbackPhotos, setFeedbackPhotos] = useState([]);
  const [cutoutBusyIdx, setCutoutBusyIdx] = useState(null);
  const [dragPhotoIdx, setDragPhotoIdx] = useState(null);
  const [demoClip, setDemoClip] = useState(null);
  const [durationSec, setDurationSec] = useState(savedDraft.durationSec || 55);
  const [voiceId, setVoiceId] = useState(
    voices.find((v) => v.profile_id === 'edge_nam_nghe_nhan')?.profile_id ||
      voices[0]?.profile_id ||
      'edge_nam_minh_movie'
  );
  const [voiceSpeed, setVoiceSpeed] = useState(1.01);
  const [voicePitch, setVoicePitch] = useState(-1.4);
  const [bgmPresetId, setBgmPresetId] = useState('bgm_luxury_acoustic');
  const [customBgmPath, setCustomBgmPath] = useState(null);
  const [bgmVolume, setBgmVolume] = useState(0.06);
  const [subtitleStyle, setSubtitleStyle] = useState(savedDraft.subtitleStyle || 'CINEMA');

  useEffect(() => {
    try {
      localStorage.setItem(
        PRODUCT_DRAFT_KEY,
        JSON.stringify({
          parentGroupId,
          productName,
          category,
          copywritingTone,
          salesAngle,
          rawDescription,
          ctaText,
          durationSec,
          subtitleStyle,
        })
      );
    } catch {
      // ignore
    }
  }, [
    parentGroupId,
    productName,
    category,
    copywritingTone,
    salesAngle,
    rawDescription,
    ctaText,
    durationSec,
    subtitleStyle,
  ]);

  const [complianceReport, setComplianceReport] = useState(null);
  const [checkingPolicy, setCheckingPolicy] = useState(false);
  const [analyzingBrief, setAnalyzingBrief] = useState(false);
  const [productAiAnalysis, setProductAiAnalysis] = useState(null);
  const [uploadingPhotos, setUploadingPhotos] = useState(false);
  const [uploadingFeedback, setUploadingFeedback] = useState(false);
  const [uploadingDemo, setUploadingDemo] = useState(false);
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

  const loadTemplates = async () => {
    try {
      const list = await studioApi.listProductTemplates();
      setTemplates(list);
    } catch {
      // ignore
    }
  };

  useEffect(() => {
    loadTemplates();
    setLayoutConfig((prev) => ({
      ...prev,
      show_top_banner: false,
      sales_badge_enabled: false,
      show_photo_callouts: false,
      transition_style: prev.transition_style || 'CAPCUT_DISSOLVE',
      product_framing: prev.product_framing || 'BLURRED_STUDIO_CARD',
    }));
  }, []);

  useEffect(() => {
    const onWindowPaste = (e) => {
      if (!rootRef.current || rootRef.current.offsetParent === null) return;
      const items = e.clipboardData?.items;
      if (!items) return;
      const imageFiles = [];
      for (let i = 0; i < items.length; i += 1) {
        const it = items[i];
        if (it.kind === 'file' && (it.type.startsWith('image/') || it.type.startsWith('video/'))) {
          const f = it.getAsFile();
          if (f) {
            const ext = f.type.includes('png') ? '.png' : f.type.includes('webp') ? '.webp' : '.jpg';
            const named = new File([f], f.name || `zalo_paste_${Date.now()}_${i}${ext}`, {
              type: f.type,
            });
            imageFiles.push(named);
          }
        }
      }
      if (imageFiles.length > 0) {
        e.preventDefault();
        handlePhotosSelected(imageFiles, true);
      }
    };
    window.addEventListener('paste', onWindowPaste);
    return () => window.removeEventListener('paste', onWindowPaste);
  }, []);

  const handleScrapeProductUrl = async () => {
    const clean = scrapeUrl.trim();
    if (!isValidHttpUrl(clean)) {
      const msg = 'Vui lòng dán đường dẫn sản phẩm hợp lệ (bắt đầu bằng https://...).';
      setActiveStep(1);
      setErrors((prev) => ({ ...prev, scrapeUrl: msg }));
      scrollToFirstValidationError(rootRef);
      notify(msg);
      return;
    }
    clearError('scrapeUrl', 'photos', 'productName', 'rawDescription');
    setScrapingUrl(true);
    try {
      const res = await studioApi.scrapeProductUrl(clean);
      if (res.product_name) setProductName(res.product_name);
      if (res.raw_description) setRawDescription(res.raw_description);
      if (res.media_items?.length > 0) {
        const enriched = res.media_items.map((m) => ({ ...m, note: '', isVideo: false }));
        setUploadedPhotos((prev) => {
          const merged = [...prev, ...enriched];
          if (merged[0]?.media_url && onPreviewFrameReady) {
            onPreviewFrameReady(merged[0].media_url);
          }
          return merged;
        });
      }
      notify(
        `Đã hút thành công "${res.product_name}" kèm ${res.media_items?.length || 0} ảnh từ website.`
      );
    } catch (err) {
      notify(`Không thể hút dữ liệu từ link: ${err.message}`);
    } finally {
      setScrapingUrl(false);
    }
  };

  const handleStartBatchFromUrls = async () => {
    const rawLines = batchUrlsText
      .split(/\r?\n/)
      .map((s) => s.trim())
      .filter(Boolean);
    const urls = rawLines.filter((s) => isValidHttpUrl(s));
    const invalidCount = rawLines.length - urls.length;

    if (urls.length === 0) {
      const msg = 'Vui lòng dán ít nhất 1 đường dẫn sản phẩm hợp lệ (mỗi dòng 1 link https://...).';
      setActiveStep(1);
      setErrors((prev) => ({ ...prev, batchUrls: msg }));
      scrollToFirstValidationError(rootRef);
      notify(msg);
      return;
    }
    if (invalidCount > 0) {
      const msg = `Có ${invalidCount} dòng chưa đúng chuẩn URL https://... — vui lòng kiểm tra lại.`;
      setActiveStep(1);
      setErrors((prev) => ({ ...prev, batchUrls: msg }));
      scrollToFirstValidationError(rootRef);
      notify(msg);
      return;
    }
    if (urls.length > 20) {
      const msg = `Tối đa 20 link sản phẩm mỗi đợt (hiện đang có ${urls.length} link).`;
      setActiveStep(1);
      setErrors((prev) => ({ ...prev, batchUrls: msg }));
      scrollToFirstValidationError(rootRef);
      notify(msg);
      return;
    }

    clearError('batchUrls');
    setStartingBatch(true);
    try {
      const res = await studioApi.startProductBatchUrls({
        urls,
        product_category: category,
        copywriting_tone: copywritingTone,
        diversify_angles: batchDiversify,
        target_duration_sec: Number(durationSec),
        call_to_action: ctaText.trim(),
        voice_profile_id: voiceId,
        voice_speed_global: Number(voiceSpeed),
        voice_pitch_global: Number(voicePitch),
        subtitle_style: subtitleStyle,
        bgm_preset_id: bgmPresetId,
        custom_bgm_path: customBgmPath,
        bgm_volume: bgmVolume,
        layout_config: layoutConfig,
        parent_group_id: parentGroupId || null,
        auto_one_click: true,
      });
      notify(
        `Đã tự động hút dữ liệu & xếp hàng tạo ${res.created_count} dự án video bán hàng!`
      );
      if (res.created_projects?.[0]) {
        onProjectStarted(res.created_projects[0].project_id, res.created_projects[0].state);
      }
    } catch (err) {
      notify(`Lỗi chạy hàng loạt: ${err.message}`);
    } finally {
      setStartingBatch(false);
    }
  };

  const handleApplyTemplate = (tpl) => {
    if (!tpl) return;
    setSelectedTplId(tpl.template_id);
    setProductName(tpl.product_name);
    setCategory(tpl.product_category);
    setRawDescription(tpl.raw_description);
    setCtaText(tpl.call_to_action || ctaText);
    setComplianceReport(null);
    setLayoutConfig((prev) => ({
      ...prev,
      sales_price_or_offer: stripLeadingEmoji(tpl.offer_badge || ''),
      sales_contact_info: stripLeadingEmoji(tpl.contact_badge || ''),
    }));
    notify(`Đã nạp nội dung mẫu: ${tpl.product_name}`);
  };

  const handleSaveCurrentAsTemplate = async () => {
    if (productName.trim().length < 2) {
      notify('Vui lòng nhập tên sản phẩm trước khi lưu mẫu.');
      return;
    }
    try {
      const saved = await studioApi.saveProductTemplate({
        product_name: productName.trim(),
        product_category: category,
        raw_description: rawDescription,
        call_to_action: ctaText,
        offer_badge: layoutConfig.sales_price_or_offer || '',
        contact_badge: layoutConfig.sales_contact_info || '',
        qr_code_content: layoutConfig.qr_code_content || '',
      });
      await loadTemplates();
      setSelectedTplId(saved.template_id);
      notify(`Đã lưu "${saved.product_name}" vào danh mục cửa hàng.`);
    } catch (err) {
      notify(`Lỗi lưu mẫu: ${err.message}`);
    }
  };

  const handleDeleteTemplate = async () => {
    if (!selectedTplId) return;
    try {
      await studioApi.deleteProductTemplate(selectedTplId);
      setSelectedTplId('');
      await loadTemplates();
      notify('Đã xóa mẫu sản phẩm.');
    } catch (err) {
      notify(`Lỗi xóa mẫu: ${err.message}`);
    }
  };

  const handleCheckCompliance = async (autoApplyClean = false) => {
    setCheckingPolicy(true);
    try {
      const fullText = `${rawDescription}\n${ctaText}`;
      const rep = await studioApi.checkProductCompliance(fullText);
      setComplianceReport(rep);
      if (autoApplyClean && !rep.is_safe) {
        const cleanDesc = await studioApi.checkProductCompliance(rawDescription);
        const cleanCta = await studioApi.checkProductCompliance(ctaText);
        setRawDescription(cleanDesc.sanitized_text);
        setCtaText(cleanCta.sanitized_text);
        setComplianceReport({ ...rep, is_safe: true, safety_score: 100, issues: [] });
        notify('Đã tự động điều chỉnh từ ngữ phù hợp chính sách quảng cáo.');
      } else if (rep.is_safe) {
        notify('Nội dung an toàn (100/100 điểm), không có từ khóa hạn chế hiển thị.');
      }
    } catch (err) {
      notify(`Lỗi kiểm tra từ ngữ: ${err.message}`);
    } finally {
      setCheckingPolicy(false);
    }
  };

  const handlePhotosSelected = async (files, fromClipboard = false) => {
    if (!files || files.length === 0) return;
    const allowedMediaExts = [
      '.jpg',
      '.jpeg',
      '.png',
      '.webp',
      '.bmp',
      '.mp4',
      '.mov',
      '.mkv',
      '.webm',
      '.avi',
      '.m4v',
    ];
    const invalidFile = Array.from(files).find(
      (f) => f.name && !hasAllowedExtension(f.name, allowedMediaExts)
    );
    if (invalidFile) {
      const msg = `Tệp "${invalidFile.name}" không đúng định dạng Ảnh/Video hỗ trợ (.jpg, .png, .webp, .mp4, .mov).`;
      setErrors((prev) => ({ ...prev, photos: msg }));
      notify(msg);
      return;
    }
    clearError('photos');
    setUploadingPhotos(true);
    try {
      const results = await studioApi.uploadBatchFiles(files, 'product_photo');
      const enriched = results.map((r) => ({
        ...r,
        note: '',
        isVideo: VIDEO_EXT_RE.test(r.original_name || ''),
      }));
      setUploadedPhotos((prev) => {
        const merged = [...prev, ...enriched];
        const firstImg = merged.find((x) => !x.isVideo);
        if (firstImg?.media_url && onPreviewFrameReady) {
          onPreviewFrameReady(firstImg.media_url);
        }
        return merged;
      });
      notify(
        fromClipboard
          ? `Đã dán trực tiếp ${results.length} ảnh từ Clipboard/Zalo vào dự án.`
          : `Đã thêm ${results.length} tệp — cam kết lên hình đủ 100% theo đúng thứ tự.`
      );
    } catch (err) {
      notify(`Lỗi tải tệp sản phẩm: ${err.message}`);
    } finally {
      setUploadingPhotos(false);
    }
  };

  const handleSinglePhotoCutout = async (idx) => {
    const target = uploadedPhotos[idx];
    if (!target || target.isVideo) return;
    setCutoutBusyIdx(idx);
    try {
      const res = await studioApi.previewPhotoCutout(target.local_path);
      setUploadedPhotos((prev) =>
        prev.map((item, i) =>
          i !== idx
            ? item
            : { ...item, local_path: res.local_path, media_url: res.media_url, cutoutDone: true }
        )
      );
      if (idx === 0 && onPreviewFrameReady) onPreviewFrameReady(res.media_url);
      notify(`Đã tách nền Studio cho Ảnh ${idx + 1}.`);
    } catch (err) {
      notify(`Lỗi tách nền: ${err.message}`);
    } finally {
      setCutoutBusyIdx(null);
    }
  };

  const handleFeedbackUpload = async (e) => {
    const files = e.target.files;
    if (!files?.length) return;
    setUploadingFeedback(true);
    try {
      const res = await studioApi.uploadBatchFiles(files, 'customer_feedback');
      setFeedbackPhotos((prev) => [...prev, ...res].slice(0, 2));
      notify('Đã đính kèm ảnh đánh giá thực tế của khách hàng.');
    } catch (err) {
      notify(`Lỗi tải ảnh feedback: ${err.message}`);
    } finally {
      setUploadingFeedback(false);
      e.target.value = '';
    }
  };

  const movePhoto = (fromIdx, toIdx) => {
    setUploadedPhotos((prev) => {
      if (toIdx < 0 || toIdx >= prev.length || fromIdx === toIdx) return prev;
      const copy = [...prev];
      const [picked] = copy.splice(fromIdx, 1);
      copy.splice(toIdx, 0, picked);
      const firstImg = copy.find((x) => !x.isVideo);
      if (firstImg?.media_url && onPreviewFrameReady) {
        onPreviewFrameReady(firstImg.media_url);
      }
      return copy;
    });
  };

  const handlePhotoNoteChange = (idx, note) => {
    setUploadedPhotos((prev) =>
      prev.map((item, i) => (i !== idx ? item : { ...item, note }))
    );
  };

  const handleDemoUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploadingDemo(true);
    try {
      const res = await studioApi.uploadStudioFile(file, 'product_demo');
      const isVideo = VIDEO_EXT_RE.test(res.original_name || '');
      setDemoClip({ ...res, isVideo });
      notify(`Đã đính kèm tệp âm thanh/clip mộc: ${res.original_name}`);
    } catch (err) {
      notify(`Lỗi tải tệp thực tế: ${err.message}`);
    } finally {
      setUploadingDemo(false);
      e.target.value = '';
    }
  };

  const updateSalesLayout = (patch) => setLayoutConfig((prev) => ({ ...prev, ...patch }));

  const handleExpandProductBrief = async () => {
    const cleanName = productName.trim();
    const cleanDesc = rawDescription.trim();
    const nextErrs = {};
    if ((cleanName + cleanDesc).length < 4) {
      nextErrs.productName =
        'Vui lòng nhập tên sản phẩm hoặc vài từ mô tả ngắn trước khi bấm Phân tích AI.';
    } else if (cleanName.length > 160) {
      nextErrs.productName = 'Tên sản phẩm tối đa 160 ký tự.';
    }
    if (Object.keys(nextErrs).length > 0) {
      setActiveStep(1);
      setErrors((prev) => ({ ...prev, ...nextErrs }));
      scrollToFirstValidationError(rootRef);
      notify(Object.values(nextErrs)[0]);
      return;
    }
    clearError('productName', 'rawDescription');
    setAnalyzingBrief(true);
    try {
      const res = await studioApi.expandShortBrief({
        mode: 'PRODUCT_SHOWCASE',
        raw_title: productName.trim(),
        short_brief: rawDescription.trim(),
        product_category: category,
        target_duration_sec: Number(durationSec),
        part_count: 1,
      });
      if (res.refined_title) setProductName(res.refined_title);
      if (res.expanded_description) setRawDescription(res.expanded_description);
      if (res.recommended_cta) setCtaText(res.recommended_cta);
      if (res.recommended_tone) setCopywritingTone(res.recommended_tone);
      if (res.recommended_sales_angle) setSalesAngle(res.recommended_sales_angle);
      if (res.recommended_duration_sec) setDurationSec(Number(res.recommended_duration_sec));
      if (res.recommended_voice_id && voices.some((v) => v.profile_id === res.recommended_voice_id)) {
        const mv = voices.find((v) => v.profile_id === res.recommended_voice_id);
        setVoiceId(mv.profile_id);
        if (typeof mv.speed_rate === 'number') setVoiceSpeed(mv.speed_rate);
        if (typeof mv.pitch_hz === 'number') setVoicePitch(mv.pitch_hz);
      }
      if (res.recommended_bgm_id && bgmPresets.some((b) => b.preset_id === res.recommended_bgm_id)) {
        setBgmPresetId(res.recommended_bgm_id);
      }
      setComplianceReport(null);
      setProductAiAnalysis(res);
      notify(
        res.used_api_key
          ? 'Đã phân tích chuyên sâu & viết chi tiết mô tả sản phẩm chuẩn bán hàng!'
          : 'Đã mở rộng mô tả chi tiết cho sản phẩm!'
      );
    } catch (err) {
      notify(`Lỗi phân tích AI: ${err.message}`);
    } finally {
      setAnalyzingBrief(false);
    }
  };

  const handleStart = async (autoOneClick) => {
    const cleanName = productName.trim();
    const cleanDesc = rawDescription.trim();
    const nextErrs = {};

    if (uploadedPhotos.length === 0) {
      nextErrs.photos =
        'Bắt buộc tải lên hoặc dán (Ctrl+V) ít nhất 1 ảnh hoặc video sản phẩm ở Bước 1.';
    } else if (Boolean(layoutConfig.comparison_split_enabled) && uploadedPhotos.length < 2) {
      nextErrs.photos =
        'Bạn đang bật chế độ "Chia đôi so sánh A/B" — vui lòng tải lên ít nhất 2 ảnh sản phẩm.';
    }

    if (cleanName.length < 2) {
      nextErrs.productName = 'Vui lòng nhập tên sản phẩm (tối thiểu 2 ký tự).';
    } else if (cleanName.length > 160) {
      nextErrs.productName = 'Tên sản phẩm tối đa 160 ký tự.';
    }

    if (cleanDesc.length < 5) {
      nextErrs.rawDescription =
        'Vui lòng nhập mô tả ngắn hoặc thông số chính của sản phẩm (tối thiểu 5 ký tự).';
    }

    if (Object.keys(nextErrs).length > 0) {
      setActiveStep(1);
      setErrors(nextErrs);
      scrollToFirstValidationError(rootRef);
      notify(Object.values(nextErrs)[0]);
      return;
    }

    setErrors({});
    setSubmitting(true);
    try {
      const fbPaths = feedbackPhotos.map((f) => f.local_path);
      const mergedLayout = {
        ...layoutConfig,
        feedback_image_paths: fbPaths,
      };
      const res = await studioApi.startProductProject({
        product_name: productName.trim(),
        product_category: category,
        sales_angle: salesAngle,
        copywriting_tone: copywritingTone,
        variant_count: Number(variantCount),
        raw_description: rawDescription,
        image_paths: uploadedPhotos.map((p) => p.local_path),
        photo_notes: uploadedPhotos.map((p) => p.note || ''),
        feedback_image_paths: fbPaths,
        comparison_enabled: Boolean(layoutConfig.comparison_split_enabled),
        comparison_left_label: layoutConfig.comparison_label_a || 'Phiên bản A',
        comparison_right_label: layoutConfig.comparison_label_b || 'Phiên bản B',
        demo_clip_path: demoClip?.local_path || null,
        target_duration_sec: Number(durationSec),
        call_to_action: ctaText.trim(),
        voice_profile_id: voiceId,
        voice_speed_global: Number(voiceSpeed),
        voice_pitch_global: Number(voicePitch),
        subtitle_style: subtitleStyle,
        bgm_preset_id: bgmPresetId,
        custom_bgm_path: customBgmPath,
        bgm_volume: bgmVolume,
        layout_config: mergedLayout,
        parent_group_id: parentGroupId || null,
        auto_one_click: autoOneClick,
      });
      onProjectStarted(res.project_id, res.state);
    } catch (err) {
      notify(`Lỗi khởi tạo video: ${err.message}`);
    } finally {
      setSubmitting(false);
    }
  };

  useEffect(() => {
    const onKeyDown = (e) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
        if (!rootRef.current || rootRef.current.offsetParent === null) return;
        if (submitting || uploadingPhotos || uploadingDemo) return;
        e.preventDefault();
        handleStart(true);
      }
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  });

  const stepItems = [
    {
      title: 'Ảnh / Clip & Sản phẩm',
      meta:
        uploadedPhotos.length > 0
          ? `${uploadedPhotos.length} tệp • ${productName.trim().slice(0, 22)}`
          : 'Tải ảnh/video hoặc dán Ctrl+V',
      done: uploadedPhotos.length > 0 && productName.trim().length >= 2,
    },
    {
      title: 'Khung CapCut & Giọng đọc',
      meta: `${layoutConfig.aspect_ratio || '9:16'} • Chuyển cảnh mượt`,
      done: activeStep > 2,
    },
    {
      title: 'Ảnh bìa & Xuất bản',
      meta: `~${durationSec}s • ${variantCount} bản`,
      done: false,
    },
  ];

  const showStep1 = showAllSteps || activeStep === 1;
  const showStep2 = showAllSteps || activeStep === 2;
  const showStep3 = showAllSteps || activeStep === 3;

  return (
    <div ref={rootRef} className="card">
      <StudioPageHeader
        icon={ShoppingBag}
        title="Video Giới Thiệu & Bán Sản Phẩm"
        subtitle="Dán ảnh từ Zalo (Ctrl+V), hút dữ liệu từ Website, trộn đa clip + ảnh, tách nền Studio & vẽ sóng âm thực tế"
        badges={[
          {
            label: apiKeyConfigured ? 'AI sẵn sàng' : 'Chưa gắn API Key',
            cls: apiKeyConfigured ? 'badge-ok' : 'badge-warn',
            icon: KeyRound,
          },
          { label: `${uploadedPhotos.length} tư liệu`, cls: 'badge-info' },
          { label: `~${durationSec}s`, cls: '' },
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

      {/* ==================== BƯỚC 1: ẢNH / CLIP & THÔNG TIN SẢN PHẨM ==================== */}
      {showStep1 && (
        <div className="step-box fade-slide-in">
          <div className="step-header">
            <span className="step-num">1</span>
            <div style={{ flex: 1 }}>
              <div className="step-title">Tư liệu hình ảnh &amp; Nội dung giới thiệu sản phẩm</div>
              <div className="step-desc">
                Thả trộn lẫn ảnh chụp và video quay cận, hút nhanh từ Website cửa hàng hoặc chọn từ Kho mẫu đã lưu
              </div>
            </div>
            <span className="badge badge-info">
              <ClipboardPaste size={12} /> Dán nhanh Ctrl+V từ Zalo
            </span>
          </div>

          {/* QUICK IMPORT & CATALOG STRIP */}
          <div className="surface-box" style={{ marginBottom: 16 }}>
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
              <Globe size={16} style={{ color: 'var(--brand-text)', flexShrink: 0 }} />
              <input
                className={`input ${errors.scrapeUrl ? 'input-error' : ''}`}
                style={{ flex: 1, minWidth: 220 }}
                placeholder="Dán link sản phẩm trên Website để tự lấy tên, mô tả & bộ ảnh..."
                value={scrapeUrl}
                onChange={(e) => {
                  setScrapeUrl(e.target.value);
                  clearError('scrapeUrl');
                }}
                onKeyDown={(e) => e.key === 'Enter' && handleScrapeProductUrl()}
              />
              <button
                type="button"
                className="btn btn-primary btn-sm"
                style={{ minHeight: 40 }}
                disabled={scrapingUrl}
                onClick={handleScrapeProductUrl}
              >
                {scrapingUrl ? <Loader2 size={14} className="spin" /> : <Globe size={14} />}
                <span>{scrapingUrl ? 'Đang hút...' : 'Hút 1 link'}</span>
              </button>
              <button
                type="button"
                className={`btn btn-sm ${showBatchPanel ? 'btn-primary' : 'btn-secondary'}`}
                style={{ minHeight: 40 }}
                onClick={() => setShowBatchPanel((p) => !p)}
              >
                <Layers size={14} /> Nhiều link
              </button>
            </div>
            <FieldError message={errors.scrapeUrl} />

            <StudioLoadingBanner
              loading={scrapingUrl}
              title="Đang hút thông tin & tải bộ ảnh gốc từ trang sản phẩm..."
              subtitle="Hệ thống đang bóc tách tên sản phẩm, thông số kỹ thuật và ảnh độ phân giải cao"
              steps={['Kết nối Website sản phẩm', 'Trích xuất mô tả & tải bộ ảnh về máy']}
              stepIntervalMs={2400}
            />

            {showBatchPanel && (
              <div className="studio-callout studio-callout-brand fade-slide-in" style={{ marginTop: 12 }}>
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
                  <strong className="text-sm text-brand">
                    Sản xuất hàng loạt từ danh sách Link sản phẩm (1 – 20 link/lần)
                  </strong>
                  <span className="badge badge-info">
                    {
                      batchUrlsText
                        .split(/\r?\n/)
                        .map((s) => s.trim())
                        .filter((s) => isValidHttpUrl(s)).length
                    }
                    /20 link hợp lệ
                  </span>
                </div>
                <textarea
                  className={`textarea ${errors.batchUrls ? 'input-error' : ''}`}
                  style={{ minHeight: 92, marginBottom: 8 }}
                  placeholder={`Dán mỗi dòng 1 đường dẫn sản phẩm:\nhttps://www.sonmusic.vn/dan-violin-avaro-s2\nhttps://www.sonmusic.vn/dan-violin-avaro-s2s`}
                  value={batchUrlsText}
                  onChange={(e) => {
                    setBatchUrlsText(e.target.value);
                    clearError('batchUrls');
                  }}
                />
                <FieldError message={errors.batchUrls} />
                <StudioLoadingBanner
                  loading={startingBatch}
                  title="Đang quét danh sách sản phẩm & khởi tạo hàng đợi xuất loạt video..."
                  steps={['Đọc dữ liệu từng trang sản phẩm', 'Xếp lịch dựng video tự động']}
                  stepIntervalMs={2800}
                />
                <div
                  style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    gap: 10,
                    flexWrap: 'wrap',
                    marginTop: 8,
                  }}
                >
                  <SwitchCard checked={batchDiversify} onChange={setBatchDiversify}>
                    Tự xoay vòng 4 góc kịch bản để các video không lặp câu chữ
                  </SwitchCard>
                  <button
                    type="button"
                    className="btn btn-primary"
                    disabled={startingBatch}
                    onClick={handleStartBatchFromUrls}
                  >
                    {startingBatch ? <Loader2 size={15} className="spin" /> : <Layers size={15} />}
                    <span>{startingBatch ? 'Đang hút danh sách...' : 'Hút & Xếp hàng xuất loạt'}</span>
                  </button>
                </div>
              </div>
            )}

            <div
              style={{
                display: 'flex',
                gap: 8,
                flexWrap: 'wrap',
                alignItems: 'center',
                marginTop: 10,
                paddingTop: 10,
                borderTop: '1px solid var(--border)',
              }}
            >
              <Package size={16} style={{ color: 'var(--brand-text)', flexShrink: 0 }} />
              <select
                className="select"
                style={{ flex: 1, minWidth: 200 }}
                value={selectedTplId}
                onChange={(e) => {
                  const id = e.target.value;
                  setSelectedTplId(id);
                  const found = templates.find((t) => t.template_id === id);
                  if (found) handleApplyTemplate(found);
                }}
              >
                <option value="">Chọn nhanh sản phẩm đã lưu trong kho ({templates.length})</option>
                {templates.map((t) => (
                  <option key={t.template_id} value={t.template_id}>
                    {t.product_name}
                  </option>
                ))}
              </select>
              <button
                type="button"
                className="btn btn-secondary btn-sm"
                style={{ minHeight: 40 }}
                onClick={handleSaveCurrentAsTemplate}
              >
                <BookmarkPlus size={14} /> Lưu mẫu
              </button>
              {selectedTplId && (
                <button
                  type="button"
                  className="btn btn-danger btn-sm"
                  style={{ minHeight: 40 }}
                  onClick={handleDeleteTemplate}
                  title="Xóa mẫu này khỏi kho"
                >
                  <Trash2 size={14} />
                </button>
              )}
            </div>
          </div>

          {/* PHOTO & CLIP UPLOADER */}
          <div style={{ marginBottom: 18 }}>
            <div
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                marginBottom: 8,
              }}
            >
              <label className="form-label" style={{ marginBottom: 0 }}>
                Bộ ảnh &amp; clip sản phẩm ({uploadedPhotos.length} mục)
              </label>
              {uploadedPhotos.length > 0 && (
                <button
                  type="button"
                  className="btn btn-danger btn-sm"
                  onClick={() => setUploadedPhotos([])}
                >
                  <Trash2 size={13} /> Xóa hết
                </button>
              )}
            </div>

            <MediaDropzone
              accept="image/*,video/*"
              multiple
              disabled={uploadingPhotos}
              loading={uploadingPhotos}
              error={errors.photos}
              icon={Images}
              title={
                uploadingPhotos
                  ? 'Đang tải tệp đa phương tiện lên...'
                  : 'Kéo thả nhiều Ảnh + Video quay cận vào đây, bấm chọn tệp, hoặc bấm Ctrl+V dán ảnh Zalo'
              }
              hint="Hỗ trợ JPG, PNG, WEBP và MP4, MOV — lên hình đủ 100% số lượng theo đúng thứ tự sắp xếp"
              onFilesSelected={(fl) => handlePhotosSelected(fl, false)}
            />

            {uploadedPhotos.length > 0 && (
              <div
                style={{
                  display: 'grid',
                  gridTemplateColumns: 'repeat(auto-fill, minmax(148px, 1fr))',
                  gap: 10,
                  marginTop: 14,
                }}
              >
                {uploadedPhotos.map((ph, idx) => (
                  <div
                    key={`${ph.local_path}_${idx}`}
                    draggable
                    onDragStart={() => setDragPhotoIdx(idx)}
                    onDragOver={(e) => e.preventDefault()}
                    onDrop={() => {
                      if (dragPhotoIdx !== null) movePhoto(dragPhotoIdx, idx);
                      setDragPhotoIdx(null);
                    }}
                    style={{
                      background: 'var(--bg-panel)',
                      border: idx === 0 ? '1.5px solid var(--brand)' : '1px solid var(--border)',
                      borderRadius: 10,
                      padding: 8,
                    }}
                  >
                    <div
                      onClick={() =>
                        !ph.isVideo && onPreviewFrameReady && onPreviewFrameReady(ph.media_url)
                      }
                      title="Bấm để xem thử trên khung điện thoại • Kéo thả để đổi thứ tự"
                      style={{
                        position: 'relative',
                        borderRadius: 7,
                        overflow: 'hidden',
                        aspectRatio: '3 / 4',
                        cursor: 'grab',
                        marginBottom: 6,
                        background: '#080a0f',
                      }}
                    >
                      {ph.isVideo ? (
                        <video
                          src={ph.media_url}
                          muted
                          loop
                          playsInline
                          onMouseEnter={(e) => e.currentTarget.play().catch(() => {})}
                          onMouseLeave={(e) => e.currentTarget.pause()}
                          style={{ width: '100%', height: '100%', objectFit: 'contain' }}
                        />
                      ) : (
                        <img
                          src={ph.media_url}
                          alt={ph.original_name}
                          style={{ width: '100%', height: '100%', objectFit: 'contain' }}
                        />
                      )}
                      <span
                        className="text-xs fw-700"
                        style={{
                          position: 'absolute',
                          left: 6,
                          bottom: 6,
                          background: ph.isVideo
                            ? 'rgba(16, 185, 129, 0.92)'
                            : idx === 0
                            ? 'rgba(79, 70, 229, 0.94)'
                            : 'rgba(9, 9, 11, 0.86)',
                          color: '#ffffff',
                          padding: '2px 7px',
                          borderRadius: 5,
                        }}
                      >
                        {ph.isVideo
                          ? `Cảnh ${idx + 1} • Video`
                          : idx === 0
                          ? 'Mở màn'
                          : `Ảnh ${idx + 1}`}
                      </span>

                      {!ph.isVideo ? (
                        <button
                          type="button"
                          disabled={cutoutBusyIdx === idx}
                          title="Tách nền sang phông Studio cho riêng bức ảnh này"
                          onClick={(ev) => {
                            ev.stopPropagation();
                            handleSinglePhotoCutout(idx);
                          }}
                          className="text-xs fw-600"
                          style={{
                            position: 'absolute',
                            top: 6,
                            left: 6,
                            height: 24,
                            padding: '0 8px',
                            borderRadius: 6,
                            border: '1px solid rgba(255,255,255,0.22)',
                            background: ph.cutoutDone
                              ? 'rgba(5, 150, 105, 0.92)'
                              : 'rgba(9, 9, 11, 0.88)',
                            color: '#ffffff',
                            display: 'inline-flex',
                            alignItems: 'center',
                            gap: 4,
                            cursor: 'pointer',
                          }}
                        >
                          <Wand2 size={11} />{' '}
                          {cutoutBusyIdx === idx ? '...' : ph.cutoutDone ? 'Đã tách' : 'Tách nền'}
                        </button>
                      ) : (
                        <button
                          type="button"
                          title="Cắt chọn đúng đoạn giây đẹp nhất của clip này"
                          onClick={(ev) => {
                            ev.stopPropagation();
                            setTrimOpenIdx((prev) => (prev === idx ? null : idx));
                          }}
                          className="text-xs fw-600"
                          style={{
                            position: 'absolute',
                            top: 6,
                            left: 6,
                            height: 24,
                            padding: '0 8px',
                            borderRadius: 6,
                            border: '1px solid rgba(255,255,255,0.22)',
                            background: ph.trimmedDone
                              ? 'rgba(5, 150, 105, 0.92)'
                              : 'rgba(9, 9, 11, 0.88)',
                            color: '#ffffff',
                            display: 'inline-flex',
                            alignItems: 'center',
                            gap: 4,
                            cursor: 'pointer',
                          }}
                        >
                          <Scissors size={11} /> {ph.trimmedDone ? 'Đã cắt' : 'Cắt đoạn'}
                        </button>
                      )}

                      <button
                        type="button"
                        onClick={(ev) => {
                          ev.stopPropagation();
                          setUploadedPhotos((prev) => prev.filter((_, i) => i !== idx));
                        }}
                        style={{
                          position: 'absolute',
                          top: 6,
                          right: 6,
                          width: 24,
                          height: 24,
                          borderRadius: 6,
                          border: 'none',
                          background: 'rgba(9, 9, 11, 0.86)',
                          color: '#ffffff',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          cursor: 'pointer',
                        }}
                      >
                        <X size={13} />
                      </button>
                    </div>

                    <div
                      style={{
                        display: 'flex',
                        justifyContent: 'space-between',
                        gap: 4,
                        marginBottom: layoutConfig.show_photo_callouts && !ph.isVideo ? 6 : 0,
                      }}
                    >
                      <button
                        type="button"
                        className="btn btn-secondary btn-sm"
                        style={{ padding: '2px 7px', minHeight: 28 }}
                        disabled={idx === 0}
                        title="Đẩy sang trước"
                        onClick={() => movePhoto(idx, idx - 1)}
                      >
                        <ArrowLeft size={12} />
                      </button>
                      {idx > 0 && (
                        <button
                          type="button"
                          className="btn btn-secondary btn-sm"
                          style={{ padding: '2px 6px', minHeight: 28, flex: 1 }}
                          title="Đưa lên làm cảnh đầu tiên mở màn"
                          onClick={() => movePhoto(idx, 0)}
                        >
                          <Star size={11} /> Lên đầu
                        </button>
                      )}
                      <button
                        type="button"
                        className="btn btn-secondary btn-sm"
                        style={{ padding: '2px 7px', minHeight: 28 }}
                        disabled={idx === uploadedPhotos.length - 1}
                        title="Đẩy ra sau"
                        onClick={() => movePhoto(idx, idx + 1)}
                      >
                        <ArrowRight size={12} />
                      </button>
                    </div>

                    {layoutConfig.show_photo_callouts && !ph.isVideo && (
                      <input
                        className="input input-sm"
                        placeholder="Nhãn ngắn trên ảnh..."
                        value={ph.note}
                        onChange={(e) => handlePhotoNoteChange(idx, e.target.value)}
                      />
                    )}
                  </div>
                ))}
              </div>
            )}

            {trimOpenIdx !== null && uploadedPhotos[trimOpenIdx]?.isVideo && (
              <InlineClipTrimmer
                mediaItem={uploadedPhotos[trimOpenIdx]}
                playerRef={null}
                notify={notify}
                onTrimApplied={(trimmedRes) => {
                  setUploadedPhotos((prev) =>
                    prev.map((it, idx) =>
                      idx !== trimOpenIdx
                        ? it
                        : {
                            ...it,
                            local_path: trimmedRes.local_path,
                            media_url: trimmedRes.media_url,
                            duration_ms: trimmedRes.duration_ms,
                            trimmedDone: true,
                          }
                    )
                  );
                  setTrimOpenIdx(null);
                }}
              />
            )}
          </div>

          {/* PRODUCT COPYWRITING & DESCRIPTION */}
          <div className="form-grid">
            <div className="form-group">
              <label className="form-label">Tên sản phẩm</label>
              <input
                className={`input ${errors.productName ? 'input-error' : ''}`}
                value={productName}
                onChange={(e) => {
                  setProductName(e.target.value);
                  clearError('productName');
                }}
              />
              <FieldError message={errors.productName} />
            </div>
            <div className="form-group">
              <label className="form-label">Nhóm mặt hàng</label>
              <select
                className="select"
                value={category}
                onChange={(e) => setCategory(e.target.value)}
              >
                <option value="MUSICAL_INSTRUMENT">Nhạc cụ (Đàn Violin, Guitar, Piano...)</option>
                <option value="FASHION_APPAREL">Thời trang, Quần áo &amp; Phụ kiện</option>
                <option value="GENERAL_PRODUCT">Sản phẩm tiêu dùng chung</option>
              </select>
            </div>
          </div>

          <div className="form-group">
            <label className="form-label">Phong cách lời bình &amp; Trọng tâm nội dung</label>
            <ModeChoiceGrid
              options={TONE_CHOICES}
              value={copywritingTone}
              onChange={setCopywritingTone}
            />
          </div>

          <div className="form-group">
            <label className="form-label">Góc tiếp cận tư vấn khách hàng</label>
            <ModeChoiceGrid
              options={ANGLE_CHOICES}
              value={salesAngle}
              onChange={setSalesAngle}
            />
          </div>

          <div className="form-group" style={{ marginBottom: 0 }}>
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
              <label className="form-label" style={{ marginBottom: 0 }}>
                Mô tả sản phẩm &amp; điểm nổi bật
              </label>
              <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                <button
                  type="button"
                  className="btn btn-secondary btn-sm"
                  disabled={checkingPolicy}
                  onClick={() => handleCheckCompliance(false)}
                >
                  <ShieldCheck size={14} />
                  <span>{checkingPolicy ? 'Đang kiểm tra...' : 'Kiểm tra từ hạn chế TikTok'}</span>
                </button>
                <button
                  type="button"
                  className="btn btn-primary btn-sm"
                  disabled={analyzingBrief || submitting}
                  onClick={handleExpandProductBrief}
                >
                  {analyzingBrief ? <Loader2 size={13} className="spin" /> : <Wand2 size={13} />}
                  <span>{analyzingBrief ? 'Đang viết...' : 'Phân tích & Viết chi tiết (AI)'}</span>
                </button>
              </div>
            </div>
            <textarea
              className={`textarea ${errors.rawDescription ? 'input-error' : ''}`}
              style={{ minHeight: 124 }}
              placeholder="Gõ ngắn gọn vài thông số (VD: Đàn Guitar gỗ thông nguyên tấm cho người mới tập, âm ấm, tặng kèm bao da) rồi bấm Phân tích AI..."
              value={rawDescription}
              onChange={(e) => {
                setRawDescription(e.target.value);
                clearError('rawDescription');
                if (complianceReport) setComplianceReport(null);
              }}
            />
            <FieldError message={errors.rawDescription} />
          </div>

          <StudioLoadingBanner
            loading={analyzingBrief}
            showSkeleton={!productAiAnalysis}
            title="Đang phân tích sản phẩm & viết lời bình bán hàng truyền cảm..."
            subtitle="Hệ thống đang chuyển hóa thông số khô cứng thành lời kể tự nhiên có chiều sâu"
            steps={[
              'Phân tích điểm đắt giá của sản phẩm',
              'Viết kịch bản lời bình & câu kêu gọi hành động (CTA)',
            ]}
            stepIntervalMs={2400}
          />

          {productAiAnalysis && (
            <div className="studio-callout studio-callout-success fade-slide-in" style={{ marginTop: 12 }}>
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
                <strong
                  className="text-sm text-success"
                  style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}
                >
                  <CheckCircle2 size={15} />
                  <span>
                    {productAiAnalysis.used_api_key
                      ? 'AI đã nâng cấp tiêu đề, mô tả chi tiết & chọn giọng tư vấn tối ưu'
                      : 'Đã chuẩn hóa mô tả chi tiết cho sản phẩm'}
                  </span>
                </strong>
              </div>
              {productAiAnalysis.analysis_summary && (
                <div className="text-xs text-sub" style={{ marginBottom: 6 }}>
                  {productAiAnalysis.analysis_summary}
                </div>
              )}
              {productAiAnalysis.alternative_titles?.length > 0 && (
                <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                  {productAiAnalysis.alternative_titles.map((alt, idx) => (
                    <button
                      key={idx}
                      type="button"
                      className="filter-pill"
                      onClick={() => setProductName(alt)}
                    >
                      Đổi tên: {alt}
                    </button>
                  ))}
                </div>
              )}
            </div>
          )}

          {complianceReport && (
            <div
              className={`studio-callout ${
                complianceReport.is_safe ? 'studio-callout-success' : ''
              } fade-slide-in`}
              style={{
                marginTop: 12,
                borderColor: complianceReport.is_safe ? undefined : 'var(--gold-border)',
                background: complianceReport.is_safe ? undefined : 'var(--gold-soft)',
              }}
            >
              {complianceReport.is_safe ? (
                <div
                  className="text-sm fw-600 text-success"
                  style={{ display: 'flex', alignItems: 'center', gap: 7 }}
                >
                  <CheckCircle2 size={16} /> Đạt {complianceReport.safety_score}/100 điểm — Không có từ khóa vi phạm chính sách hiển thị.
                </div>
              ) : (
                <div>
                  <div
                    style={{
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                      gap: 8,
                      marginBottom: 6,
                      flexWrap: 'wrap',
                    }}
                  >
                    <strong className="text-sm" style={{ color: 'var(--gold-text)' }}>
                      Phát hiện {complianceReport.issues.length} cụm từ dễ bị hạn chế phân phối:
                    </strong>
                    <button
                      type="button"
                      className="btn btn-primary btn-sm"
                      onClick={() => handleCheckCompliance(true)}
                    >
                      Tự động thay thế an toàn
                    </button>
                  </div>
                  {complianceReport.issues.map((iss, i) => (
                    <div key={i} className="text-xs text-sub" style={{ marginTop: 3 }}>
                      - &quot;{iss.phrase}&quot; → Đổi thành: <strong>&quot;{iss.suggestion}&quot;</strong>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          <StudioCollapsible
            icon={Music2}
            title="Đính kèm Tiếng đàn mộc, Ảnh Feedback khách hàng & Nhóm Dự Án Cha"
            subtitle="Tùy chọn chèn đoạn thu âm mộc 5–20s, ảnh đánh giá thực tế hoặc gán vào Bộ sưu tập"
            defaultOpen={Boolean(demoClip || feedbackPhotos.length > 0)}
            badge={
              demoClip || feedbackPhotos.length > 0
                ? `${demoClip ? '1 clip mộc ' : ''}${
                    feedbackPhotos.length > 0 ? `• ${feedbackPhotos.length} feedback` : ''
                  }`
                : ''
            }
          >
            <div className="form-grid" style={{ marginBottom: 14 }}>
              <div className="surface-box">
                <div
                  style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    gap: 8,
                    flexWrap: 'wrap',
                  }}
                >
                  <div>
                    <div className="text-sm fw-600">Tiếng đàn mộc / Clip test âm (5–20s)</div>
                    <div className="text-xs text-sub" style={{ marginTop: 2 }}>
                      Tự ngắt giọng đọc &amp; vẽ sóng âm vàng kim theo tiếng đàn thực
                    </div>
                  </div>
                  <div style={{ display: 'flex', gap: 6 }}>
                    <label className="btn btn-secondary btn-sm" style={{ cursor: 'pointer' }}>
                      <Music2 size={14} />{' '}
                      {uploadingDemo ? 'Đang tải...' : demoClip ? 'Đổi tệp' : 'Chọn tệp mộc'}
                      <input
                        type="file"
                        accept="video/*,audio/*"
                        hidden
                        disabled={uploadingDemo}
                        onChange={handleDemoUpload}
                      />
                    </label>
                    {demoClip && (
                      <button
                        type="button"
                        className="btn btn-danger btn-sm"
                        onClick={() => setDemoClip(null)}
                      >
                        <X size={13} />
                      </button>
                    )}
                  </div>
                </div>
                {demoClip?.media_url && (
                  <div style={{ marginTop: 10 }}>
                    {demoClip.isVideo ? (
                      <video
                        ref={demoPlayerRef}
                        controls
                        src={demoClip.media_url}
                        onLoadedMetadata={(e) => {
                          const dMs = Math.round((e.currentTarget.duration || 0) * 1000);
                          if (dMs > 500 && !demoClip.duration_ms) {
                            setDemoClip((prev) => (prev ? { ...prev, duration_ms: dMs } : prev));
                          }
                        }}
                        style={{ width: '100%', maxHeight: 145, borderRadius: 8, background: '#000' }}
                      />
                    ) : (
                      <audio
                        ref={demoPlayerRef}
                        controls
                        src={demoClip.media_url}
                        onLoadedMetadata={(e) => {
                          const dMs = Math.round((e.currentTarget.duration || 0) * 1000);
                          if (dMs > 500 && !demoClip.duration_ms) {
                            setDemoClip((prev) => (prev ? { ...prev, duration_ms: dMs } : prev));
                          }
                        }}
                        style={{ width: '100%', height: 36 }}
                      />
                    )}
                    <InlineClipTrimmer
                      mediaItem={demoClip}
                      playerRef={demoPlayerRef}
                      notify={notify}
                      onTrimApplied={(trimmedRes) =>
                        setDemoClip((prev) =>
                          prev
                            ? {
                                ...prev,
                                local_path: trimmedRes.local_path,
                                media_url: trimmedRes.media_url,
                                duration_ms: trimmedRes.duration_ms,
                                trimmedDone: true,
                              }
                            : prev
                        )
                      }
                    />
                  </div>
                )}
              </div>

              <div className="surface-box">
                <div
                  style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    gap: 8,
                    flexWrap: 'wrap',
                  }}
                >
                  <div>
                    <div className="text-sm fw-600">Ảnh khách khen / Feedback thực tế</div>
                    <div className="text-xs text-sub" style={{ marginTop: 2 }}>
                      Chèn 1–2 ảnh chụp tin nhắn khách phản hồi gần cuối video
                    </div>
                  </div>
                  <label className="btn btn-secondary btn-sm" style={{ cursor: 'pointer' }}>
                    <MessageSquarePlus size={14} />{' '}
                    {uploadingFeedback ? 'Đang tải...' : `Đính kèm (${feedbackPhotos.length}/2)`}
                    <input
                      type="file"
                      accept="image/*"
                      multiple
                      hidden
                      disabled={uploadingFeedback}
                      onChange={handleFeedbackUpload}
                    />
                  </label>
                </div>
                {feedbackPhotos.length > 0 && (
                  <div style={{ display: 'flex', gap: 10, marginTop: 10 }}>
                    {feedbackPhotos.map((fb, fIdx) => (
                      <div key={fIdx} style={{ position: 'relative', width: 60, height: 60 }}>
                        <img
                          src={fb.media_url}
                          alt="Feedback"
                          style={{
                            width: '100%',
                            height: '100%',
                            objectFit: 'cover',
                            borderRadius: 8,
                            border: '1px solid var(--border-strong)',
                          }}
                        />
                        <button
                          type="button"
                          onClick={() =>
                            setFeedbackPhotos((prev) => prev.filter((_, i) => i !== fIdx))
                          }
                          style={{
                            position: 'absolute',
                            top: -5,
                            right: -5,
                            width: 20,
                            height: 20,
                            borderRadius: 99,
                            border: 'none',
                            background: 'var(--danger)',
                            color: '#fff',
                            fontSize: 12,
                            fontWeight: 700,
                            cursor: 'pointer',
                          }}
                        >
                          ×
                        </button>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>

            <ParentGroupSelector
              projectGroups={projectGroups}
              value={parentGroupId}
              onChange={setParentGroupId}
              onGroupsChanged={onGroupsChanged}
              notify={notify}
              label="Thuộc Nhóm Dự Án Cha (Bộ sưu tập / Chiến dịch bán hàng)"
            />
          </StudioCollapsible>
        </div>
      )}

      {/* ==================== BƯỚC 2: KHUNG HÌNH CAPCUT & GIỌNG ĐỌC ==================== */}
      {showStep2 && (
        <div className="step-box fade-slide-in">
          <div className="step-header">
            <span className="step-num">2</span>
            <div>
              <div className="step-title">Dựng hình CapCut, Giọng đọc &amp; Nhạc nền</div>
              <div className="step-desc">
                Chọn kiểu chuyển cảnh mượt, phông nền sản phẩm và giọng tư vấn truyền cảm
              </div>
            </div>
          </div>

          <div className="form-grid" style={{ marginBottom: 16 }}>
            <div>
              <label className="form-label">Hiệu ứng chuyển cảnh mượt</label>
              <select
                className="select"
                value={layoutConfig.transition_style || 'CAPCUT_DISSOLVE'}
                onChange={(e) => updateSalesLayout({ transition_style: e.target.value })}
              >
                <option value="CAPCUT_DISSOLVE">Mờ chồng êm ái chuẩn CapCut (Khuyên dùng)</option>
                <option value="CAPCUT_SMOOTH_SLIDE">Lướt ngang mượt mà (Smooth Slide)</option>
                <option value="CAPCUT_ZOOM_FLOW">Thu phóng mềm mại (Zoom Flow)</option>
                <option value="CAPCUT_FLASH_BEAT">Chớp sáng tinh tế (Soft Flash)</option>
                <option value="STATIC_LOOKBOOK">Đứng tĩnh 100% (Không chuyển động zoom)</option>
              </select>
            </div>

            <div>
              <label className="form-label">Kiểu nền &amp; Tỷ lệ khung xuất</label>
              <div style={{ display: 'flex', gap: 8 }}>
                <select
                  className="select"
                  style={{ flex: 1 }}
                  value={layoutConfig.product_framing || 'BLURRED_STUDIO_CARD'}
                  onChange={(e) => updateSalesLayout({ product_framing: e.target.value })}
                >
                  <option value="BLURRED_STUDIO_CARD">Thẻ nguyên vẹn + Nền mờ</option>
                  <option value="VELVET_DARK_LUXURY">Thẻ nguyên vẹn + Nền Đen Nhung</option>
                  <option value="FULL_BLEED_LUXURY">Phóng vừa tràn khung</option>
                </select>
                <select
                  className="select"
                  style={{ width: 136 }}
                  value={layoutConfig.aspect_ratio || '9:16'}
                  onChange={(e) => updateSalesLayout({ aspect_ratio: e.target.value })}
                >
                  <option value="9:16">9:16 TikTok</option>
                  <option value="4:5">4:5 Facebook</option>
                  <option value="1:1">1:1 Zalo</option>
                </select>
              </div>
            </div>
          </div>

          <div className="form-group">
            <label className="form-label">Xử lý hình ảnh &amp; Hiệu ứng âm thanh Studio</label>
            <div className="toggle-grid">
              <SwitchCard
                icon={Wand2}
                checked={Boolean(layoutConfig.studio_cutout_enabled)}
                onChange={(val) => updateSalesLayout({ studio_cutout_enabled: val })}
              >
                Tự tách nền sang phông Đen Nhung
              </SwitchCard>
              <SwitchCard
                icon={Columns}
                checked={Boolean(layoutConfig.comparison_split_enabled)}
                onChange={(val) => updateSalesLayout({ comparison_split_enabled: val })}
              >
                Chia đôi so sánh A/B (Ảnh 1 &amp; 2)
              </SwitchCard>
              <SwitchCard
                icon={Music2}
                checked={layoutConfig.soundwave_enabled !== false}
                onChange={(val) => updateSalesLayout({ soundwave_enabled: val })}
              >
                Vẽ sóng âm vàng kim theo tiếng đàn
              </SwitchCard>
            </div>
          </div>

          {layoutConfig.comparison_split_enabled && (
            <div className="form-grid" style={{ marginBottom: 16 }}>
              <input
                className="input"
                placeholder="Nhãn cột trái (VD: Bản S2 • Giữ dây kim loại)"
                value={layoutConfig.comparison_label_a || ''}
                onChange={(e) => updateSalesLayout({ comparison_label_a: e.target.value })}
              />
              <input
                className="input"
                placeholder="Nhãn cột phải (VD: Bản S2S • Giữ dây gỗ)"
                value={layoutConfig.comparison_label_b || ''}
                onChange={(e) => updateSalesLayout({ comparison_label_b: e.target.value })}
              />
            </div>
          )}

          <div className="form-grid">
            <InlineVoiceSelector
              voices={voices}
              voiceId={voiceId}
              onChange={setVoiceId}
              voiceSpeed={voiceSpeed}
              onSpeedChange={setVoiceSpeed}
              voicePitch={voicePitch}
              onPitchChange={setVoicePitch}
              defaultCategory="ECOMMERCE_SALES"
              onOpenVoiceLab={onNavigateTab ? () => onNavigateTab('voices') : null}
              label="Giọng đọc tư vấn sản phẩm"
              sampleText="Điểm chạm cảm xúc đầu tiên của cây đàn này nằm ở mặt top gỗ thịt tự nhiên nguyên tấm, cho tiếng đàn ngân dày, ấm và có chiều sâu."
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
              label="Nhạc nền Violin / Acoustic"
            />
          </div>
        </div>
      )}

      {/* ==================== BƯỚC 3: HOÀN TẤT, ẢNH BÌA & XUẤT BẢN ==================== */}
      {showStep3 && (
        <div className="step-box fade-slide-in">
          <div className="step-header">
            <span className="step-num">3</span>
            <div style={{ flex: 1 }}>
              <div className="step-title">Thời lượng, Lời kêu gọi (CTA) &amp; Thành phần hiển thị</div>
              <div className="step-desc">
                Mặc định giữ khung sạch sang trọng; bật thêm nhãn ưu đãi, ảnh bìa hoặc mã QR khi cần
              </div>
            </div>
            <div className="studio-segmented">
              {[1, 2, 3].map((n) => (
                <button
                  key={n}
                  type="button"
                  className={`studio-seg-btn ${variantCount === n ? 'active' : ''}`}
                  onClick={() => setVariantCount(n)}
                >
                  {n} bản A/B
                </button>
              ))}
            </div>
          </div>

          <div className="form-grid">
            <div className="form-group">
              <label className="form-label">
                Thời lượng dự kiến mỗi video: <strong>{durationSec} giây</strong>
              </label>
              <input
                type="range"
                min="25"
                max="110"
                step="5"
                style={{ width: '100%', marginTop: 8 }}
                value={durationSec}
                onChange={(e) => setDurationSec(Number(e.target.value))}
              />
            </div>
            <div className="form-group">
              <label className="form-label">Kiểu hiển thị chữ phụ đề dưới video</label>
              <select
                className="select"
                value={subtitleStyle}
                onChange={(e) => setSubtitleStyle(e.target.value)}
              >
                <option value="CINEMA">Phụ đề câu thanh lịch dưới màn hình (Khuyên dùng)</option>
                <option value="KARAOKE_CAPCUT">Chữ chạy nổi bật từng từ</option>
                <option value="NONE">Tắt hoàn toàn chữ phụ đề (Chỉ nghe giọng đọc)</option>
              </select>
            </div>
          </div>

          <div className="form-group">
            <label className="form-label">Lời nhắn kết cuối video (CTA)</label>
            <input
              className="input"
              value={ctaText}
              onChange={(e) => setCtaText(e.target.value)}
            />
          </div>

          <div className="form-group" style={{ marginBottom: 0 }}>
            <label className="form-label">Thành phần chữ &amp; thẻ hiển thị trên video</label>
            <div className="toggle-grid">
              <SwitchCard
                checked={layoutConfig.show_top_banner !== false}
                onChange={(val) => updateSalesLayout({ show_top_banner: val })}
              >
                Hiện tên sản phẩm đầu video
              </SwitchCard>
              <SwitchCard
                checked={Boolean(layoutConfig.sales_badge_enabled)}
                onChange={(val) => updateSalesLayout({ sales_badge_enabled: val })}
              >
                Hiện nhãn ưu đãi &amp; địa chỉ
              </SwitchCard>
              <SwitchCard
                checked={Boolean(layoutConfig.show_photo_callouts)}
                onChange={(val) => updateSalesLayout({ show_photo_callouts: val })}
              >
                Hiện nhãn ghi chú trên từng ảnh
              </SwitchCard>
              <SwitchCard
                checked={Boolean(layoutConfig.outro_card_enabled)}
                onChange={(val) => updateSalesLayout({ outro_card_enabled: val })}
              >
                Thêm Thẻ kết 2.5s cuối video
              </SwitchCard>
            </div>
          </div>

          {layoutConfig.sales_badge_enabled && (
            <div className="form-grid" style={{ marginTop: 12 }}>
              <input
                className="input"
                placeholder="Nhãn ưu đãi tinh tế (VD: Tặng trọn bộ phụ kiện)"
                value={layoutConfig.sales_price_or_offer || ''}
                onChange={(e) => updateSalesLayout({ sales_price_or_offer: e.target.value })}
              />
              <input
                className="input"
                placeholder="Địa chỉ / liên hệ (VD: Test đàn trực tiếp tại Hà Nội)"
                value={layoutConfig.sales_contact_info || ''}
                onChange={(e) => updateSalesLayout({ sales_contact_info: e.target.value })}
              />
            </div>
          )}

          {layoutConfig.outro_card_enabled && (
            <div className="form-grid" style={{ marginTop: 12 }}>
              <input
                className="input"
                placeholder="Tên cửa hàng ở Thẻ kết 2.5s (VD: Sơn Music — Violin Tuyển Chọn)"
                value={layoutConfig.outro_brand_title || ''}
                onChange={(e) => updateSalesLayout({ outro_brand_title: e.target.value })}
              />
              <input
                className="input"
                placeholder="Địa chỉ & Website Thẻ kết (VD: Showroom Hà Nội • www.sonmusic.vn)"
                value={layoutConfig.outro_contact_line || ''}
                onChange={(e) => updateSalesLayout({ outro_contact_line: e.target.value })}
              />
            </div>
          )}

          <StudioCollapsible
            icon={Camera}
            title="Thiết kế Ảnh Bìa (Cover Thumbnail) & Mã QR góc màn hình"
            subtitle="Tự động xuất kèm ảnh bìa đồng bộ trong gói .ZIP và tạo QR dẫn về trang sản phẩm"
            badge={layoutConfig.qr_code_content ? 'Có QR' : ''}
          >
            <div
              className="form-grid"
              style={{ marginBottom: layoutConfig.cover_style !== 'CLEAN_POSTER' ? 12 : 14 }}
            >
              <div>
                <label className="form-label">Kiểu trình bày Ảnh Bìa</label>
                <select
                  className="select"
                  value={layoutConfig.cover_style || 'CLEAN_POSTER'}
                  onChange={(e) => updateSalesLayout({ cover_style: e.target.value })}
                >
                  <option value="CLEAN_POSTER">Bìa sạch tinh tế (Không chèn chữ lớn)</option>
                  <option value="BOLD_HOOK">Chữ lớn nổi bật dễ đọc trên lưới 3 cột TikTok</option>
                  <option value="LUXURY_MAGAZINE">Khung tạp chí Đen Nhung &amp; Vàng Champagne</option>
                </select>
              </div>
              <div>
                <label className="form-label">Tấm ảnh làm nền Ảnh Bìa</label>
                <select
                  className="select"
                  value={layoutConfig.cover_photo_index || 0}
                  onChange={(e) => updateSalesLayout({ cover_photo_index: Number(e.target.value) })}
                >
                  {uploadedPhotos.filter((p) => !p.isVideo).length === 0 ? (
                    <option value={0}>Mặc định lấy Ảnh mở màn đầu tiên</option>
                  ) : (
                    uploadedPhotos
                      .filter((p) => !p.isVideo)
                      .map((ph, idx) => (
                        <option key={`${ph.local_path}_cov_${idx}`} value={idx}>
                          Ảnh {idx + 1} — {ph.original_name}
                        </option>
                      ))
                  )}
                </select>
              </div>
            </div>

            {layoutConfig.cover_style !== 'CLEAN_POSTER' && (
              <div className="form-grid" style={{ marginBottom: 14 }}>
                <input
                  className="input"
                  placeholder="Tiêu đề lớn trên Ảnh Bìa (VD: Test Âm Violin S2S Gỗ Thịt)"
                  value={layoutConfig.cover_headline || ''}
                  onChange={(e) => updateSalesLayout({ cover_headline: e.target.value })}
                />
                <input
                  className="input"
                  placeholder="Nhãn điểm nhấn trên bìa (VD: Nghe Thử Âm Mộc)"
                  value={layoutConfig.cover_badge_text || ''}
                  onChange={(e) => updateSalesLayout({ cover_badge_text: e.target.value })}
                />
              </div>
            )}

            <div className="form-grid">
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <QrCode size={17} style={{ color: 'var(--brand-text)', flexShrink: 0 }} />
                <input
                  className="input"
                  placeholder="Dán link tạo Mã QR góc màn hình (Để trống = Không hiện QR)"
                  value={layoutConfig.qr_code_content || ''}
                  onChange={(e) => updateSalesLayout({ qr_code_content: e.target.value })}
                />
                {layoutConfig.qr_code_content && (
                  <button
                    type="button"
                    className="btn btn-secondary btn-sm"
                    onClick={() => updateSalesLayout({ qr_code_content: '' })}
                  >
                    <X size={13} />
                  </button>
                )}
              </div>
              <input
                className="input"
                placeholder="Chú thích dưới Mã QR (VD: Quét xem chi tiết)"
                value={layoutConfig.qr_code_label || ''}
                disabled={!layoutConfig.qr_code_content}
                onChange={(e) => updateSalesLayout({ qr_code_label: e.target.value })}
              />
            </div>
          </StudioCollapsible>
        </div>
      )}

      <StudioLoadingBanner
        loading={submitting}
        title="Đang khởi tạo dự án Video Giới Thiệu Sản Phẩm..."
        subtitle="Hệ thống đang khớp từng tấm ảnh/clip sản phẩm với lời bình & chuẩn bị dựng khung CapCut"
        steps={[
          'Kiểm tra bộ ảnh sản phẩm & kịch bản lời bình',
          'Đưa vào hàng đợi kết xuất GPU NVENC',
        ]}
        stepIntervalMs={1800}
      />

      <StudioStepFooter
        activeStep={activeStep}
        totalSteps={3}
        showAllSteps={showAllSteps}
        onStepChange={setActiveStep}
        nextStepLabel={
          activeStep === 1 ? 'Tiếp tục: Khung hình & Giọng đọc' : 'Tiếp tục: Ảnh bìa & Xuất'
        }
        hintText="Tự động lưu nháp • Dán ảnh Ctrl + V • Xuất ngay Ctrl + Enter"
        secondaryAction={{
          label: 'Duyệt kịch bản trước',
          icon: submitting ? <Loader2 size={15} className="spin" /> : <Edit3 size={15} />,
          disabled: submitting || uploadingPhotos || uploadingDemo || scrapingUrl,
          onClick: () => handleStart(false),
        }}
        primaryAction={{
          label: submitting
            ? 'Đang khởi tạo...'
            : `Tạo ${variantCount > 1 ? `${variantCount} video bán hàng` : 'video bán hàng'} ngay`,
          icon: submitting ? <Loader2 size={16} className="spin" /> : <Play size={16} />,
          disabled: submitting || uploadingPhotos || uploadingDemo || scrapingUrl,
          onClick: () => handleStart(true),
        }}
      />
    </div>
  );
}
