(() => {
  "use strict";

  let operatorToken = "";
  let runs = [];
  let selectedRunId = "";
  let selectedTab = "summary";
  let detail = null;
  let context = null;
  let approvals = null;
  let policy = null;

  const elements = {
    tokenForm: document.querySelector("#token-form"),
    tokenInput: document.querySelector("#operator-token"),
    refreshRuns: document.querySelector("#refresh-runs"),
    runList: document.querySelector("#run-list"),
    runListStatus: document.querySelector("#run-list-status"),
    selectedRun: document.querySelector("#selected-run"),
    detailStatus: document.querySelector("#detail-status"),
    detailOutput: document.querySelector("#detail-output"),
    tabs: Array.from(document.querySelectorAll(".tab")),
  };
  const policyProfile = document.body.dataset.policyProfile || "default";

  elements.tokenForm.addEventListener("submit", (event) => {
    event.preventDefault();
    operatorToken = elements.tokenInput.value.trim();
    loadRuns();
  });
  elements.refreshRuns.addEventListener("click", () => loadRuns());
  elements.tabs.forEach((tab) => {
    tab.addEventListener("click", () => {
      selectedTab = tab.dataset.tab;
      renderTabs();
      renderDetail();
    });
  });

  function headers() {
    return {"X-Agent-Harness-Operator-Token": operatorToken};
  }

  async function api(path) {
    const response = await fetch(path, {headers: headers()});
    const payload = await response.json();
    if (!response.ok) {
      throw new Error(payload.detail || `Request failed: ${response.status}`);
    }
    return payload;
  }

  async function loadRuns() {
    if (!operatorToken) {
      setStatus(elements.runListStatus, "Enter the generated token.", true);
      return;
    }
    setStatus(elements.runListStatus, "Loading runs.", false);
    try {
      const payload = await api("/api/v1/runs");
      runs = payload.runs || [];
      renderRuns();
      setStatus(elements.runListStatus, `${runs.length} run(s) available.`, false);
    } catch (error) {
      setStatus(elements.runListStatus, error.message, true);
    }
  }

  async function openRun(runId) {
    selectedRunId = runId;
    detail = null;
    context = null;
    approvals = null;
    policy = null;
    renderRuns();
    elements.selectedRun.textContent = runId;
    setStatus(elements.detailStatus, "Loading run evidence.", false);
    try {
      detail = await api(`/api/v1/runs/${encodeURIComponent(runId)}`);
      context = await api(`/api/v1/runs/${encodeURIComponent(runId)}/context`);
      approvals = await api(`/api/v1/runs/${encodeURIComponent(runId)}/approvals`);
      policy = await api(`/api/v1/policy/${encodeURIComponent(policyProfile)}`);
      setStatus(elements.detailStatus, "Run evidence loaded.", false);
      renderDetail();
    } catch (error) {
      setStatus(elements.detailStatus, error.message, true);
      renderJson({error: error.message});
    }
  }

  function renderRuns() {
    elements.runList.textContent = "";
    runs.forEach((run) => {
      const item = document.createElement("li");
      const button = document.createElement("button");
      button.type = "button";
      if (run.run_id === selectedRunId) {
        button.classList.add("active");
      }
      button.addEventListener("click", () => openRun(run.run_id));
      const title = document.createElement("span");
      title.className = "run-title";
      title.textContent = run.run_id;
      const meta = document.createElement("span");
      meta.className = "run-meta";
      meta.textContent = `${run.status || "unknown"} - ${run.task_id || "unknown task"}`;
      button.append(title, meta);
      item.append(button);
      elements.runList.append(item);
    });
  }

  function renderTabs() {
    elements.tabs.forEach((tab) => {
      tab.classList.toggle("active", tab.dataset.tab === selectedTab);
    });
  }

  function renderDetail() {
    if (!detail) {
      renderJson({});
      return;
    }
    const views = {
      summary: detail.summary,
      timeline: detail.events || [],
      context: context || {},
      artifacts: {
        artifact_index: detail.artifact_index,
        artifact_statuses: detail.artifact_statuses || {},
      },
      provider: {
        provider: detail.provider || null,
        provider_input: detail.provider_input || null,
        provider_calls: detail.provider_calls || null,
      },
      security: {
        security_findings: detail.security_findings || null,
        policy: policy || null,
      },
      evals: {
        eval_results: detail.eval_results || null,
        retrieval_scorecards: detail.retrieval_scorecards || null,
      },
      approvals: approvals || {},
    };
    renderJson(views[selectedTab] || {});
  }

  function renderJson(value) {
    elements.detailOutput.textContent = JSON.stringify(value, null, 2);
  }

  function setStatus(element, message, isError) {
    element.textContent = message;
    element.classList.toggle("error", Boolean(isError));
  }
})();
