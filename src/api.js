const apiUrl = (import.meta.env.VITE_API_URL || "http://127.0.0.1:8010/api").replace(/\/$/, "");
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

export function takeTicket(ticketId) {
  return request(`/tickets/${ticketId}/take/`, { method: "POST" });
}

export function resolveTicket(ticketId, resolutionNotes) {
  return request(`/tickets/${ticketId}/resolve/`, { method: "POST", body: { resolution_notes: resolutionNotes } });
}

export function validateTicket(ticketId, approved, comment = "") {
  return request(`/tickets/${ticketId}/validate/`, { method: "POST", body: { approved, comment } });
}
