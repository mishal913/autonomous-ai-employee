import {
  useEffect,
  useMemo,
  useState,
  type ElementType,
  type FormEvent,
  type ReactNode,
} from "react";

import {
  Activity,
  AlertTriangle,
  Bot,
  BrainCircuit,
  CheckCircle2,
  ChevronDown,
  Clock3,
  Database,
  Edit3,
  FileText,
  LayoutDashboard,
  RefreshCw,
  Send,
  ShieldAlert,
  ShieldCheck,
  Sparkles,
  Trash2,
  Upload,
  Wifi,
  WifiOff,
  X,
  XCircle,
} from "lucide-react";

import { api } from "./api";


type View =
  | "dashboard"
  | "new-task"
  | "knowledge"
  | "observability";

type StepStatus =
  | "pending"
  | "running"
  | "completed"
  | "failed"
  | "skipped";

interface OperationStats {
  runs: number;
  completed: number;
  failures: number;
  average_duration_ms: number | null;
  minimum_duration_ms: number | null;
  maximum_duration_ms: number | null;
}

interface ObservabilitySummary {
  log_file: string;
  total_events: number;
  tasks_observed: number;
  task_ids: number[];
  event_counts: Record<string, number>;
  operations: Record<string, OperationStats>;
}

interface AgentEvent {
  timestamp?: string;
  event_type?: string;
  data?: Record<string, unknown> | null;
}


interface SecurityMetrics {
  eventsAnalyzed: number;

  webSourcesInspected: number;
  highRiskWebSources: number;
  webWarnings: number;
  webHighConfidenceDetections: number;

  ragChunksInspected: number;
  highRiskRagChunks: number;
  ragWarnings: number;
  ragHighConfidenceDetections: number;

  emailActionsValidated: number;
  emailActionsBlocked: number;

  highConfidenceEvents: number;
  warningEvents: number;

  highCategories: string[];
  warningCategories: string[];
}

interface KnowledgeDocument {
  id?: number;
  filename?: string;
  document_type?: string;
  source_path?: string;
  created_at?: string;
  chunk_count?: number;
}

interface LiveStep {
  step: number;
  key: string;
  label: string;
  status: StepStatus;
  started_at?: string | null;
  completed_at?: string | null;
  duration_ms?: number | null;
  details?: Record<string, unknown>;
}

interface WebSource {
  title?: string;
  url?: string;
}

interface RagSource {
  document_id?: number;
  filename?: string;
  chunk_index?: number;
  similarity?: number;
}

interface TaskTrace {
  found?: boolean;
  task_id?: number;
  thread_id?: string;
  company_name?: string;
  status?: string;
  current_step?: number;
  current_node?: string | null;
  steps?: LiveStep[];
  memory?: {
    existing_memory_found?: boolean | null;
  };
  web_research?: {
    query?: string | null;
    results_count?: number | null;
    sources?: WebSource[];
  };
  rag_sources?: RagSource[];
  score_breakdown?: {
    industry_fit?: number | null;
    company_size_fit?: number | null;
    ai_need?: number | null;
    growth_signal?: number | null;
    contact_potential?: number | null;
  };
  lead_score?: number | null;
  rating?: string | null;
  recommended_services?: string[];
  draft_id?: number | null;
  approval_status?: string | null;
  email_send_status?: string | null;
  errors?: Array<Record<string, unknown>>;
  events?: AgentEvent[];
}

interface EmailDraft {
  success?: boolean;
  found?: boolean;
  draft_id?: number;
  company_name?: string;
  recipient_email?: string;
  subject?: string;
  body?: string;
  status?: string;
  gmail_message_id?: string | null;
  gmail_thread_id?: string | null;
  sent_at?: string | null;
  send_error?: string | null;
}

interface LiveWorkflowResponse {
  success?: boolean;
  task_id?: number;
  thread_id?: string;
  status?: string;
  background_running?: boolean;
  task?: Record<string, unknown>;
  trace?: TaskTrace;
  workflow?: Record<string, unknown>;
  email_draft?: EmailDraft | null;
}

interface NavigationItem {
  key: View;
  label: string;
  icon: ElementType;
}


const navigation: NavigationItem[] = [
  { key: "dashboard", label: "Dashboard", icon: LayoutDashboard },
  { key: "new-task", label: "New Agent Task", icon: Bot },
  { key: "knowledge", label: "Knowledge Base", icon: Database },
  { key: "observability", label: "Observability", icon: Activity },
];


function formatDuration(value?: number | null) {
  if (value === null || value === undefined) return "—";
  if (value < 1000) return `${value.toFixed(0)} ms`;
  return `${(value / 1000).toFixed(2)} s`;
}

function formatDate(value?: string | null) {
  if (!value) return "—";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toLocaleString();
}

function formatSimilarity(value?: number | null) {
  if (value === null || value === undefined) return "—";
  return `${(value * 100).toFixed(1)}%`;
}

function prettyName(value: unknown) {
  const text =
    typeof value === "string" && value.trim()
      ? value
      : "unknown_event";

  return text
    .replace(/^workflow_/, "")
    .replace(/^rag_/, "RAG ")
    .replaceAll("_", " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}


function asNumber(value: unknown) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : 0;
}


function asStringArray(value: unknown) {
  if (!Array.isArray(value)) return [];

  return value
    .map((item) => String(item))
    .filter(Boolean);
}


function buildSecurityMetrics(events: AgentEvent[]): SecurityMetrics {
  const metrics: SecurityMetrics = {
    eventsAnalyzed: events.length,

    webSourcesInspected: 0,
    highRiskWebSources: 0,
    webWarnings: 0,
    webHighConfidenceDetections: 0,

    ragChunksInspected: 0,
    highRiskRagChunks: 0,
    ragWarnings: 0,
    ragHighConfidenceDetections: 0,

    emailActionsValidated: 0,
    emailActionsBlocked: 0,

    highConfidenceEvents: 0,
    warningEvents: 0,

    highCategories: [],
    warningCategories: [],
  };

  const highCategories = new Set<string>();
  const warningCategories = new Set<string>();

  for (const event of events) {
    if (!event || typeof event !== "object") continue;

    const eventType =
      typeof event.event_type === "string"
        ? event.event_type
        : "unknown_event";

    const data =
      event.data && typeof event.data === "object"
        ? event.data
        : {};

    if (eventType === "security_web_evidence_scanned") {
      metrics.webSourcesInspected += asNumber(data.sources_inspected);
      metrics.highRiskWebSources += asNumber(
        data.high_risk_sources ?? data.suspicious_sources
      );
      metrics.webWarnings += asNumber(data.warning_sources);
      metrics.webHighConfidenceDetections += asNumber(
        data.high_confidence_detections
      );

      asStringArray(data.high_categories).forEach((value) =>
        highCategories.add(value)
      );

      asStringArray(data.warning_categories).forEach((value) =>
        warningCategories.add(value)
      );
    }

    if (eventType === "security_rag_evidence_scanned") {
      metrics.ragChunksInspected += asNumber(data.chunks_inspected);
      metrics.highRiskRagChunks += asNumber(
        data.high_risk_chunks ?? data.suspicious_chunks
      );
      metrics.ragWarnings += asNumber(data.warning_chunks);
      metrics.ragHighConfidenceDetections += asNumber(
        data.high_confidence_detections
      );

      asStringArray(data.high_categories).forEach((value) =>
        highCategories.add(value)
      );

      asStringArray(data.warning_categories).forEach((value) =>
        warningCategories.add(value)
      );
    }

    if (
      eventType === "security_prompt_injection_blocked" ||
      (
        eventType === "security_prompt_injection_detected" &&
        String(data.severity ?? "").toLowerCase() === "high"
      )
    ) {
      metrics.highConfidenceEvents += 1;

      asStringArray(data.categories).forEach((value) =>
        highCategories.add(value)
      );
    }

    if (eventType === "security_prompt_injection_warning") {
      metrics.warningEvents += 1;

      asStringArray(data.categories).forEach((value) =>
        warningCategories.add(value)
      );
    }

    if (eventType === "security_email_action_validated") {
      metrics.emailActionsValidated += 1;
    }

    if (eventType === "security_email_action_blocked") {
      metrics.emailActionsBlocked += 1;
    }
  }

  metrics.highCategories = [...highCategories].sort();
  metrics.warningCategories = [...warningCategories].sort();

  return metrics;
}

function isEditableKnowledge(filename?: string) {
  const lower = (filename ?? "").toLowerCase();
  return lower.endsWith(".txt") || lower.endsWith(".md");
}

function getTaskError(run?: LiveWorkflowResponse | null) {
  const value = run?.task?.error;
  return typeof value === "string" ? value.trim() : "";
}

function isKnowledgeRequiredError(message?: string | null) {
  const lower = (message ?? "").toLowerCase();

  return (
    lower.includes("private company knowledge") ||
    lower.includes("knowledge base") ||
    lower.includes("no relevant private")
  );
}


function App() {
  const [activeView, setActiveView] = useState<View>("dashboard");
  const [backendOnline, setBackendOnline] = useState(false);
  const [loading, setLoading] = useState(true);
  const [summary, setSummary] = useState<ObservabilitySummary | null>(null);
  const [events, setEvents] = useState<AgentEvent[]>([]);
  const [documents, setDocuments] = useState<KnowledgeDocument[]>([]);

  const [objective, setObjective] = useState("");
  const [companyName, setCompanyName] = useState("");
  const [recipientEmail, setRecipientEmail] = useState("");
  const [startingTask, setStartingTask] = useState(false);
  const [activeTaskId, setActiveTaskId] = useState<number | null>(null);
  const [liveRun, setLiveRun] = useState<LiveWorkflowResponse | null>(null);
  const [workflowError, setWorkflowError] = useState<string | null>(null);
  const [approvalLoading, setApprovalLoading] = useState(false);
  const [approvalMessage, setApprovalMessage] = useState<string | null>(null);

  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [uploadingDocument, setUploadingDocument] = useState(false);
  const [knowledgeMessage, setKnowledgeMessage] = useState<string | null>(null);
  const [knowledgeError, setKnowledgeError] = useState<string | null>(null);

  const [editingDocument, setEditingDocument] = useState<KnowledgeDocument | null>(null);
  const [editingContent, setEditingContent] = useState("");
  const [editLoading, setEditLoading] = useState(false);
  const [saveLoading, setSaveLoading] = useState(false);
  const [deletingId, setDeletingId] = useState<number | null>(null);

  const loadAppData = async () => {
    setLoading(true);

    try {
      const healthRequest = api
        .get("/health")
        .then(() => setBackendOnline(true))
        .catch(() => setBackendOnline(false));

      const summaryRequest = api
        .get("/observability/summary")
        .then((response) => setSummary(response.data))
        .catch(() => setSummary(null));

      const eventsRequest = api
        .get("/observability/events", { params: { limit: 200 } })
        .then((response) => {
          const nextEvents = response.data?.events;
          setEvents(Array.isArray(nextEvents) ? nextEvents : []);
        })
        .catch(() => setEvents([]));

      const documentsRequest = api
        .get("/knowledge")
        .then((response) => {
      const rawDocuments = Array.isArray(response.data?.documents)
        ? response.data.documents
        : Array.isArray(response.data)
        ? response.data
        : [];

      const normalizedDocuments: KnowledgeDocument[] = rawDocuments.map(
         (item: any) => ({
         id: item.id ?? item.document_id,
         filename: item.filename,
         document_type: item.document_type,
         source_path: item.source_path,
         created_at: item.created_at,
         chunk_count: item.chunk_count ?? item.chunks ?? 0,
      })
    );

      setDocuments(normalizedDocuments);
  })
   .catch(() => setDocuments([]));
      await Promise.all([
        healthRequest,
        summaryRequest,
        eventsRequest,
        documentsRequest,
      ]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadAppData();
  }, []);

  const pollTask = async (taskId: number) => {
    try {
      const response = await api.get(`/workflow/${taskId}/live`);
      setLiveRun(response.data);
      setWorkflowError(null);
      return response.data as LiveWorkflowResponse;
    } catch (error: any) {
      setWorkflowError(
        error?.response?.data?.detail ||
          error?.message ||
          "Could not read live workflow state."
      );
      return null;
    }
  };

  useEffect(() => {
    if (!activeTaskId) return;

    let cancelled = false;
    let timer: number | undefined;

    const tick = async () => {
      if (cancelled) return;

      const result = await pollTask(activeTaskId);
      const status = result?.status;

      if (
        !cancelled &&
        status !== "awaiting_approval" &&
        status !== "completed" &&
        status !== "failed"
      ) {
        timer = window.setTimeout(tick, 1000);
      }
    };

    void tick();

    return () => {
      cancelled = true;
      if (timer !== undefined) window.clearTimeout(timer);
    };
  }, [activeTaskId]);

  const startWorkflow = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setWorkflowError(null);
    setApprovalMessage(null);
    setLiveRun(null);
    setActiveTaskId(null);

    if (!objective.trim() || !companyName.trim() || !recipientEmail.trim()) {
      setWorkflowError("Please complete objective, company and recipient email.");
      return;
    }

    setStartingTask(true);

    try {
      const response = await api.post("/workflow/start", {
        objective: objective.trim(),
        company_name: companyName.trim(),
        recipient_email: recipientEmail.trim(),
      });

      const taskId = Number(response.data?.task_id);

      if (!Number.isFinite(taskId)) {
        throw new Error("Backend did not return a valid task_id.");
      }

      setLiveRun(response.data);
      setActiveTaskId(taskId);
      void loadAppData();
    } catch (error: any) {
      setWorkflowError(
        error?.response?.data?.detail || error?.message || "Could not start workflow."
      );
    } finally {
      setStartingTask(false);
    }
  };

  const submitDecision = async (decision: "approve" | "reject") => {
    if (!activeTaskId) return;

    setApprovalLoading(true);
    setApprovalMessage(null);
    setWorkflowError(null);

    try {
      await api.post(`/workflow/${activeTaskId}/decision`, {
        decision,
        comment:
          decision === "approve"
            ? "Reviewed and approved from the live frontend."
            : "Rejected from the live frontend.",
      });

      setApprovalMessage(
        decision === "approve"
          ? "Approved. The workflow resumed and Gmail may execute."
          : "Rejected. Gmail will not send this outreach."
      );

      const latest = await pollTask(activeTaskId);

      if (
        latest?.status !== "completed" &&
        latest?.status !== "failed" &&
        latest?.status !== "awaiting_approval"
      ) {
        // Force the polling effect to restart for resumed work.
        const id = activeTaskId;
        setActiveTaskId(null);
        window.setTimeout(() => setActiveTaskId(id), 0);
      }

      void loadAppData();
    } catch (error: any) {
      setWorkflowError(
        error?.response?.data?.detail || error?.message || "Decision failed."
      );
    } finally {
      setApprovalLoading(false);
    }
  };

  const uploadDocument = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setKnowledgeError(null);
    setKnowledgeMessage(null);

    if (!selectedFile) {
      setKnowledgeError("Choose a PDF, TXT or Markdown file first.");
      return;
    }

    const formData = new FormData();
    formData.append("file", selectedFile);
    setUploadingDocument(true);

    try {
      const response = await api.post("/knowledge/upload", formData);
      setKnowledgeMessage(
        response.data?.message ?? "Document uploaded and indexed successfully."
      );
      setSelectedFile(null);

      const input = document.getElementById(
        "knowledge-file-input"
      ) as HTMLInputElement | null;
      if (input) input.value = "";

      await loadAppData();
    } catch (error: any) {
      setKnowledgeError(
        error?.response?.data?.detail || error?.message || "Upload failed."
      );
    } finally {
      setUploadingDocument(false);
    }
  };

  const openEditDocument = async (documentItem: KnowledgeDocument) => {
    if (documentItem.id === null || documentItem.id === undefined) return;

    setKnowledgeError(null);
    setKnowledgeMessage(null);
    setEditLoading(true);

    try {
      const response = await api.get(`/knowledge/${documentItem.id}/content`);

      if (!response.data?.editable) {
        setKnowledgeError(
          response.data?.edit_note || "This document type cannot be edited inline."
        );
        return;
      }

      setEditingDocument(documentItem);
      setEditingContent(response.data?.content ?? "");
    } catch (error: any) {
      setKnowledgeError(
        error?.response?.data?.detail || error?.message || "Could not load document."
      );
    } finally {
      setEditLoading(false);
    }
  };

  const saveEditedDocument = async () => {
    if (editingDocument?.id === null || editingDocument?.id === undefined) return;

    setSaveLoading(true);
    setKnowledgeError(null);
    setKnowledgeMessage(null);

    try {
      const response = await api.put(`/knowledge/${editingDocument.id}`, {
        content: editingContent,
      });

      setKnowledgeMessage(
        response.data?.message ?? "Document updated and re-indexed."
      );
      setEditingDocument(null);
      setEditingContent("");
      await loadAppData();
    } catch (error: any) {
      setKnowledgeError(
        error?.response?.data?.detail || error?.message || "Could not save document."
      );
    } finally {
      setSaveLoading(false);
    }
  };

  const deleteDocument = async (documentItem: KnowledgeDocument) => {
    if (documentItem.id === null || documentItem.id === undefined) return;

    const confirmed = window.confirm(
      `Delete ${documentItem.filename ?? "this document"}?\n\n` +
        "Its database record, chunks and embeddings will be removed."
    );

    if (!confirmed) return;

    setDeletingId(documentItem.id);
    setKnowledgeError(null);
    setKnowledgeMessage(null);

    try {
      const response = await api.delete(`/knowledge/${documentItem.id}`);

      setDocuments((current) =>
        current.filter((item) => item.id !== documentItem.id)
      );

      setKnowledgeMessage(
        response.data?.message ??
          `${documentItem.filename ?? "Document"} deleted successfully.`
      );

      await loadAppData();
    } catch (error: any) {
      setKnowledgeError(
        error?.response?.data?.detail || error?.message || "Delete failed."
      );
    } finally {
      setDeletingId(null);
    }
  };

  const failureCount = useMemo(() => {
    const operations = summary?.operations ?? {};

    return Object.values(operations).reduce(
      (sum, operation) =>
        sum +
        (operation && typeof operation.failures === "number"
          ? operation.failures
          : 0),
      0
    );
  }, [summary]);

  const operationRows = useMemo(() => {
    const rows = Object.entries(summary?.operations ?? {}).filter(
      ([, value]) => value && typeof value === "object"
    ) as [string, OperationStats][];

    return rows.sort(
      ([, first], [, second]) =>
        (second?.average_duration_ms ?? 0) -
        (first?.average_duration_ms ?? 0)
    );
  }, [summary]);

  const securityMetrics = useMemo(
    () => buildSecurityMetrics(events),
    [events]
  );

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-icon">
            <BrainCircuit size={23} />
          </div>
          <div>
            <div className="brand-title">AI Employee</div>
            <div className="brand-subtitle">Autonomous BD Agent</div>
          </div>
        </div>

        <nav className="navigation">
          <div className="nav-section-title">Workspace</div>
          {navigation.map(({ key, label, icon: Icon }) => (
            <button
              key={key}
              className={activeView === key ? "nav-item active" : "nav-item"}
              onClick={() => setActiveView(key)}
            >
              <Icon size={18} />
              <span>{label}</span>
            </button>
          ))}
        </nav>

        <div className="sidebar-footer">
          <div
            className={
              backendOnline
                ? "connection-card connected"
                : "connection-card disconnected"
            }
          >
            {backendOnline ? <Wifi size={17} /> : <WifiOff size={17} />}
            <div>
              <strong>{backendOnline ? "Backend Online" : "Backend Offline"}</strong>
              <span>127.0.0.1:8000</span>
            </div>
          </div>
        </div>
      </aside>

      <main className="main-content">
        <header className="topbar">
          <div>
            <h1>
              {activeView === "dashboard"
                ? "Command Center"
                : activeView === "new-task"
                  ? "New Agent Task"
                  : activeView === "knowledge"
                    ? "Knowledge Base"
                    : "Observability"}
            </h1>
            <p>
              {activeView === "new-task"
                ? "Watch the real LangGraph execution as it happens."
                : activeView === "knowledge"
                  ? "Upload, edit, re-index and delete private RAG knowledge."
                  : activeView === "observability"
                    ? "Inspect execution latency, security enforcement and structured events."
                    : "Monitor your autonomous AI employee."}
            </p>
          </div>

          <button className="secondary-button" onClick={() => void loadAppData()}>
            <RefreshCw size={17} className={loading ? "spinning" : ""} />
            Refresh
          </button>
        </header>

        {activeView === "dashboard" && (
          <DashboardView
            backendOnline={backendOnline}
            summary={summary}
            documents={documents}
            failureCount={failureCount}
            operationRows={operationRows}
            events={events}
          />
        )}

        {activeView === "new-task" && (
          <section className="task-layout">
            <div className="panel task-panel">
              <div className="panel-heading">
                <div>
                  <h2>Launch Autonomous Task</h2>
                  <p>The API returns a task ID immediately. The UI then polls live state.</p>
                </div>
                <Sparkles size={21} />
              </div>

              <form className="task-form" onSubmit={startWorkflow}>
                <label>
                  Objective
                  <textarea
                    rows={6}
                    value={objective}
                    onChange={(event) => setObjective(event.target.value)}
                    placeholder="Research DHL Supply Chain and identify evidence-supported needs for our AI services."
                  />
                </label>

                <label>
                  Prospect company
                  <input
                    value={companyName}
                    onChange={(event) => setCompanyName(event.target.value)}
                    placeholder="DHL Supply Chain"
                  />
                </label>

                <label>
                  Recipient email
                  <input
                    type="email"
                    value={recipientEmail}
                    onChange={(event) => setRecipientEmail(event.target.value)}
                    placeholder="your-email@example.com"
                  />
                </label>

                {workflowError && (
                  <div className="error-box">
                    <AlertTriangle size={17} />
                    {workflowError}
                  </div>
                )}

                <button className="primary-button" disabled={startingTask} type="submit">
                  {startingTask ? (
                    <RefreshCw size={18} className="spinning" />
                  ) : (
                    <Send size={18} />
                  )}
                  {startingTask ? "Creating task..." : "Launch Agent"}
                </button>
              </form>

              {activeTaskId && (
                <div className="task-id-card">
                  <span>LIVE TASK</span>
                  <strong>#{activeTaskId}</strong>
                  <small>{liveRun?.status ?? "queued"}</small>
                </div>
              )}
            </div>

            <div className="panel pipeline-panel">
              <div className="panel-heading">
                <div>
                  <h2>Live Execution Pipeline</h2>
                  <p>Everything below comes from the current task trace.</p>
                </div>
                {liveRun?.background_running && <span className="live-badge">LIVE</span>}
              </div>

              <LivePipeline
                run={liveRun}
                approvalLoading={approvalLoading}
                approvalMessage={approvalMessage}
                onDecision={submitDecision}
              />
            </div>
          </section>
        )}

        {activeView === "knowledge" && (
          <KnowledgeView
            documents={documents}
            selectedFile={selectedFile}
            setSelectedFile={setSelectedFile}
            uploadingDocument={uploadingDocument}
            uploadDocument={uploadDocument}
            knowledgeMessage={knowledgeMessage}
            knowledgeError={knowledgeError}
            openEditDocument={openEditDocument}
            editLoading={editLoading}
            deleteDocument={deleteDocument}
            deletingId={deletingId}
          />
        )}

        {activeView === "observability" && (
          <section className="page-grid">
            <SecurityPanel metrics={securityMetrics} />

            <div className="panel">
              <div className="panel-heading">
                <div>
                  <h2>Operation Performance</h2>
                  <p>Real measured execution times.</p>
                </div>
              </div>
              <OperationTable operations={operationRows} />
            </div>

            <div className="panel">
              <div className="panel-heading">
                <div>
                  <h2>Event Stream</h2>
                  <p>Latest structured workflow, RAG and security events.</p>
                </div>
              </div>
              <EventList events={events} />
            </div>
          </section>
        )}
      </main>

      {editingDocument && (
        <div className="modal-backdrop">
          <div className="edit-modal">
            <div className="modal-header">
              <div>
                <span>EDIT & RE-INDEX</span>
                <h2>{editingDocument.filename}</h2>
              </div>
              <button
                className="icon-button"
                onClick={() => {
                  setEditingDocument(null);
                  setEditingContent("");
                }}
              >
                <X size={19} />
              </button>
            </div>

            <p className="modal-help">
              Saving rebuilds every text chunk and embedding, so pgvector uses the new content.
            </p>

            <textarea
              className="editor-textarea"
              value={editingContent}
              onChange={(event) => setEditingContent(event.target.value)}
            />

            <div className="modal-actions">
              <button
                className="secondary-button"
                onClick={() => {
                  setEditingDocument(null);
                  setEditingContent("");
                }}
              >
                Cancel
              </button>
              <button className="primary-button" disabled={saveLoading} onClick={saveEditedDocument}>
                {saveLoading && <RefreshCw size={16} className="spinning" />}
                {saveLoading ? "Re-indexing..." : "Save & Re-index"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}


function LivePipeline({
  run,
  approvalLoading,
  approvalMessage,
  onDecision,
}: {
  run: LiveWorkflowResponse | null;
  approvalLoading: boolean;
  approvalMessage: string | null;
  onDecision: (decision: "approve" | "reject") => void;
}) {
  const trace = run?.trace;
  const steps = trace?.steps ?? [];
  const emailDraft = run?.email_draft ?? null;

  if (!run) {
    return (
      <div className="pipeline-empty">
        <Bot size={30} />
        <strong>No live task yet</strong>
        <p>Launch a task and each real execution step will appear here.</p>
      </div>
    );
  }

  const taskError = getTaskError(run);
  const knowledgeRequired = isKnowledgeRequiredError(taskError);

  const currentStepLabel =
    knowledgeRequired
      ? "Knowledge Base documents required"
      : steps.find((step) => step.status === "running")?.label ??
        (run.status === "awaiting_approval"
          ? "Human approval"
          : run.status === "completed"
            ? "Workflow completed"
            : run.status === "failed"
              ? "Workflow stopped"
              : "Preparing workflow");

  return (
    <div className="live-pipeline">
      <div className="current-state-card">
        <div>
          {run.status === "completed" ? <CheckCircle2 size={18} /> : <Activity size={18} />}
        </div>
        <div>
          <span>CURRENT WORKFLOW STATE</span>
          <strong>{currentStepLabel}</strong>
          <small>
            Task #{run.task_id ?? "—"} · {run.status ?? "queued"}
          </small>
        </div>
      </div>

      {steps.map((step) => (
        <LiveStepCard key={step.step} step={step} forceOpen={step.status === "running"}>
          <StepActualData stepNumber={step.step} run={run} />
        </LiveStepCard>
      ))}

      {!knowledgeRequired && (
        <ServicesCard services={trace?.recommended_services ?? []} />
      )}

      {run.status === "awaiting_approval" && (
        <div className="approval-console">
          <div className="approval-title">
            <AlertTriangle size={18} />
            <div>
              <strong>Human approval required</strong>
              <span>The workflow is paused before the Gmail side effect.</span>
            </div>
          </div>

          {emailDraft ? (
            <div className="email-preview">
              <div><span>TO</span><strong>{emailDraft.recipient_email ?? "—"}</strong></div>
              <div><span>SUBJECT</span><strong>{emailDraft.subject ?? "—"}</strong></div>
              <div className="email-body"><span>BODY</span><pre>{emailDraft.body ?? "—"}</pre></div>
            </div>
          ) : (
            <div className="soft-warning">Waiting for the saved draft to become available.</div>
          )}

          <div className="approval-actions">
            <button className="reject-button" disabled={approvalLoading} onClick={() => onDecision("reject")}>
              <XCircle size={16} /> Reject
            </button>
            <button className="approve-button" disabled={approvalLoading || !emailDraft} onClick={() => onDecision("approve")}>
              {approvalLoading ? <RefreshCw size={16} className="spinning" /> : <CheckCircle2 size={16} />}
              {approvalLoading ? "Processing..." : "Approve & Send"}
            </button>
          </div>
        </div>
      )}

      {approvalMessage && <div className="success-box"><CheckCircle2 size={16} />{approvalMessage}</div>}

      {run.status === "failed" && (
        <div className="error-box">
          <AlertTriangle size={17} />
          <span>
            {taskError ||
              "Workflow stopped safely. Open Observability for the recorded error."}
          </span>
        </div>
      )}
    </div>
  );
}


function LiveStepCard({
  step,
  forceOpen,
  children,
}: {
  step: LiveStep;
  forceOpen?: boolean;
  children: ReactNode;
}) {
  return (
    <details className={`live-step ${step.status}`} open={forceOpen ? true : undefined}>
      <summary>
        <div className={`step-circle ${step.status}`}>
          {step.status === "completed" ? <CheckCircle2 size={15} /> : step.step}
        </div>
        <div className="step-copy">
          <strong>{step.label}</strong>
          <span>
            {step.status === "running"
              ? "Running now"
              : step.status === "completed"
                ? "Completed"
                : step.status === "failed"
                  ? "Failed"
                  : step.status === "skipped"
                    ? "Skipped"
                    : "Waiting"}
          </span>
        </div>
        <div className="step-meta">
          <span className={`status-pill ${step.status}`}>{step.status}</span>
          <small>{formatDuration(step.duration_ms)}</small>
        </div>
        <ChevronDown size={16} className="chevron" />
      </summary>
      <div className="step-body">{children}</div>
    </details>
  );
}


function StepActualData({
  stepNumber,
  run,
}: {
  stepNumber: number;
  run: LiveWorkflowResponse;
}) {
  const trace = run.trace;

  if (!trace) return <div className="waiting-copy">Waiting for trace data...</div>;

  if (stepNumber === 1) {
    const found = trace.memory?.existing_memory_found;
    return (
      <div className="actual-grid">
        <ActualValue label="Prospect" value={trace.company_name ?? "—"} />
        <ActualValue
          label="Previous lead found"
          value={found === null || found === undefined ? "Checking..." : found ? "Yes" : "No"}
        />
        <ActualValue label="Database" value="PostgreSQL" />
      </div>
    );
  }

  if (stepNumber === 2) {
    const research = trace.web_research;
    return (
      <div className="actual-stack">
        <ActualValue label="Search query" value={research?.query ?? "Waiting..."} wide />
        <ActualValue
          label="Results returned"
          value={research?.results_count === null || research?.results_count === undefined ? "—" : String(research.results_count)}
        />
        {(research?.sources?.length ?? 0) > 0 && (
          <div className="source-list">
            <span className="section-label">SOURCES USED</span>
            {research?.sources?.map((source, index) => (
              <div className="source-item" key={`${source.url ?? index}-${index}`}>
                <strong>{source.title ?? "Untitled source"}</strong>
                {source.url && <small>{source.url}</small>}
              </div>
            ))}
          </div>
        )}
      </div>
    );
  }

  if (stepNumber === 3) {
    const sources = trace.rag_sources ?? [];
    return sources.length ? (
      <div className="rag-result-list">
        {sources.map((source, index) => (
          <div className="rag-result" key={`${source.filename ?? index}-${source.chunk_index ?? index}`}>
            <div>
              <FileText size={16} />
              <div>
                <strong>{source.filename ?? "Knowledge document"}</strong>
                <span>Chunk {source.chunk_index ?? 0}</span>
              </div>
            </div>
            <b>{formatSimilarity(source.similarity)}</b>
          </div>
        ))}
      </div>
    ) : (
      <div className={
        isKnowledgeRequiredError(getTaskError(run))
          ? "soft-warning"
          : "waiting-copy"
      }>
        {isKnowledgeRequiredError(getTaskError(run))
          ? getTaskError(run)
          : "No private RAG knowledge has been retrieved yet."}
      </div>
    );
  }

  if (stepNumber === 4) {
    return (
      <div className="actual-stack">
        <ActualValue
          label="Current node"
          value={trace.current_node === "analyze" ? "Mistral structured analysis running" : "Analysis state recorded"}
          wide
        />
        <ActualValue
          label="Recommended services identified"
          value={String(trace.recommended_services?.length ?? 0)}
        />
      </div>
    );
  }

  if (stepNumber === 5) {
    return <ScoreBreakdown trace={trace} />;
  }

  if (stepNumber === 6) {
    const draft = run.email_draft;
    return draft ? (
      <div className="actual-stack">
        <ActualValue label="Draft ID" value={String(draft.draft_id ?? "—")} />
        <ActualValue label="Draft status" value={draft.status ?? "—"} />
        <ActualValue label="Subject" value={draft.subject ?? "—"} wide />
      </div>
    ) : (
      <div className="waiting-copy">
        {trace.lead_score !== null && trace.lead_score !== undefined && trace.lead_score < 60
          ? "Lead did not reach the outreach threshold, so email drafting was skipped."
          : "Waiting for an email draft."}
      </div>
    );
  }

  if (stepNumber === 7) {
    return (
      <div className="actual-grid">
        <ActualValue label="Approval state" value={trace.approval_status ?? run.status ?? "pending"} />
        <ActualValue label="Draft ID" value={String(trace.draft_id ?? "—")} />
      </div>
    );
  }

  if (stepNumber === 8) {
    return (
      <div className="actual-stack">
        <ActualValue label="Email state" value={trace.email_send_status ?? run.email_draft?.status ?? "pending"} />
        <ActualValue label="Gmail message ID" value={run.email_draft?.gmail_message_id ?? "—"} wide />
        <ActualValue label="Sent at" value={formatDate(run.email_draft?.sent_at)} wide />
      </div>
    );
  }

  return null;
}


function ScoreBreakdown({ trace }: { trace: TaskTrace }) {
  const scores = trace.score_breakdown ?? {};
  const rows = [
    ["Industry fit", scores.industry_fit],
    ["Company-size fit", scores.company_size_fit],
    ["AI need", scores.ai_need],
    ["Growth signal", scores.growth_signal],
    ["Contact potential", scores.contact_potential],
  ] as const;

  return (
    <div className="score-live-box">
      {rows.map(([label, value]) => {
        const numeric = typeof value === "number" ? value : null;
        const percent = numeric === null ? 0 : (numeric / 20) * 100;

        return (
          <div className="score-row" key={label}>
            <div className="score-row-top">
              <span>{label}</span>
              <strong>{numeric === null ? "— / 20" : `${numeric} / 20`}</strong>
            </div>
            <div className="score-track">
              <div className="score-fill" style={{ width: `${percent}%` }} />
            </div>
          </div>
        );
      })}

      <div className="total-score-live">
        <div>
          <span>TOTAL</span>
          <strong>{trace.lead_score ?? "—"}/100</strong>
        </div>
        <b>{trace.rating ?? "Waiting for score"}</b>
      </div>
    </div>
  );
}


function ServicesCard({ services }: { services: string[] }) {
  return (
    <div className="services-card">
      <div className="services-card-heading">
        <Sparkles size={17} />
        <div>
          <strong>Services we can provide this prospect</strong>
          <span>Selected by Mistral from our private internal knowledge.</span>
        </div>
      </div>

      {services.length ? (
        <div className="service-chip-list">
          {services.map((service, index) => (
            <div className="service-match" key={`${service}-${index}`}>
              <span>{index + 1}</span>
              <strong>{service}</strong>
            </div>
          ))}
        </div>
      ) : (
        <p>No service recommendations have been produced yet.</p>
      )}
    </div>
  );
}


function ActualValue({
  label,
  value,
  wide = false,
}: {
  label: string;
  value: string;
  wide?: boolean;
}) {
  return (
    <div className={wide ? "actual-value wide" : "actual-value"}>
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}


function KnowledgeView({
  documents,
  selectedFile,
  setSelectedFile,
  uploadingDocument,
  uploadDocument,
  knowledgeMessage,
  knowledgeError,
  openEditDocument,
  editLoading,
  deleteDocument,
  deletingId,
}: {
  documents: KnowledgeDocument[];
  selectedFile: File | null;
  setSelectedFile: (file: File | null) => void;
  uploadingDocument: boolean;
  uploadDocument: (event: FormEvent<HTMLFormElement>) => Promise<void>;
  knowledgeMessage: string | null;
  knowledgeError: string | null;
  openEditDocument: (document: KnowledgeDocument) => Promise<void>;
  editLoading: boolean;
  deleteDocument: (document: KnowledgeDocument) => Promise<void>;
  deletingId: number | null;
}) {
  return (
    <section className="knowledge-page">
      <div className="panel">
        <div className="panel-heading">
          <div>
            <h2>Upload Knowledge</h2>
            <p>PDF, TXT and Markdown files are chunked, embedded and indexed in pgvector.</p>
          </div>
          <Upload size={20} />
        </div>

        <form className="knowledge-upload-form" onSubmit={uploadDocument}>
          <label className="file-drop-area">
            <Upload size={26} />
            <strong>{selectedFile ? selectedFile.name : "Choose a knowledge document"}</strong>
            <span>PDF · TXT · MD</span>
            <input
              id="knowledge-file-input"
              type="file"
              accept=".pdf,.txt,.md,application/pdf,text/plain,text/markdown"
              onChange={(event) => setSelectedFile(event.target.files?.[0] ?? null)}
            />
          </label>

          <button className="primary-button" type="submit" disabled={!selectedFile || uploadingDocument}>
            {uploadingDocument ? <RefreshCw size={17} className="spinning" /> : <Upload size={17} />}
            {uploadingDocument ? "Indexing..." : "Upload & Index"}
          </button>
        </form>

        {knowledgeMessage && <div className="success-box"><CheckCircle2 size={16} />{knowledgeMessage}</div>}
        {knowledgeError && <div className="error-box"><AlertTriangle size={16} />{knowledgeError}</div>}
      </div>

      <div className="panel">
        <div className="panel-heading">
          <div>
            <h2>Indexed Documents</h2>
            <p>TXT/MD can be edited and automatically re-embedded. All files can be deleted.</p>
          </div>
          <span className="small-badge">{documents.length} documents</span>
        </div>

        <div className="knowledge-grid">
          {documents.map((documentItem, index) => {
            const editable = isEditableKnowledge(documentItem.filename);
            const deleting = documentItem.id === deletingId;

            return (
              <div className="knowledge-card" key={documentItem.id ?? index}>
                <div className="knowledge-card-main">
                  <div className="document-icon"><FileText size={20} /></div>
                  <div>
                    <strong>{documentItem.filename ?? "Knowledge document"}</strong>
                    <span>{documentItem.document_type ?? "document"}</span>
                    <small>
                      {documentItem.chunk_count !== undefined ? `${documentItem.chunk_count} chunks · ` : ""}
                      {formatDate(documentItem.created_at)}
                    </small>
                  </div>
                </div>

                <div className="knowledge-actions">
                  <button
                    type="button"
                    className="edit-button"
                    disabled={!editable || editLoading}
                    title={editable ? "Edit and rebuild embeddings" : "PDF inline editing is disabled. Delete and upload a replacement."}
                    onClick={() => void openEditDocument(documentItem)}
                  >
                    <Edit3 size={15} /> Edit
                  </button>
                  <button
                    type="button"
                    className="delete-button"
                    disabled={deleting}
                    title="Delete this document and its indexed vector chunks"
                    onClick={() => void deleteDocument(documentItem)}
                  >
                    {deleting ? <RefreshCw size={15} className="spinning" /> : <Trash2 size={15} />}
                    {deleting ? "Deleting" : "Delete"}
                  </button>
                </div>
              </div>
            );
          })}

          {!documents.length && (
            <div className="empty-state">
              <Database size={28} />
              <strong>No documents yet</strong>
              <p>Upload the first knowledge file above.</p>
            </div>
          )}
        </div>
      </div>
    </section>
  );
}



function SecurityPanel({
  metrics,
}: {
  metrics: SecurityMetrics;
}) {
  const highRiskDetections =
    metrics.webHighConfidenceDetections +
    metrics.ragHighConfidenceDetections;

  const warningDetections =
    metrics.webWarnings +
    metrics.ragWarnings;

  const hasHighRisk =
    highRiskDetections > 0 ||
    metrics.highConfidenceEvents > 0;

  const hasBlockedAction =
    metrics.emailActionsBlocked > 0;

  const statusLabel = hasHighRisk
    ? "High-confidence injection neutralized"
    : hasBlockedAction
      ? "Unsafe action blocked"
      : warningDetections > 0
        ? "Protected with contextual warnings"
        : "Security controls healthy";

  const StatusIcon =
    hasHighRisk || hasBlockedAction
      ? ShieldAlert
      : ShieldCheck;

  return (
    <div className="panel security-panel observability-wide">
      <div className="panel-heading security-heading">
        <div>
          <div className="security-title-row">
            <span className={`security-status-icon ${hasHighRisk || hasBlockedAction ? "warning" : "safe"}`}>
              <StatusIcon size={18} />
            </span>

            <div>
              <h2>Agent Security</h2>
              <p>
                Prompt-injection scanning, untrusted-evidence isolation and deterministic action policy.
              </p>
            </div>
          </div>
        </div>

        <span className={`security-health-badge ${hasHighRisk || hasBlockedAction ? "warning" : "safe"}`}>
          {statusLabel}
        </span>
      </div>

      <div className="security-metric-grid">
        <SecurityMetric
          label="Web sources inspected"
          value={metrics.webSourcesInspected}
          tone="neutral"
        />

        <SecurityMetric
          label="High-risk web sources"
          value={metrics.highRiskWebSources}
          tone={metrics.highRiskWebSources > 0 ? "danger" : "safe"}
        />

        <SecurityMetric
          label="Web warnings"
          value={metrics.webWarnings}
          tone={metrics.webWarnings > 0 ? "warning" : "safe"}
        />

        <SecurityMetric
          label="RAG chunks inspected"
          value={metrics.ragChunksInspected}
          tone="neutral"
        />

        <SecurityMetric
          label="High-risk RAG chunks"
          value={metrics.highRiskRagChunks}
          tone={metrics.highRiskRagChunks > 0 ? "danger" : "safe"}
        />

        <SecurityMetric
          label="RAG warnings"
          value={metrics.ragWarnings}
          tone={metrics.ragWarnings > 0 ? "warning" : "safe"}
        />

        <SecurityMetric
          label="Email actions validated"
          value={metrics.emailActionsValidated}
          tone="safe"
        />

        <SecurityMetric
          label="Email actions blocked"
          value={metrics.emailActionsBlocked}
          tone={metrics.emailActionsBlocked > 0 ? "danger" : "safe"}
        />
      </div>

      <div className="security-detail-grid">
        <div className="security-detail-card">
          <span>HIGH-CONFIDENCE DETECTIONS</span>
          <strong>{highRiskDetections}</strong>

          {metrics.highCategories.length ? (
            <div className="security-chip-row">
              {metrics.highCategories.map((category) => (
                <span className="security-chip high" key={category}>
                  {prettyName(category)}
                </span>
              ))}
            </div>
          ) : (
            <small>No high-confidence categories in the loaded event window.</small>
          )}
        </div>

        <div className="security-detail-card">
          <span>CONTEXTUAL WARNINGS</span>
          <strong>{warningDetections}</strong>

          {metrics.warningCategories.length ? (
            <div className="security-chip-row">
              {metrics.warningCategories.map((category) => (
                <span className="security-chip warning" key={category}>
                  {prettyName(category)}
                </span>
              ))}
            </div>
          ) : (
            <small>No medium-severity warning categories in the loaded event window.</small>
          )}
        </div>

        <div className="security-detail-card security-policy-card">
          <span>POLICY BOUNDARY</span>
          <strong>
            {metrics.emailActionsBlocked > 0
              ? "Enforcement triggered"
              : "Human approval + Python gate active"}
          </strong>

          <small>
            Web and RAG text are reference data only. Consequential email actions still require stored approval and deterministic validation.
          </small>
        </div>
      </div>

      <div className="security-window-note">
        Showing security metrics from the most recent {metrics.eventsAnalyzed} structured events loaded by the UI.
      </div>
    </div>
  );
}


function SecurityMetric({
  label,
  value,
  tone,
}: {
  label: string;
  value: number;
  tone: "neutral" | "safe" | "warning" | "danger";
}) {
  return (
    <div className={`security-metric-card ${tone}`}>
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}


function DashboardView({
  backendOnline,
  summary,
  documents,
  failureCount,
  operationRows,
  events,
}: {
  backendOnline: boolean;
  summary: ObservabilitySummary | null;
  documents: KnowledgeDocument[];
  failureCount: number;
  operationRows: [string, OperationStats][];
  events: AgentEvent[];
}) {
  return (
    <>
      <section className="metric-grid">
        <MetricCard label="Backend" value={backendOnline ? "Online" : "Offline"} icon={backendOnline ? CheckCircle2 : AlertTriangle} />
        <MetricCard label="Tasks" value={String(summary?.tasks_observed ?? 0)} icon={Bot} />
        <MetricCard label="Knowledge" value={String(documents.length)} icon={Database} />
        <MetricCard label="Failures" value={String(failureCount)} icon={failureCount ? AlertTriangle : CheckCircle2} />
      </section>

      <section className="hero-panel">
        <div>
          <span className="eyebrow">LIVE AUTONOMOUS WORKFORCE</span>
          <h2>Research. Retrieve. Reason. Score. Review. Act.</h2>
          <p>
            The frontend now reads real workflow state instead of pretending each pipeline step happened.
          </p>
        </div>
        <BrainCircuit size={54} />
      </section>

      <section className="page-grid">
        <div className="panel">
          <div className="panel-heading"><div><h2>Operation Performance</h2><p>Measured backend latency.</p></div><Clock3 size={19} /></div>
          <OperationTable operations={operationRows.slice(0, 8)} />
        </div>
        <div className="panel">
          <div className="panel-heading"><div><h2>Recent Events</h2><p>Structured execution events.</p></div><Activity size={19} /></div>
          <EventList events={events.slice(-10)} />
        </div>
      </section>
    </>
  );
}


function MetricCard({ label, value, icon: Icon }: { label: string; value: string; icon: ElementType }) {
  return (
    <div className="metric-card">
      <div className="metric-icon"><Icon size={20} /></div>
      <div><span>{label}</span><strong>{value}</strong></div>
    </div>
  );
}


function OperationTable({ operations }: { operations: [string, OperationStats][] }) {
  if (!operations.length) return <div className="empty-state"><Activity size={26} /><strong>No operation data yet</strong></div>;

  return (
    <div className="operation-table">
      <div className="operation-row header"><span>Operation</span><span>Runs</span><span>Failures</span><span>Average</span></div>
      {operations.map(([name, data]) => (
        <div className="operation-row" key={name}>
          <span>{prettyName(name)}</span>
          <span>{data.runs}</span>
          <span className={data.failures ? "danger-text" : "success-text"}>{data.failures}</span>
          <span>{formatDuration(data.average_duration_ms)}</span>
        </div>
      ))}
    </div>
  );
}


function EventList({ events }: { events: AgentEvent[] }) {
  const safeEvents = Array.isArray(events)
    ? events.filter((event) => event && typeof event === "object")
    : [];

  if (!safeEvents.length) {
    return (
      <div className="empty-state">
        <Activity size={26} />
        <strong>No events yet</strong>
      </div>
    );
  }

  return (
    <div className="event-list">
      {[...safeEvents].reverse().map((event, index) => {
        const eventType =
          typeof event.event_type === "string" && event.event_type.trim()
            ? event.event_type
            : "unknown_event";

        const timestamp =
          typeof event.timestamp === "string"
            ? event.timestamp
            : "";

        const data =
          event.data && typeof event.data === "object"
            ? event.data
            : {};

        const sourceLabel = String(
          data.company_name ??
          data.operation ??
          data.source_type ??
          "System"
        );

        return (
          <div
            className="event-item"
            key={`${timestamp || "event"}-${index}`}
          >
            <span
              className={
                eventType.includes("failed") ||
                eventType.includes("blocked")
                  ? "event-dot failed"
                  : "event-dot"
              }
            />

            <div>
              <strong>{prettyName(eventType)}</strong>
              <small>{sourceLabel}</small>
            </div>

            <time>
              {timestamp ? formatDate(timestamp) : "—"}
            </time>
          </div>
        );
      })}
    </div>
  );
}

export default App;
