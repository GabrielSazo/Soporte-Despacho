import React, { useEffect, useState } from "react";
import {
  createGroup as createGroupRequest,
  createTeam as createTeamRequest,
  createTicket as createTicketRequest,
  createUser as createUserRequest,
  getCurrentUser,
  createRequestType,
  getDashboard,
  getGroups,
  getRequestTypes,
  getTicket,
  getTeams,
  getTickets,
  getUsers,
  updateMyTeams,
  confirmPasswordReset,
  hasActiveSession,
  requestPasswordReset,
  resetPassword,
  resolveTicket as resolveTicketRequest,
  releaseTicket as releaseTicketRequest,
  signIn,
  signOut,
  takeTicket as takeTicketRequest,
  checkOpenTicket,
  updateGroup as updateGroupRequest,
  updateRequestType,
  updateTeam as updateTeamRequest,
  updateUser as updateUserRequest,
  uploadAttachment,
  reassignTicket as reassignTicketRequest,
  validateTicket as validateTicketRequest,
} from "./api";
import { Icon } from "./icons";

const navigation = [
  { label: "Resumen", icon: "dashboard" },
  { label: "Tickets", icon: "ticket", badge: "12" },
  { label: "Validaciones", icon: "checkCircle", badge: "3" },
  { label: "Mi grupo", icon: "users" },
  { label: "Informes", icon: "chart" },
];

const statusClass = {
  Abierto: "status-open",
  Asignado: "status-assigned",
  "En proceso": "status-progress",
  Validación: "status-validation",
  Cerrado: "status-closed",
  Escalado: "status-escalated",
};

const priorityClass = {
  Crítica: "priority-critical",
  Alta: "priority-high",
  Media: "priority-medium",
  Baja: "priority-low",
};

const roleLabels = {
  DESPACHADOR: "Despachadora",
  SOPORTE: "Agente de soporte",
  SUPERVISOR: "Supervisor",
  ADMIN: "Administradora",
};

function readStoredSession() {
  try {
    if (!hasActiveSession()) return null;
    const savedSession = window.sessionStorage.getItem("sestel-user");
    return savedSession ? JSON.parse(savedSession) : null;
  } catch {
    return null;
  }
}

function initials(name = "") {
  return name.split(" ").filter(Boolean).slice(0, 2).map((part) => part[0]).join("").toUpperCase() || "US";
}

function avatarClass(name = "") {
  if (name.includes("Andrea")) return "avatar-andrea";
  if (name.includes("Mario")) return "avatar-mario";
  if (name.includes("Carla")) return "avatar-carla";
  return "";
}

function formatRelativeDate(value) {
  const date = new Date(value);
  const seconds = Math.max(0, Math.floor((Date.now() - date.getTime()) / 1000));
  if (seconds < 60) return "Ahora";
  if (seconds < 3600) return `Hace ${Math.floor(seconds / 60)} min`;
  if (seconds < 86400) return `Hace ${Math.floor(seconds / 3600)} h`;
  return `Hace ${Math.floor(seconds / 86400)} d`;
}

function formatRemaining(seconds = 0) {
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  return `${String(hours).padStart(2, "0")}:${String(minutes).padStart(2, "0")}`;
}

function formatDateTime(value) {
  if (!value) return "Sin registro";
  return new Intl.DateTimeFormat("es-GT", { dateStyle: "medium", timeStyle: "short" }).format(new Date(value));
}

function mapUser(user) {
  const teams = user.teams || (user.team ? [user.team] : []);
  const firstTeam = teams[0];
  const groups = user.groups || (user.group ? [user.group] : []);
  const groupsLabel = teams.length ? [...new Set(teams.map((t) => t.group?.name).filter(Boolean))].join(", ") : groups.length ? groups.map((g) => g.name).join(", ") : user.group?.name || "Sin grupo";
  return {
    ...user,
    initials: initials(user.name),
    avatarClass: avatarClass(user.name),
    group: firstTeam?.group?.name || groups[0]?.name || user.group?.name || "Sin grupo",
    groupsLabel,
    roleLabel: roleLabels[user.role] || user.role,
    team: groupsLabel === "Sin grupo" ? "Vista global" : groupsLabel,
    teams,
    groups,
  };
}

function mapManagedUser(user) {
  const teams = user.teams_detail || user.teams || (user.team_detail ? [user.team_detail] : user.team ? [{ name: user.team_detail?.name, group: user.team_detail?.group }] : []);
  const teamIds = (user.teams || []).map(String);
  const mgroups = user.managed_groups_detail || user.managed_groups || [];
  let groupNames = teams.length ? [...new Set(teams.map((t) => t.group?.name || t.group_detail?.name).filter(Boolean))].join(", ") : user.team_detail?.group?.name || "Sin grupo";
  if (user.role === "SUPERVISOR" && mgroups.length) {
    groupNames = mgroups.map((g) => g.name).join(", ");

  }
  if (!groupNames || groupNames === "Sin grupo") {
    groupNames = "Sin grupo";
  }
  return {
    ...user,
    avatarClass: avatarClass(user.name),
    initials: initials(user.name),
    roleLabel: roleLabels[user.role] || user.role,
    teamId: teamIds[0] || user.team || "",
    teamIds,
    managedGroups: mgroups.map((g) => String(g.id)),
    teams,
    teamName: user.role === "SUPERVISOR" ? (mgroups.length ? `Supervisa: ${groupNames}` : groupNames) : groupNames,
    groupName: groupNames,
  };
}

function mapTicket(ticket) {
  const slaTone = {
    VENCIDO: "danger",
    ADVERTENCIA: "warning",
    EN_TIEMPO: "safe",
    CERRADO: "safe",
  };
  return {
    apiId: ticket.id,
    id: ticket.reference,
    title: ticket.title,
    category: ticket.category_label,
    priority: ticket.priority_label,
    priorityCode: ticket.priority,
    status: ticket.status_label,
    statusCode: ticket.status,
    team: ticket.assigned_team?.group?.name || ticket.assigned_team?.name || "Sin asignar",
    teamId: ticket.assigned_team?.id || null,
    groupCode: ticket.assigned_team?.group?.code || null,
    identificador: ticket.identificador || "",
    cliente: ticket.cliente_nombre || "",
    nodo: ticket.nodo || "",
    tipoSolicitud: ticket.tipo_solicitud_detail?.name || "",
    requester: ticket.creator?.name || "Sin asignar",
    creatorId: ticket.creator?.id || null,
    assigneeId: ticket.assignee?.id || null,
    created: formatRelativeDate(ticket.created_at),
    createdAt: ticket.created_at,
    sla: formatRemaining(ticket.sla?.remaining_seconds),
    slaTone: slaTone[ticket.sla?.state] || "safe",
    slaState: ticket.sla?.state,
    slaDueAt: ticket.sla_due_at,
    avatar: initials(ticket.creator?.name),
    description: ticket.description,
    resolutionNotes: ticket.resolution_notes,
    assignee: ticket.assignee?.name || "Sin asignar",
    originTeam: ticket.origin_team?.group?.name || ticket.origin_team?.name || "Sin asignar",
    attachments: ticket.attachments || [],
    events: ticket.events || [],
  };
}

function App() {
  const [activeView, setActiveView] = useState("Resumen");
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [theme, setTheme] = useState("light");
  const [brand] = useState("tigo");
  const [showNotifications, setShowNotifications] = useState(false);
  const [showUserMenu, setShowUserMenu] = useState(false);
  const [showGroupMenu, setShowGroupMenu] = useState(false);
  const [session, setSession] = useState(readStoredSession);
  const [tickets, setTickets] = useState([]);
  const [dashboard, setDashboard] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [loadError, setLoadError] = useState("");
  const [newTicketOpen, setNewTicketOpen] = useState(false);
  const [ticketToResolve, setTicketToResolve] = useState(null);
  const [ticketDetail, setTicketDetail] = useState(null);
  const [isDetailLoading, setIsDetailLoading] = useState(false);
  const [users, setUsers] = useState([]);
  const [teams, setTeams] = useState([]);
  const [groups, setGroups] = useState([]);
  const [usersLoading, setUsersLoading] = useState(false);
  const [usersError, setUsersError] = useState("");
  const [userModal, setUserModal] = useState(null);
  const [teamModal, setTeamModal] = useState(null);
  const [groupModal, setGroupModal] = useState(null);
  const [requestTypeModal, setRequestTypeModal] = useState(null);
  const [requestTypes, setRequestTypes] = useState([]);
  const [passwordModal, setPasswordModal] = useState(null);
  const [showProfile, setShowProfile] = useState(false);
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState("Todos");
  const [toast, setToast] = useState("");

  useEffect(() => {
    if (!session) return;
    if (session.role === "SOPORTE") setFilter("Trabajables");
    else if (session.role === "DESPACHADOR") setFilter("Míos");
    else setFilter("Todos");
  }, [session?.id]);

  useEffect(() => {
    const closeOnEscape = (event) => {
      if (event.key === "Escape") {
        setSidebarOpen(false);
        setNewTicketOpen(false);
        setTicketToResolve(null);
        setTicketDetail(null);
        setUserModal(null);
        setTeamModal(null);
        setGroupModal(null);
        setPasswordModal(null);
        setShowProfile(false);
        setShowNotifications(false);
        setShowUserMenu(false);
        setShowGroupMenu(false);
      }
    };
    window.addEventListener("keydown", closeOnEscape);
    return () => window.removeEventListener("keydown", closeOnEscape);
  }, []);

  useEffect(() => {
    document.body.style.overflow = sidebarOpen || newTicketOpen || ticketToResolve || ticketDetail || userModal || teamModal || groupModal || passwordModal || showProfile ? "hidden" : "";
    return () => {
      document.body.style.overflow = "";
    };
  }, [sidebarOpen, newTicketOpen, ticketToResolve, ticketDetail, userModal, teamModal, groupModal, passwordModal, showProfile]);

  useEffect(() => {
    if (session) {
      refreshWorkspace();
      refreshTeams();
    }
  }, [session?.id]);

  useEffect(() => {
    if (!session) return;
    const token = sessionStorage.getItem("sestel-access-token");
    if (!token) return;
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const wsUrl = `${protocol}//${window.location.host}/ws/tickets/?token=${token}`;
    let ws;
    let closed = false;
    function connect() {
      ws = new WebSocket(wsUrl);
      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (data.type === "ticket_update" || data.type === "connected") {
            if (data.type === "ticket_update") refreshWorkspace(true);
          }
        } catch {
          if (event.data === "pong") return;
        }
      };
      ws.onclose = () => {
        if (!closed) setTimeout(connect, 5000);
      };
      ws.onerror = () => ws.close();
    }
    connect();
    const ping = setInterval(() => { if (ws && ws.readyState === WebSocket.OPEN) ws.send("ping"); }, 30000);
    return () => { closed = true; clearInterval(ping); if (ws) ws.close(); };
  }, [session?.id]);

  async function refreshTeams() {
    try {
      const [teamPayload, groupPayload] = await Promise.all([getTeams(), getGroups()]);
      setTeams(teamPayload.results || teamPayload);
      setGroups(groupPayload.results || groupPayload);
    } catch {}
  }

  useEffect(() => {
    if (session && ["ADMIN", "SUPERVISOR"].includes(session?.role) && activeView === "Usuarios") refreshUsers();
    if (session && activeView === "Mi grupo") refreshUsers();
  }, [activeView, session?.role]);


  function notify(message) {
    setToast(message);
    window.setTimeout(() => setToast(""), 3600);
  }

  async function refreshWorkspace(silent = false) {
    if (!silent) setIsLoading(true);
    setLoadError("");
    try {
      const [ticketPayload, dashboardPayload] = await Promise.all([getTickets(), getDashboard()]);
      setTickets((ticketPayload.results || ticketPayload).map(mapTicket));
      setDashboard(dashboardPayload);
    } catch (error) {
      if (error.status === 401) {
        sessionStorage.removeItem("sestel-user");
        setSession(null);
      } else {
        setLoadError(error.message || "No fue posible cargar los datos de operación.");
      }
    } finally {
      if (!silent) setIsLoading(false);
    }
  }

  async function refreshUsers() {
    setUsersLoading(true);
    setUsersError("");
    try {
      const [userPayload, teamPayload, groupPayload, rtPayload] = await Promise.all([getUsers(), getTeams(), getGroups(), getRequestTypes().catch(() => [])]);
      setUsers((userPayload.results || userPayload).map(mapManagedUser));
      setTeams(teamPayload.results || teamPayload);
      setGroups(groupPayload.results || groupPayload);
      setRequestTypes(rtPayload.results || rtPayload || []);
    } catch (error) {
      setUsersError(error.message || "No fue posible cargar los usuarios.");
    } finally {
      setUsersLoading(false);
    }
  }

  async function saveRequestType(form, existing) {
    const payload = { kind: form.kind, service: form.service, name: form.name.trim(), is_active: form.isActive };
    if (existing) await updateRequestType(existing.id, payload);
    else await createRequestType(payload);
    setRequestTypeModal(null);
    await refreshUsers();
    notify(existing ? "Tipo de solicitud actualizado." : "Tipo de solicitud creado.");
  }

  async function startSession({ email, password }) {
    const user = mapUser(await signIn(email, password));
    sessionStorage.setItem("sestel-user", JSON.stringify(user));
    sessionStorage.removeItem("sestel-session");
    setSession(user);
    notify(`Sesión iniciada como ${user.roleLabel.toLowerCase()}.`);
  }

  async function endSession() {
    await signOut().catch(() => undefined);
    sessionStorage.removeItem("sestel-user");
    sessionStorage.removeItem("sestel-session");
    setSession(null);
    setTickets([]);
    setDashboard(null);
    setSidebarOpen(false);
    setNewTicketOpen(false);
    setToast("");
  }

  function changeView(view) {
    setActiveView(view);
    setSidebarOpen(false);
  }

  function replaceTicket(ticket) {
    const mappedTicket = mapTicket(ticket);
    setTickets((currentTickets) => currentTickets.map((item) => (item.apiId === mappedTicket.apiId ? mappedTicket : item)));
  }

  async function openTicketDetail(ticket) {
    setTicketDetail(ticket);
    setIsDetailLoading(true);
    try {
      if (!users.length) await refreshUsers().catch(() => undefined);
      const detail = await getTicket(ticket.apiId);
      setTicketDetail(mapTicket(detail));
      replaceTicket(detail);
    } catch (error) {
      notify(error.message || `No fue posible cargar ${ticket.id}.`);
      setTicketDetail(null);
    } finally {
      setIsDetailLoading(false);
    }
  }

  async function createTicket(form) {
    const ticket = await createTicketRequest({
      title: form.title,
      description: form.description,
      category: form.category,
      priority: form.priority,
      identificador: form.identificador,
      cliente_nombre: form.cliente_nombre || form.cliente,
      nodo: form.nodo,
      tipo_solicitud: form.tipo_solicitud,
    });
    if (form.attachment) {
      const files = Array.isArray(form.attachment) ? form.attachment : [form.attachment];
      for (const f of files.slice(0, 5)) await uploadAttachment(ticket.id, f);
    }
    setNewTicketOpen(false);
    setActiveView("Tickets");
    await refreshWorkspace(true);
    notify(`${ticket.reference} fue enviado a Soporte Despacho.`);
  }

  async function validateTicket(ticket, accepted, comment = "") {
    const updatedTicket = await validateTicketRequest(ticket.apiId, accepted, comment);
    replaceTicket(updatedTicket);
    if (ticketDetail && ticketDetail.apiId === ticket.apiId) {
      const detail = await getTicket(ticket.apiId);
      setTicketDetail(mapTicket(detail));
    }
    await refreshWorkspace(true);
    notify(accepted ? `${ticket.id} se cerró correctamente.` : `${ticket.id} volvió a Soporte para retrabajo.`);
  }

  async function takeTicket(ticket) {
    const updatedTicket = await takeTicketRequest(ticket.apiId);
    replaceTicket(updatedTicket);
    await refreshWorkspace(true);
    notify(`${ticket.id} quedó asignado a tu atención.`);
  }

  async function resolveTicket(ticket, resolutionNotes) {
    const updatedTicket = await resolveTicketRequest(ticket.apiId, resolutionNotes);
    replaceTicket(updatedTicket);
    setTicketToResolve(null);
    await refreshWorkspace(true);
    notify(`${ticket.id} fue enviado al despachador para validación.`);
  }

  async function releaseTicket(ticket) {
    const updated = await releaseTicketRequest(ticket.apiId);
    const mapped = mapTicket(updated);
    setTicketDetail(mapped);
    replaceTicket(updated);
    await refreshWorkspace(true);
    notify(`${ticket.id} liberado a la bandeja del grupo.`);
  }

  async function reassignTicket(ticket, userId) {
    const updated = await reassignTicketRequest(ticket.apiId, userId);
    const mapped = mapTicket(updated);
    setTicketDetail(mapped);
    replaceTicket(updated);
    await refreshWorkspace(true);
    notify(`${ticket.id} reasignado a ${mapped.team}.`);
  }

  async function saveUser(form, existingUser) {
    const payload = {
      username: form.email.trim().toLowerCase(),
      email: form.email.trim().toLowerCase(),
      first_name: form.firstName.trim(),
      last_name: form.lastName.trim(),
      role: form.role,
      teams: form.teams.map((id) => Number(id)),
      managed_groups: form.managedGroups ? form.managedGroups.map((id) => Number(id)) : [],
      is_active: form.isActive,
    };
    if (form.password) payload.password = form.password;

    const savedUser = existingUser
      ? await updateUserRequest(existingUser.id, payload)
      : await createUserRequest(payload);
    setUserModal(null);
    await refreshUsers();
    notify(existingUser ? `${savedUser.name} fue actualizado.` : `${savedUser.name} fue creado.`);
  }

  async function saveTeam(form, existingTeam) {
    const payload = {
      name: form.name.trim(),
      code: form.code.trim().toLowerCase().replace(/\s+/g, "-"),
      group: Number(form.group),
      is_active: form.isActive,
    };
    const saved = existingTeam ? await updateTeamRequest(existingTeam.id, payload) : await createTeamRequest(payload);
    setTeamModal(null);
    await refreshUsers();
    notify(existingTeam ? `Equipo ${saved.name} actualizado.` : `Equipo ${saved.name} creado.`);
  }

  async function saveGroup(form, existingGroup) {
    const payload = {
      name: form.name.trim(),
      code: form.code.trim().toLowerCase().replace(/\s+/g, "-"),
      is_active: form.isActive,
    };
    const saved = existingGroup ? await updateGroupRequest(existingGroup.id, payload) : await createGroupRequest(payload);
    setGroupModal(null);
    await refreshUsers();
    notify(existingGroup ? `Grupo ${saved.name} actualizado.` : `Grupo ${saved.name} creado.`);
  }

  async function resetUserPassword(user, newPassword) {
    await updateUserRequest(user.id, { password: newPassword });
    setPasswordModal(null);
    notify(`Contraseña de ${user.name} restablecida correctamente.`);
  }

  async function attachToTicket(ticket, file) {
    const uploaded = await uploadAttachment(ticket.apiId, file);
    const detail = await getTicket(ticket.apiId);
    const mapped = mapTicket(detail);
    setTicketDetail(mapped);
    replaceTicket(detail);
    notify(`Evidencia ${uploaded.original_name} adjuntada a ${ticket.id}.`);
    return mapped;
  }

  const openTickets = tickets.filter((ticket) => ticket.statusCode !== "CERRADO").length;
  const validationTickets = tickets.filter((ticket) => ticket.statusCode === "VALIDACION" && (session?.role === "DESPACHADOR" ? ticket.creatorId === session.id : true));
  const myValidationCount = tickets.filter((t) => t.statusCode === "VALIDACION" && t.creatorId === session?.id).length;
  const criticalTickets = tickets.filter((ticket) => ticket.priorityCode === "CRITICA").length;
  const statusMap = { "Todos": null, "Míos": null, "Trabajables": null, "Abierto": "ABIERTO", "Asignado": "ASIGNADO", "En proceso": "EN_PROCESO", "Validación": "VALIDACION" };
  const filteredTickets = tickets.filter((ticket) => {
    const searchable = `${ticket.id} ${ticket.title} ${ticket.team} ${ticket.requester} ${ticket.identificador} ${ticket.cliente} ${ticket.nodo} ${ticket.tipoSolicitud}`.toLowerCase();
    if (!searchable.includes(query.toLowerCase())) return false;
    if (filter === "Míos") return ticket.assigneeId === session?.id || ticket.creatorId === session?.id;
    if (filter === "Trabajables") return ["ABIERTO", "ASIGNADO"].includes(ticket.statusCode) && ticket.assigneeId !== session?.id;
    return !statusMap[filter] || ticket.statusCode === statusMap[filter];
  });
  const canCreateTickets = session && ["DESPACHADOR", "ADMIN", "SUPERVISOR"].includes(session.role);
  const visibleNavigation = session && ["ADMIN", "SUPERVISOR"].includes(session.role) ? [...navigation, { label: "Usuarios", icon: "users" }] : navigation;
  const myTickets = tickets.filter((t) => t.creatorId === session?.id);
  const myValidation = tickets.filter((t) => t.statusCode === "VALIDACION" && t.creatorId === session?.id);
  const trabajables = tickets.filter((t) => ["ABIERTO", "ASIGNADO"].includes(t.statusCode) && !t.assigneeId);
  const notifications = session?.role === "DESPACHADOR"
    ? [
        ...myValidation.slice(0, 3).map((t) => ({ key: `val-${t.id}`, type: "warning", title: `Validación pendiente: ${t.id}`, desc: t.title, time: t.created, ticket: t })),
        ...myTickets.filter((t) => t.slaTone === "danger").slice(0, 3).map((t) => ({ key: `sla-${t.id}`, type: "danger", title: `SLA vencido: ${t.id}`, desc: t.title, time: t.created, ticket: t })),
      ].slice(0, 5)
    : [
        ...trabajables.slice(0, 3).map((t) => ({ key: `new-${t.id}`, type: "info", title: `Nuevo en bandeja: ${t.id}`, desc: t.title, time: t.created, ticket: t })),
        ...trabajables.filter((t) => t.slaTone === "danger").slice(0, 2).map((t) => ({ key: `sla-${t.id}`, type: "danger", title: `SLA vencido: ${t.id}`, desc: t.title, time: t.created, ticket: t })),
        ...myValidation.slice(0, 2).map((t) => ({ key: `val-${t.id}`, type: "warning", title: `Validación pendiente: ${t.id}`, desc: t.title, time: t.created, ticket: t })),
      ].slice(0, 5);

  if (typeof window !== "undefined" && window.location.pathname === "/reset-password") {
    return <PasswordResetPage brand={brand} theme={theme} onToggleTheme={() => setTheme((currentTheme) => (currentTheme === "light" ? "dark" : "light"))} />;
  }

  if (!session) {
    return <LoginScreen brand={brand} onLogin={startSession} onToggleTheme={() => setTheme((currentTheme) => (currentTheme === "light" ? "dark" : "light"))} theme={theme} />;
  }

  return (
    <div className="app-shell" data-brand={brand} data-theme={theme}>
      <aside className={`sidebar ${sidebarOpen ? "is-open" : ""}`} aria-label="Navegación principal">
        <div className="sidebar-top">
          <a className="brand" href="#inicio" onClick={() => changeView("Resumen")}>
            <span className="brand-mark" aria-hidden="true"><span /><span /><span /></span>
            <span><strong>Soporte Despacho</strong><small>Tigo · Centro de control</small></span>
          </a>
          <button className="icon-button sidebar-close" type="button" aria-label="Cerrar menú" onClick={() => setSidebarOpen(false)}><Icon name="close" /></button>
        </div>
        <div style={{ position: "relative", margin: "0 4px 28px" }}>
          <button type="button" className="context-card" style={{ width: "100%", margin: 0, textAlign: "left", cursor: session.role === "SOPORTE" ? "pointer" : "default" }} onClick={() => { if (session.role === "SOPORTE") { setShowGroupMenu((v) => !v); setShowNotifications(false); setShowUserMenu(false); } }} aria-label="Grupos que atiendes" aria-expanded={showGroupMenu}>
            <span className="context-dot" /><div><span>{session.role === "SOPORTE" ? "Mis grupos" : "Grupo actual"}</span><strong>{session.team}</strong></div><Icon name="chevronDown" size={16} style={{ transform: showGroupMenu ? "rotate(180deg)" : "none", transition: "transform 150ms ease" }} />
          </button>
          {session.role === "SOPORTE" && showGroupMenu && <>
            <button className="dropdown-overlay" type="button" aria-label="Cerrar grupos" onClick={() => setShowGroupMenu(false)} />
            <div className="user-dropdown" role="menu" style={{ left: 0, right: 0, width: "100%" }}>
              <div className="user-dropdown-menu" style={{ maxHeight: "220px", overflowY: "auto" }}>
                {groups.map((g) => { const checked = session.teams?.some((t) => t.group?.id === g.id) || session.groups?.some((sg) => sg.id === g.id); return <label key={g.id} className="user-dropdown-item" style={{ cursor: "pointer" }}><input type="checkbox" checked={checked} onChange={async () => { const teamIds = teams.filter((t) => t.group === g.id || t.group_detail?.id === g.id).map((t) => t.id); const currentTeamIds = (session.teams || []).map((t) => t.id).filter(Boolean); const hasAll = teamIds.length > 0 && teamIds.every((id) => currentTeamIds.includes(id)); const newTeamIds = hasAll ? currentTeamIds.filter((id) => !teamIds.includes(id)) : [...new Set([...currentTeamIds, ...teamIds])]; if (!newTeamIds.length) { notify("Debes atender al menos un grupo."); return; } try { await updateMyTeams(newTeamIds, null); const fresh = await getCurrentUser(); const mapped = mapUser(fresh); setSession(mapped); sessionStorage.setItem("sestel-user", JSON.stringify(mapped)); notify(hasAll ? `Ya no atiendes ${g.name}` : `Ahora atiendes ${g.name}`); refreshWorkspace(true); } catch (e) { notify(e.message || "No se pudo actualizar"); } }} />{g.name}</label>; })}
              </div>
            </div>
          </>}
        </div>
        <nav className="main-nav">
          <p className="nav-caption">Operación</p>
          {visibleNavigation.map((item) => <button className={`nav-item ${activeView === item.label ? "active" : ""}`} key={item.label} onClick={() => changeView(item.label)} type="button"><Icon name={item.icon} size={19} /><span>{item.label}</span>{item.badge && <b>{item.label === "Tickets" ? openTickets : session.role !== "SOPORTE" ? validationTickets.length : 0}</b>}</button>)}
        </nav>
        <div className="sidebar-bottom">
          <button className="nav-item" type="button" onClick={() => ["ADMIN","SUPERVISOR"].includes(session.role) ? changeView("Usuarios") : setShowProfile(true)}><Icon name="settings" size={19} /><span>{["ADMIN","SUPERVISOR"].includes(session.role) ? "Gestionar usuarios" : "Mi perfil"}</span></button>
          <button className="nav-item logout-item" type="button" onClick={endSession}><Icon name="logout" size={19} /><span>Cerrar sesión</span></button>
        </div>
      </aside>
      {sidebarOpen && <button className="sidebar-overlay" type="button" aria-label="Cerrar menú" onClick={() => setSidebarOpen(false)} />}
      <main className="workspace">
        <header className="topbar">
          <button className="icon-button menu-toggle" type="button" aria-label="Abrir menú" onClick={() => setSidebarOpen(true)}><Icon name="menu" /></button>
          <div className="mobile-brand">Soporte Despacho</div>
          <label className="global-search"><Icon name="search" size={19} /><input type="search" value={query} onChange={(event) => setQuery(event.target.value)} onFocus={() => setActiveView("Tickets")} placeholder="Buscar ticket, técnico o grupo..." aria-label="Buscar tickets" /></label>
          <div className="topbar-actions">
            <button className="icon-button theme-button" type="button" aria-label={theme === "light" ? "Activar tema oscuro" : "Activar tema claro"} aria-pressed={theme === "dark"} onClick={() => setTheme((currentTheme) => (currentTheme === "light" ? "dark" : "light"))} title={theme === "light" ? "Cambiar a modo oscuro" : "Cambiar a modo claro"}><Icon name={theme === "light" ? "moon" : "sun"} size={19} /></button>
            <div className="notification-wrapper">
              <button className={`icon-button notification-button ${notifications.length ? "has-notifications" : ""}`} type="button" aria-label={`Notificaciones ${notifications.length ? `(${notifications.length} nuevas)` : ""}`} aria-expanded={showNotifications} onClick={() => { setShowNotifications((v) => !v); setShowUserMenu(false); if (!showNotifications) refreshWorkspace(true); }}><Icon name="bell" size={20} />{notifications.length > 0 && <span />}</button>
              {showNotifications && (
                <>
                  <button className="dropdown-overlay" type="button" aria-label="Cerrar notificaciones" onClick={() => setShowNotifications(false)} />
                  <div className="notification-dropdown" role="region" aria-label="Notificaciones">
                    <div className="notification-header"><strong>Notificaciones</strong><span>{notifications.length}</span></div>
                    <div className="notification-list">
                      {notifications.length ? notifications.map((n) => (
                        <button key={n.key} type="button" className="notification-item" onClick={() => { setShowNotifications(false); openTicketDetail(n.ticket); }}>
                          <span className={`notification-icon ${n.type}`}><Icon name={n.type === "danger" ? "alert" : n.type === "warning" ? "clock" : "ticket"} size={16} /></span>
                          <span className="notification-content"><strong>{n.title}</strong><p>{n.desc}</p><small>{n.time} · {n.ticket.team}</small></span>
                        </button>
                      )) : <div className="notification-empty"><Icon name="checkCircle" size={24} /><p>Todo al día</p><small>No hay alertas pendientes</small></div>}
                    </div>
                    <div className="notification-footer"><button type="button" className="text-button" onClick={() => { setShowNotifications(false); refreshWorkspace(); }}>Actualizar</button></div>
                  </div>
                </>
              )}
            </div>
            <div className="user-menu-wrapper">
              <button type="button" className="topbar-user" aria-label="Abrir menú de usuario" aria-expanded={showUserMenu} onClick={() => { setShowUserMenu((v) => !v); setShowNotifications(false); }}>
                <div className={`avatar ${session.avatarClass}`}>{session.initials}</div><div><strong>{session.name}</strong><span>{session.team}</span></div><Icon name="chevronDown" size={15} style={{ transform: showUserMenu ? "rotate(180deg)" : "none", transition: "transform 150ms ease" }} />
              </button>
              {showUserMenu && (
                <>
                  <button className="dropdown-overlay" type="button" aria-label="Cerrar menú de usuario" onClick={() => setShowUserMenu(false)} />
                  <div className="user-dropdown" role="menu">
                    <div className="user-dropdown-header">
                      <div className={`avatar ${session.avatarClass}`}>{session.initials}</div>
                      <div className="user-dropdown-info"><strong>{session.name}</strong><span>{session.roleLabel}</span><small>{session.email} · {session.team}</small></div>
                    </div>
                    <div className="user-dropdown-menu">
                      <button type="button" className="user-dropdown-item" role="menuitem" onClick={() => { setShowUserMenu(false); setShowProfile(true); }}><Icon name="users" size={16} /> Ver perfil</button>
                      <button type="button" className="user-dropdown-item danger" role="menuitem" onClick={() => { setShowUserMenu(false); endSession(); }}><Icon name="logout" size={16} /> Cerrar sesión</button>
                    </div>
                  </div>
                </>
              )}
            </div>
          </div>
        </header>
        <section className="page-content">
          {loadError && <ApiConnectionError message={loadError} onRetry={() => refreshWorkspace()} />}
          {isLoading ? <LoadingState /> : <>
            {activeView === "Resumen" && <Dashboard canCreate={canCreateTickets} criticalTickets={criticalTickets} dashboard={dashboard} onCreate={() => setNewTicketOpen(true)} onOpen={openTicketDetail} onShowTickets={() => setActiveView("Tickets")} tickets={tickets} validationTickets={validationTickets} />}
            {activeView === "Tickets" && <TicketsView canCreate={canCreateTickets} currentUser={session} filter={filter} filteredTickets={filteredTickets} onCreate={() => setNewTicketOpen(true)} onFilterChange={setFilter} onNotify={notify} onOpen={openTicketDetail} onResolve={setTicketToResolve} onTake={takeTicket} query={query} setQuery={setQuery} />}
            {activeView === "Validaciones" && <ValidationsView canValidate={session.role !== "SOPORTE"} tickets={validationTickets} onOpen={openTicketDetail} onValidate={validateTicket} />}
            {activeView === "Mi grupo" && <TeamView currentUser={session} onNotify={notify} tickets={tickets} users={users} />}
            {activeView === "Informes" && <ReportsView tickets={tickets} />}
            {activeView === "Usuarios" && ["ADMIN","SUPERVISOR"].includes(session.role) && <UsersView currentRole={session.role} error={usersError} groups={groups} loading={usersLoading} onCreate={() => setUserModal("new")} onCreateGroup={() => setGroupModal("new")} onCreateTeam={() => setTeamModal("new")} onCreateRequestType={() => setRequestTypeModal("new")} onEdit={setUserModal} onEditGroup={setGroupModal} onEditTeam={setTeamModal} onEditRequestType={setRequestTypeModal} onResetPassword={setPasswordModal} onRetry={refreshUsers} requestTypes={requestTypes} teams={teams} users={users} />}
          </>}
        </section>
      </main>
      {newTicketOpen && canCreateTickets && <NewTicketModal onClose={() => setNewTicketOpen(false)} onCreate={createTicket} onOpenTicket={async (id) => { setNewTicketOpen(false); const t = tickets.find((x) => x.apiId === id); if (t) openTicketDetail(t); }} session={session} />}
      {ticketToResolve && <ResolveTicketModal onClose={() => setTicketToResolve(null)} onResolve={resolveTicket} ticket={ticketToResolve} />}
      {ticketDetail && <TicketDetailModal currentUser={session} isLoading={isDetailLoading} onAttach={attachToTicket} onClose={() => setTicketDetail(null)} onReassign={reassignTicket} onResolve={(ticket) => { setTicketDetail(null); setTicketToResolve(ticket); }} onTake={async (ticket) => { const updated = await takeTicket(ticket); const detail = await getTicket(ticket.apiId); setTicketDetail(mapTicket(detail)); }} onRelease={releaseTicket} onValidate={async (ticket, accepted, comment) => { await validateTicket(ticket, accepted, comment); setTicketDetail(null); }} teams={teams} ticket={ticketDetail} users={users} />}
      {userModal && <UserFormModal onClose={() => setUserModal(null)} onSave={saveUser} teams={teams} groups={groups} user={userModal === "new" ? null : userModal} />}
      {teamModal && <TeamFormModal groups={groups} onClose={() => setTeamModal(null)} onSave={saveTeam} team={teamModal === "new" ? null : teamModal} />}
      {groupModal && <GroupFormModal onClose={() => setGroupModal(null)} onSave={saveGroup} group={groupModal === "new" ? null : groupModal} />}
      {requestTypeModal && <RequestTypeFormModal onClose={() => setRequestTypeModal(null)} onSave={saveRequestType} requestType={requestTypeModal === "new" ? null : requestTypeModal} />}
      {passwordModal && <PasswordResetModal onClose={() => setPasswordModal(null)} onSave={resetUserPassword} user={passwordModal} />}
      {showProfile && <ProfileModal onClose={() => setShowProfile(false)} tickets={tickets} user={session} />}
      {toast && <Toast message={toast} onClose={() => setToast("")} />}
    </div>
  );
}

function Dashboard({ canCreate, criticalTickets, dashboard, onCreate, onOpen, onShowTickets, tickets, validationTickets }) {
  const activeTickets = dashboard?.metrics?.active_tickets ?? tickets.filter((ticket) => ticket.statusCode !== "CERRADO").length;
  const resolvedToday = dashboard?.metrics?.closed_today ?? tickets.filter((ticket) => ticket.statusCode === "CERRADO").length;
  const sla = dashboard?.sla || { en_tiempo: 0, advertencia: 0, vencido: 0 };
  const slaTotal = sla.en_tiempo + sla.advertencia + sla.vencido;
  const slaScore = slaTotal ? Math.round((sla.en_tiempo / slaTotal) * 100) : 100;
  const slaPercentage = (value) => (slaTotal ? Math.round((value / slaTotal) * 100) : 0);

  const metrics = [
    { label: "Tickets activos", value: activeTickets, trend: "+12%", detail: "vs. turno anterior", icon: "ticket", tone: "green" },
    { label: "Requieren atención", value: dashboard?.metrics?.critical_tickets ?? criticalTickets, trend: `${sla.vencido} vencidos`, detail: "SLA menor a 1 hora", icon: "alert", tone: "coral" },
    { label: "En validación", value: validationTickets.length, trend: "1 nuevo", detail: "pendiente de respuesta", icon: "checkCircle", tone: "violet" },
    { label: "Resueltos hoy", value: resolvedToday, trend: "94%", detail: "dentro del SLA", icon: "activity", tone: "blue" },
  ];

  return (
    <>
      <PageHeader
        eyebrow="Operación en tiempo real"
        title="Todo bajo control."
        description="Supervisa el trabajo de tu equipo y prioriza lo que necesita atención ahora."
        action={canCreate ? <button className="primary-button" type="button" onClick={onCreate}><Icon name="plus" size={18} /> Nuevo ticket</button> : null}
      />

      <section className="metrics-grid" aria-label="Resumen de operación">
        {metrics.map((metric) => (
          <article className="metric-card" key={metric.label}>
            <div className={`metric-icon ${metric.tone}`}><Icon name={metric.icon} size={21} /></div>
            <div className="metric-heading">
              <span>{metric.label}</span>
              <button type="button" aria-label={`Más información sobre ${metric.label}`}><Icon name="dots" size={18} /></button>
            </div>
            <strong>{metric.value}</strong>
            <p><b>{metric.trend}</b> {metric.detail}</p>
          </article>
        ))}
      </section>

      <section className="dashboard-grid">
        <article className="panel ticket-panel">
          <PanelHeading
            eyebrow="Bandeja de entrada"
            title="Prioridad del turno"
            action={<button className="text-button" type="button" onClick={onShowTickets}>Ver todos <Icon name="arrowRight" size={16} /></button>}
          />
          <div className="ticket-table-wrap compact-table-wrap">
            <TicketTable onOpen={onOpen} tickets={tickets.slice(0, 4)} compact />
          </div>
        </article>

        <article className="panel SLA-panel">
          <PanelHeading eyebrow="Ritmo de atención" title="Estado del SLA" />
          <div className="sla-score">
            <div className="score-ring" style={{ "--score": `${slaScore}` }}><span>{slaScore}<small>%</small></span></div>
            <div>
              <strong>En buen ritmo</strong>
              <p>La mayor parte de los casos avanza dentro del tiempo acordado.</p>
            </div>
          </div>
          <div className="sla-breakdown">
            <SlaItem label="Dentro del SLA" count={sla.en_tiempo} value={slaPercentage(sla.en_tiempo)} tone="safe" />
            <SlaItem label="Próximos a vencer" count={sla.advertencia} value={slaPercentage(sla.advertencia)} tone="warning" />
            <SlaItem label="SLA vencido" count={sla.vencido} value={slaPercentage(sla.vencido)} tone="danger" />
          </div>
        </article>

        <article className="panel flow-panel">
          <PanelHeading eyebrow="Pulso operativo" title="Flujo de tickets" action={<span className="legend-label"><i /> Últimas 8 horas</span>} />
          <div className="flow-chart" aria-label="Gráfico de flujo de tickets durante ocho horas">
            <div className="chart-axis"><span>16</span><span>12</span><span>8</span><span>4</span><span>0</span></div>
            <div className="chart-area">
              <svg viewBox="0 0 640 220" preserveAspectRatio="none" role="img" aria-label="Tendencia ascendente de tickets procesados">
                <defs>
                  <linearGradient id="flow-gradient" x1="0" x2="0" y1="0" y2="1">
                    <stop offset="0%" stopColor="currentColor" stopOpacity="0.28" />
                    <stop offset="100%" stopColor="currentColor" stopOpacity="0" />
                  </linearGradient>
                </defs>
                <path className="chart-grid" d="M0 20H640M0 72H640M0 124H640M0 176H640" />
                <path className="area-line" d="M0 164 C40 151, 53 156, 83 143 S126 110, 161 128 S213 142, 245 100 S299 116, 329 83 S377 113, 407 95 S459 42, 493 68 S546 87, 572 40 S614 55, 640 23 V220H0Z" />
                <path className="line-path" d="M0 164 C40 151, 53 156, 83 143 S126 110, 161 128 S213 142, 245 100 S299 116, 329 83 S377 113, 407 95 S459 42, 493 68 S546 87, 572 40 S614 55, 640 23" />
                <circle cx="572" cy="40" r="5" className="chart-dot" />
              </svg>
              <div className="chart-labels"><span>08:00</span><span>10:00</span><span>12:00</span><span>14:00</span><span>16:00</span></div>
            </div>
          </div>
        </article>

        <article className="panel activity-panel">
          <PanelHeading eyebrow="Actividad reciente" title="Cambios importantes" />
          <div className="activity-list">
            <Activity icon="checkCircle" tone="green" text={<><b>INC-1046</b> pasó a validación</>} time="Hace 4 min" />
            <Activity icon="users" tone="blue" text={<><b>Mario R.</b> tomó INC-1048</>} time="Hace 12 min" />
            <Activity icon="alert" tone="coral" text={<><b>INC-1047</b> está próximo a vencer</>} time="Hace 18 min" />
          </div>
        </article>
      </section>
    </>
  );
}

function TicketsView({ canCreate, currentUser, filter, filteredTickets, onCreate, onFilterChange, onNotify, onOpen, onResolve, onTake, query, setQuery }) {
  const filters = currentUser?.role === "SOPORTE" ? ["Trabajables", "Míos", "Asignado", "En proceso", "Validación", "Todos"] : currentUser?.role === "DESPACHADOR" ? ["Míos", "Asignado", "En proceso", "Validación", "Todos"] : ["Todos", "Abierto", "Asignado", "En proceso", "Validación"];

  return (
    <>
      <PageHeader
        eyebrow="Gestión de solicitudes"
        title="Bandeja de tickets"
        description="Consulta y prioriza los casos asignados a tu grupo de trabajo."
        action={canCreate ? <button className="primary-button" type="button" onClick={onCreate}><Icon name="plus" size={18} /> Nuevo ticket</button> : null}
      />
      <article className="panel tickets-page-panel">
        <div className="toolbar">
          <label className="table-search">
            <Icon name="search" size={18} />
            <input type="search" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Buscar por ID, asunto o persona" />
          </label>
          <div className="filter-row" aria-label="Filtrar tickets por estado">
            <Icon name="filter" size={17} />
            {filters.map((item) => (
              <button className={filter === item ? "selected" : ""} key={item} type="button" onClick={() => onFilterChange(item)}>{item}</button>
            ))}
          </div>
        </div>
        <div className="table-summary"><span><b>{filteredTickets.length}</b> tickets encontrados</span><button type="button" onClick={() => onNotify("Los filtros se actualizarán automáticamente con la API.")}>Ordenar: prioridad <Icon name="chevronDown" size={15} /></button></div>
        <div className="ticket-table-wrap"><TicketTable currentUser={currentUser} onNotify={onNotify} onOpen={onOpen} onResolve={onResolve} onTake={onTake} tickets={filteredTickets} /></div>
        {filteredTickets.length === 0 && <EmptyState />}
      </article>
    </>
  );
}

function ValidationsView({ canValidate, tickets, onOpen, onValidate }) {
  const [rejectId, setRejectId] = useState(null);
  const [rejectComment, setRejectComment] = useState("");
  return (
    <>
      <PageHeader
        eyebrow="Cierre con validación cruzada"
        title="Pendientes de confirmar"
        description=""
      />
      <section className="validation-grid">
        {!canValidate ? <EmptyValidation /> : null}
        {canValidate && tickets.length > 0 ? tickets.map((ticket) => (
          <article className="validation-card" key={ticket.id} onClick={() => onOpen && onOpen(ticket)} style={{ cursor: onOpen ? "pointer" : "default" }}>
            <div className="validation-card-top"><span className="ticket-id">{ticket.id}</span><span className="status-pill status-validation">Validación</span></div>
            <h2>{ticket.title}</h2>
            <div className="solution-note"><Icon name="checkCircle" size={19} /><div><span>Solución de Soporte</span><p>{ticket.resolutionNotes || "Soporte marcó este caso como resuelto. Confirma el resultado en campo."}</p></div></div>
            <div className="validation-meta"><span><div className="avatar small-avatar">{initials(ticket.assignee)}</div> {ticket.assignee}</span><span><Icon name="clock" size={16} /> {ticket.created}</span></div>
            {rejectId === ticket.apiId ? <div style={{ display: "grid", gap: "8px", marginTop: "10px" }} onClick={(e) => e.stopPropagation()}><textarea value={rejectComment} onChange={(e) => setRejectComment(e.target.value)} placeholder="Motivo del rechazo (obligatorio)" rows="3" style={{ width: "100%", border: "1px solid var(--line-strong)", borderRadius: "6px", padding: "8px", fontSize: "11px" }} /><div style={{ display: "flex", gap: "6px" }}><button className="secondary-button" disabled={!rejectComment.trim()} type="button" onClick={() => { onValidate(ticket, false, rejectComment); setRejectId(null); setRejectComment(""); }}>Confirmar rechazo</button><button className="secondary-button" type="button" onClick={() => { setRejectId(null); setRejectComment(""); }}>Cancelar</button></div></div> : <div className="validation-actions" onClick={(e) => e.stopPropagation()}><button className="secondary-button" type="button" onClick={() => setRejectId(ticket.apiId)}>Rechazar y devolver</button><button className="primary-button" type="button" onClick={() => onValidate(ticket, true)}><Icon name="check" size={17} /> Aprobar solución</button></div>}
            <div style={{ marginTop: "8px", fontSize: "10px", color: "var(--quiet)", textAlign: "center" }}>Clic para ver detalle →</div>
          </article>
        )) : null}
        {canValidate && tickets.length === 0 ? <EmptyValidation /> : null}
      </section>
    </>
  );
}

function TeamView({ currentUser, onNotify, tickets, users }) {
  const peopleByName = new Map();
  const memberUsers = (users || []).filter((u) => u.is_active && !u.is_locked);
  if (memberUsers.length) {
    memberUsers.forEach((u) => {
      peopleByName.set(u.name, { initials: u.initials, name: u.name, role: u.roleLabel, load: 0, status: u.name === currentUser.name ? "En línea" : "En atención", className: u.avatarClass });
    });
  } else if (currentUser.role === "SOPORTE") {
    peopleByName.set(currentUser.name, { initials: currentUser.initials, name: currentUser.name, role: currentUser.roleLabel, load: 0, status: "En línea", className: currentUser.avatarClass });
  }
  tickets.forEach((ticket) => {
    if (ticket.assignee === "Sin asignar") return;
    const person = peopleByName.get(ticket.assignee) || { initials: initials(ticket.assignee), name: ticket.assignee, role: "Soporte", load: 0, status: "En atención", className: avatarClass(ticket.assignee) };
    if (ticket.statusCode !== "CERRADO") person.load += 1;
    peopleByName.set(ticket.assignee, person);
  });
  const people = [...peopleByName.values()];
  return (
    <>
      <PageHeader eyebrow="Disponibilidad del grupo" title="Personas que respaldan tu operación" description="La carga se calcula a partir de los tickets visibles para tu perfil y grupo." action={<button className="secondary-button" type="button" onClick={() => onNotify("La asignación automática prioriza al agente que lleva más tiempo sin recibir un caso.")}><Icon name="users" size={18} /> Ver reglas de asignación</button>} />
      <section className="team-grid">
        {people.length ? people.map((person) => (
          <article className="team-card" key={person.name}>
            <div className={`avatar team-avatar ${person.className}`}>{person.initials}</div>
            <div className="team-card-title"><h2>{person.name}</h2><span className="online-status"><i /> {person.status}</span></div>
            <p>{person.role}</p>
            <div className="capacity"><div><span>Carga activa</span><strong>{person.load} <small>tickets</small></strong></div><div className="capacity-bars"><i /><i /><i /><i /><i className={person.load < 5 ? "off" : ""} /></div></div>
            <button type="button" onClick={() => onNotify(`Se abrió el perfil de ${person.name}.`)}>Ver carga <Icon name="arrowRight" size={16} /></button>
          </article>
        )) : <EmptyState />}
      </section>
    </>
  );
}

function ReportsView({ tickets }) {
  const total = tickets.length;
  const closed = tickets.filter((ticket) => ticket.statusCode === "CERRADO").length;
  const withinSla = tickets.filter((ticket) => ticket.slaTone === "safe").length;
  const byCategory = ["FTTH", "HFC", "DTH"].map((category) => ({
    category,
    total: tickets.filter((ticket) => ticket.category === category).length,
  }));
  const percentage = (value) => (total ? Math.round((value / total) * 100) : 0);
  const ftth = percentage(byCategory[0].total);
  const hfc = percentage(byCategory[1].total);
  const dth = percentage(byCategory[2].total);
  const donutStyle = { background: `conic-gradient(#4c8c69 0 ${ftth}%, #6387be ${ftth}% ${ftth + hfc}%, #d59b47 ${ftth + hfc}% 100%)` };
  return (
    <>
      <PageHeader eyebrow="Indicadores operativos" title="El turno en cifras" description="Vista consolidada para identificar capacidad, cumplimiento y oportunidades de mejora." action={<div className="date-picker"><Icon name="calendar" size={18} /> Hoy, 22 de agosto <Icon name="chevronDown" size={15} /></div>} />
      <section className="report-highlights">
        <article><span>Tickets visibles</span><strong>{total}</strong><p><b>Según tu perfil</b> y restricciones de grupo</p></article>
        <article><span>Tickets cerrados</span><strong>{closed}</strong><p><b>{percentage(closed)}%</b> de los tickets visibles</p></article>
        <article><span>Cumplimiento SLA</span><strong>{percentage(withinSla)}<small>%</small></strong><p><b>Meta: 90%</b> del turno</p></article>
      </section>
      <section className="reports-grid">
        <article className="panel channel-panel"><PanelHeading eyebrow="Por tecnología" title="Origen de los tickets" /><div className="donut-layout"><div className="donut" style={donutStyle}><span>{total}<small>total</small></span></div><div className="donut-legend"><span><i className="ftth" /> FTTH <b>{ftth}%</b></span><span><i className="hfc" /> HFC <b>{hfc}%</b></span><span><i className="dth" /> DTH <b>{dth}%</b></span></div></div></article>
        <article className="panel performance-panel"><PanelHeading eyebrow="Distribución" title="Participación por tecnología" /><div className="performance-bars"><ReportBar label="FTTH" value={ftth} /><ReportBar label="HFC" value={hfc} /><ReportBar label="DTH" value={dth} /></div></article>
      </section>
    </>
  );
}

function UsersView({ error, groups, loading, onCreate, onCreateGroup, onCreateTeam, onCreateRequestType, onEdit, onEditGroup, onEditTeam, onEditRequestType, onResetPassword, onRetry, requestTypes, teams, users, currentRole }) {
  const [query, setQuery] = useState("");
  const [role, setRole] = useState("Todos");
  const [tab, setTab] = useState("usuarios");
  const filteredUsers = users.filter((user) => {
    const matchesQuery = `${user.name} ${user.email} ${user.teamName}`.toLowerCase().includes(query.toLowerCase());
    return matchesQuery && (role === "Todos" || user.role === role);
  });

  return (
    <>
      <PageHeader eyebrow="Administración" title="Usuarios y accesos" description="Gestiona personas y grupos. Los roles son asignables por administrador y las credenciales se restablecen desde aquí." action={tab === "usuarios" ? <button className="primary-button" type="button" onClick={onCreate}><Icon name="plus" size={18} /> Nuevo usuario</button> : tab === "tipos" ? <button className="primary-button" type="button" onClick={onCreateRequestType}><Icon name="plus" size={18} /> Nuevo tipo</button> : <button className="primary-button" type="button" onClick={onCreateGroup}><Icon name="plus" size={18} /> Nuevo grupo</button>} />
      {error && <ApiConnectionError message={error} onRetry={onRetry} />}
      {currentRole !== "SUPERVISOR" && <div className="admin-tabs" role="tablist">
        <button className={tab === "usuarios" ? "selected" : ""} type="button" role="tab" aria-selected={tab === "usuarios"} onClick={() => setTab("usuarios")}><Icon name="users" size={16} /> Usuarios <span>{users.length}</span></button>
        <button className={tab === "grupos" ? "selected" : ""} type="button" role="tab" aria-selected={tab === "grupos"} onClick={() => setTab("grupos")}><Icon name="shield" size={16} /> Grupos <span>{groups.length}</span></button>
        <button className={tab === "tipos" ? "selected" : ""} type="button" role="tab" aria-selected={tab === "tipos"} onClick={() => setTab("tipos")}><Icon name="ticket" size={16} /> Tipos <span>{(requestTypes || []).length}</span></button>
      </div>}
      {loading ? <LoadingState /> : tab === "usuarios" ? <article className="panel users-panel">
        <div className="toolbar users-toolbar">
          <label className="table-search"><Icon name="search" size={18} /><input type="search" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Buscar nombre, correo o grupo" /></label>
          <div className="filter-row" aria-label="Filtrar usuarios por rol"><Icon name="filter" size={17} />{[["Todos", "Todos"], ["DESPACHADOR", "Despachadores"], ["SOPORTE", "Soporte"], ["SUPERVISOR", "Supervisores"], ["ADMIN", "Administración"]].map(([value, label]) => <button className={role === value ? "selected" : ""} key={value} type="button" onClick={() => setRole(value)}>{label}</button>)}</div>
        </div>
        <div className="table-summary"><span><b>{filteredUsers.length}</b> usuarios encontrados</span><span>Bloqueo tras 5 intentos · Solo desbloquea vía correo</span></div><div className="users-table-wrap"><table className="users-table"><thead><tr><th>Usuario</th><th>Rol</th><th>Grupo</th><th>Estado</th><th aria-label="Acciones" /></tr></thead><tbody>{filteredUsers.map((user) => <tr key={user.id}><td data-label="Usuario"><div className="managed-user"><div className={`avatar ${user.avatarClass}`}>{user.initials}</div><div><strong>{user.name}</strong><small>{user.email}</small></div></div></td><td data-label="Rol"><span className={`role-pill role-${user.role.toLowerCase()}`}>{user.roleLabel}</span></td><td data-label="Grupo"><div className="team-cell"><strong>{user.groupName}</strong></div></td><td data-label="Estado"><span className={`user-status ${user.is_locked ? "locked" : user.is_active ? "active" : "inactive"}`}><i /> {user.is_locked ? `Bloqueada (${user.failed_login_attempts})` : user.is_active ? "Activo" : "Inactivo"}</span></td><td className="user-action">{currentRole === "SUPERVISOR" && user.role === "ADMIN" ? <small style={{ color: "var(--quiet)" }}>Solo admin</small> : <><button type="button" onClick={() => onEdit(user)}>Editar</button><button className="reset-link" type="button" onClick={() => onResetPassword(user)}>Contraseña</button></>}</td></tr>)}</tbody></table></div>{filteredUsers.length === 0 && <EmptyState />}
      </article> : tab === "equipos" ? <article className="panel users-panel"><div className="table-summary"><span><b>{teams.length}</b> equipos registrados</span><span>Agrupados por grupo · Código único</span></div><div className="users-table-wrap"><table className="users-table"><thead><tr><th>Equipo</th><th>Grupo</th><th>Código</th><th>Estado</th><th aria-label="Acciones" /></tr></thead><tbody>{teams.map((team) => <tr key={team.id}><td data-label="Equipo"><strong>{team.name}</strong></td><td data-label="Grupo"><span className="team-label">{team.group_detail?.name || team.group?.name || "-"}</span></td><td data-label="Código"><span className="team-label">{team.code}</span></td><td data-label="Estado"><span className={`user-status ${team.is_active ? "active" : "inactive"}`}><i /> {team.is_active ? "Activo" : "Inactivo"}</span></td><td className="user-action"><button type="button" onClick={() => onEditTeam(team)}>Editar</button></td></tr>)}</tbody></table></div>{teams.length === 0 && <EmptyState />}</article> : tab === "tipos" ? <article className="panel users-panel"><div className="table-summary"><span><b>{(requestTypes || []).length}</b> tipos registrados</span><span>Solicitud → Servicio → Tipo</span></div><div className="users-table-wrap"><table className="users-table"><thead><tr><th>Tipo</th><th>Solicitud</th><th>Servicio</th><th>Estado</th><th aria-label="Acciones" /></tr></thead><tbody>{(requestTypes || []).map((rt) => <tr key={rt.id}><td data-label="Tipo"><strong>{rt.name}</strong></td><td data-label="Solicitud"><span className="team-label">{rt.kind_label}</span></td><td data-label="Servicio"><span className="team-label">{rt.service}</span></td><td data-label="Estado"><span className={`user-status ${rt.is_active ? "active" : "inactive"}`}><i /> {rt.is_active ? "Activo" : "Inactivo"}</span></td><td className="user-action"><button type="button" onClick={() => onEditRequestType(rt)}>Editar</button></td></tr>)}</tbody></table></div>{(requestTypes || []).length === 0 && <EmptyState />}</article> : <article className="panel users-panel"><div className="table-summary"><span><b>{groups.length}</b> grupos registrados</span><span>Área macro (Tigo, Contrata, BBI N-2, etc.)</span></div><div className="users-table-wrap"><table className="users-table"><thead><tr><th>Grupo</th><th>Código</th><th>Estado</th><th aria-label="Acciones" /></tr></thead><tbody>{groups.map((group) => <tr key={group.id}><td data-label="Grupo"><strong>{group.name}</strong></td><td data-label="Código"><span className="team-label">{group.code}</span></td><td data-label="Estado"><span className={`user-status ${group.is_active ? "active" : "inactive"}`}><i /> {group.is_active ? "Activo" : "Inactivo"}</span></td><td className="user-action"><button type="button" onClick={() => onEditGroup(group)}>Editar</button></td></tr>)}</tbody></table></div>{groups.length === 0 && <EmptyState />}</article>}
    </>
  );
}

function UserFormModal({ onClose, onSave, teams, groups, user }) {
  const isNew = !user;
  const [form, setForm] = useState({
    firstName: user?.first_name || "",
    lastName: user?.last_name || "",
    email: user?.email || "",
    password: "",
    role: user?.role || "DESPACHADOR",
    teams: user?.teamIds || (user?.teamId ? [String(user.teamId)] : []),
    managedGroups: user?.managedGroups?.map(String) || user?.managed_groups?.map(String) || [],
    isActive: user?.is_active ?? true,
  });
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  function updateField(event) {
    const { name, value, type, checked } = event.target;
    setForm((current) => ({ ...current, [name]: type === "checkbox" ? checked : value }));
  }

  function toggleTeam(teamId) {
    const id = String(teamId);
    setForm((current) => ({
      ...current,
      teams: current.teams.includes(id) ? current.teams.filter((t) => t !== id) : [...current.teams, id],
    }));
  }
  function toggleGroup(groupId) {
    const id = String(groupId);
    setForm((current) => ({
      ...current,
      managedGroups: current.managedGroups.includes(id) ? current.managedGroups.filter((g) => g !== id) : [...current.managedGroups, id],
    }));
  }
  function toggleGroupTeams(groupId) {
    const groupTeams = teams.filter((t) => String(t.group) === String(groupId) || String(t.group_detail?.id) === String(groupId));
    const groupTeamIds = groupTeams.map((t) => String(t.id));
    const allSelected = groupTeamIds.every((id) => form.teams.includes(id));
    setForm((current) => ({
      ...current,
      teams: allSelected ? current.teams.filter((id) => !groupTeamIds.includes(id)) : [...new Set([...current.teams, ...groupTeamIds])],
    }));
  }

  async function submit(event) {
    event.preventDefault();
    if (form.role === "SUPERVISOR" && form.managedGroups.length === 0) {
      setError("Selecciona al menos un grupo para el supervisor.");
      return;
    }
    if (form.role !== "ADMIN" && form.role !== "SUPERVISOR" && form.teams.length === 0) {
      setError("Selecciona al menos un grupo para despachador o soporte.");
      return;
    }
    setSubmitting(true);
    setError("");
    try {
      await onSave(form, user);
    } catch (requestError) {
      setError(requestError.message || "No fue posible guardar el usuario.");
      setSubmitting(false);
    }
  }

  return (
    <div className="modal-backdrop" role="presentation" onMouseDown={onClose}>
      <section className="ticket-modal user-modal" role="dialog" aria-modal="true" aria-labelledby="user-form-title" onMouseDown={(event) => event.stopPropagation()}>
        <header className="modal-header"><div><p className="eyebrow">Administración de acceso</p><h2 id="user-form-title">{isNew ? "Crear usuario" : "Editar usuario"}</h2><p>{isNew ? "El acceso se asignará al guardar el perfil." : "Actualiza permisos, grupo o credenciales de forma segura."}</p></div><button className="icon-button" type="button" aria-label="Cerrar formulario" onClick={onClose}><Icon name="close" /></button></header>
        <form onSubmit={submit}>
          <div className="form-grid user-form-grid">
            <label className="field"><span>Nombres <b>*</b></span><input autoFocus required name="firstName" value={form.firstName} onChange={updateField} placeholder="Nombres" /></label>
            <label className="field"><span>Apellidos <b>*</b></span><input required name="lastName" value={form.lastName} onChange={updateField} placeholder="Apellidos" /></label>
            <label className="field field-wide"><span>Correo institucional <b>*</b></span><input required type="email" name="email" value={form.email} onChange={updateField} placeholder="nombre@empresa.com" /></label>
            <label className="field"><span>Rol <b>*</b></span><select name="role" value={form.role} onChange={updateField}><option value="DESPACHADOR">Despachador</option><option value="SOPORTE">Agente de soporte</option><option value="SUPERVISOR">Supervisor</option><option value="ADMIN">Administrador</option></select></label>
            {form.role === "SUPERVISOR" ? <label className="field field-wide"><span>Grupos supervisados <b>*</b></span><div className="teams-checklist compact">{groups.map((g) => <label key={g.id} className="team-check"><input type="checkbox" checked={form.managedGroups.includes(String(g.id))} onChange={() => toggleGroup(g.id)} /><span>{g.name} <small>· {g.code}</small></span></label>)}{groups.length === 0 && <small>Sin grupos registrados</small>}</div></label> : <label className="field field-wide"><span>Grupos {(form.role !== "ADMIN") && <b>*</b>}</span><div className="teams-checklist compact">{groups.map((g) => { const groupTeams = teams.filter((t) => String(t.group) === String(g.id) || String(t.group_detail?.id) === String(g.id)); if (!groupTeams.length) return null; const allSelected = groupTeams.every((t) => form.teams.includes(String(t.id))); return <label key={g.id} className="team-check"><input type="checkbox" checked={allSelected} onChange={() => toggleGroupTeams(g.id)} /><span>{g.name} <small>· {g.code}</small></span></label>; })}{groups.length === 0 && <small>Sin grupos registrados</small>}</div></label>}
            <label className="field field-wide"><span>{isNew ? "Contraseña temporal" : "Nueva contraseña"} {isNew && <b>*</b>}</span><input required={isNew} minLength="8" name="password" type="password" value={form.password} onChange={updateField} placeholder={isNew ? "Mínimo 8 caracteres" : "Déjalo vacío para conservarla"} /></label>
          </div>
          <label className="active-user-toggle"><input checked={form.isActive} name="isActive" type="checkbox" onChange={updateField} /><span><i /></span><div><strong>Usuario activo</strong><small>Puede iniciar sesión y recibir asignaciones.</small></div></label>
          {error && <p className="form-submit-error" role="alert"><Icon name="alert" size={16} /> {error}</p>}
          <footer className="modal-actions"><button className="secondary-button" disabled={submitting} type="button" onClick={onClose}>Cancelar</button><button className="primary-button" disabled={submitting} type="submit"><Icon name="check" size={18} /> {submitting ? "Guardando..." : isNew ? "Crear usuario" : "Guardar cambios"}</button></footer>
        </form>
      </section>
    </div>
  );
}

function TeamFormModal({ groups, onClose, onSave, team }) {
  const isNew = !team;
  const [form, setForm] = useState({ name: team?.name || "", code: team?.code || "", group: team?.group ? String(team.group) : groups[0] ? String(groups[0].id) : "", isActive: team?.is_active ?? true });
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  function updateField(e) { const { name, value, type, checked } = e.target; setForm((c) => ({ ...c, [name]: type === "checkbox" ? checked : value })); }
  async function submit(e) { e.preventDefault(); if (!form.name.trim() || !form.code.trim() || !form.group) { setError("Completa nombre, código y grupo."); return; } setSubmitting(true); setError(""); try { await onSave(form, team); } catch (err) { setError(err.message || "No fue posible guardar el equipo."); setSubmitting(false); } }
  return <div className="modal-backdrop" role="presentation" onMouseDown={onClose}><section className="ticket-modal user-modal" role="dialog" aria-modal="true" aria-labelledby="team-form-title" onMouseDown={(e) => e.stopPropagation()}><header className="modal-header"><div><p className="eyebrow">Estructura operativa</p><h2 id="team-form-title">{isNew ? "Nuevo equipo" : "Editar equipo"}</h2><p>Define el equipo por zona o sector y su grupo padre.</p></div><button className="icon-button" type="button" aria-label="Cerrar" onClick={onClose}><Icon name="close" /></button></header><form onSubmit={submit}><div className="form-grid user-form-grid"><label className="field"><span>Nombre <b>*</b></span><input autoFocus required name="name" value={form.name} onChange={updateField} placeholder="FTTH Norte" /></label><label className="field"><span>Código <b>*</b></span><input required name="code" value={form.code} onChange={updateField} placeholder="ftth-norte" /></label><label className="field field-wide"><span>Grupo <b>*</b></span><select name="group" value={form.group} onChange={updateField}>{groups.map((g) => <option key={g.id} value={g.id}>{g.name}</option>)}</select></label></div><label className="active-user-toggle"><input checked={form.isActive} name="isActive" type="checkbox" onChange={updateField} /><span><i /></span><div><strong>Equipo activo</strong><small>Disponible para asignación.</small></div></label>{error && <p className="form-submit-error" role="alert"><Icon name="alert" size={16} /> {error}</p>}<footer className="modal-actions"><button className="secondary-button" disabled={submitting} type="button" onClick={onClose}>Cancelar</button><button className="primary-button" disabled={submitting} type="submit"><Icon name="check" size={18} /> {submitting ? "Guardando..." : isNew ? "Crear equipo" : "Guardar cambios"}</button></footer></form></section></div>;
}

function GroupFormModal({ group, onClose, onSave }) {
  const isNew = !group;
  const [form, setForm] = useState({ name: group?.name || "", code: group?.code || "", isActive: group?.is_active ?? true });
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  function updateField(e) { const { name, value, type, checked } = e.target; setForm((c) => ({ ...c, [name]: type === "checkbox" ? checked : value })); }
  async function submit(e) { e.preventDefault(); if (!form.name.trim() || !form.code.trim()) { setError("Completa nombre y código."); return; } setSubmitting(true); setError(""); try { await onSave(form, group); } catch (err) { setError(err.message || "No fue posible guardar el grupo."); setSubmitting(false); } }
  return <div className="modal-backdrop" role="presentation" onMouseDown={onClose}><section className="ticket-modal user-modal" role="dialog" aria-modal="true" aria-labelledby="group-form-title" onMouseDown={(e) => e.stopPropagation()}><header className="modal-header"><div><p className="eyebrow">Segmentación organizacional</p><h2 id="group-form-title">{isNew ? "Nuevo grupo" : "Editar grupo"}</h2><p>El grupo es el área macro (Tigo, Contrata, BBI N-2).</p></div><button className="icon-button" type="button" aria-label="Cerrar" onClick={onClose}><Icon name="close" /></button></header><form onSubmit={submit}><div className="form-grid user-form-grid"><label className="field"><span>Nombre <b>*</b></span><input autoFocus required name="name" value={form.name} onChange={updateField} placeholder="Tigo" /></label><label className="field"><span>Código <b>*</b></span><input required name="code" value={form.code} onChange={updateField} placeholder="tigo" /></label></div><label className="active-user-toggle"><input checked={form.isActive} name="isActive" type="checkbox" onChange={updateField} /><span><i /></span><div><strong>Grupo activo</strong><small>Visible para asignación.</small></div></label>{error && <p className="form-submit-error" role="alert"><Icon name="alert" size={16} /> {error}</p>}<footer className="modal-actions"><button className="secondary-button" disabled={submitting} type="button" onClick={onClose}>Cancelar</button><button className="primary-button" disabled={submitting} type="submit"><Icon name="check" size={18} /> {submitting ? "Guardando..." : isNew ? "Crear grupo" : "Guardar cambios"}</button></footer></form></section></div>;
}

function RequestTypeFormModal({ onClose, onSave, requestType }) {
  const isNew = !requestType;
  const [form, setForm] = useState({ kind: requestType?.kind || "CLIENTE", service: requestType?.service || "HFC", name: requestType?.name || "", isActive: requestType?.is_active ?? true });
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  function updateField(e) { const { name, value, type, checked } = e.target; setForm((c) => ({ ...c, [name]: type === "checkbox" ? checked : value })); }
  async function submit(e) { e.preventDefault(); if (!form.name.trim()) { setError("Completa el nombre del tipo."); return; } setSubmitting(true); setError(""); try { await onSave(form, requestType); } catch (err) { setError(err.message || "No fue posible guardar el tipo."); setSubmitting(false); } }
  return <div className="modal-backdrop" role="presentation" onMouseDown={onClose}><section className="ticket-modal user-modal" role="dialog" aria-modal="true" aria-labelledby="rt-form-title" onMouseDown={(e) => e.stopPropagation()}><header className="modal-header"><div><p className="eyebrow">Catálogo de solicitudes</p><h2 id="rt-form-title">{isNew ? "Nuevo tipo" : "Editar tipo"}</h2><p>Define a qué solicitud y servicio aplica.</p></div><button className="icon-button" type="button" aria-label="Cerrar" onClick={onClose}><Icon name="close" /></button></header><form onSubmit={submit}><div className="form-grid user-form-grid"><label className="field"><span>Tipo de solicitud <b>*</b></span><select name="kind" value={form.kind} onChange={updateField}><option value="CLIENTE">Solicitud de Soporte Cliente</option><option value="TECNICO">Soporte Al Tecnico</option></select></label><label className="field"><span>Servicio <b>*</b></span><select name="service" value={form.service} onChange={updateField}><option value="HFC">HFC</option><option value="FTTH">FTTH</option><option value="WTTX">WTTX</option><option value="DTH">DTH</option></select></label><label className="field field-wide"><span>Nombre <b>*</b></span><input autoFocus required name="name" value={form.name} onChange={updateField} placeholder="ONT sin VLAN" /></label></div><label className="active-user-toggle"><input checked={form.isActive} name="isActive" type="checkbox" onChange={updateField} /><span><i /></span><div><strong>Tipo activo</strong><small>Visible en el formulario.</small></div></label>{error && <p className="form-submit-error" role="alert"><Icon name="alert" size={16} /> {error}</p>}<footer className="modal-actions"><button className="secondary-button" disabled={submitting} type="button" onClick={onClose}>Cancelar</button><button className="primary-button" disabled={submitting} type="submit"><Icon name="check" size={18} /> {submitting ? "Guardando..." : isNew ? "Crear tipo" : "Guardar cambios"}</button></footer></form></section></div>;
}

function PasswordResetModal({ onClose, onSave, user }) {
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  async function submit(e) { e.preventDefault(); if (password.length < 8) { setError("La contraseña debe tener al menos 8 caracteres."); return; } if (password !== confirm) { setError("Las contraseñas no coinciden."); return; } setSubmitting(true); setError(""); try { await onSave(user, password); } catch (err) { setError(err.message || "No fue posible restablecer la contraseña."); setSubmitting(false); } }
  return <div className="modal-backdrop" role="presentation" onMouseDown={onClose}><section className="ticket-modal user-modal" role="dialog" aria-modal="true" aria-labelledby="pwd-title" onMouseDown={(e) => e.stopPropagation()}><header className="modal-header"><div><p className="eyebrow">Seguridad</p><h2 id="pwd-title">Restablecer contraseña</h2><p>Define una nueva contraseña para {user.name} ({user.email}).</p></div><button className="icon-button" type="button" aria-label="Cerrar" onClick={onClose}><Icon name="close" /></button></header><form onSubmit={submit}><div className="form-grid user-form-grid"><label className="field field-wide"><span>Nueva contraseña <b>*</b></span><input autoFocus required minLength="8" type="password" value={password} onChange={(e) => setPassword(e.target.value)} placeholder="Mínimo 8 caracteres" /></label><label className="field field-wide"><span>Confirmar contraseña <b>*</b></span><input required minLength="8" type="password" value={confirm} onChange={(e) => setConfirm(e.target.value)} placeholder="Repite la contraseña" /></label></div>{error && <p className="form-submit-error" role="alert"><Icon name="alert" size={16} /> {error}</p>}<footer className="modal-actions"><button className="secondary-button" disabled={submitting} type="button" onClick={onClose}>Cancelar</button><button className="primary-button" disabled={submitting} type="submit"><Icon name="shield" size={18} /> {submitting ? "Guardando..." : "Restablecer"}</button></footer></form></section></div>;
}

function PageHeader({ eyebrow, title, description, action }) {
  return <header className="page-header"><div><p className="eyebrow">{eyebrow}</p><h1>{title}</h1><p className="page-description">{description}</p></div>{action && <div className="page-header-action">{action}</div>}</header>;
}

function PanelHeading({ eyebrow, title, action }) {
  return <header className="panel-heading"><div><p className="eyebrow">{eyebrow}</p><h2>{title}</h2></div>{action}</header>;
}

function TicketTable({ tickets, compact = false, currentUser, onNotify, onOpen, onResolve, onTake }) {
  return (
    <table className={`ticket-table ${compact ? "compact" : ""}`}>
      <thead><tr><th>Ticket</th><th>Prioridad</th><th>Estado</th><th>Grupo</th><th>SLA restante</th>{!compact && <th aria-label="Acciones" />}</tr></thead>
      <tbody>
        {tickets.map((ticket) => (
          <tr className={onOpen ? "ticket-row-clickable" : ""} key={ticket.id} onClick={() => onOpen?.(ticket)}>
            <td data-label="Ticket"><div className="ticket-title"><div className="avatar ticket-avatar">{ticket.avatar}</div><div><span>{ticket.id}{ticket.identificador ? ` · ${ticket.identificador}` : ""}</span><strong>{ticket.title}</strong><small>{ticket.category}{ticket.tipoSolicitud ? ` · ${ticket.tipoSolicitud}` : ""} · {ticket.created}</small></div></div></td>
            <td data-label="Prioridad"><span className={`priority-pill ${priorityClass[ticket.priority]}`}>{ticket.priority}</span></td>
            <td data-label="Estado"><span className={`status-pill ${statusClass[ticket.status]}`}>{ticket.status}</span></td>
            <td data-label="Equipo"><span className="team-label">{ticket.team}</span></td>
            <td data-label="SLA restante"><span className={`sla-time ${ticket.slaTone}`}><i /> {ticket.sla}</span></td>
            {!compact && <td className="table-action">
              {currentUser?.role === "SOPORTE" && ["ABIERTO", "ASIGNADO"].includes(ticket.statusCode) ? <button className="quick-action" type="button" onClick={(event) => { event.stopPropagation(); onTake(ticket); }}>Tomar</button> : null}
              {currentUser?.role === "SOPORTE" && ticket.statusCode === "EN_PROCESO" ? <button className="quick-action" type="button" onClick={(event) => { event.stopPropagation(); onResolve(ticket); }}>Resolver</button> : null}
              {(!currentUser || currentUser.role !== "SOPORTE" || !["ABIERTO", "ASIGNADO", "EN_PROCESO"].includes(ticket.statusCode)) && <button type="button" aria-label={`Ver ${ticket.id}`} onClick={(event) => { event.stopPropagation(); if (onOpen) onOpen(ticket); else onNotify?.(`El detalle de ${ticket.id} no está disponible.`); }}><Icon name="dots" size={19} /></button>}
            </td>}
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function SlaItem({ label, count, value, tone }) {
  return <div className="sla-item"><div><span>{label}</span><strong>{count}</strong></div><div className="progress-track"><i className={tone} style={{ width: `${value}%` }} /></div></div>;
}

function Activity({ icon, tone, text, time }) {
  return <div className="activity-item"><span className={`activity-icon ${tone}`}><Icon name={icon} size={17} /></span><p>{text}<small>{time}</small></p></div>;
}

function ReportBar({ label, value }) {
  return <div className="report-bar"><div><span>{label}</span><b>{value}%</b></div><div><i style={{ width: `${value}%` }} /></div></div>;
}

function EmptyState() {
  return <div className="empty-state"><span><Icon name="search" size={25} /></span><strong>No encontramos tickets</strong><p>Prueba con otra búsqueda o cambia los filtros.</p></div>;
}

function EmptyValidation() {
  return <article className="empty-validation"><span><Icon name="checkCircle" size={28} /></span><h2>Todo al día</h2><p>No tienes soluciones pendientes de validar en este momento.</p></article>;
}

function LoadingState() {
  return <div className="workspace-state"><span className="loading-mark"><i /><i /><i /></span><strong>Actualizando operación</strong><p>Consultando tickets, SLA y validaciones.</p></div>;
}

function ApiConnectionError({ message, onRetry }) {
  return <div className="api-connection-error" role="alert"><Icon name="alert" size={20} /><div><strong>No se pudieron cargar los datos</strong><p>{message}</p></div><button className="secondary-button" type="button" onClick={onRetry}>Reintentar</button></div>;
}

function ResolveTicketModal({ onClose, onResolve, ticket }) {
  const [resolutionNotes, setResolutionNotes] = useState("");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  async function submit(event) {
    event.preventDefault();
    setSubmitting(true);
    setError("");
    try {
      await onResolve(ticket, resolutionNotes);
    } catch (requestError) {
      setError(requestError.message || "No fue posible enviar la solución.");
      setSubmitting(false);
    }
  }

  return (
    <div className="modal-backdrop" role="presentation" onMouseDown={onClose}>
      <section className="ticket-modal resolution-modal" role="dialog" aria-modal="true" aria-labelledby="resolve-ticket-title" onMouseDown={(event) => event.stopPropagation()}>
        <header className="modal-header"><div><p className="eyebrow">Resolución técnica</p><h2 id="resolve-ticket-title">Enviar a validación</h2><p>{ticket.id} volverá al despachador para confirmar la solución.</p></div><button className="icon-button" type="button" aria-label="Cerrar formulario" onClick={onClose}><Icon name="close" /></button></header>
        <form onSubmit={submit}>
          <div className="resolution-ticket"><span>{ticket.id}</span><strong>{ticket.title}</strong></div>
          <label className="field"><span>Solución aplicada <b>*</b></span><textarea autoFocus required minLength="8" name="resolutionNotes" value={resolutionNotes} onChange={(event) => setResolutionNotes(event.target.value)} rows="5" placeholder="Describe el diagnóstico, la acción aplicada y el resultado verificado." /></label>
          {error && <p className="form-submit-error" role="alert"><Icon name="alert" size={16} /> {error}</p>}
          <footer className="modal-actions"><button className="secondary-button" disabled={submitting} type="button" onClick={onClose}>Cancelar</button><button className="primary-button" disabled={submitting} type="submit"><Icon name="checkCircle" size={18} /> {submitting ? "Enviando..." : "Enviar a validación"}</button></footer>
        </form>
      </section>
    </div>
  );
}

function TicketDetailModal({ currentUser, isLoading, onAttach, onClose, onReassign, onRelease, onResolve, onTake, onValidate, teams, ticket, users }) {
  const [actionError, setActionError] = useState("");
  const [acting, setActing] = useState(false);
  const [attachFile, setAttachFile] = useState(null);
  const [attachError, setAttachError] = useState("");
  const [uploading, setUploading] = useState(false);
  const attachList = attachFile ? (Array.isArray(attachFile) ? attachFile : [attachFile]) : [];
  const [attachPreviews, setAttachPreviews] = useState([]);
  useEffect(() => {
    const urls = attachList.map((f) => URL.createObjectURL(f));
    setAttachPreviews(urls);
    return () => urls.forEach((u) => URL.revokeObjectURL(u));
  }, [attachFile]);

  function removeAttachFile(index) {
    const list = attachList.filter((_, i) => i !== index);
    setAttachFile(list.length === 0 ? null : list.length === 1 ? list[0] : list);
    setAttachError("");
  }
  const [reassignTeam, setReassignTeam] = useState("");
  const [rejectComment, setRejectComment] = useState("");
  const [showReject, setShowReject] = useState(false);
  const canTake = currentUser.role === "SOPORTE" && ["ABIERTO", "ASIGNADO"].includes(ticket.statusCode);
  const canRelease = ["ASIGNADO", "EN_PROCESO"].includes(ticket.statusCode) && (ticket.assigneeId === currentUser.id || currentUser.role === "ADMIN" || (currentUser.role === "SUPERVISOR" && (currentUser.groups || []).map((g) => g.code).includes(ticket.groupCode)));
  const canResolve = currentUser.role === "SOPORTE" && ticket.statusCode === "EN_PROCESO";
  const canValidate = currentUser.role !== "SOPORTE" && ticket.statusCode === "VALIDACION";
  const canAttach = currentUser.is_administrator || currentUser.role === "ADMIN" || ticket.requester === currentUser.name || (currentUser.role === "SOPORTE" && currentUser.team === ticket.team);
  const canReassign = ticket.statusCode !== "CERRADO" && ["DESPACHADOR", "SOPORTE", "SUPERVISOR", "ADMIN"].includes(currentUser.role) && (currentUser.role === "ADMIN" || (currentUser.groups || []).map((g) => g.code).includes(ticket.groupCode));
  const candidates = (users || []).filter((u) => u.is_active && !u.is_locked && u.role === "SOPORTE" && (u.groupName || "").split(",").map((s) => s.trim()).includes(ticket.team));

  async function runAction(action, accepted) {
    setActing(true);
    setActionError("");
    try {
      await action(ticket, accepted);
    } catch (error) {
      setActionError(error.message || "No fue posible actualizar el ticket.");
      setActing(false);
    }
  }

  function pickAttachFiles(files, append = false) {
    if (!files.length) return;
    const current = append ? (Array.isArray(attachFile) ? attachFile : attachFile ? [attachFile] : []) : [];
    const combined = [...current, ...files];
    if (ticket.attachments.length + combined.length > 5) {
      setAttachError(`Máximo 5 imágenes por ticket (ya tienes ${ticket.attachments.length}).`);
      return;
    }
    for (const f of files) {
      if (f.size > 5 * 1024 * 1024) {
        setAttachError(`"${f.name}" supera 5 MB.`);
        return;
      }
      if (!["image/jpeg", "image/jpg", "image/png"].includes(f.type) && !/\.jpe?g$|\.png$/i.test(f.name)) {
        setAttachError(`"${f.name}" no es JPG/PNG.`);
        return;
      }
    }
    setAttachError("");
    setAttachFile(combined.length === 1 ? combined[0] : combined);
  }

  function handleAttach(event) {
    pickAttachFiles(Array.from(event.target.files || []));
  }

  function handleAttachPaste(event) {
    const files = Array.from(event.clipboardData?.files || []).filter((f) => f.type.startsWith("image/"));
    if (!files.length) return;
    event.preventDefault();
    pickAttachFiles(files, true);
  }

  async function submitAttach(event) {
    event.preventDefault();
    if (!attachFile) {
      setAttachError("Selecciona una imagen.");
      return;
    }
    setUploading(true);
    setAttachError("");
    try {
      const files = Array.isArray(attachFile) ? attachFile : [attachFile];
      for (const f of files) await onAttach(ticket, f);
      setAttachFile(null);
      if (event.target) event.target.reset();
    } catch (error) {
      setAttachError(error.message || "No fue posible adjuntar la imagen.");
    } finally {
      setUploading(false);
    }
  }

  return (
    <div className="modal-backdrop detail-backdrop" role="presentation" onMouseDown={onClose}>
      <section className="ticket-detail-modal" role="dialog" aria-modal="true" aria-labelledby="ticket-detail-title" onMouseDown={(event) => event.stopPropagation()}>
        <header className="detail-header">
          <div><span className="ticket-id">{ticket.id}</span><h2 id="ticket-detail-title">{ticket.title}</h2><p>{ticket.category} · Creado {ticket.created}</p></div>
          <div className="detail-header-actions"><span className={`status-pill ${statusClass[ticket.status]}`}>{ticket.status}</span><button className="icon-button" type="button" aria-label="Cerrar detalle" onClick={onClose}><Icon name="close" /></button></div>
        </header>
        {isLoading ? <div className="detail-loading"><span className="loading-mark"><i /><i /><i /></span><p>Cargando historial del ticket...</p></div> : <div className="ticket-detail-content">
          <div className="detail-main">
            <section className="detail-section"><div className="detail-section-heading"><span className="detail-label">Datos de la solicitud</span><span>{ticket.identificador}</span></div><div className="profile-details" style={{ padding: 0, marginTop: "10px" }}>{ticket.identificador && <div className="profile-row"><span>Contrato / OT</span><span>{ticket.identificador}</span></div>}{ticket.cliente && <div className="profile-row"><span>Cliente</span><span>{ticket.cliente}</span></div>}{ticket.nodo && <div className="profile-row"><span>Nodo</span><span>{ticket.nodo}</span></div>}{ticket.tipoSolicitud && <div className="profile-row"><span>Tipo</span><span>{ticket.tipoSolicitud}</span></div>}</div></section>
            <section className="detail-section"><span className="detail-label">Descripción reportada</span><p className="detail-description">{ticket.description || "Sin descripción adicional."}</p></section>
            {ticket.resolutionNotes && <section className="detail-section solution-detail"><span className="detail-label"><Icon name="checkCircle" size={15} /> Solución registrada</span><p>{ticket.resolutionNotes}</p></section>}
            <section className="detail-section"><div className="detail-section-heading"><span className="detail-label">Evidencia adjunta</span><span>{ticket.attachments.length}/5</span></div>{ticket.attachments.length ? <div className="attachment-list">{ticket.attachments.map((attachment) => <a href={attachment.url} key={attachment.id} rel="noreferrer" target="_blank"><img src={attachment.url} alt={attachment.original_name} style={{ width: "52px", height: "52px", objectFit: "cover", borderRadius: "6px", flex: "0 0 auto" }} onError={(e) => { e.target.style.display = "none"; }} /><span><strong>{attachment.original_name}</strong><small>{Math.max(1, Math.round(attachment.size / 1024))} KB · {formatDateTime(attachment.created_at)}</small></span><Icon name="arrowRight" size={15} /></a>)}</div> : <p className="detail-empty">No hay evidencia adjunta.</p>}{canAttach && <form className="detail-attach-form" onSubmit={submitAttach} onPaste={handleAttachPaste}><label className={`upload-box small ${attachError ? "has-error" : ""}`}><input type="file" accept=".jpg,.jpeg,.png" multiple onChange={handleAttach} /><Icon name="upload" size={16} /><span>{attachList.length ? `${attachList.length} ${attachList.length === 1 ? "imagen" : "imágenes"}` : "Adjuntar o pegar (Ctrl+V)"}</span></label><button className="secondary-button" disabled={uploading || !attachFile} type="submit">{uploading ? "Subiendo..." : "Adjuntar"}</button></form>}{attachList.length > 0 && <div className="attach-preview-grid">{attachList.map((f, i) => <div className="attach-preview" key={`${f.name}-${f.size}-${i}`}><img src={attachPreviews[i]} alt={f.name} /><span title={f.name}>{f.name}</span><button type="button" aria-label={`Quitar ${f.name}`} onClick={() => removeAttachFile(i)}>✕</button></div>)}</div>}{attachError && <p className="form-submit-error" role="alert"><Icon name="alert" size={14} /> {attachError}</p>}</section>
            <section className="detail-section history-section"><div className="detail-section-heading"><span className="detail-label">Historial del ticket</span><span>{ticket.events.length}</span></div>{ticket.events.length ? <ol className="ticket-history">{ticket.events.map((event) => <li key={event.id}><span className="history-dot" /><div><strong>{event.event_label}</strong><p>{event.comment || `${event.actor?.name || "Sistema"} actualizó el ticket.`}</p><small>{event.actor?.name || "Sistema"} · {formatDateTime(event.created_at)}</small></div></li>)}</ol> : <p className="detail-empty">Aún no hay eventos registrados.</p>}</section>
          </div>
          <aside className="detail-sidebar">
            <div className="detail-meta"><span className="detail-label">Prioridad</span><span className={`priority-pill ${priorityClass[ticket.priority]}`}>{ticket.priority}</span></div>
            <div className="detail-meta"><span className="detail-label">SLA restante</span><strong className={`sla-time ${ticket.slaTone}`}><i /> {ticket.sla}</strong><small>Vence: {formatDateTime(ticket.slaDueAt)}</small></div>
            <div className="detail-meta"><span className="detail-label">Despachador</span><strong>{ticket.requester}</strong><small>{ticket.originTeam}</small></div>
            <div className="detail-meta"><span className="detail-label">Atiende</span><strong>{ticket.assignee}</strong><small>{ticket.team}</small></div>
            {(canTake || canRelease || canResolve || canValidate) && <div className="detail-actions">
              {canTake && <button className="primary-button" disabled={acting} type="button" onClick={() => runAction(onTake)}>Tomar ticket</button>}
              {canRelease && <button className="secondary-button" disabled={acting} type="button" onClick={() => runAction(onRelease)}>Liberar a bandeja</button>}
              {canResolve && <button className="primary-button" type="button" onClick={() => onResolve(ticket)}>Registrar solución</button>}
              {canValidate && <>
                <button className="primary-button" disabled={acting} type="button" onClick={() => runAction((t) => onValidate(t, true), true)}><Icon name="check" size={17} /> Aprobar solución</button>
                {!showReject ? <button className="secondary-button" disabled={acting} type="button" onClick={() => setShowReject(true)}>Rechazar y devolver</button> : <div style={{ display: "grid", gap: "6px", marginTop: "8px", width: "100%" }}><textarea value={rejectComment} onChange={(e) => setRejectComment(e.target.value)} placeholder="Motivo del rechazo (obligatorio) — explica qué falta o por qué se devuelve" rows="3" style={{ width: "100%", border: "1px solid var(--line-strong)", borderRadius: "6px", padding: "8px", fontSize: "11px" }} /><div style={{ display: "flex", gap: "6px" }}><button className="secondary-button" disabled={acting || !rejectComment.trim()} type="button" onClick={async () => { setActing(true); setActionError(""); try { await onValidate(ticket, false, rejectComment); setShowReject(false); setRejectComment(""); } catch (e) { setActionError(e.message || "No se pudo rechazar."); } finally { setActing(false); } }}>Confirmar rechazo</button><button className="secondary-button" type="button" onClick={() => { setShowReject(false); setRejectComment(""); }}>Cancelar</button></div></div>}
              </>}
            </div>}
            {canReassign && <div className="detail-meta" style={{ marginTop: "14px" }}><span className="detail-label">Reasignar a persona del grupo</span><div style={{ display: "flex", gap: "6px", marginTop: "6px" }}><select value={reassignTeam} onChange={(e) => setReassignTeam(e.target.value)} style={{ flex: 1, height: "34px", border: "1px solid var(--line-strong)", borderRadius: "6px", padding: "0 8px", fontSize: "11px" }}><option value="">Seleccionar persona</option>{candidates.map((u) => <option key={u.id} value={u.id}>{u.name}</option>)}</select><button className="secondary-button" disabled={acting || !reassignTeam} type="button" style={{ minHeight: "34px" }} onClick={async () => { setActing(true); setActionError(""); try { await onReassign(ticket, Number(reassignTeam)); setReassignTeam(""); } catch (e) { setActionError(e.message || "No se pudo reasignar."); } finally { setActing(false); } }}>Mover</button></div>{candidates.length === 0 && <small style={{ color: "var(--quiet)", fontSize: "10px" }}>Sin agentes en este grupo.</small>}</div>}
            {actionError && <p className="detail-action-error" role="alert"><Icon name="alert" size={15} /> {actionError}</p>}
          </aside>
        </div>}
      </section>
    </div>
  );
}

function NewTicketModal({ onClose, onCreate, onOpenTicket, session }) {
  const [form, setForm] = useState({ kind: "", service: "", tipoId: "", identificador: "", cliente: "", nodo: "", title: "", description: "" });
  const [catalog, setCatalog] = useState([]);
  const [attachment, setAttachment] = useState(null);
  const [attachmentError, setAttachmentError] = useState("");
  const [submitError, setSubmitError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [duplicate, setDuplicate] = useState(null);
  const [checking, setChecking] = useState(false);
  const [idError, setIdError] = useState("");
  const [clientError, setClientError] = useState("");
  const attachList = attachment ? (Array.isArray(attachment) ? attachment : [attachment]) : [];
  const [previews, setPreviews] = useState([]);
  useEffect(() => {
    const urls = attachList.map((f) => URL.createObjectURL(f));
    setPreviews(urls);
    return () => urls.forEach((u) => URL.revokeObjectURL(u));
  }, [attachment]);

  function removeAttachment(index) {
    const list = attachList.filter((_, i) => i !== index);
    setAttachment(list.length === 0 ? null : list.length === 1 ? list[0] : list);
    setAttachmentError("");
  }

  function validateIdentificador(value) {
    if (!value.trim()) { setIdError(""); return false; }
    if (!/^[0-9]+$/.test(value.trim())) { setIdError("Contrato / OT solo admite números."); return false; }
    setIdError("");
    return true;
  }

  function validateCliente(value) {
    if (!value.trim()) { setClientError(""); return false; }
    if (!/^[A-Za-zÁÉÍÓÚÜÑáéíóúüñ0-9\s.\-,&()']+$/.test(value.trim())) { setClientError("Solo letras, números, espacios y . , - & ( )."); return false; }
    setClientError("");
    return true;
  }

  useEffect(() => {
    getRequestTypes({ active: "1" }).then((payload) => setCatalog(payload.results || payload)).catch(() => setCatalog([]));
  }, []);

  const services = [...new Set(catalog.filter((t) => !form.kind || t.kind === form.kind).map((t) => t.service))];
  const options = catalog.filter((t) => (!form.kind || t.kind === form.kind) && (!form.service || t.service === form.service));

  function updateField(event) {
    const { name, value } = event.target;
    setForm((currentForm) => {
      const next = { ...currentForm, [name]: value };
      if (name === "kind") { next.service = ""; next.tipoId = ""; }
      if (name === "service") { next.tipoId = ""; }
      if (name === "tipoId") {
        const sel = options.find((o) => String(o.id) === String(value));
        if (sel) next.title = sel.name;
      }
      return next;
    });
    if (name === "identificador") setDuplicate(null);
  }

  async function checkDuplicate() {
    const value = form.identificador.trim();
    if (!value || !validateIdentificador(value)) return;
    setChecking(true);
    try {
      const payload = await checkOpenTicket(value);
      const results = payload.results || payload;
      setDuplicate(results.length ? results[0] : null);
    } catch {
      setDuplicate(null);
    } finally {
      setChecking(false);
    }
  }

  function pickFiles(files, append = false) {
    if (!files.length) return;
    const current = append ? (Array.isArray(attachment) ? attachment : attachment ? [attachment] : []) : [];
    const combined = [...current, ...files];
    if (combined.length > 5) {
      setAttachmentError(`Máximo 5 imágenes (ya tienes ${current.length}).`);
      return;
    }
    for (const f of files) {
      if (f.size > 5 * 1024 * 1024) {
        setAttachmentError(`"${f.name}" supera 5 MB.`);
        return;
      }
      if (!["image/jpeg", "image/jpg", "image/png"].includes(f.type) && !/\.jpe?g$|\.png$/i.test(f.name)) {
        setAttachmentError(`"${f.name}" no es JPG/PNG.`);
        return;
      }
    }
    setAttachment(combined.length === 1 ? combined[0] : combined);
    setAttachmentError("");
  }

  function handleAttachment(event) {
    pickFiles(Array.from(event.target.files || []));
  }

  function handlePaste(event) {
    const files = Array.from(event.clipboardData?.files || []).filter((f) => f.type.startsWith("image/"));
    if (!files.length) return;
    event.preventDefault();
    pickFiles(files, true);
  }

  async function submit(event) {
    event.preventDefault();
    const idOk = validateIdentificador(form.identificador);
    const clientOk = validateCliente(form.cliente);
    if (!idOk || !clientOk) {
      setSubmitError("Revisa los campos marcados en rojo.");
      return;
    }
    const idValue = form.identificador.trim();
    const clientValue = form.cliente.trim();
    setSubmitting(true);
    setSubmitError("");
    try {
      await onCreate({
        title: form.title,
        description: form.description,
        category: form.service,
        priority: "MEDIA",
        identificador: idValue,
        cliente_nombre: clientValue,
        nodo: form.nodo.trim(),
        tipo_solicitud: form.tipoId ? Number(form.tipoId) : null,
        attachment,
      });
    } catch (error) {
      setSubmitError(error.message || "No fue posible crear el ticket.");
      setSubmitting(false);
    }
  }

  const idLabel = form.kind === "CLIENTE" ? "Contrato" : form.kind === "TECNICO" ? "OT" : "Contrato / OT";
  const canFillDetails = Boolean(form.kind && form.service && form.tipoId);

  return (
    <div className="modal-backdrop" role="presentation" onMouseDown={onClose}>
      <section className="ticket-modal" role="dialog" aria-modal="true" aria-labelledby="new-ticket-title" onMouseDown={(event) => event.stopPropagation()}>
        <header className="modal-header"><div><p className="eyebrow">Nueva solicitud</p><h2 id="new-ticket-title">Crear ticket de soporte</h2><p>Elige el tipo de solicitud y completa los campos.</p></div><button className="icon-button" type="button" aria-label="Cerrar formulario" onClick={onClose}><Icon name="close" /></button></header>
        <form onSubmit={submit}>
          <div className="auto-assignment"><Icon name="shield" size={19} /><div><span>Enrutamiento automático</span><strong>{session.groupsLabel || session.group} · Soporte Despacho</strong></div></div>
          <div className="form-grid">
            <label className="field"><span>Tipo de solicitud <b>*</b></span><select required name="kind" value={form.kind} onChange={updateField}><option value="">Seleccionar</option><option value="CLIENTE">Solicitud de Soporte Cliente</option><option value="TECNICO">Soporte Al Tecnico</option></select></label>
            <label className="field"><span>Tipo de servicio <b>*</b></span><select required name="service" value={form.service} onChange={updateField} disabled={!form.kind}><option value="">Seleccionar</option>{services.map((s) => <option key={s} value={s}>{s}</option>)}</select></label>
            <label className="field field-wide"><span>Solicitud específica <b>*</b></span><select required name="tipoId" value={form.tipoId} onChange={updateField} disabled={!form.service}><option value="">Seleccionar</option>{options.map((o) => <option key={o.id} value={o.id}>{o.name}</option>)}</select></label>
            <label className="field"><span>{idLabel} <b>*</b></span><input required name="identificador" inputMode="numeric" value={form.identificador} onChange={updateField} onBlur={(e) => { validateIdentificador(e.target.value); checkDuplicate(); }} disabled={!canFillDetails} placeholder={form.kind === "TECNICO" ? "Solo números" : "Solo números"} />{idError && <small className="field-error">{idError}</small>}</label>
            <label className="field"><span>Prioridad</span><input disabled value="Media (automática)" /></label>
            <label className="field"><span>Nombre Cliente <b>*</b></span><input required name="cliente" value={form.cliente} onChange={updateField} onBlur={(e) => validateCliente(e.target.value)} disabled={!canFillDetails} placeholder="Nombre del cliente" />{clientError && <small className="field-error">{clientError}</small>}</label>
            <label className="field"><span>Nodo <b>*</b></span><input required name="nodo" value={form.nodo} onChange={updateField} disabled={!canFillDetails} placeholder="Nodo" /></label>
            <label className="field field-wide"><span>Comentarios <b>*</b></span><textarea required name="description" value={form.description} onChange={updateField} disabled={!canFillDetails} rows="4" placeholder="Detalle del caso, síntomas, ubicación o pasos ya realizados." /></label>
          </div>
          {checking && <p className="form-info" role="status">Verificando {idLabel}...</p>}
          {duplicate && <p className="form-submit-error" role="alert"><Icon name="alert" size={16} /> Ya existe {duplicate.reference} abierto con este {idLabel} ({duplicate.status_label}). <button type="button" className="text-button" onClick={() => onOpenTicket && onOpenTicket(duplicate.id)}>Ver ticket y documentarlo ahí</button></p>}
          <div className="attachment-section" onPaste={handlePaste}><div><span>Adjuntar evidencia</span><small>JPG o PNG, máximo 5 MB, hasta 5 imágenes — o pega con Ctrl+V</small></div><label className={`upload-box ${attachmentError ? "has-error" : ""}`}><input type="file" accept=".jpg,.jpeg,.png" multiple onChange={handleAttachment} /><Icon name="upload" size={20} /><span>{attachList.length ? `${attachList.length} ${attachList.length === 1 ? "imagen" : "imágenes"}` : "Seleccionar o pegar imagen"}</span></label>{attachmentError && <p className="field-error">{attachmentError}</p>}</div>
          {attachList.length > 0 && <div className="attach-preview-grid">{attachList.map((f, i) => <div className="attach-preview" key={`${f.name}-${f.size}-${i}`}><img src={previews[i]} alt={f.name} /><span title={f.name}>{f.name}</span><button type="button" aria-label={`Quitar ${f.name}`} onClick={() => removeAttachment(i)}>✕</button></div>)}</div>}
          {submitError && <p className="form-submit-error" role="alert"><Icon name="alert" size={16} /> {submitError}</p>}
          <footer className="modal-actions"><button className="secondary-button" disabled={submitting} type="button" onClick={onClose}>Cancelar</button><button className="primary-button" disabled={submitting} type="submit"><Icon name="ticket" size={18} /> {submitting ? "Enviando..." : "Enviar a soporte"}</button></footer>
        </form>
      </section>
    </div>
  );
}

function Toast({ message, onClose }) {
  return <div className="toast" role="status"><span><Icon name="checkCircle" size={19} /></span><p>{message}</p><button type="button" aria-label="Cerrar mensaje" onClick={onClose}><Icon name="close" size={16} /></button></div>;
}

function LoginScreen({ brand, onLogin, onToggleTheme, theme }) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [showReset, setShowReset] = useState(false);
  const [resetEmail, setResetEmail] = useState("");
  const [resetError, setResetError] = useState("");
  const [resetSuccess, setResetSuccess] = useState("");
  const [resetting, setResetting] = useState(false);
  const [requestInfo, setRequestInfo] = useState("");

  async function submit(event) {
    event.preventDefault();
    setError("");
    setSubmitting(true);
    try {
      await onLogin({ email: email.trim().toLowerCase(), password });
    } catch (loginError) {
      setError(loginError.message || "No fue posible iniciar sesión.");
      setSubmitting(false);
    }
  }

  async function submitResetRequest(event) {
    event.preventDefault();
    setResetError("");
    setResetSuccess("");
    setRequestInfo("");
    if (!resetEmail.trim()) { setResetError("Ingresa el correo de la cuenta."); return; }
    setResetting(true);
    try {
      const res = await requestPasswordReset(resetEmail.trim().toLowerCase());
      setResetSuccess(res.detail || "Se envió un correo con el enlace para restablecer tu contraseña. Revisa tu bandeja de entrada (válido 1 hora).");
      if (res.debug_link) {
        setRequestInfo(`Modo desarrollo: ${res.debug_link} (también en logs del contenedor api)`);
      }
    } catch (e) {
      setResetError(e.message || "No fue posible enviar el correo.");
    } finally {
      setResetting(false);
    }
  }

  function openReset() {
    setResetEmail(email);
    setResetError("");
    setResetSuccess("");
    setRequestInfo("");
    setShowReset(true);
  }

  return (
    <main className="login-screen app-shell" data-brand={brand} data-theme={theme}>
      <section className="login-intro" aria-label="Información del sistema">
        <a className="brand login-brand" href="#inicio">
          <span className="brand-mark" aria-hidden="true"><span /><span /><span /></span>
          <span><strong>Soporte Despacho</strong><small>Tigo · Centro de control</small></span>
        </a>
        <div className="login-intro-content">
          <p className="eyebrow">Soporte técnico conectado</p>
          <h1>Soporte Despacho</h1>
          <p>Centro de control Tigo.</p>
        </div>
      </section>

      <section className="login-form-area">
        <div className="login-form-top"><span>Acceso seguro</span><button className="icon-button" type="button" aria-label={theme === "light" ? "Activar tema oscuro" : "Activar tema claro"} onClick={onToggleTheme}><Icon name={theme === "light" ? "moon" : "sun"} size={19} /></button></div>
        <form className="login-card" onSubmit={submit}>
          <p className="eyebrow">Bienvenido</p>
          <h2>Inicia sesión</h2>
          <p className="login-copy">Ingresa con el perfil asignado para acceder a tu operación.</p>
          <label className="login-field"><span>Correo institucional</span><input autoComplete="email" required type="email" value={email} onChange={(event) => setEmail(event.target.value)} placeholder="nombre@empresa.com" /></label>
          <label className="login-field"><span>Contraseña</span><input autoComplete="current-password" required type="password" value={password} onChange={(event) => setPassword(event.target.value)} placeholder="Tu contraseña" /></label>
          <div className="login-forgot"><button type="button" className="text-button" onClick={openReset}>¿Olvidaste tu contraseña?</button></div>
          {error && <p className="login-error" role="alert"><Icon name="alert" size={16} /> {error}</p>}
          <button className="primary-button login-submit" disabled={submitting} type="submit">{submitting ? "Verificando acceso..." : "Ingresar al centro de control"} <Icon name="arrowRight" size={18} /></button>
        </form>
      </section>
      {showReset && <div className="modal-backdrop" role="presentation" onMouseDown={() => setShowReset(false)}><section className="ticket-modal user-modal" role="dialog" aria-modal="true" aria-labelledby="reset-title" onMouseDown={(e) => e.stopPropagation()}><header className="modal-header"><div><p className="eyebrow">Recuperar acceso</p><h2 id="reset-title">Restablecer contraseña</h2><p>Te enviaremos un correo con un enlace seguro (válido 1 hora). Desde el correo accederás al módulo exclusivo para definir tu nueva clave.</p></div><button className="icon-button" type="button" aria-label="Cerrar" onClick={() => setShowReset(false)}><Icon name="close" /></button></header><form onSubmit={submitResetRequest}><div className="form-grid user-form-grid"><label className="field field-wide"><span>Correo institucional <b>*</b></span><input autoFocus required type="email" value={resetEmail} onChange={(e) => setResetEmail(e.target.value)} placeholder="nombre@empresa.com" /></label></div>{resetError && <p className="form-submit-error" role="alert"><Icon name="alert" size={16} /> {resetError}</p>}{resetSuccess && <p className="form-success" role="status"><Icon name="checkCircle" size={16} /> {resetSuccess}</p>}{requestInfo && <p className="form-info" role="status"><Icon name="shield" size={16} /> {requestInfo}</p>}<footer className="modal-actions"><button className="secondary-button" type="button" onClick={() => setShowReset(false)}>Cerrar</button><button className="primary-button" disabled={resetting} type="submit"><Icon name="shield" size={18} /> {resetting ? "Enviando..." : "Enviar correo"}</button></footer></form></section></div>}
    </main>
  );
}

function PasswordResetPage({ brand, theme, onToggleTheme }) {
  const params = new URLSearchParams(typeof window !== "undefined" ? window.location.search : "");
  const initialUid = params.get("uid") || "";
  const initialToken = params.get("token") || "";
  const [email, setEmail] = useState("");
  const [uid, setUid] = useState(initialUid);
  const [token, setToken] = useState(initialToken);
  const [newPassword, setNewPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const hasLink = Boolean(initialUid && initialToken);

  async function submit(e) {
    e.preventDefault();
    setError("");
    setSuccess("");
    if (!uid.trim() || !token.trim()) { setError("El enlace debe contener uid y token. Solicita un nuevo correo si es necesario."); return; }
    if (newPassword.length < 8) { setError("La nueva contraseña debe tener al menos 8 caracteres."); return; }
    if (newPassword !== confirm) { setError("Las contraseñas no coinciden."); return; }
    setSubmitting(true);
    try {
      await confirmPasswordReset({ email: "", uid: uid.trim(), token: token.trim(), newPassword });
      setSuccess("Clave restablecida correctamente. Ya puedes iniciar sesión.");
    } catch (err) {
      setError(err.message || "No fue posible restablecer la clave.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="login-screen app-shell" data-brand={brand} data-theme={theme}>
      <section className="login-intro" aria-label="Información del sistema">
        <a className="brand login-brand" href="/"><span className="brand-mark" aria-hidden="true"><span /><span /><span /></span><span><strong>Soporte Despacho</strong><small>Tigo · Centro de control</small></span></a>
        <div className="login-intro-content">
          <p className="eyebrow">Acceso seguro</p>
          <h1>Restablece tu clave.</h1>
          <p>Este módulo solo permite definir una nueva contraseña mediante el enlace enviado a tu correo. No expone otras acciones del sistema.</p>
          {!hasLink && <p className="form-info"><Icon name="alert" size={16} /> Abre el enlace recibido por correo para autocompletar el token. Si no tienes el enlace, vuelve al login y solicita uno nuevo.</p>}
        </div>
      </section>
      <section className="login-form-area">
        <div className="login-form-top"><span>Módulo exclusivo</span><button className="icon-button" type="button" aria-label={theme === "light" ? "Activar tema oscuro" : "Activar tema claro"} onClick={onToggleTheme}><Icon name={theme === "light" ? "moon" : "sun"} size={19} /></button></div>
        {success ? (
          <div className="login-card" style={{ textAlign: "center", padding: "32px 24px" }}>
            <span style={{ display: "inline-grid", placeItems: "center", width: "56px", height: "56px", borderRadius: "50%", background: "var(--accent-soft)", color: "var(--accent)", marginBottom: "16px" }}><Icon name="checkCircle" size={28} /></span>
            <h2>Clave restablecida con éxito</h2>
            <p className="login-copy" style={{ marginTop: "8px" }}>Tu contraseña fue actualizada correctamente. Ya puedes ingresar con la nueva clave. Este enlace ya no es válido.</p>
            <a href="/" className="primary-button login-submit" style={{ marginTop: "20px", textDecoration: "none" }}>Ir al inicio de sesión</a>
          </div>
        ) : (
          <form className="login-card" onSubmit={submit}>
            <p className="eyebrow">Restablecer</p>
            <h2>Nueva contraseña</h2>
            <p className="login-copy">Define tu nueva clave. El enlace es válido por 1 hora y de un solo uso.</p>
            <input type="hidden" value={uid} />
            <input type="hidden" value={token} />
            <label className="login-field"><span>Nueva contraseña</span><input required minLength="8" type="password" value={newPassword} onChange={(e) => setNewPassword(e.target.value)} placeholder="Mínimo 8 caracteres" /></label>
            <label className="login-field"><span>Confirmar contraseña</span><input required minLength="8" type="password" value={confirm} onChange={(e) => setConfirm(e.target.value)} placeholder="Repite la clave" /></label>
            {error && <p className="login-error" role="alert"><Icon name="alert" size={16} /> {error}</p>}
            <button className="primary-button login-submit" disabled={submitting} type="submit">{submitting ? "Guardando..." : "Restablecer clave"}</button>
            <a className="text-button" href="/" style={{ display: "inline-flex", marginTop: "12px", justifyContent: "center", width: "100%", textDecoration: "none" }}>Volver al inicio de sesión</a>
          </form>
        )}
      </section>
    </main>
  );
}

function ProfileModal({ onClose, tickets, user }) {
  const created = tickets.filter((t) => t.requester === user.name).length;
  const assigned = tickets.filter((t) => t.assignee === user.name).length;
  const active = tickets.filter((t) => (t.requester === user.name || t.assignee === user.name) && t.statusCode !== "CERRADO").length;
  return (
    <div className="modal-backdrop" role="presentation" onMouseDown={onClose}>
      <section className="ticket-modal profile-modal" role="dialog" aria-modal="true" aria-labelledby="profile-title" onMouseDown={(e) => e.stopPropagation()}>
        <div className="profile-header">
          <div className={`avatar ${user.avatarClass}`} style={{ width: "48px", height: "48px", fontSize: "14px" }}>{user.initials}</div>
          <div><strong id="profile-title">{user.name}</strong><span>{user.roleLabel} · {user.team}</span><small>{user.email} · {user.group}</small></div>
        </div>
        <div className="profile-details">
          <div className="profile-row"><span>Usuario</span><span>{user.username}</span></div>
          <div className="profile-row"><span>Grupos</span><span>{user.groupsLabel || user.group}</span></div>
          <div className="profile-row"><span>Estado</span><span>{user.is_locked ? "Bloqueada" : "Activa"}</span></div>
        </div>
        <div className="profile-stats">
          <div className="profile-stat"><strong>{created}</strong><span>Creados</span></div>
          <div className="profile-stat"><strong>{assigned}</strong><span>Asignados</span></div>
          <div className="profile-stat"><strong>{active}</strong><span>Activos</span></div>
        </div>
        <footer className="modal-actions" style={{ marginTop: "16px" }}><button className="secondary-button" type="button" onClick={onClose}>Cerrar</button></footer>
      </section>
    </div>
  );
}

export default App;
