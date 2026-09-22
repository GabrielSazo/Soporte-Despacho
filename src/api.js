const apiUrl = (import.meta.env.VITE_API_URL || "/api").replace(/\/$/, "");
const accessTokenKey = "sestel-access-token";
const refreshTokenKey = "sestel-refresh-token";

export class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

function getErrorMessage(payload, fallback) {
  if (typeof payload === "string") return payload;
  if (!payload || typeof payload !== "object") return fallback;
  if (payload.detail) return payload.detail;
  const firstError = Object.values(payload).flat().find(Boolean);
  return typeof firstError === "string" ? firstError : fallback;
}

function saveTokens({ access, refresh }) {
  if (access) sessionStorage.setItem(accessTokenKey, access);
  if (refresh) sessionStorage.setItem(refreshTokenKey, refresh);
}

function clearTokens() {
  sessionStorage.removeItem(accessTokenKey);
  sessionStorage.removeItem(refreshTokenKey);
}

export function hasActiveSession() {
  return Boolean(sessionStorage.getItem(accessTokenKey));
}

async function refreshAccessToken() {
  const refresh = sessionStorage.getItem(refreshTokenKey);
  if (!refresh) return false;

  try {
    const response = await fetch(`${apiUrl}/auth/token/refresh/`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh }),
    });
    const payload = await response.json();
    if (!response.ok) {
      clearTokens();
      return false;
    }
    saveTokens(payload);
    return true;
  } catch {
    return false;
  }
}

async function request(path, { body, headers = {}, method = "GET", retry = true, useAuth = true } = {}) {
  const requestHeaders = { ...headers };
  const isFormData = body instanceof FormData;
  const accessToken = sessionStorage.getItem(accessTokenKey);

  if (useAuth && accessToken) requestHeaders.Authorization = `Bearer ${accessToken}`;
  if (body && !isFormData) requestHeaders["Content-Type"] = "application/json";

  let response;
  try {
    response = await fetch(`${apiUrl}${path}`, {
      method,
      headers: requestHeaders,
      body: body ? (isFormData ? body : JSON.stringify(body)) : undefined,
    });
  } catch {
    throw new ApiError(`No se pudo conectar con la API en ${apiUrl}. Verifica que Django esté ejecutándose.`);
  }

  if (response.status === 401 && useAuth && retry && await refreshAccessToken()) {
    return request(path, { body, headers, method, retry: false, useAuth });
  }

  const contentType = response.headers.get("content-type") || "";
  const payload = contentType.includes("application/json") ? await response.json() : null;

  if (!response.ok) {
    if (response.status === 401) clearTokens();
    throw new ApiError(getErrorMessage(payload, "No fue posible completar la solicitud."), response.status);
  }

  return payload;
}

export async function signIn(email, password) {
  const payload = await request("/auth/token/", {
    method: "POST",
    body: { email, password },
    useAuth: false,
  });
  saveTokens(payload);
  return payload.user;
}

export function requestPasswordReset(email) {
  return request("/auth/password-reset/", {
    method: "POST",
    body: { email },
    useAuth: false,
  });
}

export function confirmPasswordReset({ email, uid, token, newPassword }) {
  return request("/auth/password-reset/confirm/", {
    method: "POST",
    body: { email, uid, token, new_password: newPassword },
    useAuth: false,
  });
}

// Compatibilidad: restablecimiento directo (uso administrativo)
export function resetPassword(email, newPassword) {
  return request("/auth/password-reset/", {
    method: "POST",
    body: { email, new_password: newPassword },
    useAuth: false,
  });
}

export async function signOut() {
  const refresh = sessionStorage.getItem(refreshTokenKey);
  try {
    if (refresh) await request("/auth/logout/", { method: "POST", body: { refresh } });
  } finally {
    clearTokens();
  }
}

export function getCurrentUser() {
  return request("/auth/me/");
}

export function updateMyTeams(teams, managedGroups) {
  const body = {};
  if (teams) body.teams = teams;
  if (managedGroups) body.managed_groups = managedGroups;
  return request("/auth/me/", { method: "PATCH", body });
}

export function getTickets() {
  return request("/tickets/");
}

export function getTicket(ticketId) {
  return request(`/tickets/${ticketId}/`);
}

export function getDashboard() {
  return request("/dashboard/");
}

export function getUsers() {
  return request("/users/");
}

export function getTeams() {
  return request("/teams/");
}

export function createTeam(team) {
  return request("/teams/", { method: "POST", body: team });
}

export function updateTeam(teamId, team) {
  return request(`/teams/${teamId}/`, { method: "PATCH", body: team });
}

export function getGroups() {
  return request("/groups/");
}

export function createGroup(group) {
  return request("/groups/", { method: "POST", body: group });
}

export function updateGroup(groupId, group) {
  return request(`/groups/${groupId}/`, { method: "PATCH", body: group });
}

export function createUser(user) {
  return request("/users/", { method: "POST", body: user });
}

export function updateUser(userId, user) {
  return request(`/users/${userId}/`, { method: "PATCH", body: user });
}

export function createTicket(ticket) {
  return request("/tickets/", { method: "POST", body: ticket });
}

export function uploadAttachment(ticketId, file) {
  const form = new FormData();
  form.append("file", file);
  return request(`/tickets/${ticketId}/attachments/`, { method: "POST", body: form });
}

export function analyzeAttachment(ticketId, attachmentId, prompt = "") {
  return request(`/tickets/${ticketId}/analizar-imagen/`, { method: "POST", body: { attachment_id: attachmentId, prompt } });
}

export function reviewTicket(ticketId) {
  return request(`/tickets/${ticketId}/revisar/`, { method: "POST" });
}

export function takeTicket(ticketId) {
  return request(`/tickets/${ticketId}/take/`, { method: "POST" });
}

export function releaseTicket(ticketId) {
  return request(`/tickets/${ticketId}/release/`, { method: "POST" });
}

export function resolveTicket(ticketId, resolutionNotes) {
  return request(`/tickets/${ticketId}/resolve/`, { method: "POST", body: { resolution_notes: resolutionNotes } });
}

export function validateTicket(ticketId, approved, comment = "") {
  return request(`/tickets/${ticketId}/validate/`, { method: "POST", body: { approved, comment } });
}

export function reassignTicket(ticketId, userId) {
  return request(`/tickets/${ticketId}/reassign/`, { method: "POST", body: { user_id: userId } });
}

export function getRequestTypes(params = {}) {
  const qs = new URLSearchParams(params).toString();
  return request(`/request-types/${qs ? `?${qs}` : ""}`);
}

export function createRequestType(data) {
  return request("/request-types/", { method: "POST", body: data });
}

export function updateRequestType(id, data) {
  return request(`/request-types/${id}/`, { method: "PATCH", body: data });
}

export function checkOpenTicket({ identificador = "", contrato = "", numero_ot = "" } = {}) {
  const params = { abierto: "1" };
  if (identificador) params.identificador = identificador;
  if (contrato) params.contrato = contrato;
  if (numero_ot) params.numero_ot = numero_ot;
  const qs = new URLSearchParams(params).toString();
  return request(`/tickets/?${qs}`);
}

export function escalateTicket(ticketId, { area_id, motivo, contrato = "", numero_ot = "", instrucciones = "" }) {
  return request(`/tickets/${ticketId}/escalar/`, { method: "POST", body: { area_id, motivo, contrato, numero_ot, instrucciones } });
}

export function deescalateTicket(ticketId) {
  return request(`/tickets/${ticketId}/desescalar/`, { method: "POST" });
}

export function instructTicket(ticketId, instrucciones) {
  return request(`/tickets/${ticketId}/instruir/`, { method: "POST", body: { instrucciones } });
}

export function getEscalationAreas() {
  return request("/escalation-areas/");
}

export function createEscalationArea(data) {
  return request("/escalation-areas/", { method: "POST", body: data });
}

export function updateEscalationArea(id, data) {
  return request(`/escalation-areas/${id}/`, { method: "PATCH", body: data });
}

export function getReportsSummary(params = {}) {
  const cleaned = Object.fromEntries(Object.entries(params).filter(([, v]) => v));
  const qs = new URLSearchParams(cleaned).toString();
  return request(`/reports/summary/${qs ? `?${qs}` : ""}`);
}

export async function downloadReportsCsv(params = {}) {
  const cleaned = Object.fromEntries(Object.entries(params).filter(([, v]) => v));
  const qs = new URLSearchParams(cleaned).toString();
  const base = (import.meta.env.VITE_API_URL || "/api").replace(/\/$/, "");
  const token = sessionStorage.getItem("sestel-access-token");
  const response = await fetch(`${base}/reports/export/${qs ? `?${qs}` : ""}`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!response.ok) throw new Error("No fue posible descargar el reporte.");
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "reporte_actividades.csv";
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}
