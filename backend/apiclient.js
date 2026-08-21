/**
 * api-client.js
 * ================
 * ไฟล์กลางที่ทุกหน้า dashboard include เพื่อ:
 *   1. เช็คว่า login แล้วหรือยัง (redirect ไป Login.html ถ้ายัง)
 *   2. แนบ Authorization header ให้ทุก fetch ไปยัง backend อัตโนมัติ
 *   3. ซ่อนปุ่ม Import/Export ถ้า role เป็น visitor
 *   4. แสดง badge ชื่อผู้ใช้ + ปุ่ม Logout มุมขวาบน (inject อัตโนมัติ ไม่ต้องแก้ HTML)
 *   5. ให้ฟังก์ชันช่วย upload หลายไฟล์พร้อมกัน และ export ตารางเป็น Excel
 *
 * วิธีใช้: ใส่ <script src="common/api-client.js"></script> ไว้ก่อนแท็ก </body>
 * ของทุกหน้า (หรือใน <head> ก็ได้ เพราะ logic รันหลัง DOMContentLoaded)
 */
(function () {
  'use strict';

  const API_BASE = 'http://localhost:8000';

  function getToken() {
    return localStorage.getItem('access_token');
  }
  function getUser() {
    try {
      return JSON.parse(localStorage.getItem('user') || 'null');
    } catch (e) {
      return null;
    }
  }
  function clearAuth() {
    localStorage.removeItem('access_token');
    localStorage.removeItem('user');
  }
  function goToLogin() {
    clearAuth();
    const here = encodeURIComponent(location.pathname.split('/').pop() || 'index.html');
    location.href = 'Login.html?next=' + here;
  }

  /**
   * apiFetch: ใช้แทน fetch() ธรรมดาสำหรับเรียก backend ที่ต้อง login
   * แนบ Authorization header ให้อัตโนมัติ และ redirect ไปหน้า login ถ้าโทเคนหมดอายุ/ไม่ถูกต้อง (401)
   */
  async function apiFetch(url, options) {
    options = options || {};
    const token = getToken();
    if (!token) {
      goToLogin();
      return Promise.reject(new Error('ยังไม่ได้เข้าสู่ระบบ'));
    }
    options.headers = Object.assign({}, options.headers, { Authorization: 'Bearer ' + token });
    const res = await fetch(url, options);
    if (res.status === 401) {
      goToLogin();
      return Promise.reject(new Error('เซสชันหมดอายุ'));
    }
    return res;
  }

  /**
   * ดาวน์โหลดข้อมูลตาราง table_name เป็นไฟล์ .xlsx ผ่าน browser
   */
  async function downloadExport(tableName) {
    const user = getUser();
    if (!user || (user.role !== 'owner' && user.role !== 'admin')) {
      alert('เฉพาะ Owner หรือ Admin เท่านั้นที่ export ข้อมูลได้');
      return;
    }
    try {
      const res = await apiFetch(API_BASE + '/api/export?table_name=' + encodeURIComponent(tableName));
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: 'Export ล้มเหลว' }));
        alert('Export ล้มเหลว: ' + (err.detail || res.statusText));
        return;
      }
      const blob = await res.blob();
      const disposition = res.headers.get('Content-Disposition') || '';
      const match = disposition.match(/filename="?([^"]+)"?/);
      const filename = match ? match[1] : tableName + '.xlsx';
      const objUrl = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = objUrl;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(objUrl);
    } catch (err) {
      console.error(err);
      alert('เกิดข้อผิดพลาดขณะ export: ' + err.message);
    }
  }

  /**
   * uploadMultipleFiles: ส่งไฟล์หลายไฟล์พร้อมกันไปที่ /api/upload ในคำขอเดียว
   * fileList = FileList จาก <input type="file" multiple>
   * onStatus(message, isSuccess) = callback ไว้แสดงผลบนหน้าเว็บ (เช่น showUploadMsg เดิม)
   * คืนค่า response JSON เต็มๆ (มี field results เป็น array รายละเอียดต่อไฟล์)
   */
  async function uploadMultipleFiles(fileList, onStatus) {
    const files = Array.from(fileList || []);
    if (!files.length) return null;

    const formData = new FormData();
    files.forEach(function (f) {
      formData.append('files', f);
    });

    if (onStatus) onStatus('กำลังอัปโหลด ' + files.length + ' ไฟล์...', true);

    try {
      const res = await apiFetch(API_BASE + '/api/upload', { method: 'POST', body: formData });
      const data = await res.json();
      if (!res.ok) {
        if (onStatus) onStatus('อัปโหลดล้มเหลว: ' + (data.detail || data.message || res.statusText), false);
        return data;
      }
      if (onStatus) onStatus(data.message || 'อัปโหลดเสร็จสิ้น', data.status === 'success');
      return data;
    } catch (err) {
      if (onStatus) onStatus('อัปโหลดล้มเหลว: เชื่อมต่อเซิร์ฟเวอร์ไม่ได้', false);
      throw err;
    }
  }

  function injectUserBadge(user) {
    if (document.getElementById('authUserBadge')) return;
    const roleColor = user.role === 'owner' ? '#F2954D' : user.role === 'admin' ? '#34D6BE' : '#8996A6';
    const badge = document.createElement('div');
    badge.id = 'authUserBadge';
    badge.style.cssText =
      'position:fixed;top:12px;right:12px;z-index:99999;' +
      "background:#121821;border:1px solid #232D3A;border-radius:999px;padding:7px 14px;" +
      "font-family:'JetBrains Mono',monospace;font-size:12px;color:#E7EDF4;" +
      'display:flex;align-items:center;gap:10px;box-shadow:0 4px 14px rgba(0,0,0,.5);';
    badge.innerHTML =
      '<span style="color:' + roleColor + ';font-weight:700;text-transform:uppercase;font-size:10px;letter-spacing:.04em;">' +
      user.role +
      '</span>' +
      '<span>' + (user.username || '') + '</span>' +
      (user.role === 'owner'
        ? '<a href="UserManagement.html" style="color:#34D6BE;text-decoration:none;">Users</a>'
        : '') +
      '<button id="authLogoutBtn" style="background:none;border:none;color:#8996A6;cursor:pointer;font-family:inherit;font-size:12px;padding:0;">Logout</button>';
    document.body.appendChild(badge);
    document.getElementById('authLogoutBtn').addEventListener('click', function () {
      clearAuth();
      location.href = 'Login.html';
    });
  }

  function applyRoleRestrictions(user) {
    if (user.role === 'visitor') {
      // ซ่อนปุ่ม Import/Export ถ้ามี id มาตรฐานเหล่านี้อยู่ในหน้า (visitor ดูได้อย่างเดียว)
      ['uploadBtn', 'fileInput', 'exportBtn', 'uploadStatus'].forEach(function (id) {
        const el = document.getElementById(id);
        if (el) el.style.display = 'none';
      });
    }
  }

  /**
   * guardPage: เรียกอัตโนมัติทุกหน้าที่ include ไฟล์นี้
   * เช็ค token -> validate กับ backend -> inject badge -> ซ่อนปุ่มตาม role
   * ถ้าไม่ผ่านจะ redirect ไป Login.html ให้เอง
   */
  async function guardPage() {
    const token = getToken();
    if (!token) {
      goToLogin();
      return;
    }
    try {
      const res = await fetch(API_BASE + '/api/auth/me', {
        headers: { Authorization: 'Bearer ' + token },
      });
      if (!res.ok) {
        goToLogin();
        return;
      }
      const json = await res.json();
      localStorage.setItem('user', JSON.stringify(json.user));
      injectUserBadge(json.user);
      applyRoleRestrictions(json.user);
    } catch (err) {
      console.error('auth check failed', err);
      goToLogin();
    }
  }

  window.NEM_AUTH = {
    apiFetch: apiFetch,
    getToken: getToken,
    getUser: getUser,
    clearAuth: clearAuth,
    goToLogin: goToLogin,
    downloadExport: downloadExport,
    uploadMultipleFiles: uploadMultipleFiles,
    guardPage: guardPage,
    API_BASE: API_BASE,
  };

  document.addEventListener('DOMContentLoaded', guardPage);
})();