const root = document.documentElement;
const messagesEl = document.getElementById('messages');
const form = document.getElementById('chat-form');
const input = document.getElementById('chat-input');
const sendBtn = document.getElementById('send-btn');
const statusEl = document.getElementById('status');
const themeToggle = document.getElementById('theme-toggle');
const quickEl = document.getElementById('quick-replies');
const aboutBtn = document.getElementById('about-btn');
const clearBtn = document.getElementById('clear-btn');
const chatShell = document.getElementById('chat-shell');
const aboutModal = document.getElementById('about-modal');
const aboutClose = document.getElementById('about-close');

// ============ Theme setup ============
const savedTheme = localStorage.getItem('theme')
  || (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
root.setAttribute('data-theme', savedTheme);
setToggleIcon(savedTheme);

// API base for cross-origin calls (set window.__API_BASE__ on separate frontend port)
const API_BASE = (typeof window !== 'undefined' && window.__API_BASE__) ? window.__API_BASE__ : '';

function setToggleIcon(theme) {
  const iconEl = themeToggle.querySelector('.icon');
  if (iconEl) iconEl.textContent = theme === 'dark' ? '🌙' : '☀️';
}
themeToggle.addEventListener('click', () => {
  const next = root.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
  root.setAttribute('data-theme', next);
  localStorage.setItem('theme', next);
  setToggleIcon(next);
});

// ============ Quick replies ============
const quickReplies = [
  'List all Freshservice endpoints',
  'How to create a ticket?',
  'How to update a requester?',
  'Search tickets by keyword',
  'Show ticket fields and payload'
];
function renderQuickReplies() {
  quickEl.innerHTML = '';
  quickReplies.forEach(q => {
    const chip = document.createElement('button');
    chip.className = 'chip';
    chip.type = 'button';
    chip.textContent = q;
    chip.addEventListener('click', () => {
      input.value = q;
      input.focus();
      form.requestSubmit();
    });
    quickEl.appendChild(chip);
  });
}

// ============ Message utilities ============
function sanitize(text = '') {
  // keep plain text, allow code fencing later
  return text.replace(/[<>]/g, c => ({'<':'&lt;','>':'&gt;'}[c]));
}

function renderMarkdownLite(text) {
  // inline code
  let t = sanitize(text).replace(/`([^`]+)`/g, '<code>$1</code>');
  // fenced blocks ```lang? ... ```
  t = t.replace(/```[a-zA-Z0-9]*\n?([\s\S]*?)```/g, (_m, code) => {
    const safe = sanitize(code);
    const id = 'copy_' + Math.random().toString(36).slice(2,8);
    return `<pre>${safe}</pre><button class="copy-btn" data-copy="${id}">Copy</button><textarea id="${id}" class="hidden">${code}</textarea>`;
  });
  // simple bullets
  t = t.replace(/^(?:\*|\-|\•)\s+(.*)$/gm, '• $1');
  return t;
}

function addMessage(role, text, opts = {}) {
  const msg = document.createElement('div');
  msg.className = `msg ${role}${opts.thinking ? ' thinking' : ''}`;
  const avatar = document.createElement('div');
  avatar.className = 'avatar';
  const bubble = document.createElement('div');
  bubble.className = 'bubble';

  if (opts.html) {
    bubble.innerHTML = opts.html;
  } else {
    bubble.textContent = text;
  }

  const contentWrap = document.createElement('div');
  const meta = document.createElement('div');
  meta.className = 'meta';
  meta.textContent = role === 'user' ? 'You' : 'Assistant';

  contentWrap.appendChild(meta);
  contentWrap.appendChild(bubble);

  msg.appendChild(avatar);
  msg.appendChild(contentWrap);

  messagesEl.appendChild(msg);
  messagesEl.scrollTop = messagesEl.scrollHeight;
  return msg;
}

function setTypingBubble(msgEl) {
  const bubble = msgEl.querySelector('.bubble');
  bubble.innerHTML = `<span class="typing"><span class="dot"></span><span class="dot"></span><span class="dot"></span></span>`;
}

function upgradeCopyButtons(container) {
  container.querySelectorAll('.copy-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      const id = btn.getAttribute('data-copy');
      const ta = document.getElementById(id);
      if (!ta) return;
      ta.select();
      document.execCommand('copy');
      btn.textContent = 'Copied!';
      setTimeout(() => (btn.textContent = 'Copy'), 1200);
    });
  });
}

// ============ Ripple interactions ============
function addRippleTo(el) {
  if (!el) return;
  el.addEventListener('click', (e) => {
    const rect = el.getBoundingClientRect();
    const r = document.createElement('span');
    r.className = 'ripple';
    r.style.width = r.style.height = Math.max(rect.width, rect.height) + 'px';
    r.style.left = (e.clientX - rect.left - rect.width / 2) + 'px';
    r.style.top = (e.clientY - rect.top - rect.height / 2) + 'px';
    el.appendChild(r);
    setTimeout(() => r.remove(), 650);
  });
}
[sendBtn, themeToggle, aboutBtn, clearBtn].forEach(addRippleTo);

// ============ Footer runner interactions ============
const footerRunner = document.getElementById('footerRunner');
if (footerRunner) {
  footerRunner.addEventListener('mouseenter', () => footerRunner.classList.add('jump'));
  footerRunner.addEventListener('mouseleave', () => footerRunner.classList.remove('jump'));
  footerRunner.addEventListener('click', () => {
    footerRunner.classList.add('jump');
    setTimeout(() => footerRunner.classList.remove('jump'), 500);
  });
}

// ============ Parallax background & shell tilt ============
const motionOk = !window.matchMedia('(prefers-reduced-motion: reduce)').matches;
if (motionOk && window.matchMedia('(pointer:fine)').matches) {
  document.addEventListener('mousemove', (e) => {
    const x = (e.clientX / window.innerWidth - 0.5) * 2;
    const y = (e.clientY / window.innerHeight - 0.5) * 2;
    root.style.setProperty('--bg-pos-x', `${50 + x * 4}%`);
    root.style.setProperty('--bg-pos-y', `${50 + y * 3}%`);
    root.style.setProperty('--mid-x', `${x * 12}px`);
    root.style.setProperty('--mid-y', `${y * 10}px`);
  });

  function applyTilt(el, intensity = 1.5) {
    el.addEventListener('mousemove', (e) => {
      const rect = el.getBoundingClientRect();
      const rx = (e.clientX - rect.left) / rect.width;
      const ry = (e.clientY - rect.top) / rect.height;
      const tiltX = (ry - 0.5) * -2 * intensity;
      const tiltY = (rx - 0.5) * 2 * intensity;
      el.style.transform = `rotateX(${tiltX}deg) rotateY(${tiltY}deg) translateZ(${intensity * 2}px)`;
    });
    el.addEventListener('mouseleave', () => {
      el.style.transform = 'rotateX(0deg) rotateY(0deg) translateZ(0)';
    });
  }
  applyTilt(chatShell, 2);
  document.querySelectorAll('.tilt').forEach((el) => {
    const intensity = parseFloat(el.dataset.tilt || '1.3');
    applyTilt(el, intensity);
  });
}

// ============ Chat transport: SSE stream with fallback ============
async function postJSON(url, body) {
  const res = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body)
  });
  return res;
}

async function sendQuestion(question) {
  const thinking = addMessage('assistant', '', { thinking: true });
  setTypingBubble(thinking);
  statusEl.textContent = 'Thinking…';

  // Try SSE stream
  let streamed = false;
  try {
    const ctrl = new AbortController();
    const res = await fetch(`${API_BASE}/api/chat/stream`, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ question }),
      signal: ctrl.signal
    });

    if (res.ok && res.headers.get('content-type')?.includes('text/event-stream')) {
      streamed = true;
      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let acc = '';

      // Replace thinking bubble with live message
      thinking.classList.remove('thinking');
      const live = thinking.querySelector('.bubble');

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        const chunk = decoder.decode(value, { stream: true });
        const lines = chunk.split('\n\n');
        for (const line of lines) {
          if (!line.startsWith('data:')) continue;
          const data = line.slice(5).trim();
          if (data === '[DONE]') { break; }
          acc += data;
          live.innerHTML = renderMarkdownLite(acc);
          upgradeCopyButtons(live.parentElement);
          messagesEl.scrollTop = messagesEl.scrollHeight;
        }
      }
      statusEl.textContent = 'Ready';
      return;
    }
  } catch(_) {
    // ignore streaming failures and fallback
  }

  if (!streamed) {
    // Fallback: standard JSON call
    try {
      const res = await postJSON(`${API_BASE}/api/chat`, { question });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      const html = renderMarkdownLite(data.answer || 'No answer.');
      thinking.classList.remove('thinking');
      const bubble = thinking.querySelector('.bubble');
      bubble.innerHTML = html;
      upgradeCopyButtons(thinking);
      statusEl.textContent = 'Ready';
    } catch (e) {
      thinking.classList.remove('thinking');
      thinking.querySelector('.bubble').textContent = '⚠️ Sorry, something went wrong.';
      statusEl.textContent = 'Error';
    }
  }
}

// ============ Form & UI bindings ============
form.addEventListener('submit', (e) => {
  e.preventDefault();
  const question = input.value.trim();
  if (!question) return;
  addMessage('user', question);
  input.value = '';
  sendQuestion(question);
});

// About modal
function openAbout() { aboutModal.classList.remove('hidden'); aboutModal.setAttribute('aria-hidden', 'false'); }
function closeAbout() { aboutModal.classList.add('hidden'); aboutModal.setAttribute('aria-hidden', 'true'); }
aboutBtn.addEventListener('click', openAbout);
aboutClose.addEventListener('click', closeAbout);
aboutModal.addEventListener('click', (e) => { if (e.target === aboutModal) closeAbout(); });
window.addEventListener('keydown', (e) => { if (e.key === 'Escape') closeAbout(); });

// Set about avatar image using asset base (supports cross-origin)
(function(){
  const ASSET_BASE = (typeof window !== 'undefined' && window.__ASSET_BASE__) ? window.__ASSET_BASE__ : API_BASE;
  const avatarEl = document.querySelector('.avatar.galaxy');
  if (avatarEl) {
    const imgUrl = (ASSET_BASE ? ASSET_BASE : '') + '/images/about_avatar.jpg';
    avatarEl.style.backgroundImage = `url('${imgUrl}')`;
    avatarEl.style.backgroundSize = 'cover';
    avatarEl.style.backgroundPosition = 'center';
  }
})();

// Clear chat
clearBtn.addEventListener('click', () => {
  messagesEl.innerHTML = '';
  addMessage('assistant', 'Chat cleared. Ask me anything about Freshservice APIs.');
});


// ============ Premium 3D Tilt + Reactive Glow (About Modal) ============
let aboutCard = document.querySelector('.modal-card'); // avoid redeclare
if (aboutCard) {
  aboutCard.classList.add('tilt-3d');

  aboutCard.addEventListener('mousemove', (e) => {
    const rect = aboutCard.getBoundingClientRect();
    const x = (e.clientX - rect.left) / rect.width - 0.5;
    const y = (e.clientY - rect.top) / rect.height - 0.5;

    const rotateX = y * -12;
    const rotateY = x * 12;
    aboutCard.style.transform = `rotateX(${rotateX}deg) rotateY(${rotateY}deg) scale(1.03)`;
    aboutCard.style.boxShadow = `0 ${20 - y * 20}px ${60 + x * 20}px rgba(0,0,0,0.4)`;

    // Dynamic glow response for ::before radial gradient
    aboutCard.style.setProperty('--mx', `${(x + 0.5) * 100}%`);
    aboutCard.style.setProperty('--my', `${(y + 0.5) * 100}%`);
  });

  aboutCard.addEventListener('mouseleave', () => {
    aboutCard.style.transform = 'rotateX(0deg) rotateY(0deg) scale(1)';
    aboutCard.style.boxShadow = '0 25px 60px rgba(0,0,0,0.5)';
  });
}

// ============ Aurora Particles (GPU-friendly) ============
(() => {
  const motionOk = !window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const canvas = document.getElementById('aurora');
  if (!canvas || !motionOk) return;

  const ctx = canvas.getContext('2d', { alpha: true });
  let DPR = Math.max(1, Math.min(2, window.devicePixelRatio || 1));
  let W = 0, H = 0, particles = [], animId = null, lastTheme = null;

  function cssVar(name) {
    const styles = getComputedStyle(document.documentElement);
    return styles.getPropertyValue(name).trim();
  }

  function resize() {
    W = canvas.clientWidth = window.innerWidth;
    H = canvas.clientHeight = window.innerHeight;
    canvas.width = Math.floor(W * DPR);
    canvas.height = Math.floor(H * DPR);
    ctx.setTransform(DPR, 0, 0, DPR, 0, 0);
  }

  function genPalette() {
    // Pull current site accents (distinct from modal's)
    const p = cssVar('--accent-primary') || '#4E9CF5';
    const s = cssVar('--accent-secondary') || '#6C63FF';
    return [p, s];
  }

  function spawnParticles() {
    particles = [];
    const [c1, c2] = genPalette();
    const N = Math.round(Math.min(80, 40 + Math.sqrt(W * H) / 20));
    for (let i = 0; i < N; i++) {
      particles.push({
        x: Math.random() * W,
        y: Math.random() * H,
        r: 60 + Math.random() * 160,
        dx: (-0.25 + Math.random() * 0.5) * 0.6,
        dy: (-0.25 + Math.random() * 0.5) * 0.6,
        hueA: c1,
        hueB: c2,
        a: 0.08 + Math.random() * 0.08,
      });
    }
  }

  function blendCircle(gx, gy, r, colorA, colorB, alpha) {
    const g = ctx.createRadialGradient(gx, gy, 0, gx, gy, r);
    g.addColorStop(0, colorA + (colorA.includes('rgba') ? '' : ''));
    g.addColorStop(1, colorB + (colorB.includes('rgba') ? '' : ''));
    ctx.globalAlpha = alpha;
    ctx.globalCompositeOperation = 'lighter';
    ctx.fillStyle = g;
    ctx.beginPath();
    ctx.arc(gx, gy, r, 0, Math.PI * 2);
    ctx.fill();
  }

  function loop() {
    animId = requestAnimationFrame(loop);
    // Detect theme change and re-seed palette
    const theme = document.documentElement.getAttribute('data-theme');
    if (theme !== lastTheme) {
      lastTheme = theme;
      spawnParticles();
    }

    ctx.clearRect(0, 0, W, H);

    for (const p of particles) {
      p.x += p.dx;
      p.y += p.dy;

      // wrap around edges for infinite space
      if (p.x < -p.r) p.x = W + p.r;
      if (p.x > W + p.r) p.x = -p.r;
      if (p.y < -p.r) p.y = H + p.r;
      if (p.y > H + p.r) p.y = -p.r;

      blendCircle(p.x, p.y, p.r, p.hueA, p.hueB, p.a);
    }
  }

  function start() {
    resize();
    spawnParticles();
    loop();
  }

  function stop() {
    if (animId) cancelAnimationFrame(animId);
    animId = null;
  }

  window.addEventListener('resize', () => {
    resize();
    // keep density consistent on resize
    spawnParticles();
  });

  document.addEventListener('visibilitychange', () => {
    if (document.hidden) stop(); else start();
  });

  start();
})();

// Subtle chat-shell tilt and parallax (same family as modal)
(() => {
  const shell = document.getElementById('chat-shell');
  if (!shell) return;
  let active = false;

  shell.addEventListener('mousemove', (e) => {
    const rect = shell.getBoundingClientRect();
    const x = (e.clientX - rect.left) / rect.width - 0.5;
    const y = (e.clientY - rect.top) / rect.height - 0.5;
    shell.style.transform = `rotateX(${y * -4}deg) rotateY(${x * 4}deg) translateZ(10px)`;
    active = true;
  });

  shell.addEventListener('mouseleave', () => {
    if (!active) return;
    shell.style.transform = 'rotateX(0deg) rotateY(0deg)';
    active = false;
  });
})();


// Init
renderQuickReplies();
addMessage('assistant', 'Hi! Ask me anything about Freshservice APIs. Try the quick replies below.');
