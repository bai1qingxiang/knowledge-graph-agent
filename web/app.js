const state = { candidateStatus: "pending", graph: null };

const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => [...document.querySelectorAll(selector)];

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(body.detail || `请求失败 (${response.status})`);
  return body;
}

function toast(message) {
  const element = $("#toast");
  element.textContent = message;
  element.classList.add("show");
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => element.classList.remove("show"), 3200);
}

function switchView(id) {
  $$(".tab").forEach((button) => button.classList.toggle("active", button.dataset.view === id));
  $$(".view").forEach((view) => view.classList.toggle("active", view.id === id));
  if (id === "review") loadCandidates();
  if (id === "graph") loadGraph();
}

async function refreshStats() {
  try {
    const data = await api("/stats");
    $("#stats").innerHTML = [
      ["实体", data.entities], ["正式关系", data.relations], ["证据", data.evidence],
      ["待审核", data.candidates_pending], ["已接受", data.candidates_accepted],
    ].map(([label, value]) => `<div class="stat"><strong>${value}</strong><span>${label}</span></div>`).join("");
    $(".health").classList.add("online");
    $("#healthText").textContent = "服务正常";
  } catch (error) {
    $("#healthText").textContent = "连接失败";
  }
}

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>'"]/g, (char) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;",
  })[char]);
}

async function loadCandidates() {
  const list = $("#candidateList");
  list.innerHTML = '<div class="empty">正在读取候选事实……</div>';
  try {
    const items = await api(`/candidates?status=${state.candidateStatus}&limit=500`);
    if (!items.length) {
      list.innerHTML = '<div class="panel empty">这个分类中暂时没有候选事实。</div>';
      return;
    }
    list.innerHTML = items.map((item) => `
      <article class="candidate" data-id="${item.id}">
        <div>
          <div class="triple">
            <span>${escapeHtml(item.source_name)} <small class="entity-type">${escapeHtml(item.source_type)}</small></span>
            <span class="predicate">${escapeHtml(item.predicate)}</span>
            <span>${escapeHtml(item.target_name)} <small class="entity-type">${escapeHtml(item.target_type)}</small></span>
          </div>
          <p class="quote">“${escapeHtml(item.evidence_quote)}”</p>
          <span class="meta">文档：${escapeHtml(item.document_id)} · 置信度：${Math.round(item.confidence * 100)}%</span>
        </div>
        ${item.status === "pending" ? `<div class="review-actions"><button class="accept" data-action="accept">接受</button><button class="reject" data-action="reject">拒绝</button></div>` : `<span class="badge">${item.status === "accepted" ? "已接受" : "已拒绝"}</span>`}
      </article>`).join("");
  } catch (error) {
    list.innerHTML = `<div class="panel empty">${escapeHtml(error.message)}</div>`;
  }
}

async function reviewCandidate(card, action) {
  card.querySelectorAll("button").forEach((button) => { button.disabled = true; });
  try {
    await api(`/candidates/${card.dataset.id}/${action}`, { method: "POST" });
    card.remove();
    toast(action === "accept" ? "候选事实已写入正式图谱" : "候选事实已拒绝");
    refreshStats();
    if (!$("#candidateList .candidate")) loadCandidates();
  } catch (error) {
    toast(error.message);
    card.querySelectorAll("button").forEach((button) => { button.disabled = false; });
  }
}

async function loadGraph() {
  try {
    state.graph = await api("/graph?limit=1000");
    drawGraph(state.graph);
  } catch (error) {
    toast(error.message);
  }
}

function drawGraph(data) {
  const svg = $("#graphCanvas");
  const empty = $("#graphEmpty");
  svg.innerHTML = "";
  if (!data.entities.length || !data.relations.length) {
    empty.classList.remove("hidden");
    return;
  }
  empty.classList.add("hidden");
  const width = svg.clientWidth || 800;
  const height = svg.clientHeight || 590;
  const cx = width / 2;
  const cy = height / 2;
  const radius = Math.max(120, Math.min(width, height) * .37);
  const nodes = data.entities.map((node, index) => ({
    ...node,
    x: cx + Math.cos((index / data.entities.length) * Math.PI * 2 - Math.PI / 2) * radius,
    y: cy + Math.sin((index / data.entities.length) * Math.PI * 2 - Math.PI / 2) * radius,
  }));
  const lookup = Object.fromEntries(nodes.map((node) => [node.id, node]));
  const ns = "http://www.w3.org/2000/svg";

  data.relations.forEach((relation) => {
    const source = lookup[relation.source_id];
    const target = lookup[relation.target_id];
    if (!source || !target) return;
    const line = document.createElementNS(ns, "line");
    line.setAttribute("x1", source.x); line.setAttribute("y1", source.y);
    line.setAttribute("x2", target.x); line.setAttribute("y2", target.y);
    line.setAttribute("class", "edge");
    line.addEventListener("click", () => showRelation(relation));
    svg.appendChild(line);
    const label = document.createElementNS(ns, "text");
    label.setAttribute("x", (source.x + target.x) / 2);
    label.setAttribute("y", (source.y + target.y) / 2 - 6);
    label.setAttribute("class", "edge-label");
    label.setAttribute("text-anchor", "middle");
    label.textContent = relation.predicate;
    svg.appendChild(label);
  });

  nodes.forEach((node) => {
    const group = document.createElementNS(ns, "g");
    group.setAttribute("class", "node");
    const circle = document.createElementNS(ns, "circle");
    circle.setAttribute("cx", node.x); circle.setAttribute("cy", node.y); circle.setAttribute("r", 28);
    const text = document.createElementNS(ns, "text");
    text.setAttribute("x", node.x); text.setAttribute("y", node.y + 44);
    text.textContent = node.name.length > 12 ? `${node.name.slice(0, 11)}…` : node.name;
    const type = document.createElementNS(ns, "text");
    type.setAttribute("x", node.x); type.setAttribute("y", node.y + 4);
    type.setAttribute("class", "edge-label"); type.setAttribute("text-anchor", "middle");
    type.textContent = node.type;
    group.append(circle, type, text); svg.appendChild(group);
  });
}

function showRelation(relation) {
  const evidence = relation.evidence.length
    ? relation.evidence.map((item) => `<div class="evidence">“${escapeHtml(item.quote)}”<br><small>${escapeHtml(item.document_id)}</small></div>`).join("")
    : '<div class="evidence">没有关联证据</div>';
  $("#relationDetail").innerHTML = `
    <h3>${escapeHtml(relation.source_name)}</h3>
    <span class="predicate">${escapeHtml(relation.predicate)}</span>
    <h3>${escapeHtml(relation.target_name)}</h3>
    <p class="meta">置信度：${Math.round(relation.confidence * 100)}%</p>
    ${evidence}`;
}

function renderAnswer(data) {
  const content = $("#answerContent");
  const citations = $("#answerCitations");
  content.className = "";
  content.innerHTML = `<div class="answer-text">${escapeHtml(data.answer)}</div>${data.insufficient ? '<span class="answer-status">证据不足</span>' : ''}`;
  citations.innerHTML = data.citations.map((citation, index) => `
    <article class="citation">
      <div class="citation-route">
        <span>证据 ${index + 1}</span>
        <span>${escapeHtml(citation.source_name)}</span>
        <span class="predicate">${escapeHtml(citation.predicate)}</span>
        <span>${escapeHtml(citation.target_name)}</span>
      </div>
      ${citation.evidence.map((item) => `<blockquote>“${escapeHtml(item.quote)}”<br><small>${escapeHtml(item.document_id)}</small></blockquote>`).join("")}
    </article>`).join("");
}

$$('.tab').forEach((button) => button.addEventListener("click", () => switchView(button.dataset.view)));
$$('.go-to').forEach((button) => button.addEventListener("click", () => switchView(button.dataset.target)));
$("#refreshGraph").addEventListener("click", loadGraph);
$("#candidateList").addEventListener("click", (event) => {
  const button = event.target.closest("button[data-action]");
  if (button) reviewCandidate(button.closest(".candidate"), button.dataset.action);
});
$("#statusFilter").addEventListener("click", (event) => {
  const button = event.target.closest("button[data-status]");
  if (!button) return;
  state.candidateStatus = button.dataset.status;
  $$("#statusFilter button").forEach((item) => item.classList.toggle("active", item === button));
  loadCandidates();
});
$("#fileInput").addEventListener("change", async (event) => {
  const file = event.target.files[0];
  if (!file) return;
  $("#documentText").value = await file.text();
  $("#documentId").value = file.name;
  $("#sourceUri").value = file.name;
  $("#fileHint").textContent = `${file.name} · ${(file.size / 1024).toFixed(1)} KB`;
});
$("#ingestForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  const button = $("#ingestButton");
  const result = $("#ingestResult");
  button.disabled = true; result.textContent = "DeepSeek 正在抽取，请稍候……";
  try {
    const data = await api("/documents/ingest", {
      method: "POST",
      body: JSON.stringify({
        document_id: $("#documentId").value.trim(),
        source_uri: $("#sourceUri").value.trim() || null,
        text: $("#documentText").value,
      }),
    });
    result.textContent = `完成：生成 ${data.candidates_created} 条候选，跳过 ${data.facts_skipped} 条`;
    toast("文档抽取完成，可以进入审核页");
    refreshStats();
  } catch (error) {
    result.textContent = `失败：${error.message}`;
  } finally {
    button.disabled = false;
  }
});
$$('.question-samples button').forEach((button) => button.addEventListener("click", () => {
  $("#questionInput").value = button.textContent;
  $("#questionInput").focus();
}));
$("#questionForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  const button = $("#askButton");
  const content = $("#answerContent");
  button.disabled = true;
  content.className = "answer-placeholder";
  content.textContent = "正在查阅已审核关系和原文证据……";
  $("#answerCitations").innerHTML = "";
  try {
    const data = await api("/questions/ask", {
      method: "POST",
      body: JSON.stringify({ question: $("#questionInput").value.trim() }),
    });
    renderAnswer(data);
  } catch (error) {
    content.className = "answer-placeholder";
    content.textContent = `回答失败：${error.message}`;
  } finally {
    button.disabled = false;
  }
});

refreshStats();
