const serverList = document.querySelector("#server-list");
const errorState = document.querySelector("#error-state");
const refreshButton = document.querySelector("#refresh-button");

function makeElement(tag, className, text) {
  const element = document.createElement(tag);
  if (className) element.className = className;
  if (text !== undefined) element.textContent = text;
  return element;
}

function formatTime(value) {
  if (!value) return "No calls yet";
  return new Intl.DateTimeFormat(undefined, {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  }).format(new Date(value));
}

function renderServer(server) {
  const row = makeElement("article", "server-row");
  const main = makeElement("div", "server-main");
  const identity = makeElement("div", "server-identity");
  const name = makeElement("div", "server-name");
  const symbol = makeElement("span", "server-symbol", server.name.slice(0, 1).toUpperCase());
  symbol.setAttribute("aria-hidden", "true");
  name.append(symbol, makeElement("span", "", server.name));
  const credentialsReady = server.env.every((item) => item.configured);
  const state = makeElement(
    "span",
    `server-state ${credentialsReady ? "ready" : "missing"}`,
    credentialsReady ? "Environment ready" : "Missing environment",
  );
  identity.append(name, state);

  const commandBlock = makeElement("div", "config-block");
  commandBlock.append(makeElement("span", "metric-label", "LAUNCH COMMAND"));
  commandBlock.append(makeElement("code", "command", [server.command, ...server.args].join(" ")));

  const envBlock = makeElement("div", "config-block");
  envBlock.append(makeElement("span", "metric-label", "ENVIRONMENT"));
  const envList = makeElement("div", "env-list");
  if (server.env.length) {
    for (const item of server.env) {
      envList.append(makeElement("span", `env-key ${item.configured ? "configured" : ""}`, item.name));
    }
  } else {
    envList.append(makeElement("span", "empty-env", "No variables required"));
  }
  envBlock.append(envList);

  const statsBlock = makeElement("div", "stats-block");
  const stats = server.stats;
  const statValues = [
    ["CALLS", stats.calls],
    ["SUCCESS / FAIL", `${stats.successes} / ${stats.failures}`],
    ["AVG LATENCY", stats.average_latency_ms === null ? "--" : `${stats.average_latency_ms} ms`],
  ];
  for (const [label, value] of statValues) {
    const stat = makeElement("div", "stat");
    stat.append(makeElement("span", "metric-label", label));
    stat.append(makeElement("strong", "", String(value)));
    statsBlock.append(stat);
  }
  const track = makeElement("div", "activity-track");
  track.setAttribute("role", "img");
  track.setAttribute("aria-label", `${stats.successes} successful calls, ${stats.failures} failed calls`);
  const total = Math.max(stats.successes + stats.failures, 1);
  const successBar = makeElement("span", "activity-success");
  successBar.style.width = `${(stats.successes / total) * 100}%`;
  const failureBar = makeElement("span", "activity-failure");
  failureBar.style.width = `${(stats.failures / total) * 100}%`;
  track.append(successBar, failureBar);
  statsBlock.append(track, makeElement("span", "call-time", `LAST CALL  ${formatTime(stats.last_call_at)}`));

  main.append(identity, commandBlock, envBlock, statsBlock);
  row.append(main);
  return row;
}

function renderDashboard(data) {
  document.querySelector("#server-total").textContent = data.totals.servers;
  document.querySelector("#call-total").textContent = data.totals.calls;
  document.querySelector("#failure-total").textContent = data.totals.failures;
  document.querySelector("#server-count").textContent = `${data.totals.servers} ${data.totals.servers === 1 ? "SERVER" : "SERVERS"}`;
  document.querySelector("#updated-at").textContent = formatTime(data.generated_at);

  serverList.replaceChildren();
  if (!data.servers.length) {
    serverList.append(makeElement("div", "empty-state", "No managed servers are configured."));
    return;
  }
  for (const server of data.servers) serverList.append(renderServer(server));
}

async function refreshDashboard() {
  refreshButton.classList.add("is-loading");
  errorState.hidden = true;
  try {
    const response = await fetch("/api/dashboard", { cache: "no-store" });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || `Request failed (${response.status})`);
    renderDashboard(data);
  } catch (error) {
    errorState.textContent = `Dashboard data unavailable: ${error.message}`;
    errorState.hidden = false;
  } finally {
    refreshButton.classList.remove("is-loading");
  }
}

refreshButton.addEventListener("click", refreshDashboard);
refreshDashboard();
window.setInterval(refreshDashboard, 5000);