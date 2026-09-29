/**
 * SACCO AI Admin Intelligence & Operations Dashboard Client Controller
 */

const API_BASE = window.location.origin;
let authToken = localStorage.getItem("sacco_admin_token") || null;
let currentAdmin = null;

// --------------------------------------------------------------------------
// API Client Helper
// --------------------------------------------------------------------------
async function apiFetch(endpoint, options = {}) {
  const headers = {
    "Content-Type": "application/json",
    ...(options.headers || {}),
  };
  if (authToken) {
    headers["Authorization"] = `Bearer ${authToken}`;
  }
  const response = await fetch(`${API_BASE}${endpoint}`, {
    ...options,
    headers,
  });
  if (response.status === 401) {
    handleLogout();
    throw new Error("Session expired. Please sign in again.");
  }
  if (!response.ok) {
    const errData = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(errData.detail || `Request failed with status ${response.status}`);
  }
  return response.json();
}

// --------------------------------------------------------------------------
// Auth Lifecycle
// --------------------------------------------------------------------------
async function checkAuth() {
  if (!authToken) {
    showLogin();
    return;
  }
  try {
    currentAdmin = await apiFetch("/api/admin/auth/me");
    setupUserInterface(currentAdmin);
    hideLogin();
    loadDashboardData();
  } catch (err) {
    showLogin();
  }
}

function showLogin() {
  document.getElementById("login-overlay").classList.remove("hidden");
  document.getElementById("app-shell").classList.add("hidden");
}

function hideLogin() {
  document.getElementById("login-overlay").classList.add("hidden");
  document.getElementById("app-shell").classList.remove("hidden");
}

function handleLogout() {
  authToken = null;
  localStorage.removeItem("sacco_admin_token");
  currentAdmin = null;
  showLogin();
}

function setupUserInterface(admin) {
  document.getElementById("sidebar-sacco-id").textContent = admin.sacco_id;
  document.getElementById("user-name").textContent = admin.username;
  document.getElementById("user-role").textContent = admin.role.toUpperCase();
  document.getElementById("user-avatar").textContent = admin.username[0].toUpperCase();
}

// --------------------------------------------------------------------------
// Tab Navigation
// --------------------------------------------------------------------------
function setupNavigation() {
  const navItems = document.querySelectorAll(".nav-item");
  navItems.forEach((btn) => {
    btn.addEventListener("click", () => {
      navItems.forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      const targetTab = btn.getAttribute("data-tab");

      document.querySelectorAll(".tab-pane").forEach((pane) => pane.classList.remove("active"));
      const activePane = document.getElementById(`tab-${targetTab}`);
      if (activePane) activePane.classList.add("active");

      // Update Header title
      const titles = {
        overview: ["Executive Operations Overview", "Real-time member interactions, financial goal trends & automated intelligence"],
        gaps: ["Knowledge-Gap Intelligence", "Unanswered member inquiries flagged by RAG answerability gates"],
        escalations: ["Staff Escalations & Dispute Queue", "Inquiries routed for human customer-care intervention"],
        knowledge: ["Policy Knowledge Base & Workflow", "Approved SACCO knowledge synchronized into Qdrant vector memory"],
        quality: ["AI Quality & Evaluation Benchmarks", "Continuous evaluation metrics tracked across developmental milestones"],
        health: ["System & Infrastructure Health", "Real-time connectivity of PostgreSQL, Qdrant cluster & Groq LLM inference"],
      };
      if (titles[targetTab]) {
        document.getElementById("page-title").textContent = titles[targetTab][0];
        document.getElementById("page-subtitle").textContent = titles[targetTab][1];
      }

      // Refresh tab-specific data
      if (targetTab === "gaps") loadKnowledgeGaps();
      if (targetTab === "escalations") loadEscalations();
      if (targetTab === "knowledge") loadKnowledgeDocs();
      if (targetTab === "quality") loadEvaluationHistory();
      if (targetTab === "health") loadSystemHealth();
    });
  });
}

// --------------------------------------------------------------------------
// Data Fetching: Overview & KPIs
// --------------------------------------------------------------------------
async function loadDashboardData() {
  try {
    const kpis = await apiFetch("/api/admin/analytics/overview");
    document.getElementById("kpi-members").textContent = kpis.total_members.toLocaleString();
    document.getElementById("kpi-questions").textContent = kpis.total_questions_answered.toLocaleString();
    document.getElementById("kpi-gaps").textContent = kpis.knowledge_gaps_count;
    document.getElementById("kpi-escalations").textContent = kpis.open_escalations_count;
    document.getElementById("kpi-csat").textContent = `${kpis.satisfaction_rate_pct}%`;
    document.getElementById("kpi-groundedness").textContent = `${kpis.groundedness_score_pct}%`;

    document.getElementById("badge-gaps-count").textContent = kpis.knowledge_gaps_count;
    document.getElementById("badge-escalations-count").textContent = kpis.open_escalations_count;

    loadTopQuestions();
    loadGoalInsights();
    loadLanguageBreakdown();
  } catch (err) {
    console.error("Failed to load overview KPIs:", err);
  }
}

async function loadTopQuestions() {
  try {
    const questions = await apiFetch("/api/admin/analytics/questions?limit=6");
    const tbody = document.getElementById("tbody-faq");
    if (!questions.length) {
      tbody.innerHTML = `<tr><td colspan="3" class="loading">No question data recorded yet.</td></tr>`;
      return;
    }
    tbody.innerHTML = questions
      .map(
        (q) => `
        <tr>
          <td><strong>${q.topic_or_query}</strong><br><small style="color:var(--text-dim)">${q.category}</small></td>
          <td><b>${q.count}</b></td>
          <td><span class="panel-badge">${q.percentage}%</span></td>
        </tr>
      `
      )
      .join("");
  } catch (err) {
    console.error("Failed to load questions:", err);
  }
}

async function loadGoalInsights() {
  try {
    const goals = await apiFetch("/api/admin/analytics/goals");
    const tbody = document.getElementById("tbody-goals");
    if (!goals.length) {
      tbody.innerHTML = `<tr><td colspan="3" class="loading">No member goals created yet.</td></tr>`;
      return;
    }
    tbody.innerHTML = goals
      .map(
        (g) => `
        <tr>
          <td><strong>${g.goal_type}</strong></td>
          <td>${g.count} <small>(${g.percentage}%)</small></td>
          <td>KSh ${g.avg_target_amount.toLocaleString()}</td>
        </tr>
      `
      )
      .join("");
  } catch (err) {
    console.error("Failed to load goal insights:", err);
  }
}

async function loadLanguageBreakdown() {
  try {
    const lang = await apiFetch("/api/admin/analytics/languages");
    document.getElementById("lang-bar-en").style.width = `${lang.english_pct}%`;
    document.getElementById("lang-bar-sw").style.width = `${lang.swahili_pct}%`;
    document.getElementById("lang-bar-mixed").style.width = `${lang.mixed_sheng_pct}%`;

    document.getElementById("lang-pct-en").textContent = `${lang.english_pct}%`;
    document.getElementById("lang-pct-sw").textContent = `${lang.swahili_pct}%`;
    document.getElementById("lang-pct-mixed").textContent = `${lang.mixed_sheng_pct}%`;
  } catch (err) {
    console.error("Failed to load language breakdown:", err);
  }
}

// --------------------------------------------------------------------------
// Data Fetching: Knowledge Gaps
// --------------------------------------------------------------------------
async function loadKnowledgeGaps() {
  const tbody = document.getElementById("tbody-knowledge-gaps");
  try {
    const summary = await apiFetch("/intelligence/knowledge-gaps/summary?limit=50");
    const gaps = summary.recent_gaps || [];
    if (!gaps.length) {
      tbody.innerHTML = `<tr><td colspan="6" style="text-align:center; padding:24px; color:var(--text-muted)">🎉 No unresolved knowledge gaps found. All member questions are grounded!</td></tr>`;
      return;
    }
    tbody.innerHTML = gaps
      .map(
        (gap) => `
        <tr>
          <td><code>${gap.sacco_id}</code></td>
          <td><strong>${gap.query}</strong></td>
          <td><span class="panel-badge">${(gap.language || "en").toUpperCase()}</span></td>
          <td>${gap.top_retrieval_score !== null ? gap.top_retrieval_score.toFixed(3) : "0.000"}</td>
          <td>${(gap.created_at || "").slice(0, 16).replace("T", " ")}</td>
          <td>
            <button class="btn-secondary btn-sm" onclick="openCreateDocForGap('${escapeHtml(gap.query)}')">+ Draft Policy</button>
          </td>
        </tr>
      `
      )
      .join("");
  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="6" class="loading">Failed to load knowledge gaps.</td></tr>`;
  }
}

// --------------------------------------------------------------------------
// Data Fetching: Escalations Queue
// --------------------------------------------------------------------------
async function loadEscalations() {
  const tbody = document.getElementById("tbody-escalations");
  const statusFilter = document.getElementById("filter-escalation-status").value;
  const endpoint = statusFilter ? `/api/admin/escalations?status=${statusFilter}` : `/api/admin/escalations`;
  try {
    const escalations = await apiFetch(endpoint);
    if (!escalations.length) {
      tbody.innerHTML = `<tr><td colspan="8" style="text-align:center; padding:24px; color:var(--text-muted)">No escalation tickets matching this filter.</td></tr>`;
      return;
    }
    tbody.innerHTML = escalations
      .map(
        (esc) => `
        <tr>
          <td><code>#${esc.id}</code></td>
          <td><strong>${esc.member_name || "Guest Member"}</strong><br><small style="color:var(--text-dim)">${esc.conversation_key}</small></td>
          <td style="max-width:280px;">${esc.query}</td>
          <td><span class="panel-badge">${esc.category.replace("_", " ")}</span></td>
          <td><span class="priority-tag ${esc.priority}">${esc.priority.toUpperCase()}</span></td>
          <td><span class="status-tag ${esc.status}">${esc.status.replace("_", " ")}</span></td>
          <td>${(esc.created_at || "").slice(0, 16).replace("T", " ")}</td>
          <td>
            <button class="btn-primary btn-sm" onclick="openEscalationModal(${esc.id}, '${escapeHtml(esc.query)}', '${esc.status}', '${esc.priority}')">Manage</button>
          </td>
        </tr>
      `
      )
      .join("");
  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="8" class="loading">Failed to load escalations.</td></tr>`;
  }
}

// --------------------------------------------------------------------------
// Data Fetching: Knowledge Documents
// --------------------------------------------------------------------------
async function loadKnowledgeDocs() {
  const tbody = document.getElementById("tbody-docs");
  try {
    const docs = await apiFetch("/api/admin/knowledge");
    if (!docs.length) {
      tbody.innerHTML = `<tr><td colspan="7" style="text-align:center; padding:24px; color:var(--text-muted)">No custom policy documents created yet.</td></tr>`;
      return;
    }
    tbody.innerHTML = docs
      .map(
        (d) => `
        <tr>
          <td><code>${d.id}</code></td>
          <td><strong>${d.title}</strong></td>
          <td><span class="panel-badge">${d.category}</span></td>
          <td>v${d.version}</td>
          <td><span class="status-tag ${d.status}">${d.status}</span></td>
          <td>${d.qdrant_indexed_at ? "✅ Synced" : "⏳ Pending Approval"}</td>
          <td>
            ${
              d.status !== "approved"
                ? `<button class="btn-primary btn-sm" onclick="approveDocument('${d.id}')">Approve & Ingest</button>`
                : `<span style="color:var(--primary); font-size:12px; font-weight:600;">Active in RAG</span>`
            }
          </td>
        </tr>
      `
      )
      .join("");
  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="7" class="loading">Failed to load knowledge documents.</td></tr>`;
  }
}

async function approveDocument(docId) {
  if (!confirm("Approve this policy document and index into live Qdrant vector memory?")) return;
  try {
    await apiFetch(`/api/admin/knowledge/${docId}/approve`, { method: "PATCH" });
    alert("Document approved! Vector embeddings synchronized with Qdrant.");
    loadKnowledgeDocs();
    loadDashboardData();
  } catch (err) {
    alert(`Failed to approve document: ${err.message}`);
  }
}

// --------------------------------------------------------------------------
// Data Fetching: AI Evaluation History
// --------------------------------------------------------------------------
async function loadEvaluationHistory() {
  const tbody = document.getElementById("tbody-eval-history");
  try {
    const history = await apiFetch("/api/admin/analytics/evaluations?limit=15");
    if (!history.length) {
      tbody.innerHTML = `<tr><td colspan="9" class="loading">No evaluation run benchmarks found.</td></tr>`;
      return;
    }
    tbody.innerHTML = history
      .map(
        (h) => `
        <tr>
          <td><code>${h.run_id}</code></td>
          <td>${h.timestamp}</td>
          <td>${h.total_cases} cases</td>
          <td>${h.recall_1}%</td>
          <td><b>${h.recall_3}%</b></td>
          <td><b style="color:var(--primary)">${h.recall_5}%</b></td>
          <td>${h.answerability_acc}%</td>
          <td><span class="panel-badge success">${h.groundedness}%</span></td>
          <td><b style="color:${h.hallucinations === 0 ? 'var(--primary)' : 'var(--accent-red)'}">${h.hallucinations}</b></td>
        </tr>
      `
      )
      .join("");
  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="9" class="loading">Failed to load evaluation benchmarks.</td></tr>`;
  }
}

// --------------------------------------------------------------------------
// Data Fetching: System Health
// --------------------------------------------------------------------------
async function loadSystemHealth() {
  try {
    const health = await apiFetch("/api/admin/analytics/health");
    updateHealthBadge("status-db", health.database);
    updateHealthBadge("status-qdrant", health.qdrant);
    updateHealthBadge("status-groq", health.groq_api);
    document.getElementById("header-system-status").textContent = health.overall.toUpperCase();
  } catch (err) {
    console.error("Failed to fetch health status:", err);
  }
}

function updateHealthBadge(elemId, status) {
  const elem = document.getElementById(elemId);
  if (!elem) return;
  elem.textContent = status.toUpperCase();
  elem.className = `health-badge ${status === "healthy" || status === "operational" ? "healthy" : "degraded"}`;
}

// --------------------------------------------------------------------------
// Modals & User Action Handlers
// --------------------------------------------------------------------------
function openCreateDocForGap(query) {
  document.getElementById("nav-knowledge").click();
  document.getElementById("doc-title").value = `Policy Resolution: ${query}`;
  document.getElementById("doc-content").value = `Approved SACCO Policy regarding: "${query}".\n\n1. Details:\n2. Fees / Requirements:\n3. Effective Date:\n`;
  document.getElementById("modal-doc").classList.remove("hidden");
}

let activeEscalationId = null;

function openEscalationModal(id, query, currentStatus, currentPriority) {
  activeEscalationId = id;
  document.getElementById("modal-esc-id").textContent = id;
  document.getElementById("modal-esc-query").textContent = query;
  document.getElementById("modal-esc-status").value = currentStatus;
  document.getElementById("modal-esc-priority").value = currentPriority;
  document.getElementById("modal-esc").classList.remove("hidden");
}

function setupModals() {
  // Policy document modal
  document.getElementById("btn-open-doc-modal").addEventListener("click", () => {
    document.getElementById("form-doc").reset();
    document.getElementById("modal-doc").classList.remove("hidden");
  });
  document.getElementById("btn-create-gap-policy").addEventListener("click", () => {
    document.getElementById("form-doc").reset();
    document.getElementById("modal-doc").classList.remove("hidden");
  });
  document.getElementById("btn-close-modal").addEventListener("click", () => {
    document.getElementById("modal-doc").classList.add("hidden");
  });
  document.getElementById("btn-cancel-modal").addEventListener("click", () => {
    document.getElementById("modal-doc").classList.add("hidden");
  });

  document.getElementById("form-doc").addEventListener("submit", async (e) => {
    e.preventDefault();
    const title = document.getElementById("doc-title").value.trim();
    const category = document.getElementById("doc-category").value;
    const content = document.getElementById("doc-content").value.trim();
    const effectiveDate = document.getElementById("doc-effective-date").value || null;

    try {
      await apiFetch("/api/admin/knowledge", {
        method: "POST",
        body: JSON.stringify({ title, category, content, effective_date: effectiveDate }),
      });
      document.getElementById("modal-doc").classList.add("hidden");
      loadKnowledgeDocs();
      alert("Policy document draft created! You can now click 'Approve & Ingest' to make it active in RAG.");
    } catch (err) {
      alert(`Failed to save draft: ${err.message}`);
    }
  });

  // Escalations modal
  document.getElementById("btn-close-esc-modal").addEventListener("click", () => {
    document.getElementById("modal-esc").classList.add("hidden");
  });
  document.getElementById("btn-cancel-esc-modal").addEventListener("click", () => {
    document.getElementById("modal-esc").classList.add("hidden");
  });

  document.getElementById("form-esc").addEventListener("submit", async (e) => {
    e.preventDefault();
    if (!activeEscalationId) return;
    const newStatus = document.getElementById("modal-esc-status").value;
    const newPriority = document.getElementById("modal-esc-priority").value;
    const notes = document.getElementById("modal-esc-notes").value.trim();

    try {
      await apiFetch(`/api/admin/escalations/${activeEscalationId}`, {
        method: "PATCH",
        body: JSON.stringify({ status: newStatus, priority: newPriority, notes: notes || null }),
      });
      document.getElementById("modal-esc").classList.add("hidden");
      loadEscalations();
      loadDashboardData();
    } catch (err) {
      alert(`Failed to update ticket: ${err.message}`);
    }
  });

  // Escalation filter change
  document.getElementById("filter-escalation-status").addEventListener("change", () => {
    loadEscalations();
  });

  // Health refresh
  document.getElementById("btn-refresh-health").addEventListener("click", () => {
    loadSystemHealth();
  });

  // Export CSV
  document.getElementById("btn-export-csv").addEventListener("click", async () => {
    try {
      const res = await fetch(`${API_BASE}/api/admin/reports/export`, {
        headers: { Authorization: `Bearer ${authToken}` },
      });
      if (!res.ok) throw new Error("Failed to export report");
      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `sacco_ai_report_${new Date().toISOString().slice(0, 10)}.csv`;
      document.body.appendChild(a);
      a.click();
      a.remove();
    } catch (err) {
      alert(`Export failed: ${err.message}`);
    }
  });
}

function escapeHtml(str) {
  if (!str) return "";
  return str.replace(/'/g, "\\'").replace(/"/g, "&quot;");
}

// --------------------------------------------------------------------------
// Initialization
// --------------------------------------------------------------------------
document.addEventListener("DOMContentLoaded", () => {
  setupNavigation();
  setupModals();

  // Login form handler
  document.getElementById("login-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const u = document.getElementById("login-username").value.trim();
    const p = document.getElementById("login-password").value.trim();
    const errBox = document.getElementById("login-error");
    errBox.classList.add("hidden");

    try {
      const data = await apiFetch("/api/admin/auth/login", {
        method: "POST",
        body: JSON.stringify({ username: u, password: p }),
      });
      authToken = data.access_token;
      localStorage.setItem("sacco_admin_token", authToken);
      await checkAuth();
    } catch (err) {
      errBox.textContent = err.message || "Invalid staff login credentials";
      errBox.classList.remove("hidden");
    }
  });

  document.getElementById("btn-logout").addEventListener("click", handleLogout);

  checkAuth();
});
