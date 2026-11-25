import React, { useEffect, useState } from 'react';
import {
  Clapperboard,
  Cpu,
  FileText,
  Film,
  FolderKanban,
  Mic,
  Pause,
  Play,
  ShoppingBag,
  SlidersHorizontal,
  Smartphone,
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
  const [activeTab, setActiveTab] = useState('movie');
  const [systemStatus, setSystemStatus] = useState(null);
  const [voices, setVoices] = useState([]);
  const [bgmPresets, setBgmPresets] = useState([]);
  const [projects, setProjects] = useState([]);
  const [activeProjectId, setActiveProjectId] = useState('');
  const [layoutConfig, setLayoutConfig] = useState(DEFAULT_LAYOUT_CONFIG);
  const [previewFrameUrl, setPreviewFrameUrl] = useState('');
  const [showSettings, setShowSettings] = useState(false);
  const [showMobilePreviewDrawer, setShowMobilePreviewDrawer] = useState(false);
  const [toastMsg, setToastMsg] = useState('');

  const notify = (msg) => {
    setToastMsg(msg);
    setTimeout(() => setToastMsg(''), 3400);
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
  const runningProjects = projects.filter((p) => ACTIVE_OR_PAUSED.includes(p.state));
  const pinnedJob = runningProjects[0] || null;
  const queuedCount = projects.filter((p) => p.state === 'QUEUED').length;

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
    { id: 'movie', label: 'Cắt & Dịch Video', shortLabel: 'Cắt Video', icon: Film },
    { id: 'product', label: 'Video Bán Hàng', shortLabel: 'Bán Hàng', icon: ShoppingBag },
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
      {/* TOP COMPACT HEADER */}
      <header className="studio-header">
        <div className="brand-wrap">
          <div className="brand-mark">
            <Clapperboard size={18} strokeWidth={2} />
          </div>
          <div style={{ minWidth: 0 }}>
            <div className="brand-title">ShortVideo Studio</div>
            <div className="brand-sub">
              Biên tập video ngắn dọc 9:16 cho cửa hàng và nhà sáng tạo nội dung
            </div>
          </div>
        </div>

        <div className="header-actions">
          {systemStatus?.lan_urls?.[0] && (
            <button
              type="button"
              className="badge badge-info hide-on-mobile"
              style={{ cursor: 'pointer' }}
              title="Bấm để sao chép liên kết mở trên điện thoại hoặc máy tính cùng mạng Wi-Fi"
              onClick={() => {
                copyTextSafe(systemStatus.lan_urls[0]);
                notify(`Đã sao chép địa chỉ mạng nội bộ: ${systemStatus.lan_urls[0]}`);
              }}
            >
              <Wifi size={13} /> {systemStatus.lan_urls[0].replace('http://', '')}
            </button>
          )}

          <span className={`badge ${primaryGpu ? 'badge-ok' : 'badge-warn'} hide-on-mobile`}>
            <Cpu size={13} />{' '}
            {primaryGpu
              ? `${primaryGpu.name} (${Math.round(primaryGpu.vram_total_mb / 1024)}GB)`
              : 'Chế độ CPU'}
          </span>

          <button className="btn btn-secondary btn-sm" onClick={() => setShowSettings(true)}>
            <SlidersHorizontal size={14} /> <span className="hide-on-mobile">Kết nối API</span>
          </button>
        </div>
      </header>

      {/* MAIN 3-COLUMN STUDIO LAYOUT */}
      <div className="studio-layout-3col">
        {/* LEFT SIDEBAR RAIL */}
        <aside className="studio-sidebar">
          <nav className="nav-rail">
            <div className="nav-section-label">Công cụ tạo video</div>
            {navItems.slice(0, 3).map((item) => {
              const Icon = item.icon;
              return (
                <button
                  key={item.id}
                  className={`rail-btn ${activeTab === item.id ? 'active' : ''}`}
                  onClick={() => setActiveTab(item.id)}
                >
                  <span className="rail-btn-left">
                    <Icon size={17} strokeWidth={1.8} />
                    <span>{item.label}</span>
                  </span>
                </button>
              );
            })}

            <div className="nav-section-label" style={{ marginTop: 6 }}>
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
                    <Icon size={17} strokeWidth={1.8} />
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
                <span style={{ fontSize: 11.5, fontWeight: 600, color: '#38bdf8' }}>
                  {pinnedJob.state === 'PAUSED' ? 'Đang tạm dừng' : 'Đang xử lý video'}
                </span>
                {queuedCount > 0 && (
                  <span className="badge badge-warn" style={{ fontSize: 10.5, padding: '1px 6px' }}>
                    +{queuedCount} chờ
                  </span>
                )}
              </div>

              <div
                style={{
                  fontSize: 13,
                  fontWeight: 600,
                  whiteSpace: 'nowrap',
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                  marginBottom: 3,
                }}
                title={pinnedJob.name}
              >
                {pinnedJob.name}
              </div>

              <div style={{ fontSize: 11.5, color: '#9ca3af' }}>
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
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  fontSize: 11.5,
                  color: '#d1d5db',
                  marginBottom: 8,
                }}
              >
                <span>{pinnedJob.live_progress?.percent || 0}%</span>
                <span style={{ color: '#34d399', fontWeight: 500 }}>
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
                  Xem
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
              onPreviewFrameReady={setPreviewFrameUrl}
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
              onPreviewFrameReady={setPreviewFrameUrl}
              onProjectStarted={handleProjectStarted}
              notify={notify}
            />
          )}

          {activeTab === 'topic' && (
            <TopicStudioForm
              voices={voices}
              bgmPresets={bgmPresets}
              layoutConfig={layoutConfig}
              onProjectStarted={handleProjectStarted}
              notify={notify}
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
              onPreviewFrameReady={setPreviewFrameUrl}
              notify={notify}
            />
          )}
        </main>

        {/* RIGHT DESKTOP DOCK */}
        <div className="right-dock-desktop">
          <Canvas916Designer
            layoutConfig={layoutConfig}
            setLayoutConfig={setLayoutConfig}
            previewFrameUrl={previewFrameUrl}
            systemStatus={systemStatus}
            onSystemStatusUpdated={setSystemStatus}
            activeTab={activeTab}
            notify={notify}
          />
        </div>
      </div>

      {/* FLOATING 9:16 PREVIEW TRIGGER FOR LAPTOP / TABLET / MOBILE */}
      <button
        type="button"
        className="btn btn-primary floating-preview-fab"
        onClick={() => setShowMobilePreviewDrawer(true)}
      >
        <Smartphone size={16} /> Khung hình & Phần cứng
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
                marginBottom: 10,
              }}
            >
              <strong style={{ fontSize: 14 }}>Xem trước khung hình & Thiết bị</strong>
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
              previewFrameUrl={previewFrameUrl}
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
              <Icon size={19} strokeWidth={1.8} />
              <span>{item.shortLabel}</span>
            </button>
          );
        })}
      </nav>

      {showSettings && (
        <SettingsModal
          systemStatus={systemStatus}
          onClose={() => setShowSettings(false)}
          onUpdated={setSystemStatus}
          notify={notify}
        />
      )}

      {toastMsg && <div className="toast">{toastMsg}</div>}
    </div>
  );
}
