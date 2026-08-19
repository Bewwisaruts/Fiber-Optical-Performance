(function () {
  'use strict';

  var TOKEN_KEY = 'nem_token';
  var USERNAME_KEY = 'nem_username';
  var ROLE_KEY = 'nem_role';
  var LOGIN_PAGE = 'Login.html';

  function getToken() { return localStorage.getItem(TOKEN_KEY); }
  function getUsername() { return localStorage.getItem(USERNAME_KEY) || ''; }
  function getRole() { return localStorage.getItem(ROLE_KEY) || ''; }

  function setSession(token, username, role) {
    localStorage.setItem(TOKEN_KEY, token);
    localStorage.setItem(USERNAME_KEY, username || '');
    localStorage.setItem(ROLE_KEY, role || '');
  }

  function clearSession() {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USERNAME_KEY);
    localStorage.removeItem(ROLE_KEY);
  }

  function logout() {
    clearSession();
    window.location.href = LOGIN_PAGE;
  }

  // เช็คก่อนว่ามี token ไหม ถ้าไม่มีเด้งไปหน้า login ทันที (กันหน้าโหลดค้างรอ fetch แล้วค่อย 401)
  function requireAuth() {
    if (!getToken()) {
      window.location.href = LOGIN_PAGE;
    }
  }

  // ใช้แทน fetch() ปกติเวลาเรียก backend — แนบ Authorization header ให้อัตโนมัติ
  // และเด้งไปหน้า login อัตโนมัติถ้า token หมดอายุ/ไม่ถูกต้อง (401)
  async function authFetch(url, options) {
    options = options || {};
    var headers = Object.assign({}, options.headers || {});
    var token = getToken();
    if (token) headers['Authorization'] = 'Bearer ' + token;
    options.headers = headers;

    var res = await fetch(url, options);
    if (res.status === 401) {
      clearSession();
      window.location.href = LOGIN_PAGE;
      throw new Error('Unauthorized — redirecting to login');
    }
    return res;
  }

  function paintUserBadge() {
    var el = document.getElementById('navUsername');
    if (el) el.textContent = getUsername() + (getRole() ? ' (' + getRole() + ')' : '');
  }

  // แทรกลิงก์ "User Management" ให้เฉพาะ role owner เท่านั้น
  // - ถ้าหน้ามี side-nav (.side-nav-menu) จะแทรกเป็นรายการก่อนปุ่ม Logout
  // - ถ้าไม่มี side-nav (เช่น index.html) จะแทรกเป็นปุ่มไว้ข้างๆ #navUsername ใน header
  function injectOwnerNav() {
    if (getRole() !== 'owner') return;

    var menu = document.querySelector('.side-nav-menu');
    if (menu) {
      if (menu.querySelector('a[href="Users.html"]')) return; // กันแทรกซ้ำ
      var logoutLi = null;
      var items = menu.querySelectorAll('li.side-nav-item');
      for (var i = 0; i < items.length; i++) {
        if (items[i].querySelector('button[onclick="logout()"]')) { logoutLi = items[i]; break; }
      }
      var li = document.createElement('li');
      li.className = 'side-nav-item';
      li.innerHTML = '<a href="Users.html" class="side-nav-link">\u{1F464} User Management</a>';
      if (logoutLi) menu.insertBefore(li, logoutLi);
      else menu.appendChild(li);
      return;
    }

    // fallback: หน้าที่ไม่มี side-nav (index.html) — วางปุ่มไว้ข้าง navUsername ใน header
    var navUser = document.getElementById('navUsername');
    if (navUser && !document.querySelector('a[href="Users.html"]')) {
      var btn = document.createElement('a');
      btn.href = 'Users.html';
      btn.textContent = 'User Management';
      btn.style.cssText = 'background:var(--panel); border:1px solid var(--border-soft); color:var(--accent);' +
        ' border-radius:8px; padding:6px 12px; font-family:var(--font-body); font-size:12.5px;' +
        ' font-weight:600; text-decoration:none; white-space:nowrap;';
      var parent = navUser.parentElement;
      if (parent) parent.insertBefore(btn, navUser.nextSibling);
    }
  }

  // เปิดให้ทุกหน้าเรียกใช้ได้แบบ global
  window.getToken = getToken;
  window.getUsername = getUsername;
  window.getRole = getRole;
  window.setSession = setSession;
  window.clearSession = clearSession;
  window.logout = logout;
  window.authFetch = authFetch;

  // สำคัญ: ต้องรันก่อน DOMContentLoaded handler อื่นๆ ในหน้า ดังนั้น
  // <script src="auth-client.js"> ต้องอยู่ก่อน <script> หลักของแต่ละหน้าเสมอ
  document.addEventListener('DOMContentLoaded', function () {
    requireAuth();
    paintUserBadge();
    injectOwnerNav();
  });
})();