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

  async function api(path, options = {}) {
    const request = {
      ...options,
      headers: {...headers(), ...(options.headers || {})},
    };
    const response = await fetch(path, request);
    const payload = await response.json();
    if (!response.ok) {
      throw new Error(payload.detail || `Request failed: ${response.status}`);
    }
    return payload;
  }

  async function refreshSelectedRun() {
    if (!selectedRunId) {
      return;
    }
    await openRun(selectedRunId);
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
    };
    if (selectedTab === "approvals") {
      renderApprovals();
      return;
    }
    renderJson(views[selectedTab] || {});
  }

  function renderApprovals() {
    clearOutput();
    const approvalPayload = approvals || {approvals: [], counts: {}};
    const approvalRecords = approvalPayload.approvals || [];
    const view = document.createElement("div");
    view.className = "approval-view";
    view.append(renderApprovalSummary(approvalPayload));
    view.append(renderApprovalReviewFields());
    const list = document.createElement("div");
    list.className = "approval-list";
    if (approvalRecords.length === 0) {
      const empty = document.createElement("p");
      empty.className = "approval-note";
      empty.textContent = "No approvals recorded for this run.";
      list.append(empty);
    } else {
      approvalRecords.forEach((approval) => {
        list.append(renderApprovalItem(approval));
      });
    }
    view.append(list);
    elements.detailOutput.append(view);
  }

  function renderApprovalSummary(approvalPayload) {
    const counts = approvalPayload.counts || {};
    const summary = document.createElement("div");
    summary.className = "approval-summary";
    summary.append(
      approvalCount("Pending", counts.pending || 0),
      approvalCount("Approved", counts.approved || 0),
      approvalCount("Denied", counts.denied || 0),
    );
    return summary;
  }

  function approvalCount(label, count) {
    const item = document.createElement("span");
    item.textContent = `${label}: ${count}`;
    return item;
  }

  function renderApprovalReviewFields() {
    const fields = document.createElement("div");
    fields.className = "approval-review";
    const actorLabel = document.createElement("label");
    actorLabel.textContent = "Actor";
    const actorInput = document.createElement("input");
    actorInput.id = "approval-actor";
    actorInput.name = "approval-actor";
    actorInput.autocomplete = "off";
    actorInput.value = "operator-ui";
    actorLabel.append(actorInput);
    const reasonLabel = document.createElement("label");
    reasonLabel.textContent = "Reason";
    const reasonInput = document.createElement("textarea");
    reasonInput.id = "approval-reason";
    reasonInput.name = "approval-reason";
    reasonInput.autocomplete = "off";
    reasonLabel.append(reasonInput);
    fields.append(actorLabel, reasonLabel);
    return fields;
  }

  function renderApprovalItem(approval) {
    const actionId = String(approval.action_id || "");
    const status = String(approval.status || "unknown");
    const item = document.createElement("section");
    item.className = "approval-item";
    const header = document.createElement("div");
    header.className = "approval-item-header";
    const title = document.createElement("strong");
    title.textContent = actionId || approval.approval_id || "approval";
    const badge = document.createElement("span");
    badge.className = "approval-status";
    badge.textContent = status;
    header.append(title, badge);
    item.append(header);
    const meta = document.createElement("div");
    meta.className = "approval-meta";
    meta.append(
      approvalMeta("Tool", approval.tool_name),
      approvalMeta("Requested", approval.requested_at),
      approvalMeta("Decided", approval.decided_at || "not decided"),
      approvalMeta("Actor", approval.actor || "not recorded"),
    );
    item.append(meta);
    if (approval.reason) {
      const reason = document.createElement("div");
      reason.className = "approval-note";
      reason.textContent = `Reason: ${approval.reason}`;
      item.append(reason);
    }
    if (status === "pending" && actionId) {
      item.append(renderApprovalActions(actionId));
    } else {
      const decided = document.createElement("div");
      decided.className = "approval-note";
      decided.textContent = `Already decided as ${status}.`;
      item.append(decided);
    }
    const raw = document.createElement("pre");
    raw.className = "approval-raw";
    raw.textContent = JSON.stringify(approval, null, 2);
    item.append(raw);
    return item;
  }

  function approvalMeta(label, value) {
    const item = document.createElement("span");
    item.textContent = `${label}: ${value || "unknown"}`;
    return item;
  }

  function renderApprovalActions(actionId) {
    const actions = document.createElement("div");
    actions.className = "approval-actions";
    const approveButton = document.createElement("button");
    approveButton.type = "button";
    approveButton.textContent = "Approve";
    approveButton.addEventListener("click", () => {
      decideApproval(actionId, {decision: "approve"});
    });
    const denyButton = document.createElement("button");
    denyButton.type = "button";
    denyButton.textContent = "Deny";
    denyButton.addEventListener("click", () => {
      decideApproval(actionId, {decision: "deny"});
    });
    actions.append(approveButton, denyButton);
    return actions;
  }

  async function decideApproval(actionId, decisionRequest) {
    const actor = fieldValue("approval-actor");
    const reason = fieldValue("approval-reason");
    const body = {...decisionRequest};
    if (actor) {
      body.actor = actor;
    }
    if (reason) {
      body.reason = reason;
    }
    setStatus(elements.detailStatus, `Submitting ${body.decision} decision.`, false);
    try {
      await api(
        `/api/v1/runs/${encodeURIComponent(selectedRunId)}/approvals/${encodeURIComponent(actionId)}/decision`,
        {
          method: "POST",
          headers: {"Content-Type": "application/json"},
          body: JSON.stringify(body),
        },
      );
      await refreshSelectedRun();
      const status = body.decision === "approve" ? "approved" : "denied";
      setStatus(elements.detailStatus, `Approval ${actionId} ${status}.`, false);
    } catch (error) {
      setStatus(elements.detailStatus, error.message, true);
    }
  }

  function fieldValue(id) {
    const field = document.querySelector(`#${id}`);
    return field ? field.value.trim() : "";
  }

  function renderJson(value) {
    clearOutput();
    const pre = document.createElement("pre");
    pre.textContent = JSON.stringify(value, null, 2);
    elements.detailOutput.append(pre);
  }

  function clearOutput() {
    elements.detailOutput.replaceChildren();
  }

  function setStatus(element, message, isError) {
    element.textContent = message;
    element.classList.toggle("error", Boolean(isError));
  }
})();
