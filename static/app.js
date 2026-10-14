// IT Support Helpdesk - English Client Application

let allTickets = [];
let currentTicketId = null;
let currentFilter = 'all';
let searchQuery = '';
let soundEnabled = localStorage.getItem('sound_enabled') !== 'false';
let socket = null;
let currentUser = null;

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
    loadTickets();
    connectWebSocket();
}

// Sound Generator using Web Audio API
function playDing() {
    if (!soundEnabled) return;
    try {
        const AudioContext = window.AudioContext || window.webkitAudioContext;
        if (!AudioContext) return;
        const ctx = new AudioContext();
        const now = ctx.currentTime;
        
        // Tone 1
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

        // Tone 2
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
        
        if (data.bot_running && data.bot && data.bot.username) {
            dot.className = 'w-2.5 h-2.5 rounded-full bg-emerald-400 shadow shadow-emerald-500/50';
            text.innerHTML = `Connected: <a href="https://t.me/${data.bot.username}" target="_blank" class="text-sky-400 hover:underline">@${data.bot.username}</a>`;
        } else if (!data.configured) {
            dot.className = 'w-2.5 h-2.5 rounded-full bg-rose-500 animate-ping';
            text.innerHTML = `<span class="text-rose-400 font-bold">Token Missing - Click to Setup</span>`;
            document.getElementById('bot-status-container').onclick = openTokenModal;
            document.getElementById('bot-status-container').classList.add('cursor-pointer');
            setTimeout(openTokenModal, 600);
        } else {
            dot.className = 'w-2.5 h-2.5 rounded-full bg-amber-400 animate-pulse';
            text.textContent = 'Checking bot connection...';
        }
        
        if (data.stats) {
            updateStatsCounters(data.stats);
        }
    } catch (err) {
        dot.className = 'w-2.5 h-2.5 rounded-full bg-rose-500';
        text.textContent = 'Server Disconnected';
    }
}

function updateStatsCounters(stats) {
    document.getElementById('count-total').textContent = `(${stats.total || 0})`;
    document.getElementById('count-open').textContent = `(${stats.open || 0})`;
    document.getElementById('count-in_progress').textContent = `(${stats.in_progress || 0})`;
    document.getElementById('count-closed').textContent = `(${stats.closed || 0})`;
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
    }
}

// Load tickets
async function loadTickets() {
    try {
        const res = await fetch(`/api/tickets?status=${currentFilter}`);
        if (res.status === 401) {
            document.getElementById('login-overlay').classList.remove('hidden');
            return;
        }
        const data = await res.json();
        allTickets = data.tickets || [];
        renderTicketsList();
    } catch (e) {
        console.error('Error loading tickets:', e);
    }
}

function setFilter(filter) {
    currentFilter = filter;
    document.querySelectorAll('.filter-tab').forEach(btn => btn.classList.remove('active'));
    const activeBtn = document.getElementById(`filter-${filter}`);
    if (activeBtn) activeBtn.classList.add('active');
    loadTickets();
}

function handleSearch(query) {
    searchQuery = query.trim().toLowerCase();
    renderTicketsList();
}

// Render ticket list
function renderTicketsList() {
    const container = document.getElementById('tickets-container');
    
    let filtered = allTickets;
    if (searchQuery) {
        filtered = allTickets.filter(t => 
            (t.ticket_number && t.ticket_number.toLowerCase().includes(searchQuery)) ||
            (t.user_name && t.user_name.toLowerCase().includes(searchQuery)) ||
            (t.phone_number && t.phone_number.includes(searchQuery)) ||
            (t.subject && t.subject.toLowerCase().includes(searchQuery)) ||
            (t.username && t.username.toLowerCase().includes(searchQuery))
        );
    }

    if (filtered.length === 0) {
        container.innerHTML = `
            <div class="h-64 flex flex-col items-center justify-center text-slate-500 p-6 text-center">
                <i class="fa-solid fa-inbox text-4xl mb-3 text-slate-600"></i>
                <p class="text-xs font-medium">No tickets found</p>
            </div>
        `;
        return;
    }

    container.innerHTML = filtered.map(t => {
        const isActive = t.id === currentTicketId ? 'active' : '';
        const statusBadge = getStatusBadge(t.status);
        const timeAgo = formatTimeAgo(t.updated_at || t.created_at);
        const phone = t.phone_number ? `<span class="text-emerald-400 font-mono text-[10px] flex items-center gap-1"><i class="fa-solid fa-phone text-[9px]"></i>${escapeHtml(t.phone_number)}</span>` : '<span class="text-slate-500 text-[10px]">No phone</span>';
        const snippet = t.last_message || t.subject || 'New ticket';
        const isGroup = (t.chat_type === 'group' || t.chat_type === 'supergroup');

        return `
            <div onclick="selectTicket(${t.id})" class="ticket-card ${isActive} p-3.5 space-y-2 border-b border-slate-800/60">
                <div class="flex items-center justify-between">
                    <div class="flex items-center gap-2">
                        <span class="font-mono text-xs font-bold text-indigo-400">${escapeHtml(t.ticket_number)}</span>
                        ${statusBadge}
                    </div>
                    <span class="text-[10px] text-slate-500">${timeAgo}</span>
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
        } else {
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
