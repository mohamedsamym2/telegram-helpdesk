// IT Support Helpdesk v2.0 - English Client Application
// Features: Ticket Assignment, Priority & SLA Tracking, Team Leaderboard, and Analytics Reports

let allTickets = [];
let currentTicketId = null;
let currentFilter = 'all'; // 'all', 'open', 'in_progress', 'closed'
let currentQueueFilter = 'all'; // 'all', 'me', 'unassigned'
let searchQuery = '';
let soundEnabled = localStorage.getItem('sound_enabled') !== 'false';
let socket = null;
let currentUser = null;
let cachedUsers = [];
let activeReportPreset = 'this_month';
let slaTickTimer = null;

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    updateSoundUI();
    checkAuth();

    // Listen for Ctrl+Enter in textarea
    const replyTextarea = document.getElementById('reply-text');
    if (replyTextarea) {
        replyTextarea.addEventListener('keydown', (e) => {
            if (e.ctrlKey && e.key === 'Enter') {
                e.preventDefault();
                document.getElementById('reply-form').requestSubmit();
            }
        });
    }
});

// Authentication System
async function checkAuth() {
    try {
        const res = await fetch('/api/auth/me');
        const data = await res.json();
        if (data.authenticated) {
            currentUser = data.username;
            document.getElementById('login-overlay').classList.add('hidden');
            document.getElementById('nav-username').textContent = currentUser;
            initializeApp();
        } else {
            document.getElementById('login-overlay').classList.remove('hidden');
        }
    } catch (e) {
        document.getElementById('login-overlay').classList.remove('hidden');
    }
}

async function handleLogin(e) {
    e.preventDefault();
    const user = document.getElementById('login-username').value.trim();
    const pass = document.getElementById('login-password').value;
    const btn = document.getElementById('login-btn');
    const errBox = document.getElementById('login-error');
    const errText = document.getElementById('login-error-text');

    btn.disabled = true;
    btn.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Signing In...`;
    errBox.classList.add('hidden');

    try {
        const res = await fetch('/api/auth/login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username: user, password: pass })
        });
        const data = await res.json();
        if (res.ok) {
            currentUser = data.username;
            document.getElementById('nav-username').textContent = currentUser;
            document.getElementById('login-overlay').classList.add('hidden');
            initializeApp();
        } else {
            errText.textContent = data.detail || 'Invalid username or password';
            errBox.classList.remove('hidden');
        }
    } catch (err) {
        errText.textContent = 'Server connection error';
        errBox.classList.remove('hidden');
    } finally {
        btn.disabled = false;
        btn.innerHTML = `<span>Sign In</span><i class="fa-solid fa-arrow-right text-xs"></i>`;
    }
}

async function handleLogout() {
    if (!confirm('Are you sure you want to sign out?')) return;
    try {
        await fetch('/api/auth/logout', { method: 'POST' });
    } catch(e) {}
    location.reload();
}

function initializeApp() {
    checkBotStatus();
    loadTeamUsers();
    loadTickets();
    connectWebSocket();

    if (!slaTickTimer) {
        slaTickTimer = setInterval(updateAllSlaBadges, 30000);
    }
}

// Sound Generator using Web Audio API
function playDing() {
    if (!soundEnabled) return;
    try {
        const ctx = new (window.AudioContext || window.webkitAudioContext)();
        const now = ctx.currentTime;

        const osc1 = ctx.createOscillator();
        const gain1 = ctx.createGain();
        osc1.type = 'sine';
        osc1.frequency.setValueAtTime(587.33, now); // D5
        gain1.gain.setValueAtTime(0.2, now);
        gain1.gain.exponentialRampToValueAtTime(0.001, now + 0.35);
        osc1.connect(gain1);
        gain1.connect(ctx.destination);
        osc1.start(now);
        osc1.stop(now + 0.35);

        const osc2 = ctx.createOscillator();
        const gain2 = ctx.createGain();
        osc2.type = 'sine';
        osc2.frequency.setValueAtTime(880, now + 0.12); // A5
        gain2.gain.setValueAtTime(0.25, now + 0.12);
        gain2.gain.exponentialRampToValueAtTime(0.001, now + 0.6);
        osc2.connect(gain2);
        gain2.connect(ctx.destination);
        osc2.start(now + 0.12);
        osc2.stop(now + 0.6);
    } catch (e) {
        console.warn('Audio chime error:', e);
    }
}

function toggleSound() {
    soundEnabled = !soundEnabled;
    localStorage.setItem('sound_enabled', soundEnabled);
    updateSoundUI();
    if (soundEnabled) playDing();
}

function updateSoundUI() {
    const icon = document.getElementById('sound-icon');
    const btn = document.getElementById('sound-toggle-btn');
    if (soundEnabled) {
        icon.className = 'fa-solid fa-volume-high text-indigo-400';
        btn.classList.add('border-indigo-500/40');
    } else {
        icon.className = 'fa-solid fa-volume-xmark text-slate-500';
        btn.classList.remove('border-indigo-500/40');
    }
}

// Check Bot Status
async function checkBotStatus() {
    const dot = document.getElementById('bot-status-dot');
    const text = document.getElementById('bot-status-text');
    try {
        const res = await fetch('/api/status');
        const data = await res.json();
        
        if (data.configured && data.bot_running) {
            dot.className = 'w-2.5 h-2.5 rounded-full bg-emerald-400 shadow-sm shadow-emerald-400/50';
            text.textContent = `@${data.bot.username || 'Bot'} (Live Online)`;
            text.className = 'text-emerald-300 font-semibold text-[11px]';
        } else if (data.configured && !data.bot_running) {
            dot.className = 'w-2.5 h-2.5 rounded-full bg-amber-400 animate-pulse';
            text.textContent = 'Bot Offline / Reconnecting';
            text.className = 'text-amber-300 font-medium text-[11px]';
        } else {
            dot.className = 'w-2.5 h-2.5 rounded-full bg-rose-400';
            text.textContent = 'Token Not Configured';
            text.className = 'text-rose-300 font-medium text-[11px]';
        }

        if (data.stats) {
            updateBadgeCounters(data.stats);
        }
    } catch (e) {
        dot.className = 'w-2.5 h-2.5 rounded-full bg-slate-500';
        text.textContent = 'Server Offline';
    }
}

// Load team users for assignment dropdowns
async function loadTeamUsers() {
    try {
        const res = await fetch('/api/users');
        if (res.ok) {
            const data = await res.json();
            cachedUsers = data.users || [];
        }
    } catch (e) {
        console.error('Error fetching users:', e);
    }
}

// WebSocket Live Updates
function connectWebSocket() {
    const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${location.host}/ws`;
    
    socket = new WebSocket(wsUrl);

    socket.onopen = () => {
        console.log('WebSocket connected.');
    };

    socket.onmessage = (event) => {
        try {
            const data = JSON.parse(event.data);
            handleWsEvent(data);
        } catch (e) {
            console.error('WS Parse Error', e);
        }
    };

    socket.onclose = () => {
        console.warn('WebSocket closed, reconnecting in 3s...');
        setTimeout(connectWebSocket, 3000);
    };

    socket.onerror = (err) => {
        console.error('WebSocket error:', err);
    };
}

function handleWsEvent(event) {
    if (event.type === 'new_ticket') {
        playDing();
        loadTickets();
        checkBotStatus();
    } else if (event.type === 'new_message') {
        playDing();
        loadTickets();
        if (currentTicketId === event.ticket_id) {
            loadTicketDetails(currentTicketId, false);
        }
    } else if (event.type === 'status_changed') {
        loadTickets();
        checkBotStatus();
        if (currentTicketId === event.ticket_id) {
            loadTicketDetails(currentTicketId, false);
        }
    } else if (event.type === 'ticket_updated') {
        loadTickets();
        if (currentTicketId === event.ticket_id && event.phone_number) {
            document.getElementById('current-user-phone').textContent = event.phone_number;
        }
    } else if (event.type === 'ticket_assigned') {
        loadTickets();
        if (currentTicketId === event.ticket_id) {
            loadTicketDetails(currentTicketId, false);
        }
    } else if (event.type === 'priority_changed') {
        loadTickets();
        if (currentTicketId === event.ticket_id) {
            loadTicketDetails(currentTicketId, false);
        }
    }
}

// Load tickets
async function loadTickets() {
    try {
        let assignedParam = '';
        if (currentQueueFilter === 'me') {
            assignedParam = `&assigned=${encodeURIComponent(currentUser || '')}`;
        } else if (currentQueueFilter === 'unassigned') {
            assignedParam = `&assigned=unassigned`;
        }

        const res = await fetch(`/api/tickets?status=${currentFilter}${assignedParam}`);
        if (res.status === 401) {
            document.getElementById('login-overlay').classList.remove('hidden');
            return;
        }
        const data = await res.json();
        allTickets = data.tickets || [];
        
        if (data.stats) {
            updateBadgeCounters(data.stats);
        }
        renderTicketsList();
    } catch (e) {
        console.error('Error loading tickets:', e);
    }
}

function updateBadgeCounters(stats) {
    if (!stats) return;
    const elTotal = document.getElementById('count-total');
    const elOpen = document.getElementById('count-open');
    const elProg = document.getElementById('count-in_progress');
    const elClosed = document.getElementById('count-closed');
    const elMine = document.getElementById('count-assigned-me');
    const elUnassigned = document.getElementById('count-unassigned');

    if (elTotal) elTotal.textContent = `(${stats.total ?? 0})`;
    if (elOpen) elOpen.textContent = `(${stats.open ?? 0})`;
    if (elProg) elProg.textContent = `(${stats.in_progress ?? 0})`;
    if (elClosed) elClosed.textContent = `(${stats.closed ?? 0})`;
    if (elMine) elMine.textContent = `(${stats.assigned_to_me ?? 0})`;
    if (elUnassigned) elUnassigned.textContent = `(${stats.unassigned ?? 0})`;
}

function setFilter(filter) {
    currentFilter = filter;
    document.querySelectorAll('.filter-tab').forEach(btn => btn.classList.remove('active'));
    const activeBtn = document.getElementById(`filter-${filter}`);
    if (activeBtn) activeBtn.classList.add('active');
    loadTickets();
}

function setQueueFilter(queue) {
    currentQueueFilter = queue;
    document.querySelectorAll('.queue-tab').forEach(btn => {
        btn.classList.remove('active', 'bg-indigo-600', 'text-white');
        btn.classList.add('text-slate-400');
    });
    const activeBtn = document.getElementById(`queue-${queue}`);
    if (activeBtn) {
        activeBtn.classList.add('active', 'bg-indigo-600', 'text-white');
        activeBtn.classList.remove('text-slate-400');
    }
    loadTickets();
}

function handleSearch(query) {
    searchQuery = query.trim().toLowerCase();
    renderTicketsList();
}

// SLA Calculation & Formatting
function getSlaInfo(ticket) {
    const isClosed = ticket.status === 'closed' || ticket.status === 'resolved';
    if (isClosed) {
        if (ticket.sla_breached) {
            return {
                text: 'Breached',
                badgeClass: 'bg-rose-500/20 text-rose-300 border-rose-500/40',
                isBreached: true
            };
        }
        return {
            text: 'Met on time',
            badgeClass: 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40',
            isBreached: false
        };
    }

    if (!ticket.sla_deadline) {
        return {
            text: 'No SLA',
            badgeClass: 'bg-slate-700/50 text-slate-400 border-slate-600',
            isBreached: false
        };
    }

    try {
        const deadline = new Date(ticket.sla_deadline.replace(' ', 'T'));
        const now = new Date();
        const diffMs = deadline - now;
        const diffMins = Math.floor(diffMs / 60000);

        if (diffMins < 0) {
            const breachMins = Math.abs(diffMins);
            let timeStr = `${breachMins}m`;
            if (breachMins >= 60) {
                timeStr = `${Math.floor(breachMins / 60)}h ${breachMins % 60}m`;
            }
            return {
                text: `Breached by ${timeStr}`,
                badgeClass: 'bg-rose-500/25 text-rose-300 border-rose-500/50 animate-pulse',
                isBreached: true
            };
        } else {
            let timeStr = `${diffMins}m left`;
            if (diffMins >= 60) {
                timeStr = `${Math.floor(diffMins / 60)}h ${diffMins % 60}m left`;
            }
            if (diffMins <= 60) {
                return {
                    text: timeStr,
                    badgeClass: 'bg-amber-500/25 text-amber-300 border-amber-500/50',
                    isBreached: false
                };
            }
            return {
                text: timeStr,
                badgeClass: 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40',
                isBreached: false
            };
        }
    } catch (e) {
        return {
            text: 'SLA Error',
            badgeClass: 'bg-slate-700 text-slate-400 border-slate-600',
            isBreached: false
        };
    }
}

function updateAllSlaBadges() {
    if (currentTicketId) {
        const t = allTickets.find(item => item.id === currentTicketId);
        if (t) renderSlaBadge(t);
    }
    renderTicketsList();
}

function renderSlaBadge(ticket) {
    const badgeEl = document.getElementById('ticket-sla-badge');
    const textEl = document.getElementById('ticket-sla-text');
    if (!badgeEl || !textEl) return;
    
    const sla = getSlaInfo(ticket);
    textEl.textContent = `SLA: ${sla.text}`;
    badgeEl.className = `px-2.5 py-1.5 rounded-xl border text-xs font-mono flex items-center gap-1.5 ${sla.badgeClass}`;
}

function getPriorityBadge(prio) {
    switch ((prio || 'medium').toLowerCase()) {
        case 'critical':
            return '<span class="px-1.5 py-0.5 rounded text-[9px] font-bold bg-rose-500/20 text-rose-300 border border-rose-500/40">Critical</span>';
        case 'high':
            return '<span class="px-1.5 py-0.5 rounded text-[9px] font-bold bg-amber-500/20 text-amber-300 border border-amber-500/40">High</span>';
        case 'medium':
            return '<span class="px-1.5 py-0.5 rounded text-[9px] font-semibold bg-sky-500/20 text-sky-300 border border-sky-500/40">Medium</span>';
        case 'low':
            return '<span class="px-1.5 py-0.5 rounded text-[9px] font-semibold bg-slate-700 text-slate-400 border border-slate-600">Low</span>';
        default:
            return '';
    }
}

// Render ticket list in sidebar
function renderTicketsList() {
    const container = document.getElementById('tickets-container');
    
    let filtered = allTickets;
    if (searchQuery) {
        filtered = allTickets.filter(t => 
            (t.ticket_number && t.ticket_number.toLowerCase().includes(searchQuery)) ||
            (t.user_name && t.user_name.toLowerCase().includes(searchQuery)) ||
            (t.phone_number && t.phone_number.includes(searchQuery)) ||
            (t.subject && t.subject.toLowerCase().includes(searchQuery)) ||
            (t.username && t.username.toLowerCase().includes(searchQuery)) ||
            (t.assigned_to && t.assigned_to.toLowerCase().includes(searchQuery))
        );
    }

    if (filtered.length === 0) {
        container.innerHTML = `
            <div class="h-64 flex flex-col items-center justify-center text-slate-500 p-6 text-center">
                <i class="fa-solid fa-inbox text-4xl mb-3 text-slate-600"></i>
                <p class="text-xs font-medium">No tickets found</p>
                <p class="text-[11px] text-slate-600 mt-1">Try changing filters or search terms</p>
            </div>
        `;
        return;
    }

    container.innerHTML = filtered.map(t => {
        const isActive = t.id === currentTicketId ? 'active' : '';
        const statusBadge = getStatusBadge(t.status);
        const priorityBadge = getPriorityBadge(t.priority || 'medium');
        const sla = getSlaInfo(t);
        const timeAgo = formatTimeAgo(t.updated_at || t.created_at);
        const phone = t.phone_number ? `<span class="text-emerald-400 font-mono text-[10px] flex items-center gap-1"><i class="fa-solid fa-phone text-[9px]"></i>${escapeHtml(t.phone_number)}</span>` : '<span class="text-slate-500 text-[10px]">No phone</span>';
        const snippet = t.last_message || t.subject || 'New ticket';
        const isGroup = (t.chat_type === 'group' || t.chat_type === 'supergroup');
        
        const assigneeBadge = t.assigned_to 
            ? `<span class="text-[10px] text-indigo-300 flex items-center gap-1 font-semibold truncate max-w-[105px]"><i class="fa-solid fa-user-check text-[9px] text-indigo-400"></i>${escapeHtml(t.assigned_to === currentUser ? 'You' : t.assigned_to)}</span>`
            : `<span class="text-[10px] text-amber-400/90 flex items-center gap-1 font-semibold"><i class="fa-solid fa-hand text-[9px]"></i>Unassigned</span>`;

        return `
            <div onclick="selectTicket(${t.id})" class="ticket-card ${isActive} p-3.5 space-y-2 border-b border-slate-800/60 cursor-pointer transition">
                <div class="flex items-center justify-between">
                    <div class="flex items-center gap-1.5 flex-wrap">
                        <span class="font-mono text-xs font-bold text-indigo-400">${escapeHtml(t.ticket_number)}</span>
                        ${priorityBadge}
                        ${statusBadge}
                    </div>
                    <span class="text-[10px] text-slate-500 shrink-0">${timeAgo}</span>
                </div>

                <div class="flex items-center justify-between text-xs">
                    <div class="font-semibold text-slate-200 truncate max-w-[170px] flex items-center gap-1.5">
                        <span>${escapeHtml(t.user_name || 'User')}</span>
                        ${isGroup ? `<span class="text-[9px] px-1.5 py-0.5 rounded bg-purple-500/20 text-purple-300 border border-purple-500/30 truncate max-w-[110px]" title="${escapeHtml(t.chat_title || 'Group')}"><i class="fa-solid fa-users text-[8px] mr-1"></i>${escapeHtml(t.chat_title || 'Group')}</span>` : ''}
                    </div>
                    ${phone}
                </div>

                <p class="text-[11px] text-slate-400 truncate line-clamp-1 leading-relaxed">
                    ${escapeHtml(snippet)}
                </p>

                <div class="flex items-center justify-between pt-1 border-t border-slate-800/40 text-[10px]">
                    ${assigneeBadge}
                    <span class="px-1.5 py-0.5 rounded font-mono border ${sla.badgeClass}">${sla.text}</span>
                </div>
            </div>
        `;
    }).join('');
}

function getStatusBadge(status) {
    switch (status) {
        case 'open':
            return '<span class="px-2 py-0.5 rounded text-[10px] font-semibold bg-amber-500/20 text-amber-300 border border-amber-500/30">Open</span>';
        case 'in_progress':
            return '<span class="px-2 py-0.5 rounded text-[10px] font-semibold bg-sky-500/20 text-sky-300 border border-sky-500/30">In Progress</span>';
        case 'resolved':
        case 'closed':
            return '<span class="px-2 py-0.5 rounded text-[10px] font-semibold bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">Closed</span>';
        default:
            return '';
    }
}

// Select ticket
async function selectTicket(ticketId) {
    currentTicketId = ticketId;
    renderTicketsList();
    await loadTicketDetails(ticketId, true);
}

async function loadTicketDetails(ticketId, shouldScrollBottom = true) {
    try {
        const res = await fetch(`/api/tickets/${ticketId}`);
        if (!res.ok) return;
        const data = await res.json();
        const ticket = data.ticket;
        if (!ticket) return;

        // Reveal panel
        document.getElementById('no-ticket-selected').classList.add('hidden');
        const panel = document.getElementById('ticket-chat-panel');
        panel.classList.remove('hidden');

        // Populate Info Header
        document.getElementById('current-user-avatar').textContent = (ticket.user_name || 'U')[0].toUpperCase();
        document.getElementById('current-user-name').textContent = ticket.user_name || 'Unknown User';
        document.getElementById('current-ticket-number').textContent = ticket.ticket_number;
        
        const isGroup = ticket.chat_type === 'group' || ticket.chat_type === 'supergroup';
        const chatTypeEl = document.getElementById('current-chat-type');
        if (isGroup) {
            chatTypeEl.innerHTML = `<i class="fa-solid fa-users text-[9px] mr-1"></i>${escapeHtml(ticket.chat_title || 'Group')}`;
        } else {
            chatTypeEl.innerHTML = `<i class="fa-solid fa-lock text-[9px] mr-1"></i>Direct Chat`;
        }
        
        document.getElementById('current-user-phone').textContent = ticket.phone_number || 'No phone recorded';
        document.getElementById('current-user-username').textContent = ticket.username ? `@${ticket.username}` : '';
        document.getElementById('current-ticket-time').textContent = formatTimeAgo(ticket.created_at);

        // Priority Selector
        const prioSelect = document.getElementById('ticket-priority-select');
        if (prioSelect) {
            prioSelect.value = ticket.priority || 'medium';
        }

        // SLA Badge
        renderSlaBadge(ticket);

        // Assignment Controls
        renderAssignmentControls(ticket);

        // Check if ticket is closed/resolved (Locked State)
        const isLocked = ticket.status === 'resolved' || ticket.status === 'closed';
        const statusContainer = document.getElementById('status-container');
        const replyForm = document.getElementById('reply-form');
        const cannedBar = document.getElementById('canned-bar');
        const replyLockedNotice = document.getElementById('reply-locked-notice');

        if (isLocked) {
            statusContainer.innerHTML = `
                <div class="px-3 py-1.5 rounded-xl bg-emerald-500/15 border border-emerald-500/35 text-emerald-300 text-xs font-bold flex items-center gap-1.5">
                    <i class="fa-solid fa-lock text-[10px]"></i>
                    <span>Resolved & Closed</span>
                </div>
            `;
            replyForm.classList.add('hidden');
            cannedBar.classList.add('hidden');
            replyLockedNotice.classList.remove('hidden');
            if (prioSelect) prioSelect.disabled = true;
        } else {
            if (prioSelect) prioSelect.disabled = false;
            let progressBtn = '';
            if (ticket.status === 'open') {
                progressBtn = `
                    <button onclick="changeStatus('in_progress')" class="px-3 py-1.5 rounded-xl bg-sky-600/80 hover:bg-sky-500 text-white text-xs font-semibold flex items-center gap-1.5 transition">
                        <i class="fa-solid fa-spinner"></i>
                        <span>In Progress</span>
                    </button>
                `;
            } else {
                progressBtn = `
                    <span class="px-2.5 py-1 rounded-lg bg-sky-500/20 text-sky-300 border border-sky-500/30 text-[11px] font-semibold">
                        In Progress
                    </span>
                `;
            }

            statusContainer.innerHTML = `
                ${progressBtn}
                <button onclick="changeStatus('closed')" class="px-3.5 py-1.5 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-bold flex items-center gap-1.5 shadow-md shadow-emerald-600/25 transition active:scale-95">
                    <i class="fa-solid fa-circle-check"></i>
                    <span>Resolve & Close</span>
                </button>
            `;
            replyForm.classList.remove('hidden');
            cannedBar.classList.remove('hidden');
            replyLockedNotice.classList.add('hidden');
        }

        // Render Messages
        const msgContainer = document.getElementById('messages-container');
        const messages = ticket.messages || [];

        msgContainer.innerHTML = messages.map(m => {
            const isAgent = m.sender_type === 'agent';
            const bubbleBg = isAgent 
                ? 'bg-gradient-to-r from-indigo-600 to-indigo-700 text-white rounded-tr-none' 
                : 'bg-slate-800 text-slate-100 border border-slate-700/80 rounded-tl-none';
            const alignClass = isAgent ? 'items-end ml-auto' : 'items-start mr-auto';
            const senderLabel = isAgent ? '👨‍💻 IT Support (Private Reply)' : escapeHtml(m.sender_name || 'User');

            let mediaHtml = '';
            if (m.media_url && m.media_type === 'photo') {
                mediaHtml = `
                    <div class="mt-2 rounded-lg overflow-hidden border border-slate-700/60 max-w-sm cursor-pointer" onclick="openImageModal('${m.media_url}')">
                        <img src="${m.media_url}" alt="Attachment" class="max-h-60 w-full object-cover hover:opacity-90 transition">
                    </div>
                `;
            }

            return `
                <div class="flex flex-col ${alignClass} message-bubble-enter max-w-xl">
                    <span class="text-[10px] text-slate-500 mb-1 px-1 font-medium">${senderLabel} • ${formatTime(m.created_at)}</span>
                    <div class="${bubbleBg} p-3.5 rounded-2xl shadow-md text-xs leading-relaxed whitespace-pre-wrap break-words">
                        ${escapeHtml(m.text)}
                        ${mediaHtml}
                    </div>
                </div>
            `;
        }).join('');

        if (shouldScrollBottom) {
            msgContainer.scrollTop = msgContainer.scrollHeight;
        }
    } catch (e) {
        console.error('Error fetching ticket details:', e);
    }
}

// Assignment Controls rendering
function renderAssignmentControls(ticket) {
    const container = document.getElementById('assignment-container');
    if (!container) return;

    const isLocked = ticket.status === 'resolved' || ticket.status === 'closed';
    const assignedTo = ticket.assigned_to;

    let userOptions = `<option value="">-- Reassign --</option>`;
    cachedUsers.forEach(u => {
        const selected = (assignedTo === u.username) ? 'selected' : '';
        userOptions += `<option value="${escapeHtml(u.username)}" ${selected}>${escapeHtml(u.username)}${u.username === currentUser ? ' (You)' : ''}</option>`;
    });

    if (isLocked) {
        container.innerHTML = `
            <div class="px-2.5 py-1.5 rounded-xl bg-slate-800 border border-slate-700/80 text-xs font-semibold text-slate-300 flex items-center gap-1.5">
                <i class="fa-solid fa-user-check text-[10px] text-indigo-400"></i>
                <span>${assignedTo ? escapeHtml(assignedTo) : 'Unassigned'}</span>
            </div>
        `;
        return;
    }

    if (!assignedTo) {
        container.innerHTML = `
            <button onclick="claimTicket(${ticket.id})" title="Take this ticket yourself" 
                    class="px-2.5 py-1.5 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-bold flex items-center gap-1.5 shadow-md shadow-indigo-600/20 transition active:scale-95">
                <i class="fa-solid fa-hand text-[10px]"></i>
                <span>Take Ticket</span>
            </button>
            <div class="relative">
                <select onchange="assignTicket(${ticket.id}, this.value)" title="Assign to technician" class="bg-slate-800 border border-slate-700/80 text-slate-300 text-xs rounded-xl px-2 py-1.5 focus:outline-none focus:border-indigo-500 cursor-pointer">
                    <option value="">Assign to...</option>
                    ${cachedUsers.map(u => `<option value="${escapeHtml(u.username)}">${escapeHtml(u.username)}</option>`).join('')}
                </select>
            </div>
        `;
    } else {
        const isAssignedToMe = assignedTo === currentUser;
        container.innerHTML = `
            <div class="flex items-center gap-1.5 px-2.5 py-1.5 rounded-xl ${isAssignedToMe ? 'bg-indigo-600/25 border-indigo-500/40 text-indigo-200' : 'bg-slate-800 border-slate-700/80 text-slate-300'} border text-xs font-semibold">
                <i class="fa-solid fa-user-check text-[10px] text-indigo-400"></i>
                <span>${isAssignedToMe ? 'Assigned: You' : escapeHtml(assignedTo)}</span>
            </div>
            <div class="relative">
                <select onchange="assignTicket(${ticket.id}, this.value)" title="Reassign ticket" class="bg-slate-800 border border-slate-700/80 text-slate-400 hover:text-slate-200 text-xs rounded-xl px-2 py-1.5 focus:outline-none focus:border-indigo-500 cursor-pointer">
                    ${userOptions}
                </select>
            </div>
        `;
    }
}

async function claimTicket(ticketId) {
    if (!currentUser) return;
    await assignTicket(ticketId, currentUser);
}

async function assignTicket(ticketId, username) {
    try {
        const res = await fetch(`/api/tickets/${ticketId}/assign`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ assigned_to: username || null })
        });
        if (res.ok) {
            const data = await res.json();
            const idx = allTickets.findIndex(t => t.id === ticketId);
            if (idx !== -1) allTickets[idx] = data.ticket;
            renderTicketsList();
            if (currentTicketId === ticketId) {
                renderAssignmentControls(data.ticket);
            }
            loadTickets();
        } else {
            alert('Failed to assign ticket');
        }
    } catch (e) {
        console.error('Error assigning ticket:', e);
    }
}

async function handlePriorityChange(newPriority) {
    if (!currentTicketId) return;
    try {
        const res = await fetch(`/api/tickets/${currentTicketId}/priority`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ priority: newPriority })
        });
        if (res.ok) {
            const data = await res.json();
            const idx = allTickets.findIndex(t => t.id === currentTicketId);
            if (idx !== -1) allTickets[idx] = data.ticket;
            renderTicketsList();
            renderSlaBadge(data.ticket);
        } else {
            alert('Failed to update priority');
        }
    } catch (e) {
        console.error('Error changing priority', e);
    }
}

// Send Agent Reply (Sent PRIVATELY to user)
async function sendReply(e) {
    e.preventDefault();
    if (!currentTicketId) return;

    const textarea = document.getElementById('reply-text');
    const text = textarea.value.trim();
    if (!text) return;

    const btn = document.getElementById('send-reply-btn');
    btn.disabled = true;
    btn.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Sending Private Reply...`;

    try {
        const res = await fetch(`/api/tickets/${currentTicketId}/reply`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ text })
        });
        
        const data = await res.json();
        if (res.ok) {
            textarea.value = '';
            await loadTicketDetails(currentTicketId, true);
            loadTickets();
            
            if (data.reason === 'user_not_started_private') {
                alert('Notice: The user has not started the bot in private yet. A prompt was posted in the group asking them to click Start on @IT_Support3_bot to receive private replies.');
            }
        } else {
            alert('Failed to send reply: ' + (data.detail || 'Unknown error'));
        }
    } catch (err) {
        alert('Server communication error');
    } finally {
        btn.disabled = false;
        btn.innerHTML = `<span>Send Private Reply</span><i class="fa-solid fa-paper-plane text-xs"></i>`;
    }
}

// Change Status
async function changeStatus(newStatus) {
    if (!currentTicketId) return;
    try {
        const res = await fetch(`/api/tickets/${currentTicketId}/status`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ status: newStatus })
        });
        const data = await res.json();
        if (res.ok) {
            await loadTicketDetails(currentTicketId, false);
            loadTickets();
            checkBotStatus();
        } else {
            alert(data.detail || 'Failed to update ticket status');
        }
    } catch (e) {
        console.error('Error changing status', e);
    }
}

// Edit Phone Number Manually
async function promptEditPhone() {
    if (!currentTicketId) return;
    const currentPhone = document.getElementById('current-user-phone').textContent.replace('No phone recorded', '');
    const newPhone = prompt('Enter customer/employee phone number:', currentPhone.trim());
    if (newPhone === null) return;

    try {
        const res = await fetch(`/api/tickets/${currentTicketId}/update-info`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ phone_number: newPhone.trim() })
        });
        if (res.ok) {
            document.getElementById('current-user-phone').textContent = newPhone.trim() || 'No phone recorded';
            loadTickets();
        }
    } catch (e) {
        alert('Failed to update phone number');
    }
}

// Quick canned reply
function insertTemplate(templateText) {
    const textarea = document.getElementById('reply-text');
    textarea.value = templateText;
    textarea.focus();
}

// Analytics & Reports Controller
function openReportsModal() {
    document.getElementById('reports-modal').classList.remove('hidden');
    setReportPreset('this_month');
}

function closeReportsModal() {
    document.getElementById('reports-modal').classList.add('hidden');
}

function setReportPreset(preset) {
    activeReportPreset = preset;
    document.querySelectorAll('.report-preset-btn').forEach(b => {
        b.classList.remove('active', 'bg-indigo-600', 'text-white');
        b.classList.add('text-slate-300');
    });
    const btn = document.getElementById(`preset-${preset}`);
    if (btn) {
        btn.classList.add('active', 'bg-indigo-600', 'text-white');
        btn.classList.remove('text-slate-300');
    }

    const today = new Date();
    let startDate = '';
    let endDate = today.toISOString().split('T')[0];

    if (preset === 'today') {
        startDate = endDate;
    } else if (preset === '7days') {
        const d = new Date();
        d.setDate(d.getDate() - 7);
        startDate = d.toISOString().split('T')[0];
    } else if (preset === 'this_month') {
        startDate = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, '0')}-01`;
    } else if (preset === 'last_month') {
        const lastMonthStart = new Date(today.getFullYear(), today.getMonth() - 1, 1);
        const lastMonthEnd = new Date(today.getFullYear(), today.getMonth(), 0);
        startDate = lastMonthStart.toISOString().split('T')[0];
        endDate = lastMonthEnd.toISOString().split('T')[0];
    } else if (preset === 'all') {
        startDate = '';
        endDate = '';
    }

    document.getElementById('report-start-date').value = startDate;
    document.getElementById('report-end-date').value = endDate;
    fetchReportData(startDate, endDate);
}

function applyCustomReportDate() {
    const s = document.getElementById('report-start-date').value;
    const e = document.getElementById('report-end-date').value;
    document.querySelectorAll('.report-preset-btn').forEach(b => {
        b.classList.remove('active', 'bg-indigo-600', 'text-white');
        b.classList.add('text-slate-300');
    });
    fetchReportData(s, e);
}

async function fetchReportData(startDate, endDate) {
    let url = '/api/reports';
    const params = [];
    if (startDate) params.push(`start_date=${startDate}`);
    if (endDate) params.push(`end_date=${endDate}`);
    if (params.length > 0) url += `?${params.join('&')}`;

    try {
        const res = await fetch(url);
        if (res.ok) {
            const data = await res.json();
            renderReportUI(data.report);
        }
    } catch (e) {
        console.error('Failed to load report:', e);
    }
}

function renderReportUI(report) {
    if (!report) return;
    const s = report.summary || {};
    
    // KPI Cards
    document.getElementById('kpi-total-tickets').textContent = s.total_tickets || 0;
    document.getElementById('kpi-resolved-tickets').textContent = s.closed_tickets || 0;
    const rate = s.total_tickets > 0 ? Math.round((s.closed_tickets / s.total_tickets) * 100) : 0;
    document.getElementById('kpi-resolution-rate').textContent = `${rate}% resolution rate (${s.open_tickets || 0} open, ${s.in_progress_tickets || 0} in progress)`;
    
    document.getElementById('kpi-sla-compliance').textContent = `${s.sla_compliance_rate || 100}%`;
    document.getElementById('kpi-sla-breaches').textContent = `${s.sla_breached_count || 0} Breached`;

    const avgRes = s.avg_resolution_mins || 0;
    let avgResStr = `${avgRes}m`;
    if (avgRes >= 60) avgResStr = `${(avgRes / 60).toFixed(1)}h`;
    document.getElementById('kpi-avg-resolution').textContent = avgResStr;
    document.getElementById('kpi-first-response').textContent = `Avg first response: ${s.avg_first_response_mins || 0}m`;

    // Team Leaderboard Table
    const teamTbody = document.getElementById('team-performance-tbody');
    const techs = report.technicians || [];
    if (techs.length === 0) {
        teamTbody.innerHTML = `<tr><td colspan="5" class="py-4 text-center text-slate-500">No technician activity recorded</td></tr>`;
    } else {
        teamTbody.innerHTML = techs.map((t, idx) => {
            const isTop = idx === 0 && t.resolved > 0;
            const rankIcon = isTop ? '<i class="fa-solid fa-crown text-amber-400 mr-1.5 text-xs"></i>' : '';
            let avgTime = `${t.avg_resolution_mins}m`;
            if (t.avg_resolution_mins >= 60) avgTime = `${(t.avg_resolution_mins / 60).toFixed(1)}h`;
            
            return `
                <tr class="hover:bg-slate-800/40 transition">
                    <td class="py-2.5 px-4 font-semibold flex items-center">
                        ${rankIcon}
                        <span>${escapeHtml(t.username)}</span>
                    </td>
                    <td class="py-2.5 px-4 text-center font-mono">${t.total_handled}</td>
                    <td class="py-2.5 px-4 text-center font-mono font-bold text-emerald-400">${t.resolved}</td>
                    <td class="py-2.5 px-4 text-center font-mono text-slate-300">${avgTime}</td>
                    <td class="py-2.5 px-4 text-center font-mono font-semibold ${t.sla_compliance_rate >= 90 ? 'text-indigo-400' : 'text-amber-400'}">${t.sla_compliance_rate}%</td>
                </tr>
            `;
        }).join('');
    }

    // Period Tickets List Table
    const ticketsTbody = document.getElementById('report-tickets-tbody');
    const tickets = report.tickets || [];
    document.getElementById('report-ticket-count').textContent = `${tickets.length} tickets`;
    
    if (tickets.length === 0) {
        ticketsTbody.innerHTML = `<tr><td colspan="7" class="py-4 text-center text-slate-500">No tickets found in this period</td></tr>`;
    } else {
        ticketsTbody.innerHTML = tickets.map(t => {
            const slaStatus = t.sla_breached 
                ? '<span class="text-rose-400 font-bold">Breached</span>' 
                : '<span class="text-emerald-400 font-semibold">Met</span>';
            const statusClass = t.status === 'closed' ? 'text-emerald-400' : 'text-amber-400';
            
            return `
                <tr class="hover:bg-slate-800/40 transition">
                    <td class="py-2 px-3 text-indigo-300 font-bold">${escapeHtml(t.ticket_number)}</td>
                    <td class="py-2 px-3 font-sans truncate max-w-[120px]">${escapeHtml(t.user_name || 'User')}</td>
                    <td class="py-2 px-3 font-sans truncate max-w-[180px] text-slate-300">${escapeHtml(t.subject || '')}</td>
                    <td class="py-2 px-3 text-center uppercase text-[10px]">${getPriorityBadge(t.priority)}</td>
                    <td class="py-2 px-3 text-center font-sans text-slate-300">${escapeHtml(t.assigned_to || 'Unassigned')}</td>
                    <td class="py-2 px-3 text-center ${statusClass} uppercase font-bold text-[10px]">${t.status}</td>
                    <td class="py-2 px-3 text-center text-[10px]">${slaStatus}</td>
                </tr>
            `;
        }).join('');
    }
}

function exportReportsCSV() {
    const s = document.getElementById('report-start-date').value;
    const e = document.getElementById('report-end-date').value;
    let url = '/api/reports/export';
    const params = [];
    if (s) params.push(`start_date=${s}`);
    if (e) params.push(`end_date=${e}`);
    if (params.length > 0) url += `?${params.join('&')}`;
    window.location.href = url;
}

// Users Management Modal
function openUsersModal() {
    document.getElementById('users-modal').classList.remove('hidden');
    document.getElementById('create-user-error').classList.add('hidden');
    document.getElementById('new-user-username').value = '';
    document.getElementById('new-user-password').value = '';
    loadUsersList();
}

function closeUsersModal() {
    document.getElementById('users-modal').classList.add('hidden');
}

async function loadUsersList() {
    const container = document.getElementById('users-list-container');
    container.innerHTML = `<div class="p-4 text-center text-slate-500 text-xs"><i class="fa-solid fa-spinner fa-spin mr-1"></i> Loading users...</div>`;

    try {
        const res = await fetch('/api/users');
        const data = await res.json();
        const users = data.users || [];
        cachedUsers = users;

        if (users.length === 0) {
            container.innerHTML = `<div class="p-4 text-center text-slate-500 text-xs">No users found.</div>`;
            return;
        }

        container.innerHTML = users.map(u => {
            const isSelf = u.username === currentUser;
            const roleBadge = u.role === 'admin' 
                ? '<span class="px-1.5 py-0.5 rounded text-[9px] font-bold bg-indigo-500/20 text-indigo-300 border border-indigo-500/30">Admin</span>' 
                : '<span class="px-1.5 py-0.5 rounded text-[9px] font-medium bg-slate-700 text-slate-300">Agent</span>';

            const deleteBtn = isSelf 
                ? `<span class="text-[10px] text-slate-500 font-mono">(You)</span>` 
                : `<button onclick="handleDeleteUser(${u.id}, '${escapeHtml(u.username)}')" title="Delete User" class="w-7 h-7 rounded-lg hover:bg-rose-500/20 text-slate-400 hover:text-rose-400 flex items-center justify-center transition"><i class="fa-solid fa-trash-can text-xs"></i></button>`;

            return `
                <div class="p-3 flex items-center justify-between">
                    <div class="flex items-center gap-2.5">
                        <div class="w-8 h-8 rounded-full bg-slate-800 border border-slate-700 flex items-center justify-center text-xs font-bold text-indigo-400">
                            ${escapeHtml(u.username[0].toUpperCase())}
                        </div>
                        <div>
                            <div class="text-xs font-semibold text-slate-200 flex items-center gap-1.5">
                                <span>${escapeHtml(u.username)}</span>
                                ${roleBadge}
                            </div>
                            <span class="text-[10px] text-slate-500">Created: ${escapeHtml(u.created_at || 'Recently')}</span>
                        </div>
                    </div>
                    ${deleteBtn}
                </div>
            `;
        }).join('');
    } catch (e) {
        container.innerHTML = `<div class="p-4 text-center text-rose-400 text-xs">Failed to load users.</div>`;
    }
}

async function handleAddUser(e) {
    e.preventDefault();
    const username = document.getElementById('new-user-username').value.trim();
    const password = document.getElementById('new-user-password').value;
    const errBox = document.getElementById('create-user-error');
    const btn = document.getElementById('add-user-btn');

    errBox.classList.add('hidden');
    btn.disabled = true;
    btn.innerHTML = `<i class="fa-solid fa-spinner fa-spin text-[10px]"></i> Creating...`;

    try {
        const res = await fetch('/api/users', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username, password, role: 'agent' })
        });
        const data = await res.json();
        if (res.ok) {
            document.getElementById('new-user-username').value = '';
            document.getElementById('new-user-password').value = '';
            loadUsersList();
        } else {
            errBox.textContent = data.detail || 'Failed to create user';
            errBox.classList.remove('hidden');
        }
    } catch (err) {
        errBox.textContent = 'Server connection error';
        errBox.classList.remove('hidden');
    } finally {
        btn.disabled = false;
        btn.innerHTML = `<i class="fa-solid fa-user-plus text-[10px]"></i><span>Create User</span>`;
    }
}

async function handleDeleteUser(userId, username) {
    if (!confirm(`Are you sure you want to delete user "${username}"?`)) return;

    try {
        const res = await fetch(`/api/users/${userId}`, { method: 'DELETE' });
        const data = await res.json();
        if (res.ok) {
            loadUsersList();
        } else {
            alert(data.detail || 'Failed to delete user');
        }
    } catch (e) {
        alert('Server communication error');
    }
}

// Token Modal
function openTokenModal() {
    document.getElementById('token-modal').classList.remove('hidden');
    document.getElementById('token-error').classList.add('hidden');
    document.getElementById('token-input').focus();
}

function closeTokenModal() {
    document.getElementById('token-modal').classList.add('hidden');
}

async function saveToken(e) {
    e.preventDefault();
    const token = document.getElementById('token-input').value.trim();
    if (!token) return;

    const btn = document.getElementById('save-token-btn');
    const errBox = document.getElementById('token-error');
    btn.disabled = true;
    btn.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Connecting...`;
    errBox.classList.add('hidden');

    try {
        const res = await fetch('/api/settings/token', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ token })
        });
        const data = await res.json();
        if (res.ok) {
            closeTokenModal();
            checkBotStatus();
            alert('Bot Token connected successfully!');
        } else {
            errBox.textContent = data.detail || 'Invalid token. Please check @BotFather.';
            errBox.classList.remove('hidden');
        }
    } catch (e) {
        errBox.textContent = 'Server connection failed';
        errBox.classList.remove('hidden');
    } finally {
        btn.disabled = false;
        btn.textContent = 'Save & Connect';
    }
}

// Account Settings Modal (Change Password)
function openAccountModal() {
    document.getElementById('account-modal').classList.remove('hidden');
    document.getElementById('account-error').classList.add('hidden');
    document.getElementById('account-success').classList.add('hidden');
    document.getElementById('curr-password').value = '';
    document.getElementById('new-password').value = '';
}

function closeAccountModal() {
    document.getElementById('account-modal').classList.add('hidden');
}

async function saveCredentials(e) {
    e.preventDefault();
    const currPass = document.getElementById('curr-password').value;
    const newPass = document.getElementById('new-password').value;
    
    const errBox = document.getElementById('account-error');
    const succBox = document.getElementById('account-success');
    const btn = document.getElementById('save-account-btn');

    errBox.classList.add('hidden');
    succBox.classList.add('hidden');
    btn.disabled = true;
    btn.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Updating...`;

    try {
        const res = await fetch('/api/auth/credentials', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                current_password: currPass,
                new_password: newPass
            })
        });
        const data = await res.json();
        if (res.ok) {
            succBox.textContent = 'Password updated successfully!';
            succBox.classList.remove('hidden');
            setTimeout(closeAccountModal, 1500);
        } else {
            errBox.textContent = data.detail || 'Failed to update password';
            errBox.classList.remove('hidden');
        }
    } catch (err) {
        errBox.textContent = 'Server connection failed';
        errBox.classList.remove('hidden');
    } finally {
        btn.disabled = false;
        btn.textContent = 'Update Password';
    }
}

// Image Zoom Modal
function openImageModal(src) {
    const modal = document.getElementById('image-modal');
    const img = document.getElementById('image-modal-src');
    img.src = src;
    modal.classList.remove('hidden');
}

function closeImageModal() {
    document.getElementById('image-modal').classList.add('hidden');
}

// Helper: Escape HTML
function escapeHtml(str) {
    if (!str) return '';
    return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}

// Helper: Format Time
function formatTime(dtStr) {
    if (!dtStr) return '';
    try {
        const d = new Date(dtStr.replace(' ', 'T'));
        return d.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' });
    } catch (e) {
        return dtStr;
    }
}

function formatTimeAgo(dtStr) {
    if (!dtStr) return '';
    try {
        const d = new Date(dtStr.replace(' ', 'T'));
        const diffSec = Math.floor((new Date() - d) / 1000);
        if (diffSec < 60) return 'Just now';
        if (diffSec < 3600) return `${Math.floor(diffSec / 60)}m ago`;
        if (diffSec < 86400) return `${Math.floor(diffSec / 3600)}h ago`;
        return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
    } catch (e) {
        return dtStr;
    }
}
