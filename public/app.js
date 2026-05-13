/* ══════════════════════════════════════════════════════════════
   AthleticConnect — Frontend Application
   ══════════════════════════════════════════════════════════════ */

const API_BASE = '';  // same origin

// ── Auth State ──────────────────────────────────────────────
function getToken() { return localStorage.getItem('ac_token'); }
function setToken(t) { localStorage.setItem('ac_token', t); }
function clearToken() { localStorage.removeItem('ac_token'); localStorage.removeItem('ac_user'); }
function getUser() { try { return JSON.parse(localStorage.getItem('ac_user')); } catch { return null; } }
function setUser(u) { localStorage.setItem('ac_user', JSON.stringify(u)); }

function authHeaders() {
    return {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${getToken()}`
    };
}

// ── API Helper ──────────────────────────────────────────────
async function apiFetch(url, options = {}) {
    const res = await fetch(API_BASE + url, {
        ...options,
        headers: { ...authHeaders(), ...(options.headers || {}) }
    });
    const data = await res.json();
    if (!res.ok) {
        if (res.status === 401 || res.status === 403) {
            clearToken();
            showAuth();
        }
        throw new Error(data.error || `Request failed (${res.status})`);
    }
    return data;
}

// ══════════════════════════════════════════════════════════════
//  AUTH UI
// ══════════════════════════════════════════════════════════════
function showAuth() {
    document.getElementById('app-shell').style.display = 'none';
    document.getElementById('auth-overlay').style.display = 'flex';
}

function hideAuth() {
    document.getElementById('auth-overlay').style.display = 'none';
    document.getElementById('app-shell').style.display = 'flex';
}

function toggleAuthMode() {
    const card = document.getElementById('auth-card');
    const isLogin = card.dataset.mode === 'login';
    card.dataset.mode = isLogin ? 'register' : 'login';

    document.getElementById('auth-title').textContent = isLogin ? 'Create Account' : 'Welcome Back';
    document.getElementById('auth-subtitle').textContent = isLogin
        ? 'Join AthleticConnect and start your fitness journey'
        : 'Sign in to your AthleticConnect account';
    document.getElementById('auth-submit-btn').textContent = isLogin ? 'Create Account' : 'Sign In';
    document.getElementById('auth-toggle-text').innerHTML = isLogin
        ? 'Already have an account? <a onclick="toggleAuthMode()">Sign In</a>'
        : 'Don\'t have an account? <a onclick="toggleAuthMode()">Create one</a>';

    // Show/hide registration fields
    document.getElementById('register-fields').style.display = isLogin ? 'flex' : 'none';
    document.getElementById('auth-error').style.display = 'none';
}

async function handleAuthSubmit(e) {
    e.preventDefault();
    const card = document.getElementById('auth-card');
    const errorEl = document.getElementById('auth-error');
    const btn = document.getElementById('auth-submit-btn');
    const isRegister = card.dataset.mode === 'register';

    const email = document.getElementById('auth-email').value.trim();
    const password = document.getElementById('auth-password').value;

    errorEl.style.display = 'none';
    btn.disabled = true;
    btn.textContent = isRegister ? 'Creating...' : 'Signing in...';

    try {
        let data;
        if (isRegister) {
            const name = document.getElementById('auth-name').value.trim();
            const location = document.getElementById('auth-location').value.trim();
            if (!name) throw new Error('Name is required');
            data = await fetch(API_BASE + '/api/auth/register', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ name, email, password, location, sports: [] })
            }).then(r => r.json().then(d => { if (!r.ok) throw new Error(d.error); return d; }));
        } else {
            data = await fetch(API_BASE + '/api/auth/login', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ email, password })
            }).then(r => r.json().then(d => { if (!r.ok) throw new Error(d.error); return d; }));
        }

        setToken(data.token);
        setUser(data.user);
        hideAuth();
        initApp();
    } catch (err) {
        errorEl.textContent = err.message;
        errorEl.style.display = 'block';
    } finally {
        btn.disabled = false;
        btn.textContent = isRegister ? 'Create Account' : 'Sign In';
    }
}

function logout() {
    clearToken();
    conversationHistory = [];
    showAuth();
}

// ══════════════════════════════════════════════════════════════
//  NAVIGATION
// ══════════════════════════════════════════════════════════════
function showSection(id) {
    document.querySelectorAll('.section').forEach(s => s.classList.remove('active'));
    document.querySelectorAll('.sidebar-item').forEach(i => i.classList.remove('active'));

    const target = document.getElementById(id);
    if (target) target.classList.add('active');

    const sideItem = document.getElementById('side-' + id);
    if (sideItem) sideItem.classList.add('active');

    // Load data when switching sections
    if (id === 'dashboard') loadDashboard();
    if (id === 'challenges') loadChallenges();
    if (id === 'social') loadCommunity();
    if (id === 'profile') loadProfile();
}

// ══════════════════════════════════════════════════════════════
//  DASHBOARD
// ══════════════════════════════════════════════════════════════
async function loadDashboard() {
    try {
        const data = await apiFetch('/api/dashboard');

        document.getElementById('stat-calories').textContent = data.stats.calories.toLocaleString();
        document.getElementById('stat-minutes').textContent = data.stats.minutes.toLocaleString();
        document.getElementById('stat-points').textContent = data.stats.points.toLocaleString();
        document.getElementById('stat-friends').textContent = data.stats.friends.toLocaleString();

        // Render recent activities
        const container = document.getElementById('recent-activities');
        if (data.recentActivities.length === 0) {
            container.innerHTML = '<p style="color: var(--text-dim)">No activities yet. Start your first workout!</p>';
        } else {
            container.innerHTML = data.recentActivities.map(a => {
                const icon = a.type === 'Running' ? '🏃' : a.type === 'Cycling' ? '🚴' : '🏋️';
                return `
                    <div class="activity-item">
                        <div class="activity-icon">${icon}</div>
                        <div class="activity-details">
                            <strong>${a.description || a.type}</strong><br>
                            <small>${a.date}</small>
                        </div>
                        <div class="activity-stats">
                            ${a.distance_km}km · ${Math.round(a.duration_minutes)} min<br>
                            <small>${a.calories} cal</small>
                        </div>
                    </div>`;
            }).join('');
        }
    } catch (err) {
        console.error('Dashboard load error:', err);
    }
}

// ══════════════════════════════════════════════════════════════
//  PROFILE
// ══════════════════════════════════════════════════════════════
async function loadProfile() {
    try {
        const data = await apiFetch('/api/profile');

        document.getElementById('profile-initials').textContent = data.user.avatar_initials;
        document.getElementById('profile-name').textContent = data.user.name;
        document.getElementById('profile-info').textContent =
            `${data.user.sports.join(' & ')} • ${data.user.location}`;

        // Personal bests
        const pbContainer = document.getElementById('profile-pbs');
        pbContainer.innerHTML = data.personalBests.map(pb =>
            `<div class="item-row"><span>${pb.event_name}</span> <strong>${pb.time_display}</strong></div>`
        ).join('') || '<p style="color: var(--text-dim)">No personal bests recorded yet.</p>';

        // Achievements
        const achContainer = document.getElementById('profile-achievements');
        achContainer.innerHTML = data.achievements.map(a =>
            `<span title="${a.label}" style="font-size: 24px; cursor: help;">${a.icon}</span>`
        ).join(' ') || '<p style="color: var(--text-dim)">Complete workouts to earn achievements!</p>';

    } catch (err) {
        console.error('Profile load error:', err);
    }
}

// ══════════════════════════════════════════════════════════════
//  CHALLENGES
// ══════════════════════════════════════════════════════════════
async function loadChallenges() {
    try {
        const data = await apiFetch('/api/challenges');
        const container = document.getElementById('challenges-list');

        container.innerHTML = data.challenges.map(c => `
            <div class="item-row">
                <div>
                    <strong>${c.icon} ${c.title}</strong><br>
                    <small style="color: var(--text-muted)">${c.joined ? c.progress : c.description}</small>
                </div>
                <button class="btn-outline ${c.joined ? 'active' : ''}"
                    onclick="${c.joined ? '' : `joinChallenge(${c.id}, this)`}"
                    ${c.joined ? 'disabled' : ''}>
                    ${c.joined ? 'Joined ✓' : 'Join'}
                </button>
            </div>
        `).join('');
    } catch (err) {
        console.error('Challenges load error:', err);
    }
}

async function joinChallenge(id, btn) {
    try {
        btn.disabled = true;
        btn.textContent = 'Joining...';
        await apiFetch(`/api/challenges/${id}/join`, { method: 'POST' });
        btn.textContent = 'Joined ✓';
        btn.classList.add('active');
    } catch (err) {
        btn.disabled = false;
        btn.textContent = 'Join';
        alert(err.message);
    }
}

// ══════════════════════════════════════════════════════════════
//  COMMUNITY
// ══════════════════════════════════════════════════════════════
async function loadCommunity() {
    try {
        const data = await apiFetch('/api/community/feed');
        const container = document.getElementById('community-feed');

        container.innerHTML = data.posts.map((p, i) => {
            const isFirst = i === 0;
            let detail = '';
            if (p.post_type === 'achievement' && p.metadata.event) {
                detail = ` ${p.metadata.event} in ${p.metadata.time}`;
            }
            return `
                <div class="community-post ${isFirst ? '' : 'secondary'}">
                    <strong>${p.author.name}</strong> ${p.content}${detail}<br>
                    <small>${p.timeAgo}</small>
                </div>`;
        }).join('') || '<p style="color: var(--text-dim)">No community posts yet.</p>';
    } catch (err) {
        console.error('Community load error:', err);
    }
}

async function submitPost() {
    const input = document.getElementById('post-input');
    const content = input.value.trim();
    if (!content) return;

    try {
        input.disabled = true;
        await apiFetch('/api/community/post', {
            method: 'POST',
            body: JSON.stringify({ content })
        });
        input.value = '';
        input.disabled = false;
        loadCommunity(); // Refresh feed
    } catch (err) {
        input.disabled = false;
        alert(err.message);
    }
}

// ══════════════════════════════════════════════════════════════
//  AI COACH
// ══════════════════════════════════════════════════════════════
let conversationHistory = [];

function showTyping() {
    const box = document.getElementById('chat-msgs');
    const typing = document.createElement('div');
    typing.className = 'typing-indicator';
    typing.id = 'typing-indicator';
    typing.innerHTML = '<span></span><span></span><span></span>';
    box.appendChild(typing);
    box.scrollTop = box.scrollHeight;
}

function hideTyping() {
    const el = document.getElementById('typing-indicator');
    if (el) el.remove();
}

function quickAsk(text) {
    document.getElementById('chat-field').value = text;
    sendMsg();
}

async function sendMsg() {
    const input = document.getElementById('chat-field');
    const box = document.getElementById('chat-msgs');
    const sendBtn = document.getElementById('send-btn');
    const userText = input.value.trim();
    if (!userText) return;

    // Show user message
    const uDiv = document.createElement('div');
    uDiv.className = 'bubble user';
    uDiv.textContent = userText;
    box.appendChild(uDiv);
    input.value = '';
    box.scrollTop = box.scrollHeight;

    // Disable input
    input.disabled = true;
    sendBtn.disabled = true;
    showTyping();

    // Add to history
    conversationHistory.push({ role: 'user', text: userText });

    try {
        const data = await apiFetch('/api/ai/chat', {
            method: 'POST',
            body: JSON.stringify({
                message: userText,
                history: conversationHistory.slice(0, -1) // exclude current message
            })
        });

        hideTyping();

        // Add AI reply to history
        conversationHistory.push({ role: 'model', text: data.reply });

        // Display AI response
        const aDiv = document.createElement('div');
        aDiv.className = 'bubble ai';
        aDiv.innerHTML = formatAIResponse(data.reply);
        box.appendChild(aDiv);

    } catch (err) {
        hideTyping();
        console.error('AI error:', err);

        const errDiv = document.createElement('div');
        errDiv.className = 'bubble error';
        errDiv.textContent = `❌ ${err.message}`;
        box.appendChild(errDiv);

        // Remove failed message from history
        conversationHistory.pop();
    }

    // Re-enable input
    input.disabled = false;
    sendBtn.disabled = false;
    input.focus();
    box.scrollTop = box.scrollHeight;
}

function formatAIResponse(text) {
    return text
        .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
        .replace(/\*(.+?)\*/g, '<em>$1</em>')
        .replace(/\n/g, '<br>');
}

// ══════════════════════════════════════════════════════════════
//  INITIALIZATION
// ══════════════════════════════════════════════════════════════
function initApp() {
    const user = getUser();
    if (!user) return;

    // Update header
    document.getElementById('header-initials').textContent = user.avatar_initials || 'U';
    document.getElementById('header-name').textContent = user.name;

    // Update dashboard greeting
    const firstName = user.name.split(' ')[0];
    document.getElementById('dashboard-greeting').textContent =
        `Welcome back, ${firstName} — here's your activity overview`;

    // Load dashboard data
    loadDashboard();
}

// On page load
window.addEventListener('DOMContentLoaded', () => {
    if (getToken()) {
        hideAuth();
        initApp();
    } else {
        showAuth();
    }

    // Auth form submit
    document.getElementById('auth-form').addEventListener('submit', handleAuthSubmit);
});
