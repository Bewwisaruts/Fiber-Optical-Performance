/*
 * auth-client.js — ระบบ auth ฝั่ง frontend ใช้ร่วมกันทุกหน้า dashboard
 * ผูกกับ backend endpoint /api/login ใน fast.py (ผ่าน auth.py)
 *
 * วิธีใช้ในแต่ละหน้า HTML:
 *   1. ใส่ <script src="auth-client.js"></script> ไว้ใน <head> (ก่อน script อื่นๆ)
 *   2. เปลี่ยนทุก fetch('http://localhost:8000/...') เป็น authFetch('http://localhost:8000/...')
 *   3. (ถ้ามี) ใส่ <span id="navUsername"></span> ตรงไหนก็ได้ให้โชว์ชื่อผู้ใช้ที่ login อยู่
 */
(function () {
  'use strict';

  var TOKEN_KEY = 'nem_token';
  var USERNAME_KEY = 'nem_username';
  var ROLE_KEY = 'nem_role';
  var LOGIN_PAGE = 'Longin.html';

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
  });
})();