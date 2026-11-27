import React, { useEffect, useState } from 'react';
import {
  Clapperboard,
  Copy,
  Cpu,
  FileText,
  Film,
  FolderKanban,
  Mic,
  Moon,
  Pause,
  Play,
  QrCode,
  ShoppingBag,
  SlidersHorizontal,
  Smartphone,
  Sun,
  Wifi,
  X,
} from 'lucide-react';
import { studioApi } from './modules/m00_core_contracts/apiClient';
import {
  copyTextSafe,
  DEFAULT_LAYOUT_CONFIG,
  formatSecondsVi,
  STAGE_LABELS,
} from './modules/m00_core_contracts/constants';
import MovieStudioForm from './modules/m01_m04_movie_studio/MovieStudioForm';
import TopicStudioForm from './modules/m03_topic_studio/TopicStudioForm';
import VoiceCloneLab from './modules/m05_voice_lab/VoiceCloneLab';
import Canvas916Designer from './modules/m06_canvas_916/Canvas916Designer';
import ProjectWorkspaceView from './modules/m07_review_and_seo/ProjectWorkspaceView';
import SettingsModal from './modules/m07_review_and_seo/SettingsModal';
import ProductStudioForm from './modules/m08_product_studio/ProductStudioForm';

const ACTIVE_OR_PAUSED = [
  'QUEUED',
  'INGESTING',
  'TRANSCRIBING_GPU',
  'AI_ANALYZING',
  'GENERATING_ASSETS',
  'RENDERING_NVENC',
  'PACKAGING_SEO',
  'PAUSED',
];

export default function App() {
  const [activeTab, setActiveTab] = useState('product');
  const [theme, setTheme] = useState(() => localStorage.getItem('chaos_theme') || 'dark');
  const [systemStatus, setSystemStatus] = useState(null);
  const [voices, setVoices] = useState([]);
  const [bgmPresets, setBgmPresets] = useState([]);
  const [projects, setProjects] = useState([]);
  const [activeProjectId, setActiveProjectId] = useState('');
  const [layoutConfig, setLayoutConfig] = useState(DEFAULT_LAYOUT_CONFIG);
  const [previewFramesByTab, setPreviewFramesByTab] = useState({
    movie: '',
    product: '',
    topic: '',
    workspace: '',
  });
  const [showSettings, setShowSettings] = useState(false);
  const [showLanQrModal, setShowLanQrModal] = useState(false);
  const [selectedLanUrl, setSelectedLanUrl] = useState('');
  const [showMobilePreviewDrawer, setShowMobilePreviewDrawer] = useState(false);
  const [toastMsg, setToastMsg] = useState('');

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('chaos_theme', theme);
  }, [theme]);

  const notify = (msg) => {
    setToastMsg(msg);
    setTimeout(() => setToastMsg(''), 3400);
  };

  const setTabPreviewFrame = (tabKey, url) => {
    setPreviewFramesByTab((prev) => ({ ...prev, [tabKey]: url || '' }));
  };

  const refreshAllData = async () => {
    try {
      const [st, vList, pList, bList] = await Promise.all([
        studioApi.getSystemStatus(),
        studioApi.listVoices(),
        studioApi.listProjects(),
        studioApi.listBgmPresets(),
      ]);
      setSystemStatus(st);
      if (st?.lan_urls?.[0] && !selectedLanUrl) {
        setSelectedLanUrl(st.lan_urls[0]);
      }
      setVoices(vList);
      setProjects(pList);
      setBgmPresets(bList);
      if (!activeProjectId && pList.length > 0) {
        setActiveProjectId(pList[0].id);
      }
    } catch {
      // backend starting
    }
  };

  useEffect(() => {
    refreshAllData();
    const timer = setInterval(async () => {
      try {
        const [st, pList] = await Promise.all([
          studioApi.getSystemStatus(),
          studioApi.listProjects(),
        ]);
        setSystemStatus(st);
        setProjects(pList);
      } catch {
        // ignore
      }
    }, 3500);
    return () => clearInterval(timer);
  }, []);

  const handleProjectStarted = async (projectId, initialState) => {
    setActiveProjectId(projectId);
    setActiveTab('workspace');
    await refreshAllData();
    if (initialState === 'QUEUED') {
      notify('Đã đưa dự án vào hàng đợi tự động.');
    } else {
      notify('Đã bắt đầu xử lý video.');
    }
  };

  const primaryGpu = systemStatus?.gpus?.[0];
  const lanUrls = systemStatus?.lan_urls || [];
  const activeLanUrl = selectedLanUrl || lanUrls[0] || window.location.origin;
  const runningProjects = projects.filter((p) => ACTIVE_OR_PAUSED.includes(p.state));
  const pinnedJob = runningProjects[0] || null;
  const queuedCount = projects.filter((p) => p.state === 'QUEUED').length;
  const currentPreviewFrameUrl = previewFramesByTab[activeTab] || '';

  const handleQuickPauseResume = async (job) => {
    try {
      if (job.state === 'PAUSED') {
        await studioApi.resumeProject(job.id);
        notify('Đã tiếp tục dự án.');
      } else {
        await studioApi.pauseProject(job.id);
        notify('Đã tạm dừng dự án.');
      }
      refreshAllData();
    } catch (err) {
      notify(`Lỗi điều khiển: ${err.message}`);
    }
  };

  const navItems = [
    { id: 'product', label: 'Video Bán Hàng', shortLabel: 'Bán Hàng', icon: ShoppingBag },
    { id: 'movie', label: 'Cắt & Dịch Video', shortLabel: 'Cắt Video', icon: Film },
    { id: 'topic', label: 'Tạo Từ Chủ Đề', shortLabel: 'Chủ Đề', icon: FileText },
    {
      id: 'workspace',
      label: 'Danh Sách Dự Án',
      shortLabel: 'Dự Án',
      icon: FolderKanban,
      count: projects.length,
    },
    {
      id: 'voices',
      label: 'Giọng Đọc & Thu Mẫu',
      shortLabel: 'Giọng Đọc',
      icon: Mic,
      count: voices.length,
    },
  ];

  return (
    <div>
      {/* TOP HIGH-CLARITY STUDIO HEADER */}
      <header className="studio-header">
        <div className="brand-wrap">
          <div className="brand-mark">
            <Clapperboard size={20} strokeWidth={2.1} />
          </div>
          <div style={{ minWidth: 0 }}>
            <div className="brand-title">
              ChaosShortVideo
              <span className="brand-version-pill">Studio v3.1</span>
            </div>
            <div className="brand-sub">
              Hệ thống dựng video bán hàng, cắt dịch phim & sáng tạo nội dung ngắn đa nền tảng
            </div>
          </div>
        </div>

        <div className="header-actions">
          {lanUrls.length > 0 && (
            <button
              type="button"
              className="badge badge-info hide-on-mobile"
              style={{ cursor: 'pointer' }}
              title="Bấm để mở Mã QR quét bằng điện thoại cùng mạng Wi-Fi"
              onClick={() => setShowLanQrModal(true)}
            >
              <QrCode size={13} /> Điện thoại LAN: {lanUrls[0].replace('http://', '')}
            </button>
          )}

          <span className={`badge ${primaryGpu ? 'badge-ok' : 'badge-warn'} hide-on-mobile`}>
            <Cpu size={13} />{' '}
            {primaryGpu
              ? `${primaryGpu.name} (${Math.round(primaryGpu.vram_total_mb / 1024)}GB${
                  systemStatus?.nvenc_available ? ' • NVENC' : ''
                })`
              : 'Chế độ CPU'}
          </span>

          <button
            type="button"
            className="btn btn-secondary btn-sm"
            onClick={() => setTheme((prev) => (prev === 'dark' ? 'light' : 'dark'))}
            title="Chuyển đổi giao diện Tối / Sáng dễ nhìn"
          >
            {theme === 'dark' ? (
              <>
                <Sun size={14} /> <span className="hide-on-mobile">Nền sáng</span>
              </>
            ) : (
              <>
                <Moon size={14} /> <span className="hide-on-mobile">Nền tối</span>
              </>
            )}
          </button>

          <button className="btn btn-secondary btn-sm" onClick={() => setShowSettings(true)}>
            <SlidersHorizontal size={14} />{' '}
            <span className="hide-on-mobile">API & Sao lưu</span>
          </button>
        </div>
      </header>

      {/* MAIN 3-COLUMN STABLE STUDIO LAYOUT */}
      <div className="studio-layout-3col">
        {/* LEFT SIDEBAR RAIL */}
        <aside className="studio-sidebar">
          <nav className="nav-rail">
            <div className="nav-section-label">Công cụ sản xuất</div>
            {navItems.slice(0, 3).map((item) => {
              const Icon = item.icon;
              return (
                <button
                  key={item.id}
                  className={`rail-btn ${activeTab === item.id ? 'active' : ''}`}
                  onClick={() => setActiveTab(item.id)}
                >
                  <span className="rail-btn-left">
                    <Icon size={18} strokeWidth={1.9} />
                    <span>{item.label}</span>
                  </span>
                </button>
              );
            })}

            <div className="nav-section-label" style={{ marginTop: 8 }}>
              Quản lý & Thư viện
            </div>
            {navItems.slice(3).map((item) => {
              const Icon = item.icon;
              return (
                <button
                  key={item.id}
                  className={`rail-btn ${activeTab === item.id ? 'active' : ''}`}
                  onClick={() => {
                    if (item.id === 'workspace') refreshAllData();
                    setActiveTab(item.id);
                  }}
                >
                  <span className="rail-btn-left">
                    <Icon size={18} strokeWidth={1.9} />
                    <span>{item.label}</span>
                  </span>
                  {item.count !== undefined && <span className="rail-count">{item.count}</span>}
                </button>
              );
            })}
          </nav>

          {/* PINNED LIVE PROGRESS WIDGET */}
          {pinnedJob && (
            <div className="pinned-job-box">
              <div
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  marginBottom: 4,
                }}
              >
                <span style={{ fontSize: 12, fontWeight: 700, color: 'var(--brand-text)' }}>
                  {pinnedJob.state === 'PAUSED' ? 'Đang tạm dừng' : 'Đang xử lý video'}
                </span>
                {queuedCount > 0 && (
                  <span className="badge badge-warn" style={{ fontSize: 10.5, padding: '1px 7px' }}>
                    +{queuedCount} chờ
                  </span>
                )}
              </div>

              <div
                style={{
                  fontSize: 13.5,
                  fontWeight: 700,
                  whiteSpace: 'nowrap',
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                  marginBottom: 3,
                }}
                title={pinnedJob.name}
              >
                {pinnedJob.name}
              </div>

              <div className="text-sub" style={{ fontSize: 12 }}>
                {pinnedJob.live_progress?.step_label ||
                  STAGE_LABELS[pinnedJob.state] ||
                  pinnedJob.state}
              </div>

              <div className="progress-track">
                <div
                  className={`progress-fill ${pinnedJob.state === 'PAUSED' ? 'paused' : ''}`}
                  style={{
                    width: `${Math.max(4, Math.min(100, pinnedJob.live_progress?.percent || 4))}%`,
                  }}
                />
              </div>

              <div
                className="text-sub"
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  fontSize: 12,
                  marginBottom: 9,
                }}
              >
                <strong>{pinnedJob.live_progress?.percent || 0}%</strong>
                <span style={{ color: 'var(--success-text)', fontWeight: 600 }}>
                  {pinnedJob.live_progress?.eta_sec !== null &&
                  pinnedJob.live_progress?.eta_sec !== undefined
                    ? `Còn ~${formatSecondsVi(pinnedJob.live_progress.eta_sec)}`
                    : `Đã chạy ${formatSecondsVi(pinnedJob.live_progress?.elapsed_sec || 0)}`}
                </span>
              </div>

              <div style={{ display: 'flex', gap: 6 }}>
                <button
                  type="button"
                  className="btn btn-secondary btn-sm"
                  style={{ flex: 1 }}
                  onClick={() => handleQuickPauseResume(pinnedJob)}
                >
                  {pinnedJob.state === 'PAUSED' ? (
                    <>
                      <Play size={13} /> Tiếp tục
                    </>
                  ) : (
                    <>
                      <Pause size={13} /> Tạm dừng
                    </>
                  )}
                </button>
                <button
                  type="button"
                  className="btn btn-primary btn-sm"
                  onClick={() => {
                    setActiveProjectId(pinnedJob.id);
                    setActiveTab('workspace');
                  }}
                >
                  Chi tiết
                </button>
              </div>
            </div>
          )}
        </aside>

        {/* CENTER STAGE */}
        <main style={{ minWidth: 0 }}>
          {activeTab === 'movie' && (
            <MovieStudioForm
              voices={voices}
              bgmPresets={bgmPresets}
              layoutConfig={layoutConfig}
              onPreviewFrameReady={(u) => setTabPreviewFrame('movie', u)}
              onProjectStarted={handleProjectStarted}
              notify={notify}
            />
          )}

          {activeTab === 'product' && (
            <ProductStudioForm
              voices={voices}
              bgmPresets={bgmPresets}
              layoutConfig={layoutConfig}
              setLayoutConfig={setLayoutConfig}
              onPreviewFrameReady={(u) => setTabPreviewFrame('product', u)}
              onProjectStarted={handleProjectStarted}
              notify={notify}
              apiKeyConfigured={Boolean(systemStatus?.keys_configured?.gemini)}
              onOpenApiSettings={() => setShowSettings(true)}
            />
          )}

          {activeTab === 'topic' && (
            <TopicStudioForm
              voices={voices}
              bgmPresets={bgmPresets}
              layoutConfig={layoutConfig}
              onProjectStarted={handleProjectStarted}
              notify={notify}
              apiKeyConfigured={Boolean(systemStatus?.keys_configured?.gemini)}
              onOpenApiSettings={() => setShowSettings(true)}
            />
          )}

          {activeTab === 'voices' && (
            <VoiceCloneLab
              voices={voices}
              onVoicesChanged={refreshAllData}
              notify={notify}
            />
          )}

          {activeTab === 'workspace' && (
            <ProjectWorkspaceView
              activeProjectId={activeProjectId}
              projects={projects}
              onSelectProject={setActiveProjectId}
              onProjectsRefresh={refreshAllData}
              voices={voices}
              bgmPresets={bgmPresets}
              layoutConfig={layoutConfig}
              setLayoutConfig={setLayoutConfig}
              onPreviewFrameReady={(u) => setTabPreviewFrame('workspace', u)}
              notify={notify}
            />
          )}
        </main>

        {/* RIGHT DESKTOP DOCK */}
        <div className="right-dock-desktop">
          <Canvas916Designer
            layoutConfig={layoutConfig}
            setLayoutConfig={setLayoutConfig}
            previewFrameUrl={currentPreviewFrameUrl}
            systemStatus={systemStatus}
            onSystemStatusUpdated={setSystemStatus}
            activeTab={activeTab}
            notify={notify}
          />
        </div>
      </div>

      {/* FLOATING PREVIEW TRIGGER FOR LAPTOP / TABLET / MOBILE */}
      <button
        type="button"
        className="btn btn-primary floating-preview-fab"
        onClick={() => setShowMobilePreviewDrawer(true)}
      >
        <Smartphone size={16} /> Xem trước & Phần cứng
      </button>

      {/* SLIDE-OVER DRAWER FOR SMALL SCREENS */}
      {showMobilePreviewDrawer && (
        <div className="drawer-backdrop" onClick={() => setShowMobilePreviewDrawer(false)}>
          <div className="drawer-sheet" onClick={(e) => e.stopPropagation()}>
            <div
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                marginBottom: 12,
              }}
            >
              <strong style={{ fontSize: 15 }}>Xem trước khung hình & Thiết bị</strong>
              <button
                type="button"
                className="btn btn-secondary btn-sm"
                onClick={() => setShowMobilePreviewDrawer(false)}
              >
                <X size={15} /> Đóng
              </button>
            </div>
            <Canvas916Designer
              layoutConfig={layoutConfig}
              setLayoutConfig={setLayoutConfig}
              previewFrameUrl={currentPreviewFrameUrl}
              systemStatus={systemStatus}
              onSystemStatusUpdated={setSystemStatus}
              activeTab={activeTab}
              notify={notify}
            />
          </div>
        </div>
      )}

      {/* MOBILE BOTTOM APP TAB BAR */}
      <nav className="mobile-bottom-nav">
        {navItems.map((item) => {
          const Icon = item.icon;
          return (
            <button
              key={item.id}
              type="button"
              className={`mobile-nav-item ${activeTab === item.id ? 'active' : ''}`}
              onClick={() => {
                if (item.id === 'workspace') refreshAllData();
                setActiveTab(item.id);
              }}
            >
              <Icon size={19} strokeWidth={1.9} />
              <span>{item.shortLabel}</span>
            </button>
          );
        })}
      </nav>

      {/* LAN WI-FI MOBILE QR MODAL (ITEM 7) */}
      {showLanQrModal && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            background: 'rgba(2, 6, 23, 0.76)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 120,
            padding: 16,
          }}
          onClick={() => setShowLanQrModal(false)}
        >
          <div
            className="card"
            onClick={(e) => e.stopPropagation()}
            style={{ width: '100%', maxWidth: 460, marginBottom: 0, textAlign: 'center' }}
          >
            <div className="page-header" style={{ marginBottom: 14, textAlign: 'left' }}>
              <div>
                <div className="page-title">
                  <Wifi size={19} /> Mở ChaosShortVideo trên Điện thoại
                </div>
                <div className="page-subtitle">
                  Tải thẳng ảnh & video gốc vừa chụp từ iPhone / Android vào máy chủ qua Wi-Fi
                </div>
              </div>
              <button
                type="button"
                className="btn btn-secondary btn-sm"
                onClick={() => setShowLanQrModal(false)}
              >
                <X size={15} /> Đóng
              </button>
            </div>

            {lanUrls.length > 1 && (
              <div className="form-group" style={{ textAlign: 'left' }}>
                <label className="form-label">Chọn địa chỉ mạng nội bộ:</label>
                <select
                  className="select"
                  value={activeLanUrl}
                  onChange={(e) => setSelectedLanUrl(e.target.value)}
                >
                  {lanUrls.map((u) => (
                    <option key={u} value={u}>
                      {u}
                    </option>
                  ))}
                </select>
              </div>
            )}

            <div
              style={{
                display: 'inline-block',
                padding: 14,
                borderRadius: 16,
                background: '#ffffff',
                border: '2px solid var(--brand)',
                marginBottom: 12,
                boxShadow: '0 8px 24px rgba(0, 0, 0, 0.25)',
              }}
            >
              <img
                src={studioApi.getLanQrImageUrl(activeLanUrl)}
                alt="LAN Wi-Fi QR Code"
                style={{ width: 220, height: 220, display: 'block' }}
              />
            </div>

            <div
              className="step-box"
              style={{ textAlign: 'left', padding: '12px 14px', marginBottom: 12 }}
            >
              <div style={{ fontSize: 13, fontWeight: 700, marginBottom: 4 }}>
                Hướng dẫn kết nối nhanh (Không cần gửi vòng qua Zalo):
              </div>
              <div className="text-sub" style={{ fontSize: 12.6, lineHeight: 1.5 }}>
                1. Đảm bảo điện thoại bắt <strong>cùng mạng Wi-Fi</strong> với máy tính này.
                <br />
                2. Mở <strong>Camera điện thoại</strong> (hoặc trình quét mã QR) hướng vào hình trên để mở thẳng giao diện Studio trên điện thoại.
              </div>
            </div>

            <div style={{ display: 'flex', gap: 8 }}>
              <input
                className="input"
                readOnly
                value={activeLanUrl}
                style={{ flex: 1, fontWeight: 700, textAlign: 'center' }}
              />
              <button
                type="button"
                className="btn btn-primary"
                onClick={() => {
                  copyTextSafe(activeLanUrl);
                  notify(`Đã sao chép địa chỉ LAN: ${activeLanUrl}`);
                }}
              >
                <Copy size={15} /> Sao chép
              </button>
            </div>
          </div>
        </div>
      )}

      {showSettings && (
        <SettingsModal
          systemStatus={systemStatus}
          onClose={() => setShowSettings(false)}
          onUpdated={setSystemStatus}
          onBackupRestored={refreshAllData}
          notify={notify}
        />
      )}

      {toastMsg && <div className="toast">{toastMsg}</div>}
    </div>
  );
}
